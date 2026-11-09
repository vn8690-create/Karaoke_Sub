#!/bin/bash
# Quick syntax and structure check (no dependencies required)
# Run this before every deployment!

set -e

echo "🔍 Quick Backend Check (no dependencies required)"
echo "=================================================="
echo ""

# Change to backend directory
cd "$(dirname "$0")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

ERRORS=0

# Check 1: Python syntax
echo "1. Checking Python syntax..."
for file in $(find . -name "*.py" -not -path "./__pycache__/*" -not -path "./venv/*"); do
    if ! python3 -m py_compile "$file" 2>/dev/null; then
        echo -e "  ${RED}❌ Syntax error in $file${NC}"
        python3 -m py_compile "$file"
        ERRORS=$((ERRORS+1))
    fi
done

if [ $ERRORS -eq 0 ]; then
    echo -e "  ${GREEN}✅ All Python files have valid syntax${NC}"
fi

# Check 2: No missing imports (basic check)
echo ""
echo "2. Checking for obvious import issues..."

# Check that we don't import deleted modules
if grep -r "from backend.services.processing_service import" --include="*.py" . 2>/dev/null; then
    echo -e "  ${RED}❌ Found import of deleted processing_service${NC}"
    ERRORS=$((ERRORS+1))
else
    echo -e "  ${GREEN}✅ No imports of deleted modules${NC}"
fi

# Check 3: Required files exist
echo ""
echo "3. Checking required files exist..."
REQUIRED_FILES=(
    "main.py"
    "config.py"
    "requirements.txt"
    "Dockerfile"
    "api/routes/health.py"
    "api/routes/jobs.py"
    "api/routes/internal.py"
    "api/routes/file_upload.py"
    "services/job_manager.py"
    "services/firestore_service.py"
    "services/storage_service.py"
    "services/worker_service.py"
    "services/auth_service.py"
    "workers/audio_worker.py"
    "workers/lyrics_worker.py"
    "workers/screens_worker.py"
    "workers/video_worker.py"
    "models/job.py"
    "models/requests.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "  ${RED}❌ Missing required file: $file${NC}"
        ERRORS=$((ERRORS+1))
    fi
done

if [ $ERRORS -eq 0 ]; then
    echo -e "  ${GREEN}✅ All required files exist${NC}"
fi

# Summary
echo ""
echo "=================================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed! Safe to deploy.${NC}"
    exit 0
else
    echo -e "${RED}❌ $ERRORS error(s) found. Fix before deploying!${NC}"
    exit 1
fi

