# Web-Based Karaoke Generator - Master Migration Plan

> **Read this first!** This is the primary plan for migrating from Modal to scalable cloud architecture.
>
> For detailed CLI workflow analysis, see [`CLOUD-MIGRATION-REQUIREMENTS.md`](CLOUD-MIGRATION-REQUIREMENTS.md)

---

## Executive Summary

**Goal:** Build a production-ready web version of karaoke-gen that maintains CLI quality while being scalable and maintainable.

**Status:** ✅ Phase 1.1 Complete (Backend API) | ⏭️ Next: Phase 1.2 (Async Processing)

**Key Insight:** The CLI workflow is **not a simple batch job** - it's a multi-stage, human-in-the-loop process that takes 30-45 minutes with **2 required human interaction points**. The cloud architecture must embrace this complexity, not fight it.

---

## Current State Analysis

### Problems with Modal Version
- [`app.py`](../../app.py) (7000+ lines): Monolithic backend
- [`frontend/app.js`](../../frontend/app.js) (8000+ lines): Monolithic frontend
- Everything served from Modal (frontend + backend + GPU)
- Code duplication between CLI and web version
- Performance issues with concurrent jobs

### Why We're Migrating
1. **Maintainability:** Monolithic code is unmaintainable
2. **Scalability:** Modal not suited for frontend + long-running backend tasks
3. **Code Reuse:** Eliminate duplication between CLI and web
4. **Cost:** Better cost control with GCP credits
5. **Quality:** CLI is battle-tested, web version is not

---

## Target Architecture

```
┌─────────────────────────────────────────────────────┐
│          Frontend (Cloudflare Pages)                │
│  - React + TypeScript                               │
│  - Job submission                                   │
│  - Lyrics review interface ⚠️ CRITICAL             │
│  - Instrumental selection ⚠️ CRITICAL               │
│  - Progress tracking                                │
│  - File download                                    │
└───────────────────┬─────────────────────────────────┘
                    │ HTTPS
                    v
┌─────────────────────────────────────────────────────┐
│       Backend API (Cloud Run - FastAPI)             │
│  - Job creation & status                            │
│  - Corrections submission                           │
│  - Signed URL generation                            │
│  - Async task coordination                          │
└───────────┬──────────────┬──────────────────────────┘
            │              │
            v              v
┌───────────────────┐  ┌──────────────────────────────┐
│    Firestore      │  │  Google Cloud Storage        │
│  - Job state      │  │  - Uploads                   │
│  - Timeline       │  │  - Temp files (7-day expiry) │
│  - User data      │  │  - Finals (30-day expiry)    │
└───────────────────┘  └──────────────────────────────┘
            │
            v
┌─────────────────────────────────────────────────────┐
│          Processing Workers (Async)                 │
│  ┌─────────────────────────────────────────┐       │
│  │  Audio/Lyrics Processor                 │       │
│  │  - Calls audio-separator API (Modal)    │       │
│  │  - Calls AudioShake API                 │       │
│  │  - Runs LyricsTranscriber               │       │
│  │  - State: awaiting_review               │       │
│  └─────────────────────────────────────────┘       │
│  ┌─────────────────────────────────────────┐       │
│  │  Video Generator (Cloud Build)          │       │
│  │  - FFmpeg encoding (15-20 min)          │       │
│  │  - Multiple format exports              │       │
│  │  - Uploads to GCS                       │       │
│  └─────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────┘
```

**External Services:**
- **Modal:** Audio separation (GPU, 3-5 min)
- **AudioShake:** Lyrics transcription (API, 1-2 min)
- **Genius/Spotify:** Lyrics fetching (APIs, <1 min)
- **YouTube API:** Video upload (optional, 2-5 min)

---

## Migration Strategy: MVP-First Approach

Focus on **basic karaoke generation** only.

### MVP Scope (MUST HAVE)
✅ Job submission (URL or file upload)  
✅ Async audio separation (via Modal API)  
✅ Async lyrics transcription (via AudioShake)  
✅ **Lyrics review interface** (human-in-the-loop)  
✅ **Instrumental selection** (human choice)  
✅ Video generation (background worker)  
✅ File download (signed URLs)  
✅ Job status polling  

