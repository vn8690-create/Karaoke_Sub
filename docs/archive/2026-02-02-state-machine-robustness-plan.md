# State Machine Robustness Plan

**Date**: 2026-02-02
**Status**: ✓ Complete (Weeks 1-3 implemented)
**Context**: Jobs 06cfea29 and 984da08b got stuck at `pending` because state transitions failed silently.

## Problem Analysis

The root issues that allowed this bug:

1. **Silent failures**: `transition_to_state()` returns `False` on invalid transitions, but callers don't check it
2. **No centralized worker trigger pattern**: Each handler (file_upload.py, users.py, audio_search.py) implements "transition + trigger workers" independently
3. **No runtime consistency checks**: Nothing detects when `state_data` says complete but `status` is wrong
4. **Workers don't validate prerequisites**: Workers run regardless of job status

## Proposed Improvements

### 1. Make State Transition Failures Loud (High Priority)

**Option A**: Raise exception by default (breaking change, but safest)
```python
class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass

def transition_to_state(self, job_id: str, new_status: JobStatus, ...,
                        raise_on_invalid: bool = True) -> bool:
    if not self.validate_state_transition(job_id, new_status):
        if raise_on_invalid:
            raise InvalidStateTransitionError(
                f"Invalid transition for job {job_id}: {current} -> {new_status}"
            )
        return False
    ...
```

**Option B**: Always log + metric, return bool (non-breaking)
```python
def transition_to_state(...) -> bool:
    if not self.validate_state_transition(job_id, new_status):
        # Log with structured data for alerting
        logger.error(
            f"STATE_TRANSITION_FAILED job={job_id} from={current} to={new_status}",
            extra={"job_id": job_id, "from_status": current, "to_status": new_status}
        )
        # Emit metric for monitoring
        emit_metric("state_transition_failed", 1, {"from": current, "to": new_status})
        return False
    ...
```

**Recommendation**: Option A with `raise_on_invalid=True` default. Forces callers to handle failures explicitly.

### 2. Centralize "Start Processing" Pattern (High Priority)

Create a single function that handles the transition + worker trigger pattern:

```python
# backend/services/job_manager.py

async def start_job_processing(self, job_id: str, worker_service) -> None:
    """
    Transition job to DOWNLOADING and trigger workers.

    This is the single entry point for starting job processing.
    All handlers (file_upload, webhook, audio_search) should use this.

    Raises:
        InvalidStateTransitionError: If job can't transition to DOWNLOADING
        ValueError: If job not found or missing required fields
    """
    job = self.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    if not job.input_media_gcs_path:
        raise ValueError(f"Job {job_id} missing input_media_gcs_path")

    # This will raise if transition is invalid
    self.transition_to_state(
        job_id=job_id,
        new_status=JobStatus.DOWNLOADING,
        progress=15,
        message="Starting audio and lyrics processing"
    )

    # Only trigger workers if transition succeeded
    await asyncio.gather(
        worker_service.trigger_audio_worker(job_id),
        worker_service.trigger_lyrics_worker(job_id)
    )
```

Then update all handlers to use this:
```python
# In _handle_made_for_you_order, file_upload, audio_search:
await job_manager.start_job_processing(job_id, worker_service)
```

### 3. Add State Consistency Checks (Medium Priority)

Add a health check that detects inconsistent state:

```python
# backend/services/job_health_service.py

def check_job_consistency(job: Job) -> List[str]:
    """
    Check for state inconsistencies in a job.
    Returns list of issues found.
    """
    issues = []
    state_data = job.state_data or {}

    # Check: audio_complete but status still pending
    if state_data.get('audio_complete') and job.status == JobStatus.PENDING:
        issues.append(f"audio_complete=True but status=pending")

    # Check: lyrics_complete but status still pending
    if state_data.get('lyrics_complete') and job.status == JobStatus.PENDING:
        issues.append(f"lyrics_complete=True but status=pending")

    # Check: screens_progress.stage=complete but status not awaiting_review
    screens = state_data.get('screens_progress', {})
    if screens.get('stage') == 'complete' and job.status not in [
        JobStatus.AWAITING_REVIEW, JobStatus.IN_REVIEW, JobStatus.REVIEW_COMPLETE,
        JobStatus.RENDERING_VIDEO, JobStatus.INSTRUMENTAL_SELECTED, ...
    ]:
        issues.append(f"screens complete but status={job.status}")

    return issues
```

Run this:
- In a daily Cloud Scheduler job
- After each worker completes
- Expose via `/health/job-consistency` endpoint

### 4. Workers Validate Prerequisites (Medium Priority)

Workers should verify job is in expected state before processing:

```python
# backend/workers/screens_worker.py

async def generate_screens(job_id: str) -> bool:
    job = job_manager.get_job(job_id)

    # Validate job is in expected state for this worker
    valid_statuses = [JobStatus.DOWNLOADING, JobStatus.AUDIO_COMPLETE, JobStatus.LYRICS_COMPLETE]
    if job.status not in [s.value for s in valid_statuses]:
        logger.error(
            f"[job:{job_id}] screens_worker called but job status is {job.status}, "
            f"expected one of {valid_statuses}. This indicates a bug in the trigger logic."
        )
        # Option: return False, or try to recover, or alert
        return False

    # ... rest of worker
```

### 5. Add Integration Tests for State Flow (Medium Priority)

Add tests that verify the complete state machine flow without mocking transitions:

