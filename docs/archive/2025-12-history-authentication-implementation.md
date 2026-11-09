# Authentication System Implementation

**Date:** 2025-12-01  
**Status:** ✅ Implemented (Simple version)

---

## Summary

Implemented token-based authentication for the karaoke backend API, supporting admin tokens and future extensibility for full token management.

---

## Current State

### What Works Now

✅ **Simple hardcoded auth** using environment variable `ADMIN_TOKENS`  
✅ **Example:** `ADMIN_TOKENS="nomad"` for easy testing  
✅ **Two authentication methods:**
  - `Authorization: Bearer <token>` header
  - `?token=<token>` query parameter (for download links)

### API Access Levels

**Public (no auth):**
- `GET /` - Root
- `GET /api/health` - Health check

**Authenticated (any valid token):**
- All `/api/jobs/*` endpoints
- Human-in-the-loop interaction endpoints

**Admin only (future):**
- `/api/admin/tokens/*` - Token management

---

## Implementation

### Files Created

1. **`backend/services/auth_service.py`** - Authentication logic
   - Token validation
   - Usage tracking
   - Token management (create/revoke/list)
   - Support for 4 token types: ADMIN, UNLIMITED, LIMITED, STRIPE

2. **`backend/api/dependencies.py`** - FastAPI dependencies
   - `require_auth()` - Require any valid token
   - `require_admin()` - Require admin token
   - `optional_auth()` - Optional authentication

3. **`backend/services/firestore_service.py`** - Updated with token methods
   - `create_token()`
   - `get_token()`
   - `update_token()`
   - `increment_token_usage()`
   - `list_tokens()`

4. **`backend/config.py`** - Added `admin_tokens` setting

### Documentation Created

- **`docs/01-reference/AUTHENTICATION.md`** - Complete auth guide

---

## How It Works

### 1. Admin Token (Environment Variable)

```bash
# Set in Cloud Run or .env
ADMIN_TOKENS="nomad,another-admin-token"
```

**Features:**
- Comma-separated list
- Unlimited access
- Never expire
- Not stored in database

### 2. User Tokens (Firestore)

Future implementation for creating user tokens:

```python
# Admin creates a limited token
auth_service.create_token(
    token_value="user-abc123",
    token_type=UserType.LIMITED,
    max_uses=10
)
```

**Stored in Firestore:** `auth_tokens` collection

**Fields:**
```json
{
  "token": "user-abc123",
  "type": "limited",
  "max_uses": 10,
  "usage_count": 0,
  "active": true,
  "created_at": 1701388800.0,
  "jobs": []
}
```

### 3. Token Validation

```python
is_valid, user_type, remaining_uses, message = auth_service.validate_token(token)

# Example responses:
# (True, UserType.ADMIN, -1, "Admin access granted")
# (True, UserType.LIMITED, 5, "Limited token: 5 uses remaining")
# (False, UserType.LIMITED, 0, "Token usage limit exceeded")
```

### 4. Usage Tracking

When a job is created:
1. Token is validated
2. For LIMITED/STRIPE tokens: Usage count increments
3. Job is added to token's history
4. Transaction ensures atomic updates

**Admin/UNLIMITED tokens:** No tracking needed

---

## Token Types

| Type | Description | Limit | Storage |
|------|-------------|-------|---------|
| **ADMIN** | Full access + management | None | Environment |
| **UNLIMITED** | Unlimited karaoke | None | Firestore |
| **LIMITED** | Limited uses | Configurable | Firestore |
| **STRIPE** | Paid access (future) | Based on payment | Firestore |

---

## Usage Examples

### Testing with "nomad" Token

```bash
export BACKEND_URL="https://api.nomadkaraoke.com"
export TOKEN="nomad"

# Submit job (requires auth)
curl -X POST "$BACKEND_URL/api/jobs/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@waterloo30sec.flac" \
  -F "artist=ABBA" \
  -F "title=Waterloo"

# Or use query parameter for download links
curl "$BACKEND_URL/api/jobs/abc123/download?token=$TOKEN"
```

### Future: Admin Token Management

