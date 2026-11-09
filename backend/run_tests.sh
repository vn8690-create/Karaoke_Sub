#!/bin/bash
# Backend Test Runner
# Runs integration tests against the deployed Cloud Run service

set -e

echo "🧪 Backend Integration Test Suite"
echo "=================================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install Google Cloud SDK."
    exit 1
fi

if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Installing test dependencies..."
    pip install -r tests/requirements.txt
fi

# Verify authentication
echo "Verifying authentication..."
if ! gcloud auth print-identity-token &> /dev/null; then
    echo "❌ Not authenticated with gcloud. Run: gcloud auth login"
    exit 1
fi

echo "✅ Prerequisites met"
echo ""

# Run tests
echo "Running integration tests..."
echo ""

# Run fast tests (no slow marker)
echo "📝 Running fast tests..."
pytest tests/test_api_integration.py -v -m "not slow" --tb=short

echo ""
echo "✅ Fast tests complete!"
echo ""

# Ask if user wants to run slow tests
read -p "Run slow/integration tests? These test actual job processing (5-10 min). [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🐌 Running slow integration tests..."
    pytest tests/test_api_integration.py -v -m "slow" --tb=short
    echo ""
    echo "✅ All tests complete!"
else
    echo "⏭️  Skipping slow tests"
fi

echo ""
echo "=================================="
echo "Test run complete! 🎉"

