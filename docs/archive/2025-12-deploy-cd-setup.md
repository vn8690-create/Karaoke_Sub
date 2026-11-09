# Continuous Deployment (CD) Setup Guide

This guide explains how to set up automated deployment from GitHub Actions to Google Cloud Run.

## Overview

The CD pipeline is configured to:
1. ✅ Run all tests (unit + integration + code quality)
2. ✅ Build Docker images and push to Artifact Registry
3. ✅ Deploy to Cloud Run with proper configuration
4. ✅ Verify deployment health

**Trigger**: Automatic deployment on every push to `replace-modal-with-google-cloud` branch (after all tests pass)

## Prerequisites

### 1. GCP Service Account with Permissions

You need a service account with the following roles:
- `roles/run.admin` - Deploy to Cloud Run
- `roles/iam.serviceAccountUser` - Act as the Cloud Run service account
- `roles/artifactregistry.writer` - Push images to Artifact Registry
- `roles/storage.admin` - Manage GCS (if needed for deployment)

### 2. Create Service Account (if not exists)

```bash
# Set your project ID
export PROJECT_ID=nomadkaraoke

# Create service account
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployer" \
  --project=$PROJECT_ID

# Grant necessary roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

echo "✅ Service account created with necessary permissions"
```

### 3. Generate and Download Service Account Key

```bash
# Create and download key
gcloud iam service-accounts keys create ~/github-actions-key.json \
  --iam-account=github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com

echo "✅ Key saved to ~/github-actions-key.json"
echo "⚠️  Keep this file secure - it provides full access to your GCP project"
```

### 4. Add Secrets to GitHub Repository

You need to add two secrets to your GitHub repository:

#### Secret 1: `GCP_SA_KEY`

This is the service account key JSON content.

**Steps**:
1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `GCP_SA_KEY`
5. Value: Copy the **entire contents** of `~/github-actions-key.json`
6. Click **Add secret**

```bash
# View the key (to copy):
cat ~/github-actions-key.json
```

#### Secret 2: `ADMIN_TOKENS`

This is a comma-separated list of admin authentication tokens.

**Steps**:
1. In the same GitHub secrets page
2. Click **New repository secret**
3. Name: `ADMIN_TOKENS`
4. Value: Your comma-separated admin tokens (e.g., `token1,token2,token3`)
5. Click **Add secret**

Example:
```
ADMIN_TOKENS=super-secret-admin-token-1,another-admin-token-2
```

### 5. Verify Secrets Are Set

You should now have these secrets in your repository:
- ✅ `GCP_SA_KEY` - Service account JSON key
- ✅ `ADMIN_TOKENS` - Admin authentication tokens

## How It Works

### Workflow Triggers

The CD pipeline runs when:
- ✅ Code is pushed to `replace-modal-with-google-cloud` branch
- ✅ All tests pass (unit, integration, code quality)
- ❌ Does NOT run on pull requests (only on direct pushes)

### Deployment Steps

1. **Run Tests** (parallel):
   - Unit tests (~20s)
   - Emulator integration tests (~1m)
   - Code quality checks (~20s)

2. **Build & Push** (~2-3m):
   - Build Docker image
   - Tag with `latest` and commit SHA
   - Push to Artifact Registry

3. **Deploy** (~1-2m):
   - Deploy to Cloud Run with environment variables
   - Configure resources (2 vCPU, 2GB RAM)
   - Set scaling (0-10 instances)

4. **Verify** (~10s):
   - Health check at `/api/health`
   - Ensure service is responding

**Total Time**: ~4-6 minutes from push to live deployment

### Environment Variables Set on Deployment

The deployment automatically sets these environment variables:
- `GOOGLE_CLOUD_PROJECT=nomadkaraoke`
- `GCS_BUCKET_NAME=nomadkaraoke-uploads`
- `FIRESTORE_COLLECTION=jobs`
- `ENVIRONMENT=production`
- `ADMIN_TOKENS=<from GitHub secret>`

## Monitoring Deployments

### View Deployment Status

**GitHub Actions UI**:
1. Go to your repository on GitHub
2. Click **Actions** tab
3. Click on the latest workflow run
4. View the **Deploy to Cloud Run** job

**Command Line**:
```bash
# List recent workflow runs
gh run list --branch replace-modal-with-google-cloud --limit 5

# View specific run
gh run view <run_id>

# View logs for deployment job
gh run view <run_id> --log --job=<job_id>
```

### View Deployed Service

