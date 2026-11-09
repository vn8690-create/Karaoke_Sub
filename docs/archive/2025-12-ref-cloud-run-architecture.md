# Cloud Run Architecture Explained

**How our karaoke backend actually works in production**

---

## What is Cloud Run?

**Yes, Cloud Run is Google's serverless container platform** - very similar to AWS Fargate, but with more automatic scaling and "scale-to-zero" capability.

### Key Concepts

```
Cloud Run = Serverless + Containers + Auto-scaling
```

**Not like:**
- Traditional VMs (always running, fixed size)
- Kubernetes (you manage nodes, scaling, orchestration)

**Like:**
- AWS Fargate (serverless containers)
- AWS Lambda (but for containers, not just functions)
- Heroku (but with containers and better scaling)

---

## Container Lifecycle: Cold Start vs Warm

### Does the container always run?

**No!** Cloud Run can **scale to zero** when there's no traffic.

### Lifecycle Stages

```
No Traffic → Container Stopped (scale to zero)
         ↓
First Request → Cold Start (container boots)
         ↓
Active Traffic → Container Running (warm)
         ↓
15 minutes no traffic → Container Stops
```

### Cold Start (First Request)

```
1. Request arrives
2. Cloud Run pulls Docker image
3. Starts container
4. Container runs startup code (imports, FastAPI app creation)
5. uvicorn starts listening on port 8080
6. Request is processed
   
Duration: 5-10 seconds (first time)
```

### Warm State (Subsequent Requests)

```
1. Request arrives
2. Container already running
3. Request processed immediately
   
Duration: <100ms
```

### Our Current Config

```python
# infrastructure/__main__.py
backend_service = cloudrun.Service(
    # ...
    template=cloudrun.ServiceTemplateArgs(
        spec=cloudrun.ServiceTemplateSpecArgs(
            # No min_instance_count set = can scale to zero
            # No max_instance_count set = unlimited scaling
            container_concurrency=80,  # 80 requests per container
```

**What this means:**
- **Scale to zero:** If no one uses it for 15 minutes, container stops (save money!)
- **Cold starts:** First request after idle period will be slow (5-10s)
- **Warm requests:** Subsequent requests are fast (<100ms)
- **Auto-scaling:** Cloud Run automatically adds containers as needed

---

## How Our Backend Handles Requests

### Single Container Architecture

```
┌─────────────────────────────────────────┐
│     Cloud Run Container                 │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │  uvicorn (ASGI server)            │ │
│  │  - Listens on port 8080           │ │
│  │  - Handles HTTP requests          │ │
│  └───────────────────────────────────┘ │
│            ↓                            │
│  ┌───────────────────────────────────┐ │
│  │  FastAPI Application              │ │
│  │  - Route handling                 │ │
│  │  - Request validation             │ │
│  │  - Response formatting            │ │
│  └───────────────────────────────────┘ │
│            ↓                            │
│  ┌───────────────────────────────────┐ │
│  │  Background Workers               │ │
│  │  - Audio processing               │ │
│  │  - Lyrics transcription           │ │
│  │  - Video generation               │ │
│  └───────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

### One Python Process Per Container

**Yes, each container runs a single Python process:**

```bash
# Inside the container:
$ ps aux
USER       PID COMMAND
root         1 python -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

**That's it!** Just one Python process running uvicorn + FastAPI.

---

## Concurrency: Multiple Users

### Scenario 1: Low Traffic (1 container)

```
Container 1 (80 concurrent requests max)
┌────────────────────────────────┐
│ Request 1: User A → Job 123    │
│ Request 2: User B → Job 124    │
│ Request 3: User A → Status 123 │
│                                │
│ All handled by same container  │
└────────────────────────────────┘
```

**Within one container:**
- uvicorn handles requests **asynchronously** using Python's `asyncio`
- Each request gets its own coroutine
- **Blocking operations** (like FFmpeg) run in `BackgroundTasks`
- Up to **80 concurrent requests** per container

### Scenario 2: High Traffic (auto-scaling)

```
Request 81 arrives → Cloud Run starts Container 2

Container 1                    Container 2
┌──────────────────┐          ┌──────────────────┐
│ Requests 1-80    │          │ Requests 81-160  │
│ (User A, B, C)   │          │ (User D, E, F)   │
└──────────────────┘          └──────────────────┘

Request 161 arrives → Cloud Run starts Container 3

Container 3
┌──────────────────┐
│ Requests 161-240 │
│ (User G, H)      │
└──────────────────┘
```

**Cloud Run automatically:**
1. Monitors container CPU/memory/concurrency
2. Starts new containers when needed
3. Routes requests to available containers
4. Stops containers when traffic decreases

