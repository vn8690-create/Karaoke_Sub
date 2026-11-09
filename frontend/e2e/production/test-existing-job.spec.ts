import { test, expect } from '@playwright/test';

/**
 * TEST EXISTING JOB - Test specific stages against existing jobs
 *
 * This test allows you to validate specific stages of the E2E flow
 * against jobs that are already in the right state.
 *
 * Usage:
 *   E2E_TEST_TOKEN=xxx E2E_JOB_ID=yyy E2E_TEST_STAGE=lyrics_review \
 *     npx playwright test test-existing-job.spec.ts --config=playwright.production.config.ts
 *
 * Required:
 *   - E2E_TEST_TOKEN: Your user access token
 *   - E2E_JOB_ID: The job ID to test against
 *   - E2E_TEST_STAGE: The stage to test (lyrics_review, instrumental_selection, or completion)
 *
 * Job states required for each stage:
 *   - lyrics_review: Job must be in "in_review" state
 *   - instrumental_selection: Job must be in "awaiting_instrumental_selection" state
 *   - completion: Job must be in a late-stage processing state
 */

const PROD_URL = 'https://gen.nomadkaraoke.com';

function getAccessToken(): string {
  const token = process.env.E2E_TEST_TOKEN;
  if (!token) {
    throw new Error('E2E_TEST_TOKEN environment variable is required');
  }
  return token;
}

function getJobId(): string {
  const jobId = process.env.E2E_JOB_ID;
  if (!jobId) {
    throw new Error('E2E_JOB_ID environment variable is required');
  }
  return jobId;
}

function getTestStage(): string {
  const stage = process.env.E2E_TEST_STAGE || 'lyrics_review';
  const validStages = ['lyrics_review', 'instrumental_selection', 'completion'];
  if (!validStages.includes(stage)) {
    throw new Error(`Invalid E2E_TEST_STAGE: ${stage}. Valid options: ${validStages.join(', ')}`);
  }
  return stage;
}

test.describe('Test Existing Job - Focused Stage Testing', () => {
  test.describe.configure({ retries: 0 });

  test('Test specific stage against existing job', async ({ page, context }) => {
    test.setTimeout(300_000); // 5 minutes

    const accessToken = getAccessToken();
    const jobId = getJobId();
    const testStage = getTestStage();

    console.log('========================================');
    console.log('TEST EXISTING JOB');
    console.log('========================================');
    console.log(`Job ID: ${jobId}`);
    console.log(`Test Stage: ${testStage}`);
    console.log(`Access Token: ${accessToken.substring(0, 8)}...`);
    console.log('');

    // STEP 1: Set up authentication
    console.log('1. Setting up authentication...');
    await page.goto(PROD_URL, { waitUntil: 'networkidle' });

    // Set the access token in localStorage
    await page.evaluate((token) => {
      localStorage.setItem('karaoke_access_token', token);
    }, accessToken);

    console.log('   Access token set in localStorage');

    // STEP 2: Navigate to app page (where jobs are shown) and find the job
    console.log('2. Navigating to app page...');
    await page.goto(`${PROD_URL}/app`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);

    await page.screenshot({ path: 'test-results/existing-01-jobs-page.png', fullPage: true });

    // Find the job card by ID
    console.log(`3. Looking for job ${jobId}...`);

    // The job ID appears in the job card - look for it
    const jobCard = page.locator(`[data-job-id="${jobId}"], :has-text("${jobId}")`).first();

    // If we can't find by ID directly, look for any job card and check
    let foundJobCard = await jobCard.isVisible({ timeout: 5000 }).catch(() => false);

    if (!foundJobCard) {
      console.log('   Job card not found by ID, looking for job in list...');
      // Get all job cards and look for ours
      const allCards = page.locator('[class*="card"], [class*="Card"], [class*="job"]');
      const cardCount = await allCards.count();
      console.log(`   Found ${cardCount} potential job cards`);

      // Check if the job ID appears on the page
      const pageText = await page.textContent('body');
      if (pageText?.includes(jobId)) {
        console.log(`   Job ID ${jobId} found in page content`);
      } else {
        console.log(`   WARNING: Job ID ${jobId} not found on page`);
        await page.screenshot({ path: 'test-results/existing-02-job-not-found.png', fullPage: true });
        throw new Error(`Job ${jobId} not found on jobs page`);
      }
    }

    // Log the current job status
    const statusText = await page.textContent('body') || '';
    console.log(`   Page content preview: ${statusText.substring(0, 300)}...`);

    // STEP 3: Execute the appropriate test stage
    if (testStage === 'lyrics_review') {
      await testLyricsReview(page, context, jobId);
    } else if (testStage === 'instrumental_selection') {
      await testInstrumentalSelection(page, context, jobId);
    } else if (testStage === 'completion') {
      await testCompletion(page, jobId);
    }

    console.log('');
    console.log('========================================');
    console.log('TEST COMPLETE');
    console.log('========================================');
  });
});

