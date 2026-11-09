"""
GCE Encoding Worker Service.

This package contains the FastAPI application that runs on the GCE encoding worker VM.
It provides HTTP endpoints for video encoding jobs.

The service:
- Downloads input files from GCS
- Runs FFmpeg encoding via LocalEncodingService
- Uploads results back to GCS
- Provides job status tracking

Endpoints:
- POST /encode - Submit a full encoding job
- POST /encode-preview - Submit a preview encoding job (fast, low-res)
- GET /status/{job_id} - Get job status
- GET /health - Health check
"""

from .main import app

__all__ = ["app"]
