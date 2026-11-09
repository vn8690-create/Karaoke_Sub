# Buy Site Architecture Analysis

**Date**: 2025-12-29
**Status**: Analysis Complete - Consolidation Recommended

## Executive Summary

The current two-site architecture (buy.nomadkaraoke.com + gen.nomadkaraoke.com) has fundamental issues that break the user authentication flow. **Strong recommendation: Consolidate into a single site** to simplify the architecture, fix auth issues, and improve user experience.

## Critical Bugs Found

### 1. Token Storage Key Mismatch

**Location**: `buy-site/app/page.tsx:95` vs `frontend/lib/api.ts:18`

```javascript
// buy-site stores token as:
localStorage.setItem('nomad_karaoke_token', response.session_token);

// frontend reads token as:
localStorage.getItem('karaoke_access_token');
```

Even if the user stays on the same domain, this key mismatch means tokens wouldn't transfer.

### 2. Cross-Domain localStorage Isolation

**The fundamental problem**: localStorage is domain-specific. Data stored on `buy.nomadkaraoke.com` is completely inaccessible from `gen.nomadkaraoke.com`.

This means:
- Beta tester enrollment stores a session token on buy.nomadkaraoke.com
- Redirect to gen.nomadkaraoke.com loses the token
- User appears unauthenticated on the main app

### 3. Broken Beta Tester Flow

**Expected user experience**:
1. User fills beta form on buy site
2. Gets session token
3. Redirects to gen site
4. Is authenticated and can create karaoke

**Actual experience**:
1. User fills beta form on buy site
2. Token stored in buy site's localStorage
3. Redirects to gen site (different domain!)
4. Token is NOT accessible
5. User sees "Authentication Required" message
6. User is confused

## Architecture Comparison

### Current: Two Sites

```
buy.nomadkaraoke.com (Cloudflare Pages)     gen.nomadkaraoke.com (GitHub Pages)
├── Landing page                            ├── Main app
├── Pricing                                 ├── Job creation
├── Beta enrollment                         ├── Job management
├── Stripe checkout redirect                ├── Auth dialog
└── localStorage: nomad_karaoke_token       └── localStorage: karaoke_access_token
         ↓                                           ↑
         └───── REDIRECT (token lost!) ──────────────┘
```

**Problems**:
- Cross-domain auth doesn't work with localStorage
- Two separate codebases to maintain
- Two separate deployments (Cloudflare + GitHub Pages)
- Duplicate dependencies (React, Next.js, Tailwind on both)
- Confusing user navigation between sites
- "Already have credits? Sign in" link goes to unauthenticated state

### Proposed: Single Site

```
gen.nomadkaraoke.com (GitHub Pages)
├── Landing page (new /welcome or / route)
├── Pricing (/pricing or landing page section)
├── Beta enrollment (modal or dedicated route)
├── Stripe checkout redirect
├── Main app (/app or /)
├── Job creation
├── Job management
└── localStorage: karaoke_access_token (single key)
```

**Benefits**:
- Single domain = single localStorage = no auth issues
- One codebase to maintain
- One deployment pipeline
- Shared components and styles
- Clear user navigation
- Consistent branding/experience

## Migration Path

### Phase 1: Integrate Landing/Pricing into Main Frontend

1. Create new routes in `frontend/`:
   - `/welcome` - Landing page (can be set as default for unauthenticated users)
   - `/pricing` - Pricing section (or integrate into landing)

2. Move buy-site components to frontend:
   - Copy pricing UI from `buy-site/app/page.tsx`
   - Copy beta enrollment form
   - Reuse existing auth components

3. Update frontend routing:
   - Unauthenticated users → Landing page
   - Authenticated users → Main app

### Phase 2: Update Auth Flow

1. Fix token key to be consistent:
   ```javascript
   localStorage.setItem('karaoke_access_token', token);
   ```

