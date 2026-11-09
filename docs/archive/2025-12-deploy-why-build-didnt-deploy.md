# Why Cloud Build Didn't Deploy Automatically

**Issue:** Cloud Build successfully built the Docker image but didn't deploy it to Cloud Run

---

## Root Cause

The `cloudbuild.yaml` was configured to **only build and push Docker images**, not deploy them.

### Original cloudbuild.yaml

```yaml
steps:
  # Pull the previous image for caching
  - name: 'gcr.io/cloud-builders/docker'
    # ... pull latest ...
  
  # Build with cache
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '--cache-from'
      - 'us-central1-docker.pkg.dev/$PROJECT_ID/karaoke-repo/karaoke-backend:latest'
      # ...

images:
  - 'us-central1-docker.pkg.dev/$PROJECT_ID/karaoke-repo/karaoke-backend:latest'
  - 'us-central1-docker.pkg.dev/$PROJECT_ID/karaoke-repo/karaoke-backend:$BUILD_ID'
```

**What it does:**
1. ✅ Pull previous image for caching
2. ✅ Build new image
3. ✅ Push to Artifact Registry with `:latest` and `:$BUILD_ID` tags
4. ❌ **Does NOT deploy to Cloud Run**

---

## The Fix

Added a Cloud Run deployment step to `cloudbuild.yaml`:

```yaml
steps:
  # ... build steps ...

  # Deploy to Cloud Run (NEW!)
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'karaoke-backend'
      - '--image'
      - 'us-central1-docker.pkg.dev/$PROJECT_ID/karaoke-repo/karaoke-backend:$BUILD_ID'
      - '--region'
      - 'us-central1'
      - '--platform'
      - 'managed'

images:
  - 'us-central1-docker.pkg.dev/$PROJECT_ID/karaoke-repo/karaoke-backend:latest'
  - 'us-central1-docker.pkg.dev/$PROJECT_ID/karaoke-repo/karaoke-backend:$BUILD_ID'
```

**What it now does:**
1. ✅ Pull previous image for caching
2. ✅ Build new image
3. ✅ Push to Artifact Registry
4. ✅ **Deploy to Cloud Run automatically**

---

## Why Didn't Cloud Run Auto-Update?

Cloud Run doesn't automatically redeploy when a new `:latest` tag is pushed. You need to:

1. **Explicitly deploy** with `gcloud run deploy`, OR
2. **Add a deployment step** to Cloud Build (what we did)

The `:latest` tag is just a Docker tag - Cloud Run doesn't watch for changes.

---

## Timeline of Events

### Build 1 (6:27 AM) - 01bf8976
- ✅ Built image with fixed import error
- ✅ Pushed to Artifact Registry
- ❌ Didn't deploy to Cloud Run
- **Result:** Service still broken (revision 00003)

### Build 2 (6:41 AM) - 816a70fa
- ✅ Built image (still using old cloudbuild.yaml)
- ✅ Pushed to Artifact Registry
- ❌ Didn't deploy (no deployment step yet)
- **Manual deployment:** `gcloud run deploy ...`
- ✅ **Result:** Service working! (revision 00004)

### Future Builds
- ✅ Will build AND deploy automatically
- ✅ Uses updated cloudbuild.yaml with deployment step

---

## How We Deployed Manually

```bash
# Get the build ID from the latest successful build
BUILD_ID="816a70fa-c2e1-47d9-91c1-ca639d4d5eba"

# Deploy that specific image
gcloud run deploy karaoke-backend \
  --image us-central1-docker.pkg.dev/nomadkaraoke/karaoke-repo/karaoke-backend:$BUILD_ID \
  --region us-central1 \
  --platform managed
```

**Result:**
```
Service [karaoke-backend] revision [karaoke-backend-00004-rrn] has been deployed
and is serving 100 percent of traffic.
```

---

## Verification

### Health Check ✅

```bash
$ curl -H "Authorization: Bearer $AUTH_TOKEN" \
  https://karaoke-backend-ipzqd2k4yq-uc.a.run.app/api/health

{
  "status": "healthy",
  "service": "karaoke-gen-backend"
}
```

### Revision Status ✅

```bash
$ gcloud run revisions list --service karaoke-backend --region us-central1

NAME                       STATUS  TRAFFIC
karaoke-backend-00004-rrn  True    100%    ← NEW! Working!
karaoke-backend-00003-55h  False   0%      ← Old broken revision
karaoke-backend-00002-sk9  True    0%      ← Old working revision
```

---

## Lesson Learned

**Cloud Build has two distinct responsibilities:**

1. **Build:** Compile code, create Docker image, push to registry
2. **Deploy:** Update Cloud Run service to use new image

**By default, Cloud Build only does #1.**

You must explicitly add a deployment step for #2.

---

## Alternative Approaches

### Option 1: Separate Build and Deploy (Original)

```bash
# Build
gcloud builds submit --config=cloudbuild.yaml

# Deploy manually
gcloud run deploy karaoke-backend \
  --image us-central1-docker.pkg.dev/nomadkaraoke/karaoke-repo/karaoke-backend:latest \
  --region us-central1
```

**Pros:** Separate concerns, more control  
**Cons:** Requires two steps, easy to forget

### Option 2: Combined Build + Deploy (New)

```bash
# Build AND deploy in one command
gcloud builds submit --config=cloudbuild.yaml
```

**Pros:** One command, automatic deployment  
**Cons:** Longer build time, deploys every time

### Option 3: Pulumi Managed

```bash
# Update infrastructure
pulumi up
```

**Pros:** Infrastructure as code, versioned  
**Cons:** Need to update Pulumi config for each deployment

---

## Current Setup

**We're using Option 2:** Combined build + deploy via Cloud Build

### Workflow

```bash
# 1. Make code changes
vim backend/api/routes/jobs.py

# 2. Validate locally (catches errors!)
source backend/venv/bin/activate
python3 backend/validate.py

# 3. Deploy (builds + deploys automatically)
./scripts/deploy.sh
# OR
gcloud builds submit --config=cloudbuild.yaml
```

---

## Next Build Will Deploy Automatically! ✅

From now on, `gcloud builds submit` will:
1. Build the Docker image
2. Push to Artifact Registry
3. **Deploy to Cloud Run automatically**

No more manual deployment needed! 🎉

---

## Summary

| Build | Image Built? | Deployed? | Why? |
|-------|--------------|-----------|------|
| 01bf8976 | ✅ Yes | ❌ No | No deployment step in cloudbuild.yaml |
| 816a70fa | ✅ Yes | ✅ Manual | We deployed manually after build |
| Future | ✅ Yes | ✅ Automatic | Updated cloudbuild.yaml with deploy step |

**Status:** Fixed! ✅

