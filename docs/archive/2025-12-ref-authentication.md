# Authentication System

**Status:** ✅ Implemented  
**Current:** Simple token-based auth with admin tokens  
**Future:** Full token management dashboard (like Modal implementation)

---

## Overview

The backend uses **token-based authentication** to control access to the karaoke generation API.

### Token Types

| Type | Description | Usage Limit | Use Case |
|------|-------------|-------------|----------|
| **ADMIN** | Full access + token management | Unlimited | Administrators |
| **UNLIMITED** | Generate karaoke videos | Unlimited | Premium users |
| **LIMITED** | Generate karaoke videos | Configurable | Free tier users |
| **STRIPE** | Paid access (future) | Based on payment | Paying customers |

---

## Current Setup (Simple)

### Admin Tokens (Hardcoded)

Admin tokens are set via environment variable:

```bash
# In Secret Manager or .env
ADMIN_TOKENS="nomad,your-secret-admin-token-here"
```

**Features:**
- ✅ Comma-separated list
- ✅ Unlimited access
- ✅ Can create/manage other tokens
- ✅ Never expire
- ✅ Not stored in database

### Example: Testing with "nomad" Token

```bash
export BACKEND_URL="https://api.nomadkaraoke.com"
export TOKEN="nomad"

# Test health endpoint (no auth required)
curl $BACKEND_URL/api/health

# Submit job (requires auth)
curl -X POST "$BACKEND_URL/api/jobs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=...",
    "artist": "ABBA",
    "title": "Waterloo"
  }'
```

---

## Future Setup (Full Token Management)

### Token Management API (Admin Only)

#### Create Token
```bash
POST /api/admin/tokens
Authorization: Bearer <admin-token>

{
  "token_value": "user-abc123",
  "token_type": "limited",
  "max_uses": 10
}
```

#### List Tokens
```bash
GET /api/admin/tokens
Authorization: Bearer <admin-token>
```

#### Revoke Token
```bash
DELETE /api/admin/tokens/{token}
Authorization: Bearer <admin-token>
```

#### Get Token Info
```bash
GET /api/admin/tokens/{token}
Authorization: Bearer <admin-token>
```

---

## How It Works

### 1. Authentication Flow

```
Client Request
  ↓
Extract token from:
  - Authorization: Bearer <token>
  - OR ?token=<token> (for download links)
  ↓
Validate token:
  - Check if admin token (env var)
  - Check if in Firestore
  - Check if active
  - Check usage limits
  ↓
Allow/Deny request
```

### 2. Token Validation

```python
is_valid, user_type, remaining_uses, message = auth_service.validate_token(token)

# Returns:
# is_valid: True/False
# user_type: ADMIN/UNLIMITED/LIMITED/STRIPE
# remaining_uses: -1 (unlimited) or count
# message: Human-readable status
```

### 3. Usage Tracking

When a job is created:
1. Token is validated
2. Usage count is incremented (for LIMITED/STRIPE tokens)
3. Job is added to token's history
4. Remaining uses are updated

**Admin and UNLIMITED tokens:** No usage tracking

---

## Authentication Levels

### Public Endpoints (No Auth)

```bash
GET /
GET /api/health
```

### Authenticated Endpoints (Any Valid Token)

```bash
POST /api/jobs              # Create job
POST /api/jobs/upload       # Upload file
GET /api/jobs/{job_id}      # Get job status
DELETE /api/jobs/{job_id}   # Delete job

# Human-in-the-loop endpoints
POST /api/jobs/{job_id}/lyrics/review
GET /api/jobs/{job_id}/instrumentals
POST /api/jobs/{job_id}/instrumentals/select
```

### Admin Endpoints (Admin Token Only)

```bash
POST /api/admin/tokens          # Create token
GET /api/admin/tokens           # List tokens
GET /api/admin/tokens/{token}   # Get token info
DELETE /api/admin/tokens/{token}# Revoke token
GET /api/admin/stats            # Usage statistics
```

