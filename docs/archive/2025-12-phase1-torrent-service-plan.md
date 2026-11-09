# Flacfetch HTTP API Service Implementation Plan

**Created:** 2025-12-20  
**Updated:** 2025-12-22  
**Status:** Complete ✅  
**Priority:** Medium  
**Estimated Effort:** 3-4 days (actual: ~3 days)

## Problem Statement

BitTorrent downloads don't work reliably in Cloud Run due to:
- No inbound peer connections (NAT/firewall)
- Ephemeral containers with no stable IP
- DHT peer discovery blocked
- Container timeout limits (max 60 min)

This prevents downloading lossless audio from private trackers (RED, OPS) via the remote backend.

## Solution Overview

Add an HTTP API mode to **flacfetch** (our audio fetching library) and deploy it on a dedicated GCP VM with:
- Full BitTorrent peer connectivity via Transmission daemon
- Static IP for tracker whitelist (seedbox-like)
- Indefinite seeding of downloaded torrents
- Automatic disk cleanup when space runs low
- YouTube downloads also handled (single service for all audio acquisition)

This approach provides clean separation of concerns:
- **flacfetch**: Handles ALL audio acquisition (torrents + YouTube)
- **karaoke-gen backend**: Orchestrates karaoke generation pipeline, calls flacfetch API

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FLACFETCH SERVICE ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Cloud Run Backend                    Flacfetch VM (e2-small)              │
│   ┌────────────────────┐               ┌─────────────────────────┐          │
│   │                    │               │                         │          │
│   │ karaoke-gen        │  1. Search    │  flacfetch HTTP API     │          │
│   │ AudioSearchService │ ────────────▶ │  POST /search           │          │
│   │                    │               │                         │          │
│   │                    │  2. Results   │  Providers:             │          │
│   │                    │ ◀──────────── │  • RED (FLAC)           │          │
│   │                    │               │  • OPS (FLAC)           │          │
│   │                    │  3. Download  │  • YouTube (fallback)   │          │
│   │                    │ ────────────▶ │                         │          │
│   │                    │               │  POST /download         │          │
│   │                    │  4. Status    │  GET /download/{id}     │          │
│   │                    │ ◀──────────── │                         │          │
│   │                    │  (polling)    │  Transmission Daemon    │          │
│   │                    │               │  • Full peer connect    │          │
│   │                    │  5. Complete  │  • DHT enabled          │          │
│   │                    │ ◀──────────── │  • Indefinite seeding   │          │
│   │                    │  (file path)  │                         │          │
│   └────────────────────┘               └───────────┬─────────────┘          │
│            │                                       │                         │
│            │                                       │ 6. Upload to GCS        │
│            │                                       │                         │
│            ▼                                       ▼                         │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │                    Google Cloud Storage                          │       │
│   │                                                                  │       │
│   │   uploads/{job_id}/audio/{filename}.flac                        │       │
│   │                                                                  │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. HTTP API in flacfetch (not separate service)
- **Why**: Clean separation of concerns, reusable by future projects, single source of truth
- **How**: Add `flacfetch/api/` module with FastAPI, new CLI mode `flacfetch serve`

### 2. Indefinite Seeding
- **Why**: VM is always-on anyway, helps maintain tracker ratio, acts like a seedbox
- **Current behavior**: Torrent removed after download (line 317-321 in torrent.py)
- **New behavior**: Torrent kept seeding, only removed by cleanup or explicit delete

### 3. Static IP
- **Why**: Required for tracker account IP whitelist, consistent for firewall rules
- **Cost**: ~$3/month additional

### 4. Disk Space Management
- **Strategy**: Auto-cleanup oldest torrents when free space < 5GB threshold
- **API**: Manual cleanup endpoints + automatic background cleanup

### 5. Instance Type: e2-small
- **Specs**: 0.5 vCPU, 2GB RAM, ~$12/month
- **Why**: Sufficient for I/O-bound workload, newer C3/N4 require 2+ vCPUs (overkill)
- **Disk**: 30GB SSD (20GB for torrents + headroom)

