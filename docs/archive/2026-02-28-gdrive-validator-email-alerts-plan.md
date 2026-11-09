# GDrive Validator: Email Alerts, Manual Trigger, Post-Job Check

## Context

The GDrive validator cloud function checks the public Google Drive share for duplicate brand codes, invalid filenames, and sequence gaps. Currently it:
- Runs once daily at 9 PM Eastern via Cloud Scheduler
- Sends results via Pushbullet (easy to miss, no persistent record)
- Cannot be easily triggered manually
- Doesn't run after each job, so issues can persist for up to 24 hours before detection

The recent NOMAD-1271 duplicate brand code incident showed that daily checks aren't frequent enough — the duplicate existed for at least a day before manual discovery.

## Changes

### 1. Cloud Function: Replace Pushbullet with Email (SendGrid)

**File:** `infrastructure/functions/gdrive_validator/main.py`

- Replace `send_pushbullet_notification()` with `send_email_notification()` using SendGrid API
- SendGrid API key already in Secret Manager as `sendgrid-api-key`
- Send from `gen@nomadkaraoke.com` to `gen@nomadkaraoke.com`
- Keep Pushbullet as a secondary fallback (both are cheap; belt + suspenders)
- Add `SENDGRID_API_KEY` env var to the function

**File:** `infrastructure/functions/gdrive_validator/requirements.txt`

- Add `sendgrid>=6.0.0`

**File:** `infrastructure/__main__.py`

- Add `sendgrid-api-key` secret to the function's `secret_environment_variables`
- Add `EMAIL_TO` env var = `gen@nomadkaraoke.com`

**File:** `infrastructure/functions/gdrive_validator/deploy.sh`

- Add `--set-secrets` entry for `SENDGRID_API_KEY=sendgrid-api-key:latest`
- Add `--set-env-vars` entry for `EMAIL_TO=gen@nomadkaraoke.com`

### 2. Local Command: `check_public_share`

**File:** `scripts/check_public_share.py`

- Calls the Cloud Function via `gcloud functions call gdrive-validator --region=us-central1`
- Parses the JSON response and prints formatted results to terminal
- Exit code 0 = all clear, 1 = issues found, 2 = error
- Supports `--json` flag for raw JSON output

### 3. Post-Job Trigger from Backend

**File:** `backend/services/gdrive_validator_client.py` (new)

- Lightweight client that calls the Cloud Function via HTTP with OIDC token
- Uses `google.oauth2.id_token.fetch_id_token()` for authentication
- Fire-and-forget pattern (never blocks or fails the job)
- Logs the response but does not raise on validation issues (just notifies)

**File:** `backend/workers/video_worker_orchestrator.py`

- After `_run_notifications()` (line ~253), add a new call: `await self._trigger_gdrive_validation()`
- Only triggers for non-private, non-test jobs (private jobs don't upload to public share)
- Wrapped in try/except so validation failure never blocks job completion

**File:** `infrastructure/__main__.py`

- Add IAM binding: grant `karaoke-backend` service account `roles/cloudfunctions.invoker` on the gdrive-validator function
- For Gen2 functions also need `roles/run.invoker` on the underlying Cloud Run service

**File:** `infrastructure/modules/iam/backend_sa.py`

- Add the Cloud Functions invoker permission

### 4. Pulumi Infrastructure Updates

All IAM and secret changes go through `infrastructure/__main__.py` — deployed automatically on merge to main.

## Comparison: Local Script vs Cloud Function

| Check | Local Script | Cloud Function |
|-------|-------------|----------------|
| Duplicate sequence numbers | ✅ | ✅ |
| Invalid filenames | ✅ | ✅ |
| Sequence gaps (with known gaps) | ✅ | ✅ |
| Known gaps config | ✅ (identical) | ✅ (identical) |
| ZIP contents (MP3+CDG) | ✅ | ❌ (expensive, needs file download) |
| Video resolution (4K/720p) | ✅ | ❌ (expensive, needs file download) |
| Render quality (pixel check) | ✅ | ❌ (expensive, needs ffmpeg) |
| Bidirectional sync | ✅ (rclone) | ❌ (read-only) |

The cloud function correctly implements the "quick/cheap" checks (metadata-only via GDrive API). The expensive content checks (ZIP, resolution, pixel) belong in the local script since they require downloading files. No changes needed to align them.

## Files Modified

| File | Change |
|------|--------|
| `infrastructure/functions/gdrive_validator/main.py` | Add SendGrid email, keep Pushbullet as fallback |
| `infrastructure/functions/gdrive_validator/requirements.txt` | Add `sendgrid` |
| `infrastructure/functions/gdrive_validator/deploy.sh` | Add SendGrid secret + EMAIL_TO env var |
| `infrastructure/__main__.py` | Add SendGrid secret to function, add backend invoker IAM |
| `backend/services/gdrive_validator_client.py` | New: HTTP client to invoke cloud function |
| `backend/workers/video_worker_orchestrator.py` | Add post-distribution GDrive validation trigger |
| `scripts/check_public_share.py` | New: local command to trigger cloud function |

## Verification

1. Deploy cloud function with `./deploy.sh`
2. Run `python scripts/check_public_share.py` — should print formatted results and receive email at gen@nomadkaraoke.com
3. Trigger a test job or wait for the daily E2E test — after job completes, check Cloud Function logs to confirm it was invoked
4. Check gen@nomadkaraoke.com inbox for the validation email
5. Run `make test` to verify no regressions