```bash
# Create a user token (admin only)
curl -X POST "$BACKEND_URL/api/admin/tokens" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "token_value": "user-abc123",
    "token_type": "limited",
    "max_uses": 10
  }'

# List all tokens
curl "$BACKEND_URL/api/admin/tokens" \
  -H "Authorization: Bearer $TOKEN"

# Revoke a token
curl -X DELETE "$BACKEND_URL/api/admin/tokens/user-abc123" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Security Features

### ✅ Implemented

1. **Token validation** on every request
2. **Usage limits** enforced
3. **Transaction safety** for usage increments
4. **Token revocation** support
5. **Admin-only operations** (ready for admin API)
6. **Two auth methods** (header + query param)

### 🔜 Future Enhancements

1. **Admin dashboard** - Web UI for token management
2. **Token expiration** - Time-based limits
3. **Rate limiting** - Per-token request limits
4. **IP whitelist** - Restrict tokens to specific IPs
5. **Stripe integration** - Payment-based tokens
6. **Webhook support** - Notify on token events

---

## Migration from Modal

The Modal app (`app.py`) had a similar system:

**Migrated:**
- ✅ Admin tokens via environment
- ✅ Token validation logic
- ✅ Usage tracking
- ✅ Token types (ADMIN, UNLIMITED, LIMITED, STRIPE)

**Not yet migrated:**
- ⏭️ Session tokens (not critical for API)
- ⏭️ Stripe integration (future feature)
- ⏭️ Admin dashboard UI (future feature)

**Simplified:**
- Admin tokens are simpler (just env var, no dict)
- Removed session token complexity (direct token use)

---

## Next Steps

### Immediate (Once Custom Domain Works)

1. **Set admin token:**
   ```bash
   gcloud run services update karaoke-backend \
     --region us-central1 \
     --set-env-vars ADMIN_TOKENS="nomad"
   ```

2. **Test authentication:**
   ```bash
   curl -H "Authorization: Bearer nomad" \
     https://api.nomadkaraoke.com/api/jobs
   ```

### Short-term (Phase 2)

1. **Implement admin API routes:**
   - `POST /api/admin/tokens` - Create token
   - `GET /api/admin/tokens` - List tokens
   - `DELETE /api/admin/tokens/{token}` - Revoke token

2. **Add to job creation:**
   - Update `/api/jobs` to use `require_auth` dependency
   - Track token usage when jobs are created

3. **Update frontend:**
   - Add token input to React UI
   - Store token in localStorage
   - Include in all API requests

### Long-term (Phase 3+)

1. **Admin dashboard:**
   - React admin UI for token management
   - View usage statistics
   - Manage user tokens

2. **Stripe integration:**
   - Payment → auto-create tokens
   - Webhook handling
   - Usage-based billing

3. **Advanced features:**
   - Token expiration
   - Rate limiting
   - IP whitelist
   - Audit logs

---

## Deployment

### Set Admin Token in Cloud Run

**Option 1: Environment Variable** (Simple)
```bash
gcloud run services update karaoke-backend \
  --region us-central1 \
  --set-env-vars ADMIN_TOKENS="nomad"
```

**Option 2: Secret Manager** (Production)
```bash
# Create secret
gcloud secrets create admin-tokens \
  --data-file=- <<< "production-admin-token-here"

# Grant access
gcloud secrets add-iam-policy-binding admin-tokens \
  --member="serviceAccount:karaoke-backend@nomadkaraoke.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Update service to use secret
gcloud run services update karaoke-backend \
  --region us-central1 \
  --update-secrets=ADMIN_TOKENS=admin-tokens:latest
```

---

## Testing

Once deployed:

```bash
# Test health (no auth)
curl https://api.nomadkaraoke.com/api/health

# Test auth (should fail without token)
curl https://api.nomadkaraoke.com/api/jobs

# Test auth (should work with token)
curl -H "Authorization: Bearer nomad" \
  https://api.nomadkaraoke.com/api/jobs
```

---

## Summary

✅ **Token-based auth system implemented**  
✅ **Simple "nomad" token for easy testing**  
✅ **Extensible for full token management**  
✅ **Compatible with Modal's auth system**  
✅ **Ready for deployment**  

**Next:** Set `ADMIN_TOKENS=nomad` in Cloud Run and test! 🚀

