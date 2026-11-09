# Cloud Migration Requirements - Key Architectural Implications

## Executive Summary

The `karaoke-gen` CLI is **not a simple batch job**. It's a **multi-stage, human-in-the-loop workflow** that requires:

1. **Async job processing** (30-45 min total, with gaps for human decisions)
2. **Two human interaction points** (lyrics review, instrumental selection)
3. **State persistence** across stages
4. **Large file handling** (~2GB temp files, ~950MB final output per song)
5. **Multiple external services** (Modal, AudioShake, YouTube, etc.)

## Current CLI Workflow (Simplified)

```
Input → [Stage 1: Parallel Processing] → [Stage 2: Human Review] → 
[Stage 3: User Selects Instrumental] → [Stage 4: Video Finalization] → 
[Stage 5: Distribution]
```

**Total Time:** 30-45 minutes per song
**Human Involvement:** 5-15 minutes (review) + 30 seconds (selection)
**Blocking:** CLI blocks waiting for human input

## Required Cloud Architecture Changes

### 1. Job State Machine

**Problem:** CLI is synchronous, blocks waiting for user input

**Solution:** Async job queue with state transitions

```
Job States:
├── pending (initial)
├── processing_audio (Stage 1A - separation)
├── processing_lyrics (Stage 1B - transcription)
├── awaiting_review (HUMAN DECISION POINT 1)
├── in_review (user actively reviewing)
├── review_complete (user submitted corrections)
├── awaiting_instrumental_selection (HUMAN DECISION POINT 2)
├── generating_video (Stage 4 - encoding)
├── finalizing (Stage 5 - packaging)
├── completed
├── failed
└── cancelled
```

**Implementation:**
- Firestore document per job
- Timeline events array for progress tracking
- Status polling endpoint for frontend
- Webhook/notification when review is ready

### 2. Lyrics Review Interface

**Problem:** CLI launches local web server (port 8000), blocks until user completes review

**Solution:** Cloud-hosted review interface

**Architecture:**
```
┌────────────────────────────────────────────┐
│  React Review App (Cloudflare Pages)       │
│  - Loads corrections JSON from GCS         │
│  - Plays audio from GCS                    │
│  - Allows user edits                       │
│  - Submits corrections back to API         │
└────────────────┬───────────────────────────┘
                 │
                 v
┌────────────────────────────────────────────┐
│  FastAPI Backend (Cloud Run)               │
│  POST /api/jobs/{job_id}/corrections      │
│  - Validates corrections data              │
│  - Updates job state → review_complete    │
│  - Triggers video generation worker        │
└────────────────────────────────────────────┘
```

**Required API Endpoint:**
```typescript
POST /api/jobs/{job_id}/corrections
{
  "corrections": {
    "corrected_segments": [...],
    "original_segments": [...],
    // Full CorrectionResult.to_dict() format
  }
}
```

**Process Flow:**
1. Job reaches `awaiting_review` state
2. System notifies user (email with review URL)
3. User opens: `https://gen.nomadkaraoke.com/review/{job_id}`
4. React app loads:
   - Corrections JSON from GCS
   - Audio file from GCS
   - Renders lyrics-transcriber review UI
5. User makes edits, clicks "Submit"
6. POST to `/api/jobs/{job_id}/corrections`
7. Backend resumes processing (video generation)

**Key Difference from CLI:**
- CLI: Local server at `localhost:8000`, synchronous
- Cloud: Static React app, async communication via API

### 3. Instrumental Selection Interface

**Problem:** CLI presents audio file choices, blocks for user input

**Solution:** Audio preview player in frontend

**API Endpoint:**
```typescript
GET /api/jobs/{job_id}/instrumentals
Response:
{
  "instrumentals": [
    {
      "id": "clean",
      "name": "Clean Instrumental (No Backing Vocals)",
      "file_url": "https://storage.googleapis.com/.../instrumental_clean.flac",
      "model": "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
    },
    {
      "id": "with_backing",
      "name": "Instrumental with Backing Vocals",
      "file_url": "https://storage.googleapis.com/.../instrumental_backing.flac",
      "model": "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"
    }
  ]
}

POST /api/jobs/{job_id}/select-instrumental
{
  "instrumental_id": "clean"
}
```

**UI Component:**
```tsx
<InstrumentalSelector job={job}>
  {instrumentals.map(inst => (
    <AudioPreview 
      key={inst.id}
      name={inst.name}
      audioUrl={inst.file_url}
      onSelect={() => selectInstrumental(inst.id)}
    />
  ))}
</InstrumentalSelector>
```

### 4. File Storage Strategy

**Problem:** CLI uses local disk (~2GB per song during processing)

**Solution:** Google Cloud Storage with lifecycle policies

