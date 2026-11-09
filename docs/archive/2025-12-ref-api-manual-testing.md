# Backend API Manual Testing Guide

Complete guide for manually testing the karaoke generation backend API using curl and command-line tools.

## Prerequisites

1. **Authentication Token**
   
   All API requests require authentication with a Google Cloud identity token:

   ```bash
   export AUTH_TOKEN=$(gcloud auth print-identity-token)
   export SERVICE_URL="https://karaoke-backend-718638054799.us-central1.run.app"
   ```

2. **Tools Required**
   - `curl` - Make HTTP requests
   - `jq` - Parse JSON responses (optional but recommended)
   - `gcloud` - Get authentication tokens

## Quick Start

### 1. Test Service Health

```bash
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  $SERVICE_URL/api/health | jq
```

**Expected Response:**
```json
{
  "status": "healthy",
  "service": "karaoke-gen-backend"
}
```

### 2. Submit a Karaoke Job (YouTube URL)

```bash
curl -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}' \
  $SERVICE_URL/api/jobs | jq
```

**Expected Response:**
```json
{
  "status": "success",
  "job_id": "abc123-def456-ghi789",
  "message": "Job created successfully"
}
```

**Save the job_id for later:**
```bash
export JOB_ID="abc123-def456-ghi789"  # Use the actual job_id from response
```

### 3. Check Job Status

```bash
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  $SERVICE_URL/api/jobs/$JOB_ID | jq
```

**Expected Response:**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "processing",
  "progress": 45,
  "created_at": "2025-12-01T10:30:00.000Z",
  "updated_at": "2025-12-01T10:32:15.000Z",
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "timeline": [
    {
      "status": "queued",
      "timestamp": "2025-12-01T10:30:00.000Z",
      "progress": 0
    },
    {
      "status": "processing",
      "timestamp": "2025-12-01T10:30:05.000Z",
      "progress": 10,
      "message": "Downloading audio..."
    }
  ],
  "output_files": {},
  "download_urls": {}
}
```

## Complete API Reference

### Endpoints

#### 1. Root Endpoint

Get service information.

```bash
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  $SERVICE_URL | jq
```

---

#### 2. Health Check

Check service health.

```bash
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  $SERVICE_URL/api/health | jq
```

---

#### 3. Submit Job from URL

Create a karaoke generation job from a YouTube URL or direct audio URL.

**Request:**
```bash
curl -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}' \
  $SERVICE_URL/api/jobs | jq
```

**Parameters:**
- `url` (required): YouTube URL or direct audio file URL

**Response:**
```json
{
  "status": "success",
  "job_id": "unique-job-id",
  "message": "Job created successfully"
}
```

---

#### 4. Upload Audio File

Create a karaoke generation job from an uploaded audio file.

**Request:**
```bash
curl -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -F "file=@/path/to/audio.mp3" \
  -F "artist=Artist Name" \
  -F "title=Song Title" \
  $SERVICE_URL/api/upload | jq
```

**Parameters:**
- `file` (required): Audio file (.mp3, .wav, .flac, .m4a, .ogg)
- `artist` (required): Artist name
- `title` (required): Song title

**Supported File Types:**
- MP3 (.mp3)
- WAV (.wav)
- FLAC (.flac)
- M4A (.m4a)
- OGG (.ogg)

**Response:**
```json
{
  "status": "success",
  "job_id": "unique-job-id",
  "message": "File uploaded and job created successfully"
}
```

---

#### 5. Get Job Status

Retrieve status and details of a specific job.

**Request:**
```bash
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  $SERVICE_URL/api/jobs/$JOB_ID | jq
```

**Response:**
```json
{
  "job_id": "unique-job-id",
  "status": "complete",
  "progress": 100,
  "created_at": "2025-12-01T10:30:00.000Z",
  "updated_at": "2025-12-01T10:45:00.000Z",
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "artist": "Artist Name",
  "title": "Song Title",
  "timeline": [...],
  "output_files": {
    "video": "outputs/abc123/karaoke_video.mp4",
    "audio_instrumental": "outputs/abc123/instrumental.mp3"
  },
  "download_urls": {
    "video": "https://storage.googleapis.com/...",
    "audio_instrumental": "https://storage.googleapis.com/..."
  }
}
```

**Job Statuses:**
- `queued` - Job is queued and waiting to start
- `processing` - Job is currently being processed
- `awaiting_review` - Lyrics transcription needs review
- `ready_for_finalization` - Ready for final video generation
- `finalizing` - Creating final video
- `complete` - Job finished successfully
- `error` - Job failed with an error

---

#### 6. List All Jobs

List all jobs with optional filtering.

**Request:**
```bash
# List all jobs
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  $SERVICE_URL/api/jobs | jq

