# Observability & Tracing Plan for Karaoke Generator

**Created:** 2025-12-22  
**Status:** Planning  
**Priority:** High  

## Executive Summary

The karaoke-gen backend has **partial observability infrastructure** but **no rich tracing implemented**. While the code includes OpenTelemetry setup and tracing utilities, actual job processing is minimally instrumented. This means debugging job failures requires manually querying Cloud Logging with grep-style searches rather than clicking through a trace waterfall.

### Current State: 🟡 Partial

| Capability | Status | Notes |
|------------|--------|-------|
| **Logs exported to Cloud Logging** | ✅ Working | Standard Python logs visible |
| **OpenTelemetry SDK installed** | ✅ Working | Dependencies in pyproject.toml |
| **Cloud Trace exporter configured** | 🟡 Broken | 403 permission errors (fixed in infra today) |
| **FastAPI auto-instrumentation** | ✅ Working | HTTP requests create spans |
| **HTTPX instrumentation** | ✅ Working | Outgoing HTTP calls traced |
| **Job ID correlation in logs** | ❌ Missing | Can't filter logs by job ID |
| **Worker tracing spans** | ❌ Missing | No spans in audio/lyrics workers |
| **Custom metrics** | ❌ Missing | No Cloud Monitoring metrics |
| **Dashboard** | ❌ Missing | No pre-built observability view |
| **Alerting** | ❌ Missing | No alerts for job failures |

### What You Can Do Today

```bash
# Query Cloud Logging for a specific job (manual grep)
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload:"JOB_ID"' \
  --project=nomadkaraoke --limit=100

# View traces (once permission is fixed)
# Go to: https://console.cloud.google.com/traces/list?project=nomadkaraoke
```

### What You Should Be Able To Do

1. Go to a dashboard, enter job ID → see entire job lifecycle
2. Click trace → see waterfall of audio worker, lyrics worker, Cloud Tasks
3. See metrics: jobs/hour, success rate, p95 latency by stage
4. Get alerted when job failure rate exceeds threshold

---

## Current Implementation Analysis

### 1. Tracing Infrastructure (Exists, Partially Working)

**File: `backend/services/tracing.py`**

```python
# Good: SDK is set up, exporter is configured
setup_tracing(service_name="karaoke-backend", service_version=VERSION)

# Good: Utility functions exist
@traced("my-function")  # Decorator for automatic spans
with create_span("operation", {"job_id": job_id}):  # Context manager
add_span_attribute("key", "value")  # Add to current span
```

**Problem:** These utilities are barely used! Only `backend/api/routes/review.py` actually creates spans for business logic. The critical workers (`audio_worker.py`, `lyrics_worker.py`, etc.) have zero tracing.

### 2. Logging Infrastructure (Exists, Not Correlated)

**File: `backend/workers/worker_logging.py`**

```python
# Good: Logs go to Firestore for CLI streaming
class JobLogHandler(logging.Handler):
    """Forwards logs to Firestore job document"""
    
# Good: Context vars prevent log mixing in concurrent jobs
with job_logging_context(job_id):
    # logs isolated per job
```

**Problem:** Logs go to Firestore for CLI display, but Cloud Logging has no job_id label. You can't filter Cloud Logging by job ID.

### 3. Permission Issues (Fixed Today)

The Cloud Trace exporter was failing with 403 errors because the Cloud Run service account lacked `roles/cloudtrace.agent`. This was just fixed in `infrastructure/__main__.py`:

```python
# NEW: Added today
cloud_trace_iam = gcp.projects.IAMMember(
    "karaoke-backend-cloudtrace-agent",
    role="roles/cloudtrace.agent",
    ...
)
```

---

## Gap Analysis: What's Missing

### Gap 1: No Trace Context Propagation to Workers

When Cloud Tasks triggers a worker (audio, lyrics), a new trace is started. The parent trace from the initial API call is lost.

```
Current:
POST /uploads-complete → Trace A
                ↓ (Cloud Task)
POST /internal/workers/audio → NEW Trace B (no link to A!)
```

**Should be:**
```
POST /uploads-complete → Trace A
                ↓ (Cloud Task - propagates trace context)
POST /internal/workers/audio → Trace A, Span B (child of A)
```

### Gap 2: No Job ID on Traces

Even when traces exist, they don't have `job_id` as a searchable attribute. You can't search Cloud Trace for "all spans for job 8f03f0ac".

### Gap 3: No Custom Spans in Workers

The workers just log text. There are no spans for:
- Audio download duration
- Modal API call duration  
- GCS upload duration
- Lyrics transcription duration
- Each processing stage