### 6. Authentication
- **Method**: Static API key in `X-API-Key` header
- **Firewall**: Permissive (allows future web UI), auth enforced at app level

## Implementation Phases

### Phase 1: Add HTTP API to flacfetch

**Location:** `./flacfetch/flacfetch/api/`

**New Directory Structure:**
```
flacfetch/
├── flacfetch/
│   ├── api/                      # NEW
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── auth.py              # API key authentication
│   │   ├── models.py            # Pydantic request/response models
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── search.py        # POST /search
│   │   │   ├── download.py      # POST /download, GET /download/{id}/status
│   │   │   ├── torrents.py      # GET /torrents, DELETE /torrents/{id}
│   │   │   └── health.py        # GET /health, GET /disk-usage
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── download_manager.py   # Track active downloads
│   │       └── disk_manager.py       # Disk cleanup logic
│   ├── core/
│   ├── downloaders/
│   │   └── torrent.py           # MODIFIED: optional keep-seeding mode
│   ├── interface/
│   │   └── cli.py               # MODIFIED: add 'serve' subcommand
│   └── providers/
└── pyproject.toml               # MODIFIED: add fastapi, uvicorn deps
```

**API Endpoints:**

```yaml
# All endpoints require X-API-Key header

# Search for audio
POST /search
  Request:
    { "artist": "ABBA", "title": "Waterloo" }
  Response:
    {
      "search_id": "abc123",
      "results": [
        {
          "index": 0,
          "title": "Waterloo",
          "artist": "ABBA",
          "provider": "RED",
          "quality": "FLAC 16bit CD",
          "seeders": 45,
          "size_bytes": 31457280,
          "target_file": "02. Waterloo.flac",
          ...
        },
        ...
      ]
    }

# Start download
POST /download
  Request:
    {
      "search_id": "abc123",       # From previous search
      "result_index": 0,           # Which result to download
      "output_filename": "ABBA - Waterloo",  # Optional
      "upload_to_gcs": true,       # Upload to GCS when complete
      "gcs_path": "uploads/job123/audio/"    # Required if upload_to_gcs
    }
  Response:
    {
      "download_id": "dl_xyz789",
      "status": "queued"
    }

# Check download status
GET /download/{download_id}/status
  Response:
    {
      "download_id": "dl_xyz789",
      "status": "downloading",  # queued, downloading, uploading, seeding, complete, failed
      "progress": 45.2,
      "peers": 3,
      "download_speed_kbps": 1250.5,
      "eta_seconds": 120,
      "provider": "RED",
      "title": "ABBA - Waterloo",
      "output_path": null,        # Set when complete (local path)
      "gcs_path": null,           # Set when uploaded to GCS
      "error": null
    }

# List all torrents (for management)
GET /torrents
  Response:
    {
      "torrents": [
        {
          "id": 1,
          "name": "ABBA - Waterloo [FLAC]",
          "status": "seeding",
          "progress": 100.0,
          "size_bytes": 314572800,
          "uploaded_bytes": 628145600,  # Seeding stats
          "ratio": 2.0,
          "added_at": "2025-12-20T10:30:00Z"
        },
        ...
      ],
      "total_size_bytes": 5368709120,
      "count": 15
    }

# Delete a torrent (manual cleanup)
DELETE /torrents/{torrent_id}
  Query params: ?delete_data=true  # Also delete downloaded files
  Response:
    { "status": "deleted" }

# Trigger cleanup (free disk space)
POST /torrents/cleanup
  Request:
    {
      "strategy": "oldest",      # oldest, largest, lowest_ratio
      "target_free_gb": 10       # Keep removing until this much free
    }
  Response:
    {
      "removed_count": 3,
      "freed_bytes": 1073741824,
      "free_space_gb": 10.5
    }

# Health check
GET /health
  Response:
    {
      "status": "healthy",
      "transmission": {
        "available": true,
        "version": "4.0.5",
        "active_torrents": 5
      },
      "disk": {
        "total_gb": 30,
        "used_gb": 18,
        "free_gb": 12
      },
      "providers": {
        "red": true,
        "ops": true,
        "youtube": true
      }
    }
```

