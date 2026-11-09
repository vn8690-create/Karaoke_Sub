# Scalable Architecture Plan

**Last Updated:** 2025-12-11
**Status:** Phase 1 Complete - Cloud Tasks Enabled

This document outlines the plan for evolving karaoke-gen's cloud backend to support **100+ concurrent jobs** with no performance degradation, while also achieving a clean, maintainable codebase with proper separation of concerns.

---

## Executive Summary

After thorough codebase analysis, I recommend a **phased approach** that prioritizes infrastructure scalability first (Cloud Tasks), followed by incremental adoption of the existing pipeline architecture for code sharing.

### Key Findings

1. **The infrastructure problem is well-isolated** - WorkerService already abstracts worker triggering behind HTTP calls
2. **Pipeline architecture exists but is underutilized** - `karaoke_gen/pipeline/` has well-designed stages and executors, but backend workers don't use them
3. **RemoteExecutor is a placeholder** - It submits jobs to the backend but doesn't execute stages remotely
4. **Workers are self-contained** - Each worker only needs `job_id` and fetches everything from Firestore/GCS

### Recommended Priority

1. **Phase 1 (HIGH): Cloud Tasks Integration** - Solves the scalability problem immediately
2. **Phase 2 (MEDIUM): Cloud Run Jobs for Video** - Removes 30-min timeout constraint
3. **Phase 3 (LOW): Pipeline Unification** - Nice-to-have for code maintainability

---

## Goals

### Infrastructure Goals
1. **Horizontal scalability** - Each job gets dedicated resources (no resource contention)
2. **Maximum processing speed** - Same speed for 1 job or 100 concurrent jobs
3. **Reliability** - Automatic retries, no lost jobs from container restarts
4. **Cost efficiency** - Scale to zero when idle, pay only for active processing

### Software Architecture Goals
1. **SOLID principles** - Single responsibility, clean interfaces
2. **DRY** - Share code between local CLI and remote backend
3. **Testability** - Each component independently testable
4. **Maintainability** - Bug fixes apply everywhere, easy to add features

---

## Current Architecture Analysis

### What Works Well

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CURRENT ARCHITECTURE (v0.71.x)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ✅ Heavy work already offloaded to external services:                     │
│                                                                             │
│   Audio Separation  ──────────────────▶  Modal API (GPU, ~5-8 min)         │
│   Lyrics Transcription  ──────────────▶  AudioShake API (~2-3 min)         │
│                                                                             │
│   ✅ State persistence in Firestore (survives restarts)                     │
│   ✅ Files in GCS (no local storage dependencies)                           │
│   ✅ Internal HTTP endpoints exist for worker triggers                      │
│   ✅ Workers are self-contained (only need job_id)                          │
│   ✅ WorkerService abstracts HTTP calls                                     │
│   ✅ Pipeline stages exist in karaoke_gen/pipeline/                         │
│   ✅ LocalExecutor for CLI, RemoteExecutor placeholder ready                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Current Code Structure

```
WorkerService (backend/services/worker_service.py)
    │
    └── trigger_worker(worker_type, job_id)
            │
            └── HTTP POST /api/internal/workers/{worker_type}
                    │
                    └── BackgroundTasks.add_task(process_xxx, job_id)  ⚠️ PROBLEM
```

The **single point of change** is `WorkerService.trigger_worker()`. Currently it:
1. Makes HTTP POST to internal endpoint
2. Internal endpoint adds to FastAPI BackgroundTasks
3. BackgroundTask runs in same container (problem!)

### Current Limitations

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CURRENT FLOW (PROBLEMATIC)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   POST /api/jobs/upload                                                     │
│      │                                                                      │
│      ├──▶ Save job to Firestore  ✅                                         │
│      │                                                                      │
│      └──▶ BackgroundTasks.add_task(trigger_workers)                        │
│               │                                                             │
│               └──▶ HTTP POST /api/internal/workers/audio                   │
│                        │                                                    │
│                        └──▶ BackgroundTasks.add_task(process_audio)  ⚠️    │
│                                   │                                         │
│                                   └── Runs IN THE SAME CONTAINER            │
│                                       as the API request handler            │
│                                                                             │
│   PROBLEMS:                                                                 │
│   ⚠️  Container may be killed before background tasks complete              │
│   ⚠️  No guaranteed delivery - if container crashes, job is lost            │
│   ⚠️  Multiple concurrent jobs share CPU/memory (resource contention)       │
│   ⚠️  Long-running video encoding (15-20 min) vulnerable to timeouts        │
│   ⚠️  FFmpeg renders compete for resources when jobs run in parallel        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Existing Pipeline Architecture (Underutilized)

