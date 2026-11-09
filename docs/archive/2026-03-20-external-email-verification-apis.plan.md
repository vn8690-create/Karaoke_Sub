# Plan: External Email Verification APIs (DeBounce + verifymail.io)

**Created:** 2026-03-20
**Branch:** feat/sess-20260320-1114-investigate-user-abuse
**Status:** Draft

## Overview

Replace the static disposable domain blocklist (community GitHub list of ~5,339 domains) with real-time API checks using two external services. Our investigation found that the static list misses many disposable domains — 4 out of 10 disposable signups in a 4-day period got through.

**Strategy: Tiered checking to minimize cost and latency.**

```
Email submitted
  → Step 0: Well-known provider? (gmail, yahoo, etc.) → skip all checks
  → Step 1: Static blocklist check (existing, instant, free)
  → Step 2: Verified clean in last 7 days? → skip API calls
  → Step 3: DeBounce API check (free, <50ms)
  → Step 4: verifymail.io API check (paid, only if DeBounce says clean)
  → Any says disposable → auto-learn domain + reject with 422
  → All say clean → persist clean result for 7 days
```

This means verifymail.io is only called for emails that pass both the static list AND DeBounce — minimizing paid API usage to only the tricky edge cases where it adds value.

## Requirements

- [ ] Add DeBounce API client (free, no auth, GET `https://disposable.debounce.io/?email={email}`)
- [ ] Add verifymail.io API client (paid, GET `https://verifymail.io/api/{email}?key={key}`)
- [ ] Store verifymail.io API key in GCP Secret Manager (secret name: `verifymail-api-key`)
- [ ] Wire both checks into `is_disposable_domain()` as a fallback after the static list check
- [ ] Handle API failures gracefully — if external APIs are down, fall back to static list only (don't block real users)
- [ ] Add timeout protection (2s per API call max)
- [ ] Auto-learn: when an external API flags a domain, add it to `manual_domains` so future checks don't need the API call
- [ ] Log API results for monitoring
- [ ] Unit tests with mocked HTTP calls
- [ ] Integration test verifying the full magic link rejection flow

## Technical Approach

### Where to add the logic

The change is concentrated in `EmailValidationService.is_disposable_domain()` (line 171 of `email_validation_service.py`). Currently it only checks the static set. We'll add external API calls as a fallback.

### Tiered check flow in `is_disposable_domain()`

```python
def is_disposable_domain(self, email: str) -> bool:
    domain = email.lower().split("@")[-1]

    # Tier 0: Well-known providers (gmail, yahoo, etc.) — skip everything
    if domain in WELL_KNOWN_PROVIDERS:
        return False

    # Tier 1: Static blocklist (instant, always available)
    if domain in config["disposable_domains"]:
        return True

    # Tier 2: Recently verified clean? (skip API calls)
    if self._is_domain_verified_clean(domain):
        return False

    # Tier 3: DeBounce API (free, fast)
    debounce_result = self._check_debounce(email)
    if debounce_result is True:
        self._auto_learn_domain(domain)  # Persist to manual_domains
        return True

    # Tier 4: verifymail.io (paid, only if DeBounce says clean)
    if debounce_result is False:  # Only escalate if DeBounce gave a definitive "no"
        verifymail_result = self._check_verifymail(email)
        if verifymail_result is True:
            self._auto_learn_domain(domain)
            return True

    # Both APIs say clean (or errored) — persist clean result
    if debounce_result is False:
        self._mark_domain_clean(domain)

    return False
```

### Auto-learn mechanism

When an external API flags a domain as disposable, we add it to `manual_domains` in Firestore. This means:
- The domain is blocked immediately for all future requests via the static check
- No further API calls needed for that domain
- The allowlist still overrides if we get false positives

### Error handling

- API timeout (2s) or network error → treat as "unknown" (not disposable), log warning
- DeBounce error → skip to verifymail.io
- Both APIs error → fall back to static list only
- Never block a real user because an external API is down

### Secret management

Follow existing pattern: `settings.get_secret("verifymail-api-key")`. For local dev, set `VERIFYMAIL_API_KEY` env var. For production, create the secret in GCP Secret Manager.

### Caching strategy

Two layers of caching to minimize API calls:

**Disposable domains (persistent):** Auto-learn adds flagged domains to `manual_domains` in Firestore. Once learned, that domain is blocked via the static list forever — no API call needed again. This handles the "block" case.

**Clean domains (persistent):** Store verified-clean domains in a `verified_clean_domains` dict in the blocklist Firestore doc, keyed by domain with a `checked_at` timestamp. Domains verified clean within the last 7 days skip external API calls. This gets loaded into the existing 5-minute blocklist cache, so adds zero extra Firestore reads. Periodic cleanup removes entries older than 7 days (during the daily sync job).

**In-memory (both):** The existing 5-minute `_blocklist_cache` TTL already covers this — both `manual_domains` and `verified_clean_domains` are loaded with the blocklist config.

**Net effect:** For a given unknown domain, external APIs are called at most once per 7 days. Well-known providers (gmail, yahoo, etc.) skip APIs entirely via the short-circuit set.

### Performance considerations

- Static list check is instant — most legitimate emails (gmail.com, yahoo.com, etc.) short-circuit here without any API call
- DeBounce adds <50ms for unknown domains
- verifymail.io adds ~200-500ms but is only called for domains that pass both static + DeBounce
- In practice, the vast majority of signups will never hit an external API
- `httpx` with connection pooling for efficient HTTP (already a project dependency)

## Implementation Steps

### Step 1: Create the verifymail.io secret in GCP Secret Manager

```bash
echo -n "YOUR_VERIFYMAIL_API_KEY" | \
  gcloud secrets create verifymail-api-key \
    --project=nomadkaraoke \
    --data-file=-
```

No Pulumi change needed — this is a runtime secret, not infrastructure. The Cloud Run service account already has Secret Manager access.

### Step 2: Add external API checking to `EmailValidationService`

**File:** `backend/services/email_validation_service.py`

Add three private methods and modify `is_disposable_domain()`:

- `_check_debounce(email: str) -> Optional[bool]` — calls DeBounce API, returns True/False/None (None = error)
- `_check_verifymail(email: str) -> Optional[bool]` — calls verifymail.io API, returns True/False/None
- `_auto_learn_domain(domain: str)` — adds domain to `manual_domains` in Firestore (fire-and-forget, non-blocking)
- `_mark_domain_clean(domain: str)` — adds domain to `verified_clean_domains` in Firestore with `checked_at` timestamp
- `_is_domain_verified_clean(domain: str) -> bool` — checks `verified_clean_domains` cache, returns True if verified within 7 days
- Modify `is_disposable_domain()` to check verified-clean cache before API calls, and call external APIs as fallback
- Modify `get_blocklist_config()` to load `verified_clean_domains` into the cache

Use `httpx` (already in dependencies) for HTTP calls with:
- 2-second timeout per request
- Connection pooling via module-level client
- Structured logging of API calls and results

### Step 3: Add well-known provider skip list

Domains like `gmail.com`, `yahoo.com`, `hotmail.com`, `outlook.com`, etc. should never hit external APIs — they're obviously not disposable. Add a `WELL_KNOWN_PROVIDERS` set and short-circuit before API calls.

### Step 4: Unit tests

**File:** `backend/tests/test_email_validation_service.py`

Add tests for:
- DeBounce returns disposable=true → domain auto-learned, returns True
- DeBounce returns disposable=false, verifymail returns disposable=true → domain auto-learned, returns True
- Both APIs return clean → returns False
- DeBounce timeout → falls through to verifymail
- Both APIs timeout → falls back to static list (returns False)
- Well-known providers skip API calls entirely
- Auto-learn adds domain to manual_domains in Firestore
- verifymail.io API key missing → skip verifymail, only use DeBounce

### Step 5: Integration test for magic link rejection

**File:** `backend/tests/test_email_validation_integration.py`

Add test: email from domain not in static list but flagged by external API → magic link returns 422 with `disposable_email_not_allowed`.

### Step 6: Version bump

Bump `tool.poetry.version` in `pyproject.toml`.

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `backend/services/email_validation_service.py` | Modify | Add `_check_debounce()`, `_check_verifymail()`, `_auto_learn_domain()`, modify `is_disposable_domain()` |
| `backend/tests/test_email_validation_service.py` | Modify | Add unit tests for external API checks |
| `backend/tests/test_email_validation_integration.py` | Modify | Add integration test for API-based rejection |
| `pyproject.toml` | Modify | Version bump |

## Testing Strategy

- **Unit tests**: Mock `httpx` responses for both APIs. Test all branches: success, timeout, error, auto-learn.
- **Integration tests**: Mock HTTP at the transport level, verify full magic link → 422 flow.
- **Manual verification**: After deploy, attempt signup with a known-disposable domain not in the static list (e.g., `test@lxbeta.com`) and confirm rejection.

## Open Questions

- [x] ~~Which service to use?~~ → Both, tiered (DeBounce free primary, verifymail.io paid secondary)
- [x] ~~Cache API results?~~ → Yes. Blocked domains auto-learn to `manual_domains` (permanent). Clean domains persist to `verified_clean_domains` with 7-day TTL. Both loaded via existing 5-min blocklist cache.
- [ ] Should we add monitoring/alerting for external API failures? **Recommendation: Log warnings for now, add alerting later if needed.**

## Rollback Plan

The external API checks are additive — they only add domains to the block list, never remove them. To rollback:
1. Revert the code change (external APIs stop being called)
2. Static blocklist continues to work as before
3. Any auto-learned domains remain in `manual_domains` (can be removed via admin API if false positives)
