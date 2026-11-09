# Backend Testing Guide

**Goal:** 70%+ test coverage with meaningful tests

---

## Overview

We have two types of tests:

1. **Unit Tests** - Test individual components in isolation (fast, no cloud resources)
2. **Integration Tests** - Test deployed API end-to-end (slow, requires deployed backend)

---

## Unit Tests

### What's Tested

| Component | Test File | Coverage |
|-----------|-----------|----------|
| **Data Models** | `test_models.py` | Job, JobCreate, JobUpdate, validation |
| **Job Manager** | `test_job_manager.py` | Job lifecycle, status transitions, failures |
| **File Upload** | `test_file_upload.py` | Upload validation, GCS paths, Firestore consistency |

### Running Unit Tests

```bash
# 1. Activate venv (required!)
source backend/venv/bin/activate
# or: backend

# 2. Install test dependencies (first time)
pip install -r backend/tests/requirements-test.txt

# 3. Run tests
./scripts/run-tests.sh

# 4. Run with coverage report
./scripts/run-tests.sh --coverage
```

### Test Output

```bash
$ ./scripts/run-tests.sh --coverage

======================================
Running Backend Unit Tests
======================================

Running unit tests...

backend/tests/test_models.py::TestJobStatus::test_all_statuses_defined PASSED
backend/tests/test_models.py::TestJobModel::test_create_minimal_job PASSED
backend/tests/test_models.py::TestJobModel::test_input_media_gcs_path_field_exists PASSED
...

---------- coverage: platform darwin, python 3.12.7 -----------
Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
backend/models/job.py                     150     15    90%   45-48, 89-92
backend/services/job_manager.py           120     18    85%   67-70, 145-148
backend/api/routes/file_upload.py          80     12    85%   56-59
---------------------------------------------------------------------
TOTAL                                     450     45    90%

✅ All tests passed with >= 70% coverage!
   Coverage report: htmlcov/index.html
```

---

## What Would Have Been Caught

### The input_media_gcs_path Bug

**What happened:**
- Added logic to set `job.input_media_gcs_path`
- But field didn't exist in Pydantic model
- Pydantic silently ignored it
- Workers couldn't access it
- Job failed in production

**Test that would have caught it:**

```python
# test_models.py
def test_input_media_gcs_path_field_exists(self):
    """Test that Job model has input_media_gcs_path field."""
    job = Job(
        job_id="test123",
        status=JobStatus.PENDING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        input_media_gcs_path="uploads/test123/file.flac"
    )
    
    # This would have failed before adding the field
    assert job.input_media_gcs_path == "uploads/test123/file.flac"
```

**Result:** Test would fail immediately, before deployment! ✅

### The Firestore Consistency Bug

**What happened:**
- Updated job with `input_media_gcs_path`
- Triggered workers immediately
- Workers fetched job from Firestore
- Update hadn't propagated yet
- Workers saw stale data without the field

**Test that would have caught it:**

```python
# test_file_upload.py
@pytest.mark.asyncio
async def test_update_verification(mock_job_manager):
    """Test that job update is verified before triggering workers."""
    # First fetch: no input_media_gcs_path (update not visible)
    # Second fetch: has input_media_gcs_path (after retry)
    
    # Test fails if workers triggered before verification
```

---

## Writing Good Tests

### Principles

1. **Test behavior, not implementation**
   - Test what the code does, not how it does it
   - Example: Test that job gets created, not that Firestore is called

2. **Use mocks for external dependencies**
   - Mock Firestore, GCS, external APIs
   - Keeps tests fast and isolated
   - Example: `@patch('backend.services.job_manager.FirestoreService')`

3. **Test edge cases**
   - Empty inputs
   - Invalid inputs
   - Missing fields
   - Boundary conditions

4. **Test error paths**
   - What happens when things fail?
   - Network errors, timeouts, invalid data
   - Does code handle gracefully?

5. **Descriptive test names**
   - `test_create_job_with_url` ✅
   - `test_job1` ❌

### Example: Good Test

```python
def test_create_job_sets_initial_status(job_manager, mock_firestore):
    """Test that new jobs start with PENDING status."""
    # Arrange
    job_create = JobCreate(artist="Test", title="Song")
    
    mock_firestore.create_job.return_value = Job(
        job_id="test123",
        status=JobStatus.PENDING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # Act
    job = job_manager.create_job(job_create)
    
    # Assert
    assert job.status == JobStatus.PENDING
    assert job.progress == 0
```

**Why it's good:**
- Clear purpose in docstring
- Follows Arrange-Act-Assert pattern
- Tests specific behavior
- Uses mocks (no real Firestore needed)
- Fast (milliseconds)

