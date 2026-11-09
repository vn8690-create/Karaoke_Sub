# Observability & Debugging Guide

**How to debug issues in production**

---

## Quick Debug Tools

### 1. Debug Script (Recommended)

**Single command to see everything about a job:**

```bash
./scripts/debug-job.sh <job_id>
```

**Shows:**
- ✅ Job status and progress
- ✅ Full timeline of events
- ✅ GCS file existence
- ✅ Cloud Run logs
- ✅ Firestore document fields
- ✅ Color-coded errors/warnings

**Example:**
```bash
$ ./scripts/debug-job.sh e168cb20

========================================
Debugging Job: e168cb20
========================================

1. Job Status:
---
{
  "status": "failed",
  "progress": 0,
  "error_message": "Failed to download audio file",
  "error_details": {
    "error": "Failed to download audio file",
    "stage": "audio_separation"
  },
  "timeline": 2
}

2. Timeline (last 10 events):
---
2025-12-01T07:17:03.968082 [failed] Failed: Audio separation failed
2025-12-01T07:17:06.706201 [failed] Failed: Lyrics transcription failed

3. GCS Files:
---
⚠ No input_media_gcs_path in job

4. Cloud Run Logs (last 20 relevant):
---
[2025-12-01T07:17:03] ERROR: Job e168cb20: Failed to download audio: 'Job' object has no attribute 'input_media_gcs_path'

========================================
Summary:
✗ Job failed: Failed to download audio file
========================================
```

---

## Manual Debugging

### Check Job Status

```bash
export BACKEND_URL="https://karaoke-backend-ipzqd2k4yq-uc.a.run.app"
export AUTH_TOKEN=$(gcloud auth print-identity-token)
export JOB_ID="your-job-id"

# Quick status
curl -s "$BACKEND_URL/api/jobs/$JOB_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN" | \
  jq '{status, progress, error_message}'

# Full details
curl -s "$BACKEND_URL/api/jobs/$JOB_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN" | jq .

# Timeline
curl -s "$BACKEND_URL/api/jobs/$JOB_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN" | \
  jq '.timeline[] | "\(.timestamp) [\(.status)] \(.message)"'
```

---

## Logging

### Current Logging Setup

**What we log:**
- ✅ Job creation
- ✅ Worker starts/stops
- ✅ File uploads/downloads
- ✅ Errors with stack traces
- ✅ State transitions
- ✅ API requests (uvicorn)

**Log levels:**
- `INFO` - Normal operations
- `ERROR` - Failures (what we care about)
- `WARNING` - Potential issues

### View Logs

#### 1. Logs for Specific Job

```bash
JOB_ID="e168cb20"

# All logs for this job
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend AND textPayload=~"'$JOB_ID'"' \
  --limit=50 \
  --format="table(timestamp,severity,textPayload)"
```

#### 2. Recent Errors

```bash
# Last 20 errors
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend AND severity>=ERROR' \
  --limit=20 \
  --format="table(timestamp,textPayload)"
```

#### 3. Worker-Specific Logs

```bash
# Audio worker logs
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend AND textPayload=~"audio_worker"' \
  --limit=20

# Lyrics worker logs
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend AND textPayload=~"lyrics_worker"' \
  --limit=20
```

#### 4. Live Tail

```bash
# Stream logs in real-time
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend" \
  --format="value(timestamp,severity,textPayload)"
```

### Log Format

Our logs follow this pattern:

```
YYYY-MM-DD HH:MM:SS,mmm - <module> - <level> - <message>

Examples:
2025-12-01 07:17:03,628 - backend.services.job_manager - INFO - Created new job e168cb20
2025-12-01 07:17:03,967 - backend.workers.audio_worker - ERROR - Job e168cb20: Failed to download audio
```

---

## GCS File Inspection

### Check if Files Exist

```bash
JOB_ID="e168cb20"

# List all files for a job
gsutil ls -r gs://karaoke-gen-storage-nomadkaraoke/uploads/$JOB_ID/

# Check specific file
gsutil ls gs://karaoke-gen-storage-nomadkaraoke/uploads/$JOB_ID/input.flac

# Get file size
gsutil du -h gs://karaoke-gen-storage-nomadkaraoke/uploads/$JOB_ID/
```

### Download Files for Local Inspection

```bash
# Download input file
gsutil cp gs://karaoke-gen-storage-nomadkaraoke/uploads/$JOB_ID/input.flac /tmp/

# Check if it's valid
ffprobe /tmp/input.flac
```

---

## Firestore Inspection

### View Job Document

```bash
# Get job from Firestore
gcloud firestore documents get \
  "projects/nomadkaraoke/databases/(default)/documents/jobs/$JOB_ID"

# Prettier output
gcloud firestore documents get \
  "projects/nomadkaraoke/databases/(default)/documents/jobs/$JOB_ID" \
  --format=json | jq .
```

### List Recent Jobs

```bash
# Last 10 jobs
gcloud firestore documents list \
  "projects/nomadkaraoke/databases/(default)/documents/jobs" \
  --limit=10 \
  --format="table(name,createTime,updateTime)"
```

---

## Cloud Run Service Health

### Service Status

```bash
# Current revision status
gcloud run services describe karaoke-backend \
  --region us-central1 \
  --format="value(status.latestReadyRevisionName,status.conditions[0].status,status.conditions[0].message)"

# List all revisions
gcloud run revisions list \
  --service karaoke-backend \
  --region us-central1 \
  --format="table(metadata.name,status.conditions[0].status,metadata.creationTimestamp)"
```

