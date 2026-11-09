# Local Development Environment Setup - Complete! ✅

**Date:** 2025-12-01  
**Status:** Fully working with validation

---

## Summary

Successfully set up local Python virtual environment with:
- ✅ **Python 3.12** (3.13+ has pydantic compatibility issues)
- ✅ **Relaxed dependency versions** (allows minor/patch updates)
- ✅ **Full validation** working (catches import errors!)
- ✅ **All 18 backend modules** importing correctly
- ✅ **FastAPI app** creating successfully with 27 endpoints

---

## Quick Setup (Copy-Paste)

```bash
cd /Users/andrew/Projects/karaoke-gen

# Create venv with Python 3.12 (NOT 3.13!)
python3.12 -m venv backend/venv

# Activate
source backend/venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r backend/requirements.txt
pip install -e .
pip install -e lyrics_transcriber_local/
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

# Test validation
python3 backend/validate.py
# ✅ Should pass all checks!
```

---

## What We Fixed

### Issue 1: Python 3.13 Incompatibility

**Problem:**
```
error: Building wheel for pydantic-core (pyproject.toml) did not run successfully
TypeError: ForwardRef._evaluate() missing 1 required keyword-only argument: 'recursive_guard'
```

**Solution:** Use Python 3.12 instead
```bash
python3.12 -m venv backend/venv  # ← Forces Python 3.12
```

### Issue 2: Pinned Dependency Versions

**Problem:** `requirements.txt` had exact versions (`==`) preventing updates

**Solution:** Relaxed to allow minor/patch updates:
```
fastapi>=0.104.0,<1.0.0       # Was: ==0.104.1
pydantic>=2.5.0,<3.0.0         # Was: ==2.5.0
google-cloud-firestore>=2.14.0,<3.0.0  # Was: ==2.14.0
```

**Result:** Latest compatible versions installed:
- `fastapi` 0.104.1 → 0.123.0
- `pydantic` 2.5.0 → 2.12.5
- `google-cloud-firestore` 2.14.0 → 2.21.0
- `uvicorn` 0.24.0 → 0.38.0

### Issue 3: Missing httpx

**Problem:** `httpx` was used but not in `requirements.txt`

**Solution:** Added `httpx>=0.25.0,<1.0.0` to requirements

### Issue 4: Validation Checking venv Files

**Problem:** Validation tried to check Python files in `venv/` causing errors

**Solution:** Updated `validate.py` to skip `venv/` and `.venv/` directories

---

## Current Dependencies

### Backend (`backend/requirements.txt`)

```
fastapi>=0.104.0,<1.0.0
uvicorn[standard]>=0.24.0,<1.0.0
pydantic>=2.5.0,<3.0.0
pydantic-settings>=2.1.0,<3.0.0
python-multipart>=0.0.6,<1.0.0
httpx>=0.25.0,<1.0.0
google-cloud-firestore>=2.14.0,<3.0.0
google-cloud-storage>=2.14.0,<3.0.0
google-cloud-secret-manager>=2.18.0,<3.0.0
python-dotenv>=1.0.0,<2.0.0
```

### Additional (installed separately)

```bash
pip install -e .                          # karaoke_gen
pip install -e lyrics_transcriber_local/  # lyrics transcriber
pip install google-api-python-client      # YouTube API
```

---

## Validation Results

```bash
$ python3 backend/validate.py

============================================================
Backend Validation
============================================================

🔍 Checking Python syntax...
  ✅ All 20048 Python files have valid syntax

🔍 Validating imports...
  ✅ backend.main
  ✅ backend.config
  ✅ backend.api.routes.health
  ✅ backend.api.routes.jobs
  ✅ backend.api.routes.internal
  ✅ backend.api.routes.file_upload
  ✅ backend.api.dependencies
  ✅ backend.services.job_manager
  ✅ backend.services.storage_service
  ✅ backend.services.firestore_service
  ✅ backend.services.worker_service
  ✅ backend.services.auth_service
  ✅ backend.workers.audio_worker
  ✅ backend.workers.lyrics_worker
  ✅ backend.workers.screens_worker
  ✅ backend.workers.video_worker
  ✅ backend.models.job
  ✅ backend.models.requests

✅ All 18 modules imported successfully

🔍 Validating configuration...
  ✅ Configuration loaded
     Environment: development
     Project: Not set (OK for local)

🔍 Validating FastAPI application...
  ✅ FastAPI app created successfully
     Title: Karaoke Generator API
     Version: 1.0.0
     Routes: 27 endpoints

============================================================
Summary
============================================================
✅ PASS   Syntax Check
✅ PASS   Import Check
✅ PASS   Config Check
✅ PASS   FastAPI Check

🎉 All validations passed! Safe to deploy.
```

