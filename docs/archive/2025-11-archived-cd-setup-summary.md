# 🚀 Continuous Deployment (CD) Setup - Ready to Activate!

**Status**: CD pipeline configured with Workload Identity Federation  
**Remaining**: Add 3 GitHub secrets (instructions below)  
**Time to complete**: ~2 minutes

---

## ✅ What's Already Done

1. ✅ **CI/CD Workflow configured** (`.github/workflows/test.yml`)
   - Runs all 73 tests
   - Builds and pushes Docker images
   - Deploys to Cloud Run
   - Verifies health

2. ✅ **GCP Infrastructure created**
   - Service account: `github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com`
   - IAM roles granted (run.admin, iam.serviceAccountUser, artifactregistry.writer)
   - Workload Identity Pool: `github-actions-pool`
   - Workload Identity Provider: `github-actions-provider`

3. ✅ **Documentation complete**
   - Setup instructions
   - Troubleshooting guide
   - Security best practices

---

## 🎯 What You Need to Do

### Add 3 GitHub Secrets

Go to: https://github.com/nomadkaraoke/karaoke-gen/settings/secrets/actions

Click **"New repository secret"** for each:

#### Secret 1: `GCP_WORKLOAD_IDENTITY_PROVIDER`

**Name**: `GCP_WORKLOAD_IDENTITY_PROVIDER`

**Value** (copy this exactly):
```
projects/718638054799/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider
```

#### Secret 2: `GCP_SERVICE_ACCOUNT`

**Name**: `GCP_SERVICE_ACCOUNT`

**Value** (copy this exactly):
```
github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com
```

#### Secret 3: `ADMIN_TOKENS`

**Name**: `ADMIN_TOKENS`

**Value**: Your comma-separated admin authentication tokens

Example:
```
super-secret-token-1,another-secure-token-2
```

---

## ⚠️ One Manual Step Required (If Not Already Done)

The service account needs one IAM binding that may require higher permissions. Try running this command:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com \
  --project=nomadkaraoke \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/718638054799/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/nomadkaraoke/karaoke-gen"
```

**If that fails with permission error**, use the Cloud Console:

1. Go to: https://console.cloud.google.com/iam-admin/serviceaccounts?project=nomadkaraoke
2. Click on `github-actions-deployer`
3. Go to **PERMISSIONS** tab
4. Click **GRANT ACCESS**
5. Principal: `principalSet://iam.googleapis.com/projects/718638054799/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/nomadkaraoke/karaoke-gen`
6. Role: **Workload Identity User**
7. Save

---

## 🧪 Test the CD Pipeline

After adding the secrets:

```bash
# Option 1: Make an empty commit to trigger deployment
git commit --allow-empty -m "Test CD pipeline"
git push origin replace-modal-with-google-cloud

# Option 2: Just push the current changes
git push origin replace-modal-with-google-cloud

# Watch the deployment
gh run watch
```

---

## ✅ Verify It Worked

### Check GitHub Actions
https://github.com/nomadkaraoke/karaoke-gen/actions

You should see:
- ✅ Unit Tests pass
- ✅ Emulator Integration Tests pass
- ✅ Code Quality pass
- ✅ **Deploy to Cloud Run** pass (new!)

### Check Cloud Run

```bash
# Get service info
gcloud run services describe karaoke-backend --region=us-central1

# Test health endpoint
curl https://api.nomadkaraoke.com/api/health
```

Expected response:
```json
{"status":"healthy","timestamp":"..."}
```

---

## 🎉 What Happens After Setup

### Every Push to `replace-modal-with-google-cloud` Branch:

1. **CI runs** (~3 min):
   - 62 unit tests
   - 11 integration tests
   - Code quality checks

2. **If tests pass, CD runs** (~4 min):
   - Build Docker image
   - Tag with `latest` and commit SHA
   - Push to Artifact Registry
   - Deploy to Cloud Run
   - Verify health

3. **Total time**: ~7 minutes from push to live! 🚀

### What About Pull Requests?

- ✅ Tests run automatically
- ❌ Deployment does NOT run (only on direct push to branch)

This prevents deploying unreviewed code.

---

## 🔒 Security Benefits of Workload Identity

✅ **No service account keys to manage**  
✅ **Automatic credential rotation**  
✅ **Better security posture**  
✅ **No key expiration issues**  
✅ **Least-privilege access** (GitHub can only deploy, not read data)

Much more secure than traditional service account keys!

---

## 📊 Current Test Coverage

Once CD is active, every deployment will be validated by:

- **62 unit tests** - Models, services, business logic
- **11 integration tests** - Real Firestore + GCS emulators
- **Code quality checks** - Python syntax and imports

**Total**: 73 automated tests ensuring code quality before deployment

---

## 🐛 Troubleshooting

### Deployment fails with "Permission denied"

Check the Workload Identity binding is set correctly:

```bash
gcloud iam service-accounts get-iam-policy \
  github-actions-deployer@nomadkaraoke.iam.gserviceaccount.com \
  --project=nomadkaraoke
```

You should see a binding with role `roles/iam.workloadIdentityUser`.

### Tests pass but deployment doesn't run

- Check that you pushed to `replace-modal-with-google-cloud` branch (not a PR)
- Verify all 3 GitHub secrets are set correctly
- Check GitHub Actions logs for error messages

### Deployment succeeds but service fails

- Check Cloud Run logs for errors
- Verify environment variables are set
- Ensure `ADMIN_TOKENS` secret is correct

---

## 📚 Related Documentation

- [Detailed Setup Guide](docs/03-deployment/CD-SETUP.md)
- [Manual Setup Instructions](docs/03-deployment/CD-SETUP-INSTRUCTIONS.md)
- [GitHub Actions Overview](.github/README.md)
- [Emulator Testing](docs/03-deployment/EMULATOR-TESTING.md)
- [Observability Guide](docs/03-deployment/OBSERVABILITY-GUIDE.md)

---

## 🎯 Summary

**You're 3 GitHub secrets away from true continuous deployment!**

1. Add `GCP_WORKLOAD_IDENTITY_PROVIDER` secret
2. Add `GCP_SERVICE_ACCOUNT` secret
3. Add `ADMIN_TOKENS` secret
4. Complete the IAM binding (command above)
5. Push to branch → automatic deployment! 🚀

---

**Questions?** See `docs/03-deployment/CD-SETUP-INSTRUCTIONS.md` for detailed help.

