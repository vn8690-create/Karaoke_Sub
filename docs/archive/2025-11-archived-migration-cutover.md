# Migration Cutover Plan

Step-by-step plan for migrating from Modal to the new Cloud Run + Cloudflare Pages architecture.

## Pre-Cutover Checklist

### Backend (Cloud Run)
- [ ] Backend code tested locally
- [ ] Docker image builds successfully
- [ ] GCP infrastructure provisioned (Firestore, Cloud Storage, Secret Manager)
- [ ] Secrets configured (API keys)
- [ ] Service account permissions set
- [ ] Deployed to Cloud Run and tested
- [ ] Health check endpoint responds
- [ ] Test job submission works
- [ ] Test file upload works

### Frontend (Cloudflare Pages)
- [ ] React app tested locally
- [ ] Builds successfully
- [ ] API_URL environment variable configured
- [ ] Connected to GitHub
- [ ] Deployed to Cloudflare Pages
- [ ] Test deployment accessible
- [ ] API calls work end-to-end

### Integration
- [ ] Frontend can communicate with backend
- [ ] CORS configured correctly
- [ ] File uploads work
- [ ] Downloads work
- [ ] Error handling tested
- [ ] Concurrent jobs tested

## Cutover Steps

### Phase 1: Parallel Run (Days 1-3)

Run both systems simultaneously for testing and comparison.

**Day 1: Initial Deployment**

1. Deploy backend to Cloud Run:
```bash
cd /Users/andrew/Projects/karaoke-gen
export PROJECT_ID=your-project-id

# Build image
gcloud builds submit --tag gcr.io/$PROJECT_ID/karaoke-backend -f backend/Dockerfile .

# Deploy
gcloud run deploy karaoke-backend \
  --image gcr.io/$PROJECT_ID/karaoke-backend \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --max-instances 10 \
  --min-instances 1 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GCS_BUCKET_NAME=karaoke-gen-storage" \
  --set-secrets="AUDIOSHAKE_API_KEY=audioshake-api-key:latest,GENIUS_API_KEY=genius-api-key:latest,AUDIO_SEPARATOR_API_URL=audio-separator-api-url:latest"

# Get service URL
export BACKEND_URL=$(gcloud run services describe karaoke-backend --region us-central1 --format='value(status.url)')
echo "Backend deployed at: $BACKEND_URL"
```

2. Deploy frontend to Cloudflare Pages:
```bash
cd frontend-react

# Build
npm run build

# Deploy (if using Wrangler)
npx wrangler pages deploy dist --project-name=karaoke-gen

# Or connect via Cloudflare Dashboard
# - Go to Pages
# - Connect GitHub repo
# - Set build command: cd frontend-react && npm install && npm run build
# - Set output: frontend-react/dist
# - Set env var: VITE_API_URL=$BACKEND_URL/api
```

3. Test the new system thoroughly
4. Keep Modal deployment running

**Day 2-3: Monitoring**

- Monitor Cloud Run logs for errors
- Monitor Firestore for job completion rates
- Compare performance with Modal
- Fix any issues discovered
- Run test jobs through both systems

### Phase 2: DNS Cutover (Day 4)

Switch `gen.nomadkaraoke.com` to point to new frontend.

**Current State:**
- `gen.nomadkaraoke.com` → Modal deployment
- New frontend → `*.pages.dev` temporary URL

**Target State:**
- `gen.nomadkaraoke.com` → Cloudflare Pages
- Modal deployment → Accessible via original Modal URL (for rollback)

**Steps:**

1. Configure custom domain in Cloudflare Pages:
   - Go to Pages project settings
   - Add custom domain: `gen.nomadkaraoke.com`
   - Cloudflare will update DNS automatically

2. Verify DNS propagation:
```bash
# Check DNS
dig gen.nomadkaraoke.com

# Test new URL
curl https://gen.nomadkaraoke.com/
```

3. Test complete workflow on production URL

4. Monitor for 24 hours

### Phase 3: Monitor and Validate (Days 5-7)

**Monitoring Checklist:**

- [ ] No errors in Cloud Run logs
- [ ] Jobs completing successfully
- [ ] Download links work
- [ ] Performance acceptable (<10min per job)
- [ ] No cost overruns
- [ ] Frontend loads quickly
- [ ] Mobile experience good

