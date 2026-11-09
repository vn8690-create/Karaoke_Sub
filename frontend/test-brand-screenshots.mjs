/**
 * Brand consistency visual testing script
 * Takes screenshots of key pages in both light and dark modes
 * for visual verification of brand colors.
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { mkdir } from 'fs/promises';

const __dirname = dirname(fileURLToPath(import.meta.url));
const screenshotsDir = join(__dirname, 'brand-screenshots');

async function takeScreenshots() {
  // Create screenshots directory
  await mkdir(screenshotsDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 }
  });
  const page = await context.newPage();

  const baseUrl = 'http://localhost:3000';

  console.log('Taking screenshots...\n');
  console.log('=== DARK MODE ===\n');

  // Landing page - dark mode (default)
  console.log('1. Landing page (dark mode)...');
  await page.goto(baseUrl, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000); // Wait for animations
  await page.screenshot({
    path: join(screenshotsDir, '01-landing-dark.png'),
    fullPage: true
  });
  console.log('   ✓ Saved: 01-landing-dark.png');

  // Scroll to beta section
  console.log('2. Beta section (dark mode)...');
  await page.evaluate(() => {
    const betaSection = document.querySelector('[class*="beta"]') ||
                        document.evaluate("//h3[contains(text(),'Try It Free')]", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue?.closest('section');
    if (betaSection) betaSection.scrollIntoView({ behavior: 'instant' });
  });
  await page.waitForTimeout(500);
  await page.screenshot({
    path: join(screenshotsDir, '02-beta-section-dark.png'),
    fullPage: false
  });
  console.log('   ✓ Saved: 02-beta-section-dark.png');

  // Scroll to pricing section
  console.log('3. Pricing section (dark mode)...');
  await page.goto(`${baseUrl}#pricing`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  await page.screenshot({
    path: join(screenshotsDir, '03-pricing-dark.png'),
    fullPage: false
  });
  console.log('   ✓ Saved: 03-pricing-dark.png');

  // Footer
  console.log('4. Footer (dark mode)...');
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);
  await page.screenshot({
    path: join(screenshotsDir, '04-footer-dark.png'),
    fullPage: false
  });
  console.log('   ✓ Saved: 04-footer-dark.png');

  // === LIGHT MODE ===
  console.log('\n=== LIGHT MODE ===\n');

  // Create a new context with localStorage preset for light mode
  console.log('Switching to light mode...');
  const lightContext = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    storageState: {
      cookies: [],
      origins: [{
        origin: baseUrl,
        localStorage: [
          { name: 'theme', value: 'light' },
          { name: 'nomad-karaoke-theme', value: 'light' }
        ]
      }]
    }
  });
  const lightPage = await lightContext.newPage();

  // Landing page - light mode
  console.log('5. Landing page (light mode)...');
  await lightPage.goto(baseUrl, { waitUntil: 'networkidle' });
  await lightPage.waitForTimeout(1000);
  await lightPage.screenshot({
    path: join(screenshotsDir, '05-landing-light.png'),
    fullPage: true
  });
  console.log('   ✓ Saved: 05-landing-light.png');

  // Scroll to beta section
  console.log('6. Beta section (light mode)...');
  await lightPage.evaluate(() => {
    const betaSection = document.querySelector('[class*="beta"]') ||
                        document.evaluate("//h3[contains(text(),'Try It Free')]", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue?.closest('section');
    if (betaSection) betaSection.scrollIntoView({ behavior: 'instant' });
  });
  await lightPage.waitForTimeout(500);
  await lightPage.screenshot({
    path: join(screenshotsDir, '06-beta-section-light.png'),
    fullPage: false
  });
  console.log('   ✓ Saved: 06-beta-section-light.png');

  // Scroll to pricing section
  console.log('7. Pricing section (light mode)...');
  await lightPage.goto(`${baseUrl}#pricing`, { waitUntil: 'networkidle' });
  await lightPage.waitForTimeout(500);
  await lightPage.screenshot({
    path: join(screenshotsDir, '07-pricing-light.png'),
    fullPage: false
  });
  console.log('   ✓ Saved: 07-pricing-light.png');

  // Footer
  console.log('8. Footer (light mode)...');
  await lightPage.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await lightPage.waitForTimeout(500);
  await lightPage.screenshot({
    path: join(screenshotsDir, '08-footer-light.png'),
    fullPage: false
  });
  console.log('   ✓ Saved: 08-footer-light.png');

  await lightContext.close();

  // Note: App page requires authentication, so we can't test it directly
  // The instrumental and lyrics review pages require specific job data

  await browser.close();

  console.log('\n✅ Screenshots saved to:', screenshotsDir);
  console.log('\nReview checklist:');
  console.log('1. Primary buttons should be brand pink (#ff7acc) in both modes');
  console.log('2. Gradients should flow to pink in both modes');
  console.log('3. Beta section badge and button should be brand pink');
  console.log('4. Light mode backgrounds should be light, text should be dark');
  console.log('5. Dark mode backgrounds should be dark, text should be light');
}

takeScreenshots().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
