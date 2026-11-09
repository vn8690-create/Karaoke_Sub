# Tenant Portal UI Rework

**Date**: 2026-03-04
**Branch**: `feat/sess-20260304-0007-tenant-ui-rework`
**Worktree**: `karaoke-gen-tenant-ui-rework`
**Status**: Implementation + Config Complete — Ready for PR

## Context

The tenant portal at `vocalstar.nomadkaraoke.com` shows the same 3-step consumer wizard (song search -> audio source -> customize) designed for end users. B2B white-label customers like Vocal Star always provide their own mixed audio AND instrumental files. They don't need audio search, YouTube URL input, theme selection, privacy toggles, or customization options.

**Goal**: Replace the multi-step wizard with a streamlined 4-field form (Artist, Title, Mixed Audio, Instrumental Audio) for tenant portals. All tracks are automatically private, delivered to tenant-specific Dropbox/Google Drive folders, with tenant brand codes and styling.

## Implementation Plan

### Phase 1: Backend — Tenant Distribution Defaults

| Step | File | Change | Status |
|------|------|--------|--------|
| 1.1 | `backend/models/tenant.py` | Add `dropbox_path`, `gdrive_folder_id` to TenantDefaults | Done |
| 1.2 | `backend/api/routes/file_upload.py` | Create `_apply_tenant_overrides()`, call in 2 endpoints | Done |
| 1.3 | `backend/services/job_defaults_service.py` | Tenant-aware private job handling (skip NonPublished override) | Done |
| 1.4 | `frontend/lib/api.ts` | Add `existing_instrumental` flag to createJobWithUploadUrls | Done |
| 1.5 | `backend/tests/test_tenant_job_defaults.py` | 9 unit tests for tenant override logic | Done |

**1.1 Details**: Two new Optional fields on TenantDefaults:
- `dropbox_path: Optional[str]` — e.g., `/Karaoke/Vocal-Star`
- `gdrive_folder_id: Optional[str]` — tenant GDrive folder ID

Already excluded from TenantPublicConfig (line 194 only copies theme_id, locked_theme, distribution_mode).

**1.2 Details**: `_apply_tenant_overrides(dist, tenant_config, body)` helper that:
1. Overlays tenant `brand_prefix`, `dropbox_path`, `gdrive_folder_id` onto EffectiveDistributionSettings
2. Forces `is_private = True` for all tenant jobs
3. Applies `locked_theme` as effective theme
4. Disables YouTube upload

Called in: `create_job_with_upload_urls` (line 971) and `upload_and_create_job` (line 324).

**1.3 Details**: In `get_effective_distribution_for_job` (line 64), if `job.tenant_id` is set AND `is_private=True`, skip the NonPublished path override. Use job's own distribution fields (which contain tenant defaults from creation). Still disable YouTube.

**1.4 Details**: The backend `CreateJobWithUploadUrlsRequest` already has `existing_instrumental: bool` (line 170). Frontend `api.ts` `createJobWithUploadUrls()` just needs to pass it through in the request body.

**1.5 Tests**:
- `test_tenant_defaults_applied_to_distribution` — brand_prefix, dropbox_path, gdrive_folder_id applied
- `test_tenant_job_forced_private` — is_private always True for tenant jobs
- `test_tenant_locked_theme_applied` — locked_theme overrides user theme
- `test_private_tenant_job_uses_tenant_paths` — uses tenant Dropbox/GDrive, NOT NonPublished
- `test_non_tenant_private_job_still_uses_nonpublished` — existing behavior preserved

### Phase 2: Frontend — TenantJobFlow Component

| Step | File | Change | Status |
|------|------|--------|--------|
| 2.1 | `frontend/components/job/TenantJobFlow.tsx` | **Create** single-page 4-field form | Done |
| 2.2 | `frontend/app/app/page.tsx` | TenantLogo in header, conditional form rendering | Done |
| 2.3 | `frontend/__tests__/tenant-job-flow.test.tsx` | Component tests (4 tests) | Done |

**2.1 Details**: Single-page form (~250 lines) with:
- Artist text input, Title text input
- Mixed Audio file upload (drag-and-drop, accepts .mp3,.wav,.flac,.m4a,.ogg,.aac)
- Instrumental Audio file upload (same types)
- Submit button (disabled until all 4 fields filled)
- Submission: `createJobWithUploadUrls` -> `uploadToSignedUrl` x2 -> `completeJobUpload`
- Success view: simplified timeline (review lyrics -> video delivered), "Create Another" button
- Omits "audio processing" step since instrumental is provided

