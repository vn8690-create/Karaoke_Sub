import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config for interactive fixture review.
 *
 * Usage:
 *   cd frontend
 *   npx playwright test --config=playwright.review.config.ts --headed
 *
 * Filters:
 *   FIXTURE_START=10  npx playwright test --config=playwright.review.config.ts --headed
 *   FIXTURE_SLUG=bon-jovi-it-s-my-life  npx playwright test --config=playwright.review.config.ts --headed
 *   FIXTURE_TIER=3  npx playwright test --config=playwright.review.config.ts --headed
 */

const PORT = process.env.E2E_PORT || '3000';
const BASE_URL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: './e2e/fixtures',
  testMatch: 'review-fixtures.spec.ts',

  fullyParallel: false,
  forbidOnly: false,
  retries: 0,
  workers: 1,

  reporter: [['list']],

  use: {
    baseURL: BASE_URL,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
    actionTimeout: 30_000,
  },

  // Long timeout since each test pauses for human review
  timeout: 600_000, // 10 minutes per fixture

  expect: {
    timeout: 30_000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: {
    command: `npm run dev -- -p ${PORT}`,
    url: BASE_URL,
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
