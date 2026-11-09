# E2E Test Suite Consolidation Plan

**Date**: December 29, 2025
**Status**: Completed
**Author**: Claude (with Andrew's direction)

---

## Executive Summary

This document outlines a plan to consolidate and improve the frontend E2E test suite. The goal is to create:

1. **A single, comprehensive production E2E test** that exercises the full user journey with real APIs (manual execution only)
2. **A robust regression test suite** using recorded API fixtures that can run in CI without hitting production

---

## Current State Analysis

### Test File Inventory

| File | Lines | Purpose | Test Song | Runs Against |
|------|-------|---------|-----------|--------------|
| `production-user-journey.spec.ts` | 533 | Landing page, pricing, beta enrollment, auth, token persistence | `piri/dog` (defined but unused) | Production |
| `production-e2e.spec.ts` | 319 | Full 8-step karaoke generation flow | `piri/dog` ✅ | Production |
| `karaoke-generation.spec.ts` | 570 | App UI, job interactions, search, audio selection | ABBA, LCMDF, Rick Astley ❌ | Local dev (proxy to prod) |
| `screenshot-audio-dialog.spec.ts` | 297 | Audio dialog screenshot capture | Radiohead ❌ | Local dev |
| `mobile-responsiveness.spec.ts` | 163 | Mobile viewport testing | N/A | Local dev |
| `fixtures-example.spec.ts` | 119 | Demo of mock fixture system | N/A (mocked) | Local dev |

**Total: 6 test files, ~2000 lines of test code**

### Playwright Configurations

| Config | Base URL | Test Pattern | Purpose |
|--------|----------|--------------|---------|
| `playwright.config.ts` | `localhost:3000` | All `e2e/*.spec.ts` | Local dev with proxy to prod API |
| `playwright.production.config.ts` | `gen.nomadkaraoke.com` | `production-*.spec.ts` only | Direct production testing |

### Key Issues Identified

#### 1. Inconsistent Test Songs
Only `production-e2e.spec.ts` uses the designated test song (`piri - dog`). Other files use:
- ABBA - Waterloo
- LCMDF - Take Me To The Mountains
- Rick Astley - Never Gonna Give You Up
- Radiohead - Creep

This causes unnecessary flacfetch API calls and tracker lookups instead of using cached results.

#### 2. Overlapping Test Coverage
- `production-user-journey.spec.ts` and `karaoke-generation.spec.ts` both test homepage/job UI
- `production-e2e.spec.ts` duplicates parts of both files
- Auth helper functions are copy-pasted across multiple files

#### 3. Unused Fixture System
There's a sophisticated mock/recording system in `fixtures/`:
- `recorder.ts` - Records real API calls
- `mock-server.ts` - Replays recorded fixtures
- `test-helper.ts` - Unified setup interface
- `review-cli.ts` - CLI to review/approve recordings

Only `fixtures-example.spec.ts` uses this system. The original intent was to:
1. Run production tests to capture API responses
2. Store those responses as fixtures
3. Replay them for offline regression testing

This was never completed because the full production flow wasn't working yet.

#### 4. CI Only Runs Unit Tests
From `.github/workflows/ci.yml`:
```yaml
name: "Frontend - Unit Tests"
run: npm run test:ci  # Jest unit tests only
```
No E2E tests run in CI currently.

#### 5. Auth Token Configuration
- `.env.local` contains `KARAOKE_ACCESS_TOKEN` (session token hash)
- Also contains `MAILSLURP_API_KEY` for email testing
- Token is loaded by both Playwright configs via custom env file parsing

### Fixture System Architecture

```
frontend/e2e/fixtures/
├── index.ts           # Exports all modules
├── types.ts           # TypeScript interfaces
├── recorder.ts        # Intercepts & records API calls
├── mock-server.ts     # Replays recorded fixtures
├── test-helper.ts     # Unified test setup API
└── review-cli.ts      # CLI for reviewing recordings

frontend/e2e/fixtures/data/
├── recordings/        # Raw captured API calls (not committed)
├── approved/          # Reviewed & approved fixtures (committed)
└── sets/              # Named fixture sets for specific scenarios
```

The system supports two modes:
- **Recording mode** (`RECORD_FIXTURES=true`): Captures real API responses
- **Mock mode** (default): Replays approved fixtures

---

## Target Architecture

### Test Organization

```
frontend/e2e/
├── production/                    # Real production tests (manual only)
│   └── full-user-journey.spec.ts  # Single comprehensive test
│
├── regression/                    # Offline tests using fixtures (CI)
│   ├── landing-page.spec.ts       # Landing, pricing, FAQ
│   ├── authentication.spec.ts     # Magic link, beta enrollment
│   ├── job-management.spec.ts     # Create, view, cancel jobs
│   ├── karaoke-generation.spec.ts # Audio selection, lyrics review
│   └── mobile.spec.ts             # Mobile responsiveness
│
├── fixtures/                      # Mock/replay infrastructure
│   ├── data/
│   │   ├── approved/              # Committed fixture files
│   │   └── recordings/            # Temp recordings (gitignored)
│   ├── index.ts
│   ├── recorder.ts
│   ├── mock-server.ts
│   └── test-helper.ts
│
└── helpers/
    ├── auth.ts                    # Shared auth utilities
    ├── email-testing.ts           # MailSlurp helpers
    └── constants.ts               # TEST_ARTIST, TEST_TITLE, URLs
```

### Playwright Configurations

```
frontend/
├── playwright.config.ts           # CI regression tests (fixtures)
├── playwright.production.config.ts # Manual production tests
└── playwright.record.config.ts    # Fixture recording mode (new)
```

### NPM Scripts

```json
{
  "test:e2e": "playwright test",                           // CI regression tests
  "test:e2e:ui": "playwright test --ui",                   // Interactive UI
  "test:e2e:prod": "playwright test --config=playwright.production.config.ts",
  "test:e2e:prod:headed": "playwright test --config=playwright.production.config.ts --headed",
  "test:e2e:record": "RECORD_FIXTURES=true playwright test --config=playwright.record.config.ts",
  "fixtures:review": "npx ts-node e2e/fixtures/review-cli.ts"
}
```

---

## Implementation Plan

### Phase 1: Create Production E2E Test (Priority: High)

**Goal**: Single comprehensive test that validates the entire user journey in production.

#### Test Flow
```
1. Landing Page
   └─ Verify hero, pricing, FAQ sections visible

2. Beta Enrollment (with MailSlurp)
   ├─ Create test inbox
   ├─ Fill beta form with real feedback promise
   ├─ Submit and verify session token received
   ├─ Verify welcome email received
   └─ Verify redirected to /app with 2 credits (1 welcome + 1 beta)

3. Create Karaoke Job
   ├─ Go to Search tab
   ├─ Enter "piri" / "dog"
   ├─ Submit search
   └─ Verify job created

4. Audio Selection
   ├─ Wait for audio search to complete
   ├─ Open audio selection dialog
   ├─ Select first result (should be cached)
   └─ Verify audio download starts

5. Wait for Processing
   ├─ Poll job status
   ├─ Wait for lyrics transcription (AudioShake)
   ├─ Wait for agentic correction (Vertex AI)
   └─ Verify job reaches "in_review" status

6. Lyrics Review
   ├─ Open review UI (new tab)
   ├─ Verify lyrics loaded
   ├─ Click "Preview Video"
   ├─ Wait for preview to generate
   ├─ Click "Complete Review"
   └─ Verify review completed

7. Instrumental Selection
   ├─ Wait for job to reach instrumental selection
   ├─ Open instrumental dialog
   ├─ Select "Clean" instrumental
   └─ Verify selection saved

8. Wait for Completion
   ├─ Poll job status
   ├─ Wait for video rendering
   ├─ Wait for encoding (4K, 720p, CDG)
   └─ Verify job status = "completed"

9. Verify Outputs
   ├─ Check download URLs exist
   ├─ Verify YouTube upload (if enabled)
   ├─ Verify Dropbox upload (if configured)
   └─ Verify Google Drive upload (if configured)

10. Cleanup (Optional)
    └─ Delete test job to avoid clutter
```

#### File: `frontend/e2e/production/full-user-journey.spec.ts`

Key characteristics:
- Uses `piri - dog` consistently
- Uses MailSlurp for real email testing
- 15-minute timeout (karaoke generation takes time)
- Detailed console logging at each step
- Screenshots at every milestone
- Graceful error handling with diagnostic info

### Phase 2: Extract Shared Utilities

**Goal**: Eliminate code duplication and create a single source of truth.

#### `frontend/e2e/helpers/constants.ts`
```typescript
export const TEST_SONG = {
  artist: 'piri',
  title: 'dog',
} as const;

export const URLS = {
  production: {
    frontend: 'https://gen.nomadkaraoke.com',
    api: 'https://api.nomadkaraoke.com',
  },
  local: {
    frontend: 'http://localhost:3000',
    api: 'http://localhost:8000',
  },
} as const;

export const TIMEOUTS = {
  action: 30_000,      // 30s for UI actions
  expect: 60_000,      // 60s for assertions
  apiCall: 120_000,    // 2min for API calls
  jobProcessing: 600_000, // 10min for job processing
  fullTest: 900_000,   // 15min for full test
} as const;
```

#### `frontend/e2e/helpers/auth.ts`
```typescript
export async function setAuthToken(page: Page, token: string): Promise<void>;
export async function clearAuthToken(page: Page): Promise<void>;
export async function authenticatePage(page: Page): Promise<boolean>;
export async function getAuthToken(): string | undefined;
```

### Phase 3: Record API Fixtures

**Goal**: Capture real API responses from a successful production run.

#### Process
1. Run the production E2E test with `RECORD_FIXTURES=true`
2. The recorder captures all API calls/responses
3. Review recordings with `npm run fixtures:review`
4. Approve fixtures and commit to `fixtures/data/approved/`

#### Fixtures to Capture
```
GET  /api/health
GET  /api/users/credits/packages
POST /api/users/beta/enroll
GET  /api/users/me
POST /api/audio-search/search
GET  /api/jobs
GET  /api/jobs/:id
POST /api/jobs/:id/select-audio
GET  /api/review/:id/correction-data
GET  /api/review/:id/audio/:type
POST /api/review/:id/preview-video
POST /api/review/:id/complete
POST /api/jobs/:id/select-instrumental
GET  /api/jobs/:id/download-urls
```

### Phase 4: Create Regression Test Suite

**Goal**: Comprehensive offline tests that run in CI.

#### Test Files

**`regression/landing-page.spec.ts`**
- Hero section displays correctly
- Pricing packages show all 4 options
- Package selection updates checkout form
- FAQ accordion works
- Sign in button opens auth dialog
- Logged-in users redirect to /app

**`regression/authentication.spec.ts`**
- Magic link dialog opens and validates email
- Beta form validates required fields
- Beta enrollment success flow (mocked)
- Token persistence across navigation
- Unauthenticated users redirect to landing

**`regression/job-management.spec.ts`**
- Job list displays correctly
- Job cards show status badges
- Job details expand on click
- Job logs can be viewed
- Job can be cancelled
- Completed job shows download links

**`regression/karaoke-generation.spec.ts`**
- Search tab shows artist/title inputs
- Audio selection dialog opens
- Audio options display correctly
- Instrumental selection dialog opens
- Review UI loads with lyrics data

**`regression/mobile.spec.ts`**
- Pages render without horizontal scroll
- Touch targets are adequate size
- Forms are usable on mobile
- Dialogs fit mobile viewport

### Phase 5: Update CI Configuration

**Goal**: Run regression tests on every PR.

#### `.github/workflows/ci.yml` Changes
```yaml
frontend-e2e:
  name: "Frontend - E2E Tests"
  runs-on: ubuntu-latest
  needs: [detect-changes]
  if: needs.detect-changes.outputs.frontend == 'true'
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: '20'
        cache: 'npm'
        cache-dependency-path: frontend/package-lock.json
    - run: npm ci
      working-directory: frontend
    - run: npx playwright install --with-deps chromium
      working-directory: frontend
    - run: npm run test:e2e
      working-directory: frontend
    - uses: actions/upload-artifact@v4
      if: failure()
      with:
        name: playwright-report
        path: frontend/playwright-report/
```

### Phase 6: Cleanup Legacy Files

**Goal**: Remove redundant test files.

#### Files to Delete
- `karaoke-generation.spec.ts` - Functionality merged into regression tests
- `screenshot-audio-dialog.spec.ts` - One-off utility, not a test
- `production-user-journey.spec.ts` - Merged into production test
- `production-e2e.spec.ts` - Merged into production test
- `fixtures-example.spec.ts` - Example no longer needed

#### Files to Keep (Refactored)
- `mobile-responsiveness.spec.ts` → `regression/mobile.spec.ts`

---

## Success Criteria

### Production Test
- [ ] Single test file covers entire user journey
- [ ] Uses `piri - dog` exclusively
- [ ] MailSlurp validates email delivery
- [ ] Verifies all distribution outputs
- [ ] Completes in < 15 minutes
- [ ] Produces clear diagnostic output on failure

### Regression Tests
- [ ] All tests pass with mocked API
- [ ] No network calls to production
- [ ] Tests complete in < 2 minutes total
- [ ] Mobile tests cover key viewports
- [ ] CI runs on every frontend PR

### Fixture System
- [ ] Fixtures captured from real production run
- [ ] Fixtures committed and versioned
- [ ] Recording mode works for updates
- [ ] Review CLI allows fixture management

---

## Risk Mitigation

### Production Test Risks
| Risk | Mitigation |
|------|------------|
| Flaky due to timing | Generous timeouts, retry logic |
| Costs money (AudioShake, Modal) | Only run manually, use cached song |
| Creates test data | Use identifiable test data, optional cleanup |
| Email delivery delays | MailSlurp has 60s timeout |

### Regression Test Risks
| Risk | Mitigation |
|------|------------|
| Fixtures become stale | Re-record periodically, version control |
| API changes break fixtures | Fixture review process catches mismatches |
| Mock doesn't match real API | Use exact recorded responses |

---

## Estimated Effort

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1: Production Test | 4-6 hours | None |
| Phase 2: Extract Utilities | 1-2 hours | Phase 1 |
| Phase 3: Record Fixtures | 1-2 hours | Phase 1 working |
| Phase 4: Regression Tests | 4-6 hours | Phase 2, 3 |
| Phase 5: CI Configuration | 1-2 hours | Phase 4 |
| Phase 6: Cleanup | 1 hour | Phase 4 |

**Total: 12-19 hours**

---

## Open Questions

1. **Distribution Testing**: Should the production test verify actual Dropbox/GDrive/YouTube uploads, or just that the job completed successfully?

2. **Test Data Cleanup**: Should we automatically delete test jobs after the production test runs, or keep them for debugging?

3. **Fixture Versioning**: Should fixtures be versioned separately from code (e.g., in a fixtures branch)?

4. **Review UI Testing**: How deeply should we test the lyrics review UI? It opens in a new tab with complex interactions.

---

## Next Steps

1. Create the production test file (`full-user-journey.spec.ts`)
2. Run it against production to identify current bugs
3. Fix any bugs discovered
4. Once passing, record API fixtures
5. Build regression test suite from fixtures
6. Add to CI pipeline
7. Clean up legacy files

---

## Appendix: Current Auth Token

The `.env.local` file contains:
```
KARAOKE_ACCESS_TOKEN=9021de39...
MAILSLURP_API_KEY=sk_B1mlu...
```

This token should work with the current auth system (session token hash format).
