#!/bin/bash
# Debug a specific karaoke job
# Usage: ./scripts/debug-job.sh <job_id>
#
# Requires KARAOKE_GEN_AUTH_TOKEN env var to be set to a valid admin token.
# Get your token from the GCP Secret Manager or .env file.

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <job_id>"
    echo "Example: $0 e168cb20"
    echo ""
    echo "Requires KARAOKE_GEN_AUTH_TOKEN environment variable (admin token)."
    echo "Set it with: export KARAOKE_GEN_AUTH_TOKEN=your-admin-token"
    exit 1
fi

JOB_ID="$1"
BACKEND_URL="${BACKEND_URL:-https://api.nomadkaraoke.com}"
AUTH_TOKEN="${KARAOKE_GEN_AUTH_TOKEN}"

if [ -z "$AUTH_TOKEN" ]; then
    echo "Error: KARAOKE_GEN_AUTH_TOKEN environment variable is not set."
    echo ""
    echo "Set it with: export KARAOKE_GEN_AUTH_TOKEN=your-admin-token"
    echo "You can find admin tokens in GCP Secret Manager or your .env file."
    exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "Debugging Job: $JOB_ID"
echo "========================================"
echo ""

# 1. Get job status
echo -e "${BLUE}1. Job Status:${NC}"
echo "---"

# Capture both response body and HTTP status code
HTTP_RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $AUTH_TOKEN" "$BACKEND_URL/api/jobs/$JOB_ID")
HTTP_STATUS=$(echo "$HTTP_RESPONSE" | tail -n 1)
JOB_STATUS=$(echo "$HTTP_RESPONSE" | sed '$d')

# Check HTTP status
if [ "$HTTP_STATUS" != "200" ]; then
    echo -e "${RED}API Error (HTTP $HTTP_STATUS):${NC}"
    echo "$JOB_STATUS" | jq -r '.detail // .' 2>/dev/null || echo "$JOB_STATUS"
    echo ""
    echo -e "${YELLOW}Possible causes:${NC}"
    case "$HTTP_STATUS" in
        401)
            echo "  - Invalid or expired AUTH_TOKEN"
            echo "  - Token doesn't have access to this job"
            ;;
        403)
            echo "  - Token lacks permission to view this job"
            echo "  - Job belongs to a different user (need admin token)"
            ;;
        404)
            echo "  - Job ID '$JOB_ID' not found"
            echo "  - Job may have been deleted"
            ;;
        *)
            echo "  - Server error or network issue"
            ;;
    esac
    exit 1
fi

echo "$JOB_STATUS" | jq '{status, progress, error_message, error_details, timeline: (.timeline | length)}'
echo ""

# 2. Get full timeline
echo -e "${BLUE}2. Timeline (last 10 events):${NC}"
echo "---"
TIMELINE_COUNT=$(echo "$JOB_STATUS" | jq '.timeline | length')
if [ "$TIMELINE_COUNT" = "0" ] || [ "$TIMELINE_COUNT" = "null" ]; then
    echo "(no timeline events)"
else
    echo "$JOB_STATUS" | jq -r '.timeline[-10:][] | "\(.timestamp) [\(.status)] \(.message // "(no message)")"'
fi
echo ""

# 2b. Get worker logs (more accurate real-time status)
echo -e "${BLUE}2b. Worker Logs (last 10):${NC}"
echo "---"
LOGS_RESPONSE=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$BACKEND_URL/api/jobs/$JOB_ID/logs?since_index=0")
LOGS_STATUS=$(echo "$LOGS_RESPONSE" | jq -r '.total_logs // 0')
if [ "$LOGS_STATUS" = "0" ] || [ "$LOGS_STATUS" = "null" ]; then
    echo "(no worker logs)"
else
    echo "Total logs: $LOGS_STATUS"
    echo "$LOGS_RESPONSE" | jq -r '.logs[-10:][] | "\(.timestamp) [\(.worker)] \(.level): \(.message)"' 2>/dev/null || echo "(error parsing logs)"
