# Cloudflare DNS Setup - Quick Guide

## What You Need to Do

Add **one DNS record** to Cloudflare for `nomadkaraoke.com`:

---

## DNS Record to Add

```
Type:   CNAME
Name:   api
Target: ghs.googlehosted.com
Proxy:  DNS only (gray cloud ☁️, NOT orange 🟠)
TTL:    Auto
```

---

## Step-by-Step Instructions

### 1. Log in to Cloudflare
Go to: https://dash.cloudflare.com/

### 2. Select Your Domain
Click on `nomadkaraoke.com`

### 3. Go to DNS Settings
Click **DNS** in the left sidebar

### 4. Add the Record
Click **Add record** button

### 5. Fill in the Form
```
┌─────────────────────────────────────────────────┐
│ Type:    CNAME         ▼                        │
│ Name:    api                                    │
│ Target:  ghs.googlehosted.com                   │
│ Proxy:   ☁️  (click to make gray, not orange)  │
│ TTL:     Auto          ▼                        │
│                                                 │
│                           [Save] [Cancel]       │
└─────────────────────────────────────────────────┘
```

### 6. ⚠️ IMPORTANT: Disable Proxy
Make sure the cloud icon is **GRAY** ☁️ (DNS only)
- **Not orange** 🟠 (proxied)
- Click the cloud icon to toggle between gray and orange
- Must be gray for Cloud Run to work!

### 7. Save
Click **Save**

---

## What This Does

```
Before:
  api.nomadkaraoke.com → ❌ Nothing

After:
  api.nomadkaraoke.com → ghs.googlehosted.com → Google Cloud Run → Your Backend
```

---

## Verification (After 5-15 Minutes)

### Check DNS
```bash
dig api.nomadkaraoke.com
```

Should show:
```
;; ANSWER SECTION:
api.nomadkaraoke.com.  300  IN  CNAME  ghs.googlehosted.com.
```

### Test API
```bash
curl https://api.nomadkaraoke.com/api/health
```

Should return:
```json
{
  "status": "healthy",
  "service": "karaoke-gen-backend"
}
```

**Note:** May take 5-15 minutes for DNS to propagate and SSL certificate to provision.

---

## Common Mistakes

❌ **Wrong:**
- Orange cloud 🟠 (proxied) - Won't work!
- Target: `karaoke-backend-ipzqd2k4yq-uc.a.run.app` - Wrong target!
- Type: A record - Wrong type!

✅ **Correct:**
- Gray cloud ☁️ (DNS only)
- Target: `ghs.googlehosted.com`
- Type: CNAME

---

## Need Help?

If it's not working after 20 minutes:
1. Check the DNS record in Cloudflare is saved correctly
2. Verify the cloud is gray, not orange
3. Try: `dig api.nomadkaraoke.com` to see what DNS returns
4. Check the full guide: `docs/03-deployment/CUSTOM-DOMAIN-SETUP.md`

---

That's it! Just **one DNS record** and you're done! 🎉