The codebase already has a well-designed pipeline system:

```
karaoke_gen/pipeline/
├── base.py              # PipelineStage, StageResult, PipelineExecutor abstracts
├── context.py           # PipelineContext for shared state
├── executors/
│   ├── local.py         # LocalExecutor - runs stages in-process (for CLI)
│   └── remote.py        # RemoteExecutor - placeholder for backend integration
└── stages/
    ├── separation.py    # SeparationStage - wraps AudioProcessor
    ├── transcription.py # TranscriptionStage - wraps LyricsProcessor  
    ├── screens.py       # ScreensStage - title/end screens
    ├── render.py        # RenderStage - lyrics video
    └── finalize.py      # FinalizeStage - wraps KaraokeFinalise
```

**However**: Backend workers (`backend/workers/*.py`) don't use these stages - they directly call the underlying processors. This creates two parallel implementations.

---

## Recommended Architecture

### Decision: Cloud Tasks First

**Why Cloud Tasks over Pub/Sub or Workflows:**

| Feature | Cloud Tasks | Pub/Sub | Workflows |
|---------|-------------|---------|-----------|
| HTTP delivery | ✅ Native | Requires push subscription | N/A |
| Retry control | ✅ Built-in | Manual | Built-in |
| Rate limiting | ✅ Built-in | Manual | N/A |
| Timeout (max) | 30 min | 10 min ack deadline | 1 year |
| Complexity | Low | Medium | High |
| Cost | Very low | Low | Medium |
| Existing code changes | Minimal | Medium | High |

**Cloud Tasks is the right choice because:**
1. Workers already have HTTP endpoints - Cloud Tasks delivers HTTP requests
2. Need rate limiting to protect Modal/AudioShake APIs
3. Built-in retries with configurable backoff
4. Minimal code changes (update WorkerService only)

### Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLOUD TASKS + CLOUD RUN JOBS ARCHITECTURE               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   POST /api/jobs/upload                                                     │
│      │                                                                      │
│      ├──▶ Save job to Firestore                                            │
│      │                                                                      │
│      └──▶ WorkerService.trigger_worker()                                   │
│              │                                                              │
│              │  if ENABLE_CLOUD_TASKS:                                     │
│              │     └──▶ Enqueue Cloud Task                                 │
│              │              │                                               │
│              │              ├──▶ audio-worker-queue                        │
│              │              │    {job_id, target: /internal/workers/audio} │
│              │              │                                               │
│              │              └──▶ lyrics-worker-queue                       │
│              │                   {job_id, target: /internal/workers/lyrics}│
│              │                                                              │
│              │  else: (development/testing)                                │
│              │     └──▶ HTTP POST directly (existing behavior)             │
│              │                                                              │
│   ┌──────────▼────────────────────────────────────────────────────────┐   │
│   │                     Cloud Tasks Queue                               │   │
│   │                                                                     │   │
│   │  • Guaranteed delivery (retries on failure)                        │   │
│   │  • Rate limiting / concurrency control                             │   │
│   │  • Task deduplication                                              │   │
│   │  • Configurable timeouts (up to 30 min per task)                   │   │
│   └─────────────────────────────────┬───────────────────────────────────┘   │
│                                     │                                      │
│                                     ▼                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │           Cloud Run (Auto-Scaled Worker Instances)                   │  │
│   │                                                                      │  │
│   │   Instance 1        Instance 2        Instance 3        ...         │  │
│   │   ┌──────────┐      ┌──────────┐      ┌──────────┐                  │  │
│   │   │  Job A   │      │  Job B   │      │  Job C   │                  │  │
│   │   │  Audio   │      │  Audio   │      │  Lyrics  │                  │  │
│   │   └──────────┘      └──────────┘      └──────────┘                  │  │
│   │                                                                      │  │
│   │   Each task gets a DEDICATED container instance                     │  │
│   │   • Full CPU/memory for that task alone                             │  │
│   │   • No resource contention with other jobs                          │  │
│   │   • Container lifecycle tied to task completion                     │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   For video encoding (>30 min timeout):                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │           Cloud Run Jobs (Long-Running)                              │  │
│   │                                                                      │  │
│   │   • Up to 24 hour timeout                                           │  │
│   │   • Separate from API service                                       │  │
│   │   • Higher CPU/memory (4 vCPU, 8GB)                                │  │
│   │   • Triggered via gcloud or API                                     │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Cloud Tasks Integration (HIGH Priority)

