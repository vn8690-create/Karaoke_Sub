#!/usr/bin/env node
/**
 * Fixture Review Driver
 *
 * Loads one fixture at a time into the guided flow, takes a screenshot,
 * and writes it to a predictable path for review.
 *
 * Usage:
 *   node e2e/fixtures/review-driver.mjs <fixture-index> [screenshot-path]
 *
 * fixture-index: 0-based index into the fixture index.json
 * screenshot-path: optional, defaults to /tmp/fixture-review.png
 */

import { chromium } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES_DIR = path.join(__dirname, 'data', 'search-results');
const INDEX_PATH = path.join(FIXTURES_DIR, 'index.json');

const fixtureIdx = parseInt(process.argv[2] || '0', 10);
const screenshotPath = process.argv[3] || '/tmp/fixture-review.png';

// Load fixture
const index = JSON.parse(fs.readFileSync(INDEX_PATH, 'utf-8'));
if (fixtureIdx < 0 || fixtureIdx >= index.length) {
  console.error(`Invalid fixture index ${fixtureIdx}. Range: 0-${index.length - 1}`);
  process.exit(1);
}

const entry = index[fixtureIdx];
const fixture = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, entry.file), 'utf-8'));

console.log(`Loading fixture ${fixtureIdx + 1}/${index.length}: ${entry.artist} - ${entry.title} (${entry.resultCount} results)`);

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext();
const page = await context.newPage();

// Set up API mocks
await page.route('**/api/**', async (route) => {
  const req = route.request();
  const method = req.method();
  const url = new URL(req.url());
  const apiPath = url.pathname;

  if (method === 'POST' && apiPath === '/api/audio-search/search') {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ job_id: 'fixture-review', status: 'audio_search' }) });
  }
  if (method === 'GET' && apiPath.includes('/api/audio-search/') && apiPath.includes('/results')) {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ results: fixture.results, status: 'search_complete' }) });
  }
  if (method === 'POST' && apiPath.includes('/api/audio-search/') && apiPath.includes('/select')) {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ job_id: 'fixture-review', status: 'downloading' }) });
  }
  if (method === 'GET' && apiPath === '/api/jobs') {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  }
  if (method === 'GET' && apiPath === '/api/users/me') {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user: { email: 'reviewer@test.com', credits: 99, role: 'admin' }, has_session: true }) });
  }
  if (method === 'GET' && apiPath === '/api/themes') {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ themes: [] }) });
  }
  if (method === 'GET' && apiPath === '/api/users/credits/packages') {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ packages: [] }) });
  }
  return route.continue();
});

// Set auth token
await page.addInitScript(() => {
  localStorage.setItem('karaoke_access_token', 'fixture-review-token');
});

// Navigate to app
await page.goto('http://127.0.0.1:3000/app');
await page.getByLabel(/artist/i).waitFor({ timeout: 15000 });

// Fill in artist and title
await page.getByLabel(/artist/i).fill(entry.artist);
await page.getByLabel(/title/i).fill(entry.title);

// Click Choose Audio
await page.getByRole('button', { name: /choose audio/i }).click();

// Wait for results
try {
  await page.getByText('Perfect match found')
    .or(page.getByText('Recommended'))
    .or(page.getByText('Limited sources found'))
    .or(page.getByText(/no audio sources/i))
    .waitFor({ timeout: 15000 });
} catch {
  console.log('Warning: tier text not found within timeout, taking screenshot anyway');
}

// Small delay for any animations
await page.waitForTimeout(500);

// Take full-page screenshot
await page.screenshot({ path: screenshotPath, fullPage: true });
console.log(`Screenshot saved: ${screenshotPath}`);

await browser.close();
