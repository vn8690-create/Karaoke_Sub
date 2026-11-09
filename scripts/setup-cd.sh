#!/bin/bash

# Setup Continuous Deployment for GitHub Actions
# This script creates a GCP service account for GitHub Actions to deploy to Cloud Run

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Setting up Continuous Deployment${NC}"
echo "================================================"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found. Please install it first.${NC}"
    exit 1
fi

# Get project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${YELLOW}⚠️  No default project set. Please enter your project ID:${NC}"
    read -p "Project ID: " PROJECT_ID
    gcloud config set project "$PROJECT_ID"
fi

echo -e "\n${GREEN}Project:${NC} $PROJECT_ID"

# Service account details
SA_NAME="github-actions-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="${HOME}/github-actions-key.json"

# Check if service account already exists
if gcloud iam service-accounts describe "$SA_EMAIL" &>/dev/null; then
    echo -e "\n${YELLOW}⚠️  Service account already exists: $SA_EMAIL${NC}"
    read -p "Do you want to create a new key for this account? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Aborted.${NC}"
        exit 1
    fi
else
    echo -e "\n${GREEN}Creating service account...${NC}"
    gcloud iam service-accounts create "$SA_NAME" \
        --display-name="GitHub Actions Deployer" \
        --description="Service account for GitHub Actions to deploy to Cloud Run" \
        --project="$PROJECT_ID"
    
    echo -e "${GREEN}✅ Service account created${NC}"
fi

# Grant necessary roles
echo -e "\n${GREEN}Granting IAM roles...${NC}"

ROLES=(
    "roles/run.admin"
    "roles/iam.serviceAccountUser"
    "roles/artifactregistry.writer"
)

for role in "${ROLES[@]}"; do
    echo "  - Granting $role"
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="$role" \
        --condition=None \
        --quiet \
        > /dev/null 2>&1
done

echo -e "${GREEN}✅ IAM roles granted${NC}"

# Create and download key
echo -e "\n${GREEN}Creating service account key...${NC}"

# Remove old key if exists
if [ -f "$KEY_FILE" ]; then
    echo -e "${YELLOW}⚠️  Removing old key file: $KEY_FILE${NC}"
    rm "$KEY_FILE"
fi

gcloud iam service-accounts keys create "$KEY_FILE" \
    --iam-account="$SA_EMAIL" \
    --quiet

echo -e "${GREEN}✅ Key created: $KEY_FILE${NC}"

# Display key info
echo -e "\n${GREEN}================================================${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${GREEN}================================================${NC}"

echo -e "\n${YELLOW}📋 Next Steps:${NC}"
echo ""
echo "1. Add the following secrets to your GitHub repository:"
echo "   https://github.com/nomadkaraoke/karaoke-gen/settings/secrets/actions"
echo ""
echo "   ${GREEN}Secret 1: GCP_SA_KEY${NC}"
echo "   Value: (copy the ENTIRE contents of the file below)"
echo ""
echo "   ${GREEN}Secret 2: ADMIN_TOKENS${NC}"
echo "   Value: (your comma-separated admin tokens)"
echo ""
echo "2. Copy the service account key JSON:"
echo ""
echo -e "${YELLOW}---BEGIN SERVICE ACCOUNT KEY---${NC}"
cat "$KEY_FILE"
echo -e "${YELLOW}---END SERVICE ACCOUNT KEY---${NC}"
echo ""
echo "3. After adding secrets, push to 'main' branch"
echo "   to trigger an automated deployment!"
echo ""
echo -e "${RED}⚠️  IMPORTANT SECURITY NOTES:${NC}"
echo "   - Keep $KEY_FILE secure (it's like a password)"
echo "   - Do NOT commit this file to git"
echo "   - Consider deleting it after copying: rm $KEY_FILE"
echo "   - The file is also copied to your clipboard (if pbcopy is available)"
echo ""

# Copy to clipboard if pbcopy is available (macOS)
if command -v pbcopy &> /dev/null; then
    cat "$KEY_FILE" | pbcopy
    echo -e "${GREEN}✅ Key copied to clipboard!${NC}"
fi

echo -e "\n${GREEN}For detailed instructions, see:${NC}"
echo "   docs/03-deployment/CD-SETUP.md"
echo ""

