# Cleanup: Removed Old Upload Endpoint

**Date:** 2025-12-01  
**Issue:** User discovered old `/api/upload` endpoint that bypassed worker architecture

---

## Problem

The `/api/upload` endpoint was a placeholder from the initial backend setup that:
- Used the old synchronous `KaraokePrep` approach
- Set `skip_transcription_review=True` (bypassing human interaction)
- Immediately marked jobs as "complete" without actual processing
- Created confusion by existing alongside the proper `/api/jobs` endpoint

## What Was Removed

### Files Deleted
1. **`backend/api/routes/uploads.py`** - Old upload endpoint
2. **`backend/services/processing_service.py`** - Old processing service (used `KaraokePrep` directly)

### Code Modified
- **`backend/main.py`**:
  - Removed `uploads` router import
  - Removed `app.include_router(uploads.router, prefix="/api")`

## Current Architecture

### ✅ Correct Way to Submit Jobs

**POST `/api/jobs`** - Accepts either:
- **YouTube URL**: `{"url": "...", "artist": "...", "title": "..."}`
- **File Upload**: Future implementation (will use GCS signed URLs + `/api/jobs`)

**Job Flow:**
1. Create job in Firestore (status: `CREATED`)
2. Trigger Audio Worker → `SEPARATING_AUDIO`
3. Trigger Lyrics Worker → `TRANSCRIBING_LYRICS` (parallel)
4. Wait for human review → `AWAITING_REVIEW`
5. Generate screens → `GENERATING_SCREENS`
6. Wait for instrumental selection → `AWAITING_INSTRUMENTAL_SELECTION`
7. Generate video → `GENERATING_VIDEO`
8. Encode video → `ENCODING`
9. Package outputs → `PACKAGING`
10. Complete → `COMPLETE`

### 🚫 Old Way (Now Removed)

**POST `/api/upload`** - Accepted file upload but:
- Skipped human interaction
- Used old synchronous processing
- Not compatible with worker architecture

---

## Impact

### ✅ Benefits
- **Clearer API**: Only one way to submit jobs
- **Consistent architecture**: Everything goes through worker-based flow
- **Human interaction preserved**: No bypassing of review/selection steps

### ⚠️ File Upload TODO
File uploads need to be re-implemented properly:

**Proposed Flow:**
1. Frontend requests signed upload URL: `POST /api/jobs/upload-url`
2. Backend generates GCS signed URL, returns to frontend
3. Frontend uploads directly to GCS (bypasses backend)
4. Frontend calls `POST /api/jobs` with `{"gcs_path": "...", "artist": "...", "title": "..."}`
5. Backend validates GCS file exists, creates job, triggers workers

**Benefits:**
- No file size limits on backend
- Faster uploads (direct to GCS)
- Cheaper (no bandwidth through Cloud Run)

---

## Summary

The old placeholder upload endpoint has been removed. All job submissions now use the proper worker-based architecture with human interaction points.

