# Plan: Admin Job Details Page

**Created:** 2026-01-09
**Branch:** feat/sess-20260109-1738-admin-job-details
**Status:** In Progress (Phase 1 Complete)

## Overview

The admin jobs list page links to `/admin/jobs/{job_id}` but that route doesn't exist - the detail page is at `/admin/jobs/detail` expecting `?id=` query params. This causes a 404 when clicking jobs.

We'll fix the routing and enhance the job detail page with comprehensive admin features: full job metadata display, file downloads with signed URLs, editable fields, and job stage reset capabilities.

**Note:** Due to Next.js static export constraints (the frontend deploys to Cloudflare Pages), we cannot use dynamic routes like `/admin/jobs/[jobId]`. Instead, we use query parameters: `/admin/jobs?id={job_id}`. The single page component handles both list and detail views based on the presence of the `id` query param.

## Requirements

### Must Have
- [x] Fix 404 - use query param routing at `/admin/jobs?id={job_id}` (dynamic routes not compatible with static export)
- [ ] Display all job metadata (source, user info, request_metadata, timeline)
- [ ] Stage-by-stage breakdown with timestamps and duration calculations
- [ ] Download links for all existing files (generate signed URLs)
- [ ] View worker logs with filtering by level/worker
- [ ] Restart job from beginning (reset to PENDING)
- [ ] Edit key job fields inline (artist, title, user_email, theme_id, etc.)

### Should Have
- [ ] Reset job to specific intermediate stages (audio selection, lyrics review)
- [ ] View/edit raw JSON fields (state_data, file_urls)
- [ ] Quick actions: send completion email, clear cache, impersonate user

### Nice to Have
- [ ] Job timeline visualization (Gantt-style or vertical timeline)
- [ ] Diff view when editing fields
- [ ] Audit log of admin changes

## Technical Approach

### Routing Fix (COMPLETED)
~~Create `/admin/jobs/[jobId]/page.tsx` as a dynamic route.~~ **UPDATE:** Dynamic routes are incompatible with Next.js `output: 'export'` (static site generation for Cloudflare Pages) without `generateStaticParams()`, which doesn't work for client components.

**Actual approach:** Enhanced `/admin/jobs/page.tsx` to handle both list and detail views:
- Uses `useSearchParams()` to detect `?id=` parameter
- Shows detail view when `selectedJobId` is present, list view otherwise
- Navigation uses `router.push(\`/admin/jobs?id=${job.job_id}\`)`
- Deleted old `/admin/jobs/detail/` directory

### Backend Enhancements
1. **New endpoint**: `GET /api/admin/jobs/{job_id}/files` - returns all files with signed download URLs
2. **New endpoint**: `PATCH /api/admin/jobs/{job_id}` - update editable fields (admin only)
3. **New endpoint**: `POST /api/admin/jobs/{job_id}/reset` - reset job to specific state

### Frontend Structure
The page will have collapsible sections:
1. **Header**: Job ID, status badge, artist/title, quick actions
2. **Overview Cards**: User, dates, progress, source info
3. **Stage Timeline**: Visual breakdown of each stage with times
4. **Files**: Downloadable links for all GCS files
5. **Logs**: Filterable worker logs
6. **Configuration**: Editable job settings
7. **Raw Data**: JSON views of state_data, file_urls, full job

### Job Reset Logic
Reset to specific states requires:
- Clearing downstream state_data keys
- Resetting status
- Optionally clearing associated files
- Adding timeline event for the reset

Valid reset targets:
| Target State | Clears | Use Case |
|--------------|--------|----------|
| PENDING | Everything except input | Full restart |
| AWAITING_AUDIO_SELECTION | Audio search results | Re-search for audio |
| AWAITING_REVIEW | Review data, screens, videos | Re-do lyrics review |
| AWAITING_INSTRUMENTAL_SELECTION | Instrumental selection, finals | Re-choose instrumental |

## Implementation Steps

Testing is integrated into each phase (following TDD/"write tests immediately after" guidance).

