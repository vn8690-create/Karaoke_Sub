# New Architecture Documentation

## Overview

The karaoke generation system has been redesigned with a modern, scalable architecture separating frontend, backend, and GPU processing.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User / Browser                           │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ├─────────────────────────────────────────┐
                 │                                         │
         ┌───────▼───────┐                        ┌───────▼───────┐
         │   Cloudflare   │                        │   Google      │
         │     Pages      │                        │   Cloud CDN   │
         │  (Static Site) │                        │               │
         └───────┬───────┘                        └───────┬───────┘
                 │                                         │
                 │                                         │
         ┌───────▼─────────────────────────────────────────▼───────┐
         │           Google Cloud Run (Backend API)                 │
         │  ┌─────────────────────────────────────────────────┐    │
         │  │  FastAPI Application                            │    │
         │  │  - Job Management Routes                        │    │
         │  │  - File Upload Routes                           │    │
         │  │  - Health Check Routes                          │    │
         │  └───────────┬─────────────────────────────────────┘    │
         │              │                                           │
         │  ┌───────────▼─────────────────────────────────────┐    │
         │  │  Services Layer                                  │    │
         │  │  - Job Manager                                   │    │
         │  │  - Processing Service (karaoke_gen modules)      │    │
         │  │  - Firestore Service                             │    │
         │  │  - Storage Service                               │    │
         │  └───────────┬─────────────────────────────────────┘    │
         └──────────────┼──────────────────────────────────────────┘
                        │
          ┌─────────────┼─────────────┐
          │             │             │
  ┌───────▼──────┐ ┌───▼───────┐ ┌──▼─────────┐
  │  Firestore   │ │  Cloud    │ │  Secret    │
  │   (Jobs DB)  │ │  Storage  │ │  Manager   │
  │              │ │  (Files)  │ │  (API Keys)│
  └──────────────┘ └───────────┘ └────────────┘
                        │
                 ┌──────▼──────┐
                 │   Audio     │
                 │  Separator  │
                 │  API (GPU)  │
                 │   (Modal)   │
                 └─────────────┘
```

## Components

### Frontend (Cloudflare Pages)

**Technology**: React 18 + TypeScript + Vite

**Location**: `/frontend-react/`

**Features**:
- Modern React with hooks and TypeScript
- TanStack Query for API state management
- Zustand for client state
- Tailwind CSS for styling
- Real-time job status polling
- File upload with progress
- Download links for completed jobs

**Deployment**:
- Hosted on Cloudflare Pages
- Deployed automatically on git push
- Custom domain: `gen.nomadkaraoke.com`
- Global CDN distribution

### Backend (Google Cloud Run)

**Technology**: FastAPI + Python 3.11

**Location**: `/backend/`

**Architecture**:
```
backend/
├── main.py                      # FastAPI app
├── config.py                    # Settings
├── api/
│   └── routes/                  # REST API endpoints
│       ├── jobs.py             # Job CRUD operations
│       ├── uploads.py          # File upload handling
│       └── health.py           # Health checks
├── services/
│   ├── job_manager.py          # Job lifecycle management
│   ├── processing_service.py  # Karaoke processing
│   ├── firestore_service.py   # Database operations
│   └── storage_service.py     # GCS file operations
└── models/
    ├── job.py                  # Job data models
    └── requests.py             # API request models