---

## Security Features

### ✅ Implemented

1. **Token validation** - All requests checked
2. **Usage limits** - Track and enforce limits
3. **Token revocation** - Disable tokens
4. **Admin-only endpoints** - Separate access level
5. **Firestore storage** - Persistent token data
6. **Transaction safety** - Atomic usage increments

### 🔜 Future Enhancements

1. **Token expiration** - Time-based limits
2. **Rate limiting** - Requests per minute
3. **IP whitelist** - Restrict token to IPs
4. **Webhook support** - Notify on events
5. **Stripe integration** - Payment-based tokens
6. **Admin dashboard** - Web UI for management

---

## Setup Guide

### 1. Set Admin Token

Add to Cloud Run environment variables (via Pulumi or console):

```bash
# Using gcloud
gcloud run services update karaoke-backend \
  --region us-central1 \
  --set-env-vars ADMIN_TOKENS="nomad,another-admin-token"

# Or add to Secret Manager
gcloud secrets create admin-tokens \
  --data-file=- <<< "nomad,another-admin-token"
```

### 2. Test Authentication

```bash
# Set your admin token
export TOKEN="nomad"
export BACKEND_URL="https://api.nomadkaraoke.com"

# Test authenticated endpoint
curl -H "Authorization: Bearer $TOKEN" \
  "$BACKEND_URL/api/jobs" | jq .
```

### 3. Create User Tokens (Admin Only)

Once admin API is implemented:

```bash
# Create a limited token for a user
curl -X POST "$BACKEND_URL/api/admin/tokens" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "token_value": "user-john-abc123",
    "token_type": "limited",
    "max_uses": 5
  }'

# Give "user-john-abc123" to the user
```

---

## Error Responses

### 401 Unauthorized

**No token provided:**
```json
{
  "detail": "Authentication required. Provide token via Authorization header or ?token= parameter"
}
```

**Invalid token:**
```json
{
  "detail": "Authentication failed: Invalid token"
}
```

**Token expired/revoked:**
```json
{
  "detail": "Authentication failed: Token has been revoked"
}
```

**Usage limit exceeded:**
```json
{
  "detail": "Authentication failed: Token usage limit exceeded"
}
```

### 403 Forbidden

**Admin access required:**
```json
{
  "detail": "Admin access required"
}
```

---

## Migration from Modal

The Modal app had a similar system with:
- Admin tokens (env vars) ✅ Migrated
- User sessions (session tokens) 🔜 Not yet implemented
- Token usage tracking ✅ Migrated
- Stripe integration 🔜 Not yet implemented

**Current differences:**
1. No session tokens (use access tokens directly)
2. No Stripe integration (planned for future)
3. No admin dashboard UI (planned for future)

---

## Development vs Production

### Development (Local)

```bash
# .env file
ADMIN_TOKENS=nomad,dev-token
```

### Production (Cloud Run)

```bash
# Secret Manager
gcloud secrets create admin-tokens \
  --data-file=- <<< "production-admin-token-here"

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding admin-tokens \
  --member="serviceAccount:karaoke-backend@nomadkaraoke.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Update backend to use secret
# (Already configured in config.py)
```

---

## Recommendation

**For now:** Use the simple "nomad" admin token  
**For production:** Generate strong random tokens:

```bash
# Generate a secure token
openssl rand -hex 32
# Example: 4f3d8a2b1c9e7f6a5d4c3b2a1f0e9d8c7b6a5d4c3b2a1f0e9d8c7b6a5d4c3b2a
```

---

## Summary

- ✅ **Token-based auth implemented**
- ✅ **Admin tokens via environment**
- ✅ **Usage tracking in Firestore**
- ✅ **Ready for simple deployment**
- 🔜 **Admin dashboard coming soon**
- 🔜 **Stripe integration planned**

**To use now:** Set `ADMIN_TOKENS=nomad` and authenticate with `Authorization: Bearer nomad`

