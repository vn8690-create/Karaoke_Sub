# Local Validation Before Deployment

**Always run validation before deploying to catch issues early!**

---

## Quick Check (Recommended)

**No dependencies required - runs in seconds:**

```bash
cd /Users/andrew/Projects/karaoke-gen
./backend/quick-check.sh
```

**What it checks:**
- ✅ Python syntax errors
- ✅ Missing required files
- ✅ Imports of deleted modules

**Use this before every deployment!**

---

## Full Validation (Optional)

**Requires dependencies installed - more thorough:**

```bash
cd /Users/andrew/Projects/karaoke-gen

# First time setup (create virtual environment)
python3 -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt

# Run full validation
python3 backend/validate.py
```

**What it checks:**
- ✅ Python syntax errors
- ✅ Import resolution
- ✅ Configuration loading
- ✅ FastAPI app creation
- ✅ All routes defined

---

## Deploy Script (Includes Validation)

**Recommended way to deploy:**

```bash
cd /Users/andrew/Projects/karaoke-gen
./scripts/deploy.sh
```

**What it does:**
1. Runs `quick-check.sh` automatically
2. Asks for confirmation
3. Deploys to Cloud Run
4. Shows you how to test the deployment

---

## What Would Have Been Caught

### The Processing Service Import Error

**What happened:**
```python
# backend/api/routes/jobs.py
from backend.services.processing_service import ProcessingService  # ❌ File deleted!
```

**Quick check would catch:**
```bash
$ ./backend/quick-check.sh
❌ Found import of deleted processing_service
```

**Full validation would catch:**
```bash
$ python3 backend/validate.py
❌ backend.api.routes.jobs: No module named 'backend.services.processing_service'
```

---

## Development Workflow

### Before Every Deployment

```bash
# 1. Make your changes
vim backend/api/routes/jobs.py

# 2. Quick check (5 seconds)
./backend/quick-check.sh

# 3. If passed, deploy
./scripts/deploy.sh
```

### For Major Changes

```bash
# 1. Make your changes
# ...

# 2. Quick check
./backend/quick-check.sh

# 3. Full validation (if you have venv set up)
source backend/venv/bin/activate
python3 backend/validate.py

# 4. Deploy
./scripts/deploy.sh
```

---

## Setting Up Full Validation (One-Time)

```bash
cd /Users/andrew/Projects/karaoke-gen

# Create virtual environment
python3 -m venv backend/venv

# Activate it
source backend/venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Note: You'll also need karaoke_gen dependencies
# But that's already installed in your main Python env
```

**Add to your shell profile for easy activation:**

```bash
# Add to ~/.zshrc or ~/.bashrc
alias activate-backend='source /Users/andrew/Projects/karaoke-gen/backend/venv/bin/activate'
```

Then just run:
```bash
activate-backend
python3 backend/validate.py
```

---

## CI/CD Integration (Future)

When we set up GitHub Actions:

```yaml
# .github/workflows/deploy.yml
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Quick Check
        run: ./backend/quick-check.sh
      - name: Full Validation
        run: |
          pip install -r backend/requirements.txt
          python3 backend/validate.py
```

---

## Common Issues

### Issue: "ModuleNotFoundError" in full validation

**Cause:** Dependencies not installed

**Fix:**
```bash
source backend/venv/bin/activate
pip install -r backend/requirements.txt
```

### Issue: "command not found: quick-check.sh"

**Cause:** Script not executable

**Fix:**
```bash
chmod +x backend/quick-check.sh
chmod +x scripts/deploy.sh
```

### Issue: Quick check passes but deployment fails

**Cause:** Quick check doesn't test actual imports, only syntax

**Fix:** Run full validation:
```bash
source backend/venv/bin/activate
python3 backend/validate.py
```

---

## Summary

| Tool | Speed | Dependencies | Catches | Use When |
|------|-------|--------------|---------|----------|
| **quick-check.sh** | 5s | None | Syntax, structure | Every deployment |
| **validate.py** | 30s | Required | Import errors, config | Major changes |
| **deploy.sh** | 2m+ | None | Runs quick-check | Deploying |

**Best practice:** Run `quick-check.sh` before every commit!

---

## Troubleshooting

### Check fails with "py_compile" error

**The check found a syntax error!** Read the error message carefully:

```bash
  File "backend/api/routes/jobs.py", line 24
    from backend.services.processing_service import ProcessingService
                                                                     ^
SyntaxError: invalid syntax
```

### Check fails with "Missing required file"

**A critical file is missing!** Don't delete core files without updating the check:

```bash
❌ Missing required file: services/job_manager.py
```

### Deploy script asks for confirmation every time

**That's intentional!** It ensures you're deploying intentionally.

To skip (use carefully):
```bash
yes | ./scripts/deploy.sh
```

---

## Example: Complete Development Flow

```bash
# Starting work
cd /Users/andrew/Projects/karaoke-gen

# Make changes
vim backend/api/routes/jobs.py

# Quick validation
./backend/quick-check.sh
# ✅ All checks passed!

# Commit changes
git add backend/api/routes/jobs.py
git commit -m "fix: remove unused import"

# Deploy
./scripts/deploy.sh
# ✅ Validation passed!
# Deploy to Cloud Run? (y/N) y
# 🎉 Deployment complete!

# Test
export BACKEND_URL="https://karaoke-backend-ipzqd2k4yq-uc.a.run.app"
export AUTH_TOKEN=$(gcloud auth print-identity-token)
curl -H "Authorization: Bearer $AUTH_TOKEN" $BACKEND_URL/api/health
```

---

## Future Enhancements

- [ ] Add linting (pylint, flake8)
- [ ] Add type checking (mypy)
- [ ] Add unit tests to validation
- [ ] Add integration tests
- [ ] Add performance tests
- [ ] Integrate with pre-commit hooks
- [ ] Add GitHub Actions CI/CD

---

**TL;DR:** Always run `./backend/quick-check.sh` before deploying!