### Phase 1: Fix Routing (COMPLETED)
1. [x] ~~Create `/frontend/app/admin/jobs/[jobId]/page.tsx`~~ Enhanced `/admin/jobs/page.tsx` with query param routing
2. [x] Combined list and detail views in single component
3. [x] Use `useSearchParams()` to detect `?id=` parameter
4. [x] Delete `/frontend/app/admin/jobs/detail/` directory
5. [x] **E2E Test**: Added `admin-job-detail.spec.ts` with 9 tests (navigation, metadata, timeline, logs, error states, delete dialog, refresh)
6. [x] Verified: All 9 E2E tests pass, build succeeds

### Phase 2: Backend - File Downloads with Signed URLs
7. [ ] **Write tests first**: Add test file `backend/tests/test_admin_job_detail.py`
8. [ ] Add tests for `GET /api/admin/jobs/{job_id}/files` (see Testing Strategy)
9. [ ] Add `GET /api/admin/jobs/{job_id}/files` endpoint
10. [ ] Traverse job.file_urls recursively
11. [ ] Generate signed URLs for each GCS path
12. [ ] Return structured response with file metadata
13. [ ] Verify: `poetry run pytest backend/tests/test_admin_job_detail.py -v` passes
14. [ ] Add frontend API method `adminApi.getJobFiles(jobId)`

### Phase 3: Frontend - Enhanced File Display
15. [ ] Create "Files" accordion section with grouped downloads
16. [ ] Group by category (input, stems, lyrics, screens, videos, finals, packages)
17. [ ] Show file name, type, download button
18. [ ] Handle missing/unavailable files gracefully
19. [ ] **E2E Test**: Add files section test to `admin-job-detail.spec.ts`
20. [ ] Verify: `npm run test:e2e` passes

### Phase 4: Backend - Job Update Endpoint
21. [ ] **Write tests first**: Add tests for `PATCH /api/admin/jobs/{job_id}`
22. [ ] Add `PATCH /api/admin/jobs/{job_id}` endpoint
23. [ ] Define editable fields whitelist
24. [ ] Validate field values (e.g., status must be valid enum)
25. [ ] Log admin changes for audit trail
26. [ ] Verify: Backend tests pass
27. [ ] Add frontend API method `adminApi.updateJob(jobId, updates)`

### Phase 5: Frontend - Editable Fields
28. [ ] Create "Configuration" section with editable fields
29. [ ] Use inline edit pattern (click to edit, enter to save)
30. [ ] Fields: artist, title, user_email, theme_id, enable_cdg, enable_txt, enable_youtube_upload
31. [ ] Show validation errors inline
32. [ ] **E2E Test**: Add inline edit test to `admin-job-detail.spec.ts`
33. [ ] Verify: `npm run test:e2e` passes

### Phase 6: Backend - Job Reset Endpoint
34. [ ] **Write tests first**: Add tests for `POST /api/admin/jobs/{job_id}/reset`
35. [ ] Add `POST /api/admin/jobs/{job_id}/reset` endpoint
36. [ ] Accept `target_state` parameter
37. [ ] Implement reset logic for each target state
38. [ ] Clear appropriate state_data keys
39. [ ] Optionally trigger workers after reset
40. [ ] Verify: Backend tests pass
41. [ ] Add frontend API method `adminApi.resetJob(jobId, targetState)`

### Phase 7: Frontend - Reset Actions
42. [ ] Add "Reset Job" dropdown/menu in header
43. [ ] Show available reset targets based on current state
44. [ ] Confirm dialog explaining what will be cleared
45. [ ] Show success/error toast after reset
46. [ ] **E2E Test**: Add reset confirmation dialog test
47. [ ] Verify: `npm run test:e2e` passes

### Phase 8: Enhanced Stage Timeline
48. [ ] Parse timeline events to calculate stage durations
49. [ ] Display stages as cards or timeline items
50. [ ] Show duration for each stage
51. [ ] Highlight current/blocking stages
52. [ ] **E2E Test**: Add timeline display test

### Phase 9: Final Verification
53. [ ] Run full backend test suite: `make test-backend`
54. [ ] Run full frontend test suite: `cd frontend && npm run test:all`
55. [ ] Manual production testing checklist (see Testing Strategy)
56. [ ] Verify CI passes on PR

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `frontend/app/admin/jobs/[jobId]/page.tsx` | Create | Dynamic route for job detail |
| `frontend/app/admin/jobs/detail/` | Delete | Remove old query-param based route |
| `backend/api/routes/admin.py` | Modify | Add files, update, reset endpoints |
| `frontend/lib/api.ts` | Modify | Add adminApi methods for new endpoints |
| `backend/tests/test_admin_job_detail.py` | Create | Backend unit tests for new endpoints |
| `frontend/e2e/regression/admin-job-detail.spec.ts` | Create | Frontend E2E regression tests |
| `frontend/e2e/fixtures/test-helper.ts` | Modify | Add admin auth helper if needed |