fi
echo ""

# 3. Check if files exist in GCS
echo -e "${BLUE}3. GCS Files:${NC}"
echo "---"
INPUT_PATH=$(echo "$JOB_STATUS" | jq -r '.input_media_gcs_path // empty')
if [ -n "$INPUT_PATH" ]; then
    echo "Input file: gs://karaoke-gen-storage-nomadkaraoke/$INPUT_PATH"
    if gsutil ls "gs://karaoke-gen-storage-nomadkaraoke/$INPUT_PATH" 2>/dev/null; then
        echo -e "${GREEN}✓ Input file exists${NC}"
        gsutil du -h "gs://karaoke-gen-storage-nomadkaraoke/$INPUT_PATH"
    else
        echo -e "${RED}✗ Input file NOT found${NC}"
    fi
else
    echo -e "${YELLOW}⚠ No input_media_gcs_path in job${NC}"
fi
echo ""

# 4. Check Cloud Run logs
echo -e "${BLUE}4. Cloud Run Logs (last 20 relevant):${NC}"
echo "---"
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend AND textPayload=~\"$JOB_ID\"" \
    --limit=20 \
    --format="value(timestamp,severity,textPayload)" 2>/dev/null | \
    while IFS=$'\t' read -r timestamp severity message; do
        case "$severity" in
            ERROR)
                echo -e "${RED}[$timestamp] $severity: $message${NC}"
                ;;
            WARNING)
                echo -e "${YELLOW}[$timestamp] $severity: $message${NC}"
                ;;
            *)
                echo "[$timestamp] $severity: $message"
                ;;
        esac
    done
echo ""

# 5. Job Details
echo -e "${BLUE}5. Job Details:${NC}"
echo "---"
echo "$JOB_STATUS" | jq '{
  artist,
  title,
  user_email,
  created_at,
  updated_at,
  prep_only,
  finalise_only
}'
echo ""

# 6. File URLs
echo -e "${BLUE}6. File URLs:${NC}"
echo "---"
echo "$JOB_STATUS" | jq '.file_urls // {}' | head -50
echo ""

# 7. Summary
echo "========================================"
echo -e "${BLUE}Summary:${NC}"
ARTIST=$(echo "$JOB_STATUS" | jq -r '.artist // "Unknown"')
TITLE=$(echo "$JOB_STATUS" | jq -r '.title // "Unknown"')
STATUS=$(echo "$JOB_STATUS" | jq -r '.status')
ERROR=$(echo "$JOB_STATUS" | jq -r '.error_message // "None"')
PROGRESS=$(echo "$JOB_STATUS" | jq -r '.progress // 0')

echo "Track: $ARTIST - $TITLE"

# Compute enhanced status from state_data (like frontend does)
# The backend status can be stale during parallel processing
AUDIO_STAGE=$(echo "$JOB_STATUS" | jq -r '.state_data.audio_progress.stage // empty')
LYRICS_STAGE=$(echo "$JOB_STATUS" | jq -r '.state_data.lyrics_progress.stage // empty')
AUDIO_COMPLETE=$(echo "$JOB_STATUS" | jq -r '.state_data.audio_complete // false')
LYRICS_COMPLETE=$(echo "$JOB_STATUS" | jq -r '.state_data.lyrics_complete // false')

# Determine effective status (mirrors frontend job-status.ts logic)
EFFECTIVE_STATUS="$STATUS"
STEP_INFO=""