**Goal:** Enable 100+ concurrent jobs with no performance degradation

**Effort:** 2-3 days | **Risk:** Low (feature-flagged, easy rollback)

#### Step 1.1: Add Cloud Tasks Infrastructure (Pulumi)

```python
# infrastructure/__main__.py additions

from pulumi_gcp import cloudtasks

# Create Cloud Tasks queues
audio_worker_queue = cloudtasks.Queue(
    "audio-worker-queue",
    name="audio-worker-queue",
    location="us-central1",
    rate_limits=cloudtasks.QueueRateLimitsArgs(
        max_dispatches_per_second=10,  # Protect Modal API
        max_concurrent_dispatches=50,   # Max parallel audio workers
    ),
    retry_config=cloudtasks.QueueRetryConfigArgs(
        max_attempts=3,
        min_backoff="10s",
        max_backoff="300s",
        max_retry_duration="1800s",  # 30 min total retry window
    ),
)

lyrics_worker_queue = cloudtasks.Queue(
    "lyrics-worker-queue", 
    name="lyrics-worker-queue",
    location="us-central1",
    rate_limits=cloudtasks.QueueRateLimitsArgs(
        max_dispatches_per_second=10,
        max_concurrent_dispatches=50,
    ),
    retry_config=cloudtasks.QueueRetryConfigArgs(
        max_attempts=3,
        min_backoff="10s",
        max_backoff="300s",
    ),
)

screens_worker_queue = cloudtasks.Queue(
    "screens-worker-queue",
    name="screens-worker-queue", 
    location="us-central1",
    rate_limits=cloudtasks.QueueRateLimitsArgs(
        max_dispatches_per_second=50,  # Fast, CPU-light
        max_concurrent_dispatches=100,
    ),
    retry_config=cloudtasks.QueueRetryConfigArgs(
        max_attempts=3,
        min_backoff="5s",
        max_backoff="60s",
    ),
)

render_worker_queue = cloudtasks.Queue(
    "render-worker-queue",
    name="render-worker-queue",
    location="us-central1",
    rate_limits=cloudtasks.QueueRateLimitsArgs(
        max_dispatches_per_second=5,   # CPU-intensive
        max_concurrent_dispatches=20,
    ),
    retry_config=cloudtasks.QueueRetryConfigArgs(
        max_attempts=2,
        min_backoff="30s",
        max_backoff="300s",
        max_retry_duration="3600s",  # 60 min for render
    ),
)

video_worker_queue = cloudtasks.Queue(
    "video-worker-queue",
    name="video-worker-queue",
    location="us-central1",
    rate_limits=cloudtasks.QueueRateLimitsArgs(
        max_dispatches_per_second=3,   # Very CPU-intensive
        max_concurrent_dispatches=10,
    ),
    retry_config=cloudtasks.QueueRetryConfigArgs(
        max_attempts=2,
        min_backoff="60s",
        max_backoff="600s",
        max_retry_duration="7200s",  # 2 hour total (video is long)
    ),
)

# Grant Cloud Tasks permission to invoke Cloud Run
cloud_tasks_invoker = gcp.projects.IAMMember(
    "cloud-tasks-invoker",
    project=project_id,
    role="roles/run.invoker",
    member=f"serviceAccount:service-{project.number}@gcp-sa-cloudtasks.iam.gserviceaccount.com",
)

# Export queue names
pulumi.export("audio_worker_queue", audio_worker_queue.name)
pulumi.export("lyrics_worker_queue", lyrics_worker_queue.name)
pulumi.export("screens_worker_queue", screens_worker_queue.name)
pulumi.export("render_worker_queue", render_worker_queue.name)
pulumi.export("video_worker_queue", video_worker_queue.name)
```

