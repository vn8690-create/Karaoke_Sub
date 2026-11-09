#!/bin/bash
# Admin API helper script
# Usage: ./scripts/admin_api.sh <endpoint> [method] [data]
#
# Examples:
#   ./scripts/admin_api.sh /api/jobs                          # List all jobs (admin sees all)
#   ./scripts/admin_api.sh /api/jobs?limit=10                 # List 10 jobs
#   ./scripts/admin_api.sh /api/jobs/abc123                   # Get specific job
#   ./scripts/admin_api.sh /api/jobs/abc123/retry POST        # Retry a job
#   ./scripts/admin_api.sh /api/jobs/abc123/select-instrumental POST '{"selection":"clean"}'

set -e

API_URL="${KARAOKE_API_URL:-https://api.nomadkaraoke.com}"

# Get admin token from Secret Manager if not set
if [ -z "$KARAOKE_ADMIN_TOKEN" ]; then
    KARAOKE_ADMIN_TOKEN=$(gcloud secrets versions access latest --secret=admin-tokens --project=nomadkaraoke 2>/dev/null)
fi

if [ -z "$KARAOKE_ADMIN_TOKEN" ]; then
    echo "Error: Could not get admin token. Run 'gcloud auth login' first." >&2
    exit 1
fi

ENDPOINT="${1:-/api/admin/jobs}"
METHOD="${2:-GET}"
DATA="$3"

if [ "$METHOD" = "GET" ]; then
    curl -s "${API_URL}${ENDPOINT}" \
        -H "Authorization: Bearer $KARAOKE_ADMIN_TOKEN" | jq .
elif [ -n "$DATA" ]; then
    curl -s -X "$METHOD" "${API_URL}${ENDPOINT}" \
        -H "Authorization: Bearer $KARAOKE_ADMIN_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$DATA" | jq .
else
    curl -s -X "$METHOD" "${API_URL}${ENDPOINT}" \
        -H "Authorization: Bearer $KARAOKE_ADMIN_TOKEN" | jq .
fi