**Torrent Downloader Changes:**

```python
# flacfetch/downloaders/torrent.py

class TorrentDownloader(Downloader):
    def __init__(self, ..., keep_seeding: bool = False):
        """
        Args:
            keep_seeding: If True, don't remove torrent after download.
                          Used in server mode for indefinite seeding.
        """
        self.keep_seeding = keep_seeding
    
    def download(self, release, output_path, output_filename=None):
        # ... existing download logic ...
        
        # After download complete:
        if self.keep_seeding:
            # Don't remove, just return the file path
            logger.info(f"Download complete, keeping torrent for seeding: {torrent.name}")
        else:
            # Original behavior: stop and remove
            self.client.stop_torrent(torrent.id)
            self.client.remove_torrent(torrent.id, delete_data=True)
```

**CLI Changes:**

```bash
# New serve subcommand
flacfetch serve --port 8080 --host 0.0.0.0

# Or via environment
FLACFETCH_API_PORT=8080 flacfetch serve
```

### Phase 2: Infrastructure (Pulumi)

**Location:** `./infrastructure/__main__.py`

**New Resources:**
```python
# Static IP for flacfetch service (for tracker whitelist)
flacfetch_ip = gcp.compute.Address(
    "flacfetch-ip",
    name="flacfetch-static-ip",
    region="us-central1",
)

# Service account for flacfetch VM
flacfetch_sa = gcp.serviceaccount.Account(
    "flacfetch-sa",
    account_id="flacfetch-service",
    display_name="Flacfetch Service Account",
)

# GCS write permissions for flacfetch
gcp.storage.BucketIAMMember(
    "flacfetch-gcs-writer",
    bucket=bucket.name,
    role="roles/storage.objectCreator",
    member=pulumi.Output.concat("serviceAccount:", flacfetch_sa.email),
)

# Flacfetch VM
flacfetch_vm = gcp.compute.Instance(
    "flacfetch-service",
    machine_type="e2-small",
    zone="us-central1-a",
    boot_disk=gcp.compute.InstanceBootDiskArgs(
        initialize_params=gcp.compute.InstanceBootDiskInitializeParamsArgs(
            image="debian-cloud/debian-12",
            size=30,  # GB
            type="pd-ssd",
        ),
    ),
    network_interfaces=[gcp.compute.InstanceNetworkInterfaceArgs(
        network="default",
        access_configs=[gcp.compute.InstanceNetworkInterfaceAccessConfigArgs(
            nat_ip=flacfetch_ip.address,  # Static IP
        )],
    )],
    service_account=gcp.compute.InstanceServiceAccountArgs(
        email=flacfetch_sa.email,
        scopes=["cloud-platform"],
    ),
    metadata_startup_script=FLACFETCH_STARTUP_SCRIPT,
    tags=["flacfetch-service"],
)

# Firewall for flacfetch
flacfetch_firewall = gcp.compute.Firewall(
    "flacfetch-firewall",
    network="default",
    allows=[
        # BitTorrent peer connections
        gcp.compute.FirewallAllowArgs(protocol="tcp", ports=["51413"]),
        gcp.compute.FirewallAllowArgs(protocol="udp", ports=["51413"]),
        # Flacfetch HTTP API (auth required at app level)
        gcp.compute.FirewallAllowArgs(protocol="tcp", ports=["8080"]),
    ],
    source_ranges=["0.0.0.0/0"],  # Permissive, auth at app level
    target_tags=["flacfetch-service"],
)

# Store API key in Secret Manager
flacfetch_api_key = gcp.secretmanager.Secret(
    "flacfetch-api-key",
    secret_id="flacfetch-api-key",
    replication=gcp.secretmanager.SecretReplicationArgs(
        auto=gcp.secretmanager.SecretReplicationAutoArgs(),
    ),
)

# Export for use
pulumi.export("flacfetch_static_ip", flacfetch_ip.address)
pulumi.export("flacfetch_service_url", pulumi.Output.concat("http://", flacfetch_ip.address, ":8080"))
```

