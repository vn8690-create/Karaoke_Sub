# API Fixtures for E2E Testing

This module provides tools for recording and replaying API fixtures to enable deterministic E2E testing without requiring a running backend.

## Overview

The fixture system has two modes:

1. **Recording Mode**: Intercepts real API calls during test runs and saves them for review
2. **Mock Mode**: Replays approved fixtures instead of making real API calls

## Workflow

### Step 1: Record API Responses

Run E2E tests in recording mode to capture real API responses:

```bash
cd frontend
npm run test:e2e:record
```

This will:
- Run all E2E tests against the real backend
- Intercept and save all API calls to `e2e/fixtures/data/recordings/`
- Each session creates a new JSON file with all captured requests

### Step 2: Review and Approve Fixtures

Review each captured fixture before approving it:

```bash
npm run fixtures:review
```

The review CLI will:
- Show each captured request/response pair
- Let you approve, skip, or edit each fixture
- Save approved fixtures to `e2e/fixtures/data/approved/`

For each fixture, you can:
- **Approve (a)**: Save the fixture as-is
- **Edit (e)**: Add a description or notes before approving
- **Skip (s)**: Don't save this fixture
- **Quit (q)**: Exit the review session

### Step 3: Use Fixtures in Tests

Once you have approved fixtures, update your tests to use them:

```typescript
import { test, expect } from '@playwright/test';
import { setupApiFixtures } from './fixtures';

test('shows job list', async ({ page }) => {
  // Set up mock server with approved fixtures
  const api = await setupApiFixtures(page, {
    useApprovedFixtures: true,
  });

  await page.goto('/');

  // Test runs against mock data - no real backend needed
  await expect(page.getByText('My Jobs')).toBeVisible();

  // Verify all requests were handled
  api.assertAllHandled();
});
```

## Test Helper API

### setupApiFixtures(page, options)

Main function for setting up API fixtures in a test.

**Options:**
- `fixtureSet?: string` - Load a named fixture set from `data/sets/`
- `useApprovedFixtures?: boolean` - Load all approved fixtures from `data/approved/`
- `mocks?: Array<{method, path, response}>` - Add inline mock responses
- `testFile?: string` - Test file name (used in recording mode)

**Returns:** `ApiTestContext` with:
- `isRecording: boolean` - Whether in recording mode
- `assertAllHandled()` - Throws if any requests weren't mocked
- `getUnmatchedRequests()` - Returns list of unhandled requests
- `stopRecording()` - Stop recording and return captured fixtures

### Convenience Functions

```typescript
// Quick inline mocks
await setupMocks(page, [
  { method: 'GET', path: '/api/v1/jobs', response: { body: [] } },
]);

// Pre-configured scenarios
await setupAuthenticatedUser(page);
await setupUnauthenticatedUser(page);

// Auth helpers
await setAuthToken(page, 'my-token');
await clearAuthToken(page);
```

## Directory Structure

```
e2e/fixtures/
├── data/
│   ├── recordings/     # Temporary recording sessions (gitignored content)
│   ├── approved/       # Approved fixtures (committed to repo)
│   └── sets/           # Named fixture sets for specific scenarios
├── types.ts            # TypeScript interfaces
├── recorder.ts         # Recording logic
├── mock-server.ts      # Mock server logic
├── test-helper.ts      # Test utilities
├── review-cli.ts       # CLI for reviewing fixtures
└── index.ts            # Module exports
```

## Fixture Format

Each approved fixture is a JSON file:

```json
{
  "id": "get-api-v1-jobs",
  "description": "GET /api/v1/jobs - List all jobs",
  "capturedAt": "2024-01-15T10:30:00.000Z",
  "request": {
    "method": "GET",
    "url": "http://localhost:8000/api/v1/jobs",
    "path": "/api/v1/jobs",
    "headers": { "authorization": "[REDACTED]" }
  },
  "response": {
    "status": 200,
    "statusText": "OK",
    "body": []
  },
  "reviewed": true,
  "reviewNotes": "Empty job list for new user"
}
```

## Best Practices

1. **Review every fixture**: Don't blindly approve all recordings. Check that responses are correct and don't contain sensitive data.

2. **Add descriptions**: Edit fixtures to add meaningful descriptions that explain what scenario the fixture represents.

3. **Keep fixtures minimal**: Only approve the fixtures you actually need for tests. Don't capture unnecessary API calls.

4. **Update fixtures when API changes**: If the backend API changes, re-record and review fixtures to ensure tests use correct data.

5. **Use fixture sets for scenarios**: Group related fixtures into sets for complex test scenarios (e.g., "user-with-jobs", "empty-state").

## Environment Variables

- `RECORD_FIXTURES=true` - Enable recording mode
- `NEXT_PUBLIC_API_URL` - Backend API URL (default: http://localhost:8000)