# Filter by status
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  "$SERVICE_URL/api/jobs?status=complete" | jq

# Limit results
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  "$SERVICE_URL/api/jobs?limit=10" | jq
```

**Query Parameters:**
- `status` (optional): Filter by job status
- `limit` (optional): Maximum number of results (default: 100)

**Response:**
```json
[
  {
    "job_id": "job-1",
    "status": "complete",
    "created_at": "2025-12-01T10:30:00.000Z",
    ...
  },
  {
    "job_id": "job-2",
    "status": "processing",
    "created_at": "2025-12-01T11:00:00.000Z",
    ...
  }
]
```

---

#### 7. Delete Job

Delete a job and optionally its output files.

**Request:**
```bash
# Delete job and files
curl -X DELETE \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  $SERVICE_URL/api/jobs/$JOB_ID | jq

# Delete job but keep files
curl -X DELETE \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  "$SERVICE_URL/api/jobs/$JOB_ID?delete_files=false" | jq
```

**Query Parameters:**
- `delete_files` (optional): Whether to delete output files (default: true)

**Response:**
```json
{
  "status": "success",
  "message": "Job abc123 deleted"
}
```

---

## Common Workflows

### Workflow 1: Process a YouTube Video

```bash
# 1. Submit job
RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}' \
  $SERVICE_URL/api/jobs)

# 2. Extract job ID
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# 3. Poll for completion
while true; do
  STATUS=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
    $SERVICE_URL/api/jobs/$JOB_ID | jq -r '.status')
  PROGRESS=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
    $SERVICE_URL/api/jobs/$JOB_ID | jq -r '.progress')
  
  echo "Status: $STATUS, Progress: $PROGRESS%"
  
  if [ "$STATUS" == "complete" ] || [ "$STATUS" == "error" ]; then
    break
  fi
  
  sleep 10
done

# 4. Get download URLs
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  $SERVICE_URL/api/jobs/$JOB_ID | jq '.download_urls'
```

### Workflow 2: Upload and Process Local File

```bash
# 1. Upload file
RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -F "file=@/path/to/song.mp3" \
  -F "artist=Rick Astley" \
  -F "title=Never Gonna Give You Up" \
  $SERVICE_URL/api/upload)

# 2. Extract job ID
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# 3. Monitor progress (same as Workflow 1)
```

### Workflow 3: Monitor Multiple Jobs

```bash
# Get all active jobs
curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
  "$SERVICE_URL/api/jobs?status=processing" | \
  jq -r '.[] | "\(.job_id) - \(.progress)% - \(.timeline[-1].message // "Processing")"'
```

---

## Helper Scripts

### Save Job ID for Easy Access

```bash
# After submitting a job, save the ID
echo "export JOB_ID=abc123-def456" >> ~/.karaoke_jobs
source ~/.karaoke_jobs
```

### Monitor Job Progress

Save this as `monitor-job.sh`:

```bash
#!/bin/bash
JOB_ID=$1
AUTH_TOKEN=$(gcloud auth print-identity-token)
SERVICE_URL="https://karaoke-backend-718638054799.us-central1.run.app"

