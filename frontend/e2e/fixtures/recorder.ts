/**
 * API Fixture Recorder
 *
 * Intercepts API calls during E2E tests and records them for review.
 * Run with RECORD_FIXTURES=true to capture new fixtures.
 */

import { Page, Route, Request } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { ApiFixture, RecordingSession } from './types';

const FIXTURES_DIR = path.join(__dirname, 'data');
// In E2E tests, API calls go through Next.js rewrites to /api/* on the same origin
const API_PATH_PATTERN = '**/api/**';

/**
 * Generate a unique ID for a fixture based on method and path
 */
function generateFixtureId(method: string, urlPath: string): string {
  const sanitizedPath = urlPath
    .replace(/^\/api\/v1\//, '')
    .replace(/\//g, '-')
    .replace(/[^a-zA-Z0-9-]/g, '_');
  return `${method.toLowerCase()}-${sanitizedPath}`;
}

/**
 * Extract path and query from URL
 */
function parseUrl(url: string): { path: string; query: Record<string, string> } {
  const urlObj = new URL(url);
  const query: Record<string, string> = {};
  urlObj.searchParams.forEach((value, key) => {
    query[key] = value;
  });
  return {
    path: urlObj.pathname,
    query: Object.keys(query).length > 0 ? query : undefined as any,
  };
}

/**
 * Redact sensitive information from headers
 */
function redactHeaders(headers: Record<string, string>): Record<string, string> {
  const redacted = { ...headers };
  const sensitiveKeys = ['authorization', 'x-access-token', 'cookie', 'set-cookie'];
  for (const key of sensitiveKeys) {
    if (redacted[key]) {
      redacted[key] = '[REDACTED]';
    }
  }
  return redacted;
}

/**
 * API Recorder class for capturing API calls during tests
 */
export class ApiRecorder {
  private session: RecordingSession;
  private isRecording: boolean = false;
  private outputFile: string;

  constructor(testFile?: string) {
    this.session = {
      sessionId: `session-${Date.now()}`,
      startedAt: new Date().toISOString(),
      testFile,
      calls: [],
    };
    this.outputFile = path.join(
      FIXTURES_DIR,
      'recordings',
      `${this.session.sessionId}.json`
    );
  }

  /**
   * Start recording API calls for a page
   */
  async startRecording(page: Page): Promise<void> {
    if (this.isRecording) {
      console.warn('Recording already in progress');
      return;
    }

    this.isRecording = true;

    // Ensure recordings directory exists
    const recordingsDir = path.dirname(this.outputFile);
    if (!fs.existsSync(recordingsDir)) {
      fs.mkdirSync(recordingsDir, { recursive: true });
    }

    // Intercept all API calls
    await page.route(API_PATH_PATTERN, async (route: Route, request: Request) => {
      const url = request.url();
      const method = request.method();
      const { path: urlPath, query } = parseUrl(url);

      console.log(`📡 [RECORDING] ${method} ${urlPath}`);

      // Let the request proceed and capture the response
      const response = await route.fetch();
      const status = response.status();
      const statusText = response.statusText();

      let body: any;
      try {
        const text = await response.text();
        body = text ? JSON.parse(text) : null;
      } catch {
        body = await response.text();
      }

      // Create fixture entry
      const fixture: ApiFixture = {
        id: generateFixtureId(method, urlPath),
        description: `${method} ${urlPath}`,
        capturedAt: new Date().toISOString(),
        request: {
          method,
          url,
          path: urlPath,
          query,
          body: request.postDataJSON() || undefined,
          headers: redactHeaders(request.headers()),
        },
        response: {
          status,
          statusText,
          body,
        },
        reviewed: false,
      };

      this.session.calls.push(fixture);

      // Save after each call for safety
      this.saveSession();

      // Fulfill with the actual response
      await route.fulfill({
        status,
        headers: response.headers(),
        body: typeof body === 'string' ? body : JSON.stringify(body),
      });
    });

    console.log(`🎬 Started recording API calls to ${this.outputFile}`);
  }

  /**
   * Stop recording and save the session
   */
  stopRecording(): RecordingSession {
    this.isRecording = false;
    this.saveSession();
    console.log(`🛑 Stopped recording. Captured ${this.session.calls.length} API calls.`);
    console.log(`📁 Recording saved to: ${this.outputFile}`);
    return this.session;
  }

  /**
   * Save the current session to disk
   */
  private saveSession(): void {
    fs.writeFileSync(
      this.outputFile,
      JSON.stringify(this.session, null, 2),
      'utf-8'
    );
  }

  /**
   * Get all recorded calls
   */
  getCalls(): ApiFixture[] {
    return this.session.calls;
  }

  /**
   * Get the output file path
   */
  getOutputFile(): string {
    return this.outputFile;
  }
}

/**
 * Helper to check if we should record fixtures
 */
export function shouldRecordFixtures(): boolean {
  return process.env.RECORD_FIXTURES === 'true';
}

/**
 * Create a recorder if in recording mode, otherwise return null
 */
export function createRecorderIfNeeded(testFile?: string): ApiRecorder | null {
  if (shouldRecordFixtures()) {
    return new ApiRecorder(testFile);
  }
  return null;
}
