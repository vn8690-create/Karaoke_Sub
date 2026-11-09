# Job Debugging Guide

This guide explains how to access debug info, observability, metrics, logs, and data about a given job ID in the karaoke-gen cloud backend.

**Last Updated:** 2025-12-28

---

## Prerequisites

### Service Account Authentication

For automated access, set the service account impersonation variable:

```bash
export GOOGLE_IMPERSONATE_SERVICE_ACCOUNT=claude-automation@nomadkaraoke.iam.gserviceaccount.com
```

This service account has permissions to:
- Read Firestore documents
- Read Cloud Storage files
- Query Cloud Logging
- Describe Cloud Run services
- List Cloud Tasks queues

### Required Tools

- `gcloud` CLI (authenticated)
- Python 3.10+ with `google-cloud-firestore` installed
- Access to the `nomadkaraoke` GCP project

---

## Quick Reference

| Data Type | Location | Access Method |
|-----------|----------|---------------|
| Job state & metadata | Firestore `jobs/{job_id}` | Python script |
| Processing logs | Cloud Logging | `gcloud logging read` |
| Audio/video files | GCS bucket | `gcloud storage` |
| Service health | Cloud Run | `gcloud run services describe` |
| Task queues | Cloud Tasks | `gcloud tasks queues list` |

---

## 1. Fetching Job Data from Firestore

Firestore stores all job state including status, timeline, worker logs, and file URLs.

### Using Python (Recommended)

A helper script is included at `scripts/get_job.py`. You can also create your own:

```python
#!/usr/bin/env python3
"""Fetch and display job data from Firestore."""
import sys
import json
from google.cloud import firestore

def get_job(job_id: str):
    db = firestore.Client(project='nomadkaraoke')
    doc = db.collection('jobs').document(job_id).get()

    if doc.exists:
        data = doc.to_dict()
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"Job {job_id} not found")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python get_job.py <job_id>")
        sys.exit(1)
    get_job(sys.argv[1])
```

Run it:

```bash
python get_job.py ffb0b8fa
```

### Example Output

```json
{
  "status": "in_review",
  "artist": "piri",
  "title": "dog",
  "created_at": "2025-12-28T01:55:23.914454",
  "audio_search_artist": "piri",
  "audio_search_title": "dog",
  "timeline": [
    {
      "timestamp": "2025-12-28T01:55:23.995388",
      "message": "Searching for: piri - dog",
      "progress": 5,
      "status": "searching_audio"
    },
    {
      "timestamp": "2025-12-28T01:55:24.249594",
      "message": "Found 20 audio sources. Waiting for selection.",
      "progress": 10,
      "status": "awaiting_audio_selection"
    }
    // ... more timeline entries
  ],
  "worker_logs": [
    {
      "level": "INFO",
      "message": "=== AUDIO WORKER STARTED ===",
      "timestamp": "2025-12-28T01:55:37.559644Z",
      "worker": "audio"
    }
    // ... more worker logs
  ]
}
```

### Key Fields to Check

| Field | Description |
|-------|-------------|
| `status` | Current job status (e.g., `in_review`, `complete`, `failed`) |
| `error_message` | Error description if job failed |
| `timeline` | Ordered list of status transitions with timestamps |
| `worker_logs` | Logs captured from worker processes |
| `file_urls` | Signed URLs for generated files |
| `state_data` | Worker-specific progress data |

---

## 2. Viewing Cloud Run Logs

Logs are stored in Cloud Logging and can be queried with `gcloud logging read`.

### Search Logs for a Job ID

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="karaoke-backend" AND "ffb0b8fa"' \
  --project=nomadkaraoke \
  --limit=50 \
  --format='table(timestamp,severity,jsonPayload.message,jsonPayload.logger)'
```

### Filter by Severity (Errors Only)

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="karaoke-backend" AND "ffb0b8fa" AND severity>=ERROR' \
  --project=nomadkaraoke \
  --limit=20 \
  --format=json
```

### Filter by Time Window

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="karaoke-backend" AND "ffb0b8fa" AND timestamp>="2025-12-28T01:55:00Z" AND timestamp<="2025-12-28T02:05:00Z"' \
  --project=nomadkaraoke \
  --limit=100 \
  --order=asc \
  --format='table(timestamp,severity,jsonPayload.message)'
```

### Search for Exceptions

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="karaoke-backend" AND (jsonPayload.message:"Exception" OR jsonPayload.message:"Traceback")' \
  --project=nomadkaraoke \
  --limit=10 \
  --format='table(timestamp,severity,jsonPayload.message)'
```

