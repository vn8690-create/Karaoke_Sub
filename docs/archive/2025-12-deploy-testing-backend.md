# Backend Testing Guide

Complete guide for testing the karaoke generation backend.

## Test Suite Overview

The test suite includes:
- **Health checks** - Service availability and configuration
- **Job submission** - URL and file upload validation
- **Job management** - Status checking, listing, deletion
- **File upload** - Audio file upload and validation
- **End-to-end** - Complete workflow testing (slow tests)

## Quick Start

### 1. Install Test Dependencies

```bash
cd backend
pip install -r tests/requirements.txt
```

Dependencies:
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-timeout` - Test timeouts
- `pytest-cov` - Code coverage
- `requests` - HTTP client

### 2. Run Tests

```bash
# Run all fast tests (recommended first)
./run_tests.sh

# Or manually with pytest
pytest tests/test_api_integration.py -v -m "not slow"
```

### 3. Run Slow/Integration Tests

These test actual job processing and take 5-10 minutes:

```bash
pytest tests/test_api_integration.py -v -m "slow"
```

## Test Categories

### Fast Tests (~2 minutes)

Test API endpoints without full job processing:
- ✅ Health check
- ✅ Job submission (URL and file)
- ✅ Job status retrieval
- ✅ Job listing and filtering
- ✅ Job deletion
- ✅ Input validation
- ✅ Error handling

```bash
pytest tests/ -m "not slow"
```

### Slow Tests (~10 minutes)

Test complete job workflows:
- ⏱️ End-to-end job processing
- ⏱️ Video generation
- ⏱️ File downloads

```bash
pytest tests/ -m "slow"
```

## Running Specific Tests

### Run a specific test class

```bash
pytest tests/test_api_integration.py::TestHealthEndpoint -v
```

### Run a specific test

```bash
pytest tests/test_api_integration.py::TestJobSubmission::test_submit_job_with_youtube_url -v
```

### Run with detailed output

```bash
pytest tests/ -vv --tb=long
```

### Run with coverage

```bash
pytest tests/ --cov=backend --cov-report=html
# Open htmlcov/index.html to view coverage report
```

## Test Configuration

Configuration is in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
]
```

## Expected Test Results

### All Tests Passing

```
tests/test_api_integration.py::TestHealthEndpoint::test_health_check PASSED
tests/test_api_integration.py::TestHealthEndpoint::test_health_check_without_auth PASSED
tests/test_api_integration.py::TestRootEndpoint::test_root_endpoint PASSED
tests/test_api_integration.py::TestJobSubmission::test_submit_job_with_youtube_url PASSED
tests/test_api_integration.py::TestJobSubmission::test_submit_job_with_invalid_url PASSED
tests/test_api_integration.py::TestJobSubmission::test_submit_job_without_url PASSED
tests/test_api_integration.py::TestJobRetrieval::test_get_job_status PASSED
tests/test_api_integration.py::TestJobRetrieval::test_get_nonexistent_job PASSED
tests/test_api_integration.py::TestJobRetrieval::test_list_jobs PASSED
tests/test_api_integration.py::TestJobRetrieval::test_list_jobs_with_status_filter PASSED
tests/test_api_integration.py::TestJobRetrieval::test_list_jobs_with_limit PASSED
tests/test_api_integration.py::TestJobDeletion::test_delete_job PASSED
tests/test_api_integration.py::TestJobDeletion::test_delete_job_without_files PASSED
tests/test_api_integration.py::TestJobDeletion::test_delete_nonexistent_job PASSED
tests/test_api_integration.py::TestFileUpload::test_upload_audio_file PASSED
tests/test_api_integration.py::TestFileUpload::test_upload_invalid_file_type PASSED
tests/test_api_integration.py::TestFileUpload::test_upload_without_metadata PASSED

========================== 17 passed in 45.23s ==========================
```

## Troubleshooting

### Authentication Errors

If tests fail with 403 Forbidden:

```bash
# Re-authenticate
gcloud auth login
gcloud auth application-default login

# Verify authentication works
gcloud auth print-identity-token
```

### Service URL Not Found

Update the `SERVICE_URL` in `tests/test_api_integration.py`:

```python
SERVICE_URL = "https://karaoke-backend-718638054799.us-central1.run.app"
```

### Tests Timeout

Increase timeout in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
timeout = 600  # 10 minutes
```

### Import Errors

Ensure you're in the backend directory and dependencies are installed:

```bash
cd backend
pip install -r tests/requirements.txt
python -m pytest tests/ -v
```

## Continuous Integration

For CI/CD pipelines, run tests non-interactively:

```bash
# Fast tests only (for PR checks)
pytest tests/ -v -m "not slow" --tb=short

# All tests (for deployment verification)
pytest tests/ -v --tb=short
```

## Manual Testing

For manual API testing with curl, see:
- `docs/API-MANUAL-TESTING.md` - Complete curl command reference

## Next Steps

After all tests pass:
1. ✅ Backend verified and working
2. 🚀 Build React frontend
3. 🔗 Integration testing with frontend
4. 📊 Performance testing
5. 🌐 Deploy to production

## Test Coverage Goals

- **API Endpoints**: 100% coverage
- **Service Layer**: 80%+ coverage
- **Error Handling**: 100% coverage

Run coverage report:

```bash
pytest tests/ --cov=backend --cov-report=term-missing
```

---

**Status**: Tests ready to run!

Execute `./run_tests.sh` to verify backend functionality.

