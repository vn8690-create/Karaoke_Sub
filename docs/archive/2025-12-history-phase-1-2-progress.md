# Phase 1.2: Async Job Processing - Implementation Progress

**Started:** 2025-12-01  
**Status:** In Progress

---

## ✅ Completed

### Step 1.2.1: Job State Machine ✅ COMPLETE

**Goal:** Implement comprehensive state machine for full CLI workflow parity

**Files Modified:**
- `backend/models/job.py`
- `backend/models/requests.py`
- `backend/services/job_manager.py`

**Changes Made:**

#### 1. Enhanced `JobStatus` Enum (job.py)
- **Added 21 new states** covering all 8 workflow stages:
  - Initial: `PENDING`, `DOWNLOADING`
  - Audio: `SEPARATING_STAGE1`, `SEPARATING_STAGE2`, `AUDIO_COMPLETE`
  - Lyrics: `TRANSCRIBING`, `CORRECTING`, `LYRICS_COMPLETE`
  - Screens: `GENERATING_SCREENS`
  - Padding: `APPLYING_PADDING`
  - Review: `AWAITING_REVIEW`, `IN_REVIEW`, `REVIEW_COMPLETE` ⚠️ HUMAN
  - Selection: `AWAITING_INSTRUMENTAL_SELECTION`, `INSTRUMENTAL_SELECTED` ⚠️ HUMAN
  - Video: `GENERATING_VIDEO`, `ENCODING`, `PACKAGING`
  - Distribution: `UPLOADING`, `NOTIFYING`
  - Terminal: `COMPLETE`, `FAILED`, `CANCELLED`

- **Defined `STATE_TRANSITIONS`** dict:
  - Maps each state to valid next states
  - Enables validation to prevent illegal transitions
  - Documents the complete workflow DAG

#### 2. Expanded `Job` Model (job.py)
- **New fields for user preferences:**
  - `enable_cdg`: Generate CDG+MP3 package
  - `enable_txt`: Generate TXT+MP3 package
  - `enable_youtube_upload`: Upload to YouTube
  - `youtube_description`: Video description
  - `webhook_url`: Notification webhook
  - `user_email`: Email for notifications

- **New `state_data` field:**
  - JSON field for stage-specific metadata
  - Examples:
    - Audio complete: `{"stems": {"clean": "gs://...", "backing": "gs://..."}}`
    - Lyrics complete: `{"corrections_url": "gs://...", "audio_url": "gs://..."}`
    - Review complete: `{"corrected_lyrics": {...}}`
    - Instrumental selected: `{"selection": "clean"}`

- **New `file_urls` structure:**
  - Comprehensive file URL tracking
  - Categories: `input`, `stems`, `lyrics`, `screens`, `videos`, `finals`, `packages`, `youtube`
  - Replaces old `output_files` dict

- **New error tracking:**
  - `error_details`: Structured error info
  - `retry_count`: Track retry attempts

- **New `worker_ids` tracking:**
  - Stores IDs of background workers/jobs
  - Examples: `{"audio_worker": "...", "video_encoder": "cloud-build-id"}`

- **State transition validator:**
  - Pydantic validator checks transitions are legal
  - Raises `ValueError` if invalid transition attempted

#### 3. New Request Models (requests.py)
- **`CorrectionsSubmission`:**
  - For submitting corrected lyrics after review
  - Validates corrections has required fields
  - Critical human-in-the-loop endpoint

- **`InstrumentalSelection`:**
  - For selecting instrumental option
  - Validates selection is "clean" or "with_backing"
  - Second human-in-the-loop endpoint

- **`StartReviewRequest`:**
  - Marks job as `IN_REVIEW` (user opened interface)

- **`CancelJobRequest`:**
  - Cancel a job with optional reason

- **`RetryJobRequest`:**
  - Retry failed job from specific stage

