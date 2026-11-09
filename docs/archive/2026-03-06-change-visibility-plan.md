# Change Visibility Plan

> **Date**: 2026-03-06
> **Branch**: `feat/sess-20260306-1750-change-visibility`
> **Status**: Draft

## Problem

Users who accidentally select the wrong visibility (public/private) during job creation have no way to change it after the job completes. Currently, only admins can toggle `is_private` via the PATCH endpoint, and when toggling to private it only auto-deletes outputs -- it doesn't re-distribute to the correct destination.

Example: Job `fdcc82a6` was accidentally created as private but should be public.

## Requirements

1. Any user who can see a job (creator or admin) can change visibility on completed jobs
2. A confirmation modal explains exactly what will happen before proceeding
3. Modal wording varies based on direction (public->private vs private->public)
4. Tenant jobs (Vocal Star, Singa) are excluded -- this is consumer gen only
5. No cooldown/rate limiting needed

## Two Distinct Flows

### Flow A: Public -> Private (simpler, faster)

The video content doesn't change -- same nomad theme, same screens. We just need to move outputs from public destinations to private ones.

**Steps:**
1. Delete distributed outputs (YouTube, Dropbox `/Tracks-Organized/`, GDrive) but **keep GCS finals**
2. Recycle the NOMAD brand code
3. Set `is_private = true` on the job
4. Re-run distribution only: allocate NOMADNP brand code, upload finals to Dropbox `/Tracks-NonPublished/`
5. Update job state_data with new brand_code and dropbox_link
6. Clear `outputs_deleted_at` flag
7. Mark job as complete

**Expected duration:** ~1-2 minutes (just file uploads)

### Flow B: Private -> Public (complex, slower)

Private jobs may have custom styles (backgrounds, colors) that don't conform to the public Nomad branding. We must reset to defaults and re-process from screens onward.

**Steps:**
1. Delete distributed outputs (Dropbox `/Tracks-NonPublished/`) + delete GCS finals + delete screens + delete `with_vocals.mkv`
2. Recycle the NOMADNP brand code
3. **Permanently clear custom style data:**
   - Reset `theme_id` to `"nomad"` (or whatever the default is)
   - Clear `color_overrides` to `{}`
   - Clear `style_assets` to `{}`
   - Delete any custom style files from GCS (`jobs/{job_id}/style/`)
4. Set `is_private = false` on the job
5. Set job status to `LYRICS_COMPLETE` (entry point for screens worker)
6. Clear relevant progress keys: `screens_progress`, `render_progress`, `video_progress`, `encoding_progress`
7. Trigger screens worker, which cascades through: screens -> awaiting_review (auto-skip, since review is already done) -> render -> encode -> distribute publicly
8. Job returns to `COMPLETE` with public outputs (YouTube, Dropbox `/Tracks-Organized/`, GDrive)

**Expected duration:** ~15-30 minutes (re-render + re-encode + distribute)

**Key gotcha:** After regenerating screens, the pipeline normally transitions to `AWAITING_REVIEW`. But we've already completed review -- we need to auto-skip review and proceed to rendering. We'll use a `regen_restore_status` mechanism (already exists for the `regenerate-screens` endpoint) to signal the screens worker to restore to `REVIEW_COMPLETE` instead of `AWAITING_REVIEW`, which triggers the render worker.

## Architecture

### New Backend Endpoint

```
POST /api/jobs/{job_id}/change-visibility
```

**Auth:** Requires authenticated user who is the job creator OR an admin.

**Request body:**
```json
{
  "target_visibility": "public" | "private"
}
```

**Response:**
```json
{
  "status": "success" | "processing" | "error",
  "job_id": "...",
  "message": "...",
  "previous_visibility": "public" | "private",
  "new_visibility": "public" | "private",
  "reprocessing_required": true | false
}
```

**Why a new endpoint instead of extending admin PATCH?**
- The PATCH endpoint is admin-only; this needs to work for regular users
- The logic is complex enough to warrant its own endpoint with clear semantics
- We need to orchestrate multiple steps atomically (delete outputs, update fields, trigger workers)
- The existing PATCH toggle-to-private behavior is kept as-is for admin convenience (backwards compat)

**Validation:**
- Job must be in `COMPLETE` status (not `FAILED`, `PREP_COMPLETE`, or in-progress)
- Job must not be a tenant job (`tenant_id` must be null)
- Target visibility must differ from current visibility
- Job must not already be undergoing a visibility change (guard against double-clicks)

### Backend Implementation Details

#### Public -> Private (distribution-only re-run)

This flow is novel -- we don't have an existing mechanism to re-run just distribution. Options:

**Option 1: Dedicated `_redistribute` function** (recommended)
Create a lightweight function that:
1. Downloads finals from GCS to a temp dir
2. Creates an OrchestratorConfig with private distribution settings
3. Runs only `_run_organization()` + `_run_distribution()` + `_run_notifications()` stages
4. Updates job state_data