**Bucket Structure:**
```
gs://karaoke-gen-uploads/
  └── {user_id}/
      └── {job_id}/
          └── input.flac

gs://karaoke-gen-temp/
  └── {job_id}/
      ├── stems/                    [DELETE after 7 days]
      │   ├── vocals_clean.flac
      │   ├── instrumental_clean.flac
      │   └── ...
      ├── lyrics/                   [DELETE after 7 days]
      │   ├── corrections.json
      │   ├── karaoke.lrc
      │   └── ...
      └── working/                  [DELETE after 7 days]
          ├── title.mov
          ├── end.mov
          └── with_vocals.mkv

gs://karaoke-gen-outputs/
  └── {user_id}/
      └── {job_id}/               [DELETE after 30 days]
          ├── final_lossless_4k.mp4
          ├── final_lossy_4k.mp4
          ├── final_lossy_720p.mp4
          ├── final_cdg.zip
          └── final_txt.zip
```

**Access Control:**
- Signed URLs for downloads (24-hour expiry)
- IAM policies: users can only access their own files
- CORS configuration for frontend uploads

**Cost Optimization:**
- Lifecycle rules: auto-delete temp files
- Standard storage for inputs (hot access)
- Nearline storage for finals (cold after 30 days)
- No Archive storage (retrieval time too slow)

### 5. Video Processing Strategy

**Problem:** Video encoding is CPU-intensive (15-20 minutes), too long for Cloud Run request

**Solution:** Background worker or Cloud Build job

**Option A: Cloud Run Background Worker**
```python
# In main Cloud Run service
@app.post("/api/jobs/{job_id}/start-video-generation")
async def start_video_generation(job_id: str):
    # Queue background task
    background_tasks.add_task(
        generate_video_async,
        job_id=job_id
    )
    return {"status": "started"}

async def generate_video_async(job_id: str):
    # Runs in background (Cloud Run timeout: 60 min max)
    # Downloads files from GCS
    # Runs ffmpeg encoding
    # Uploads results to GCS
    # Updates job state
```

**Option B: Cloud Build Job** (RECOMMENDED)
```yaml
# cloudbuild-video.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['run', 
           '--rm',
           '-e', 'JOB_ID=${_JOB_ID}',
           'karaoke-video-processor:latest',
           'process']
timeout: 3600s  # 1 hour
```

**Why Cloud Build?**
- Dedicated compute (not competing with API requests)
- Higher resource limits (32 CPU, 32GB RAM)
- Better for long-running tasks
- Separate billing/quotas

**Trigger via API:**
```python
from google.cloud import build_v1

build_client = build_v1.CloudBuildClient()
build = build_v1.Build(
    source=...,
    steps=[...],
    timeout=Duration(seconds=3600)
)
operation = build_client.create_build(
    project_id=PROJECT_ID,
    build=build
)
```

### 6. Notification System

**Problem:** User needs to know when review is ready, when job is complete

**Solution:** Email notifications + optional webhooks

**Email Templates:**

**1. Review Ready:**
```
Subject: Your karaoke track is ready for review!

Hi {user_name},

Your karaoke track "{artist} - {title}" has been processed and is ready for review.

Click here to review and correct the lyrics:
{review_url}

This link expires in 7 days.

Thanks,
Nomad Karaoke
```

**2. Job Complete:**
```
Subject: Your karaoke track is complete!

Hi {user_name},

Your karaoke track "{artist} - {title}" is ready!

Download your files:
- Final Video (4K): {video_url}
- Final Video (720p): {video_720p_url}
- CDG+MP3 ZIP: {cdg_url}
- TXT+MP3 ZIP: {txt_url}

Links expire in 30 days.

YouTube URL: {youtube_url}

Thanks,
Nomad Karaoke
```

**Implementation:**
- SendGrid for email delivery
- Firestore trigger: send email on state change
- Optional: SMS via Twilio for premium users
- Optional: Discord/Slack webhook for team notifications

### 7. Credentials Management

**Problem:** CLI uses environment variables for all credentials

**Solution:** Google Secret Manager + per-user credentials

**System-Level Secrets (Secret Manager):**
```
- audioshake-api-token
- audio-separator-api-url
- sendgrid-api-key
- genius-api-token (fallback)
```

**User-Level Credentials (Firestore):**
```typescript
// Collection: users/{user_id}
{
  credentials: {
    youtube: {
      access_token: "...",
      refresh_token: "...",
      expires_at: 1234567890
    },
    dropbox: {
      access_token: "..."
    },
    discord_webhook: "https://..."
  }
}
```

**OAuth Flow:**
```
1. User clicks "Connect YouTube"
2. Redirects to Google OAuth
3. User grants permission
4. Callback to: /api/auth/youtube/callback
5. Store tokens in Firestore
6. Use tokens for future uploads
```

### 8. Cost Management

**Problem:** Each job costs money, need to track and charge users

**Estimated Costs per Job:**
```
Cloud Run (processing):        $0.05
Cloud Build (video encoding):  $0.20
GCS Storage (30 days):         $0.10
GCS Bandwidth (downloads):     $0.05
AudioShake API:                $0.04
-------------------------------------------
Total:                         $0.44

Target Price:                  $2.00
Margin:                        $1.56 (78%)
```

