# Testing Guide

This guide covers how to test the karaoke-gen project, including both the CLI library and the backend API.

## Quick Start

### Run All Unit Tests
```bash
# From repo root - runs both karaoke-gen CLI and backend tests
pytest
```

### Run Specific Test Suites
```bash
# CLI library tests only
pytest tests/

# Backend tests only
pytest backend/tests/

# Specific test file
pytest backend/tests/test_models.py -v
```

## Test Organization

```
karaoke-gen/
├── tests/                      # CLI library tests
│   ├── unit/                   # Unit tests
│   └── integration/            # Integration tests
├── backend/tests/              # Backend API tests
│   ├── test_models.py          # Pydantic model tests
│   ├── test_services.py        # Service layer tests
│   ├── test_job_manager.py     # JobManager tests
│   ├── test_file_upload.py     # File upload tests
│   ├── test_api_integration.py # Live API integration tests
│   ├── test_emulator_integration.py  # Emulator tests
│   └── emulator/               # Emulator-specific tests
│       ├── conftest.py
│       └── test_emulator_integration.py
└── scripts/
    ├── run-tests.sh            # Main test runner
    ├── run-emulator-tests.sh   # Emulator tests
    └── run-backend-local.sh    # Local dev server
```

## Test Types

### 1. Unit Tests (Fast, No External Dependencies)
- Run by default with `pytest`
- Mock all external services
- ~30 seconds to complete
- **Should catch most bugs before deployment**

### 2. Emulator Tests (Medium, Local Services)
- Require GCP emulators (Firestore, GCS)
- Skip automatically if emulators aren't running
- Start emulators: `./scripts/start-emulators.sh`
- Run emulator tests: `./scripts/run-emulator-tests.sh`

### 3. Integration Tests (Slow, Live Services)
- Require deployed backend
- Skip by default
- Run with: `RUN_INTEGRATION_TESTS=true pytest backend/tests/test_api_integration.py`

## Running Tests Locally

### Standard Test Run
```bash
# Activate poetry environment and run all tests
poetry run pytest

# With verbose output
poetry run pytest -v

# Stop on first failure
poetry run pytest -x

# Run specific test
poetry run pytest backend/tests/test_models.py::TestJob::test_create_job
```

### With GCP Emulators
```bash
# Terminal 1: Start emulators
./scripts/start-emulators.sh

# Terminal 2: Run emulator tests
./scripts/run-emulator-tests.sh

# Terminal 3: Run local backend (optional)
./scripts/run-backend-local.sh --with-emulators
```

### Running Backend Locally
```bash
# Against real GCP (requires credentials)
./scripts/run-backend-local.sh

# Against emulators
./scripts/run-backend-local.sh --with-emulators
```

Then test with:
```bash
curl http://localhost:8000/api/health
```

## Writing Tests

### Best Practices

1. **Mock external services**: Always mock Firestore, GCS, and external APIs
2. **Test data structures**: Validate Pydantic models handle all expected shapes
3. **Test edge cases**: Empty values, nested dicts, type mismatches
4. **Use fixtures**: Share common setup in `conftest.py`

### Example: Testing a Model Field

```python
def test_file_urls_with_nested_stems(self):
    """Test file_urls handles nested dictionary structure."""
    job = Job(
        job_id="test123",
        status=JobStatus.SEPARATING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        file_urls={
            "stems": {
                "instrumental_clean": "gs://bucket/stems/clean.flac",
                "vocals": "gs://bucket/stems/vocals.flac"
            }
        }
    )
    assert "stems" in job.file_urls
    assert job.file_urls["stems"]["instrumental_clean"] == "gs://bucket/stems/clean.flac"
```

### Example: Testing a Service with Mocks

```python
@pytest.fixture
def mock_firestore():
    with patch('backend.services.firestore_service.firestore.Client') as mock:
        yield mock.return_value

def test_create_job(mock_firestore):
    mock_firestore.collection.return_value.document.return_value.set.return_value = None
    service = FirestoreService()
    # ... test logic
```

## Coverage

Coverage reports are generated automatically:
- Terminal: Shows missing lines
- HTML: `htmlcov/index.html`

View coverage:
```bash
pytest --cov=backend --cov=karaoke_gen --cov-report=html
open htmlcov/index.html
```

## CI/CD Testing

The GitHub Actions workflow runs:
1. **Unit Tests**: All unit tests for CLI and backend
2. **Emulator Tests**: Against local GCP emulators
3. **Deploy**: To Cloud Run (only on push to main branch)

### Why Tests Might Fail in CI but Pass Locally

1. **Missing dependencies**: Check `pyproject.toml` includes all deps
2. **Environment differences**: CI uses Ubuntu, check for path issues
3. **Timing issues**: Tests may need delays for async operations
4. **Mock leakage**: Ensure mocks are properly scoped

## Debugging Test Failures

### Check Test Output
```bash
pytest -v --tb=long backend/tests/test_models.py
```

### Run Single Test
```bash
pytest backend/tests/test_models.py::TestJob::test_create_job -v -s
```

### Debug with Print Statements
```bash
pytest -v -s  # -s shows print output
```

### Check Logs
```bash
# For emulator tests
cat /tmp/emulator-logs/firestore.log
cat /tmp/emulator-logs/gcs.log
```

## Common Issues

### "ModuleNotFoundError: No module named 'google.cloud.firestore_v1'"
- Run `poetry install` to install dependencies
- Or run tests via `poetry run pytest`

### "GCP emulators not running"
- Start emulators: `./scripts/start-emulators.sh`
- Check ports 8080 (Firestore) and 4443 (GCS) are available

### "Connection refused" errors
- Check emulators use `127.0.0.1` not `localhost` (IPv6 issues)
- Verify environment variables: `FIRESTORE_EMULATOR_HOST`, `STORAGE_EMULATOR_HOST`

### "Pydantic validation error"
- Check model field types match actual data structures
- Use `Dict[str, Any]` for nested/flexible dicts, not `Dict[str, str]`

