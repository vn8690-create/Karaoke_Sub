# CD Setup Instructions (Manual)

Your GCP project has policies that prevent automated setup. Follow these manual steps instead.

## What We've Already Done ✅

1. ✅ Created service account: `github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com`
2. ✅ Granted IAM roles: `run.admin`, `iam.serviceAccountUser`, `artifactregistry.writer`
3. ✅ Created Workload Identity Pool: `github-actions-pool`
4. ✅ Created Workload Identity Provider: `github-actions-provider`

## What You Need to Do Manually

### Step 1: Complete Workload Identity Binding

Run this command (you may need higher permissions or run from Cloud Console):

```bash
gcloud iam service-accounts add-iam-policy-binding \
  github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com \
  --project=nomadkaraoke \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/718638054799/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/nomadkaraoke/karaoke-gen"
```

**OR use Cloud Console**:
1. Go to: https://console.cloud.google.com/iam-admin/serviceaccounts?project=nomadkaraoke
2. Click on `github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com`
3. Go to **PERMISSIONS** tab
4. Click **GRANT ACCESS**
5. Add principal: `principalSet://iam.googleapis.com/projects/718638054799/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/nomadkaraoke/karaoke-gen`
6. Role: **Workload Identity User**
7. Save

### Step 2: Get Workload Identity Provider Name

```bash
gcloud iam workload-identity-pools providers describe github-actions-provider \
  --workload-identity-pool=github-actions-pool \
  --location=global \
  --project=nomadkaraoke \
  --format="value(name)"
```

This will output something like:
```
projects/718638054799/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider
```

### Step 3: Add GitHub Secrets

Go to: https://github.com/nomadkaraoke/karaoke-gen/settings/secrets/actions

**Add these 3 secrets:**

1. **`GCP_WORKLOAD_IDENTITY_PROVIDER`**
   - Value: (the output from Step 2 above)
   - Example: `projects/718638054799/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider`

2. **`GCP_SERVICE_ACCOUNT`**
   - Value: `github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com`

3. **`ADMIN_TOKENS`**
   - Value: Your comma-separated admin tokens
   - Example: `token1,token2,token3`

### Step 4: Test the CD Pipeline

Once secrets are added:

```bash
# Make a test commit
git commit --allow-empty -m "Test CD pipeline with Workload Identity"
git push origin replace-modal-with-google-cloud

# Watch the deployment
gh run watch
```

## Verification

After the workflow runs, verify:

```bash
# Check service is deployed
gcloud run services describe karaoke-backend --region=us-central1

# Test health endpoint
curl https://api.nomadkaraoke.com/api/health
```

## Troubleshooting

### If deployment fails with "Permission denied"

The Workload Identity binding might not have been set up correctly. Check:

```bash
# Verify the binding
gcloud iam service-accounts get-iam-policy \
  github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com \
  --project=nomadkaraoke
```

You should see a binding with:
- Role: `roles/iam.workloadIdentityUser`
- Member: `principalSet://iam.googleapis.com/projects/718638054799/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/nomadkaraoke/karaoke-gen`

### If you can't set the IAM binding

You may need to:
1. Check organization policies that restrict IAM changes
2. Ask an organization admin to grant you `roles/iam.securityAdmin`
3. Or have them run the binding command for you

### Alternative: Use Service Account Key (Less Secure)

If Workload Identity is blocked by policies, you can request an exception to create service account keys, or have an admin create one for you. This is less secure but may be necessary depending on your organization's policies.

## What Happens When It Works

Every push to `replace-modal-with-google-cloud` branch will:
1. ✅ Run all 73 tests (unit + integration + quality)
2. ✅ Build Docker image
3. ✅ Push to Artifact Registry
4. ✅ Deploy to Cloud Run
5. ✅ Verify health
6. ✅ Live in ~7 minutes!

No manual intervention needed - true continuous deployment! 🚀