---

## Shell Alias (Recommended)

Add to `~/.zshrc`:

```bash
alias backend='cd /Users/andrew/Projects/karaoke-gen && source backend/venv/bin/activate'
```

Then just:
```bash
backend
python3 backend/validate.py
```

---

## Development Workflow

### Daily Usage

```bash
# 1. Activate venv
backend  # or: source backend/venv/bin/activate

# 2. Make changes
vim backend/api/routes/jobs.py

# 3. Validate (catches import errors!)
python3 backend/validate.py

# 4. Deploy
./scripts/deploy.sh
```

### The deploy script now:

1. **Checks if venv is activated**
2. **Runs full validation** if venv active (catches import errors!)
3. **Falls back to quick check** if no venv (syntax only)
4. **Asks for confirmation**
5. **Deploys to Cloud Run**

---

## What This Would Have Caught

### The processing_service Import Error

**What happened:**
```python
# backend/api/routes/jobs.py
from backend.services.processing_service import ProcessingService  # ❌ Deleted!
```

**Without venv:**
```bash
$ ./backend/quick-check.sh
✅ All checks passed!  # ← Missed it!
```

**With venv:**
```bash
$ python3 backend/validate.py
❌ backend.api.routes.jobs: No module named 'backend.services.processing_service'
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                            CAUGHT IT! ✅
```

---

## Build Status

**Latest build:** SUCCESS ✅  
**Build time:** 2m 24s (Docker caching working!)  
**Image:** `us-central1-docker.pkg.dev/nomadkaraoke/karaoke-repo/karaoke-backend:01bf8976-cd3e-410c-a46e-50f00f294d47`

---

## Next Steps

### 1. Test the Backend

```bash
export BACKEND_URL="https://karaoke-backend-ipzqd2k4yq-uc.a.run.app"
export AUTH_TOKEN=$(gcloud auth print-identity-token)

curl -H "Authorization: Bearer $AUTH_TOKEN" $BACKEND_URL/api/health
```

### 2. (Optional) Recreate Custom Domain

```bash
cd infrastructure
pulumi up --yes
# Wait 15-30 minutes for SSL certificate
```

### 3. Set Up Authentication

```bash
# Set admin token
gcloud run services update karaoke-backend \
  --region us-central1 \
  --set-env-vars ADMIN_TOKENS="nomad"

# Test with token
curl -H "Authorization: Bearer nomad" \
  $BACKEND_URL/api/health
```

---

## Troubleshooting

### "ModuleNotFoundError" when validating

**Make sure venv is activated:**
```bash
source backend/venv/bin/activate
```

### Still getting Python 3.13 errors

**Recreate venv with Python 3.12:**
```bash
rm -rf backend/venv
python3.12 -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt
pip install -e . -e lyrics_transcriber_local/
```

### Validation passes but deployment fails

**Check Docker caching:**
```bash
# Build should be fast (~2 minutes)
# If slow, check cloudbuild.yaml
```

---

## Summary

| Item | Status |
|------|--------|
| **Python 3.12 venv** | ✅ Set up |
| **Relaxed dependencies** | ✅ Updated |
| **All modules importing** | ✅ Working |
| **Validation passing** | ✅ All checks |
| **Deploy script updated** | ✅ Auto-validates |
| **Backend deployed** | ✅ 2m 24s build |
| **Ready to test** | ✅ Yes! |

---

**Key Takeaway:** With venv + validation, the import error would have been caught instantly! 🎯

