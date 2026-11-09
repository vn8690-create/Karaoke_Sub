# SSL Certificate Issue - Troubleshooting

**Status:** ❌ Certificate provisioning stuck  
**Error:** "Challenge data was not visible through the public internet"

---

## Problem

Cloud Run domain mapping exists but SSL certificate won't provision:

```json
{
  "type": "CertificateProvisioned",
  "status": "Unknown",
  "reason": "CertificatePending",
  "message": "Certificate issuance pending. The challenge data was not visible 
             through the public internet. This may indicate that DNS is not 
             properly configured or has not fully propagated. The system will retry."
}
```

**System is retrying every 15 minutes but failing.**

---

## Root Cause

Google Cloud Run uses **Let's Encrypt** for SSL certificates, which requires **HTTP-01 challenge** verification. This means:

1. Let's Encrypt makes HTTP request to `http://api.nomadkaraoke.com/.well-known/acme-challenge/...`
2. Google's servers must respond with the correct challenge data
3. If Cloudflare proxy is enabled OR DNS isn't pointing correctly, verification fails

---

## Solution: Verify Cloudflare Configuration

### Check 1: Proxy Status MUST be "DNS only"

**In Cloudflare dashboard:**
1. Go to https://dash.cloudflare.com/
2. Select `nomadkaraoke.com`
3. Click **DNS**
4. Find the `api` CNAME record
5. **CRITICAL:** Cloud icon must be **GRAY** ☁️ (DNS only)
   - If it's **ORANGE** 🟠 (proxied) → Click it to make it gray
   - Save changes

**Why this matters:**
- Orange cloud (proxied) = Traffic goes through Cloudflare's servers
- Gray cloud (DNS only) = Traffic goes directly to Google
- Let's Encrypt verification REQUIRES direct access to Google's servers

### Check 2: DNS Record is Correct

Should show:
```
Type: CNAME
Name: api
Target: ghs.googlehosted.com
TTL: Auto (or 300)
Proxy: DNS only (gray cloud)
```

---

## Alternative Solution: Delete and Recreate

If the cloud is already gray and it's still not working, the domain mapping might be corrupted:

```bash
cd /Users/andrew/Projects/karaoke-gen/infrastructure

# Delete the domain mapping
pulumi destroy \
  --target urn:pulumi:dev::karaoke-gen-infrastructure::gcp:cloudrun/domainMapping:DomainMapping::karaoke-backend-domain \
  --yes

# Wait 2 minutes for cleanup

# Recreate it
pulumi up --yes

# Wait 20-30 minutes for SSL provisioning
```

---

## Checking Current Status

```bash
# Check domain mapping status
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://run.googleapis.com/v1/projects/nomadkaraoke/locations/us-central1/domainmappings/api.nomadkaraoke.com" \
  | jq -r '.status.conditions[] | "\(.type): \(.status) - \(.message // .reason)"'

# Should show:
# Ready: True - <no message>  ← This means it's working
# CertificateProvisioned: True - <no message>
# DomainRoutable: True
```

---

## Why This Happens

**Common causes:**
1. **Cloudflare proxy enabled** (most common) - Orange cloud blocks Let's Encrypt
2. **DNS not propagated** - Wait 30 minutes after DNS change
3. **Previous certificate attempt cached** - Delete and recreate domain mapping
4. **Firewall rules** - Usually not an issue with Cloud Run

---

## Expected Timeline After Fix

1. **Fix Cloudflare proxy** (if orange)
2. **Wait 5-10 minutes** for DNS to update
3. **Cloud Run retries** every 15 minutes
4. **Certificate provision** takes 10-20 minutes after successful verification
5. **Total:** 15-30 minutes after fix

---

## Workaround: Use Default URL

While waiting, you can use the default Cloud Run URL which already has SSL:

```bash
export BACKEND_URL="https://karaoke-backend-ipzqd2k4yq-uc.a.run.app"

curl $BACKEND_URL/api/health
# Works immediately!
```

Both URLs will work once the custom domain is ready.

---

## Next Steps

1. **Check Cloudflare** - Make sure proxy is disabled (gray cloud)
2. **Wait 15 minutes** - Cloud Run retries every 15 min
3. **If still failing** - Delete and recreate domain mapping
4. **Alternative** - Use default URL for now

---

## Status Check Command

Run this to see current status:

```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://run.googleapis.com/v1/projects/nomadkaraoke/locations/us-central1/domainmappings/api.nomadkaraoke.com" \
  | jq '.status.conditions[] | select(.type == "CertificateProvisioned") | .message'
```

**When working, you'll see:**
- No message, or
- "Certificate provisioned"

**When broken, you'll see:**
- "Challenge data was not visible"
- "Certificate issuance pending"

