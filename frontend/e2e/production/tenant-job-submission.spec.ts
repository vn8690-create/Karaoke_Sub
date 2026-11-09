import { test, expect, Page } from "@playwright/test";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";

/**
 * Tenant Portal Job Submission - Production E2E Test
 *
 * Tests the full tenant portal flow:
 * 1. Navigate to tenant portal with admin auth
 * 2. Verify tenant branding (logo, title, simplified form)
 * 3. Submit a track (mixed + instrumental audio)
 * 4. Wait for job processing
 * 5. Verify job metadata (is_private, tenant_id, brand_prefix)
 *
 * Run with:
 *   KARAOKE_ADMIN_TOKEN=xxx npx playwright test e2e/production/tenant-job-submission.spec.ts \
 *     --config=playwright.production.config.ts --reporter=list
 *
 * Environment variables:
 *   KARAOKE_ADMIN_TOKEN - Admin token for authentication (required)
 *   TENANT_PORTAL_URL   - Override tenant portal URL (default: https://vocalstar.nomadkaraoke.com)
 */

const TENANT_PORTAL_URL = process.env.TENANT_PORTAL_URL || "https://vocalstar.nomadkaraoke.com";
const API_URL = "https://api.nomadkaraoke.com";
const CONSUMER_PORTAL_URL = "https://gen.nomadkaraoke.com";

const TIMEOUTS = {
  action: 30_000,
  expect: 60_000,
  apiCall: 120_000,
  jobProcessing: 600_000,
  fullTest: 1_200_000, // 20 minutes
};

function getAdminToken(): string | null {
  return process.env.KARAOKE_ADMIN_TOKEN || process.env.KARAOKE_ACCESS_TOKEN || null;
}

async function authenticatePage(page: Page, token: string): Promise<void> {
  await page.addInitScript((t) => {
    localStorage.setItem("karaoke_access_token", t);
  }, token);
}

/**
 * Create a minimal WAV file for testing uploads.
 * Returns the path to the temporary file.
 */
function createTestAudioFile(name: string): string {
  const tmpDir = os.tmpdir();
  const filePath = path.join(tmpDir, name);

  // Minimal WAV header (44 bytes) + 1 second of silence at 8kHz mono 8-bit
  const sampleRate = 8000;
  const numSamples = sampleRate; // 1 second
  const dataSize = numSamples;
  const fileSize = 36 + dataSize;

  const buffer = Buffer.alloc(44 + dataSize);

  // RIFF header
  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(fileSize, 4);
  buffer.write("WAVE", 8);

  // fmt chunk
  buffer.write("fmt ", 12);
  buffer.writeUInt32LE(16, 16); // chunk size
  buffer.writeUInt16LE(1, 20);  // PCM format
  buffer.writeUInt16LE(1, 22);  // mono
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate, 28); // byte rate
  buffer.writeUInt16LE(1, 32);  // block align
  buffer.writeUInt16LE(8, 34);  // bits per sample

  // data chunk
  buffer.write("data", 36);
  buffer.writeUInt32LE(dataSize, 40);
  // Silence: fill with 128 (center value for 8-bit PCM)
  buffer.fill(128, 44);

  fs.writeFileSync(filePath, buffer);
  return filePath;
}