#### Step 1.2: Update WorkerService for Cloud Tasks

```python
# backend/services/worker_service.py - Updated

import logging
import os
import json
from typing import Optional
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Queue mapping
WORKER_QUEUES = {
    "audio": "audio-worker-queue",
    "lyrics": "lyrics-worker-queue", 
    "screens": "screens-worker-queue",
    "render-video": "render-worker-queue",
    "video": "video-worker-queue",
}

class WorkerService:
    """
    Service for coordinating background workers.
    
    Supports two modes:
    - Cloud Tasks (production): Guaranteed delivery, auto-scaling
    - Direct HTTP (development): Faster iteration, simpler debugging
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._base_url = self._get_base_url()
        self._admin_token = self._get_admin_token()
        self._use_cloud_tasks = self._should_use_cloud_tasks()
        self._tasks_client = None
        
    def _should_use_cloud_tasks(self) -> bool:
        """Check if Cloud Tasks should be used."""
        # Feature flag with environment variable
        enable_flag = os.getenv("ENABLE_CLOUD_TASKS", "false").lower()
        return enable_flag in ("true", "1", "yes")
    
    @property
    def tasks_client(self):
        """Lazy-init Cloud Tasks client."""
        if self._tasks_client is None and self._use_cloud_tasks:
            self._tasks_client = tasks_v2.CloudTasksClient()
        return self._tasks_client
    
    def _get_admin_token(self) -> Optional[str]:
        admin_tokens_str = self.settings.admin_tokens or ""
        tokens = [t.strip() for t in admin_tokens_str.split(",") if t.strip()]
        return tokens[0] if tokens else None
    
    def _get_base_url(self) -> str:
        # Check for test environment override
        test_url = os.getenv("TEST_SERVER_URL")
        if test_url:
            return test_url
        
        # Production: Cloud Run service URL
        service_url = os.getenv("CLOUD_RUN_SERVICE_URL")
        if service_url:
            return service_url
        
        # Development: localhost
        port = os.getenv("PORT", "8000")
        return f"http://localhost:{port}"
    
    async def trigger_worker(
        self,
        worker_type: str,
        job_id: str,
        timeout_seconds: int = 30
    ) -> bool:
        """
        Trigger a background worker.
        
        In production (ENABLE_CLOUD_TASKS=true):
          - Enqueues task to Cloud Tasks queue
          - Cloud Tasks calls internal endpoint with retries
          
        In development:
          - Direct HTTP call to internal endpoint
          - Faster iteration, but no retry guarantees
        """
        if self._use_cloud_tasks:
            return await self._enqueue_cloud_task(worker_type, job_id)
        else:
            return await self._trigger_http(worker_type, job_id, timeout_seconds)
    
    async def _enqueue_cloud_task(self, worker_type: str, job_id: str) -> bool:
        """Enqueue task to Cloud Tasks for guaranteed delivery."""
        try:
            queue_name = WORKER_QUEUES.get(worker_type)
            if not queue_name:
                logger.error(f"Unknown worker type: {worker_type}")
                return False
            
            project = self.settings.google_cloud_project
            location = "us-central1"
            
            # Build queue path
            parent = self.tasks_client.queue_path(project, location, queue_name)
            
            # Build task
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": f"{self._base_url}/api/internal/workers/{worker_type}",
                    "headers": {
                        "Content-Type": "application/json",
                    },
                    "body": json.dumps({"job_id": job_id}).encode(),
                    # Use OIDC token for Cloud Run authentication
                    "oidc_token": {
                        "service_account_email": f"karaoke-backend@{project}.iam.gserviceaccount.com",
                    },
                },
            }
            
            # Add admin auth header if available
            if self._admin_token:
                task["http_request"]["headers"]["Authorization"] = f"Bearer {self._admin_token}"
            
            # Create task
            response = self.tasks_client.create_task(parent=parent, task=task)
            logger.info(f"Created Cloud Task for {worker_type} worker, job {job_id}: {response.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enqueue Cloud Task for {worker_type}/{job_id}: {e}", exc_info=True)
            return False
    
    async def _trigger_http(
        self,
        worker_type: str,
        job_id: str,
        timeout_seconds: int = 30
    ) -> bool:
        """Direct HTTP trigger (for development)."""
        try:
            headers = {}
            if self._admin_token:
                headers["Authorization"] = f"Bearer {self._admin_token}"
            
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                url = f"{self._base_url}/api/internal/workers/{worker_type}"
                response = await client.post(url, json={"job_id": job_id}, headers=headers)
                
                if response.status_code == 200:
                    logger.info(f"Triggered {worker_type} worker for job {job_id}")
                    return True
                else:
                    logger.error(f"Failed to trigger {worker_type}: HTTP {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error triggering {worker_type} worker: {e}", exc_info=True)
            return False
    
    # Convenience methods (unchanged)
    async def trigger_audio_worker(self, job_id: str) -> bool:
        return await self.trigger_worker("audio", job_id)
    
    async def trigger_lyrics_worker(self, job_id: str) -> bool:
        return await self.trigger_worker("lyrics", job_id)
    
    async def trigger_screens_worker(self, job_id: str) -> bool:
        return await self.trigger_worker("screens", job_id)
    
    async def trigger_video_worker(self, job_id: str) -> bool:
        return await self.trigger_worker("video", job_id)
    
    async def trigger_render_video_worker(self, job_id: str) -> bool:
        return await self.trigger_worker("render-video", job_id)
```