### Our Configuration

```python
container_concurrency=80  # 80 requests per container
```

**What happens with concurrent users:**

| Users | Requests/sec | Containers | Behavior |
|-------|--------------|------------|----------|
| 1-5 | <10 | 1 | Single container handles all |
| 10-50 | 50-100 | 2-3 | Cloud Run adds containers |
| 100+ | 200+ | 3-5 | Auto-scales up |
| 0 | 0 | 0 | Scales to zero after 15 min |

---

## How Background Jobs Work

### The Problem

Karaoke generation takes **5-30 minutes**. We can't hold HTTP connection that long!

### Our Solution: Async Job Queue

```
User Request (POST /jobs/upload)
    ↓
FastAPI creates job in Firestore (status: pending)
    ↓
FastAPI triggers background worker via BackgroundTasks
    ↓
FastAPI returns job_id immediately (200 OK)
    ↓
Worker processes job in background (same container)
    ↓
User polls status (GET /jobs/{job_id})
```

### Inside One Container

```python
# backend/api/routes/file_upload.py

@router.post("/upload")
async def upload_file(
    file: UploadFile,
    background_tasks: BackgroundTasks,  # ← FastAPI's background task system
    # ...
):
    # 1. Quick operations (synchronous)
    job = job_manager.create_job(...)  # Fast: creates Firestore doc
    storage_service.upload_file(...)    # Fast: uploads to GCS
    
    # 2. Trigger long-running work in background
    background_tasks.add_task(
        worker_service.trigger_worker,
        "audio",
        job.job_id
    )
    
    # 3. Return immediately
    return {"job_id": job.job_id, "status": "pending"}
    # HTTP response sent!
    # Container continues processing in background...
```

### Background Processing

```
Container Lifecycle with Background Job:

1. Request arrives → Create job → Return response (200ms)
2. HTTP connection closes
3. Container stays alive, processing job in background
4. Worker runs: audio separation (10 min)
5. Worker runs: lyrics transcription (5 min)
6. Worker runs: video generation (15 min)
7. Job completes → Container can handle new requests during this time!
8. If no new requests for 15 min → Container stops
```

**Key insight:** The container doesn't dedicate itself to one job. It can:
- Process multiple jobs in parallel (up to resource limits)
- Handle new API requests while jobs run in background
- Continue processing even if user disconnects

---

## Resource Limits & Isolation

### Current Configuration

```python
# infrastructure/__main__.py
resources=cloudrun.ServiceTemplateSpecContainerResourcesArgs(
    limits={
        "cpu": "4000m",      # 4 CPU cores
        "memory": "8192Mi",  # 8 GB RAM
    },
),
```

### What Happens with Multiple Jobs?

**Scenario: 3 users start jobs simultaneously**

```
Container 1 (4 CPU, 8 GB RAM)
┌─────────────────────────────────────┐
│ Job 1 (User A): Audio separation    │ → 1 CPU, 2 GB
│ Job 2 (User B): Audio separation    │ → 1 CPU, 2 GB
│ Job 3 (User C): Lyrics transcription│ → 0.5 CPU, 1 GB
│                                     │
│ Total: 2.5 CPU, 5 GB used          │
│ Remaining: 1.5 CPU, 3 GB available │
└─────────────────────────────────────┘
```

**If container resources are exhausted:**
- Cloud Run starts a new container
- New jobs go to the new container
- Each container is isolated (separate processes, memory spaces)

### Isolation Between Jobs

**Within one container:**
```python
# Each job runs in its own asyncio task
async def process_audio_separation(job_id: str):
    # This task is isolated from other tasks
    # But shares CPU/memory with other tasks in same container
    ...

# Multiple tasks can run concurrently
await asyncio.gather(
    process_audio_separation("job_123"),
    process_lyrics_transcription("job_124"),
    generate_video("job_125"),
)
```

**Across containers:**
- Completely isolated
- Separate Python processes
- Separate memory spaces
- Cannot interfere with each other

---

## Current Limitations & Future Improvements

### Current Design: All-in-One Container

```
┌─────────────────────────────────────┐
│  Single Container Does Everything:  │
│  - API requests                     │
│  - Audio processing (FFmpeg)        │
│  - Lyrics transcription (API calls) │
│  - Video generation (FFmpeg)        │
└─────────────────────────────────────┘
```

**Problems:**
1. ❌ CPU-heavy jobs (video encoding) can slow down API responses
2. ❌ Limited parallelism (4 CPUs per container)
3. ❌ Can't scale API independently from workers
4. ❌ Container timeout (Cloud Run max: 60 minutes)

