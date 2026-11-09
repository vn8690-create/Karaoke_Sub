import { test, expect } from '@playwright/test';
import { URLS } from '../helpers/constants';

/**
 * E2E Tests for Webhook Security
 *
 * Validates that:
 * 1. Real Stripe webhook endpoint properly validates signatures
 * 2. Test webhook endpoint requires admin authentication
 * 3. Session ID prefix validation prevents collision with real sessions
 *
 * These tests verify the security boundary between production webhook
 * handling and test webhook handling.
 *
 * Prerequisites:
 *   - KARAOKE_ADMIN_TOKEN: For test-webhook authentication tests
 *
 * Run with:
 *   KARAOKE_ADMIN_TOKEN=xxx npx playwright test e2e/production/stripe-webhook-security.spec.ts
 */

const API_URL = URLS.production.api;

function getAdminToken(): string | null {
  return process.env.KARAOKE_ADMIN_TOKEN || null;
}

test.describe('Webhook Security - Real Stripe Endpoint', () => {
  test('real webhook endpoint rejects requests without signature', async ({ request }) => {
    /**
     * The real /api/users/webhooks/stripe endpoint requires a valid
     * Stripe signature header. Without it, the request should be rejected.
     */
    const response = await request.post(`${API_URL}/api/users/webhooks/stripe`, {
      headers: {
        'Content-Type': 'application/json',
        // No stripe-signature header
      },
      data: JSON.stringify({
        type: 'checkout.session.completed',
        data: {
          object: {
            id: 'cs_fake_123',
            customer_email: 'attacker@evil.com',
            metadata: {
              package_id: '1_credit',
              credits: '1000',
              user_email: 'victim@example.com',
            },
          },
        },
      }),
    });

    // Should be rejected - 400 Bad Request (missing signature)
    expect(response.status()).toBe(400);
    console.log(`  Missing signature: ${response.status()} (expected 400)`);
  });

  test('real webhook endpoint rejects requests with invalid signature', async ({ request }) => {
    /**
     * The real webhook endpoint should reject requests with an invalid
     * or forged Stripe signature.
     */
    const response = await request.post(`${API_URL}/api/users/webhooks/stripe`, {
      headers: {
        'Content-Type': 'application/json',
        'stripe-signature': 'fake_signature_t=12345,v1=fakehash',
      },
      data: JSON.stringify({
        type: 'checkout.session.completed',
        data: {
          object: {
            id: 'cs_fake_456',
            customer_email: 'attacker@evil.com',
            metadata: {
              package_id: '1_credit',
              credits: '1000',
            },
          },
        },
      }),
    });

    // Should be rejected - 400 Bad Request (invalid signature)
    expect(response.status()).toBe(400);
    console.log(`  Invalid signature: ${response.status()} (expected 400)`);
  });

  test('real webhook endpoint rejects malformed signature header', async ({ request }) => {
    /**
     * Test that malformed signature headers are properly rejected.
     */
    const response = await request.post(`${API_URL}/api/users/webhooks/stripe`, {
      headers: {
        'Content-Type': 'application/json',
        'stripe-signature': 'not_a_valid_format',
      },
      data: JSON.stringify({
        type: 'checkout.session.completed',
        data: { object: {} },
      }),
    });

    // Should be rejected
    expect(response.status()).toBe(400);
    console.log(`  Malformed signature: ${response.status()} (expected 400)`);
  });
});

