# Backend API Authentication - Remaining Work

## Overview

This document tracks the progress of adding authentication requirements to ALL backend API endpoints. Currently, many endpoints are publicly accessible without any authentication, which is a **major security vulnerability**.

## Completed Endpoints

### ✅ jobs.py (20 endpoints) - DONE
- All job management endpoints now require `Depends(require_auth)`
- Includes: create, get, list, delete, bulk_delete, review endpoints, instrumental selection, download, cancel, retry, logs

### ✅ file_upload.py (6 endpoints) - DONE
- upload_and_create_job
- create_job_with_upload_urls
- mark_uploads_complete
- create_job_from_url  
- create_finalise_only_job
- mark_finalise_uploads_complete

### ✅ audio_search.py (3 endpoints) - DONE
- search_audio
- get_audio_search_results
- select_audio_source

### ⚠️ review.py (12 endpoints) - PARTIAL (4/12 done)

**Completed:**
- get_correction_data ✅
- complete_review ✅
- add_lyrics ✅
- generate_preview_video ✅

**Remaining - Need Auth:**
- ❌ ping - Health check (maybe OK without auth?)
- ❌ get_audio_with_hash - Audio streaming for review UI
- ❌ get_audio_no_hash - Audio streaming for review UI  
- ❌ update_handlers - Correction handlers config
- ❌ get_preview_video - Preview video streaming
- ❌ submit_annotation - ML training data
- ❌ get_annotation_stats - ML stats
- ❌ (1 more endpoint not yet reviewed)

**Special Considerations:**
- Audio streaming endpoints (`get_audio_*`) are used by the review UI frontend. May need token passed via query param or special handling.
- `ping` endpoint is just a health check - possibly OK without auth

## Remaining Routes

### ❌ auth.py (8 endpoints) - TODO

These are auth-related endpoints themselves, so they have special requirements:

- `/auth/status` - Get OAuth credentials status (probably needs auth)
- `/auth/status/{service}` - Get service credential status (probably needs auth)
- `/auth/validate` - Validate credentials (probably needs auth)
- `/auth/youtube/device` - Start YouTube device auth (admin only)
- `/auth/youtube/device/{device_code}` - Poll YouTube auth (admin only)
- `/auth/gdrive/device` - Start GDrive device auth (admin only)
- `/auth/gdrive/device/{device_code}` - Poll GDrive auth (admin only)  
- (1 more endpoint)

**Recommendation:** Most/all of these should require admin auth (`Depends(require_admin)`)

### ❌ health.py (3 endpoints) - TODO

- `/health` - Basic health check (probably OK without auth for k8s/monitoring)
- `/health/detailed` - Detailed health (should require auth)
- `/readiness` - Readiness check for Cloud Run (probably OK without auth)

**Recommendation:**  
- Keep `/health` and `/readiness` unauthenticated for infrastructure monitoring
- Require auth for `/health/detailed` as it may expose sensitive info

### ❌ internal.py (6 endpoints) - CRITICAL

**All worker trigger endpoints - MUST have auth!** Currently using `X-Admin-Token` header but needs formal validation:

- `/internal/workers/audio` - Trigger audio worker
- `/internal/workers/lyrics` - Trigger lyrics worker
- `/internal/workers/screens` - Trigger screens worker
- `/internal/workers/video` - Trigger video worker
- `/internal/workers/render-video` - Trigger render worker
- `/internal/health` - Internal health (already has `require_admin`)

**Current State:** These endpoints check for `X-Admin-Token` in the request, but this should use the formal `require_admin` dependency.

**Recommendation:** ALL internal endpoints should use `Depends(require_admin)`

## Implementation Strategy

### Phase 1: Critical Security Fixes (HIGH PRIORITY)
1. ✅ Complete jobs.py, file_upload.py, audio_search.py
2. ❌ **Secure internal.py worker triggers** - These are the most critical as they allow arbitrary job manipulation
3. ❌ **Secure auth.py admin endpoints** - Prevent unauthorized OAuth credential management

### Phase 2: User-Facing Endpoints
1. ❌ Complete review.py endpoints (with special handling for streaming)
2. ❌ health.py detailed endpoint

### Phase 3: Testing & Documentation
1. ❌ Update frontend to always include auth token
2. ❌ Test all endpoints with/without auth
3. ❌ Update API documentation
4. ❌ Add integration tests for auth

## Testing Checklist

After adding auth to all endpoints:

- [ ] Test job creation without token → should return 401
- [ ] Test job listing without token → should return 401
- [ ] Test worker triggers without admin token → should return 401 or 403
- [ ] Test OAuth endpoints without admin token → should return 401 or 403
- [ ] Test health endpoint without token → should work (by design)
- [ ] Test authenticated requests with valid user token → should work
- [ ] Test authenticated requests with valid admin token → should work
- [ ] Update frontend auth flow to handle 401 errors gracefully

## Notes

- The authentication system is already implemented in `backend/api/dependencies.py`
- Functions available: `require_auth()`, `require_admin()`, `optional_auth()`
- Tokens are validated against `ADMIN_TOKENS` env var or Firestore user tokens
- Frontend already has token storage in localStorage via `AuthBanner` component

## Migration Path for Frontend

Once all endpoints require auth:

1. Frontend must obtain a token (either admin token or user token from a signup flow)
2. Token must be included in Authorization header: `Authorization: Bearer <token>`
3. Alternatively, some endpoints support `?token=<token>` query parameter
4. Update frontend API client to always include auth

##Frontend Update Required

Current state: Frontend has AuthBanner that prompts for token, but some endpoints worked without auth (security issue).  
New state: ALL endpoints require auth, so users MUST provide a token before using the app.

Update `frontend/lib/api.ts` to:
- Throw user-friendly error if token is missing when calling authenticated endpoints
- Handle 401 responses by prompting user to re-authenticate  
- Consider implementing a "logged out" state in the UI