#### Step 1.3: Update Internal Endpoints for Cloud Tasks

The internal endpoints need minor updates to handle Cloud Tasks requests:

```python
# backend/api/routes/internal.py - Updates

# Add idempotency check to prevent duplicate processing
@router.post("/workers/audio", response_model=WorkerResponse)
async def trigger_audio_worker(
    request: WorkerRequest,
    background_tasks: BackgroundTasks,
    auth_data: Tuple[str, UserType, int] = Depends(require_admin)
):
    """Trigger audio separation worker for a job."""
    job_id = request.job_id
    
    # Idempotency: Check if already processing
    job_manager = JobManager()
    job = job_manager.get_job(job_id)
    
    if job and job.state_data.get('audio_progress', {}).get('stage') == 'running':
        logger.info(f"Audio worker already running for job {job_id}, skipping")
        return WorkerResponse(
            status="already_running",
            job_id=job_id,
            message="Audio worker already in progress"
        )
    
    # Mark as running before starting (for idempotency)
    job_manager.update_state_data(job_id, 'audio_progress', {'stage': 'running'})
    
    logger.info(f"Triggering audio worker for job {job_id}")
    background_tasks.add_task(process_audio_separation, job_id)
    
    return WorkerResponse(
        status="started",
        job_id=job_id,
        message="Audio separation worker started"
    )
```

#### Step 1.4: Cloud Run Service Account Permissions

```python
# infrastructure/__main__.py additions

# Grant Cloud Tasks admin permission to the service account
# (needed to create tasks)
cloud_tasks_admin = gcp.projects.IAMMember(
    "karaoke-backend-cloudtasks-admin",
    project=project_id,
    role="roles/cloudtasks.enqueuer",
    member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)
```

### Phase 2: Cloud Run Jobs for Video Worker (MEDIUM Priority)

**Goal:** Remove 30-minute timeout constraint for video encoding

**Effort:** 1-2 days | **Risk:** Low

The video worker (final encoding) can take 15-20 minutes, sometimes longer. Cloud Tasks has a 30-minute max timeout. For safety, we use Cloud Run Jobs.

#### Step 2.1: Create Cloud Run Job

```yaml
# cloudbuild-video-job.yaml
steps:
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
      - 'run'
      - 'jobs'
      - 'create'
      - 'video-encoding-job'
      - '--image=${_IMAGE}'
      - '--region=us-central1'
      - '--cpu=4'
      - '--memory=8Gi'
      - '--max-retries=2'
      - '--task-timeout=3600'  # 1 hour max
      - '--service-account=karaoke-backend@${PROJECT_ID}.iam.gserviceaccount.com'
      - '--set-env-vars=GOOGLE_CLOUD_PROJECT=${PROJECT_ID}'
```