### Post-MVP (DEFER)
❌ Authentication (can be simple token-based initially)  
❌ Stripe payments (can charge $2 manually)  
❌ YouTube upload (users can download & upload manually)  
❌ Email/Discord notifications (polling-only for MVP)  
❌ Admin dashboard (can use Firestore console)  

---

## Phase 1: Backend Refactoring ✅ COMPLETE

### 1.1 Create Modular Backend Structure ✅ DONE

**Created:**
```
backend/
├── main.py                      # FastAPI app entry point
├── api/
│   ├── routes/
│   │   ├── jobs.py             # Job submission, status, deletion
│   │   ├── uploads.py          # File upload handling
│   │   └── health.py           # Health checks
│   └── dependencies.py         # Shared dependencies
├── services/
│   ├── job_manager.py          # Job state management
│   ├── storage_service.py      # GCS file operations
│   ├── firestore_service.py    # Database operations
│   └── processing_service.py   # Core karaoke processing
├── models/
│   ├── job.py                  # Job data models
│   └── requests.py             # API request models
├── config.py                   # Configuration management
├── requirements.txt
├── Dockerfile                  # For Cloud Run deployment
└── tests/
    └── test_api_integration.py # Integration tests (17/17 passing)
```

**Key Achievements:**
- ✅ Modular, maintainable code structure
- ✅ Comprehensive tests (17/17 passing)
- ✅ Deployed to Cloud Run
- ✅ All infrastructure in Pulumi (IaC)
- ✅ Manual API testing documented

### 1.2 Integrate karaoke_gen CLI Modules ⏭️ NEXT

**Goal:** Reuse CLI code to eliminate duplication

**Critical Understanding:**
The CLI workflow has **8 stages** (see [`CLOUD-MIGRATION-REQUIREMENTS.md`](CLOUD-MIGRATION-REQUIREMENTS.md)):
1. Input & Setup
2. **Parallel Processing** (audio separation + lyrics transcription)
3. Title/End Screen Generation
4. Countdown Padding Synchronization
5. **Human Review** (BLOCKING - 5-15 min)
6. **Human Instrumental Selection** (BLOCKING - 30 sec)
7. Video Finalization (remux, encode, package)
8. Distribution (YouTube, Dropbox, notifications)

**What This Means for Cloud Version:**
- Cannot be synchronous request/response
- Need **job state machine** with 9 states
- Need **async workers** for long-running tasks
- Need **notifications** for human interaction points
- Need **persistent storage** (Firestore + GCS)

**Implementation Plan:**

**Step 1: Audio Separation Worker** (Background task in Cloud Run)
```python
# services/audio_worker.py
async def process_audio_separation(job_id: str):
    """
    Calls Modal audio-separator API
    2-stage process:
      Stage 1: Clean instrumental (3-5 min)
      Stage 2: Backing vocals (2-3 min)
    Updates job state to 'separation_complete'
    """
```

**Step 2: Lyrics Transcription Worker** (Background task in Cloud Run)
```python
# services/lyrics_worker.py
async def process_lyrics_transcription(job_id: str):
    """
    1. Fetches lyrics from Genius/Spotify
    2. Calls AudioShake API for transcription (1-2 min)
    3. Runs automatic correction
    4. Generates corrections JSON
    5. Updates job state to 'awaiting_review'
    6. STOPS - waits for human review
    """
```

**Step 3: Human Review Interface** (React component)
```tsx
// frontend/src/components/LyricsReview.tsx
// Loads corrections JSON from GCS
// Renders lyrics-transcriber review UI
// Allows user to edit/correct
// Submits corrections back to API
// Triggers job state change to 'review_complete'
```

**Step 4: Instrumental Selection** (React component)
```tsx
// frontend/src/components/InstrumentalSelector.tsx
// Provides audio player for both options:
//   1. Clean instrumental (no backing vocals)
//   2. Instrumental with backing vocals
// User listens and chooses
// Submits selection to API
```

**Step 5: Video Generation Worker** (Cloud Build job)
```yaml
# Video encoding is CPU-intensive (15-20 min)
# Better suited to Cloud Build than Cloud Run
# Can allocate more CPU/RAM
# Doesn't block API requests
```

