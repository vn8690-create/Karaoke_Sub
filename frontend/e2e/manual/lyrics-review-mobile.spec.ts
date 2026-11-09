import { test, expect, Page } from '@playwright/test';

/**
 * Mobile Responsiveness Tests for Lyrics Review UI
 *
 * Tests the lyrics review frontend at localhost:8767 for mobile compatibility.
 */

// Common mobile viewport sizes
const MOBILE_VIEWPORTS = {
  'iPhone SE': { width: 375, height: 667 },
  'iPhone 14': { width: 390, height: 844 },
  'Pixel 7': { width: 412, height: 915 },
} as const;

// Helper to check no horizontal overflow
async function hasNoHorizontalOverflow(page: Page): Promise<boolean> {
  return await page.evaluate(() => {
    const docWidth = document.documentElement.scrollWidth;
    const viewportWidth = window.innerWidth;
    return docWidth <= viewportWidth + 2; // Allow 2px tolerance
  });
}

// Use dev server with API pointing to test server
const BASE_URL = 'http://localhost:5173?baseApiUrl=http%3A%2F%2Flocalhost%3A8767%2Fapi';

test.describe('Lyrics Review UI - Mobile Responsiveness', () => {
  for (const [deviceName, viewport] of Object.entries(MOBILE_VIEWPORTS)) {
    test(`${deviceName}: No horizontal overflow`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto(BASE_URL);
      await page.waitForLoadState('networkidle');

      // Wait for content to render
      await page.waitForTimeout(1000);

      const noOverflow = await hasNoHorizontalOverflow(page);
      expect(noOverflow).toBe(true);
    });

    test(`${deviceName}: Header content is visible`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto(BASE_URL);
      await page.waitForLoadState('networkidle');

      // Wait for content
      await page.waitForTimeout(1000);

      // Header title should be visible
      await expect(page.locator('text=Nomad Karaoke')).toBeVisible({ timeout: 5000 });
    });

    test(`${deviceName}: Lyrics segments are visible`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto(BASE_URL);
      await page.waitForLoadState('networkidle');

      // Wait for content
      await page.waitForTimeout(1000);

      // Should show lyrics text
      await expect(page.locator('body')).toContainText('Hello', { timeout: 5000 });
    });

    test(`${deviceName}: Action buttons fit viewport`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto(BASE_URL);
      await page.waitForLoadState('networkidle');

      // Wait for content
      await page.waitForTimeout(1000);

      // Look for action buttons (Find/Replace, Edit All, etc.)
      const findReplaceBtn = page.getByRole('button', { name: /find.*replace/i });

      if (await findReplaceBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        const box = await findReplaceBtn.boundingBox();
        if (box) {
          // Button should be within viewport
          expect(box.x).toBeGreaterThanOrEqual(0);
          expect(box.x + box.width).toBeLessThanOrEqual(viewport.width + 10);
        }
      }
    });
  }

  test('Screenshot comparison - iPhone SE', async ({ page }) => {
    await page.setViewportSize(MOBILE_VIEWPORTS['iPhone SE']);
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Take screenshot for visual verification
    await page.screenshot({
      path: '/tmp/lyrics-review-mobile-iphone-se.png',
      fullPage: true
    });

    // Just verify content loaded
    await expect(page.locator('body')).toContainText('Hello');
  });

  test('Screenshot comparison - Desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Take screenshot for visual verification
    await page.screenshot({
      path: '/tmp/lyrics-review-desktop.png',
      fullPage: true
    });

    // Just verify content loaded
    await expect(page.locator('body')).toContainText('Hello');
  });
});
