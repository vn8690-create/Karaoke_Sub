# Self-Hosted GitHub Actions Runner on GCP

**Date**: 2025-12-28
**Status**: Deployed and operational

## Problem

GitHub-hosted runners have ~14GB disk space. CI jobs were failing with "No space left on device" during:
- Docker builds (multi-stage, large dependencies)
- Emulator tests (Docker + Java + Firestore/GCS emulators)
- Package builds with poetry

Workarounds like `jlumbroso/free-disk-space` action helped but weren't reliable.

## Solution

Deployed a self-hosted runner on GCP with 200GB SSD via Pulumi IaC.

### Infrastructure Added

| Resource | Purpose |
|----------|---------|
| `github-runner` VM | e2-standard-4, 200GB SSD, Debian 12 |
| `github-runner` service account | Minimal permissions for runner |
| `github-runner-pat` secret | PAT for runner registration |
| IAM bindings | Artifact Registry reader, Secret Manager accessor, logging |

### Jobs Moved to Self-Hosted

- `package-build-test`
- `backend-unit-tests`
- `backend-emulator-tests`
- `deploy-backend`

These use `runs-on: [self-hosted, linux, gcp]` with labels.

## Issues Encountered

### 1. GPG tty errors in startup script

**Problem**: `gpg --dearmor` failed with "cannot open /dev/tty" in non-interactive startup.

**Fix**: Add `--batch` flag to all GPG commands.

### 2. setup-python can't find Python 3.13 on Debian 12

**Problem**: `actions/setup-python@v5` couldn't find pre-built Python 3.13 for Debian 12 on self-hosted runners.

**Fix**:
1. Install Python 3.13 via pyenv on the runner
2. Copy to tool cache: `_work/_tool/Python/3.13.0/x64/`
3. Create marker file: `x64.complete`

### 3. Java 21 not in Debian repos

**Problem**: `openjdk-21-jdk` not available in Debian 12 stable.

**Fix**: Use Temurin (Adoptium) repository directly.

## Key Files

- `infrastructure/__main__.py` - Runner VM and IAM setup
- `infrastructure/README.md` - Setup instructions
- `.github/workflows/ci.yml` - Jobs using self-hosted runner

## Lessons for Future

1. **Self-hosted runners need explicit tool setup** - Unlike GitHub-hosted, tools aren't pre-installed in expected locations
2. **setup-python tool cache location**: `$RUNNER_DIR/_work/_tool/Python/<version>/x64/`
3. **GPG in scripts**: Always use `--batch` for non-interactive execution
4. **Debian vs Ubuntu**: Many GitHub Actions assume Ubuntu; PPAs don't work on Debian

## Cost

~$50/month for e2-standard-4 running 24/7 (covered by GCP free credits).

## PRs

- #95: Initial self-hosted runner setup
- #97: Make startup script reproducible (pyenv, tool cache, GPG fixes)