**Validation:**

```bash
# Check Cloud Run metrics
gcloud run services describe karaoke-backend --region us-central1

# Check logs
gcloud logging read "resource.type=cloud_run_revision" --limit 100

# Check Firestore job count
gcloud firestore query jobs --limit 10

# Check storage usage
gsutil du -s gs://karaoke-gen-storage
```

### Phase 4: Decommission Modal (Days 8-14)

Once confident in new system, shut down Modal deployment.

**Steps:**

1. Announce maintenance window to users (if any)
2. Disable job submission on Modal
3. Let in-flight jobs complete
4. Export any data from Modal volumes if needed
5. Delete Modal app:

```bash
# List Modal apps
modal app list

# Delete app
modal app delete karaoke-generator-webapp
```

6. Remove Modal-specific files from repo (next section)

## Rollback Plan

If critical issues are discovered:

### Rollback Frontend

1. Update DNS to point back to Modal
2. Or use Cloudflare Pages rollback feature:
   - Go to Deployments
   - Find previous working deployment
   - Click "Rollback"

### Rollback Backend

1. Redeploy Modal app:
```bash
cd /Users/andrew/Projects/karaoke-gen
modal deploy app.py
```

2. Update frontend VITE_API_URL to Modal backend

### Critical Issues Warranting Rollback

- Jobs failing at >20% rate
- Complete system unavailability
- Data loss or corruption
- Security vulnerability
- Unacceptable performance degradation

## Post-Migration Cleanup

Once Modal is decommissioned, clean up old files (see cleanup-documentation todo).

## Communication Plan

### Internal Team
- Pre-cutover: "New architecture deploying, running in parallel"
- Cutover: "Switching DNS to new system"
- Post-cutover: "Monitoring new system, Modal still available for rollback"
- Decommission: "Modal shut down, migration complete"

### Users (if applicable)
- Announce improved performance and features
- Notify of any temporary downtime
- Provide support contact for issues

## Success Metrics

Track these metrics to validate migration success:

### Technical Metrics
- **Uptime**: >99.5%
- **Job Success Rate**: >95%
- **Processing Time**: <10 minutes average
- **Error Rate**: <2%
- **API Response Time**: <500ms p95

### Cost Metrics
- **Monthly Cost**: <$100 (vs Modal costs)
- **Cost per Job**: <$1
- **Storage Costs**: <$5/month

### User Experience
- **Frontend Load Time**: <2s
- **Download Speed**: Acceptable for large files
- **Mobile Experience**: Fully functional

## Monitoring Dashboard

Create a dashboard to track migration:

```bash
# Key metrics to monitor
gcloud monitoring dashboards create --config-from-file=- <<EOF
{
  "displayName": "Karaoke Gen Migration",
  "gridLayout": {
    "widgets": [
      {"title": "Cloud Run Requests", "xyChart": {...}},
      {"title": "Error Rate", "xyChart": {...}},
      {"title": "Processing Time", "xyChart": {...}},
      {"title": "Storage Usage", "xyChart": {...}}
    ]
  }
}
EOF
```

## Timeline Summary

| Day | Phase | Activities |
|-----|-------|-----------|
| 1 | Deploy | Deploy backend + frontend, initial testing |
| 2-3 | Parallel | Run both systems, monitor, test thoroughly |
| 4 | Cutover | DNS switch to new system |
| 5-7 | Validate | Monitor production, fix issues |
| 8-14 | Decommission | Shut down Modal, cleanup code |

**Total Duration**: 2 weeks for safe, monitored migration

## Emergency Contacts

- GCP Console: https://console.cloud.google.com
- Cloudflare Dashboard: https://dash.cloudflare.com
- Cloud Run: https://console.cloud.google.com/run
- Support: [Your support contact]

## Final Checklist

Before declaring migration complete:

- [ ] All Modal dependencies removed
- [ ] Documentation updated
- [ ] Old files archived/deleted
- [ ] Team trained on new system
- [ ] Runbooks updated
- [ ] Monitoring alerts configured
- [ ] Backup/disaster recovery tested
- [ ] Performance acceptable
- [ ] Costs within budget
- [ ] No outstanding issues