**Key Files to Reuse from CLI:**
- `karaoke_gen/karaoke_gen.py::KaraokePrep` - Main processing class
- `karaoke_gen/audio_processor.py::AudioProcessor` - Audio separation
- `karaoke_gen/lyrics_processor.py::LyricsProcessor` - Transcription
- `karaoke_gen/video_generator.py::VideoGenerator` - Title/end screens
- `karaoke_gen/karaoke_finalise/karaoke_finalise.py::KaraokeFinalise` - Final packaging

**Environment Variables:**
```bash
# Tells AudioProcessor to use remote API instead of local
AUDIO_SEPARATOR_API_URL=https://nomadkaraoke--audio-separator-api.modal.run

# AudioShake API for transcription
AUDIOSHAKE_API_TOKEN=<secret>

# Lyrics sources
GENIUS_API_TOKEN=<secret>
RAPIDAPI_KEY=<secret>
SPOTIFY_COOKIE_SP_DC=<secret>

# GCS configuration
GOOGLE_CLOUD_PROJECT=nomadkaraoke
GCS_UPLOAD_BUCKET=karaoke-gen-uploads
GCS_TEMP_BUCKET=karaoke-gen-temp
GCS_OUTPUT_BUCKET=karaoke-gen-outputs
```

### 1.3 Setup Google Cloud Infrastructure ✅ DONE

**Provisioned via Pulumi:**
- ✅ Firestore database (`jobs` collection with indexes)
- ✅ Cloud Storage buckets (uploads, temp, outputs)
- ✅ Cloud Run service (backend API)
- ✅ Secret Manager (API keys)
- ✅ Artifact Registry (Docker images)
- ✅ IAM roles and permissions
- ✅ Cloud Build triggers

**Documentation:**
- See [`../03-deployment/INFRASTRUCTURE-AS-CODE.md`](../03-deployment/INFRASTRUCTURE-AS-CODE.md)

---

## Phase 2: Frontend Rebuild ⏸️ WAITING FOR BACKEND

### Why We're Waiting
Backend must be **100% stable** with async processing working before we build frontend. Otherwise we're building UI for non-functional backend.

### 2.1 Create React Application

**Tech Stack:**
- React 18 + TypeScript
- Vite for build tooling
- TanStack Query for API state management
- Tailwind CSS for styling
- Zustand for client state management

**Structure:**
```
frontend-react/
├── src/
│   ├── components/
│   │   ├── JobSubmission.tsx       # Upload/URL input
│   │   ├── JobStatus.tsx           # Progress display
│   │   ├── LyricsReview.tsx        # ⚠️ CRITICAL - human review
│   │   ├── InstrumentalSelector.tsx # ⚠️ CRITICAL - user choice
│   │   ├── DownloadResults.tsx     # Download links
│   │   └── ErrorDisplay.tsx        # Error handling
│   ├── hooks/
│   │   ├── useJobSubmit.ts         # Job submission logic
│   │   ├── useJobStatus.ts         # Polling for status
│   │   ├── useFileUpload.ts        # File upload handling
│   │   └── useJobCorrections.ts    # Submit corrections
│   ├── services/
│   │   └── api.ts                  # Backend API client
│   ├── types/
│   │   └── job.ts                  # TypeScript types
│   ├── App.tsx
│   └── main.tsx
├── public/
├── package.json
└── vite.config.ts
```

### 2.2 Critical UI Components

**Lyrics Review Interface:**
The most complex component. Must support:
- Audio playback with synchronized highlighting
- Word-level editing
- Line splitting/merging
- Timing adjustments
- Preview video generation
- Submit corrections to backend

**Technical Approach:**
- Reuse `lyrics-transcriber` React components (from `lyrics_transcriber_local/`)
- Load corrections JSON from GCS signed URL
- Play audio from GCS signed URL
- Submit corrections via `POST /api/jobs/{job_id}/corrections`

**Instrumental Selector:**
Simpler component. Must support:
- Play audio preview (2 options)
- Select option
- Submit selection via `POST /api/jobs/{job_id}/select-instrumental`

### 2.3 Deploy to Cloudflare Pages

**Setup:**
1. Connect GitHub repo
2. Configure build: `npm run build`
3. Set custom domain: `gen.nomadkaraoke.com`
4. Environment variables: `VITE_API_URL=https://karaoke-backend-xxx.run.app`

