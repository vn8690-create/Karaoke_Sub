# First Backend Test - Issues and Fixes

**Date:** 2025-12-01  
**Test:** File upload endpoint

---

## Issue 1: Missing Environment Variables ❌

### Error
```json
{"detail":"400 Invalid resource field value in the request. [reason: \"RESOURCE_PROJECT_INVALID\"..."}
```

### Root Cause
Manual `gcloud run deploy` didn't include environment variables. The backend couldn't connect to Firestore because `GOOGLE_CLOUD_PROJECT` was not set.

### Fix ✅
```bash
gcloud run services update karaoke-backend \
  --region us-central1 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=nomadkaraoke,GCS_BUCKET_NAME=karaoke-gen-storage-nomadkaraoke,FIRESTORE_COLLECTION=jobs,ENVIRONMENT=production"
```

### Why It Happened
- Pulumi normally sets these env vars
- Manual deployment bypassed Pulumi
- `cloudbuild.yaml` needs to include env vars in deploy step

---

## Issue 2: Race Condition in File Upload ❌

### Error
```
'Job' object has no attribute 'input_media_gcs_path'
```

### Root Cause
Workers were triggered via `background_tasks` which run **asynchronously**:

```python
# OLD CODE (BROKEN)
job_manager.update_job(job.job_id, {
    'input_media_gcs_path': gcs_path
})

# Workers start immediately, might run before update completes
background_tasks.add_task(worker_service.trigger_audio_worker, job.job_id)
background_tasks.add_task(worker_service.trigger_lyrics_worker, job.job_id)
```

**Timeline:**
1. Job created (no `input_media_gcs_path` yet)
2. File uploaded to GCS ✅
3. `update_job()` called to add `input_media_gcs_path`
4. `background_tasks.add_task()` queues workers
5. Workers start **before update completes** ❌
6. Workers try to access `input_media_gcs_path` → AttributeError

### Fix ✅
```python
# NEW CODE (FIXED)
job_manager.update_job(job.job_id, {
    'input_media_gcs_path': gcs_path
})

# Wait for workers to be triggered (HTTP call completes before returning)
await worker_service.trigger_audio_worker(job.job_id)
await worker_service.trigger_lyrics_worker(job.job_id)
```

**Why this works:**
- `await` ensures the HTTP call completes
- Workers are triggered via internal HTTP endpoint
- By the time workers run, job is updated
- No race condition

---

## Test Results

### Before Fixes
```bash
$ curl -X POST "$BACKEND_URL/api/jobs/upload" ...

# Response:
{"detail":"400 Invalid resource field value..."}
```

### After Fix 1 (Env Vars)
```bash
$ curl -X POST "$BACKEND_URL/api/jobs/upload" ...

# Response:
{"status":"success","job_id":"78651f2e",...}

# But job status:
{
  "status": "failed",
  "error_message": "Audio separation failed: Failed to download audio file"
}
```

### After Fix 2 (Race Condition)
```bash
$ curl -X POST "$BACKEND_URL/api/jobs/upload" ...

# Response:
{"status":"success","job_id":"...",...}

# Job status:
{
  "status": "processing_audio",  # ✅ Working!
  "progress": 10,
  ...
}
```

---

## Lessons Learned

### 1. Always Set Environment Variables

**Best practice:** Include env vars in deployment:

```yaml
# cloudbuild.yaml
- name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
  entrypoint: gcloud
  args:
    - 'run'
    - 'deploy'
    - 'karaoke-backend'
    - '--image'
    - 'us-central1-docker.pkg.dev/$PROJECT_ID/karaoke-repo/karaoke-backend:$BUILD_ID'
    - '--region'
    - 'us-central1'
    - '--set-env-vars'
    - 'GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GCS_BUCKET_NAME=karaoke-gen-storage-$PROJECT_ID,FIRESTORE_COLLECTION=jobs,ENVIRONMENT=production'
```

### 2. Avoid Background Tasks for Critical Operations

**Problem:** `BackgroundTasks` are fire-and-forget

**Solution:** Use `await` for operations that must complete in order:

```python
# BAD: Race condition possible
background_tasks.add_task(worker_service.trigger_worker, job_id)

# GOOD: Waits for trigger to complete
await worker_service.trigger_worker(job_id)
```

### 3. Local Validation Would Have Caught Neither Issue

**Why:**
- ✅ Import errors → Caught by validation
- ❌ Environment variables → Not caught (local has different config)
- ❌ Race conditions → Not caught (need integration tests)

**Solution:** Need integration tests that run against deployed backend

---

## Updated cloudbuild.yaml

```yaml
steps:
  # Build steps...
  
  # Deploy to Cloud Run with environment variables
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'karaoke-backend'
      - '--image'
      - 'us-central1-docker.pkg.dev/$PROJECT_ID/karaoke-repo/karaoke-backend:$BUILD_ID'
      - '--region'
      - 'us-central1'
      - '--platform'
      - 'managed'
      - '--set-env-vars'
      - 'GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GCS_BUCKET_NAME=karaoke-gen-storage-$PROJECT_ID,FIRESTORE_COLLECTION=jobs,ENVIRONMENT=production'
```

---

## Summary

| Issue | Symptom | Root Cause | Fix |
|-------|---------|------------|-----|
| **Env vars** | Firestore error | Manual deploy | Add env vars to Cloud Run |
| **Race condition** | AttributeError | `background_tasks` timing | Use `await` instead |

**Status:** Both fixed! ✅

**Next deployment will include:**
- ✅ Environment variables in `cloudbuild.yaml`
- ✅ Fixed race condition with `await`
- ✅ Automatic deployment after build

**Ready for next test!** 🚀

