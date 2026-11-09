import { test, expect } from '@playwright/test';

test('lyrics review UI loads test data correctly', async ({ page }) => {
  // Navigate to the UI with the API URL parameter
  const url = 'http://localhost:8767?baseApiUrl=http%3A%2F%2Flocalhost%3A8767%2Fapi';
  
  await page.goto(url);
  await page.waitForLoadState('networkidle');
  
  // Wait for content to render
  await page.waitForTimeout(2000);
  
  // Check NOT in read-only mode
  const pageContent = await page.content();
  expect(pageContent.toLowerCase()).not.toContain('read-only mode');
  
  // Check for lyrics content - look for actual words from test data
  await expect(page.locator('body')).toContainText('Hello', { timeout: 5000 });
  
  // Take screenshot for verification
  await page.screenshot({ path: '/tmp/lyrics-review-test.png', fullPage: true });
});