## Testing Strategy

Based on `docs/TESTING.md` guidelines, this feature requires:

### Test Types Required

| Type | Location | Purpose |
|------|----------|---------|
| Backend Unit Tests | `backend/tests/test_admin_job_detail.py` | Test new API endpoints |
| Frontend E2E Regression | `frontend/e2e/regression/admin-job-detail.spec.ts` | Test UI flows with mocked API |
| Manual Production E2E | N/A | Final validation on staging/prod |

### Backend Unit Tests (`backend/tests/test_admin_job_detail.py`)

**Mocking approach:** Mock Firestore and GCS (following existing patterns in `backend/tests/conftest.py`). Do NOT mock our own code - test the real `JobManager` and `StorageService` logic.

**Test cases for `GET /api/admin/jobs/{job_id}/files`:**
```python
def test_get_job_files_returns_signed_urls_for_all_files():
    """Test that all files in file_urls get signed URLs."""

def test_get_job_files_handles_nested_file_urls():
    """Test recursive traversal of stems.instrumental_clean, etc."""

def test_get_job_files_handles_missing_files_gracefully():
    """Test files that don't exist in GCS are omitted or marked."""

def test_get_job_files_requires_admin():
    """Test non-admin gets 403."""

def test_get_job_files_returns_404_for_missing_job():
    """Test invalid job_id returns 404."""
```

**Test cases for `PATCH /api/admin/jobs/{job_id}`:**
```python
def test_update_job_allows_editable_fields():
    """Test artist, title, user_email, theme_id can be updated."""

def test_update_job_rejects_non_editable_fields():
    """Test job_id, created_at, etc. cannot be updated."""

def test_update_job_validates_status_enum():
    """Test invalid status value returns 422."""

def test_update_job_validates_theme_id_exists():
    """Test non-existent theme_id returns 422."""

def test_update_job_requires_admin():
    """Test non-admin gets 403."""

def test_update_job_returns_updated_job():
    """Test response includes updated job data."""
```

**Test cases for `POST /api/admin/jobs/{job_id}/reset`:**
```python
def test_reset_to_pending_clears_all_state_data():
    """Test full reset clears everything except input."""

def test_reset_to_audio_selection_clears_search_results():
    """Test audio selection reset clears audio_search_results."""

def test_reset_to_awaiting_review_clears_review_data():
    """Test review reset clears screens, videos, review data."""

def test_reset_to_instrumental_selection_clears_finals():
    """Test instrumental reset clears encoding results."""

def test_reset_adds_timeline_event():
    """Test reset adds admin action to timeline."""

def test_reset_invalid_target_returns_422():
    """Test invalid target_state returns validation error."""

def test_reset_requires_admin():
    """Test non-admin gets 403."""

def test_reset_from_complete_to_pending_works():
    """Test can reset completed job back to start."""
```

### Frontend E2E Regression Tests (`frontend/e2e/regression/admin-job-detail.spec.ts`)

**Mocking approach:** Use Playwright route interception to mock API responses (following patterns in `frontend/e2e/fixtures/test-helper.ts`).