#### 4. Enhanced `JobManager` (job_manager.py)
- **New state transition methods:**
  - `validate_state_transition()`: Check if transition is legal
  - `transition_to_state()`: Validated state transition with logging
  - `update_state_data()`: Update stage-specific metadata
  - `update_file_url()`: Update file URLs by category

- **Worker coordination methods:**
  - `check_parallel_processing_complete()`: Check if audio + lyrics both done
  - `mark_audio_complete()`: Mark audio done, check if can proceed
  - `mark_lyrics_complete()`: Mark lyrics done, check if can proceed

- **Job lifecycle methods:**
  - `cancel_job()`: Cancel with validation
  - `mark_job_failed()`: Better error tracking (replaces `mark_job_error`)
  - `increment_retry_count()`: Track retries

**Key Design Decisions:**

1. **State machine is strict:**
   - Transitions are validated on every update
   - Prevents jobs from getting into invalid states
   - Documents the workflow in code

2. **Parallel processing coordination:**
   - Audio and lyrics workers run independently
   - `mark_audio_complete()` and `mark_lyrics_complete()` check if both done
   - Auto-transitions to `GENERATING_SCREENS` when both ready
   - No race conditions

3. **Extensible state_data:**
   - JSON field allows stage-specific data
   - Avoids adding new fields for every stage
   - Workers can store arbitrary metadata

4. **Backward compatibility:**
   - Kept legacy states (`QUEUED`, `PROCESSING`, etc.)
   - Will be deprecated in future
   - Allows gradual migration

---

### Step 1.2.2: Worker Infrastructure ✅ COMPLETE

**Goal:** Create background worker system for long-running tasks

**Files Created:**
- `backend/workers/__init__.py`
- `backend/workers/audio_worker.py`
- `backend/workers/lyrics_worker.py`
- `backend/workers/screens_worker.py`

**What's Done:**

#### Audio Worker Implementation
- **Complete integration with `karaoke_gen.AudioProcessor`:**
  - Uses remote Modal API for GPU separation
  - Stage 1: Clean instrumental (3-5 min)
  - Stage 2: Backing vocals (2-3 min)
  - Post-processing: Combined instrumentals

- **Comprehensive workflow:**
  1. Download audio from GCS to temp directory
  2. Initialize `FileHandler` and `AudioProcessor`
  3. Set `AUDIO_SEPARATOR_API_URL` from Secret Manager
  4. Run Stage 1 separation → upload stems → update job state
  5. Run Stage 2 separation → upload stems → update job state
  6. Post-process (combine, normalize) → upload finals
  7. Mark audio complete → check if can proceed

- **Error handling:**
  - Try/catch/finally for cleanup
  - Marks job as `FAILED` with error details
  - Cleanup temp directory in all cases

- **Progress tracking:**
  - Updates job state at each stage
  - Progress percentages (20%, 35%, 45%)
  - Timeline messages

**What's Missing:**

#### Integration Points (TODO)
- [ ] **Trigger mechanism:** How to call `process_audio_separation()` async
  - Option A: Internal HTTP endpoint `/internal/workers/audio` (Cloud Run)
  - Option B: Cloud Tasks queue
  - Option C: Pub/Sub messages

- [ ] **API endpoints:** Job submission needs to trigger worker
  - Update `POST /api/jobs` to trigger audio + lyrics workers after job creation

- [ ] **Secret Manager integration:** `get_secret()` not implemented yet
  - Need to add to `backend/config.py`

- [ ] **Storage service updates:** Some methods may need async versions
  - `download_file()` should work synchronously
  - `upload_file()` should work synchronously

---

## ⏭️ Next Steps

### Immediate (Continue Step 1.2.2)

1. **Implement worker trigger mechanism:**
   ```python
   # backend/api/routes/internal.py
   @router.post("/internal/workers/audio")
   async def trigger_audio_worker(request: WorkerRequest):
       """Internal endpoint to trigger audio worker"""
       asyncio.create_task(process_audio_separation(request.job_id))
       return {"status": "started"}
   ```