### Container Metrics

**In Cloud Console:**
1. Go to https://console.cloud.google.com/run/detail/us-central1/karaoke-backend/metrics
2. View:
   - Request count
   - Request latency
   - Container instance count
   - CPU utilization
   - Memory utilization

**Via gcloud:**
```bash
# Get metrics (last hour)
gcloud monitoring time-series list \
  --filter='resource.type="cloud_run_revision" AND resource.labels.service_name="karaoke-backend"' \
  --format=json
```

---

## Improving Observability

### What's Missing

1. **❌ Structured logging** - Currently just text logs
2. **❌ Request tracing** - No distributed tracing
3. **❌ Custom metrics** - No business metrics (jobs/sec, etc.)
4. **❌ Alerts** - No automated alerts on failures
5. **❌ Dashboard** - No centralized monitoring

### Recommendations

#### 1. Add Structured Logging

**Current:**
```python
logger.error(f"Job {job_id}: Failed to download audio")
```

**Better:**
```python
logger.error("Failed to download audio", extra={
    "job_id": job_id,
    "stage": "audio_separation",
    "gcs_path": gcs_path,
    "error_type": "download_failed"
})
```

**Benefit:** Can filter/query by fields in Cloud Logging

#### 2. Add Cloud Trace Integration

```python
# In backend/main.py
from google.cloud import trace_v1

# Trace each request
@app.middleware("http")
async def trace_requests(request, call_next):
    with trace_v1.tracer() as tracer:
        with tracer.span(name=f"{request.method} {request.url.path}"):
            response = await call_next(request)
    return response
```

**Benefit:** See request flow through workers

#### 3. Add Custom Metrics

```python
# backend/services/metrics.py
from google.cloud import monitoring_v3

def record_job_completed(job_id: str, duration_seconds: float):
    client = monitoring_v3.MetricServiceClient()
    # Record custom metric
    ...
```

**Metrics to track:**
- Jobs created per hour
- Jobs completed per hour
- Jobs failed per hour
- Average processing time
- Worker queue depth

#### 4. Set Up Alerts

```bash
# Alert on high error rate
gcloud alpha monitoring policies create \
  --notification-channels=<channel-id> \
  --display-name="High Job Failure Rate" \
  --condition-display-name="Job failures > 10/min" \
  --condition-threshold-value=10 \
  --condition-threshold-duration=60s
```

#### 5. Create Dashboard

**Looker Studio or Cloud Monitoring Dashboard:**
- Job status pie chart (completed/failed/pending)
- Jobs over time (line chart)
- Error rate (bar chart)
- Processing time histogram
- Worker status (gauge)

---

## Common Issues & How to Debug

### Issue: Job Fails Immediately

**Symptoms:**
```json
{
  "status": "failed",
  "progress": 0,
  "error_message": "Failed to download audio file"
}
```

**Debug steps:**
1. Check logs for the job: `./scripts/debug-job.sh <job_id>`
2. Look for ERROR lines
3. Check if `input_media_gcs_path` is set
4. Verify file exists in GCS

### Issue: Job Stuck in Processing

**Symptoms:**
```json
{
  "status": "processing_audio",
  "progress": 10,
  "updated_at": "2025-12-01T06:00:00Z"  # 30 minutes ago
}
```

**Debug steps:**
1. Check if worker is still running: `gcloud logging tail ...`
2. Check container resources (CPU/memory)
3. Check for timeout errors
4. Check if worker crashed silently

### Issue: No Jobs Being Created

**Symptoms:**
```
curl -X POST .../jobs/upload
# Returns 500 error
```

**Debug steps:**
1. Check Cloud Run logs for errors
2. Check if Firestore is accessible
3. Check if environment variables are set
4. Check if service account has permissions

---

## Quick Reference Commands

```bash
# Export these once
export BACKEND_URL="https://karaoke-backend-ipzqd2k4yq-uc.a.run.app"
export AUTH_TOKEN=$(gcloud auth print-identity-token)

# Debug job
./scripts/debug-job.sh <job_id>

# Get job status
curl -s "$BACKEND_URL/api/jobs/<job_id>" -H "Authorization: Bearer $AUTH_TOKEN" | jq .

# View recent errors
gcloud logging read 'resource.type=cloud_run_revision AND severity>=ERROR' --limit=20

# Tail logs
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend"

# Check service health
gcloud run services describe karaoke-backend --region us-central1

# List GCS files
gsutil ls -r gs://karaoke-gen-storage-nomadkaraoke/uploads/<job_id>/
```

---

## Summary

### Current Observability: ⭐⭐⭐☆☆ (3/5)

**Good:**
- ✅ Comprehensive logging
- ✅ Cloud Logging integration
- ✅ Job timeline in Firestore
- ✅ Debug script for quick inspection

**Needs Improvement:**
- ⚠️ No structured logging (hard to query)
- ⚠️ No distributed tracing
- ⚠️ No custom metrics
- ⚠️ No alerts
- ⚠️ No centralized dashboard

### Next Steps

1. **Short-term:** Use `./scripts/debug-job.sh` for debugging
2. **Medium-term:** Add structured logging
3. **Long-term:** Add traces, metrics, alerts, dashboard

**The debug script makes it easy to investigate issues now!** 🔍