**Startup Script:**
```bash
#!/bin/bash
set -e

# Install dependencies
apt-get update
apt-get install -y python3-pip python3-venv transmission-daemon ffmpeg git

# Configure Transmission
systemctl stop transmission-daemon
cat > /etc/transmission-daemon/settings.json << 'EOF'
{
    "download-dir": "/var/lib/transmission-daemon/downloads",
    "incomplete-dir": "/var/lib/transmission-daemon/.incomplete",
    "incomplete-dir-enabled": true,
    "rpc-authentication-required": false,
    "rpc-bind-address": "127.0.0.1",
    "rpc-enabled": true,
    "rpc-port": 9091,
    "rpc-whitelist-enabled": false,
    "peer-port": 51413,
    "port-forwarding-enabled": false,
    "speed-limit-down": 0,
    "speed-limit-down-enabled": false,
    "speed-limit-up": 0,
    "speed-limit-up-enabled": false,
    "ratio-limit-enabled": false,
    "umask": 2
}
EOF
systemctl start transmission-daemon

# Install flacfetch
cd /opt
git clone https://github.com/nomadkaraoke/flacfetch.git
cd flacfetch
python3 -m venv venv
source venv/bin/activate
pip install -e ".[api]"

# Get secrets from metadata/Secret Manager
FLACFETCH_API_KEY=$(gcloud secrets versions access latest --secret=flacfetch-api-key)
RED_API_KEY=$(gcloud secrets versions access latest --secret=red-api-key)
RED_API_URL=$(gcloud secrets versions access latest --secret=red-api-url)
OPS_API_KEY=$(gcloud secrets versions access latest --secret=ops-api-key)
GCS_BUCKET=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/gcs-bucket" -H "Metadata-Flavor: Google")

# Create systemd service
cat > /etc/systemd/system/flacfetch.service << EOF
[Unit]
Description=Flacfetch HTTP API Service
After=network.target transmission-daemon.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/flacfetch
Environment="FLACFETCH_API_KEY=${FLACFETCH_API_KEY}"
Environment="RED_API_KEY=${RED_API_KEY}"
Environment="RED_API_URL=${RED_API_URL}"
Environment="OPS_API_KEY=${OPS_API_KEY}"
Environment="GCS_BUCKET=${GCS_BUCKET}"
Environment="FLACFETCH_KEEP_SEEDING=true"
Environment="FLACFETCH_MIN_FREE_GB=5"
ExecStart=/opt/flacfetch/venv/bin/flacfetch serve --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable flacfetch
systemctl start flacfetch
```

### Phase 3: Backend Integration

**New File:** `backend/services/flacfetch_client.py`

