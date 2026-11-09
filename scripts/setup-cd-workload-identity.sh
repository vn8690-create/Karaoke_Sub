#!/bin/bash

# Setup Continuous Deployment using Workload Identity Federation
# This is more secure than service account keys (no keys to manage!)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Setting up CD with Workload Identity Federation${NC}"
echo "================================================"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found. Please install it first.${NC}"
    exit 1
fi

# Get project details
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${YELLOW}⚠️  No default project set. Please enter your project ID:${NC}"
    read -p "Project ID: " PROJECT_ID
    gcloud config set project "$PROJECT_ID"
fi

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")

echo -e "\n${GREEN}Project ID:${NC} $PROJECT_ID"
echo -e "${GREEN}Project Number:${NC} $PROJECT_NUMBER"

# GitHub repository details
GITHUB_ORG="nomadkaraoke"
GITHUB_REPO="karaoke-gen"
GITHUB_REPO_FULL="${GITHUB_ORG}/${GITHUB_REPO}"

# Service account details
SA_NAME="github-actions-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Workload Identity Pool details
POOL_NAME="github-actions-pool"
POOL_ID="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}"
PROVIDER_NAME="github-actions-provider"
PROVIDER_ID="${POOL_ID}/providers/${PROVIDER_NAME}"

# Step 1: Create/verify service account
echo -e "\n${GREEN}Step 1: Setting up service account${NC}"
if gcloud iam service-accounts describe "$SA_EMAIL" &>/dev/null; then
    echo -e "${YELLOW}Service account already exists: $SA_EMAIL${NC}"
else
    echo "Creating service account..."
    gcloud iam service-accounts create "$SA_NAME" \
        --display-name="GitHub Actions Deployer" \
        --description="Service account for GitHub Actions CD via Workload Identity" \
        --project="$PROJECT_ID"
    echo -e "${GREEN}✅ Service account created${NC}"
fi

# Step 2: Grant IAM roles
echo -e "\n${GREEN}Step 2: Granting IAM roles${NC}"
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

# Step 3: Create Workload Identity Pool
echo -e "\n${GREEN}Step 3: Creating Workload Identity Pool${NC}"
if gcloud iam workload-identity-pools describe "$POOL_NAME" \
    --location="global" --project="$PROJECT_ID" &>/dev/null; then
    echo -e "${YELLOW}Pool already exists: $POOL_NAME${NC}"
else
    echo "Creating pool..."
    gcloud iam workload-identity-pools create "$POOL_NAME" \
        --location="global" \
        --display-name="GitHub Actions Pool" \
        --description="Workload Identity Pool for GitHub Actions" \
        --project="$PROJECT_ID"
    echo -e "${GREEN}✅ Pool created${NC}"
fi

# Step 4: Create Workload Identity Provider
echo -e "\n${GREEN}Step 4: Creating Workload Identity Provider${NC}"
if gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" \
    --workload-identity-pool="$POOL_NAME" \
    --location="global" --project="$PROJECT_ID" &>/dev/null; then
    echo -e "${YELLOW}Provider already exists: $PROVIDER_NAME${NC}"
else
    echo "Creating provider..."
    gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_NAME" \
        --workload-identity-pool="$POOL_NAME" \
        --location="global" \
        --issuer-uri="https://token.actions.githubusercontent.com" \
        --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
        --attribute-condition="assertion.repository_owner == '${GITHUB_ORG}'" \
        --project="$PROJECT_ID"
    echo -e "${GREEN}✅ Provider created${NC}"
fi

# Step 5: Allow GitHub Actions to impersonate the service account
echo -e "\n${GREEN}Step 5: Binding service account to GitHub repo${NC}"
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
    --project="$PROJECT_ID" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/${GITHUB_REPO_FULL}"

echo -e "${GREEN}✅ Service account binding complete${NC}"

# Step 6: Get Workload Identity Provider resource name
WORKLOAD_IDENTITY_PROVIDER=$(gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" \
    --workload-identity-pool="$POOL_NAME" \
    --location="global" \
    --project="$PROJECT_ID" \
    --format="value(name)")

# Display results
echo -e "\n${GREEN}================================================${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${GREEN}================================================${NC}"

echo -e "\n${YELLOW}📋 GitHub Secrets to Add:${NC}"
echo ""
echo "Go to: https://github.com/${GITHUB_REPO_FULL}/settings/secrets/actions"
echo ""
echo "1. Add secret: ${GREEN}GCP_WORKLOAD_IDENTITY_PROVIDER${NC}"
echo "   Value:"
echo "   ${WORKLOAD_IDENTITY_PROVIDER}"
echo ""
echo "2. Add secret: ${GREEN}GCP_SERVICE_ACCOUNT${NC}"
echo "   Value:"
echo "   ${SA_EMAIL}"
echo ""
echo "3. Add secret: ${GREEN}ADMIN_TOKENS${NC}"
echo "   Value:"
echo "   <your-comma-separated-admin-tokens>"
echo ""

# Copy to clipboard if available
if command -v pbcopy &> /dev/null; then
    echo -e "${GREEN}Workload Identity Provider (copied to clipboard):${NC}"
    echo "$WORKLOAD_IDENTITY_PROVIDER" | pbcopy
    echo "$WORKLOAD_IDENTITY_PROVIDER"
    echo ""
    echo -e "${YELLOW}Service Account Email:${NC}"
    echo "$SA_EMAIL"
else
    echo -e "${GREEN}Workload Identity Provider:${NC}"
    echo "$WORKLOAD_IDENTITY_PROVIDER"
    echo ""
    echo -e "${YELLOW}Service Account Email:${NC}"
    echo "$SA_EMAIL"
fi

echo ""
echo -e "${GREEN}✅ Benefits of Workload Identity Federation:${NC}"
echo "   - No service account keys to manage"
echo "   - Automatic credential rotation"
echo "   - Better security posture"
echo "   - No key expiration issues"
echo ""
echo -e "${YELLOW}Next: Update the GitHub Actions workflow to use these values${NC}"
echo ""

