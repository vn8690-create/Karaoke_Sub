# Custom Domain Setup: api.nomadkaraoke.com

**Date:** 2025-12-01  
**Status:** ✅ Cloud Run domain mapping created, ⏳ Awaiting DNS configuration

---

## Summary

We've configured Cloud Run to accept traffic at `api.nomadkaraoke.com`. Now you need to add DNS records in Cloudflare to point the domain to Google's servers.

---

## Step 1: Add DNS Records in Cloudflare ✋ **ACTION REQUIRED**

Log in to your Cloudflare account and add the following DNS records for `nomadkaraoke.com`:

### Record to Add

| Type | Name | Value | TTL | Proxy Status |
|------|------|-------|-----|--------------|
| **CNAME** | `api` | `ghs.googlehosted.com` | Auto (or 300) | ⚠️ **DNS only** (gray cloud) |

**CRITICAL:** The proxy status must be **DNS only** (gray cloud icon), NOT proxied (orange cloud). Cloud Run domain verification requires direct DNS resolution.

### How to Add in Cloudflare

1. Go to https://dash.cloudflare.com/
2. Select `nomadkaraoke.com` domain
3. Click **DNS** in the left sidebar
4. Click **Add record**
5. Fill in:
   - **Type:** CNAME
   - **Name:** api
   - **Target:** ghs.googlehosted.com
   - **Proxy status:** Click the orange cloud to turn it **gray** (DNS only)
   - **TTL:** Auto
6. Click **Save**

---

## Step 2: Wait for DNS Propagation

After adding the DNS record:

1. **Propagation time:** 5-15 minutes (usually faster with Cloudflare)
2. **Verification:** Cloud Run will automatically verify domain ownership
3. **SSL certificate:** Google will automatically provision a free SSL certificate

### Check DNS Propagation

```bash
# Check if DNS is resolving
dig api.nomadkaraoke.com

# Should show CNAME pointing to ghs.googlehosted.com
```

Or use online tools:
- https://dnschecker.org/#CNAME/api.nomadkaraoke.com
- https://www.whatsmydns.net/#CNAME/api.nomadkaraoke.com

---

## Step 3: Verify Setup

Once DNS propagates (5-15 minutes), test the endpoint:

```bash
# Test health endpoint (may take a few tries while SSL certificate provisions)
curl https://api.nomadkaraoke.com/api/health

# Expected response:
{
  "status": "healthy",
  "service": "karaoke-gen-backend"
}
```

**Note:** If you get SSL errors initially, wait 5 more minutes for Google to provision the SSL certificate.

---

## Step 4: Update Environment Variables

Once working, update your environment to use the new URL:

```bash
# Add to ~/.zshrc or ~/.bashrc
export KARAOKE_BACKEND_URL="https://api.nomadkaraoke.com"
export AUTH_TOKEN=$(gcloud auth print-identity-token)

# Or create a .env file
echo "KARAOKE_BACKEND_URL=https://api.nomadkaraoke.com" > .env
```

---

## Troubleshooting

### DNS Not Resolving

**Problem:** `dig api.nomadkaraoke.com` returns NXDOMAIN or no results

**Solutions:**
1. Verify DNS record is saved in Cloudflare
2. Ensure proxy is disabled (gray cloud, not orange)
3. Wait 5-10 more minutes for propagation
4. Try flushing your local DNS cache:
   ```bash
   # macOS
   sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
   ```

### SSL Certificate Errors

**Problem:** `curl: (60) SSL certificate problem`

**Solutions:**
1. Wait 5-10 minutes for Google to provision SSL certificate
2. Check domain mapping status:
   ```bash
   gcloud run services describe karaoke-backend --region us-central1
   ```
3. If still failing after 20 minutes, delete and recreate domain mapping:
   ```bash
   cd infrastructure
   pulumi destroy --target urn:pulumi:dev::karaoke-gen-infrastructure::gcp:cloudrun/domainMapping:DomainMapping::karaoke-backend-domain
   pulumi up
   ```

### 404 Not Found

**Problem:** DNS resolves but getting 404

**Solutions:**
1. Check domain mapping:
   ```bash
   gcloud run domain-mappings list --platform managed --region us-central1
   ```
2. Ensure Cloud Run service name is correct (`karaoke-backend`)
3. Verify service is deployed and healthy:
   ```bash
   gcloud run services list --region us-central1
   ```

### Cloudflare Proxy Issues

**Problem:** DNS record shows orange cloud (proxied)

**Solution:**
1. Click the orange cloud icon to make it gray
2. Save changes
3. Wait 5 minutes for DNS to update

---

## Architecture

### Before (Hashed URL)
```
Client → https://karaoke-backend-ipzqd2k4yq-uc.a.run.app
         (Hard to remember, not branded)
```

### After (Custom Domain)
```
Client → https://api.nomadkaraoke.com
         ↓ (DNS CNAME)
         ghs.googlehosted.com
         ↓ (Google's load balancer)
         karaoke-backend (Cloud Run service)
```

**Benefits:**
- ✅ Branded, memorable URL
- ✅ Professional appearance
- ✅ Easy to change backends without updating clients
- ✅ Free SSL certificate from Google
- ✅ Automatic certificate renewal

---

## Infrastructure as Code

The domain mapping is managed in Pulumi:

```python
# infrastructure/__main__.py
domain_mapping = cloudrun.DomainMapping(
    "karaoke-backend-domain",
    location="us-central1",
    name="api.nomadkaraoke.com",
    spec=cloudrun.DomainMappingSpecArgs(
        route_name="karaoke-backend",
    ),
)
```

**To update:**
```bash
cd infrastructure
pulumi up
```

**To remove:**
```bash
cd infrastructure
pulumi destroy --target urn:pulumi:dev::karaoke-gen-infrastructure::gcp:cloudrun/domainMapping:DomainMapping::karaoke-backend-domain
```

---

## Next Steps for Frontend

Once the backend is working on `api.nomadkaraoke.com`, you'll want to set up the React frontend on a separate subdomain:

**Suggested domains:**
- **Backend API:** `api.nomadkaraoke.com` ✅ (done)
- **Frontend:** `gen.nomadkaraoke.com` or `app.nomadkaraoke.com` (future)

The frontend will use Cloudflare Pages, which has its own custom domain setup.

---

## Status Check

**Current URLs:**
- **Old (still works):** https://karaoke-backend-ipzqd2k4yq-uc.a.run.app
- **New (after DNS):** https://api.nomadkaraoke.com

**Pulumi Exports:**
```bash
cd infrastructure
pulumi stack output

# Should show:
backend_url: https://api.nomadkaraoke.com
backend_default_url: https://karaoke-backend-ipzqd2k4yq-uc.a.run.app
```

Both URLs will work indefinitely. The custom domain is just an alias.

---

## Summary

1. ✅ **Cloud Run domain mapping created** via Pulumi
2. ⏳ **Add DNS record in Cloudflare** (you need to do this)
   - Type: CNAME
   - Name: api
   - Value: ghs.googlehosted.com
   - Proxy: **DNS only** (gray cloud)
3. ⏳ **Wait 5-15 minutes** for DNS propagation
4. ✅ **Test:** `curl https://api.nomadkaraoke.com/api/health`
5. 🎉 **Done!** Use the new URL everywhere

---

**Next:** Once DNS is configured, test the file upload endpoint at the new URL! 🚀

