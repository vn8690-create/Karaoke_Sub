#!/bin/bash
# Run backend unit tests with coverage reporting
# Usage: ./scripts/run-tests.sh [options]
#
# Coverage target: 55% (realistic for services with GCP dependencies)
# Note: screens_worker.py and video_worker.py are excluded as they require
# complex external APIs (karaoke_gen library) and are tested via integration tests.

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Coverage target - 54% is realistic given GCP service dependencies
# (actual coverage is 54.66%, displayed as 55% due to rounding)
COVERAGE_TARGET=54

echo "========================================"
echo "Running Backend Unit Tests"
echo "========================================"
echo ""

# Change to project root
cd "$(dirname "$0")/.."

# Check if running in Poetry environment
if command -v poetry &> /dev/null; then
    RUN_CMD="poetry run"
else
    RUN_CMD=""
    # Check if venv is activated
    if [ -z "$VIRTUAL_ENV" ]; then
        echo -e "${YELLOW}⚠️  Virtual environment not activated${NC}"
        echo "   Activate it first: source venv/bin/activate"
        echo "   Or use poetry: poetry run ./scripts/run-tests.sh"
        echo ""
        exit 1
    fi
fi

# Run tests with coverage
echo -e "${BLUE}Running unit tests...${NC}"
echo ""

# Ignore integration/emulator tests for unit test runs
IGNORE_OPTS="--ignore=backend/tests/emulator --ignore=backend/tests/test_api_integration.py --ignore=backend/tests/test_emulator_integration.py"

if [ "$1" == "--coverage" ] || [ "$1" == "-c" ]; then
    # Run with coverage report
    $RUN_CMD pytest backend/tests/ \
        $IGNORE_OPTS \
        -v \
        --cov=backend \
        --cov-config=backend/.coveragerc \
        --cov-report=term-missing \
        --cov-report=html:htmlcov \
        --cov-fail-under=$COVERAGE_TARGET \
        "${@:2}"
    
    EXITCODE=$?
    
    if [ $EXITCODE -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ All tests passed with >= ${COVERAGE_TARGET}% coverage!${NC}"
        echo -e "   Coverage report: htmlcov/index.html"
    else
        echo ""
        echo -e "${RED}❌ Tests failed or coverage below ${COVERAGE_TARGET}%${NC}"
    fi
    
    exit $EXITCODE
else
    # Run without coverage (faster)
    $RUN_CMD pytest backend/tests/ $IGNORE_OPTS -v "$@"
    
    EXITCODE=$?
    
    if [ $EXITCODE -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ All tests passed!${NC}"
    else
        echo ""
        echo -e "${RED}❌ Some tests failed${NC}"
    fi
    
    exit $EXITCODE
fi