**Cost Tracking:**
```typescript
// Firestore: jobs/{job_id}
{
  costs: {
    audio_separation: 0.00,  // Covered by Modal (we pay)
    transcription: 0.04,     // AudioShake API
    storage: 0.10,
    compute: 0.25,
    bandwidth: 0.05,
    total: 0.44
  }
}
```

**Implementation:**
- Cloud Billing API for actual costs
- Estimated costs shown upfront
- Usage quotas per user (5 songs/month free tier?)

## Recommended Cloud Architecture

```
┌─────────────────────────────────────────────────────┐
│          Frontend (Cloudflare Pages)                │
│  - React SPA                                        │
│  - Job submission                                   │
│  - Lyrics review interface                          │
│  - Instrumental selection                           │
│  - Progress tracking                                │
│  - File download                                    │
└───────────────────┬─────────────────────────────────┘
                    │ HTTPS
                    v
┌─────────────────────────────────────────────────────┐
│       Backend API (Cloud Run - FastAPI)             │
│  - Job creation                                     │
│  - Status polling                                   │
│  - Corrections submission                           │
│  - Instrumental selection                           │
│  - Signed URL generation                            │
└───────────┬──────────────┬──────────────────────────┘
            │              │
            v              v
┌───────────────────┐  ┌──────────────────────────────┐
│    Firestore      │  │  Google Cloud Storage        │
│  - Job state      │  │  - Uploads                   │
│  - Timeline       │  │  - Temp files                │
│  - User data      │  │  - Final outputs             │
└───────────────────┘  └──────────────────────────────┘
            │
            v
┌─────────────────────────────────────────────────────┐
│          Processing Workers                         │
│  ┌─────────────────────────────────────────┐       │
│  │  Audio Processor (Background)           │       │
│  │  - Calls audio-separator API (Modal)    │       │
│  │  - Calls AudioShake API                 │       │
│  │  - Runs LyricsTranscriber               │       │
│  │  - Updates job state                    │       │
│  └─────────────────────────────────────────┘       │
│                                                     │
│  ┌─────────────────────────────────────────┐       │
│  │  Video Generator (Cloud Build)          │       │
│  │  - FFmpeg encoding                      │       │
│  │  - Multiple format exports              │       │
│  │  - CDG/TXT generation                   │       │
│  │  - Uploads to GCS                       │       │
│  └─────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────┘
```

## Critical Path for MVP

For MVP, focus on **basic karaoke generation** without:
- ❌ Authentication (can add later)
- ❌ YouTube upload (can add later)
- ❌ Dropbox integration (can add later)
- ❌ Email/Discord notifications (can add later)
- ❌ Usage quotas/billing (can add later)

**MVP Must-Have:**
1. ✅ Job submission (URL or file upload)
2. ✅ Async audio separation (via Modal)
3. ✅ Async lyrics transcription (via AudioShake)
4. ✅ **Lyrics review interface** (critical!)
5. ✅ **Instrumental selection** (critical!)
6. ✅ Video generation (background worker)
7. ✅ File download (signed URLs)
8. ✅ Job status polling

**MVP Can Defer:**
- Lyrics review can be **one-shot** (no iterative editing)
- Instrumental can be **pre-selected** (default to "with backing vocals")
- YouTube upload can be **manual** (provide file to user)
- Notifications can be **polling-only** (no email/SMS)

## Implementation Phases

### Phase 1: Core Job Processing (Current)
- ✅ Backend API structure
- ✅ Firestore job state
- ✅ GCS file storage
- ✅ Job submission endpoint
- ✅ Status polling endpoint

### Phase 2: Async Workers (Next)
- Add background task for audio separation
- Add background task for transcription
- Integrate with Modal API
- Integrate with AudioShake API
- Store intermediate results in GCS

### Phase 3: Human Interaction Points
- **Lyrics review:**
  - Serve corrections JSON via API
  - Accept corrections submission
  - Trigger video generation on completion
- **Instrumental selection:**
  - Provide preview URLs
  - Accept selection
  - Trigger finalization

### Phase 4: Video Generation
- Cloud Build job for encoding
- Multiple format exports
- Upload to GCS
- Update job state to complete

### Phase 5: Polish & Optional Features
- Authentication
- YouTube upload
- Email notifications
- Usage quotas
- Billing integration

## Key Takeaway

**The cloud version cannot be simpler than the CLI version** because the workflow complexity is inherent to producing quality karaoke tracks. 

The cloud architecture must:
1. **Embrace async processing** (not fight it)
2. **Support human interaction** (not eliminate it)
3. **Manage state explicitly** (not rely on disk)
4. **Handle long-running tasks** (not force into request/response)

The human review and instrumental selection are **features**, not bugs. They ensure professional quality output.

