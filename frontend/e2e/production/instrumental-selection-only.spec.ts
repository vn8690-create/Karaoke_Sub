import { test, expect } from '@playwright/test';

/**
 * FOCUSED TEST: Instrumental Selection UI Only
 *
 * This test is for rapid iteration on the instrumental selection step.
 * It requires an existing job that's already in "awaiting_instrumental_selection" state.
 *
 * Usage:
 *   E2E_JOB_ID=xxx E2E_INSTRUMENTAL_TOKEN=yyy npx playwright test instrumental-selection-only.spec.ts \
 *     --config=playwright.production.config.ts --headed
 */

const PROD_URL = 'https://gen.nomadkaraoke.com';
const API_URL = 'https://api.nomadkaraoke.com';

function getJobId(): string {
  const jobId = process.env.E2E_JOB_ID;
  if (!jobId) {
    throw new Error('E2E_JOB_ID environment variable is required');
  }
  return jobId;
}

function getInstrumentalToken(): string {
  const token = process.env.E2E_INSTRUMENTAL_TOKEN;
  if (!token) {
    throw new Error('E2E_INSTRUMENTAL_TOKEN environment variable is required');
  }
  return token;
}

test.describe('Instrumental Selection Only - Focused Test', () => {
  test.describe.configure({ retries: 0 });

  test('Complete instrumental selection via UI', async ({ page }) => {
    test.setTimeout(120_000); // 2 minutes

    const jobId = getJobId();
    const token = getInstrumentalToken();

    console.log('========================================');
    console.log('FOCUSED TEST: Instrumental Selection Only');
    console.log('========================================');
    console.log(`Job ID: ${jobId}`);
    console.log(`Instrumental Token: ${token.substring(0, 8)}...`);
    console.log('');

    // Build the instrumental selection URL
    const baseApiUrl = encodeURIComponent(`${API_URL}/api/jobs/${jobId}`);
    const instrumentalUrl = `${PROD_URL}/instrumental/?baseApiUrl=${baseApiUrl}&instrumentalToken=${token}`;

    console.log(`Instrumental URL: ${instrumentalUrl}`);
    console.log('');

    // Navigate to the instrumental selection page
    console.log('1. Opening instrumental selection UI...');
    await page.goto(instrumentalUrl, { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);

    await page.screenshot({ path: 'test-results/instrumental-01-opened.png', fullPage: true });
    console.log('   Instrumental selection UI opened');

    // Wait for content to load
    await expect(page.locator('body')).not.toBeEmpty({ timeout: 30_000 });

    // Log page content for debugging
    const bodyText = await page.locator('body').textContent();
    console.log(`   Page content preview: ${bodyText?.substring(0, 300)}...`);

    // Check for error messages
    const errorMessages = await page.locator('[class*="error"], [class*="Error"]').allTextContents();
    if (errorMessages.length > 0) {
      console.log(`   WARNING: Error messages found: ${errorMessages.join(', ')}`);
    }

    // Look for selection options
    console.log('2. Looking for instrumental options...');

    // The instrumental selection page has radio buttons or selection cards
    const selectButtons = page.locator('button:has-text("Select"), input[type="submit"], input[type="radio"], .selection-option');
    const optionCount = await selectButtons.count();
    console.log(`   Found ${optionCount} selection elements`);

    await page.screenshot({ path: 'test-results/instrumental-02-options.png', fullPage: true });

    if (optionCount === 0) {
      // Try looking for any clickable elements
      const allButtons = await page.getByRole('button').allTextContents();
      console.log(`   All buttons on page: ${allButtons.join(', ')}`);

      // Maybe it's a simple form with a submit button
      const submitBtn = page.locator('#submit-btn, input[type="submit"], button[type="submit"]');
      if (await submitBtn.isVisible().catch(() => false)) {
        console.log('   Found submit button - clicking...');
        await submitBtn.click();
        await page.waitForTimeout(5000);
        await page.screenshot({ path: 'test-results/instrumental-03-after-submit.png', fullPage: true });
        console.log('   Selection submitted!');
      } else {
        throw new Error('No instrumental selection options found');
      }
    } else {
      // Click the first option
      console.log('3. Selecting first instrumental option...');
      await selectButtons.first().click();
      await page.waitForTimeout(2000);

      await page.screenshot({ path: 'test-results/instrumental-03-selected.png', fullPage: true });

      // Look for a submit/confirm button
      const submitBtn = page.locator('#submit-btn, input[type="submit"], button[type="submit"], button:has-text("Confirm"), button:has-text("Submit")');
      if (await submitBtn.isVisible().catch(() => false)) {
        console.log('4. Clicking submit button...');
        await submitBtn.click();
        await page.waitForTimeout(5000);
        console.log('   Selection submitted!');
      } else {
        console.log('   No submit button found - selection may have been automatic');
      }

      await page.screenshot({ path: 'test-results/instrumental-04-after-submit.png', fullPage: true });
    }

    console.log('');
    console.log('========================================');
    console.log('FOCUSED TEST COMPLETE');
    console.log('========================================');
  });
});