#### Step 2.2: Update Video Worker Trigger

```python
# backend/services/worker_service.py - Addition

async def trigger_video_worker_job(self, job_id: str) -> bool:
    """Trigger video worker as Cloud Run Job (for long-running encoding)."""
    if not self._use_cloud_tasks:
        # Development: use HTTP trigger
        return await self._trigger_http("video", job_id)
    
    try:
        from google.cloud import run_v2
        
        client = run_v2.JobsClient()
        project = self.settings.google_cloud_project
        location = "us-central1"
        
        job_name = f"projects/{project}/locations/{location}/jobs/video-encoding-job"
        
        # Override container args with job_id
        request = run_v2.RunJobRequest(
            name=job_name,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    run_v2.RunJobRequest.Overrides.ContainerOverride(
                        args=["--job-id", job_id],
                    )
                ]
            )
        )
        
        operation = client.run_job(request=request)
        logger.info(f"Started Cloud Run Job for video encoding: {job_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start video encoding job: {e}", exc_info=True)
        return False
```

### Phase 3: Pipeline Unification (LOW Priority - Future)

**Goal:** Share code between CLI and backend workers

**Effort:** 1-2 weeks | **Risk:** Medium (requires careful refactoring)

This phase can be deferred - the infrastructure scaling (Phase 1-2) solves the immediate problem.

**When to consider this:**
- When adding new features that need to work in both CLI and backend
- When a bug fix needs to be applied in multiple places
- When the divergence between workers and pipeline stages causes maintenance burden

**Approach:**
1. Make backend workers call pipeline stages instead of processors directly
2. Have RemoteExecutor use Cloud Tasks to trigger stage execution
3. Both CLI and backend use the same pipeline stages

---

## Resource Configuration

### Cloud Tasks Queues

| Queue | Max Concurrent | Rate Limit | Timeout | Retries | Notes |
|-------|---------------|------------|---------|---------|-------|
| audio-worker | 50 | 10/sec | 15 min | 3 | Mostly I/O (Modal API) |
| lyrics-worker | 50 | 10/sec | 10 min | 3 | Mostly I/O (AudioShake) |
| screens-worker | 100 | 50/sec | 2 min | 3 | FFmpeg (quick) |
| render-worker | 20 | 5/sec | 30 min | 2 | LyricsTranscriber + FFmpeg |
| video-worker | 10 | 3/sec | 30 min | 2 | Heavy FFmpeg (or use Jobs) |

### Cloud Run Instance Scaling

| Worker | CPU | Memory | Max Instances | Notes |
|--------|-----|--------|---------------|-------|
| audio | 2 | 2Gi | 50 | Mostly waiting on Modal API |
| lyrics | 2 | 2Gi | 50 | Mostly waiting on AudioShake |
| screens | 2 | 2Gi | 100 | Quick FFmpeg |
| render | 4 | 4Gi | 20 | CPU-intensive |
| video (Job) | 4 | 8Gi | 10 | Very CPU-intensive |

### Cost Estimate (100 concurrent jobs/day)

```
Cloud Tasks:    ~$0.40/million tasks    ≈ $0.01/day
Cloud Run:      ~$0.00002/vCPU-sec      ≈ $5-10/day (100 jobs)
Cloud Run Jobs: ~$0.00002/vCPU-sec      ≈ $2-5/day (100 jobs)
Modal (GPU):    ~$2.50/hour             ≈ $20-40/day (100 jobs)
AudioShake:     Usage-based             ≈ $10-20/day (100 jobs)

Total: ~$40-80/day for 100 concurrent jobs
```

---

## Migration Strategy

### Zero-Downtime Migration

```
Week 1: Deploy Cloud Tasks infrastructure (Pulumi)
        └── Queues exist but aren't used yet (ENABLE_CLOUD_TASKS=false)

Week 2: Test in staging
        └── Deploy to staging with ENABLE_CLOUD_TASKS=true
        └── Run 10-20 test jobs concurrently
        └── Monitor for issues

Week 3: Enable in production
        └── Set ENABLE_CLOUD_TASKS=true
        └── Monitor metrics and logs
        └── Have rollback ready

Week 4: Cleanup
        └── Remove feature flag after stable week
        └── Update documentation
```