```python
"""
Client for the remote flacfetch HTTP API service.

Used when FLACFETCH_API_URL is configured, otherwise falls back to local flacfetch.
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)


class FlacfetchServiceError(Exception):
    """Error communicating with flacfetch service."""
    pass


class FlacfetchClient:
    """Client for remote flacfetch HTTP API."""
    
    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
    
    def _headers(self) -> Dict[str, str]:
        return {"X-API-Key": self.api_key}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if service is healthy."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/health",
                headers=self._headers(),
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
    
    async def search(self, artist: str, title: str) -> Dict[str, Any]:
        """Search for audio."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/search",
                headers=self._headers(),
                json={"artist": artist, "title": title},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
    
    async def download(
        self,
        search_id: str,
        result_index: int,
        output_filename: Optional[str] = None,
        gcs_path: Optional[str] = None,
    ) -> str:
        """
        Start download and return download_id.
        
        If gcs_path is provided, file will be uploaded to GCS.
        """
        async with httpx.AsyncClient() as client:
            payload = {
                "search_id": search_id,
                "result_index": result_index,
            }
            if output_filename:
                payload["output_filename"] = output_filename
            if gcs_path:
                payload["upload_to_gcs"] = True
                payload["gcs_path"] = gcs_path
            
            resp = await client.post(
                f"{self.base_url}/download",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()["download_id"]
    
    async def get_download_status(self, download_id: str) -> Dict[str, Any]:
        """Get download status."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/download/{download_id}/status",
                headers=self._headers(),
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
    
    async def wait_for_download(
        self,
        download_id: str,
        timeout: int = 600,
        poll_interval: int = 2,
    ) -> Dict[str, Any]:
        """
        Wait for download to complete.
        
        Returns final status dict with output_path or gcs_path.
        Raises FlacfetchServiceError on failure or timeout.
        """
        elapsed = 0
        while elapsed < timeout:
            status = await self.get_download_status(download_id)
            
            if status["status"] == "complete":
                return status
            elif status["status"] == "failed":
                raise FlacfetchServiceError(f"Download failed: {status.get('error')}")
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        raise FlacfetchServiceError(f"Download timed out after {timeout}s")


# Singleton
_client: Optional[FlacfetchClient] = None


def get_flacfetch_client() -> Optional[FlacfetchClient]:
    """Get flacfetch client if configured."""
    global _client
    if _client is None:
        from backend.config import get_settings
        settings = get_settings()
        if settings.flacfetch_api_url and settings.flacfetch_api_key:
            _client = FlacfetchClient(
                base_url=settings.flacfetch_api_url,
                api_key=settings.flacfetch_api_key,
            )
    return _client
```

**Modify:** `backend/services/audio_search_service.py` to use remote client when available.

**Modify:** `backend/config.py` to add new settings:
```python
flacfetch_api_url: Optional[str] = None  # e.g., http://10.0.0.5:8080
flacfetch_api_key: Optional[str] = None
```

### Phase 4: Monitoring & Reliability

**Tasks:**
- [ ] Add Cloud Monitoring alert for VM CPU/memory
- [ ] Add alert for disk space < 5GB
- [ ] Add alert for flacfetch service down (health check fails)
- [ ] Configure Cloud Logging export from VM
- [ ] Add Grafana dashboard (optional)

**Automatic Disk Cleanup:**
The disk manager runs as a background task in the flacfetch API service:
```python
# Check every 5 minutes, cleanup if free space < threshold
async def background_cleanup_task():
    while True:
        await asyncio.sleep(300)
        free_gb = get_free_space_gb()
        if free_gb < MIN_FREE_GB:
            cleanup_oldest_torrents(target_free_gb=MIN_FREE_GB + 5)
```

### Phase 5: Testing & Documentation

**Testing:**
- [ ] Unit tests for flacfetch API endpoints
- [ ] Unit tests for disk manager
- [ ] Integration test: search → download → GCS upload
- [ ] Mock tests for karaoke-gen backend client

**Documentation:**
- [ ] Update `docs/01-reference/ARCHITECTURE.md` with flacfetch service
- [ ] Add `flacfetch/README.md` HTTP API section
- [ ] Document deployment process
- [ ] Document environment variables

## Environment Variables

