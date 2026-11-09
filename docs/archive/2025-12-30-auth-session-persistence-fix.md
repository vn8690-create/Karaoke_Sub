# Auth Session Persistence Fix

**Date**: 2025-12-30
**PR**: #130

## Problem

Users were being logged out immediately after logging in via magic link:
1. User clicks magic link, successfully authenticates
2. User is shown as logged in
3. On page reload (or even without reload), API calls return 401 Unauthorized
4. Session exists and is valid in Firestore, but requests fail

## Root Causes

### 1. Frontend Token Caching Bug

`frontend/lib/api.ts` cached the auth token in a module-level variable:

```javascript
// OLD - Buggy
let accessToken: string | null = null;
if (typeof window !== 'undefined') {
  accessToken = localStorage.getItem('karaoke_access_token');
}

export function getAccessToken(): string | null {
  return accessToken;  // Returns cached value, may be stale
}
```

**Issue**: In Next.js, if the module initializes before localStorage is properly hydrated, or if there's any module caching behavior, the cached value could be stale or null.

**Fix**: Always read fresh from localStorage:

```javascript
export function getAccessToken(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('karaoke_access_token');
  }
  return null;
}
```

### 2. Backend Timezone Comparison Bug (Main Culprit)

`backend/services/user_service.py` compared naive and timezone-aware datetimes:

```python
# OLD - Buggy
now = datetime.utcnow()  # Naive datetime (no timezone)
if session.last_activity_at < inactivity_limit:  # last_activity_at from Firestore is TZ-aware!
    # TypeError: can't compare offset-naive and offset-aware datetimes
```

**What happens**: Firestore stores datetimes as timezone-aware. The first time a session is validated, `last_activity_at` is updated in Firestore. On subsequent reads, Firestore returns it as timezone-aware. Comparing this against `datetime.utcnow()` (naive) raises TypeError, caught by the exception handler, returning "An error occurred during validation" → 401.

**Fix**: Use timezone-aware datetimes throughout:

```python
now = datetime.now(timezone.utc)

# Normalize session datetimes to be timezone-aware
expires_at = session.expires_at
if expires_at.tzinfo is None:
    expires_at = expires_at.replace(tzinfo=timezone.utc)
```

## Additional Changes

### Firestore Indexes Added to Pulumi

The `scripts/investigate_user.py` script requires composite indexes. These were created manually and are now tracked in Pulumi IaC:

- `jobs`: user_email + created_at (user job lists)
- `jobs`: status + created_at (admin/system job lists)
- `sessions`: is_active + user_email + created_at (active session queries)
- `magic_links`: email + created_at (magic link history)

### Script Deprecation Fix

Fixed `datetime.utcnow()` deprecation warning in `scripts/investigate_user.py`.

## Debugging Tools Used

1. **Direct Firestore query** to verify session exists and is valid
2. **Browser DevTools Network tab** to see 401 responses with valid-looking Authorization header
3. **`scripts/investigate_user.py`** to check user's sessions, jobs, magic links

## Key Insight

The session was valid in the database the entire time. The bug was in the *validation code*, not in session creation or storage. Always check the validation logic when auth fails unexpectedly.
