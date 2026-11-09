#!/bin/bash
# Run CLI + Backend integration tests
#
# This script:
# 1. Starts emulators
# 2. Starts local backend
# 3. Runs integration tests
# 4. Cleans up
#
# Usage:
#   ./scripts/run-cli-integration-tests.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🧪 Running CLI + Backend Integration Tests"
echo "==========================================="
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up..."
    
    # Kill backend if running
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
        echo "  Stopped backend (PID $BACKEND_PID)"
    fi
    
    # Stop emulators
    "$SCRIPT_DIR/stop-emulators.sh" 2>/dev/null || true
}

trap cleanup EXIT

# Step 1: Start emulators
echo "Step 1/4: Starting GCP emulators..."
"$SCRIPT_DIR/start-emulators.sh"
echo ""

# Step 2: Set environment
echo "Step 2/4: Setting environment..."
export FIRESTORE_EMULATOR_HOST="127.0.0.1:8080"
export STORAGE_EMULATOR_HOST="http://127.0.0.1:4443"
export GOOGLE_CLOUD_PROJECT="test-project"
export GCS_BUCKET_NAME="test-bucket"
export FIRESTORE_COLLECTION="jobs"
export ENVIRONMENT="test"
export ADMIN_TOKENS="test-admin-token"

# Disable external services for tests
export FLACFETCH_API_URL=""
export AUDIO_SEPARATOR_API_URL=""
export AUDIOSHAKE_API_TOKEN=""
export GENIUS_API_TOKEN=""
export SPOTIFY_COOKIE=""

echo "  Environment configured for local testing"
echo ""

# Step 3: Start backend
echo "Step 3/4: Starting local backend..."
cd "$PROJECT_ROOT"

if command -v poetry &> /dev/null; then
    poetry run uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
else
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
fi
BACKEND_PID=$!

# Wait for backend
echo "  Waiting for backend..."
for i in {1..30}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "  Backend ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "  ❌ Backend failed to start"
        exit 1
    fi
    sleep 1
done
echo ""

# Step 4: Run tests
echo "Step 4/4: Running integration tests..."
echo ""

cd "$PROJECT_ROOT"

if command -v poetry &> /dev/null; then
    PYTEST_CMD="poetry run pytest"
else
    PYTEST_CMD="pytest"
fi

# Run emulator tests (uses TestClient, doesn't need backend server)
echo "Running emulator tests..."
if $PYTEST_CMD backend/tests/emulator/ -v --tb=short; then
    echo "✅ Emulator tests passed!"
else
    echo "❌ Emulator tests failed"
    exit 1
fi

# Run CLI integration tests (if they exist)
if [ -f "tests/integration/test_cli_backend_integration.py" ]; then
    echo ""
    echo "Running CLI integration tests..."
    if $PYTEST_CMD tests/integration/test_cli_backend_integration.py -v --tb=short; then
        echo "✅ CLI integration tests passed!"
    else
        echo "❌ CLI integration tests failed"
        exit 1
    fi
fi

echo ""
echo "✅ All integration tests passed!"
exit 0