### Flacfetch Service (VM)
```bash
# API Configuration
FLACFETCH_API_KEY=<secret>           # Required for API auth
FLACFETCH_API_PORT=8080              # Default: 8080
FLACFETCH_API_HOST=0.0.0.0           # Default: 0.0.0.0

# Tracker API Keys
RED_API_KEY=<key>                    # For RED provider
RED_API_URL=<url>                    # For RED provider base URL
OPS_API_KEY=<key>                    # For OPS provider

# GCS Upload (optional)
GCS_BUCKET=karaoke-uploads           # For uploading completed downloads
GOOGLE_CLOUD_PROJECT=nomadkaraoke

# Transmission
TRANSMISSION_HOST=localhost          # Default: localhost
TRANSMISSION_PORT=9091               # Default: 9091

# Behavior
FLACFETCH_KEEP_SEEDING=true          # Keep torrents seeding after download
FLACFETCH_MIN_FREE_GB=5              # Minimum free disk space before cleanup
FLACFETCH_DOWNLOAD_DIR=/var/lib/transmission-daemon/downloads
```

### Cloud Run Backend
```bash
# New variables
FLACFETCH_API_URL=http://10.128.0.5:8080   # Internal IP of flacfetch VM
FLACFETCH_API_KEY=<same-secret>
```

## Security Considerations

1. **API Authentication**: Static API key in `X-API-Key` header
2. **Firewall**: Permissive for future web UI, auth enforced at application level
3. **GCS**: Service account with `storage.objectCreator` role only
4. **Transmission**: RPC bound to localhost only, no external access
5. **Static IP**: Can be whitelisted on tracker accounts

## Rollback Plan

If flacfetch service fails:
1. Set `FLACFETCH_API_URL=""` in Cloud Run (disables remote service)
2. Backend falls back to local flacfetch (YouTube only in Cloud Run)
3. Users see warning that lossless downloads may be slower/unavailable

## Cost Estimate

| Resource | Monthly Cost |
|----------|--------------|
| e2-small VM | ~$12 |
| Static IP | ~$3 |
| 30GB SSD | ~$5 |
| Network egress | ~$2-5 |
| **Total** | **~$22-25/month** |

## Success Criteria

- [x] Flacfetch HTTP API accepts search requests and returns results
- [x] Downloads complete successfully for RED/OPS sources
- [x] Downloaded files upload to GCS automatically
- [x] Torrents continue seeding after download
- [x] Disk cleanup triggers automatically when space is low
- [x] Remote CLI shows download progress from flacfetch service
- [x] Fallback to local flacfetch works when service unavailable
- [x] Static IP can be whitelisted on tracker accounts

## Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Flacfetch HTTP API | 1.5 days | None |
| Phase 2: Infrastructure | 0.5 day | Phase 1 |
| Phase 3: Backend Integration | 0.5 day | Phase 1, 2 |
| Phase 4: Monitoring | 0.5 day | Phase 2 |
| Phase 5: Testing & Docs | 0.5 day | Phase 1-3 |
| **Total** | **3.5 days** | |

## Implementation Status (2025-12-22)

### Completed Work

#### Phase 1: Flacfetch HTTP API ✅
- Full HTTP API implemented in `flacfetch/flacfetch/api/`
- Endpoints: `/search`, `/download`, `/download/{id}/status`, `/download/{id}/file`, `/torrents`, `/health`
- API key authentication via `X-API-Key` header
- Disk manager with automatic cleanup when space < 5GB
- Download manager with search caching and progress tracking
- Dynamic version reporting via `importlib.metadata`
- **Current Version:** 0.7.3

#### Phase 2: Infrastructure ✅
- Pulumi infrastructure in `infrastructure/__main__.py`
- GCP VM: `flacfetch-service` (e2-small, us-central1-a)
- Static IP: `104.198.214.26` (whitelisted with trackers)
- Firewall rules: TCP/UDP 51413 (BitTorrent), TCP 8080 (API)
- Secrets: `flacfetch-api-key`, `red-api-key`, `red-api-url`, `ops-api-key`, `ops-api-url`, `flacfetch-api-url`
- GitHub Actions deployer has `compute.admin` and `compute.osLogin` roles

#### Phase 3: Backend Integration ✅
- `FlacfetchClient` in `backend/services/flacfetch_client.py`
- `AudioSearchService` updated to use remote flacfetch when configured
- Cloud Run configured with `FLACFETCH_API_URL` and `FLACFETCH_API_KEY` from Secret Manager
- `--loop asyncio` added to uvicorn CMD (required for `nest_asyncio` compatibility)
- `nest_asyncio` applied only when async loop is running (not at import time)

