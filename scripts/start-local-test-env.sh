#!/bin/bash
# Start local test environment with emulators and backend
#
# This sets up everything needed to run CLI+Backend integration tests locally.
# Much faster than deploying to cloud for testing!
#
# Usage:
#   ./scripts/start-local-test-env.sh
#   # In another terminal:
#   pytest tests/integration/test_cli_backend_integration.py -v

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Starting local test environment"
echo "=================================="
echo ""

# Step 1: Start emulators
echo "Step 1/2: Starting GCP emulators..."
"$SCRIPT_DIR/start-emulators.sh"
echo ""

# Set environment variables for local backend
export FIRESTORE_EMULATOR_HOST="127.0.0.1:8080"
export STORAGE_EMULATOR_HOST="http://127.0.0.1:4443"
export GOOGLE_CLOUD_PROJECT="test-project"
export GCS_BUCKET_NAME="test-bucket"
export FIRESTORE_COLLECTION="jobs"
export ENVIRONMENT="test"
export ADMIN_TOKENS="test-admin-token"

# Also export for any external services to be mocked/disabled
export FLACFETCH_API_URL=""
export AUDIO_SEPARATOR_API_URL=""
export AUDIOSHAKE_API_TOKEN=""
export GENIUS_API_TOKEN=""
export SPOTIFY_COOKIE=""

echo "Step 2/2: Starting local backend..."
echo ""
echo "Environment:"
echo "  FIRESTORE_EMULATOR_HOST=$FIRESTORE_EMULATOR_HOST"
echo "  STORAGE_EMULATOR_HOST=$STORAGE_EMULATOR_HOST"
echo "  GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT"
echo "  ADMIN_TOKENS=test-admin-token"
echo ""

cd "$PROJECT_ROOT"

# Start backend in background
if command -v poetry &> /dev/null; then
    echo "Starting backend with poetry..."
    poetry run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
else
    echo "Starting backend with Python..."
    python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
fi

BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo ""
echo "Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "✅ Backend is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Backend failed to start"
        kill $BACKEND_PID 2>/dev/null || true
        "$SCRIPT_DIR/stop-emulators.sh"
        exit 1
    fi
    sleep 1
done

echo ""
echo "=============================================="
echo "✅ Local test environment is running!"
echo ""
echo "Run integration tests with:"
echo "  pytest tests/integration/test_cli_backend_integration.py -v"
echo ""
echo "Or run all CLI+Backend tests:"
echo "  ./scripts/run-cli-integration-tests.sh"
echo ""
echo "To stop:"
echo "  kill $BACKEND_PID"
echo "  ./scripts/stop-emulators.sh"
echo ""
echo "Backend PID: $BACKEND_PID"
echo "=============================================="

# Keep script running (for foreground mode)
wait $BACKEND_PID

