# API Key Management System - Phase 2 Plan

**Status:** Planned (Phase 1 complete)
**Created:** 2024-12-29

## Background

Phase 1 (completed) established that all auth_tokens must have a `user_email` field for job ownership tracking. This eliminated anonymous token authentication and ensures all jobs have proper attribution.

Phase 2 will add self-service API key management for B2B/bulk karaoke generation users.

## Current State (After Phase 1)

- All `auth_tokens` in Firestore require a `user_email` field
- Admin tokens (from `ADMIN_TOKENS` env var) are associated with `admin@nomadkaraoke.com`
- Session tokens (magic link auth) have user_email from the authenticated user
- Jobs created via any auth method are attributed to the token's user_email

## Phase 2: Self-Service API Key Management

### New Endpoints

```
POST   /api/keys              - Generate new API key for current user
GET    /api/keys              - List user's API keys (masked)
DELETE /api/keys/{key_id}     - Revoke an API key
```

### API Key Schema (auth_tokens collection)

```python
{
    "token": "sk_live_...",           # The API key (document ID)
    "type": "api_key",                # UserType.API_KEY
    "user_email": "user@example.com", # Owner's email (required)
    "api_key_id": "key_abc123",       # Short ID for display/revocation
    "name": "Production Server",       # User-provided name
    "max_uses": -1,                   # -1 = unlimited, or specific limit
    "usage_count": 0,                 # Current usage
    "active": True,                   # Can be revoked
    "created_at": 1703894400,         # Unix timestamp
    "last_used": null,                # Last usage timestamp
    "expires_at": null,               # Optional expiration
    "ip_allowlist": [],               # Optional IP restrictions
    "jobs": []                        # Job history [{job_id, created_at}]
}
```

### Implementation Details

#### 1. Generate API Key Endpoint

```python
@router.post("/keys", response_model=APIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    auth_result: AuthResult = Depends(require_auth)
) -> APIKeyResponse:
    """
    Generate a new API key for the authenticated user.

    The full key is only shown once at creation time.
    """
    # Require authenticated user (not anonymous)
    if not auth_result.user_email:
        raise HTTPException(403, "Must be logged in to create API keys")

    # Check user's API key limit (e.g., max 5 per user)
    existing_keys = firestore.list_user_api_keys(auth_result.user_email)
    if len(existing_keys) >= settings.max_api_keys_per_user:
        raise HTTPException(400, f"Maximum {settings.max_api_keys_per_user} API keys allowed")

    # Generate secure key
    key_id = shortuuid.uuid()[:8]
    token = f"sk_{'live' if settings.environment == 'production' else 'test'}_{secrets.token_urlsafe(32)}"

    # Store in Firestore
    firestore.create_token(token, {
        "token": token,
        "type": "api_key",
        "user_email": auth_result.user_email,
        "api_key_id": key_id,
        "name": request.name or f"API Key {key_id}",
        "max_uses": request.max_uses or -1,
        "usage_count": 0,
        "active": True,
        "created_at": time.time(),
        "ip_allowlist": request.ip_allowlist or [],
        "jobs": []
    })

    return APIKeyResponse(
        key_id=key_id,
        token=token,  # Only shown once!
        name=request.name,
        created_at=datetime.utcnow(),
        message="Save this key - it won't be shown again"
    )
```

#### 2. List API Keys Endpoint

```python
@router.get("/keys", response_model=List[APIKeyInfo])
async def list_api_keys(
    auth_result: AuthResult = Depends(require_auth)
) -> List[APIKeyInfo]:
    """List user's API keys with masked tokens."""
    keys = firestore.list_user_api_keys(auth_result.user_email)

    return [
        APIKeyInfo(
            key_id=k["api_key_id"],
            name=k.get("name"),
            token_prefix=k["token"][:12] + "...",  # Masked
            created_at=datetime.fromtimestamp(k["created_at"]),
            last_used=datetime.fromtimestamp(k["last_used"]) if k.get("last_used") else None,
            usage_count=k.get("usage_count", 0),
            max_uses=k.get("max_uses", -1),
            is_active=k.get("active", True)
        )
        for k in keys
    ]
```

#### 3. Revoke API Key Endpoint

```python
@router.delete("/keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    auth_result: AuthResult = Depends(require_auth)
) -> dict:
    """Revoke an API key."""
    # Find key by key_id
    key = firestore.get_api_key_by_id(key_id)

    if not key:
        raise HTTPException(404, "API key not found")

    # Verify ownership
    if key["user_email"] != auth_result.user_email and not auth_result.is_admin:
        raise HTTPException(403, "Not authorized to revoke this key")

    # Revoke (soft delete)
    firestore.update_token(key["token"], {"active": False})

    return {"status": "revoked", "key_id": key_id}
```

### Firestore Indexes Needed

```json
{
  "collectionGroup": "auth_tokens",
  "fields": [
    { "fieldPath": "user_email", "order": "ASCENDING" },
    { "fieldPath": "type", "order": "ASCENDING" },
    { "fieldPath": "created_at", "order": "DESCENDING" }
  ]
}
```

### Models

```python
class CreateAPIKeyRequest(BaseModel):
    name: Optional[str] = None
    max_uses: Optional[int] = None  # -1 = unlimited
    ip_allowlist: Optional[List[str]] = None

class APIKeyResponse(BaseModel):
    key_id: str
    token: str  # Full token - only shown at creation
    name: Optional[str]
    created_at: datetime
    message: str

class APIKeyInfo(BaseModel):
    key_id: str
    name: Optional[str]
    token_prefix: str  # Masked token
    created_at: datetime
    last_used: Optional[datetime]
    usage_count: int
    max_uses: int
    is_active: bool
```

### Frontend Integration

Add "API Keys" section to user settings page:

1. **List view**: Show all keys with name, prefix, usage, created date
2. **Create button**: Opens modal to name new key, shows full key once
3. **Revoke button**: Confirmation dialog, then revokes key
4. **Copy button**: Copy masked key prefix (for reference)

### Security Considerations

1. **Rate limiting**: Limit key creation (e.g., 5 keys max per user)
2. **Key rotation**: Encourage periodic rotation, show last_used date
3. **IP allowlist**: Optional IP restriction for production keys
4. **Audit logging**: Log all key creation/revocation events
5. **Key prefix**: Use `sk_live_` / `sk_test_` prefix for identification
6. **No key retrieval**: Full key only shown at creation, cannot be retrieved

### Migration

Existing auth_tokens without `user_email`:
- Already handled in Phase 1 - tokens without user_email are rejected
- The one existing admin token should be updated in Firestore to have `user_email: "admin@nomadkaraoke.com"`

### Testing

1. Create key as authenticated user
2. Use key to create job - verify job.user_email matches key owner
3. List keys - verify only own keys shown
4. Revoke key - verify subsequent requests fail
5. Test IP allowlist enforcement (if implemented)

## Timeline

Phase 2 can be implemented when there's B2B demand. Estimated effort: 1-2 days.

## Open Questions

1. Should API keys have expiration dates by default?
2. What usage limits should free users have?
3. Should we support webhook notifications for key events?