This avoids re-encoding entirely. We'd extract the distribution stages into a callable unit.

**Option 2: Re-run full video worker with cached encoding**
The GCE encoding worker has a cache -- if the job was recently encoded, it returns cached results. But this is fragile (cache might be cleared) and still downloads/re-uploads files unnecessarily.

Going with Option 1.

**Implementation:**
- New function in `video_worker.py`: `async def redistribute_video(job_id: str) -> bool`
- Modeled after `generate_video_orchestrated()` but skips encoding
- Downloads existing finals from GCS `jobs/{job_id}/finals/`
- Creates orchestrator with appropriate distribution config
- Runs organization + distribution stages only

#### Private -> Public (full re-process)

This reuses existing infrastructure more directly:
1. Call modified `delete_job_outputs()` that also cleans up screens and rendered video
2. Reset style fields on the job document
3. Set status to `LYRICS_COMPLETE` with `regen_restore_status = "review_complete"`
4. Trigger screens worker via `worker_service.trigger_screens_worker(job_id)`
5. The screens worker generates screens, then sees `regen_restore_status` and restores to `REVIEW_COMPLETE`
6. `REVIEW_COMPLETE` triggers render worker -> video worker -> `COMPLETE`

**Issue: Screens worker `regen_restore_status` behavior**

Looking at the existing `regenerate-screens` endpoint (admin.py:2003), it sets `regen_restore_status` to the original status. The screens worker checks this and restores to that status instead of going to `AWAITING_REVIEW`.

For our case, we want to restore to `REVIEW_COMPLETE` (not back to `COMPLETE`), so the pipeline continues through render + encode. This fits the existing mechanism perfectly -- we just set `regen_restore_status = "review_complete"`.

**Issue: Screens worker does NOT auto-trigger the render worker**

Verified: The screens worker's `regen_restore_status` handling (screens_worker.py:197-204) just does a raw Firestore update to set the status -- it does **not** trigger any downstream worker. The render worker is only triggered from the `complete-review` API endpoint (jobs.py:992).

**Solution:** Modify the screens worker's `regen_restore_status` handling to also trigger the render worker when the restore status is `review_complete`. This is the cleanest approach because:
- The trigger logic stays in the worker pipeline (not in a separate polling mechanism)
- It's a small, focused change to `screens_worker.py`
- It reuses `worker_service.trigger_render_video_worker(job_id)`

```python
# In screens_worker.py, after restoring status:
if regen_restore_status == "review_complete":
    # Visibility change flow: trigger render worker to continue pipeline
    from backend.services.worker_service import get_worker_service
    worker_service = get_worker_service()
    await worker_service.trigger_render_video_worker(job_id)
```

#### Modified `delete_job_outputs` for Public -> Private

The current `delete_job_outputs()` always deletes GCS finals. For public->private, we need to keep them. Two approaches:

**Option A: Add `keep_gcs_finals` parameter** (recommended)
Add an optional parameter to `delete_job_outputs()`: `keep_gcs_finals: bool = False`. When True, skip the GCS finals deletion step. The endpoint still deletes YouTube/Dropbox/GDrive and recycles the brand code.

**Option B: Create separate helper function**
Extract the YouTube/Dropbox/GDrive deletion into a helper. More code duplication.

Going with Option A -- minimal change, backwards compatible.

### Frontend Implementation

#### Button Location

Add a "Change Visibility" button to the `OutputLinks` component (`frontend/components/job/OutputLinks.tsx`), visible when:
- Job status is `complete`
- Job is not a tenant job
- Job is not currently being re-processed (guard state)

The button shows the current visibility and what it would change to:
- For public jobs: "Make Private" with a Lock icon
- For private jobs: "Make Public" with a Globe icon

#### Confirmation Modal

Uses the existing `AlertDialog` component from `@radix-ui/react-alert-dialog`.

**Public -> Private modal:**
```
Title: Make This Track Private?

This will:
- Remove the video from YouTube
- Remove files from Google Drive
- Move Dropbox files from public to private folder
- Assign a new private brand code (NOMADNP)

The video content won't change. This usually takes about 1-2 minutes.

You can change it back to public later, but that will require
re-rendering the video (~15-30 minutes).

[Cancel] [Make Private]
```

**Private -> Public modal:**
```
Title: Make This Track Public?

This will:
- Remove any custom styling (backgrounds, colors) and
  reset to the standard Nomad Karaoke theme
- Regenerate title and end screens
- Re-render the karaoke video with default branding
- Publish to YouTube, Google Drive, and Dropbox

This process takes approximately 15-30 minutes. You'll receive
an email when it's complete.

Any custom styling you applied will be permanently removed.

[Cancel] [Make Public]
```

#### During Re-processing (Private -> Public)

