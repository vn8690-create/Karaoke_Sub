/**
 * API Fixtures Module
 *
 * This module provides tools for recording and replaying API fixtures
 * to enable deterministic E2E testing without a real backend.
 *
 * @example Recording mode (capture real API responses):
 * ```bash
 * RECORD_FIXTURES=true npm run test:e2e
 * npm run fixtures:review   # Review and approve captured fixtures
 * ```
 *
 * @example Mock mode (use approved fixtures):
 * ```typescript
 * import { setupApiFixtures } from './fixtures';
 *
 * test('my test', async ({ page }) => {
 *   await setupApiFixtures(page, { useApprovedFixtures: true });
 *   // Test runs against mock data
 * });
 * ```
 */

export * from './types';
export * from './recorder';
export * from './mock-server';
export * from './test-helper';