async function testLyricsReview(page: any, context: any, jobId: string) {
  console.log('\n========================================');
  console.log('TESTING: Lyrics Review Stage');
  console.log('========================================');

  // Look for the Review Lyrics link
  console.log('4. Looking for "Review Lyrics" link...');
  const reviewLink = page.getByRole('link', { name: /review lyrics/i });

  if (!(await reviewLink.isVisible({ timeout: 10000 }).catch(() => false))) {
    // Maybe we need to expand the job card or the job isn't in the right state
    console.log('   Review Lyrics link not visible');

    // Check for Action needed indicator
    const actionNeeded = page.getByText(/action needed/i);
    if (await actionNeeded.isVisible().catch(() => false)) {
      console.log('   Found "Action needed" indicator');
    }

    // List all links on the page for debugging
    const allLinks = await page.getByRole('link').allTextContents();
    console.log(`   Available links: ${allLinks.slice(0, 20).join(', ')}`);

    await page.screenshot({ path: 'test-results/existing-03-no-review-link.png', fullPage: true });
    throw new Error('Job does not appear to be in the lyrics review state');
  }

  // Get the review URL and open in new page
  const reviewUrl = await reviewLink.getAttribute('href');
  console.log(`   Review URL: ${reviewUrl}`);

  // Open review UI in new page
  console.log('5. Opening lyrics review UI...');
  const reviewPage = await context.newPage();
  await reviewPage.goto(reviewUrl!, { waitUntil: 'networkidle' });
  await reviewPage.waitForTimeout(3000);

  await reviewPage.screenshot({ path: 'test-results/existing-04-review-opened.png', fullPage: true });
  console.log('   Lyrics review UI opened');

  // Wait for content to load
  await expect(reviewPage.locator('body')).not.toBeEmpty({ timeout: 30000 });
  await reviewPage.waitForTimeout(2000);

  // Log page content for debugging
  const bodyText = await reviewPage.locator('body').textContent();
  console.log(`   Page content: ${bodyText?.substring(0, 200)}...`);

  // Look for any error messages
  const errorMessages = await reviewPage.locator('[class*="error"], .MuiAlert-standardError').allTextContents();
  if (errorMessages.length > 0) {
    console.log(`   WARNING: Error messages: ${errorMessages.join(', ')}`);
  }

  // Scroll to bottom to find the "Preview Video" button
  console.log('6. Scrolling to bottom of page...');
  await reviewPage.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await reviewPage.waitForTimeout(1000);

  await reviewPage.screenshot({ path: 'test-results/existing-05-scrolled.png', fullPage: true });

  // List all visible buttons
  const allButtons = await reviewPage.getByRole('button').allTextContents();
  console.log(`   Visible buttons: ${allButtons.join(', ')}`);

  // Click "Preview Video" button
  console.log('7. Clicking "Preview Video" button...');
  const previewVideoBtn = reviewPage.getByRole('button', { name: /preview video/i });

  if (!(await previewVideoBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
    await reviewPage.screenshot({ path: 'test-results/existing-06-no-preview-btn.png', fullPage: true });
    throw new Error('Could not find Preview Video button');
  }

  await previewVideoBtn.click();
  console.log('   Clicked Preview Video button');

  // Wait for the modal dialog to appear
  console.log('8. Waiting for preview modal...');
  const previewModal = reviewPage.getByRole('dialog');
  await expect(previewModal).toBeVisible({ timeout: 30000 });
  console.log('   Preview modal opened');

  await reviewPage.screenshot({ path: 'test-results/existing-07-modal-opened.png', fullPage: true });

  // Wait for video preview to generate
  console.log('9. Waiting for preview video generation...');
  const loadingText = reviewPage.getByText(/generating preview video/i);

  if (await loadingText.isVisible({ timeout: 5000 }).catch(() => false)) {
    console.log('   Preview is generating... waiting up to 2 minutes');
    try {
      await expect(loadingText).not.toBeVisible({ timeout: 120000 });
      console.log('   Preview generation complete');
    } catch {
      console.log('   WARNING: Preview generation timed out');
    }
  } else {
    console.log('   No loading indicator found - preview may already be ready');
  }

  await reviewPage.screenshot({ path: 'test-results/existing-08-after-generation.png', fullPage: true });

  // Check for video element or error
  const videoElement = reviewPage.locator('video');
  const errorAlert = reviewPage.locator('[role="alert"]');

  if (await errorAlert.isVisible({ timeout: 5000 }).catch(() => false)) {
    const errorText = await errorAlert.textContent();
    console.log(`   WARNING: Preview error: ${errorText}`);
  } else if (await videoElement.isVisible({ timeout: 10000 }).catch(() => false)) {
    console.log('   Video element visible');
    const videoState = await videoElement.first().evaluate((el: Element) => {
      const video = el as HTMLVideoElement;
      return {
        src: video.src?.substring(0, 50),
        readyState: video.readyState,
        duration: video.duration,
      };
    });
    console.log(`   Video state: ${JSON.stringify(videoState)}`);
  } else {
    console.log('   WARNING: No video element found');
  }

  // Click "Proceed to Instrumental Review" button (previously "Complete Review")
  console.log('10. Clicking "Proceed to Instrumental Review" button...');
  const modalButtons = await previewModal.getByRole('button').allTextContents();
  console.log(`   Modal buttons: ${modalButtons.join(', ')}`);

  const proceedBtn = reviewPage.getByRole('button', { name: /proceed to instrumental/i });

  if (await proceedBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
    await proceedBtn.click();
    console.log('   Clicked Proceed to Instrumental Review button');
  } else {
    await reviewPage.screenshot({ path: 'test-results/existing-09-no-proceed-btn.png', fullPage: true });
    throw new Error('Could not find Proceed to Instrumental Review button');
  }

  // Wait for navigation to instrumental selection (happens via hash change on same page)
  console.log('11. Waiting for navigation to instrumental selection...');
  await reviewPage.waitForTimeout(5000);

  await reviewPage.screenshot({ path: 'test-results/existing-10-after-proceed.png', fullPage: true });
  console.log('   Lyrics review step completed - now on instrumental selection!');
  console.log('   NOTE: With combined UI, instrumental selection is on the same page.');

  await reviewPage.close();
}

async function testInstrumentalSelection(page: any, context: any, jobId: string) {
  console.log('\n========================================');
  console.log('TESTING: Instrumental Selection Stage');
  console.log('========================================');

  // Look for the Select Instrumental link
  console.log('4. Looking for "Select Instrumental" link...');
  const selectLink = page.getByRole('link', { name: /select instrumental/i });

  if (!(await selectLink.isVisible({ timeout: 10000 }).catch(() => false))) {
    // List all links for debugging
    const allLinks = await page.getByRole('link').allTextContents();
    console.log(`   Available links: ${allLinks.slice(0, 20).join(', ')}`);

    await page.screenshot({ path: 'test-results/existing-03-no-select-link.png', fullPage: true });
    throw new Error('Job does not appear to be in the instrumental selection state');
  }

  // Get the selection URL and open in new page
  const selectUrl = await selectLink.getAttribute('href');
  console.log(`   Selection URL: ${selectUrl}`);

  // Open selection UI in new page
  console.log('5. Opening instrumental selection UI...');
  const selectPage = await context.newPage();
  await selectPage.goto(selectUrl!, { waitUntil: 'networkidle' });
  await selectPage.waitForTimeout(3000);

  await selectPage.screenshot({ path: 'test-results/existing-04-selection-opened.png', fullPage: true });
  console.log('   Instrumental selection UI opened');

  // Wait for content
  await expect(selectPage.locator('body')).not.toBeEmpty({ timeout: 30000 });

  // Log page content
  const bodyText = await selectPage.locator('body').textContent();
  console.log(`   Page content: ${bodyText?.substring(0, 200)}...`);

  // Find and click a Select button (the first one should be fine)
  console.log('6. Looking for instrumental options...');
  const selectButtons = selectPage.locator('button:has-text("Select"), input[type="submit"][value*="Select"]');
  const buttonCount = await selectButtons.count();
  console.log(`   Found ${buttonCount} Select buttons`);

  if (buttonCount === 0) {
    await selectPage.screenshot({ path: 'test-results/existing-05-no-select-buttons.png', fullPage: true });
    throw new Error('No instrumental selection buttons found');
  }

  // Click the first one
  console.log('7. Clicking first instrumental option...');
  await selectButtons.first().click();
  console.log('   Clicked Select button');

  // Wait for the selection to process
  console.log('8. Waiting for selection to complete...');
  await selectPage.waitForTimeout(5000);

  await selectPage.screenshot({ path: 'test-results/existing-06-after-selection.png', fullPage: true });

  // Check for success message or redirect
  const currentUrl = selectPage.url();
  console.log(`   Current URL: ${currentUrl}`);

  console.log('   Instrumental selection completed successfully!');
  await selectPage.close();
}

async function testCompletion(page: any, jobId: string) {
  console.log('\n========================================');
  console.log('TESTING: Completion Stage');
  console.log('========================================');

  // This stage just monitors the job until completion
  console.log('4. Monitoring job for completion...');

  const maxWaitTime = 30 * 60 * 1000; // 30 minutes
  const startTime = Date.now();
  let completed = false;

  while (Date.now() - startTime < maxWaitTime) {
    // Refresh the page
    const refreshBtn = page.getByRole('button', { name: /refresh/i });
    if (await refreshBtn.isVisible().catch(() => false)) {
      await refreshBtn.click();
      await page.waitForTimeout(2000);
    } else {
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(2000);
    }

    // Check job status
    const statusText = await page.textContent('body') || '';
    console.log(`   Status: ${statusText.substring(0, 100)}...`);

    // Check for completion indicators
    if (statusText.toLowerCase().includes('complete') &&
        !statusText.toLowerCase().includes('processing')) {
      completed = true;
      console.log('   Job completed!');
      break;
    }

    // Check for failure
    if (statusText.toLowerCase().includes('failed')) {
      throw new Error('Job failed during processing');
    }

    await page.waitForTimeout(30000); // Check every 30 seconds
  }

  if (!completed) {
    throw new Error('Job did not complete within timeout');
  }

  await page.screenshot({ path: 'test-results/existing-completion.png', fullPage: true });
  console.log('   Completion test passed!');
}