```

**Key Features**:
- RESTful API design
- Async/await for concurrent operations
- Background job processing
- Automatic scaling (0-10 instances)
- 600s timeout for long-running jobs

**Integration**: Uses `karaoke_gen` CLI modules directly - **no code duplication**

### Database (Firestore)

**Purpose**: Job state and metadata storage

**Schema**:
```
Collection: jobs
Document: {job_id}
  - status: string (queued, processing, complete, error)
  - progress: number (0-100)
  - created_at: timestamp
  - updated_at: timestamp
  - url: string (optional)
  - artist: string (optional)
  - title: string (optional)
  - filename: string (optional)
  - timeline: array of events
  - output_files: map of file types to GCS paths
  - error_message: string (optional)
}
```

### Storage (Cloud Storage)

**Buckets**:
- `karaoke-gen-storage/uploads/` - Uploaded audio files
- `karaoke-gen-storage/outputs/` - Generated videos and files
- `karaoke-gen-storage/temp/` - Temporary processing files

**Lifecycle Policy**:
- Temp files: Delete after 7 days
- Uploads: Delete after 7 days
- Outputs: Move to Nearline after 30 days

### GPU Processing (Audio Separator API)

**Technology**: Modal.com deployment

**Purpose**: Audio separation with GPU acceleration

**Integration**: 
- Backend calls remote API via `AUDIO_SEPARATOR_API_URL`
- `karaoke_gen` audio processor automatically uses remote API
- Falls back to local processing if unavailable

## Processing Flow

### Job Submission (URL)

1. User enters YouTube URL in frontend
2. Frontend POSTs to `/api/jobs` with URL
3. Backend creates job in Firestore (status: queued)
4. Backend spawns background processing task
5. Returns job_id to frontend
6. Frontend starts polling `/api/jobs/{job_id}` for status

### Processing Workflow

1. **Download** (if URL): Download audio from YouTube/source
2. **Audio Separation** (GPU): 
   - Upload to Audio Separator API
   - Wait for GPU processing
   - Download separated stems
3. **Lyrics Processing** (CPU):
   - Fetch lyrics from Genius
   - Transcribe with AudioShake API
   - Correct and sync lyrics
4. **Video Generation** (CPU):
   - Create title screens
   - Render video with lyrics overlay
   - Generate multiple formats
5. **Upload Results**:
   - Upload files to Cloud Storage
   - Update job with file paths
   - Generate signed download URLs
6. **Complete**:
   - Update status to complete
   - Frontend displays download links

### File Upload

1. User selects file and enters artist/title
2. Frontend POSTs to `/api/upload` with multipart form data
3. Backend uploads file to GCS
4. Creates job with reference to uploaded file
5. Processing continues as above (starting from Audio Separation)

## Data Flow

```
User Input (URL/File)
    ↓
Frontend (React)
    ↓ HTTP/REST
Backend API (FastAPI)
    ↓ Job Creation
Firestore (Job Record)
    ↓ Background Processing
Processing Service
    ├→ Audio Separator API (GPU)
    ├→ AudioShake API (Transcription)
    ├→ Genius API (Lyrics)
    └→ karaoke_gen modules (Video)
         ↓
Cloud Storage (Output Files)
         ↓
Signed URLs
         ↓
Frontend (Download Links)
         ↓
