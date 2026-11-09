# GCE Encoding Worker

HTTP API service that runs on the GCE encoding worker VM for video encoding jobs.

## Overview

This service provides HTTP endpoints for submitting and monitoring video encoding jobs. It runs as a systemd service on the `encoding-worker` GCE VM instance.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/encode` | POST | Submit a full encoding job |
| `/encode-preview` | POST | Submit a preview encoding job (480x270, fast) |
| `/status/{job_id}` | GET | Get job status and progress |
| `/health` | GET | Health check |

## Authentication

All endpoints (except `/health`) require an API key via the `X-API-Key` header. The key is stored in Secret Manager (`encoding-worker-api-key`).

## Encoding Process

### Full Encoding (`/encode`)
1. Downloads input files from GCS (title screen, karaoke video, end screen, instrumental audio)
2. Uses `LocalEncodingService` from the karaoke-gen wheel to produce:
   - Lossless 4K MP4
   - Lossy 4K MP4
   - Lossless MKV
   - 720p MP4
3. Uploads results to GCS
4. Reports progress via status endpoint

### Preview Encoding (`/encode-preview`)
1. Downloads ASS subtitle and audio files from GCS
2. Runs FFmpeg to create a quick 480x270 preview video
3. Uploads result to GCS
4. Used for real-time preview in the web UI

## Dependencies

- **FFmpeg**: Static build from John Van Sickle
- **Python 3.13**: Built from source (required for karaoke-gen)
- **karaoke-gen wheel**: Downloaded from GCS at job start (enables hot updates)

## Deployment

This service is deployed via the VM's startup script. The script:
1. Installs system dependencies (FFmpeg, fonts, Python build deps)
2. Builds Python 3.13 from source
3. Creates venv and installs dependencies
4. Writes `main.py` to `/opt/encoding-worker/`
5. Creates systemd service
6. Starts the service on port 8080

## Local Development

This code is extracted from the infrastructure for maintainability. To test locally:

```bash
cd backend/services/gce_encoding
pip install -r requirements.txt
pip install ../../../  # Install karaoke-gen wheel
ENCODING_API_KEY=test python main.py
```

## Architecture Notes

- **Hot code updates**: The karaoke-gen wheel is re-downloaded at the start of each job, allowing code updates without VM restart
- **In-memory job tracking**: Job state is stored in memory. Restart clears queue.
- **Parallel encoding**: ThreadPoolExecutor with 4 workers
- **GCS integration**: Direct download/upload via google-cloud-storage client