### Gap 4: No Structured Logging with Job Context

Cloud Logging receives unstructured text logs. Should be structured JSON with `job_id`, `worker`, `stage` fields for filtering.

### Gap 5: No Metrics

No custom Cloud Monitoring metrics for:
- Jobs started/completed/failed per hour
- Processing time by stage (p50, p95, p99)
- Queue depth
- Error rates

### Gap 6: No Dashboard

No Cloud Console dashboard showing:
- Active jobs
- Success/failure rates
- Latency distribution
- Worker health

### Gap 7: No Alerting

No alerts for:
- Job stuck in status > X minutes
- Error rate spike
- Worker health degradation

---

## Implementation Plan

### Phase 1: Fix Core Tracing (2-3 hours) ⭐ High Priority

**Goal:** Every job should have a single trace that spans its entire lifecycle.

#### 1.1 Propagate Trace Context Through Cloud Tasks

**File: `backend/services/worker_service.py`**

```python
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry import trace

def _enqueue_cloud_task(self, queue: str, endpoint: str, payload: Dict, ...):
    # Get current trace context
    propagator = TraceContextTextMapPropagator()
    carrier = {}
    propagator.inject(carrier)  # Injects traceparent header
    
    # Add trace context to task headers
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
        **carrier,  # Add traceparent, tracestate
    }
    
    task = {
        "http_request": {
            "http_method": "POST",
            "url": url,
            "headers": headers,  # Now includes trace context
            "body": base64.b64encode(json.dumps(payload).encode()).decode(),
        },
        ...
    }
```

**File: `backend/api/routes/internal.py`**

```python
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry import trace

@router.post("/workers/audio")
async def trigger_audio_worker(request: Request, ...):
    # Extract trace context from headers
    propagator = TraceContextTextMapPropagator()
    context = propagator.extract(request.headers)
    
    # Create span as child of propagated context
    with tracer.start_as_current_span(
        "audio-worker",
        context=context,
        attributes={"job_id": payload.job_id}
    ):
        await process_audio_separation(payload.job_id)
```

#### 1.2 Add Job ID to All Spans

Create a helper that adds job_id as a span attribute:

```python
# backend/services/tracing.py

def job_span(name: str, job_id: str, **extra_attributes):
    """Create a span with job_id attribute for easy filtering."""
    return create_span(name, {
        "job_id": job_id,
        "service.operation": name,
        **extra_attributes
    })
```

Usage in workers:

```python
# backend/workers/audio_worker.py

async def process_audio_separation(job_id: str):
    with job_span("audio-worker", job_id) as span:
        span.set_attribute("worker", "audio")
        
        with job_span("download-audio", job_id):
            # download logic
            pass
        
        with job_span("modal-separation", job_id):
            # Modal API call
            pass
        
        with job_span("upload-stems", job_id):
            # GCS upload
            pass
```

### Phase 2: Instrument All Workers (3-4 hours) ⭐ High Priority

Add spans to every worker following this pattern:

#### Audio Worker (`audio_worker.py`)

```python
async def process_audio_separation(job_id: str):
    with job_span("audio-worker", job_id) as root:
        # Stage 1: Download/Get Audio
        with job_span("get-audio-file", job_id) as span:
            if job.audio_url:
                span.set_attribute("source", "url")
                with job_span("download-from-url", job_id):
                    audio_path = await download_from_url(...)
            else:
                span.set_attribute("source", "gcs")
                with job_span("download-from-gcs", job_id):
                    audio_path = storage.download_file(...)
        
        # Stage 2: Audio Separation
        with job_span("audio-separation", job_id) as span:
            with job_span("clean-instrumental", job_id):
                # First separation pass
                pass
            with job_span("backing-vocals", job_id):
                # Second separation pass
                pass
        
        # Stage 3: Upload Results
        with job_span("upload-stems", job_id) as span:
            span.set_attribute("stem_count", len(stems))
            for stem_name, stem_path in stems.items():
                with job_span("upload-stem", job_id, stem_name=stem_name):
                    storage.upload_file(...)
```

#### Lyrics Worker (`lyrics_worker.py`)

```python
async def process_lyrics_transcription(job_id: str):
    with job_span("lyrics-worker", job_id) as root:
        with job_span("get-vocals", job_id):
            # Download vocals from GCS
            pass
        
        with job_span("audioshake-transcription", job_id):
            # AudioShake API call
            pass
        
        with job_span("fetch-genius-lyrics", job_id) as span:
            span.set_attribute("artist", artist)
            span.set_attribute("title", title)
            # Genius API call
            pass
        
        with job_span("auto-correction", job_id):
            # LyricsTranscriber correction
            pass
        
        with job_span("upload-corrections", job_id):
            # Upload corrections.json
            pass
```

