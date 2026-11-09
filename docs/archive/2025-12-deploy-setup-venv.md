# Setting Up Local Development Environment

**⚡ Quick Setup - Do this once!**

---

## 1. Create Virtual Environment

```bash
cd /Users/andrew/Projects/karaoke-gen
python3 -m venv backend/venv
```

## 2. Activate Virtual Environment

```bash
source backend/venv/bin/activate
```

You should see `(venv)` in your prompt:
```bash
(venv) ➜  karaoke-gen git:(replace-modal-with-google-cloud)
```

## 3. Install Dependencies

```bash
# Install backend dependencies
pip install -r backend/requirements.txt

# Install karaoke_gen in development mode
pip install -e .
```

## 4. Verify Installation

```bash
python3 backend/validate.py
```

**Expected output:**
```
============================================================
Backend Validation
============================================================

🔍 Checking Python syntax...
  ✅ All 27 Python files have valid syntax
🔍 Validating imports...
  ✅ backend.main
  ✅ backend.config
  ... (all modules pass)
  ✅ All 18 modules imported successfully
🔍 Validating configuration...
  ✅ Configuration loaded
🔍 Validating FastAPI application...
  ✅ FastAPI app created successfully

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

## 5. Add Shell Alias (Optional but Recommended)

Add to `~/.zshrc`:

```bash
# Karaoke backend development
alias backend='cd /Users/andrew/Projects/karaoke-gen && source backend/venv/bin/activate'
```

Reload shell:
```bash
source ~/.zshrc
```

Now you can just type:
```bash
backend
```

And you'll be in the project directory with venv activated! ✨

---

## Daily Usage

### Starting Work

```bash
backend  # or: source backend/venv/bin/activate
```

### Before Deploying

```bash
# With venv activated, full validation runs automatically
./scripts/deploy.sh

# Or run validation manually
python3 backend/validate.py
```

**This catches import errors like the one we just hit!** ✅

---

## What Gets Validated

### ✅ Full Validation (with venv)

- **Syntax errors** - Invalid Python code
- **Import errors** - Missing modules, deleted files ← **Would have caught our bug!**
- **Configuration** - Settings can be loaded
- **FastAPI app** - App can be created
- **All dependencies** - Everything imports correctly

### ⚠️ Quick Check (without venv)

- **Syntax errors** - Invalid Python code
- **File existence** - Required files present
- **Obvious issues** - Known problematic imports

**Quick check is fast but won't catch all import errors!**

---

## Why This Matters

### The Import Error We Just Had

**What happened:**
```python
# backend/api/routes/jobs.py
from backend.services.processing_service import ProcessingService  # ❌ Deleted!
```

**Without venv:**
```bash
$ ./backend/quick-check.sh
✅ All checks passed!  # ← Didn't catch it!
```

**With venv:**
```bash
$ python3 backend/validate.py
❌ backend.api.routes.jobs: No module named 'backend.services.processing_service'
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                            Would have caught it!
```

---

## Troubleshooting

### "No module named 'fastapi'"

**You're not in the venv!**

```bash
source backend/venv/bin/activate
# or
backend
```

### "No module named 'karaoke_gen'"

**Install in development mode:**

```bash
source backend/venv/bin/activate
pip install -e .
```

### Venv takes too long to activate

**Use the alias:**

```bash
echo "alias backend='cd /Users/andrew/Projects/karaoke-gen && source backend/venv/bin/activate'" >> ~/.zshrc
source ~/.zshrc
backend  # ⚡ Instant!
```

---

## Summary

| Step | Command | Frequency |
|------|---------|-----------|
| **Setup venv** | `python3 -m venv backend/venv` | Once |
| **Install deps** | `pip install -r backend/requirements.txt` | Once |
| **Install karaoke_gen** | `pip install -e .` | Once |
| **Activate venv** | `backend` or `source backend/venv/bin/activate` | Daily |
| **Validate** | `python3 backend/validate.py` | Before deploy |
| **Deploy** | `./scripts/deploy.sh` | When ready |

---

## Pro Tip: Automatic Validation

The deploy script now automatically uses full validation if venv is activated:

```bash
backend  # Activate venv
./scripts/deploy.sh
# ✅ Automatically runs full validation!
# ✅ Catches import errors!
# ✅ Safe deployment!
```

---

**TL;DR:** 
1. Run setup once: `python3 -m venv backend/venv && source backend/venv/bin/activate && pip install -r backend/requirements.txt && pip install -e .`
2. Daily: `backend` (activates venv)
3. Deploy: `./scripts/deploy.sh` (validates automatically)

**This setup would have prevented the import error!** 🎯