#### Phase 4: Monitoring ✅
- Health endpoint reports Transmission status, disk usage, provider availability
- Version verification in deployment workflows
- Automatic deployment on release via GitHub Actions

#### Phase 5: CLI & Testing ✅
- `flacfetch-remote` CLI added for testing remote API
- Downloads file locally with descriptive filenames (e.g., `Artist - Title (Album, 2022, CD, 16bit, RED).flac`)
- 70%+ unit test coverage requirement enforced
- Integration tests for API routes

### Deployment Automation

#### Flacfetch VM (automatic)
- `.github/workflows/release-on-version-bump.yml` in flacfetch repo
- Triggers on version bump in `pyproject.toml`
- Runs tests → Creates GitHub release → SSHs to VM → Pulls latest → Restarts service
- Verifies deployed version matches release version

#### Karaoke-gen Backend (version-gated)
- `.github/workflows/ci.yml` deploy-backend job
- Only deploys if version tag doesn't exist (requires version bump)
- Verifies deployed version via `/api/health/detailed` endpoint
- Retries version check with backoff for Cloud Run routing delays

### Key Files Modified

**Flacfetch repo (`./flacfetch/`):**
- `flacfetch/api/` - New HTTP API module
- `flacfetch/interface/cli_remote.py` - New remote CLI
- `flacfetch/core/manager.py` - Improved sorting (artist match, release type, seeders)
- `flacfetch/downloaders/torrent.py` - Keep-seeding mode, file permissions fix
- `.github/workflows/release-on-version-bump.yml` - Auto-deploy to VM

**Karaoke-gen repo:**
- `backend/services/flacfetch_client.py` - Remote API client
- `backend/services/audio_search_service.py` - Remote integration with nest_asyncio
- `backend/Dockerfile` - `--loop asyncio` for uvicorn
- `infrastructure/__main__.py` - VM, firewall, secrets, WIF bindings
- `cloudbuild.yaml` - FLACFETCH_API_URL/KEY from Secret Manager
- `.github/workflows/ci.yml` - Version-gated deployments

### Testing the Integration

```bash
# Test flacfetch-remote CLI (requires env vars)
export FLACFETCH_API_URL=http://104.198.214.26:8080
export FLACFETCH_API_KEY=<from-secret-manager>
flacfetch-remote "Avril Lavigne" "Unwanted"

# Test backend health
curl -s https://api.nomadkaraoke.com/api/health/detailed | jq '.dependencies.flacfetch_remote'

# Test backend search
curl -s -X POST https://api.nomadkaraoke.com/api/audio-search/search \
  -H "Content-Type: application/json" \
  -d '{"artist": "Avril Lavigne", "title": "Unwanted"}' | jq '.results | length'
```

### Known Issues / Future Work

1. **Transmission removal from Cloud Run**: Transmission daemon and startup script removed from Docker images as torrent downloads are now handled by dedicated VM.

2. **URL field in search results**: Made optional in `AudioSearchResultResponse` since remote results don't have direct download URLs.

3. **Sorting improvements**: Results now prioritize:
   - Lossless first
   - Artist name match (exact match wins)
   - Release type (Album > Single > EP > Compilation > Anthology > Remix)
   - Seeders (more = higher)
   - Quality (24bit > 16bit, FLAC > MP3)

4. **Future enhancements**:
   - Cloud Monitoring alerts for disk/CPU/memory
   - Grafana dashboard for torrent stats
   - Web UI for manual torrent management

## References

- [Transmission RPC Spec](https://github.com/transmission/transmission/blob/main/docs/rpc-spec.md)
- [transmission-rpc Python library](https://github.com/Trim21/transmission-rpc)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [flacfetch source code](./flacfetch/)