### Phase 3: Structured Logging with Job Context (1-2 hours)

Replace text logs with structured JSON that includes job context.

**File: `backend/main.py`**

```python
import json
import logging

class StructuredFormatter(logging.Formatter):
    """JSON formatter with trace correlation."""
    
    def format(self, record):
        from backend.services.tracing import get_current_trace_id, get_current_span_id
        
        log_entry = {
            "timestamp": self.formatTime(record),
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            # Trace correlation
            "logging.googleapis.com/trace": f"projects/nomadkaraoke/traces/{get_current_trace_id()}" if get_current_trace_id() else None,
            "logging.googleapis.com/spanId": get_current_span_id(),
            # Custom fields (if available in log record)
            "job_id": getattr(record, 'job_id', None),
            "worker": getattr(record, 'worker', None),
        }
        return json.dumps({k: v for k, v in log_entry.items() if v is not None})

# Configure in Cloud Run
if os.environ.get("K_SERVICE"):
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    logging.root.handlers = [handler]
```

Now logs in Cloud Logging can be filtered:
```
jsonPayload.job_id="8f03f0ac"
```

### Phase 4: Custom Metrics (2-3 hours) 🟡 Medium Priority

Add Cloud Monitoring metrics for key indicators.

**File: `backend/services/metrics.py`**

```python
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter

def setup_metrics():
    exporter = CloudMonitoringMetricsExporter(project_id="nomadkaraoke")
    provider = MeterProvider(metric_readers=[...])
    metrics.set_meter_provider(provider)
    
    meter = metrics.get_meter("karaoke-backend")
    
    # Counter: Jobs by status
    jobs_counter = meter.create_counter(
        "jobs_total",
        description="Total jobs by status",
        unit="1"
    )
    
    # Histogram: Processing duration by stage
    duration_histogram = meter.create_histogram(
        "job_stage_duration_seconds",
        description="Duration of job processing stages",
        unit="s"
    )
    
    return {
        "jobs": jobs_counter,
        "duration": duration_histogram,
    }

# Usage
metrics["jobs"].add(1, {"status": "completed", "worker": "audio"})
metrics["duration"].record(45.2, {"stage": "audio-separation", "job_id": job_id})
```

**Metrics to track:**

| Metric | Type | Labels |
|--------|------|--------|
| `jobs_total` | Counter | status, source (upload/url/search) |
| `job_stage_duration_seconds` | Histogram | stage, worker |
| `worker_invocations_total` | Counter | worker, success/failure |
| `gcs_operations_total` | Counter | operation (upload/download), bucket |
| `external_api_duration_seconds` | Histogram | api (modal/audioshake/genius) |

### Phase 5: Dashboard & Alerting (2-3 hours) 🟡 Medium Priority

#### Create Cloud Monitoring Dashboard

**File: `infrastructure/monitoring/dashboard.json`**

```json
{
  "displayName": "Karaoke Backend Overview",
  "dashboardFilters": [],
  "mosaicLayout": {
    "columns": 12,
    "tiles": [
      {
        "title": "Active Jobs by Status",
        "scorecard": {
          "timeSeriesQuery": {
            "prometheusQuery": "sum by (status) (jobs_total)"
          }
        }
      },
      {
        "title": "Job Processing Time (p95)",
        "xyChart": {
          "dataSets": [{
            "timeSeriesQuery": {
              "prometheusQuery": "histogram_quantile(0.95, rate(job_stage_duration_seconds_bucket[5m]))"
            }
          }]
        }
      },
      {
        "title": "Error Rate",
        "xyChart": {
          "dataSets": [{
            "timeSeriesQuery": {
              "prometheusQuery": "rate(worker_invocations_total{success=\"false\"}[5m]) / rate(worker_invocations_total[5m])"
            }
          }]
        }
      },
      {
        "title": "Cloud Tasks Queue Depth",
        "xyChart": {
          "dataSets": [{
            "timeSeriesQuery": {
              "prometheusQuery": "cloud_tasks_queue_depth"
            }
          }]
        }
      }
    ]
  }
}
```

#### Create Alerts

**File: `infrastructure/__main__.py`** (Pulumi)