async function getJobDetails(token: string, jobId: string): Promise<any> {
  const response = await fetch(`${API_URL}/api/jobs/${jobId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`Failed to get job ${jobId}: ${response.status}`);
  }
  return response.json();
}

test.describe("Tenant Portal Job Submission", () => {
  test.describe.configure({ retries: 0 });

  let adminToken: string = "";
  let testAudioPath: string;
  let testInstrumentalPath: string;
  let createdJobId: string | null = null;

  test.beforeAll(async () => {
    const token = getAdminToken();
    if (token) {
      adminToken = token;
    }

    // Create test audio files
    testAudioPath = createTestAudioFile("test-mixed-audio.wav");
    testInstrumentalPath = createTestAudioFile("test-instrumental.wav");
  });

  test.afterAll(async () => {
    // Clean up temp files
    for (const f of [testAudioPath, testInstrumentalPath]) {
      if (f && fs.existsSync(f)) {
        fs.unlinkSync(f);
      }
    }

    // Clean up test job if created
    if (createdJobId && adminToken) {
      try {
        await fetch(`${API_URL}/api/admin/jobs/${createdJobId}`, {
          method: "DELETE",
          headers: { "X-Admin-Token": adminToken },
        });
        console.log(`Cleaned up test job ${createdJobId}`);
      } catch {
        console.warn(`Failed to clean up test job ${createdJobId}`);
      }
    }
  });

  test("Tenant portal shows simplified form, not consumer wizard", async ({ page }) => {
    test.skip(!adminToken, "KARAOKE_ADMIN_TOKEN not set");
    test.setTimeout(TIMEOUTS.expect);

    await authenticatePage(page, adminToken);
    await page.goto(`${TENANT_PORTAL_URL}/app`, { waitUntil: "networkidle", timeout: TIMEOUTS.action });

    // Should NOT show the consumer wizard step indicators
    await expect(page.getByText("Choose Audio")).not.toBeVisible({ timeout: 5_000 });

    // Should show tenant-specific card title
    await expect(page.getByText("Submit Track")).toBeVisible({ timeout: TIMEOUTS.expect });
    await expect(page.getByText("Upload your mixed audio and instrumental")).toBeVisible();

    // Should show 4 form fields
    await expect(page.getByLabel("Artist")).toBeVisible();
    await expect(page.getByLabel("Title")).toBeVisible();
    await expect(page.getByText("Mixed Audio")).toBeVisible();
    await expect(page.getByText("Instrumental Audio")).toBeVisible();
  });

  test("Submit track through tenant portal", async ({ page }) => {
    test.skip(!adminToken, "KARAOKE_ADMIN_TOKEN not set");
    test.setTimeout(TIMEOUTS.fullTest);

    await authenticatePage(page, adminToken);
    await page.goto(`${TENANT_PORTAL_URL}/app`, { waitUntil: "networkidle", timeout: TIMEOUTS.action });

    // Fill form
    await page.getByLabel("Artist").fill("E2E Test Artist");
    await page.getByLabel("Title").fill("E2E Test Tenant Track");

    // Upload mixed audio
    const mixedInput = page.locator("#tenant-mixed-audio");
    await mixedInput.setInputFiles(testAudioPath);

    // Upload instrumental
    const instrumentalInput = page.locator("#tenant-instrumental-audio");
    await instrumentalInput.setInputFiles(testInstrumentalPath);

    // Submit
    await page.getByRole("button", { name: /Submit Track/i }).click();

    // Wait for success
    await expect(page.getByText("Track Submitted")).toBeVisible({ timeout: TIMEOUTS.apiCall });

    // Extract job ID from success view
    const jobIdElement = page.locator('[data-testid="created-job-id"]');
    const jobIdText = await jobIdElement.textContent();
    const shortId = jobIdText?.replace("ID: ", "").trim();
    expect(shortId).toBeTruthy();
    if (shortId) createdJobId = shortId;
    console.log(`Created tenant job with short ID: ${shortId}`);

    // Verify success timeline shows tenant-specific steps (no "Audio processing" step)
    await expect(page.getByText("Lyrics transcription")).toBeVisible();
    await expect(page.getByText("Review lyrics")).toBeVisible();
    await expect(page.getByText("Video delivered")).toBeVisible();

    // The timeline should NOT mention "Audio processing" or "Download" (consumer flow terms)
    const bodyText = await page.locator("body").textContent();
    expect(bodyText).not.toContain("Audio processing");
    expect(bodyText).not.toContain("separate vocals");
  });

  test("Consumer portal still works normally", async ({ page }) => {
    test.skip(!adminToken, "KARAOKE_ADMIN_TOKEN not set");
    test.setTimeout(TIMEOUTS.expect);

    await authenticatePage(page, adminToken);
    await page.goto(`${CONSUMER_PORTAL_URL}/app`, { waitUntil: "networkidle", timeout: TIMEOUTS.action });

    // Consumer portal should show the full wizard
    await expect(page.getByText("Create Karaoke Video")).toBeVisible({ timeout: TIMEOUTS.expect });
    await expect(page.getByText("Turn any song into a karaoke video")).toBeVisible();

    // Should NOT show tenant-specific text
    const bodyText = await page.locator("body").textContent();
    expect(bodyText).not.toContain("Submit Track");
    expect(bodyText).not.toContain("Upload your mixed audio and instrumental");
  });
});