```bash
# Get service details
gcloud run services describe karaoke-backend --region=us-central1

# Get latest revision
gcloud run services describe karaoke-backend \
  --region=us-central1 \
  --format='value(status.latestReadyRevisionName)'

# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend" \
  --limit 50 \
  --format json
```

### Check Deployment Health

```bash
# Test health endpoint
curl https://api.nomadkaraoke.com/api/health

# Should return:
# {"status":"healthy","timestamp":"..."}
```

## Deployment Configuration

### Resource Limits

The deployment is configured with:
- **Memory**: 2GB
- **CPU**: 2 vCPUs
- **Timeout**: 900s (15 minutes)
- **Scaling**:
  - Min instances: 0 (scale to zero when idle)
  - Max instances: 10

### Image Tags

Each deployment creates two image tags:
- `latest` - Always points to the most recent deployment
- `<commit-sha>` - Immutable tag for each commit

This allows easy rollback if needed:
```bash
# Rollback to specific commit
gcloud run deploy karaoke-backend \
  --image us-central1-docker.pkg.dev/nomadkaraoke/karaoke-repo/karaoke-backend:<old-commit-sha> \
  --region us-central1
```

## Troubleshooting

### Deployment Fails with "Permission Denied"

**Cause**: Service account lacks necessary permissions

**Fix**:
```bash
# Re-grant all necessary roles
gcloud projects add-iam-policy-binding nomadkaraoke \
  --member="serviceAccount:github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding nomadkaraoke \
  --member="serviceAccount:github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding nomadkaraoke \
  --member="serviceAccount:github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
```

### Deployment Succeeds but Service Fails

**Cause**: Missing or incorrect environment variables

**Check**:
```bash
# View current environment variables
gcloud run services describe karaoke-backend \
  --region=us-central1 \
  --format='value(spec.template.spec.containers[0].env)'

# Check logs for errors
gcloud logging read "resource.type=cloud_run_revision" \
  --limit 50 \
  --format json | jq '.[] | select(.severity=="ERROR")'
```

**Fix**: Update secrets in GitHub or redeploy with correct values

### Health Check Fails

**Cause**: Service not responding or health endpoint broken

**Debug**:
```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe karaoke-backend \
  --region=us-central1 \
  --format 'value(status.url)')

# Test health endpoint
curl -v "$SERVICE_URL/api/health"

# Check recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend" \
  --limit 100 \
  --format json | jq '.[] | select(.httpRequest)'
```

### "Image not found" Error

**Cause**: Image wasn't pushed correctly to Artifact Registry

**Fix**: Ensure Docker authentication is working
```bash
# In CI, this is done automatically:
gcloud auth configure-docker us-central1-docker.pkg.dev

# Verify image exists
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/nomadkaraoke/karaoke-repo/karaoke-backend
```

## Security Best Practices

### 1. Service Account Key Management

- ✅ Store key as GitHub secret (never commit to repo)
- ✅ Use least-privilege principle (only necessary roles)
- ✅ Rotate keys periodically (every 90 days recommended)
- ✅ Delete old keys after rotation

```bash
# List all keys for service account
gcloud iam service-accounts keys list \
  --iam-account=github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com

# Delete old key
gcloud iam service-accounts keys delete <KEY_ID> \
  --iam-account=github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com
```

### 2. Admin Tokens

- ✅ Use strong, random tokens (minimum 32 characters)
- ✅ Store in GitHub secrets (never in code)
- ✅ Rotate regularly
- ✅ Use different tokens for different environments

### 3. Audit Logging

Enable audit logs to track all deployments:
```bash
# View deployment audit logs
gcloud logging read "protoPayload.serviceName=run.googleapis.com" \
  --limit 50 \
  --format json
```

## Alternative: Workload Identity Federation (Recommended for Production)

Instead of service account keys, you can use Workload Identity Federation (more secure, no keys to manage):

**Benefits**:
- No service account keys to rotate
- Better security posture
- Automatic credential management

**Setup**: See [Google's Workload Identity Federation Guide](https://github.com/google-github-actions/auth#workload-identity-federation-through-a-service-account)

## Related Documentation

- [GitHub Actions Workflow](../../.github/workflows/test.yml) - Full CI/CD configuration
- [Cloud Build Config](../../cloudbuild.yaml) - Alternative manual deployment
- [Observability Guide](./OBSERVABILITY-GUIDE.md) - Monitoring and debugging
- [Emulator Testing](./EMULATOR-TESTING.md) - Local testing before deployment

---

**Last Updated**: Dec 2, 2025  
**Status**: CD pipeline configured and ready to use