### Rollback Plan

If issues occur after enabling Cloud Tasks:
1. Set `ENABLE_CLOUD_TASKS=false` environment variable
2. Redeploy (takes ~2 minutes)
3. New jobs use direct HTTP (old behavior)
4. In-flight Cloud Tasks jobs continue to completion
5. No data loss - Firestore has job state

### Testing Strategy

```bash
# Run unit tests (no Cloud Tasks)
pytest backend/tests/ -v

# Run integration tests with Cloud Tasks (staging)
ENABLE_CLOUD_TASKS=true pytest backend/tests/integration/ -v

# Load test (staging)
# Submit 50 concurrent jobs, verify all complete
for i in {1..50}; do
  curl -X POST "https://staging.api.nomadkaraoke.com/api/jobs/upload" \
    -F "file=@test.flac" -F "artist=Test" -F "title=Job$i" &
done
wait
```

---

## Success Criteria

### Phase 1 (Cloud Tasks)
- [x] Cloud Tasks queues created and configured via Pulumi
- [x] WorkerService updated to support Cloud Tasks mode
- [x] Deployment configured with ENABLE_CLOUD_TASKS=true
- [x] Container concurrency set to 1 for true isolation
- [ ] 50 concurrent jobs complete without failures (to be validated)
- [ ] Processing time per job unchanged (same as 1 job)
- [ ] No resource contention (CPU/memory per job consistent)
- [ ] Automatic retry on transient failures works
- [ ] Feature flag rollback works

### Phase 2 (Cloud Run Jobs)
- [ ] Video encoding >30 min completes successfully
- [ ] Jobs triggered correctly from WorkerService
- [ ] Progress updates visible in CLI

### Phase 3 (Pipeline Unification)
- [ ] Single stage implementation used by both CLIs
- [ ] Bug fixes apply to both local and remote execution
- [ ] Each stage independently testable
- [ ] 80%+ code coverage on pipeline module

---

## Files to Modify

### Phase 1

| File | Changes |
|------|---------|
| `infrastructure/__main__.py` | Add Cloud Tasks queues, IAM permissions |
| `backend/services/worker_service.py` | Add Cloud Tasks client, feature flag |
| `backend/api/routes/internal.py` | Add idempotency checks |
| `backend/config.py` | Add ENABLE_CLOUD_TASKS setting |
| `backend/requirements.txt` | Add google-cloud-tasks |

### Phase 2

| File | Changes |
|------|---------|
| `cloudbuild-video-job.yaml` | New file for Cloud Run Job |
| `backend/services/worker_service.py` | Add Cloud Run Jobs trigger |
| `backend/workers/video_worker.py` | CLI entry point for Jobs |

---

## Related Documents

- [ARCHITECTURE.md](../01-reference/ARCHITECTURE.md) - Current system architecture
- [BACKEND-FEATURE-PARITY-PLAN.md](./BACKEND-FEATURE-PARITY-PLAN.md) - Feature parity roadmap
- [WORKER-IMPLEMENTATION-PLAN.md](./WORKER-IMPLEMENTATION-PLAN.md) - Worker details

---

## Changelog

### 2025-12-11: Analysis Complete - Updated Plan

- **Analyzed codebase thoroughly** - found existing pipeline architecture underutilized
- **Confirmed Cloud Tasks as best approach** - minimal code changes, single point of change
- **Identified WorkerService as sole modification point** - clean abstraction exists
- **Decided against immediate pipeline unification** - infrastructure scaling is the priority
- **Added detailed implementation code** - ready to start Phase 1
- **Created phased approach** - Phase 1 (Cloud Tasks) → Phase 2 (Jobs) → Phase 3 (Pipeline)

### 2025-12-11: Initial Plan
- Documented current architecture limitations
- Proposed Cloud Tasks + Cloud Run Jobs hybrid
- Outlined shared pipeline architecture
- Created implementation roadmap
