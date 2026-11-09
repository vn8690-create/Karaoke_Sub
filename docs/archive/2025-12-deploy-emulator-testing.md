# Local Emulator Testing Guide

## Overview

The karaoke-gen backend now includes comprehensive emulator-based integration tests that run against local GCP emulators (Firestore and GCS). These tests provide true end-to-end validation without requiring cloud resources or incurring costs.

## Architecture

### Test Layers

```
┌──────────────────────────────────┐
│   Unit Tests (Mocked)            │  ← 62 tests, 0.4s
│   Fast, isolated                 │     Test business logic
├──────────────────────────────────┤
│   Emulator Integration Tests     │  ← 11 tests, 2s
│   - Firestore Emulator           │     Test with local "real" services
│   - fake-gcs-server (GCS)        │     No cloud resources needed
│   - Local FastAPI (TestClient)   │
├──────────────────────────────────┤
│   Cloud Integration Tests        │  ← test_api_integration.py
│   Test deployed backend          │     Run before prod deploy
└──────────────────────────────────┘
```

### What Gets Tested

**Emulator tests validate:**
- ✅ Job creation with Firestore
- ✅ Job retrieval and listing
- ✅ Job updates and status transitions
- ✅ Job deletion
- ✅ File uploads to GCS
- ✅ Internal worker endpoints
- ✅ Error handling
- ✅ Timeline tracking

**What's mocked:**
- ❌ Background workers (to avoid race conditions)
- ❌ External APIs (AudioShake, YouTube, etc.)

## Setup

### Prerequisites

1. **Google Cloud SDK** with Firestore emulator:
```bash
gcloud components install cloud-firestore-emulator
```

2. **Docker** (for fake-gcs-server):
```bash
docker pull fsouza/fake-gcs-server
```

3. **Python venv** with dependencies:
```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running Tests

### Quick Start

```bash
# From project root
./scripts/run-emulator-tests.sh
```

This script will:
1. Start Firestore emulator (port 8080)
2. Start GCS emulator (port 4443)
3. Run all emulator integration tests
4. Stop emulators on completion

### Manual Testing

```bash
# Start emulators
./scripts/start-emulators.sh

# Run tests
source backend/venv/bin/activate
export FIRESTORE_EMULATOR_HOST=localhost:8080
export STORAGE_EMULATOR_HOST=http://localhost:4443
export GOOGLE_CLOUD_PROJECT=test-project
export GCS_BUCKET_NAME=test-bucket
export FIRESTORE_COLLECTION=test-jobs
export ENVIRONMENT=test
export ADMIN_TOKENS=test-admin-token

pytest backend/tests/emulator/ -v

# Stop emulators
./scripts/stop-emulators.sh
```

### Test Subset

```bash
# Run specific test class
pytest backend/tests/emulator/test_emulator_integration.py::TestJobCreation -v

# Run specific test
pytest backend/tests/emulator/test_emulator_integration.py::TestJobCreation::test_create_job_simple -v
```

## Test Structure

### Directory Layout

```
backend/tests/
├── conftest.py                    # Shared fixtures for unit tests
├── test_models.py                 # Unit tests
├── test_job_manager.py           # Unit tests
├── test_file_upload.py           # Unit tests
├── test_services.py              # Unit tests
├── test_api_integration.py       # Cloud integration tests
└── emulator/
    ├── __init__.py
    ├── conftest.py               # Emulator-specific fixtures
    └── test_emulator_integration.py  # Emulator integration tests
```

### Key Files

**`backend/tests/emulator/conftest.py`**
- Sets environment variables for emulators
- Mocks worker service to prevent background tasks
- Provides FastAPI TestClient

**`backend/tests/emulator/test_emulator_integration.py`**
- Contains 11 integration test classes
- Each class tests a specific feature (creation, retrieval, updates, etc.)
- Uses real Firestore and GCS emulators

**`scripts/start-emulators.sh`**
- Starts Firestore emulator (port 8080)
- Starts fake-gcs-server via Docker (port 4443)
- Creates GCS bucket

**`scripts/stop-emulators.sh`**
- Stops Firestore emulator
- Stops and removes GCS Docker container

**`scripts/run-emulator-tests.sh`**
- End-to-end test runner
- Starts emulators, runs tests, stops emulators
- Returns exit code 0 if all tests pass

## Troubleshooting

### Emulators Already Running

```
⚠️  Firestore emulator already running on port 8080
```

**Solution:** Stop existing emulators first:
```bash
./scripts/stop-emulators.sh
```

### Docker Not Running

```
❌ Docker is not running. Please start Docker and try again.
```

**Solution:** Start Docker Desktop or Docker daemon.

### Port Conflicts

If ports 8080 or 4443 are in use:

```bash
# Check what's using the ports
lsof -i :8080
lsof -i :4443

# Kill processes or change ports in scripts
```

### Tests Fail with "MagicMock" in Firestore Data

This means the unit test mocks are leaking into emulator tests.

**Solution:** Ensure emulator tests are in `backend/tests/emulator/` directory with their own `conftest.py` that does NOT mock `google.cloud.*` modules.

### Emulator Data Persists Between Runs

Firestore emulator data is in-memory and clears on restart. If you see stale data, restart the emulators:

```bash
./scripts/stop-emulators.sh
./scripts/start-emulators.sh
```

## CI/CD Integration

### Local Pre-Commit

```bash
# Run before committing
./scripts/run-tests.sh                # Unit tests (62 tests, 0.4s)
./scripts/run-emulator-tests.sh       # Integration tests (11 tests, 2s)
```

### GitHub Actions (Future)

```yaml
# .github/workflows/test.yml
- name: Install gcloud emulator
  run: gcloud components install cloud-firestore-emulator

- name: Run emulator tests
  run: ./scripts/run-emulator-tests.sh
```

## Benefits

### Why Emulator Tests?

1. **Fast Feedback** - 2 seconds vs 10+ minutes for cloud tests
2. **No Costs** - Run unlimited tests locally for free
3. **True Integration** - Real Firestore/GCS behavior, not mocks
4. **Offline Development** - No internet required
5. **Catch Real Bugs** - Found the `input_media_gcs_path` bug that unit tests missed!

### What They Catch

- Firestore query syntax errors
- Missing Firestore indexes
- GCS path issues
- Pydantic serialization bugs
- API integration issues

## Performance

```bash
# Typical run times
Unit tests:              0.4s   (62 tests)
Emulator tests:          2.0s   (11 tests)
Cloud integration tests: 10min+ (depends on backend state)
```

## Next Steps

- Add more emulator tests for human-in-the-loop flows
- Add emulator tests for corrections and instrumental selection
- Consider adding Pub/Sub emulator for future features
- Integrate into CI/CD pipeline