test.describe('Webhook Security - Test Webhook Endpoint', () => {
  test('test-webhook endpoint requires admin authentication', async ({ request }) => {
    /**
     * The test-webhook endpoint must require admin authentication.
     * Without a valid admin token, requests should be rejected.
     */
    const response = await request.post(`${API_URL}/api/internal/test-webhook`, {
      headers: {
        'Content-Type': 'application/json',
        // No Authorization header
      },
      data: JSON.stringify({
        event_type: 'checkout.session.completed',
        session_id: 'e2e-test-security-1',
        customer_email: 'test@example.com',
        metadata: {
          package_id: '1_credit',
          credits: '1',
          user_email: 'test@example.com',
        },
      }),
    });

    // Should be rejected - 401 Unauthorized
    expect(response.status()).toBe(401);
    console.log(`  Missing auth: ${response.status()} (expected 401)`);
  });

  test('test-webhook endpoint rejects invalid admin token', async ({ request }) => {
    /**
     * Invalid admin tokens should be rejected.
     */
    const response = await request.post(`${API_URL}/api/internal/test-webhook`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer invalid_fake_token_12345',
      },
      data: JSON.stringify({
        event_type: 'checkout.session.completed',
        session_id: 'e2e-test-security-2',
        customer_email: 'test@example.com',
        metadata: {
          package_id: '1_credit',
          credits: '1',
        },
      }),
    });

    // Should be rejected - 401 Unauthorized
    expect(response.status()).toBe(401);
    console.log(`  Invalid token: ${response.status()} (expected 401)`);
  });

  test('test-webhook endpoint rejects session IDs without e2e-test- prefix', async ({ request }) => {
    /**
     * Test webhook endpoint must reject session IDs that don't start
     * with "e2e-test-" to prevent collision with real Stripe sessions.
     */
    const adminToken = getAdminToken();
    test.skip(!adminToken, 'KARAOKE_ADMIN_TOKEN not set');

    const response = await request.post(`${API_URL}/api/internal/test-webhook`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${adminToken}`,
      },
      data: JSON.stringify({
        event_type: 'checkout.session.completed',
        session_id: 'cs_live_abc123', // Looks like a real Stripe session
        customer_email: 'test@example.com',
        metadata: {
          package_id: '1_credit',
          credits: '1',
        },
      }),
    });

    // Should be rejected - 400 Bad Request
    expect(response.status()).toBe(400);

    const data = await response.json();
    expect(data.detail).toContain('e2e-test-');
    console.log(`  Invalid prefix: ${response.status()} (expected 400)`);
    console.log(`  Error message: ${data.detail}`);
  });

  test('test-webhook endpoint accepts valid admin token with correct prefix', async ({ request }) => {
    /**
     * With valid admin token AND correct session ID prefix, the endpoint
     * should accept the request (though it may return an error for other reasons).
     */
    const adminToken = getAdminToken();
    test.skip(!adminToken, 'KARAOKE_ADMIN_TOKEN not set');

    const response = await request.post(`${API_URL}/api/internal/test-webhook`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${adminToken}`,
      },
      data: JSON.stringify({
        event_type: 'checkout.session.completed',
        session_id: 'e2e-test-security-valid',
        customer_email: 'test@example.com',
        metadata: {
          package_id: '1_credit',
          credits: '1',
          user_email: 'test@example.com',
        },
      }),
    });

    // Should be accepted (200 OK) - the request passes security checks
    expect(response.status()).toBe(200);
    console.log(`  Valid request: ${response.status()} (expected 200)`);
  });
});

test.describe('Webhook Security - X-Admin-Token Header', () => {
  test('test-webhook accepts X-Admin-Token header', async ({ request }) => {
    /**
     * The internal API should accept X-Admin-Token header for authentication.
     */
    const adminToken = getAdminToken();
    test.skip(!adminToken, 'KARAOKE_ADMIN_TOKEN not set');

    const response = await request.post(`${API_URL}/api/internal/test-webhook`, {
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': adminToken,
      },
      data: JSON.stringify({
        event_type: 'checkout.session.completed',
        session_id: 'e2e-test-x-admin-header',
        customer_email: 'test@example.com',
        metadata: {
          package_id: '1_credit',
          credits: '1',
          user_email: 'test@example.com',
        },
      }),
    });

    // Should be accepted with X-Admin-Token header
    expect(response.status()).toBe(200);
    console.log(`  X-Admin-Token header: ${response.status()} (expected 200)`);
  });
});

test.describe('Webhook Security - Rate Limiting', () => {
  test('test-webhook is accessible for legitimate testing purposes', async ({ request }) => {
    /**
     * While we have security controls, the endpoint should still be usable
     * for legitimate E2E testing when properly authenticated.
     *
     * This test makes multiple requests to ensure the endpoint is available.
     */
    const adminToken = getAdminToken();
    test.skip(!adminToken, 'KARAOKE_ADMIN_TOKEN not set');

    // Make 3 sequential requests
    const results: number[] = [];

    for (let i = 0; i < 3; i++) {
      const response = await request.post(`${API_URL}/api/internal/test-webhook`, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${adminToken}`,
        },
        data: JSON.stringify({
          event_type: 'checkout.session.completed',
          session_id: `e2e-test-rate-limit-${Date.now()}-${i}`,
          customer_email: 'test@example.com',
          metadata: {
            package_id: '1_credit',
            credits: '1',
            user_email: 'test@example.com',
          },
        }),
      });

      results.push(response.status());

      // Small delay between requests
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    // All requests should succeed
    results.forEach((status, i) => {
      expect(status).toBe(200);
      console.log(`  Request ${i + 1}: ${status}`);
    });

    console.log('TEST PASSED: Multiple test requests succeed');
  });
});
