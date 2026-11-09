# Phase 5: Encoding Worker Custom Machine Image

## Problem Statement

The encoding worker VM currently takes **~10 minutes** to become ready after startup because the startup script:

1. Builds Python 3.13 from source (`./configure && make -j$(nproc)`) - ~7 minutes
2. Downloads and installs FFmpeg static build - ~1 minute
3. Installs system packages and fonts - ~1 minute
4. Creates Python venv and installs dependencies - ~1 minute

This slow startup affects:
- **VM restarts**: Any maintenance event or restart requires waiting 10 minutes
- **Scaling**: Can't quickly add capacity if needed
- **Development**: Testing infrastructure changes is slow

## Solution: Pre-baked Machine Image with Packer

Create a custom GCE machine image using [Packer](https://www.packer.io/) that pre-installs all dependencies. The startup script then only needs to:

1. Fetch API key from Secret Manager (~5 seconds)
2. Download latest karaoke-gen wheel from GCS (~10 seconds)
3. Start the systemd service (~5 seconds)

**Expected startup time: ~30 seconds** (vs current ~10 minutes)

## Implementation Plan

### 1. Create Packer Directory Structure

```
infrastructure/packer/
├── encoding-worker.pkr.hcl    # Packer template
├── scripts/
│   └── provision.sh           # Provisioning script
└── README.md                  # Usage documentation
```

### 2. Packer Template (`encoding-worker.pkr.hcl`)

```hcl
packer {
  required_plugins {
    googlecompute = {
      source  = "github.com/hashicorp/googlecompute"
      version = "~> 1.1"
    }
  }
}

variable "project_id" {
  type    = string
  default = "nomadkaraoke"
}

variable "zone" {
  type    = string
  default = "us-central1-a"
}

variable "python_version" {
  type    = string
  default = "3.13.1"
}

source "googlecompute" "encoding-worker" {
  project_id          = var.project_id
  zone                = var.zone
  source_image_family = "debian-12"
  source_image_project_id = "debian-cloud"

  # Build on same machine type as production for consistency
  machine_type        = "c4-standard-8"
  disk_size           = 100
  disk_type           = "pd-ssd"  # Use SSD for faster builds

  image_name          = "encoding-worker-{{timestamp}}"
  image_family        = "encoding-worker"
  image_description   = "Encoding worker with Python ${var.python_version}, FFmpeg, and fonts pre-installed"

  ssh_username        = "packer"

  # Tags for firewall rules during build
  tags                = ["packer-build"]
}

build {
  sources = ["source.googlecompute.encoding-worker"]

  # Upload provisioning script
  provisioner "file" {
    source      = "scripts/provision.sh"
    destination = "/tmp/provision.sh"
  }

  # Run provisioning
  provisioner "shell" {
    inline = [
      "chmod +x /tmp/provision.sh",
      "sudo PYTHON_VERSION=${var.python_version} /tmp/provision.sh"
    ]
  }

  # Clean up for smaller image
  provisioner "shell" {
    inline = [
      "sudo apt-get clean",
      "sudo rm -rf /var/lib/apt/lists/*",
      "sudo rm -rf /tmp/*",
      "sudo rm -rf /var/tmp/*"
    ]
  }
}
```

### 3. Provisioning Script (`scripts/provision.sh`)

```bash
#!/bin/bash
# Provision encoding worker image with all dependencies pre-installed
set -e

echo "=== Starting encoding worker image provisioning ==="

# Install system packages
apt-get update
apt-get install -y \
    docker.io \
    curl \
    git \
    xz-utils \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncursesw5-dev \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev

# Install fonts for ASS subtitle rendering
apt-get install -y fonts-noto fonts-noto-cjk fontconfig
fc-cache -fv

# Enable Docker
systemctl enable docker

# Install optimized static FFmpeg build (John Van Sickle)
echo "Installing FFmpeg..."
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o /tmp/ffmpeg.tar.xz
tar -xf /tmp/ffmpeg.tar.xz -C /tmp
cp /tmp/ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/
cp /tmp/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/
chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe
rm -rf /tmp/ffmpeg*
ffmpeg -version

# Build and install Python from source
echo "Building Python ${PYTHON_VERSION}..."
cd /tmp
curl -L "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz" -o python.tar.xz
tar -xf python.tar.xz
cd "Python-${PYTHON_VERSION}"
./configure --prefix=/opt/python313 --enable-optimizations --with-lto
make -j$(nproc)
make install
rm -rf /tmp/python.tar.xz /tmp/Python-${PYTHON_VERSION}
/opt/python313/bin/python3.13 --version
echo "Python ${PYTHON_VERSION} installed at /opt/python313"

# Create working directory and venv
mkdir -p /opt/encoding-worker
cd /opt/encoding-worker
/opt/python313/bin/python3.13 -m venv venv

# Install base Python dependencies (wheel will add more at runtime)
source venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn google-cloud-storage aiofiles aiohttp

# Create systemd service template (API key filled at runtime)
cat > /etc/systemd/system/encoding-worker.service << 'SYSTEMD'
[Unit]
Description=Encoding Worker HTTP API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/encoding-worker
ExecStartPre=/opt/encoding-worker/startup.sh
ExecStart=/opt/encoding-worker/venv/bin/uvicorn backend.services.gce_encoding.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10
Environment="GOOGLE_CLOUD_PROJECT=nomadkaraoke"
EnvironmentFile=/opt/encoding-worker/env

[Install]
WantedBy=multi-user.target
SYSTEMD

# Create startup helper script (runs before service starts)
cat > /opt/encoding-worker/startup.sh << 'STARTUP'
#!/bin/bash
set -e

# Fetch API key from Secret Manager
ENCODING_API_KEY=$(gcloud secrets versions access latest --secret=encoding-worker-api-key 2>/dev/null || echo "")
echo "ENCODING_API_KEY=${ENCODING_API_KEY}" > /opt/encoding-worker/env

# Download and install latest karaoke-gen wheel
gsutil cp "gs://karaoke-gen-storage-nomadkaraoke/wheels/karaoke_gen-*.whl" /tmp/ 2>/dev/null || true
WHEEL_FILE=$(ls -t /tmp/karaoke_gen-*.whl 2>/dev/null | head -1)
if [ -n "$WHEEL_FILE" ]; then
    /opt/encoding-worker/venv/bin/pip install --upgrade --quiet "$WHEEL_FILE"
fi
STARTUP

chmod +x /opt/encoding-worker/startup.sh

# Enable service (will start on boot)
systemctl daemon-reload
systemctl enable encoding-worker

echo "=== Provisioning complete ==="
```

### 4. Update Pulumi to Use Custom Image

In `infrastructure/compute/encoding_worker_vm.py`, change:

```python
# Before (current)
boot_disk=compute.InstanceBootDiskArgs(
    initialize_params=compute.InstanceBootDiskInitializeParamsArgs(
        image="debian-cloud/debian-12",
        size=DiskSizes.ENCODING_WORKER,
        type="hyperdisk-balanced",
    ),
),

# After (with custom image)
boot_disk=compute.InstanceBootDiskArgs(
    initialize_params=compute.InstanceBootDiskInitializeParamsArgs(
        image=f"projects/{PROJECT_ID}/global/images/family/encoding-worker",
        size=DiskSizes.ENCODING_WORKER,
        type="hyperdisk-balanced",
    ),
),
```

### 5. Simplified Startup Script

Replace the 700-line `encoding_worker.sh` with a minimal script:

```bash
#!/bin/bash
# Encoding worker startup script (for custom image)
# Most dependencies are pre-installed in the image.
# This script just starts the service.

set -e
exec > >(tee /var/log/encoding-worker-startup.log) 2>&1
echo "Starting encoding worker at $(date)"

# Start Docker (in case it's not running)
systemctl start docker

# Start the encoding worker service
# The service's ExecStartPre handles:
# - Fetching API key from Secret Manager
# - Installing latest karaoke-gen wheel
systemctl start encoding-worker

echo "Encoding worker started at $(date)"
```

### 6. CI Integration (Optional)

Add a GitHub Actions workflow to rebuild the image when Packer files change:

```yaml
# .github/workflows/build-encoding-worker-image.yml
name: Build Encoding Worker Image

on:
  push:
    branches: [main]
    paths:
      - 'infrastructure/packer/**'
  workflow_dispatch:  # Manual trigger

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write

    steps:
      - uses: actions/checkout@v4

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com

      - name: Setup Packer
        uses: hashicorp/setup-packer@main
        with:
          version: latest

      - name: Build Image
        working-directory: infrastructure/packer
        run: |
          packer init encoding-worker.pkr.hcl
          packer build encoding-worker.pkr.hcl
```

## Execution Steps

1. **Create the Packer files** in `infrastructure/packer/`

2. **Build the image locally** (one-time, or via CI):
   ```bash
   cd infrastructure/packer
   packer init encoding-worker.pkr.hcl
   packer build encoding-worker.pkr.hcl
   ```

3. **Update Pulumi** to use the new image family

4. **Simplify the startup script** to just start the service

5. **Run `pulumi up`** to deploy with the new image

6. **Verify** the VM starts in ~30 seconds instead of ~10 minutes

## Rollback Plan

If issues occur:
1. Change the image back to `debian-cloud/debian-12` in Pulumi
2. Restore the full startup script
3. Run `pulumi up`

The old startup script is preserved in git history and can be restored.

## Benefits

| Metric | Before | After |
|--------|--------|-------|
| Startup time | ~10 min | ~30 sec |
| Python build | Every start | Never (pre-baked) |
| FFmpeg install | Every start | Never (pre-baked) |
| Image rebuild needed | N/A | Only when deps change |

## Maintenance

Rebuild the image when:
- Python version needs updating
- FFmpeg version needs updating
- New system packages required
- Font packages change

The karaoke-gen wheel is still downloaded at runtime, so application code updates don't require image rebuilds.