if [ "$STATUS" = "downloading" ]; then
    # Check if parallel workers are active
    if [ -n "$AUDIO_STAGE" ] || [ -n "$LYRICS_STAGE" ]; then
        EFFECTIVE_STATUS="processing"
        # Build status string
        PARTS=""
        if [ "$AUDIO_COMPLETE" != "true" ] && [ -n "$AUDIO_STAGE" ]; then
            case "$AUDIO_STAGE" in
                "separating_stage1") PARTS="Audio 1/2" ;;
                "separating_stage2") PARTS="Audio 2/2" ;;
                "audio_complete") PARTS="Audio done" ;;
                *) PARTS="Audio" ;;
            esac
        fi
        if [ "$LYRICS_COMPLETE" != "true" ] && [ -n "$LYRICS_STAGE" ]; then
            case "$LYRICS_STAGE" in
                "transcribing") LYRICS_PART="Transcribing" ;;
                "correcting") LYRICS_PART="Correcting" ;;
                "lyrics_complete") LYRICS_PART="Lyrics done" ;;
                *) LYRICS_PART="Lyrics" ;;
            esac
            if [ -n "$PARTS" ]; then
                PARTS="$PARTS + $LYRICS_PART"
            else
                PARTS="$LYRICS_PART"
            fi
        fi
        if [ -n "$PARTS" ]; then
            STEP_INFO="[4/10] $PARTS"
        fi
    fi
fi

# Map status to step (simplified version of frontend logic)
if [ -z "$STEP_INFO" ]; then
    case "$STATUS" in
        "pending") STEP_INFO="[1/10] Setting up" ;;
        "searching_audio") STEP_INFO="[2/10] Searching for audio" ;;
        "awaiting_audio_selection") STEP_INFO="[2/10] Select audio source" ;;
        "downloading_audio"|"downloading") STEP_INFO="[3/10] Downloading" ;;
        "separating_stage1") STEP_INFO="[4/10] Separating audio (1/2)" ;;
        "separating_stage2") STEP_INFO="[4/10] Separating audio (2/2)" ;;
        "transcribing") STEP_INFO="[4/10] Transcribing lyrics" ;;
        "correcting") STEP_INFO="[4/10] Correcting lyrics" ;;
        "generating_screens") STEP_INFO="[5/10] Generating screens" ;;
        "awaiting_review"|"in_review") STEP_INFO="[6/10] Review lyrics" ;;
        "rendering_video") STEP_INFO="[7/10] Rendering video" ;;
        "awaiting_instrumental_selection") STEP_INFO="[8/10] Select instrumental" ;;
        "generating_video"|"encoding"|"packaging") STEP_INFO="[9/10] Encoding" ;;
        "complete"|"prep_complete") STEP_INFO="[10/10] Complete" ;;
        *) STEP_INFO="$STATUS" ;;
    esac
fi

echo "Status: $STEP_INFO"
if [ "$STATUS" != "$EFFECTIVE_STATUS" ] && [ "$EFFECTIVE_STATUS" = "processing" ]; then
    echo -e "${YELLOW}(Backend status '$STATUS' is stale - workers are actively processing)${NC}"
fi

case "$STATUS" in
    "complete")
        echo -e "${GREEN}✓ Job completed successfully${NC}"
        ;;
    "prep_complete")
        echo -e "${GREEN}✓ Prep completed (ready for finalization)${NC}"
        ;;
    "failed")
        echo -e "${RED}✗ Job failed: $ERROR${NC}"
        # Show error details if available
        ERROR_DETAILS=$(echo "$JOB_STATUS" | jq -r '.error_details // empty')
        if [ -n "$ERROR_DETAILS" ] && [ "$ERROR_DETAILS" != "null" ]; then
            echo -e "${RED}Error details:${NC}"
            echo "$JOB_STATUS" | jq '.error_details'
        fi
        ;;
    "awaiting_review"|"awaiting_instrumental_selection"|"awaiting_audio_selection")
        echo -e "${YELLOW}⏸️  Waiting for user action${NC}"
        ;;
    "cancelled")
        echo -e "${YELLOW}🚫 Job cancelled${NC}"
        ;;
    *)
        if [ "$EFFECTIVE_STATUS" = "processing" ]; then
            echo -e "${BLUE}⏳ Workers actively processing${NC}"
        else
            echo -e "${YELLOW}⏳ Job in progress${NC}"
        fi
        ;;
esac
echo "========================================"

