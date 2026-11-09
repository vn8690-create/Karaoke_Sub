/**
 * Stripe Test Client for E2E Testing
 *
 * Provides helpers for sending test webhook events to the backend's
 * /api/internal/test-webhook endpoint. This allows E2E tests to simulate
 * Stripe payment flows without requiring actual Stripe checkout sessions.
 *
 * Usage:
 *   const response = await sendTestWebhook(
 *     createCreditPurchasePayload('user@example.com', 1),
 *     adminToken
 *   );
 *   expect(response.status).toBe('processed');
 *   expect(response.credits_added).toBe(1);
 */

import { URLS } from './constants';

/**
 * Payload structure for test webhooks.
 * Mirrors the backend's TestWebhookRequest model.
 */
export interface TestWebhookPayload {
  event_type: string;
  session_id: string;
  customer_email: string;
  metadata: Record<string, string>;
}

/**
 * Response structure from test webhooks.
 * Mirrors the backend's TestWebhookResponse model.
 */
export interface TestWebhookResponse {
  status: 'processed' | 'already_processed' | 'error';
  job_id?: string;
  credits_added?: number;
  new_balance?: number;
  message: string;
}

/**
 * Generate a unique test session ID.
 * All test session IDs must start with "e2e-test-" prefix.
 */
export function generateTestSessionId(prefix = 'e2e-test'): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 8);
  return `${prefix}-${timestamp}-${random}`;
}

/**
 * Send a test webhook to the backend.
 *
 * @param payload - The webhook payload to send
 * @param adminToken - Admin token for authentication
 * @param apiUrl - API URL (defaults to production)
 * @returns The webhook response
 */
export async function sendTestWebhook(
  payload: TestWebhookPayload,
  adminToken: string,
  apiUrl: string = URLS.production.api
): Promise<TestWebhookResponse> {
  const response = await fetch(`${apiUrl}/api/internal/test-webhook`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${adminToken}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Test webhook failed with status ${response.status}: ${errorText}`);
  }

  return response.json();
}

/**
 * Create a credit purchase webhook payload.
 *
 * @param email - User email to credit
 * @param credits - Number of credits to add
 * @param packageId - Package ID (defaults based on credit count)
 * @returns Webhook payload for credit purchase
 */
export function createCreditPurchasePayload(
  email: string,
  credits: number,
  packageId?: string
): TestWebhookPayload {
  // Map credit count to package ID if not provided
  const resolvedPackageId = packageId || `${credits}_credit${credits > 1 ? 's' : ''}`;

  return {
    event_type: 'checkout.session.completed',
    session_id: generateTestSessionId('e2e-test-credit'),
    customer_email: email,
    metadata: {
      package_id: resolvedPackageId,
      credits: String(credits),
      user_email: email,
    },
  };
}

/**
 * Create a made-for-you search order webhook payload.
 *
 * Search orders pause at AWAITING_AUDIO_SELECTION for admin to select audio.
 *
 * @param customerEmail - Customer email for delivery
 * @param artist - Song artist
 * @param title - Song title
 * @param notes - Optional customer notes
 * @returns Webhook payload for made-for-you search order
 */
export function createMadeForYouSearchPayload(
  customerEmail: string,
  artist: string,
  title: string,
  notes?: string
): TestWebhookPayload {
  const metadata: Record<string, string> = {
    order_type: 'made_for_you',
    customer_email: customerEmail,
    artist: artist,
    title: title,
    source_type: 'search',
  };

  if (notes) {
    metadata.notes = notes;
  }

  return {
    event_type: 'checkout.session.completed',
    session_id: generateTestSessionId('e2e-test-mfy-search'),
    customer_email: customerEmail,
    metadata,
  };
}

/**
 * Create a made-for-you YouTube URL order webhook payload.
 *
 * YouTube orders download audio first, then trigger workers immediately.
 * CRITICAL: This tests the flow that had the recent bug where input_media_gcs_path
 * was not set before triggering workers.
 *
 * @param customerEmail - Customer email for delivery
 * @param artist - Song artist
 * @param title - Song title
 * @param youtubeUrl - YouTube URL for audio
 * @param notes - Optional customer notes
 * @returns Webhook payload for made-for-you YouTube order
 */
export function createMadeForYouYouTubePayload(
  customerEmail: string,
  artist: string,
  title: string,
  youtubeUrl: string,
  notes?: string
): TestWebhookPayload {
  const metadata: Record<string, string> = {
    order_type: 'made_for_you',
    customer_email: customerEmail,
    artist: artist,
    title: title,
    source_type: 'youtube',
    youtube_url: youtubeUrl,
  };

  if (notes) {
    metadata.notes = notes;
  }

  return {
    event_type: 'checkout.session.completed',
    session_id: generateTestSessionId('e2e-test-mfy-youtube'),
    customer_email: customerEmail,
    metadata,
  };
}

/**
 * Get job details from the API.
 * Useful for verifying job state after test webhook processing.
 *
 * @param jobId - Job ID to fetch
 * @param adminToken - Admin token for authentication
 * @param apiUrl - API URL (defaults to production)
 * @returns Job details or null if not found
 */
export async function getJobDetails(
  jobId: string,
  adminToken: string,
  apiUrl: string = URLS.production.api
): Promise<Record<string, unknown> | null> {
  const response = await fetch(`${apiUrl}/api/jobs/${jobId}`, {
    headers: {
      'Authorization': `Bearer ${adminToken}`,
    },
  });

  if (!response.ok) {
    if (response.status === 404) {
      return null;
    }
    throw new Error(`Failed to fetch job: ${response.status}`);
  }

  return response.json();
}

/**
 * Get user details from the API.
 * Useful for verifying credit balance after purchase.
 *
 * @param email - User email
 * @param token - Auth token (can be user's own token or admin token)
 * @param apiUrl - API URL (defaults to production)
 * @returns User details or null if not found
 */
export async function getUserDetails(
  email: string,
  token: string,
  apiUrl: string = URLS.production.api
): Promise<{ email: string; credits: number } | null> {
  // For the user's own details
  const response = await fetch(`${apiUrl}/api/users/me`, {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    return null;
  }

  const data = await response.json();
  return {
    email: data.user?.email,
    credits: data.user?.credits ?? 0,
  };
}