while true; do
  clear
  RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
    $SERVICE_URL/api/jobs/$JOB_ID)
  
  echo "Job: $JOB_ID"
  echo "===================="
  echo $RESPONSE | jq '{
    status: .status,
    progress: .progress,
    current_step: .timeline[-1].message,
    created: .created_at,
    updated: .updated_at
  }'
  
  STATUS=$(echo $RESPONSE | jq -r '.status')
  if [ "$STATUS" == "complete" ] || [ "$STATUS" == "error" ]; then
    echo ""
    echo "Job finished!"
    echo $RESPONSE | jq '.download_urls'
    break
  fi
  
  sleep 5
done
```

Usage:
```bash
chmod +x monitor-job.sh
./monitor-job.sh YOUR_JOB_ID
```

### Download Job Outputs

Save this as `download-job.sh`:

```bash
#!/bin/bash
JOB_ID=$1
OUTPUT_DIR=${2:-.}
AUTH_TOKEN=$(gcloud auth print-identity-token)
SERVICE_URL="https://karaoke-backend-718638054799.us-central1.run.app"

# Get job details
RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
  $SERVICE_URL/api/jobs/$JOB_ID)

# Extract download URLs
echo $RESPONSE | jq -r '.download_urls | to_entries[] | "\(.key)|\(.value)"' | \
while IFS='|' read -r name url; do
  echo "Downloading $name..."
  curl -o "$OUTPUT_DIR/${JOB_ID}_${name}" "$url"
done

echo "Downloads complete in $OUTPUT_DIR"
```

Usage:
```bash
chmod +x download-job.sh
./download-job.sh YOUR_JOB_ID ./downloads
```

---

## Troubleshooting

### Authentication Errors

If you get 403 Forbidden:
```bash
# Refresh your token
export AUTH_TOKEN=$(gcloud auth print-identity-token)
```

### Check Service Logs

```bash
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=karaoke-backend" \
  --limit 50 --format json | jq '.[] | {
    timestamp: .timestamp,
    severity: .severity,
    message: .textPayload
  }'
```

### Test Service Connectivity

```bash
# Test basic connectivity
curl -I $SERVICE_URL