User Downloads
```

## Key Design Decisions

### Why Cloud Run?

- **Auto-scaling**: Scales to zero when idle, up to 10 instances under load
- **Pay-per-use**: Only pay for actual request processing time
- **Container-based**: Easy deployment with Docker
- **Built-in load balancing**: Handles traffic distribution
- **600s timeout**: Sufficient for video rendering

### Why Firestore?

- **NoSQL flexibility**: Job data varies by type
- **Real-time updates**: Could add WebSocket support later
- **Auto-scaling**: No capacity planning needed
- **Native GCP integration**: Works seamlessly with Cloud Run
- **Simple API**: Easy to use from Python

### Why Cloudflare Pages?

- **Global CDN**: Fast load times worldwide
- **Free tier**: Unlimited bandwidth
- **GitHub integration**: Auto-deploy on push
- **Custom domains**: Easy SSL setup
- **Preview deployments**: Test before production

### Why Reuse karaoke_gen Modules?

- **Zero duplication**: Same code for CLI and web
- **Battle-tested**: CLI code is proven in production
- **Single source of truth**: Bug fixes benefit both
- **Maintainability**: One codebase to maintain
- **Remote API support**: Already integrated

## API Endpoints

### Health
- `GET /api/health` - Health check
- `GET /api/readiness` - Readiness probe

### Jobs
- `POST /api/jobs` - Create job from URL
- `GET /api/jobs/{job_id}` - Get job status
- `GET /api/jobs` - List jobs
- `DELETE /api/jobs/{job_id}` - Delete job

### Upload
- `POST /api/upload` - Upload file and create job

## Environment Variables

### Backend
- `GOOGLE_CLOUD_PROJECT` - GCP project ID
- `GCS_BUCKET_NAME` - Storage bucket name
- `FIRESTORE_COLLECTION` - Firestore collection
- `AUDIO_SEPARATOR_API_URL` - GPU API endpoint
- `AUDIOSHAKE_API_KEY` - Transcription API key
- `GENIUS_API_KEY` - Lyrics API key
- `LOG_LEVEL` - Logging level

### Frontend
- `VITE_API_URL` - Backend API URL

## Security

- **API Authentication**: Not implemented in MVP (add later)
- **CORS**: Configured to allow frontend domain
- **Secrets**: Stored in Google Secret Manager
- **Signed URLs**: Time-limited download links
- **Service Account**: Least-privilege IAM roles

## Monitoring

### Metrics
- Cloud Run request count
- Job completion rate
- Error rate
- Processing time
- Storage usage

### Logging
- Structured JSON logs in Cloud Logging
- Log levels: DEBUG, INFO, WARNING, ERROR
- Job-specific log correlation

### Alerting
- Error rate > 5%
- Instance count > 8
- Processing time > 15 minutes
- Storage > 90% capacity

## Cost Estimation

**Monthly (100 jobs)**:
- Cloud Run: $10-30
- Cloud Storage: $1-5
- Firestore: $1-5
- Cloudflare Pages: $0 (free tier)
- **Total: $15-40/month**

(Excludes Audio Separator API costs)

## Scalability

**Current Limits**:
- Max concurrent instances: 10
- Max concurrent jobs: ~50
- Max file size: 100MB
- Request timeout: 600s

**Can scale to**:
- 100+ concurrent instances
- 500+ concurrent jobs
- 1GB file sizes
- With configuration changes

## Future Enhancements

- Authentication system
- User accounts and quotas
- Stripe payment integration
- YouTube upload automation
- Lyrics review interface
- Job prioritization
- WebSocket for real-time updates
- Admin dashboard
- Analytics and reporting

## Comparison: Old vs New

| Aspect | Modal (Old) | Cloud Run + Cloudflare (New) |
|--------|-------------|------------------------------|
| Frontend Hosting | Modal | Cloudflare Pages |
| Backend Hosting | Modal | Google Cloud Run |
| GPU Processing | Modal | Audio Separator API (Modal) |
| Database | Modal Dict | Firestore |
| Storage | Modal Volume | Cloud Storage |
| Code Organization | Monolithic (app.py 7000 lines) | Modular (multiple files) |
| Code Duplication | Yes (core.py vs karaoke_gen) | No (reuses karaoke_gen) |
| Frontend Code | Vanilla JS (8000 lines) | React + TypeScript (modular) |
| Scalability | Limited | Auto-scaling |
| Cost | Higher (all-in-one) | Lower (optimized per service) |
| Maintainability | Poor | Good |
| Testing | Difficult | Easy (separate components) |

## Migration Status

✅ **Completed**:
- Modular backend architecture
- React frontend with TypeScript
- GCP infrastructure setup
- Integration with karaoke_gen modules
- Deployment documentation
- Testing guides
- Performance optimization docs
- Migration cutover plan

📋 **Next Steps**:
1. Deploy backend to Cloud Run
2. Deploy frontend to Cloudflare Pages
3. Run parallel with Modal
4. Switch DNS
5. Monitor and validate
6. Decommission Modal
7. Remove old code

## Documentation

- [GCP Setup Guide](./GCP-SETUP.md)
- [Cloudflare Pages Deployment](./CLOUDFLARE-PAGES-DEPLOYMENT.md)
- [Testing Guide](./TESTING-GUIDE.md)
- [Performance Optimization](./PERFORMANCE-OPTIMIZATION.md)
- [Migration Cutover](./MIGRATION-CUTOVER.md)
- [Backend README](../backend/README.md)
- [Frontend README](../frontend-react/README.md)