### View HTTP Request Logs

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="karaoke-backend" AND httpRequest.requestUrl:"ffb0b8fa"' \
  --project=nomadkaraoke \
  --limit=20 \
  --format='table(timestamp,httpRequest.status,httpRequest.requestMethod,httpRequest.requestUrl)'
```

---

## 3. Accessing Job Files in Cloud Storage

Files are stored in `gs://karaoke-gen-storage-nomadkaraoke/jobs/{job_id}/`.

### List All Files for a Job

```bash
gcloud storage ls -r gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/ --project=nomadkaraoke
```

Example output:

```
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/:

gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/lyrics/:
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/lyrics/corrections.json
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/lyrics/karaoke.lrc
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/lyrics/piri - dog (Lyrics Genius).txt
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/lyrics/uncorrected.txt

gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/previews/:
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/previews/86b528e04907.mp4

gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/screens/:
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/screens/end.jpg
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/screens/end.mov
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/screens/title.jpg
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/screens/title.mov

gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/stems/:
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/stems/backing_vocals.flac
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/stems/instrumental_clean.flac
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/stems/instrumental_with_backing.flac
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/stems/lead_vocals.flac
gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/stems/vocals_clean.flac
```

### View File Content (Small Files)

```bash
gcloud storage cat gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/lyrics/corrections.json --project=nomadkaraoke | head -50
```

### Get File Metadata

```bash
gcloud storage objects describe gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/stems/instrumental_clean.flac --project=nomadkaraoke
```

Example output:

```yaml
bucket: karaoke-gen-storage-nomadkaraoke
content_type: application/octet-stream
crc32c_hash: /uXURg==
creation_time: 2025-12-28T01:57:44+0000
size: 18115881
storage_class: STANDARD
```

### Download a File

```bash
gcloud storage cp gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/stems/instrumental_clean.flac ./instrumental.flac --project=nomadkaraoke
```

### GCS Folder Structure

```
jobs/{job_id}/
├── lyrics/
│   ├── corrections.json      # Lyrics with timing corrections
│   ├── karaoke.lrc           # LRC format lyrics
│   ├── uncorrected.txt       # Raw transcription
│   └── *.txt                 # Reference lyrics from sources
├── previews/
│   └── {hash}.mp4            # Preview video for lyrics review
├── screens/
│   ├── title.mov/.jpg/.png   # Title screen
│   └── end.mov/.jpg/.png     # End screen
├── stems/
│   ├── instrumental_clean.flac
│   ├── instrumental_with_backing.flac
│   ├── vocals_clean.flac
│   ├── lead_vocals.flac
│   └── backing_vocals.flac
├── videos/
│   └── with_vocals.mkv       # Karaoke video with lyrics overlay
└── finals/
    ├── lossless_4k.mp4
    ├── lossless_4k.mkv
    ├── lossy_4k.mp4
    └── lossy_720p.mp4
```

---

## 4. Cloud Run Service Status

### Check Service Health

```bash
gcloud run services describe karaoke-backend \
  --project=nomadkaraoke \
  --region=us-central1 \
  --format='yaml(status.conditions,status.latestReadyRevisionName,status.url)'
```

Example output:

```yaml
status:
  conditions:
  - lastTransitionTime: '2025-12-28T01:29:43.465349Z'
    status: 'True'
    type: Ready
  - lastTransitionTime: '2025-12-28T01:29:42.192338Z'
    status: 'True'
    type: ConfigurationsReady
  - lastTransitionTime: '2025-12-28T01:29:43.430737Z'
    status: 'True'
    type: RoutesReady
  latestReadyRevisionName: karaoke-backend-00203-c7q
  url: https://karaoke-backend-ipzqd2k4yq-uc.a.run.app
```

### List Recent Revisions

```bash
gcloud run revisions list \
  --service=karaoke-backend \
  --project=nomadkaraoke \
  --region=us-central1 \
  --limit=5 \
  --format='table(name,status.conditions.type,status.conditions.status,createTime)'
```

### View Revision Details

```bash
gcloud run revisions describe karaoke-backend-00203-c7q \
  --project=nomadkaraoke \
  --region=us-central1 \
  --format='yaml(spec.containerConcurrency,spec.containers[0].resources)'
```

---

## 5. Cloud Tasks Queues

The backend uses Cloud Tasks for async worker processing.

### List All Queues

```bash
gcloud tasks queues list --project=nomadkaraoke --location=us-central1
```

Example output:

```
QUEUE_NAME            STATE    MAX_NUM_OF_TASKS  MAX_RATE (/sec)  MAX_ATTEMPTS
audio-worker-queue    RUNNING  50                10.0             3
lyrics-worker-queue   RUNNING  50                10.0             3
render-worker-queue   RUNNING  20                5.0              2
screens-worker-queue  RUNNING  100               50.0             3
video-worker-queue    RUNNING  10                3.0              2
```

### View Queue Details

```bash
gcloud tasks queues describe audio-worker-queue \
  --project=nomadkaraoke \
  --location=us-central1
```

### List Tasks in a Queue

```bash
gcloud tasks list \
  --queue=audio-worker-queue \
  --project=nomadkaraoke \
  --location=us-central1 \
  --limit=10
```

---

## 6. Common Debugging Scenarios

### Scenario: Job Stuck in Status

1. **Check job state:**
   ```bash
   python get_job.py ffb0b8fa | jq '.status, .error_message, .timeline[-3:]'
   ```

2. **Check for errors in logs:**
   ```bash
   gcloud logging read 'resource.labels.service_name="karaoke-backend" AND "ffb0b8fa" AND severity>=ERROR' --project=nomadkaraoke --limit=5 --format=json
   ```

3. **Check if worker task is queued:**
   ```bash
   gcloud tasks list --queue=audio-worker-queue --project=nomadkaraoke --location=us-central1
   ```

### Scenario: Job Failed

1. **Get error message from Firestore:**
   ```bash
   python get_job.py ffb0b8fa | jq '.error_message, .error_details'
   ```

2. **Search for exception stack trace:**
   ```bash
   gcloud logging read 'resource.labels.service_name="karaoke-backend" AND "ffb0b8fa" AND jsonPayload.message:"Traceback"' --project=nomadkaraoke --limit=3 --format='value(jsonPayload.message)'
   ```

### Scenario: Missing Output Files

1. **List all generated files:**
   ```bash
   gcloud storage ls -r gs://karaoke-gen-storage-nomadkaraoke/jobs/ffb0b8fa/ --project=nomadkaraoke
   ```

2. **Check worker logs for upload failures:**
   ```bash
   gcloud logging read 'resource.labels.service_name="karaoke-backend" AND "ffb0b8fa" AND (jsonPayload.message:"upload" OR jsonPayload.message:"GCS")' --project=nomadkaraoke --limit=20 --format='table(timestamp,jsonPayload.message)'
   ```

### Scenario: Audio Separation Slow/Failing

1. **Check audio worker logs:**
   ```bash
   gcloud logging read 'resource.labels.service_name="karaoke-backend" AND "ffb0b8fa" AND jsonPayload.worker:"audio"' --project=nomadkaraoke --limit=30 --format='table(timestamp,jsonPayload.message)'
   ```

2. **Check Modal API status in worker logs:**
   ```bash
   python get_job.py ffb0b8fa | jq '.worker_logs | map(select(.worker == "audio"))'
   ```

---

## 7. Useful Aliases

Add these to your shell profile for quick access:

```bash
# Job debugging aliases (update paths as needed)
alias kj='python scripts/get_job.py'
alias klogs='gcloud logging read "resource.labels.service_name=\"karaoke-backend\"" --project=nomadkaraoke --limit=50 --format="table(timestamp,severity,jsonPayload.message)"'
alias kfiles='gcloud storage ls -r gs://karaoke-gen-storage-nomadkaraoke/jobs/'
alias kservice='gcloud run services describe karaoke-backend --project=nomadkaraoke --region=us-central1'
alias kqueues='gcloud tasks queues list --project=nomadkaraoke --location=us-central1'

# Usage:
# kj ffb0b8fa                    # Get job data
# klogs | grep ffb0b8fa          # Search logs
# kfiles ffb0b8fa/               # List job files
```

---

## 8. API Access (Alternative)

The backend API also provides job information if you have an access token.

### Get Job via API

```bash
export TOKEN="your-access-token"
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.nomadkaraoke.com/api/jobs/ffb0b8fa" | jq
```

### List Jobs

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.nomadkaraoke.com/api/jobs?limit=10" | jq
```

---

## Related Documentation

- [Architecture Overview](./ARCHITECTURE.md) - System architecture and data flow
- [Frontend Guide](./FRONTEND-GUIDE.md) - Web UI documentation
- [Backend Feature Parity](../00-current-plan/BACKEND-FEATURE-PARITY-PLAN.md) - Feature status
- [Scalable Architecture Plan](../00-current-plan/SCALABLE-ARCHITECTURE-PLAN.md) - Cloud Tasks and scaling
