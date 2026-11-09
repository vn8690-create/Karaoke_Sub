# Cloud Build Permissions Issue - Resolution

## Problem
Cloud Build was failing with:
```
denied: Permission "artifactregistry.repositories.uploadArtifacts" denied
```

## Root Cause
Cloud Build uses **THREE different service accounts** depending on the context:

1. `{PROJECT_NUMBER}@cloudbuild.gserviceaccount.com` - Default Cloud Build service account
2. `service-{PROJECT_NUMBER}@gcp-sa-cloudbuild.iam.gserviceaccount.com` - Cloud Build service agent  
3. `{PROJECT_NUMBER}-compute@developer.gserviceaccount.com` - **Compute Engine default service account** (THIS WAS THE MISSING ONE!)

## Why This Happened
When you don't specify a service account for Cloud Build, it defaults to using the Compute Engine default service account (`{PROJECT_NUMBER}-compute@developer.gserviceaccount.com`). We only granted permissions to the first two service accounts, but not this third one.

## Solution
Grant `roles/artifactregistry.writer` permission to **all three** service accounts at the repository level:

```bash
# Service account 1
gcloud artifacts repositories add-iam-policy-binding karaoke-repo \
  --location=us-central1 \
  --member="serviceAccount:718638054799@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Service account 2
gcloud artifacts repositories add-iam-policy-binding karaoke-repo \
  --location=us-central1 \
  --member="serviceAccount:service-718638054799@gcp-sa-cloudbuild.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Service account 3 (THE KEY ONE!)
gcloud artifacts repositories add-iam-policy-binding karaoke-repo \
  --location=us-central1 \
  --member="serviceAccount:718638054799-compute@developer.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
```

## Testing Without Full Build
To test permissions without waiting for a full build:

```bash
# Create test config
cat > /tmp/test-push.yaml <<EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['pull', 'alpine:latest']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['tag', 'alpine:latest', 'us-central1-docker.pkg.dev/\$PROJECT_ID/karaoke-repo/test:latest']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'us-central1-docker.pkg.dev/\$PROJECT_ID/karaoke-repo/test:latest']
timeout: 300s
EOF

# Run test build
gcloud builds submit --config=/tmp/test-push.yaml --no-source
```

This completes in ~10 seconds and definitively tests if push permissions work.

## Now Tracked in Pulumi
The `infrastructure/__main__.py` file has been updated to include all three service accounts in the IAM binding, so if you ever recreate the infrastructure, all permissions will be set correctly automatically.

## Key Learnings
1. **GCP has multiple service accounts** for the same service
2. **Resource-level IAM** is required for Artifact Registry (project-level isn't enough)
3. **Test permissions quickly** with minimal builds before running expensive full builds
4. **Track everything in IaC** (Pulumi) so it's reproducible