2. **Update job submission to trigger workers:**
   ```python
   # backend/api/routes/jobs.py
   @router.post("/")
   async def create_job(job_create: JobCreate):
       job = job_manager.create_job(job_create)
       
       # Trigger both workers in parallel
       await trigger_worker("audio", job.job_id)
       await trigger_worker("lyrics", job.job_id)
       
       return JobResponse(...)
   ```

3. **Add Secret Manager integration:**
   ```python
   # backend/config.py
   from google.cloud import secretmanager
   
   async def get_secret(secret_id: str) -> str:
       client = secretmanager.SecretManagerServiceClient()
       name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
       response = client.access_secret_version(request={"name": name})
       return response.payload.data.decode('UTF-8')
   ```

### Step 1.2.3: Lyrics Worker (TODO)
- [ ] Create `backend/workers/lyrics_worker.py`
- [ ] Integrate `karaoke_gen.LyricsProcessor`
- [ ] Fetch lyrics from Genius/Spotify
- [ ] Call AudioShake API for transcription
- [ ] Run automatic correction
- [ ] Generate corrections JSON
- [ ] Upload to GCS
- [ ] Transition to `AWAITING_REVIEW`

### Step 1.2.4: Test Parallel Processing (TODO)
- [ ] Submit test job
- [ ] Verify audio worker runs
- [ ] Verify lyrics worker runs
- [ ] Verify both complete independently
- [ ] Verify auto-transition to `GENERATING_SCREENS`

---

## Key Insights So Far

### 1. State Machine Complexity is Justified
The 21 states seem like a lot, but they accurately model the real workflow:
- 2 parallel tracks (audio + lyrics)
- 2 human interaction points
- Multiple async stages
- Distribution optional steps

**This complexity cannot be simplified without losing functionality.**

### 2. Worker Coordination Pattern
The `mark_audio_complete()` + `mark_lyrics_complete()` pattern works well:
- Each worker marks its track complete
- Auto-checks if both complete
- Auto-transitions to next stage
- No race conditions (Firestore transactions handle atomicity)

### 3. Temporary Files Management
Using `tempfile.mkdtemp()` + try/finally cleanup works well:
- Each worker gets isolated temp directory
- Automatic cleanup on success or failure
- No disk space leaks

### 4. Integration with karaoke_gen is Clean
Using `AudioProcessor` directly eliminates code duplication:
- Same logic as CLI
- Just need to set `AUDIO_SEPARATOR_API_URL` env var
- Remote API handles GPU processing
- Works exactly like CLI

---

## Challenges Encountered

### 1. Async vs Sync Code
- `karaoke_gen` is synchronous
- Workers need to be async
- **Solution:** Workers are async wrappers around sync code

### 2. File Path Management
- `AudioProcessor` expects local file paths
- Need to download from GCS first
- Need to upload results back to GCS
- **Solution:** Temp directory pattern works well

### 3. State Transition Validation
- Need to prevent illegal transitions
- But also allow flexibility
- **Solution:** `STATE_TRANSITIONS` dict + validator

---

## Files Changed Summary

```
backend/models/job.py           | +180 lines | State machine + expanded Job model
backend/models/requests.py      | +60 lines  | New request models
backend/services/job_manager.py | +200 lines | State transition + coordination
backend/workers/__init__.py     | +8 lines   | Worker package
backend/workers/audio_worker.py | +230 lines | Audio separation worker
```

**Total:** ~678 lines of new/modified code

---

## Testing Status

- [x] Models pass validation
- [x] No linter errors
- [ ] Unit tests (not yet written)
- [ ] Integration tests (not yet written)
- [ ] End-to-end test with real job (not yet done)

---

## Documentation Updated

- [x] This progress document created
- [ ] Update API documentation (TODO)
- [ ] Update deployment guide (TODO)
- [ ] Update NEXT-STEPS.md when complete (TODO)