While the job is being re-processed:
- The button is disabled and shows a spinner: "Changing to Public..."
- Job status will cycle through intermediate states (`LYRICS_COMPLETE` -> `GENERATING_SCREENS` -> etc.)
- The job card should show these intermediate statuses normally
- When it reaches `COMPLETE` again, the button returns to normal

For public->private, the change is fast enough (~1-2 min) that we can show a loading spinner on the button and poll for completion.

#### API Integration

New method in `frontend/lib/api.ts`:

```typescript
// In the public api object (not adminApi, since regular users can use this)
async changeVisibility(jobId: string, targetVisibility: 'public' | 'private'): Promise<ChangeVisibilityResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/jobs/${jobId}/change-visibility`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify({ target_visibility: targetVisibility }),
    }
  );
  return handleResponse(response);
}
```

## State Machine Considerations

New state transitions needed:
- `COMPLETE` -> `LYRICS_COMPLETE` (for private->public re-processing)

This transition doesn't currently exist in `STATE_TRANSITIONS`. We need to add it. The `COMPLETE` -> `LYRICS_COMPLETE` transition is safe because:
- We've already validated the job has completed audio+lyrics processing
- We're resetting screens/render/video progress markers
- The screens worker will pick up from `LYRICS_COMPLETE` as normal

Also need: `COMPLETE` -> `GENERATING_VIDEO` (for public->private redistribution, if we transition through video worker states during redistribution). Actually, for the redistribution-only path, we might want a simpler approach -- keep the job in `COMPLETE` status during redistribution since it's a fast operation, or use a new transient state.

**Decision:** For public->private (fast redistribution), we'll:
1. Set a flag `state_data.visibility_change_in_progress = true` to prevent concurrent changes
2. Keep status as `COMPLETE` (since the operation is fast and the job is still "complete")
3. Run redistribution in a background task
4. Clear the flag when done

For private->public (full re-process), we'll:
1. Set `visibility_change_in_progress = true`
2. Transition to `LYRICS_COMPLETE` (triggering the normal pipeline)
3. The flag gets cleared when the job reaches `COMPLETE` again

## Implementation Plan

### Phase 1: Backend - Change Visibility Endpoint

**Files to modify:**
- `backend/api/routes/jobs.py` -- Add `POST /jobs/{job_id}/change-visibility` endpoint
- `backend/api/routes/admin.py` -- Add `keep_gcs_finals` param to `delete_job_outputs()`
- `backend/models/job.py` -- Add `COMPLETE -> LYRICS_COMPLETE` state transition
- `backend/models/requests.py` -- Add request/response models

**Files to create:**
- `backend/services/visibility_change_service.py` -- Core logic for both flows

### Phase 2: Backend - Redistribution Function

**Files to modify:**
- `backend/workers/video_worker.py` -- Add `redistribute_video()` function
- `backend/workers/video_worker_orchestrator.py` -- Possibly extract distribution stages

### Phase 3: Frontend - Button + Modal

**Files to modify:**
- `frontend/components/job/OutputLinks.tsx` -- Add Change Visibility button + modal
- `frontend/lib/api.ts` -- Add `changeVisibility()` method + response types

### Phase 4: Testing

**Files to create:**
- `backend/tests/test_change_visibility.py` -- Unit tests for the visibility change service
- `backend/tests/test_redistribute.py` -- Unit tests for the redistribution function
- `frontend/e2e/production/change-visibility.spec.ts` -- E2E test (if feasible)

**Test cases:**
1. Public -> Private: outputs deleted, finals preserved, redistributed to private destination
2. Private -> Public: styles reset, screens regenerated, full pipeline completes
3. Validation: rejects non-complete jobs, tenant jobs, same-visibility changes, concurrent changes
4. Auth: job creator can change, admin can change, other users cannot
5. Edge cases: job with no YouTube URL, job with no brand code, job with outputs already deleted

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Pipeline fails mid-visibility-change (private->public) | Job stuck in intermediate state | Use existing `FAILED` state handling; admin can restart |
| GCS finals deleted before redistribution completes (public->private) | Need to re-encode | Use `keep_gcs_finals=True` to preserve them |
| Race condition: user clicks button twice | Double processing | `visibility_change_in_progress` guard flag |
| Screens worker doesn't auto-trigger render after regen | Pipeline stalls | **Resolved**: Modify screens worker to trigger render worker when `regen_restore_status == "review_complete"` |
| Custom style files left as orphans in GCS | Storage waste | Clean up `jobs/{job_id}/style/` during private->public |

## Open Questions (Resolved)

1. **Who can trigger?** Anyone who can see the job (creator or admin). -> New user-facing endpoint.
2. **Skip re-encoding for public->private?** Yes, keep GCS finals and redistribute only.
3. **How far back for private->public?** From `LYRICS_COMPLETE` (screens -> render -> encode -> distribute).
4. **Tenant jobs?** Excluded. Consumer gen only.
5. **Custom style data?** Permanently cleared on private->public. Explained in modal.
6. **Rate limiting?** None needed.