### Future: Separate Worker Architecture

```
┌─────────────────┐         ┌──────────────────────┐
│  API Container  │         │  Worker Containers   │
│  (Fast, always  │  Pub/   │  (Heavy processing)  │
│   responsive)   │  Sub    │  - Audio worker      │
│                 │ ─────→  │  - Lyrics worker     │
│  - Job CRUD     │         │  - Video worker      │
│  - Status       │         │  (Auto-scale 0-100)  │
└─────────────────┘         └──────────────────────┘
```

**Benefits:**
- ✅ API always fast (not blocked by processing)
- ✅ Workers can scale independently (100+ parallel jobs)
- ✅ Can use different machine types (GPU for video)
- ✅ No timeout issues (workers can run for hours)

**How to implement:**
1. Use Google Cloud Pub/Sub for job queue
2. Separate Cloud Run services for API and workers
3. Workers pull jobs from Pub/Sub
4. Update job status in Firestore

---

## Comparison with Other Platforms

### Cloud Run vs AWS Fargate

| Feature | Cloud Run | AWS Fargate |
|---------|-----------|-------------|
| **Scale to zero** | ✅ Yes | ❌ No (min 1 task) |
| **Cold start** | 5-10s | 30-60s |
| **Pricing** | Pay per request + CPU time | Pay for running tasks |
| **Max timeout** | 60 min | Unlimited |
| **Auto-scaling** | Automatic | Manual (via ECS) |

### Cloud Run vs AWS Lambda

| Feature | Cloud Run | AWS Lambda |
|---------|-----------|-------------|
| **Container support** | ✅ Any Docker image | Limited (max 10 GB) |
| **Timeout** | 60 min | 15 min |
| **CPU** | Up to 8 CPUs | Up to 6 vCPUs |
| **Memory** | Up to 32 GB | Up to 10 GB |
| **Concurrency** | Configurable (1-1000) | 1 per instance |

### Our Use Case

**Cloud Run is good for us because:**
- ✅ Can run FFmpeg in containers
- ✅ Scale to zero (save money during low usage)
- ✅ Simple deployment (just Docker image)
- ✅ 60-minute timeout (enough for most videos)

**Cloud Run is limiting for us because:**
- ⚠️ CPU-heavy jobs can slow down API
- ⚠️ 60-minute timeout (some videos take longer)
- ⚠️ Limited parallelism per container

**Future solution:** Separate API + worker architecture

---

## How to Monitor

### Check Active Containers

```bash
# See current container instances
gcloud run services describe karaoke-backend \
  --region us-central1 \
  --format="value(status.traffic[0].latestRevision,status.traffic[0].percent)"

# See container metrics
gcloud run services list --platform managed --region us-central1
```

### Check Logs

```bash
# See all container logs
gcloud logging read "resource.type=cloud_run_revision" --limit=50

# See specific job processing
gcloud logging read "resource.type=cloud_run_revision AND textPayload=~'job_123'" --limit=50
```

### Cloud Console

**Best way to see real-time activity:**
1. Go to: https://console.cloud.google.com/run
2. Click `karaoke-backend`
3. Click **METRICS** tab
4. See:
   - Request count
   - Container instance count
   - CPU utilization
   - Memory utilization

---

## Summary

### Your Questions Answered

**Q: Is Cloud Run like AWS Fargate?**  
**A:** Yes! Serverless container platform, very similar.

**Q: Does container always run?**  
**A:** No! Scales to zero after 15 minutes of no traffic. First request has "cold start" delay.

**Q: Single Python process for all jobs?**  
**A:** Yes, one Python process per container. But multiple containers can run in parallel.

**Q: Can multiple people use it concurrently?**  
**A:** Yes! Two ways:
1. **Within container:** Up to 80 concurrent requests (handled asynchronously)
2. **Across containers:** Cloud Run auto-starts new containers as needed

**Q: Would separate containers start?**  
**A:** Yes, when:
- Container reaches 80 concurrent requests
- Container CPU/memory is maxed out
- Cloud Run decides it needs more capacity

### Current Architecture

```
Internet → Load Balancer → Container Pool → Firestore
                                ↓
                          GCS (files)
                                ↓
                          Background Jobs
```

**Each container:**
- 4 CPUs, 8 GB RAM
- Handles 80 concurrent HTTP requests
- Processes multiple background jobs
- Auto-scales from 0 to ∞

**Perfect for:** Low-to-medium traffic, occasional usage
**Limitations:** CPU-intensive jobs can impact API performance

**Future:** Separate API and worker containers for better scalability! 🚀

