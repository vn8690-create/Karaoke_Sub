# Job Failure Investigation Report

**Date**: 2024-12-31
**Investigated Jobs**: 76296c31, 67bc8ca8, 02207418, cadd7153, 6a461e4e, 14035e2b, 643983e3, 9726a99b
**Affected User**: [redacted]@gmail.com (plus E2E test jobs)

## Executive Summary

Investigation revealed **4 distinct issues** causing job failures and the user complaint that "jobs don't show up in my account":

1. **CRITICAL: user_email not set on jobs** - Jobs aren't associated with users
2. **YouTube URL download race condition** - Lyrics worker starts before audio is downloaded
3. **Audio search cache not shared across instances** - Cloud Run scaling breaks download
4. **Lyrics worker stalling silently** - Jobs stuck in "downloading" state forever

---

## Issue 1: user_email Not Being Set on Jobs (CRITICAL)

### Symptoms
- User reports: "jobs polling is always returning a []"
- User has active account with 2 credits, active session
- User investigation shows `Jobs Created: 0` despite creating jobs
- All 8 investigated jobs have `user_email: null`

### Root Cause
The job creation endpoints use `require_auth` dependency which returns `AuthResult` containing `user_email`. However, the endpoints **do not extract this email and set it on the job**.

**In `backend/api/routes/file_upload.py`:**
- `user_email` is an optional form field (line 397) that clients must explicitly pass
- The `auth_result.user_email` from authentication is ignored
- Jobs are created with `user_email=None` unless client explicitly sends it

**Same issue in:**
- `/jobs/upload` endpoint
- `/jobs/create-from-url` endpoint
- `/jobs/create-with-upload-urls` endpoint
- `/api/audio-search/search` endpoint

### Fix Required
Modify all job creation endpoints to:
1. Extract `user_email` from `AuthResult` when available
2. Prefer authenticated user's email over client-provided value
3. Set this on the `JobCreate` model

**Example fix for `create-from-url`:**
```python
@router.post("/jobs/create-from-url")
async def create_job_from_url(
    request: Request,
    body: CreateJobFromUrlRequest,
    auth_result: AuthResult = Depends(require_auth)  # Use AuthResult, not tuple
):
    # Extract user email from authenticated session
    effective_user_email = auth_result.user_email or body.user_email

    job_create = JobCreate(
        ...
        user_email=effective_user_email,  # Now properly set
        ...
    )
```

### Priority
**CRITICAL** - This is blocking all authenticated users from seeing their jobs.

---

## Issue 2: YouTube URL Download Race Condition

### Symptoms
- Jobs cadd7153, 6a461e4e, 14035e2b failed with: `Lyrics transcription failed: Failed to download audio file`
- All have `input_media_gcs_path: null`
- All were created from YouTube URLs

### Root Cause
In `file_upload.py` at `/jobs/create-from-url`:
1. Job is created with `url` but no `input_media_gcs_path`
2. Job immediately transitions to `DOWNLOADING` state
3. **Both audio and lyrics workers are triggered in parallel** (`_trigger_workers_parallel`)

The problem:
- Audio worker is responsible for downloading from YouTube and uploading to GCS
- Lyrics worker needs the audio file from GCS to transcribe
- Lyrics worker polls for `input_media_gcs_path` for up to 5 minutes (max_wait_seconds=300)
- If YouTube download is slow or fails, lyrics worker times out

**Additional YouTube download issues:**
- `YOUTUBE_COOKIES` env var may not be set, causing "Sign in to confirm you're not a bot" errors
- YouTube rate limiting can cause downloads to fail

### Evidence in `lyrics_worker.py:401-427`
```python
# For URL jobs, wait for audio worker to download and upload to GCS
if job.url:
    while time.time() - start_time < max_wait_seconds:
        # Poll for input_media_gcs_path
        if updated_job.input_media_gcs_path:
            return local_path
        await asyncio.sleep(poll_interval)

    logger.error(f"Timed out waiting for audio download")
    return None
```

### Fix Required
Option A (Recommended): **Sequential triggering for URL jobs**
```python
# In create-from-url endpoint:
if job.url and not job.input_media_gcs_path:
    # Only trigger audio worker first for URL jobs
    # Lyrics worker triggered after audio is downloaded
    background_tasks.add_task(worker_service.trigger_audio_worker, job_id)
else:
    # For uploaded files, parallel is fine
    background_tasks.add_task(_trigger_workers_parallel, job_id)
```

Option B: **Audio worker triggers lyrics worker after download**
- Have `audio_worker.download_audio()` trigger lyrics worker upon successful URL download

### Priority
**HIGH** - YouTube/URL-based jobs are failing consistently.

---

## Issue 3: Audio Search Cache Not Persisting

### Symptoms
- Job 76296c31 failed with: `Audio download failed: No cached result for index 0. Available indices: 0--1. Run search() first.`
- Job was created from `audio_search` mode

### Root Cause
`AudioSearchService` is a singleton with in-memory cache (`self._cached_results`). Cloud Run uses horizontal scaling with multiple instances, so:

1. Request 1 (search): Hits instance A, caches results in A's memory
2. Request 2 (select/download): May hit instance B, which has empty cache
3. Download fails because `len(self._cached_results) = 0`