---

## Phase 3: Integration & Testing

### 3.1 End-to-End Workflow Testing

**Test Scenarios:**
1. ✅ Job submission (URL)
2. ✅ Job submission (file upload)
3. ⏭️ Audio separation (async)
4. ⏭️ Lyrics transcription (async)
5. ⏭️ Human review flow
6. ⏭️ Instrumental selection
7. ⏭️ Video generation
8. ⏭️ File download
9. ⏭️ Concurrent jobs
10. ⏭️ Error handling

### 3.2 Performance Optimization

**Backend:**
- Cloud Run scaling: min 0, max 10
- Request timeout: 60s (API), 3600s (workers)
- GCS signed URLs (24hr expiry)
- Firestore indexes for queries

**Frontend:**
- Code splitting
- Asset optimization
- Service worker for offline status
- Progressive loading

### 3.3 Monitoring & Logging

**Setup:**
- Cloud Logging for all services
- Firestore metrics dashboard
- Error tracking (Cloud Error Reporting)
- Job completion rate tracking
- Cost monitoring

---

## Phase 4: Migration & Cleanup

### 4.1 Cutover Process

1. Deploy backend to Cloud Run ✅ DONE
2. Test backend thoroughly ✅ DONE
3. Build & deploy frontend ⏭️ TODO
4. Test end-to-end ⏭️ TODO
5. Update DNS to point to new frontend ⏭️ TODO
6. Monitor for 24 hours ⏭️ TODO
7. Shut down Modal deployment ⏭️ TODO

### 4.2 Code Cleanup

**Remove (after migration complete):**
- `app.py` (7000 lines → replaced)
- `core.py` (duplication → eliminated)
- `frontend/app.js` (8000 lines → replaced)
- Modal-specific configuration

**Keep:**
- `karaoke_gen/` (shared with CLI)
- `backend/` (new modular backend)
- `frontend-react/` (new React frontend)
- `infrastructure/` (Pulumi IaC)
- `docs/` (updated documentation)
- `tests/` (updated tests)

### 4.3 Documentation Updates

**Update:**
- Main README with new architecture
- API documentation
- Deployment guides
- User guides

---

## Key Technical Decisions

### Why This Architecture?

**Cloud Run for Backend:**
- Auto-scaling (0 to N instances)
- Pay-per-use pricing
- Container-based deployment
- 60-minute timeout (for long tasks)
- Native GCP integration

**Firestore for State:**
- Real-time updates
- Flexible schema
- Auto-scaling
- Native GCP integration
- Good for job state machine

**GCS for Files:**
- Large file support (~2GB working files)
- Signed URLs for secure access
- Lifecycle policies for cost control
- Native GCP integration

**Cloudflare Pages for Frontend:**
- Free hosting
- Global CDN
- Automatic HTTPS
- GitHub integration
- Fast deployment

### Why Reuse karaoke_gen Modules?

**Benefits:**
- ✅ Zero code duplication
- ✅ Battle-tested CLI code
- ✅ One codebase to maintain
- ✅ Bug fixes benefit both CLI and web
- ✅ Remote API support already exists

**Key Insight:**
`karaoke_gen/audio_processor.py` already supports remote audio separation via `AUDIO_SEPARATOR_API_URL` environment variable. Just set it and GPU tasks automatically offload to Modal!

### Why Human Review is Non-Negotiable?

**Quality Requirements:**
- Transcription has errors (homophones, slang, proper nouns)
- Artistic decisions needed (line breaks, timing)
- Professional output requires human validation
- 5-15 minutes per song (acceptable tradeoff)

**Cannot be automated without sacrificing quality.**

---

## Current Status & Next Steps

### ✅ Completed (Phase 1.1)
- Backend API structure
- Firestore job state
- GCS file storage
- Job submission endpoint
- Status polling endpoint
- Job deletion endpoint
- Comprehensive tests (17/17 passing)
- Deployed to Cloud Run
- Infrastructure as code (Pulumi)

### ⏭️ Next (Phase 1.2)
1. **Implement async audio separation worker**
   - Background task in Cloud Run
   - Calls Modal audio-separator API
   - Updates job state to `separation_complete`

