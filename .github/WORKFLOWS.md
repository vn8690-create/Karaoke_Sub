# GitHub Actions CI/CD

This directory contains GitHub Actions workflows for automated testing and deployment.

## Workflows

### `test.yml` - Automated Testing & Deployment (CI/CD)

**Triggers:**
- Push to `main` or `replace-modal-with-google-cloud` branches
- Pull requests to `main`

**Jobs:**

#### Testing Phase (runs in parallel)

1. **Unit Tests** (~30s)
   - Runs 62 unit tests with mocked dependencies
   - Fast validation of business logic
   - Uses Python 3.12 with pip caching

2. **Emulator Integration Tests** (~2min)
   - Runs 11 integration tests against local GCP emulators
   - Tests real Firestore and GCS interactions
   - Requires:
     - Java 21 (for Firestore emulator)
     - Google Cloud SDK (for Firestore emulator)
     - Docker (for GCS emulator via fake-gcs-server)
   - Uses the same `scripts/run-emulator-tests.sh` as local development

3. **Code Quality** (~20s)
   - Basic Python syntax validation
   - Import checks
   - Optional: flake8, black, isort

#### Deployment Phase (runs after all tests pass)

4. **Deploy to Cloud Run** (~3-4min)
   - **Only runs on push to `replace-modal-with-google-cloud` branch** (not on PRs)
   - Builds Docker image and pushes to Artifact Registry
   - Deploys to Cloud Run with proper configuration
   - Verifies deployment health
   - **Requires GitHub secrets:**
     - `GCP_SA_KEY` - Service account key JSON
     - `ADMIN_TOKENS` - Admin authentication tokens

**Total Runtime:** 
- **Testing only** (PRs): ~3 minutes
- **Testing + Deployment** (push to branch): ~7 minutes

## Local vs CI

The CI runs the exact same tests as local development:

```bash
# Local development
./scripts/run-tests.sh              # Unit tests (same as CI job 1)
./scripts/run-emulator-tests.sh     # Emulator tests (same as CI job 2)
python backend/validate.py          # Validation (same as CI job 3)

# CI automatically runs all three on every push
```

## Viewing Results

1. Go to the [Actions tab](../../actions) in GitHub
2. Click on the latest workflow run
3. View job logs and test results
4. Download test artifacts (coverage reports) if needed

## Adding New Tests

Tests are automatically discovered by pytest. To add new tests:

1. **Unit tests:** Add to `backend/tests/test_*.py`
2. **Emulator tests:** Add to `backend/tests/emulator/test_*.py`
3. **Cloud tests:** Add to `backend/tests/test_api_integration.py` (runs manually)

The CI will automatically pick them up!

## Troubleshooting

### Emulator Tests Fail in CI

**Common issues:**
- Emulator startup timeout → Increase wait time in `scripts/start-emulators.sh`
- Docker not available → Check GitHub Actions runner compatibility
- Port conflicts → Emulators use ports 8080 (Firestore) and 4443 (GCS)

### CI is Slow

**Optimizations:**
- ✅ Python pip caching enabled
- ✅ Jobs run in parallel
- ✅ Docker image pre-pulled
- Future: Cache gcloud SDK installation

### Tests Pass Locally But Fail in CI

**Debug steps:**
1. Check Python version matches (3.12)
2. Check environment variables are set correctly
3. Review CI logs for missing dependencies
4. Run tests in a clean venv locally

## Setting Up Continuous Deployment

The CD pipeline is configured but requires GitHub secrets to be set. See the [CD Setup Guide](../docs/03-deployment/CD-SETUP.md) for detailed instructions.

**Quick setup:**

1. Create GCP service account with deployment permissions
2. Download service account key JSON
3. Add GitHub secrets:
   - `GCP_SA_KEY` - Full service account key JSON content
   - `ADMIN_TOKENS` - Comma-separated admin tokens

Once configured, every push to `replace-modal-with-google-cloud` will automatically deploy to Cloud Run after all tests pass.

## Future Enhancements

- [ ] Add test coverage reporting (coveralls, codecov)
- [x] ✅ Add deployment workflow (deploy to Cloud Run after tests pass)
- [ ] Add frontend tests (when frontend is built)
- [ ] Add performance benchmarking
- [ ] Add security scanning (dependabot, snyk)
- [ ] Migrate to Workload Identity Federation (more secure than service account keys)