```python
# backend/tests/integration/test_state_machine_flow.py

@pytest.mark.integration
async def test_made_for_you_youtube_flow_state_transitions():
    """
    Verify complete state flow for made-for-you YouTube orders.
    Uses real JobManager (mocked Firestore) to validate state machine.
    """
    # Create job
    job = job_manager.create_job(...)
    assert job.status == JobStatus.PENDING

    # Simulate YouTube download complete
    job_manager.update_job(job_id, {'input_media_gcs_path': 'test/path'})

    # Start processing (this should transition to DOWNLOADING)
    await job_manager.start_job_processing(job_id, mock_worker_service)

    job = job_manager.get_job(job_id)
    assert job.status == JobStatus.DOWNLOADING, \
        f"Expected DOWNLOADING after start_job_processing, got {job.status}"

    # ... continue through full flow
```

### 6. State Machine Diagram Generation (Low Priority)

Auto-generate a Mermaid diagram from `STATE_TRANSITIONS`:

```python
# scripts/generate_state_diagram.py

def generate_mermaid():
    lines = ["stateDiagram-v2"]
    for from_state, to_states in STATE_TRANSITIONS.items():
        for to_state in to_states:
            lines.append(f"    {from_state} --> {to_state}")
    return "\n".join(lines)
```

Add to `docs/ARCHITECTURE.md` and regenerate on changes.

### 7. Fix Admin Reset Buttons (High Priority)

The admin dashboard has reset buttons that bypass state machine validation and have several issues:

**Current buttons:**
- "Start" → reset to `pending`
- "Audio" → reset to `awaiting_audio_selection`
- "Lyrics" → reset to `awaiting_review`
- "Inst." → reset to `awaiting_instrumental_selection`
- "Reprocess" → reset to `instrumental_selected`

**Issues identified:**

1. **"Start" button leaves job stuck**: Resets to `pending` but doesn't trigger workers or clear `audio_complete`/`lyrics_complete` flags. Job sits indefinitely.

2. **"Lyrics" and "Inst." are obsolete**: Combined review flow (Jan 2026) merged these into a single step. Should be replaced with single "Review" button that resets to `awaiting_review`.

3. **Missing state_data keys in clear list for `pending`**:
   ```python
   # Should also clear:
   "audio_complete", "lyrics_complete"
   ```

4. **State machine bypass**: Admin resets use `update_job()` directly, not `transition_to_state()`. This is intentional for admin overrides but should be documented.

**Fixes needed:**

```python
# backend/api/routes/admin.py

# 1. Update STATE_DATA_CLEAR_KEYS for "pending"
STATE_DATA_CLEAR_KEYS = {
    "pending": [
        # ... existing keys ...
        "audio_complete",      # NEW - clear parallel processing flag
        "lyrics_complete",     # NEW - clear parallel processing flag
    ],
    # ...
}

# 2. Remove awaiting_instrumental_selection from ALLOWED_RESET_STATES
ALLOWED_RESET_STATES = {
    "pending",
    "awaiting_audio_selection",
    "awaiting_review",  # Combined review (lyrics + instrumental)
    # "awaiting_instrumental_selection",  # REMOVED - deprecated
    "instrumental_selected",
}

# 3. After reset to pending, trigger audio search if job has artist/title
# or provide clear guidance to admin about next steps
```

```tsx
// frontend/app/admin/jobs/page.tsx

// Replace "Lyrics" and "Inst." buttons with single "Review" button:
{[
  { state: "pending", icon: RotateCcw, label: "Start" },
  { state: "awaiting_audio_selection", icon: Music, label: "Audio" },
  { state: "awaiting_review", icon: Mic, label: "Review" },  // Combined
  // REMOVED: { state: "awaiting_instrumental_selection", ... }
  { state: "instrumental_selected", icon: RefreshCw, label: "Reprocess" },
]}
```

## Implementation Priority

1. **Week 1** ✓ DONE:
   - ✓ Make `transition_to_state` raise by default (`InvalidStateTransitionError`, `raise_on_invalid=True`)
   - ✓ Create `start_job_processing()` helper in `job_manager.py`
   - ✓ Update `_handle_made_for_you_order` to use it
   - ✓ Added 15 unit tests covering exception behavior and new helper

2. **Week 1.5** ✓ DONE (Admin Button Fixes):
   - ✓ Add `audio_complete`, `lyrics_complete` to STATE_DATA_CLEAR_KEYS for "pending"
   - ✓ Remove `awaiting_instrumental_selection` from ALLOWED_RESET_STATES
   - ✓ Update frontend to replace "Lyrics"/"Inst." with single "Review" button
   - ✓ Add tests for admin reset endpoint (`test_reset_to_pending_clears_parallel_processing_flags`, `test_rejects_deprecated_awaiting_instrumental_selection`)

3. **Week 2** ✓ DONE:
   - ✓ Update `file_upload.py` and `audio_search.py` to use `start_job_processing()`
   - ✓ Fixed double-transition bug in YouTube URL upload flow
   - ✓ Removed unused `_trigger_workers_parallel` helper from file_upload.py and audio_search.py
   - ✓ Add worker prerequisite validation (`validate_worker_can_run()` in all workers)
   - ✓ Add state consistency health check (`job_health_service.py` with `check_job_consistency()`)
   - ✓ Added 26 tests for job_health_service

4. **Week 3** ✓ DONE:
   - ✓ Add integration tests for state flow (`tests/integration/test_state_machine_flow.py` - 11 tests)
   - ✓ Generate state machine diagram script (`scripts/generate_state_diagram.py`)
   - ✓ Expose `/health/job-consistency` endpoint for admin dashboard
   - TODO: Add monitoring/alerting on `STATE_TRANSITION_FAILED` logs (requires Cloud Logging alert setup)

## Quick Wins (Can Do Now)

1. Add explicit error logging when transition fails (already exists but add job_id to structured logging)
2. Create Cloud Logging alert for "Invalid state transition" errors
3. Add consistency check to admin dashboard "stuck jobs" view
