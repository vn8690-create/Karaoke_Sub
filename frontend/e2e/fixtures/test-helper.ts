/**
 * Test Helper for API Fixtures
 *
 * Provides a unified interface for tests to work with API fixtures.
 * Automatically switches between recording mode and mock mode based on environment.
 *
 * Usage in tests:
 *
 * ```typescript
 * import { test } from '@playwright/test';
 * import { setupApiFixtures } from './fixtures/test-helper';
 *
 * test('my test', async ({ page }) => {
 *   const api = await setupApiFixtures(page, {
 *     fixtureSet: 'authenticated-user',  // or use inline mocks
 *   });
 *
 *   // Test code here...
 *
 *   // Optionally check for unhandled requests
 *   api.assertAllHandled();
 * });
 * ```
 */

import { Page } from '@playwright/test';
import { ApiRecorder, shouldRecordFixtures, createRecorderIfNeeded } from './recorder';
import { ApiMockServer, createMockServer } from './mock-server';
import { ApiFixture } from './types';

export interface SetupOptions {
  /** Name of fixture set to load */
  fixtureSet?: string;
  /** Load all approved fixtures */
  useApprovedFixtures?: boolean;
  /** Additional inline mocks */
  mocks?: Array<{
    method: string;
    path: string;
    response: { status?: number; body: any };
  }>;
  /** Test file name (for recording mode) */
  testFile?: string;
}

export interface ApiTestContext {
  /** The mock server (if in mock mode) */
  mockServer: ApiMockServer | null;
  /** The recorder (if in recording mode) */
  recorder: ApiRecorder | null;
  /** Whether we're in recording mode */
  isRecording: boolean;
  /** Assert all API requests were handled (mock mode only) */
  assertAllHandled: () => void;
  /** Get unmatched requests (mock mode only) */
  getUnmatchedRequests: () => Array<{ method: string; url: string }>;
  /** Stop recording and get results (recording mode only) */
  stopRecording: () => ApiFixture[];
}

/**
 * Set up API fixtures for a test
 *
 * In recording mode (RECORD_FIXTURES=true):
 *   - Intercepts real API calls and records them
 *   - Saves recordings to fixtures/data/recordings/
 *
 * In mock mode (default):
 *   - Intercepts API calls and returns fixture data
 *   - No real backend requests are made
 */
export async function setupApiFixtures(
  page: Page,
  options: SetupOptions = {}
): Promise<ApiTestContext> {
  const isRecording = shouldRecordFixtures();

  if (isRecording) {
    // Recording mode: capture real API responses
    const recorder = new ApiRecorder(options.testFile);
    await recorder.startRecording(page);

    return {
      mockServer: null,
      recorder,
      isRecording: true,
      assertAllHandled: () => {
        // No-op in recording mode
      },
      getUnmatchedRequests: () => [],
      stopRecording: () => {
        const session = recorder.stopRecording();
        return session.calls;
      },
    };
  }

  // Mock mode: replay fixtures
  const mockServer = createMockServer();

  // Load fixture set if specified
  if (options.fixtureSet) {
    mockServer.loadFixtureSet(options.fixtureSet);
  }

  // Load approved fixtures if requested
  if (options.useApprovedFixtures) {
    mockServer.loadApprovedFixtures();
  }

  // Add inline mocks
  if (options.mocks) {
    for (const mock of options.mocks) {
      mockServer.mockRoute(mock.method, mock.path, mock.response);
    }
  }

  await mockServer.install(page);

  return {
    mockServer,
    recorder: null,
    isRecording: false,
    assertAllHandled: () => {
      const unmatched = mockServer.getUnmatchedRequests();
      if (unmatched.length > 0) {
        const details = unmatched
          .map((r) => `  - ${r.method} ${r.url}`)
          .join('\n');
        throw new Error(
          `Some API requests had no matching fixture:\n${details}\n\n` +
            'Run with RECORD_FIXTURES=true to capture these endpoints.'
        );
      }
    },
    getUnmatchedRequests: () => mockServer.getUnmatchedRequests(),
    stopRecording: () => [],
  };
}

/**
 * Convenience function for tests that only need simple inline mocks
 */
export async function setupMocks(
  page: Page,
  mocks: Array<{
    method: string;
    path: string;
    response: { status?: number; body: any };
  }>
): Promise<ApiTestContext> {
  return setupApiFixtures(page, { mocks });
}

/**
 * Convenience function for authenticated user scenario
 */
export async function setupAuthenticatedUser(page: Page): Promise<ApiTestContext> {
  return setupApiFixtures(page, {
    mocks: [
      {
        method: 'GET',
        path: '/api/jobs',
        response: { body: [] },
      },
    ],
  });
}

/**
 * Convenience function for unauthenticated user scenario
 * Note: The frontend checks localStorage for auth token before making API calls,
 * so no mock is needed for the unauthenticated state.
 */
export async function setupUnauthenticatedUser(page: Page): Promise<ApiTestContext> {
  return setupApiFixtures(page, { mocks: [] });
}

/**
 * Helper to set authentication token in localStorage before page navigation
 */
export async function setAuthToken(page: Page, token: string): Promise<void> {
  await page.addInitScript((t) => {
    localStorage.setItem('karaoke_access_token', t);
  }, token);
}

/**
 * Helper to clear authentication token
 */
export async function clearAuthToken(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.removeItem('karaoke_access_token');
  });
}
