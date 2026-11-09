/**
 * Production Debug Script Template
 *
 * Use this template when you need to quickly test/debug something in production.
 * Copy this file and rename it with the .local suffix so it won't be committed:
 *
 *   cp frontend/e2e/helpers/debug-prod-template.mjs frontend/test-my-issue.local.mjs
 *
 * Then customize and run:
 *   cd frontend && node test-my-issue.local.mjs
 *
 * IMPORTANT: Files matching test-*.local.* and debug-*.local.* are gitignored,
 * so you can safely put tokens in them for quick debugging.
 *
 * For proper reusable tests, use the existing E2E infrastructure instead:
 *   - frontend/e2e/production/ - Production E2E tests with env var auth
 *   - See docs/TESTING.md for guidance
 *
 * Environment variables (set these or hardcode in your .local copy):
 *   KARAOKE_ADMIN_TOKEN - Admin user token (for admin pages)
 *   KARAOKE_ACCESS_TOKEN - Regular user token (for user pages)
 *   DEBUG_JOB_ID - Job ID to test (if applicable)
 */

import { chromium } from 'playwright';

// ============================================================================
// CONFIGURATION - Customize these for your debugging session
// ============================================================================

const BASE_URL = 'https://gen.nomadkaraoke.com';
const API_URL = 'https://api.nomadkaraoke.com';

// Get tokens from environment (recommended) or hardcode in your .local copy
const ADMIN_TOKEN = process.env.KARAOKE_ADMIN_TOKEN || process.env.KARAOKE_ACCESS_TOKEN;
const JOB_ID = process.env.DEBUG_JOB_ID || null;

// What page to test - customize this
const TARGET_PAGE = JOB_ID
  ? `${BASE_URL}/app/jobs/${JOB_ID}`
  : `${BASE_URL}/app`;

// ============================================================================
// DEBUG SCRIPT
// ============================================================================

async function debug() {
  if (!ADMIN_TOKEN) {
    console.error('ERROR: No token found.');
    console.error('Set KARAOKE_ADMIN_TOKEN or KARAOKE_ACCESS_TOKEN environment variable,');
    console.error('or hardcode a token in your .local copy of this script.');
    process.exit(1);
  }

  console.log('\n=== Production Debug Session ===\n');
  console.log(`Target: ${TARGET_PAGE}`);
  console.log(`Token: ${ADMIN_TOKEN.substring(0, 8)}...`);
  if (JOB_ID) console.log(`Job ID: ${JOB_ID}`);
  console.log('');

  const browser = await chromium.launch({
    headless: true, // Set to false to see the browser
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  // Collect errors for summary
  const consoleErrors = [];
  const httpErrors = [];

  // Capture console errors
  page.on('console', (msg) => {
    const text = msg.text();
    const type = msg.type();
    if (type === 'error' || text.toLowerCase().includes('error')) {
      consoleErrors.push({ type, text: text.substring(0, 300) });
    }
  });

  // Capture HTTP errors (4xx, 5xx)
  page.on('response', (response) => {
    const status = response.status();
    if (status >= 400) {
      httpErrors.push({
        url: response.url(),
        status,
        statusText: response.statusText(),
      });
    }
  });

  try {
    // Set auth token before navigation
    await page.addInitScript((token) => {
      localStorage.setItem('karaoke_access_token', token);
    }, ADMIN_TOKEN);

    // Navigate to target page
    console.log('1. Navigating to page...');
    await page.goto(TARGET_PAGE, { waitUntil: 'networkidle', timeout: 30000 });
    console.log(`   URL: ${page.url()}`);

    // Wait for any async loading
    await page.waitForTimeout(3000);

    // ========================================================================
    // CUSTOMIZE YOUR DEBUG STEPS HERE
    // ========================================================================

    // Example: Check what's on the page
    const bodyText = await page.evaluate(() => document.body.innerText);
    console.log('\n2. Page content (first 500 chars):');
    console.log(bodyText.substring(0, 500));
    console.log('...');

    // Example: List all buttons
    const buttons = await page.getByRole('button').allTextContents();
    console.log('\n3. Buttons on page:', buttons.slice(0, 10).join(', '));

    // Example: List all links
    const links = await page.evaluate(() =>
      Array.from(document.querySelectorAll('a'))
        .slice(0, 10)
        .map((a) => ({ href: a.href, text: a.innerText.trim().substring(0, 30) }))
    );
    console.log('\n4. Links on page:', JSON.stringify(links, null, 2));

    // Example: Take a screenshot
    await page.screenshot({ path: 'debug-screenshot.png', fullPage: true });
    console.log('\n5. Screenshot saved to debug-screenshot.png');

    // Example: Click something (uncomment and customize)
    // const btn = page.getByRole('button', { name: /some button/i });
    // if (await btn.isVisible()) {
    //   await btn.click();
    //   await page.waitForTimeout(2000);
    //   console.log('Clicked button, new URL:', page.url());
    // }

    // ========================================================================
    // END CUSTOM STEPS
    // ========================================================================

  } catch (e) {
    console.error('\nERROR:', e.message);
  }

  // Summary
  console.log('\n--- Console Errors ---');
  if (consoleErrors.length === 0) {
    console.log('None');
  } else {
    consoleErrors.forEach((err, i) => {
      console.log(`${i + 1}. [${err.type}] ${err.text}`);
    });
  }

  console.log('\n--- HTTP Errors ---');
  if (httpErrors.length === 0) {
    console.log('None');
  } else {
    httpErrors.forEach((err, i) => {
      console.log(`${i + 1}. ${err.status} ${err.statusText}: ${err.url}`);
    });
  }

  await browser.close();
  console.log('\n=== Debug session complete ===\n');
}

debug().catch(console.error);