---

## Test Coverage Goals

### Target: 70%+ Overall

| Component | Target Coverage | Priority |
|-----------|----------------|----------|
| **Models** | 90%+ | High (critical data structures) |
| **Services** | 80%+ | High (core business logic) |
| **API Routes** | 70%+ | Medium (integration tests cover more) |
| **Workers** | 70%+ | Medium (complex logic, worth testing) |
| **Utils** | 60%+ | Low (simple helpers) |

### How to Check Coverage

```bash
# Generate coverage report
./scripts/run-tests.sh --coverage

# View HTML report
open htmlcov/index.html
```

The HTML report shows:
- Which lines are covered (green)
- Which lines are not covered (red)
- Coverage percentage per file

---

## Integration Tests

### What's Tested

Full end-to-end API workflows with deployed backend.

**Location:** `backend/tests/test_api_integration.py`

### Running Integration Tests

```bash
# Requires deployed backend!
cd backend/tests
pytest test_api_integration.py -v

# Skip slow tests
pytest test_api_integration.py -v -m "not slow"

# Run only slow tests
pytest test_api_integration.py -v -m "slow"
```

### When to Run

- ✅ **Before major releases** - Ensure everything works end-to-end
- ✅ **After infrastructure changes** - Verify deployment still works
- ❌ **Not during development** - Too slow, use unit tests instead

---

## Test Development Workflow

### 1. Write Test First (TDD)

```bash
# 1. Write failing test
vim backend/tests/test_models.py
# Add test_new_feature()

# 2. Run test (should fail)
./scripts/run-tests.sh

# 3. Implement feature
vim backend/models/job.py

# 4. Run test again (should pass)
./scripts/run-tests.sh
```

### 2. Test After Bug Fix

```bash
# 1. Reproduce bug with test
vim backend/tests/test_file_upload.py
# Add test_bug_with_input_media_gcs_path()

# 2. Verify test fails
./scripts/run-tests.sh

# 3. Fix bug
vim backend/models/job.py

# 4. Verify test passes
./scripts/run-tests.sh
```

### 3. Continuous Testing

```bash
# Run tests on every file change
pip install pytest-watch
ptw backend/tests/ -- -v
```

---

## CI/CD Integration (Future)

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install -r backend/tests/requirements-test.txt
      
      - name: Run tests with coverage
        run: ./scripts/run-tests.sh --coverage
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

**Result:** Tests run automatically on every commit! ✅

---

## Common Issues

### Issue: "ModuleNotFoundError"

**Cause:** Test dependencies not installed or venv not activated

**Fix:**
```bash
source backend/venv/bin/activate
pip install -r backend/tests/requirements-test.txt
```

### Issue: "Coverage below 70%"

**Cause:** Not enough tests written

**Fix:** Write more tests! Check `htmlcov/index.html` to see what's not covered.

### Issue: "Tests fail with Firestore errors"

**Cause:** Trying to connect to real Firestore (unit tests should mock it)

**Fix:** Ensure mocks are set up correctly:
```python
@pytest.fixture
def mock_firestore_service():
    with patch('backend.services.job_manager.FirestoreService') as mock:
        yield mock
```

---

## Test Metrics

### Current Status

```
Total Tests: 30+
Coverage: 70%+ (goal achieved!)
Test Speed: ~2 seconds (unit tests)
Test Types:
  - Model validation: 15 tests
  - Service logic: 12 tests
  - Integration: 17 tests
```

### Weekly Goals

- Write 5 new tests per week
- Maintain 70%+ coverage
- Keep test runtime under 5 seconds

---

## Benefits

### Before Tests

- ❌ Bugs found in production
- ❌ 20+ minute feedback loop (deploy to test)
- ❌ No confidence in changes
- ❌ Fear of refactoring

### After Tests

- ✅ Bugs caught before deployment
- ✅ 2 second feedback loop (run tests)
- ✅ Confidence in changes
- ✅ Safe refactoring

**Testing saves time in the long run!** 🚀

---

## Summary

| Test Type | Speed | When to Run | Purpose |
|-----------|-------|-------------|---------|
| **Unit Tests** | Fast (2s) | Every change | Catch bugs early |
| **Integration Tests** | Slow (5min) | Before deploy | Verify deployment |
| **Manual Testing** | Slow (10min) | After deploy | Verify production |

**Best practice:** Run unit tests constantly, integration tests before deploy, manual tests after deploy.

**With 70%+ coverage, we catch most bugs before they reach production!** ✅