2. **Implement async lyrics transcription worker**
   - Background task in Cloud Run
   - Calls AudioShake API
   - Runs automatic correction
   - Updates job state to `awaiting_review`

3. **Add corrections submission endpoint**
   - `POST /api/jobs/{job_id}/corrections`
   - Validates corrections data
   - Updates job state to `review_complete`
   - Triggers video generation

4. **Add instrumental selection endpoint**
   - `POST /api/jobs/{job_id}/select-instrumental`
   - Records user choice
   - Triggers finalization

5. **Implement video generation worker**
   - Cloud Build job (long-running)
   - FFmpeg encoding
   - Multiple format exports
   - Upload to GCS

6. **Test complete workflow end-to-end**
   - Manual testing with real songs
   - Verify state transitions
   - Check file outputs
   - Validate timings

### 🎯 Success Criteria for Phase 1.2
- Audio separation completes successfully
- Transcription produces corrections JSON
- Job state transitions work correctly
- Files are stored in GCS
- Timeline events track progress
- Can manually trigger review/selection via API

---

## Estimated Timeline

**Phase 1.1 Backend:** ✅ 3 days (COMPLETE)  
**Phase 1.2 Async Processing:** ⏭️ 3-4 days  
**Phase 2 Frontend:** 3-4 days  
**Phase 3 Integration:** 2-3 days  
**Phase 4 Migration:** 1-2 days  

**Total MVP: 12-16 days**

---

## Cost Estimates

**Per Job Costs:**
- Cloud Run (processing): $0.05
- Cloud Build (video): $0.20
- GCS storage (30 days): $0.10
- GCS bandwidth: $0.05
- AudioShake API: $0.04
- **Total: ~$0.44 per job**

**Target Pricing:** $2.00 per job  
**Margin:** $1.56 (78%)

---

## Risk Mitigation

**Risk:** Long-running tasks timeout  
**Mitigation:** Use background workers, Cloud Build for encoding

**Risk:** Concurrent job confusion  
**Mitigation:** Firestore transactions for state updates, job isolation via job_id

**Risk:** Large file costs  
**Mitigation:** GCS lifecycle policies (7-day temp, 30-day finals), signed URLs, compression

**Risk:** Human review abandonment  
**Mitigation:** Email notification, 7-day expiry, save partial progress

**Risk:** Cost overrun  
**Mitigation:** Usage quotas, cost monitoring, optimize encoding settings

---

## Future Enhancements (Post-MVP)

These features exist in Modal version but are deferred:

- **Authentication:** User accounts, private jobs
- **Stripe Payments:** Automated $2 charging
- **YouTube Upload:** Automatic to user's channel
- **Admin Dashboard:** Job monitoring, user management
- **Notifications:** Email/SMS for review ready, job complete
- **Job Queue Prioritization:** Premium users, bulk uploads
- **CDG/TXT Generation:** Karaoke machine formats
- **Multiple Output Formats:** 720p, 1080p, 4K options
- **Custom Branding:** User-uploaded fonts, logos
- **Dropbox Integration:** Auto-upload to Dropbox
- **Discord Notifications:** Team alerts

---

## Related Documentation

- [`CLOUD-MIGRATION-REQUIREMENTS.md`](CLOUD-MIGRATION-REQUIREMENTS.md) - Detailed architecture analysis
- [`../01-reference/KARAOKE-GEN-CLI-WORKFLOW.md`](../01-reference/KARAOKE-GEN-CLI-WORKFLOW.md) - CLI workflow breakdown
- [`../01-reference/API-MANUAL-TESTING.md`](../01-reference/API-MANUAL-TESTING.md) - How to test backend API
- [`../03-deployment/INFRASTRUCTURE-AS-CODE.md`](../03-deployment/INFRASTRUCTURE-AS-CODE.md) - Pulumi setup
- [`../03-deployment/TESTING-BACKEND.md`](../03-deployment/TESTING-BACKEND.md) - Running tests

---

## Questions or Issues?

1. Check this plan first
2. Review [`CLOUD-MIGRATION-REQUIREMENTS.md`](CLOUD-MIGRATION-REQUIREMENTS.md) for architectural details
3. Look at session summaries in `../02-implementation-history/`
4. Check deployment guides in `../03-deployment/`
