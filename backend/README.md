# Backend Development Setup

## One-Time Setup

### 1. Create Virtual Environment

```bash
cd /Users/andrew/Projects/karaoke-gen
python3 -m venv backend/venv
```

### 2. Activate Virtual Environment

```bash
source backend/venv/bin/activate
```

### 3. Install Dependencies

**IMPORTANT:** Use Python 3.12 (not 3.13/3.14 - pydantic has compatibility issues)

```bash
# Backend dependencies
pip install -r backend/requirements.txt

# Install karaoke_gen in development mode
pip install -e .

# Install lyrics_transcriber submodule
pip install -e lyrics_transcriber_local/

# Install Google API client (for YouTube upload)
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 4. Add Shell Alias (Optional)

Add to `~/.zshrc`:

```bash
alias backend='cd /Users/andrew/Projects/karaoke-gen && source backend/venv/bin/activate'
```

Then you can just run:
```bash
backend
# Now you're in the project directory with venv activated!
```

---

## Daily Workflow

### Before Making Changes

```bash
# Activate venv
source backend/venv/bin/activate

# Or if you set up the alias:
backend
```

### After Making Changes

```bash
# 1. Run full validation (catches import errors!)
python3 backend/validate.py

# 2. If validation passes, deploy
./scripts/deploy.sh
```

---

## Validation Options

### Full Validation (Recommended - Requires venv)

```bash
source backend/venv/bin/activate
python3 backend/validate.py
```

**Catches:**
- ✅ Syntax errors
- ✅ **Import errors** (like the processing_service issue!)
- ✅ Configuration issues
- ✅ FastAPI app creation problems
- ✅ Missing dependencies

**This would have caught the ModuleNotFoundError!**

### Quick Check (No venv needed)

```bash
./backend/quick-check.sh
```

**Catches:**
- ✅ Syntax errors
- ✅ Missing files
- ✅ Some obvious import issues

**Good for quick checks, but won't catch all import errors**

---

## Example: Complete Development Session

```bash
# 1. Activate environment
backend  # or: source backend/venv/bin/activate

# 2. Make your changes
vim backend/api/routes/jobs.py

# 3. Validate (catches import errors!)
python3 backend/validate.py
# ✅ All validations passed!

# 4. Deploy
./scripts/deploy.sh

# 5. Test
export BACKEND_URL="https://karaoke-backend-ipzqd2k4yq-uc.a.run.app"
export AUTH_TOKEN=$(gcloud auth print-identity-token)
curl -H "Authorization: Bearer $AUTH_TOKEN" $BACKEND_URL/api/health
```

---

## What About karaoke_gen Imports?

The backend imports from `karaoke_gen` (the CLI package):

```python
from karaoke_gen.karaoke_gen import KaraokePrep
from karaoke_gen.audio_processor import AudioProcessor
```

**Options:**

### Option 1: Install in development mode (Recommended)

```bash
source backend/venv/bin/activate
pip install -e .
```

This makes `karaoke_gen` available in the venv without copying files.

### Option 2: Use system Python

Your system Python already has `karaoke_gen` installed, so validation will work even if the venv doesn't have it (Python will fall back to system packages).

---

## Running the Backend Locally

```bash
# Activate venv
source backend/venv/bin/activate

# Set required environment variables
export GOOGLE_CLOUD_PROJECT="nomadkaraoke"
export GCS_BUCKET_NAME="karaoke-gen-storage-nomadkaraoke"

# Optional: Point to local credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# Run the server
cd backend
uvicorn main:app --reload --port 8080
```

Visit: http://localhost:8080/api/health

---

## Troubleshooting

### "No module named 'fastapi'"

**Fix:**
```bash
source backend/venv/bin/activate
pip install -r backend/requirements.txt
```

### "No module named 'karaoke_gen'"

**Fix:**
```bash
source backend/venv/bin/activate
cd /Users/andrew/Projects/karaoke-gen
pip install -e .
```

### Validation passes locally but fails in Cloud Run

**Check:**
1. Is `requirements.txt` up to date?
2. Did you add a new dependency without adding it to `requirements.txt`?
3. Run: `pip freeze | grep <package-name>`

---

## Updating Dependencies

When you add new packages:

```bash
# 1. Install in venv
source backend/venv/bin/activate
pip install new-package

# 2. Update requirements.txt
pip freeze > backend/requirements.txt

# 3. Or manually add just the new package:
echo "new-package==1.2.3" >> backend/requirements.txt

# 4. Validate
python3 backend/validate.py

# 5. Deploy
./scripts/deploy.sh
```

---

## Summary

**Best practice workflow:**

1. **One-time setup:** Create venv and install dependencies
2. **Daily:** Activate venv when working on backend
3. **Before deploy:** Run `python3 backend/validate.py` (catches import errors!)
4. **Deploy:** Use `./scripts/deploy.sh`

**The import error would have been caught if you ran validation in a venv!** ✅