```python
# Alert: Job failure rate > 10%
job_failure_alert = gcp.monitoring.AlertPolicy(
    "job-failure-rate-alert",
    display_name="High Job Failure Rate",
    conditions=[
        gcp.monitoring.AlertPolicyConditionArgs(
            display_name="Failure rate > 10%",
            condition_threshold=gcp.monitoring.AlertPolicyConditionConditionThresholdArgs(
                filter='metric.type="custom.googleapis.com/karaoke/job_failure_rate"',
                comparison="COMPARISON_GT",
                threshold_value=0.1,
                duration="300s",
            ),
        ),
    ],
    notification_channels=[...],  # Slack, email, etc.
)

# Alert: Job stuck in processing > 30 min
stuck_job_alert = gcp.monitoring.AlertPolicy(
    "stuck-job-alert",
    display_name="Job Stuck in Processing",
    conditions=[
        gcp.monitoring.AlertPolicyConditionArgs(
            display_name="Job > 30 min in processing state",
            condition_threshold=gcp.monitoring.AlertPolicyConditionConditionThresholdArgs(
                filter='metric.type="custom.googleapis.com/karaoke/job_age_seconds" AND metric.labels.status!="complete"',
                comparison="COMPARISON_GT",
                threshold_value=1800,
                duration="60s",
            ),
        ),
    ],
)
```

---

## Quick Wins (Do First)

These give the most debugging value with minimal effort:

### 1. Add Job ID to Worker Logs (30 min)

Simplest possible fix - add job_id to every log message:

```python
# backend/workers/audio_worker.py
logger.info(f"[job:{job_id}] Starting audio separation")
logger.info(f"[job:{job_id}] Downloaded audio file: {path}")
logger.info(f"[job:{job_id}] Modal separation complete")
```

Now you can grep:
```bash
gcloud logging read 'textPayload:"[job:8f03f0ac]"' --project=nomadkaraoke
```

### 2. Log Worker Start/End with Timing (30 min)

```python
import time

async def process_audio_separation(job_id: str):
    start = time.time()
    logger.info(f"[job:{job_id}] WORKER_START worker=audio")
    
    try:
        # ... processing ...
        
        duration = time.time() - start
        logger.info(f"[job:{job_id}] WORKER_END worker=audio status=success duration={duration:.1f}s")
    except Exception as e:
        duration = time.time() - start
        logger.error(f"[job:{job_id}] WORKER_END worker=audio status=error duration={duration:.1f}s error={e}")
        raise
```

Now you can easily find failed workers:
```bash
gcloud logging read 'textPayload:"WORKER_END" AND textPayload:"status=error"' --project=nomadkaraoke
```

### 3. Enable Cloud Trace Viewing (0 min - just fixed!)

With the IAM permission fix deployed today, Cloud Trace should start working. Visit:
https://console.cloud.google.com/traces/list?project=nomadkaraoke

---

## Summary: Implementation Priority

| Phase | Effort | Value | Priority |
|-------|--------|-------|----------|
| Quick Win #1: Job ID in logs | 30 min | High | ⭐ Do now |
| Quick Win #2: Worker timing | 30 min | High | ⭐ Do now |
| Phase 1: Trace propagation | 2-3 hrs | Very High | ⭐ Do soon |
| Phase 2: Instrument workers | 3-4 hrs | Very High | ⭐ Do soon |
| Phase 3: Structured logging | 1-2 hrs | Medium | 🟡 Nice to have |
| Phase 4: Custom metrics | 2-3 hrs | Medium | 🟡 Nice to have |
| Phase 5: Dashboard & alerts | 2-3 hrs | Medium | 🟡 Nice to have |

**Total for full observability: ~12-15 hours**

**Minimum viable observability (Quick Wins + Phase 1-2): ~5-6 hours**

---

## Appendix: GCP Observability Resources

- **Cloud Trace:** https://console.cloud.google.com/traces/list?project=nomadkaraoke
- **Cloud Logging:** https://console.cloud.google.com/logs?project=nomadkaraoke
- **Cloud Monitoring:** https://console.cloud.google.com/monitoring?project=nomadkaraoke
- **OpenTelemetry Python Docs:** https://opentelemetry.io/docs/instrumentation/python/
- **Cloud Trace Python:** https://cloud.google.com/trace/docs/setup/python-ot

### Useful Log Queries

```
# All logs for a specific job
resource.type="cloud_run_revision" AND textPayload:"JOB_ID"

# All worker starts
resource.type="cloud_run_revision" AND textPayload:"WORKER_START"

# All errors
resource.type="cloud_run_revision" AND severity>=ERROR

# Cloud Tasks failures
resource.type="cloud_tasks_queue"

# Trace-correlated logs (after structured logging)
jsonPayload.job_id="JOB_ID"
```