```typescript
import { test, expect } from '@playwright/test';
import { setupApiFixtures, setAdminAuthToken } from '../fixtures/test-helper';

test.describe('Admin Job Detail Page', () => {
  test.beforeEach(async ({ page }) => {
    await setAdminAuthToken(page);
  });

  test('navigates from jobs list to detail page', async ({ page }) => {
    // Mock jobs list and single job endpoints
    await page.route('**/api/admin/jobs', route => route.fulfill({
      json: [{ job_id: 'test123', status: 'complete', artist: 'Test', title: 'Song' }]
    }));
    await page.route('**/api/jobs/test123', route => route.fulfill({
      json: { job_id: 'test123', status: 'complete', artist: 'Test', title: 'Song' }
    }));

    await page.goto('/admin/jobs');
    await page.click('text=test123');
    await expect(page).toHaveURL('/admin/jobs/test123');
    await expect(page.getByText('Job test123')).toBeVisible();
  });

  test('displays all job metadata sections', async ({ page }) => {
    // Test overview cards, timeline, logs accordion, etc.
  });

  test('files section shows downloadable links', async ({ page }) => {
    // Mock files endpoint, verify download buttons appear
  });

  test('edit field inline and save', async ({ page }) => {
    // Click edit, change value, press Enter, verify PATCH called
  });

  test('reset job shows confirmation dialog', async ({ page }) => {
    // Click reset, verify dialog, confirm, verify POST called
  });

  test('handles API errors gracefully', async ({ page }) => {
    // Mock 500 response, verify error toast shown
  });
});
```

### Test File Organization

```
backend/tests/
├── test_admin_job_detail.py          # NEW - all backend tests for this feature
├── test_admin_api.py                 # Existing admin tests (keep separate)
└── conftest.py                       # Shared fixtures

frontend/e2e/
├── fixtures/
│   ├── test-helper.ts                # Add setAdminAuthToken helper
│   └── mock-responses.ts             # Add admin job detail mocks
└── regression/
    └── admin-job-detail.spec.ts      # NEW - E2E regression tests
```

### Mocking Guidelines

**Backend - What to mock:**
- `StorageService.generate_signed_url()` - return predictable test URLs
- `StorageService.file_exists()` - control which files "exist"
- Firestore operations via existing `mock_firestore` fixture

**Backend - What NOT to mock:**
- `JobManager` logic - test the real reset/update logic
- Validation logic - test real Pydantic validation
- Authorization checks - test real `require_admin` dependency

**Frontend - What to mock:**
- All API responses via Playwright route interception
- Time (if testing token expiry)

**Frontend - What NOT to mock:**
- React component behavior
- User interactions (click, type, etc.)

### CI Requirements

This feature will be validated by existing CI checks:
- `backend-unit-tests` - Must pass (includes new `test_admin_job_detail.py`)
- `frontend-e2e-smoke` - Must pass (includes new `admin-job-detail.spec.ts`)
- `frontend-build` - Must pass (verifies new page compiles)

### Running Tests Locally

```bash
# Backend tests only (for this feature)
poetry run pytest backend/tests/test_admin_job_detail.py -v

# All backend tests
make test-backend

# Frontend E2E regression (includes new tests)
cd frontend && npm run test:e2e

# Single E2E test file
cd frontend && npx playwright test e2e/regression/admin-job-detail.spec.ts

# With browser visible for debugging
cd frontend && npx playwright test e2e/regression/admin-job-detail.spec.ts --headed
```

### Manual Production Testing Checklist

After deployment, manually verify on production:
- [ ] Navigate `/admin/jobs` → click job → lands on `/admin/jobs/{id}` (not 404)
- [ ] All file download links work (valid signed URLs)
- [ ] Edit artist/title → refresh → changes persisted
- [ ] Reset job to pending → job status shows "pending"
- [ ] Logs section loads and filters work
- [ ] Error states handled (invalid job ID shows friendly error)

## Open Questions

1. [ ] Should we keep the old `/admin/jobs/detail?id=` route for backwards compatibility, or delete it entirely?
   - **Recommendation**: Delete it. No external links depend on it.

2. [ ] Should job reset delete GCS files or just clear state_data references?
   - **Recommendation**: Clear state_data only. Files can be useful for debugging. Add a separate "Delete Files" action if needed.

3. [ ] Should edits be immediately saved or require explicit "Save" button?
   - **Recommendation**: Inline edit with Enter to save, Escape to cancel. Show loading indicator during save.

## Rollback Plan

If issues arise:
1. Routing: Can revert to query-param routing by restoring `detail/page.tsx` and updating navigation
2. Backend: New endpoints are additive, won't affect existing functionality
3. Reset feature: Admin-only, can be disabled by removing endpoint if problematic

## Notes

- The existing detail page has good foundational code - we're enhancing rather than replacing
- Signed URLs expire (default 60-120 min) - consider caching or refresh mechanism for long sessions
- Job reset is powerful - consider adding confirmation dialogs and logging