2. Beta enrollment flow:
   - Show form on gen.nomadkaraoke.com directly
   - On success, store token and redirect to app (same domain)
   - User is immediately authenticated

### Phase 3: Cleanup

1. Delete buy-site directory
2. Remove Cloudflare Pages deployment
3. Delete buy.nomadkaraoke.com DNS record (or redirect to gen)
4. Update CI/CD to remove buy-site jobs

## Files to Delete

```
buy-site/                          # Entire directory
├── app/
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx
├── lib/
│   └── api.ts
├── next.config.mjs
├── package.json
├── package-lock.json
├── postcss.config.mjs
├── tailwind.config.js
└── tsconfig.json
```

## CI/CD Changes

In `.github/workflows/ci.yml`:
- Remove `buy_site` from path filters
- Remove `deploy-buy-site` job

## DNS/Infrastructure Changes

- Remove or redirect `buy.nomadkaraoke.com` → `gen.nomadkaraoke.com`
- Delete Cloudflare Pages project `nomadkaraoke-buy`

## Alternative Solutions (Not Recommended)

### Option A: Shared Auth via URL Token

Pass token in URL when redirecting:
```
https://gen.nomadkaraoke.com?token=xxx
```

**Problems**:
- Token in URL is a security risk (logs, referrer headers)
- Requires frontend to parse and clear URL
- Still two codebases to maintain

### Option B: Cookie with Shared Domain

Use cookies with `domain=.nomadkaraoke.com`:
```javascript
document.cookie = `session=${token}; domain=.nomadkaraoke.com; secure; samesite=strict`;
```

**Problems**:
- Still two codebases to maintain
- Cookie handling adds complexity
- CORS issues with API calls

### Option C: Subdomain with Shared localStorage

If both sites were on same origin (e.g., `gen.nomadkaraoke.com/buy`), localStorage would be shared.

**This is essentially the consolidation approach** - just with a different URL structure.

## Testing the Fix

Created Playwright e2e test: `frontend/e2e/production-user-journey.spec.ts`

Key test scenarios:
1. Landing page loads correctly
2. Beta enrollment validation works
3. Token storage is consistent
4. Auth persists after redirect
5. Cross-domain issues documented (will fail until fixed)

Run tests:
```bash
cd frontend
npx playwright test production-user-journey --config=playwright.production.config.ts --headed
```

## Email Testing for E2E

For full end-to-end magic link testing, options evaluated:

1. **MailSlurp** - Free tier (50 emails/month), good API
   - Set `MAILSLURP_API_KEY` env var
   - Creates temporary inbox
   - Waits for magic link email
   - Extracts and follows link

2. **Mailosaur** - Paid, very reliable

3. **Gmail API** - Works with user's personal Gmail

For now, tests document the flows but skip actual email verification unless `MAILSLURP_API_KEY` is set.

## Recommendation

**Strongly recommend consolidating to a single site** because:

1. **Fixes fundamental auth bug** - localStorage sharing isn't possible cross-domain
2. **Simpler architecture** - One codebase, one deployment
3. **Better UX** - No confusing navigation between sites
4. **Easier maintenance** - Single set of dependencies
5. **Consistent branding** - Same styles/components everywhere
6. **Aligns with PRODUCT-VISION.md** - Single gen.nomadkaraoke.com as the product

## References

- Product Vision: `docs/PRODUCT-VISION.md`
- Frontend auth: `frontend/lib/auth.ts`
- Frontend API: `frontend/lib/api.ts`
- Buy site page: `buy-site/app/page.tsx`
- E2E tests: `frontend/e2e/production-user-journey.spec.ts`

## Sources

Research on email testing:
- [Mailosaur Playwright guide](https://mailosaur.com/blog/playwright-email-verification)
- [MailSlurp Next Auth testing](https://www.mailslurp.com/guides/test-next-auth-magic-links/)
- [Better Stack signup testing guide](https://betterstack.com/community/guides/testing/playwright-signup-login/)