**In `audio_search_service.py:279-284`:**
```python
if result_index < 0 or result_index >= len(self._cached_results):
    raise DownloadError(
        f"No cached result for index {result_index}. "
        f"Available indices: 0-{len(self._cached_results) - 1}. "  # Shows "0--1" when empty
        "Run search() first."
    )
```

### Partial Fix Already in Place
The code stores search results in `job.state_data['audio_search_results']` and attempts to use `download_by_id()` which doesn't require cache. However, for YouTube sources, it falls back to cache-based download.

### Fix Required
**Never rely on in-memory cache across requests.** Always use job.state_data.

In `audio_search.py` `_download_and_start_processing()`:
```python
# Get the selected result from job state_data (not service cache)
search_results = job.state_data.get('audio_search_results', [])
selected = search_results[selection_index]

# For YouTube, construct a fake AudioSearchResult from state_data
# and call download_by_id with video URL
if selected['provider'] == 'YouTube':
    result = audio_search_service.download_by_id(
        source_name='YouTube',
        source_id=selected.get('source_id'),  # Video ID
        output_dir=temp_dir,
        download_url=selected.get('url'),  # YouTube URL
    )
```

### Priority
**HIGH** - Audio search mode is broken in multi-instance environments.

---

## Issue 4: Jobs Stuck in Downloading State

### Symptoms
- Jobs 643983e3, 9726a99b have status `downloading` indefinitely
- `state_data.audio_complete: true` - audio worker finished
- `state_data.lyrics_progress.stage: "transcribing"` - lyrics worker started
- NO `lyrics_complete` flag - lyrics worker never finished
- Status never transitions beyond `downloading`

### Root Cause
The lyrics worker appears to crash or timeout during AudioShake transcription without properly failing the job. Possible causes:

1. **AudioShake API timeout** - transcription takes too long
2. **Cloud Run instance killed** - worker running longer than timeout allows
3. **Unhandled exception** - error during transcription not caught properly
4. **Memory exhaustion** - large audio files causing OOM

The lyrics worker's exception handling (`lyrics_worker.py:375-383`) should mark job as failed:
```python
except Exception as e:
    job_manager.mark_job_failed(
        job_id=job_id,
        error_message=f"Lyrics transcription failed: {str(e)}",
    )
```

But if the Cloud Run instance is killed (e.g., timeout, OOM), this code never runs.

### Fix Required
1. **Add job-level timeouts with cleanup**
```python
# In job_manager.py - scheduled task to clean up stale jobs
async def cleanup_stale_jobs():
    # Find jobs in 'downloading' state for more than X hours
    # Check if workers are actually running
    # Mark as failed if stuck
```

2. **Add heartbeat mechanism**
```python
# Workers periodically update timestamp
job_manager.update_state_data(job_id, 'worker_heartbeat', datetime.now())

# Background job detects stale heartbeats and fails job
```

3. **Improve AudioShake timeout handling**
```python
# In lyrics_worker.py, add explicit timeout:
async with asyncio.timeout(600):  # 10 minute timeout
    result = await asyncio.to_thread(lyrics_processor.transcribe_lyrics, ...)
```

### Priority
**MEDIUM** - Jobs are stuck but not actively failing. Need monitoring/cleanup mechanism.

---

## Summary of Fixes

| Issue | Priority | Fix Complexity | Affected Code |
|-------|----------|---------------|---------------|
| 1. user_email not set | CRITICAL | Low | `file_upload.py`, `audio_search.py` |
| 2. URL download race | HIGH | Medium | `file_upload.py`, `audio_worker.py` |
| 3. Audio search cache | HIGH | Medium | `audio_search.py`, `audio_search_service.py` |
| 4. Stuck jobs cleanup | MEDIUM | Medium | `job_manager.py`, workers |

---

## Implemented Fixes

### Issue 1: user_email - FIXED
**Changes:**
- Updated all job creation endpoints to use `AuthResult` type instead of tuple
- Extract `auth_result.user_email` and set it on `JobCreate`
- Prefer authenticated user's email over client-provided value

**Files modified:**
- `backend/api/routes/file_upload.py` - All job creation endpoints
- `backend/api/routes/audio_search.py` - Audio search endpoint

### Issue 2: URL Download Race Condition - FIXED
**Changes:**
- For URL jobs, only trigger audio worker initially (not lyrics)
- Audio worker triggers lyrics worker after successful URL download
- Added `_trigger_audio_worker_only()` function for URL jobs
- Added `_trigger_lyrics_worker_after_url_download()` in audio_worker

**Files modified:**
- `backend/api/routes/file_upload.py` - Changed create-from-url to use sequential triggering
- `backend/workers/audio_worker.py` - Trigger lyrics worker after URL download

### Issue 3: Audio Search Cache - FIXED
**Changes:**
- For YouTube sources without remote flacfetch, download directly using URL from `state_data`
- Avoids relying on in-memory cache which doesn't persist across Cloud Run instances
- Added fallback warning for cache-based downloads

**Files modified:**
- `backend/api/routes/audio_search.py` - Added direct YouTube download path

### Issue 4: Stuck Jobs Timeout - FIXED
**Changes:**
- Added 10-minute timeout around AudioShake transcription call
- Uses `asyncio.wait_for` to ensure transcription doesn't hang forever
- On timeout, raises exception which marks job as failed

**Files modified:**
- `backend/workers/lyrics_worker.py` - Added timeout handling

---

## Testing
All 812 backend tests pass after fixes.