# Test with authentication
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  $SERVICE_URL/api/health
```

---

## API Response Codes

- `200 OK` - Request successful
- `400 Bad Request` - Invalid input (check request format)
- `403 Forbidden` - Authentication required or invalid token
- `404 Not Found` - Job not found
- `422 Unprocessable Entity` - Validation error (invalid data)
- `500 Internal Server Error` - Server error (check logs)

---

## Tips

1. **Always check authentication first**: Run health check to verify your token works
2. **Save job IDs**: You'll need them to check status and download results
3. **Poll wisely**: Check status every 10-30 seconds, not every second
4. **Use jq**: It makes JSON responses much easier to read
5. **Monitor logs**: If something fails, check Cloud Run logs for details
6. **Timeout handling**: Jobs can take 5-10 minutes for long songs

---

## Next Steps

Once you've verified the backend works via CLI:
1. Run the automated test suite
2. Build the React frontend
3. Deploy to Cloudflare Pages
4. End-to-end testing

For automated testing, see `backend/tests/test_api_integration.py`.

-----------------


Response from Andrew:

so, I ran these commands to test the backend, and while technically all of the responses look right, it's obviously not actually doing anything as both jobs supposedly "complete" in less than a second.

(base) ➜  karaoke-gen git:(replace-modal-with-google-cloud) ✗ export AUTH_TOKEN=$(gcloud auth print-identity-token)
(base) ➜  karaoke-gen git:(replace-modal-with-google-cloud) ✗ export SERVICE_URL="https://karaoke-backend-718638054799.us-central1.run.app"
(base) ➜  karaoke-gen git:(replace-modal-with-google-cloud) ✗ curl -H "Authorization: Bearer $AUTH_TOKEN" $SERVICE_URL/api/health | jq
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100    52  100    52    0     0    152      0 --:--:-- --:--:-- --:--:--   152
{
  "status": "healthy",
  "service": "karaoke-gen-backend"
}
(base) ➜  karaoke-gen git:(replace-modal-with-google-cloud) ✗ curl -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}' \
  $SERVICE_URL/api/jobs | jq
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   131  100    77  100    54     85     59 --:--:-- --:--:-- --:--:--   145
{
  "status": "success",
  "job_id": "d6108e79",
  "message": "Job created successfully"
}
(base) ➜  karaoke-gen git:(replace-modal-with-google-cloud) ✗ export JOB_ID="d6108e79"
(base) ➜  karaoke-gen git:(replace-modal-with-google-cloud) ✗ curl -H "Authorization: Bearer $AUTH_TOKEN" $SERVICE_URL/api/jobs/$JOB_ID | jq
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   586  100   586    0     0   1126      0 --:--:-- --:--:-- --:--:--  1126
{
  "job_id": "d6108e79",
  "status": "complete",
  "progress": 100,
  "created_at": "2025-12-01T02:19:25.595465",
  "updated_at": "2025-12-01T02:19:25.862304Z",
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "artist": null,
  "title": null,
  "filename": null,
  "track_output_dir": null,
  "audio_hash": null,
  "timeline": [
    {
      "status": "processing",
      "timestamp": "2025-12-01T02:19:25.738020",
      "progress": 10,
      "message": "Starting karaoke generation"
    },
    {
      "status": "complete",
      "timestamp": "2025-12-01T02:19:25.862264",
      "progress": 100,
      "message": "Karaoke generation complete"
    }
  ],
  "output_files": {},
  "download_urls": {},
  "error_message": null
}
(base) ➜  karaoke-gen git:(replace-modal-with-google-cloud) ✗
(base) ➜  karaoke-gen git:(replace-modal-with-google-cloud) ✗ ll input/waterloo.wav
-rw-r--r--@ 1 andrew  staff    28M Jun 29 17:07 input/waterloo.wav
(base) ➜  karaoke-gen git:(replace-modal-with-google-cloud) ✗ curl -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -F "file=@/Users/andrew/Projects/karaoke-gen/input/waterloo.flac" \
  -F "artist=ABBA" \
  -F "title=Waterloo" \
  $SERVICE_URL/api/upload | jq
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100 20.3M  100    95  100 20.3M      9  2173k  0:00:10  0:00:09  0:00:01 1524k
{
  "status": "success",
  "job_id": "d07a7f46",
  "message": "File uploaded and job created successfully"
}
(base) ➜  karaoke-gen git:(replace-modal-with-google-cloud) ✗ export JOB_ID="d07a7f46"
(base) ➜  karaoke-gen git:(replace-modal-with-google-cloud) ✗ curl -H "Authorization: Bearer $AUTH_TOKEN" $SERVICE_URL/api/jobs/$JOB_ID | jq
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   564  100   564    0     0   1034      0 --:--:-- --:--:-- --:--:--  1034
{
  "job_id": "d07a7f46",
  "status": "complete",
  "progress": 100,
  "created_at": "2025-12-01T02:24:05.491187",
  "updated_at": "2025-12-01T02:24:07.255171Z",
  "url": null,
  "artist": "ABBA",
  "title": "Waterloo",
  "filename": "waterloo.flac",
  "track_output_dir": null,
  "audio_hash": null,
  "timeline": [
    {
      "status": "processing",
      "timestamp": "2025-12-01T02:24:06.449626",
      "progress": 10,
      "message": "Starting karaoke generation"
    },
    {
      "status": "complete",
      "timestamp": "2025-12-01T02:24:07.255132",
      "progress": 100,
      "message": "Karaoke generation complete"
    }
  ],
  "output_files": {},
  "download_urls": {},
  "error_message": null
}

what's going on here, I assume there's some kinda no-op / hard coded success?

