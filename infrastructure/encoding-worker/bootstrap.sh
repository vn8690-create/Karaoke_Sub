#!/bin/bash
# Encoding Worker Bootstrap Script
#
# This is the ONLY script baked into the Packer image.
# It downloads and executes the real startup script from GCS.
#
# Why this pattern?
# - startup.sh logic can be updated without rebuilding the image
# - All code changes go through CI → GCS → service restart
# - No version sorting bugs (fixed path for wheel)
# - Strict version verification before starting
#
# This script should NEVER need modification. All logic lives in
# the GCS-hosted startup.sh which is managed by CI.

set -e

BUCKET="gs://karaoke-gen-storage-nomadkaraoke"
WORKER_DIR="/opt/encoding-worker"
LOG_FILE="/var/log/encoding-worker-bootstrap.log"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Bootstrap: $(date) ==="
echo "Downloading latest startup script from GCS..."

# Download the CI-managed startup script
if ! gsutil cp "${BUCKET}/encoding-worker/startup.sh" "${WORKER_DIR}/startup-latest.sh" 2>&1; then
    echo "ERROR: Failed to download startup.sh from GCS"
    echo "Falling back to local startup.sh if available..."
    if [ -f "${WORKER_DIR}/startup-fallback.sh" ]; then
        cp "${WORKER_DIR}/startup-fallback.sh" "${WORKER_DIR}/startup-latest.sh"
    else
        echo "FATAL: No fallback startup script available"
        exit 1
    fi
fi

chmod +x "${WORKER_DIR}/startup-latest.sh"

echo "=== Bootstrap: Executing downloaded startup script ==="
exec "${WORKER_DIR}/startup-latest.sh"