**2.2 Details**:
- Replace hardcoded `<img src="/nomad-karaoke-logo.svg">` (line 196) with `<TenantLogo size="sm" />`
- Tenant-aware title using `branding.site_title`
- Conditional: `<TenantJobFlow>` when `!isDefault`, else `<GuidedJobFlow>`
- Card text: "Submit Track" / "Upload your mixed audio and instrumental" for tenants
- Hide feedback banner for non-default users

### Phase 3: Config & Deployment

| Step | Change | Status |
|------|--------|--------|
| 3.1 | Update Vocalstar tenant config in GCS | Done |
| 3.2 | Post-deploy setup tasks | Done — all verified |

Config additions needed:
```json
{
  "defaults": {
    "locked_theme": "vocalstar",
    "distribution_mode": "cloud_only",
    "brand_prefix": "VSTAR",
    "dropbox_path": "<user-to-provide>",
    "gdrive_folder_id": "<user-to-provide>"
  },
  "features": {
    "audio_search": false,
    "file_upload": true,
    "youtube_url": false,
    "youtube_upload": false,
    "theme_selection": false,
    "color_overrides": false
  }
}
```

### Phase 4: Production Verification

| Step | File | Change | Status |
|------|------|--------|--------|
| 4.1 | `frontend/e2e/production/tenant-job-submission.spec.ts` | **Create** Playwright E2E test (3 tests) | Done |

Full lifecycle: navigate tenant portal -> verify branding -> submit track -> wait for processing -> approve reviews -> verify outputs delivered to tenant paths.

## Key Files

| File | Action |
|------|--------|
| `backend/models/tenant.py` | Modify — add 2 fields to TenantDefaults |
| `backend/api/routes/file_upload.py` | Modify — add `_apply_tenant_overrides()`, call in 2 endpoints |
| `backend/services/job_defaults_service.py` | Modify — tenant-aware private job handling |
| `frontend/components/job/TenantJobFlow.tsx` | **Create** — new simplified 4-field form |
| `frontend/app/app/page.tsx` | Modify — TenantLogo in header, conditional form |
| `frontend/lib/api.ts` | Modify — add `existing_instrumental` flag |
| `backend/tests/test_tenant_job_defaults.py` | **Create** — backend tests |
| `frontend/__tests__/components/job/TenantJobFlow.test.tsx` | **Create** — component tests |
| `frontend/e2e/production/tenant-job-submission.spec.ts` | **Create** — E2E prod test |

## Implementation Log

### Phase 1 — Backend (Complete)
- Added `dropbox_path` and `gdrive_folder_id` to `TenantDefaults` model
- Created `_apply_tenant_overrides()` helper in `file_upload.py` — overlays tenant config, forces private, applies locked_theme, disables YouTube
- Wired into both `upload_and_create_job` and `create_job_with_upload_urls` endpoints
- Fixed `get_effective_distribution_for_job` to respect tenant paths for private jobs (skips NonPublished override when `tenant_id` is set)
- Added `existing_instrumental` option to frontend `api.createJobWithUploadUrls()`
- 9 unit tests in `test_tenant_job_defaults.py` — all pass

### Phase 2 — Frontend (Complete)
- Created `TenantJobFlow.tsx` (~300 lines) — 4-field form with drag-and-drop, progress tracking, success timeline
- Updated `app/page.tsx`:
  - `TenantLogo` component in header (replaces hardcoded Nomad logo for tenants)
  - Tenant-aware title using `branding.site_title`
  - Conditional rendering: `TenantJobFlow` for tenants, `GuidedJobFlow` for consumers
  - Card titles/descriptions adapted per mode
  - Feedback banner hidden for tenants
- 4 component tests in `tenant-job-flow.test.tsx` — all pass (520/520 total)

### Phase 3 — Config (Complete)
- Updated `gs://karaoke-gen-storage-nomadkaraoke/tenants/vocalstar/config.json`:
  - `distribution_mode`: "download_only" → "cloud_only"
  - `dropbox_upload`/`gdrive_upload`: false → true
  - Added `dropbox_path`: "/MediaUnsynced/Karaoke/Tracks-VocalStar"
  - Added `gdrive_folder_id`: "15pKDJSh9uQSAJFbKlHsiiRLmFCUkYZPc"
- Verified: `vocalstar` theme exists with style_params.json + 6 assets (font, backgrounds)
- Verified: logo.jpg accessible via API asset endpoint (85KB, 200 OK)

### Phase 4 — E2E (Complete)
- Created `tenant-job-submission.spec.ts` with 3 tests:
  1. Tenant portal shows simplified form (not consumer wizard)
  2. Full track submission flow
  3. Consumer portal still works normally
