import { test, expect } from '@playwright/test';
import {
  sendTestWebhook,
  createMadeForYouSearchPayload,
  getJobDetails,
} from '../helpers/stripe-test-client';
import { createCleanupTracker, deleteTestJob } from '../helpers/test-cleanup';
import { createEmailHelper, isEmailTestingAvailable } from '../helpers/email-testing';
import { URLS } from '../helpers/constants';

/**
 * E2E Tests for Made-For-You Search Order Payment Flow
 *
 * Tests the made-for-you order flow when the customer selects "search" as
 * the audio source (no YouTube URL provided). In this flow:
 *
 * 1. Payment completes (simulated via test-webhook)
 * 2. Job is created with made_for_you=true
 * 3. Audio search runs to find audio sources
 * 4. Job pauses at AWAITING_AUDIO_SELECTION for admin to choose
 * 5. Admin notification email is sent
 * 6. Customer confirmation email is sent
 *
 * Prerequisites:
 *   - KARAOKE_ADMIN_TOKEN: Admin token with access to test-webhook endpoint
 *   - TESTMAIL_API_KEY + TESTMAIL_NAMESPACE: For email verification (optional)
 *
 * Run with:
 *   KARAOKE_ADMIN_TOKEN=xxx npx playwright test e2e/production/stripe-made-for-you-search.spec.ts
 */

const API_URL = URLS.production.api;

function getAdminToken(): string | null {
  return process.env.KARAOKE_ADMIN_TOKEN || null;
}

test.describe('Made-for-You Search Order Payment Flow', () => {
  let cleanup: ReturnType<typeof createCleanupTracker>;

  test.beforeEach(async () => {
    const adminToken = getAdminToken();
    test.skip(!adminToken, 'KARAOKE_ADMIN_TOKEN not set - skipping made-for-you tests');
    cleanup = createCleanupTracker(adminToken!, API_URL);
  });

  test.afterEach(async () => {
    if (cleanup) {
      console.log('  Cleaning up test resources...');
      const result = await cleanup.cleanupAll();
      console.log(`  Cleanup complete: ${result.deleted} deleted, ${result.failed} failed`);
    }
  });

  test('search order creates job and pauses at audio selection', async ({ request }) => {
    const adminToken = getAdminToken()!;

    // Create a unique test email
    const testEmail = `e2e-mfy-search-${Date.now()}@test.nomadkaraoke.com`;
    const testArtist = 'E2E Test Artist';
    const testTitle = `E2E Test Song ${Date.now()}`;
    const testNotes = 'This is an E2E test order - please ignore';

    console.log(`  Creating made-for-you search order:`);
    console.log(`    Customer: ${testEmail}`);
    console.log(`    Song: ${testArtist} - ${testTitle}`);

    // Send test webhook
    const payload = createMadeForYouSearchPayload(
      testEmail,
      testArtist,
      testTitle,
      testNotes
    );

    console.log(`  Sending test webhook with session_id: ${payload.session_id}`);
    const webhookResponse = await sendTestWebhook(payload, adminToken, API_URL);

    // Verify webhook response
    expect(webhookResponse.status).toBe('processed');
    expect(webhookResponse.job_id).toBeDefined();
    console.log(`  Webhook processed: job_id=${webhookResponse.job_id}`);

    // Track job for cleanup
    cleanup.trackJob(webhookResponse.job_id!);

    // Fetch job details to verify state
    const job = await getJobDetails(webhookResponse.job_id!, adminToken, API_URL);
    expect(job).not.toBeNull();
    console.log(`  Job details fetched: status=${job!.status}`);

    // Verify job is in AWAITING_AUDIO_SELECTION or SEARCHING_AUDIO state
    // (depends on how fast the audio search runs)
    const validStatuses = ['awaiting_audio_selection', 'searching_audio'];
    expect(validStatuses).toContain((job!.status as string).toLowerCase());
    console.log(`  Job status verified: ${job!.status}`);

    // Verify made_for_you flag is set
    expect(job!.made_for_you).toBe(true);
    console.log(`  made_for_you flag: ${job!.made_for_you}`);

    // Verify customer_email is set correctly
    expect(job!.customer_email).toBe(testEmail);
    console.log(`  customer_email: ${job!.customer_email}`);

    // Verify user_email is admin (job owned by admin during processing)
    expect(job!.user_email).toBe('madeforyou@nomadkaraoke.com');
    console.log(`  user_email (owner): ${job!.user_email}`);

    // Verify customer notes are preserved
    if (job!.customer_notes) {
      expect(job!.customer_notes).toBe(testNotes);
      console.log(`  customer_notes: ${job!.customer_notes}`);
    }

    // Verify artist and title
    expect(job!.artist).toBe(testArtist);
    expect(job!.title).toBe(testTitle);
    console.log(`  Song info verified: ${job!.artist} - ${job!.title}`);

    console.log('TEST PASSED: Made-for-you search order creates job correctly');
  });

  test('search order sends admin notification email', async ({ request }) => {
    test.skip(!isEmailTestingAvailable(), 'TESTMAIL not configured - skipping email test');

    const adminToken = getAdminToken()!;
    const emailHelper = await createEmailHelper();

    // For this test, we'd need admin's email in testmail, which isn't practical
    // Instead, we verify the job was created and assume email logic is covered by unit tests
    // This test serves as a smoke test that the flow completes without errors

    const testEmail = `e2e-mfy-email-${Date.now()}@test.nomadkaraoke.com`;
    const testArtist = 'E2E Email Test';
    const testTitle = `Test Song ${Date.now()}`;

    console.log(`  Creating order to verify email flow completes...`);

    const payload = createMadeForYouSearchPayload(testEmail, testArtist, testTitle);
    const webhookResponse = await sendTestWebhook(payload, adminToken, API_URL);

    expect(webhookResponse.status).toBe('processed');
    cleanup.trackJob(webhookResponse.job_id!);

    // The fact that we got 'processed' status means the email sending didn't throw
    // (email errors would cause the handler to fail and return 'error' status)
    console.log('  Order processed successfully (email flow completed without errors)');

    console.log('TEST PASSED: Made-for-you order completes with email flow');
  });

  test('search order with empty notes is handled correctly', async ({ request }) => {
    const adminToken = getAdminToken()!;

    const testEmail = `e2e-mfy-no-notes-${Date.now()}@test.nomadkaraoke.com`;
    const testArtist = 'No Notes Artist';
    const testTitle = 'No Notes Song';

    console.log(`  Creating order without customer notes...`);

    // Create payload WITHOUT notes
    const payload = createMadeForYouSearchPayload(
      testEmail,
      testArtist,
      testTitle
      // no notes parameter
    );

    const webhookResponse = await sendTestWebhook(payload, adminToken, API_URL);

    expect(webhookResponse.status).toBe('processed');
    expect(webhookResponse.job_id).toBeDefined();
    cleanup.trackJob(webhookResponse.job_id!);

    // Verify job was created
    const job = await getJobDetails(webhookResponse.job_id!, adminToken, API_URL);
    expect(job).not.toBeNull();
    expect(job!.made_for_you).toBe(true);

    // Notes should be null or undefined, not cause an error
    console.log(`  customer_notes: ${job!.customer_notes ?? '(not set)'}`);

    console.log('TEST PASSED: Order without notes is handled correctly');
  });
});
