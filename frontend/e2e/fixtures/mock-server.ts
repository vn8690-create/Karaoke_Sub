/**
 * API Fixture Mock Server
 *
 * Uses Playwright route interception to replay recorded API fixtures.
 * This provides deterministic test behavior without needing a real backend.
 */

import { Page, Route, Request } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { ApiFixture, FixtureSet } from './types';

const FIXTURES_DIR = path.join(__dirname, 'data');
// In E2E tests, API calls go through Next.js rewrites to /api/* on the same origin
// So we need to match **/api/** to intercept regardless of host
const API_PATH_PATTERN = '**/api/**';

/**
 * Match a request URL path to a fixture pattern
 * Supports simple wildcards like /api/v1/jobs/* matching /api/v1/jobs/123
 */
function matchPath(pattern: string, actualPath: string): boolean {
  // Exact match
  if (pattern === actualPath) return true;

  // Wildcard match: /api/v1/jobs/* matches /api/v1/jobs/anything
  if (pattern.endsWith('/*')) {
    const prefix = pattern.slice(0, -2);
    return actualPath.startsWith(prefix) && actualPath.split('/').length === pattern.split('/').length;
  }

  // Pattern with :param placeholders
  const patternParts = pattern.split('/');
  const actualParts = actualPath.split('/');

  if (patternParts.length !== actualParts.length) return false;

  return patternParts.every((part, i) => {
    if (part.startsWith(':')) return true; // Matches any value
    return part === actualParts[i];
  });
}

/**
 * Load a fixture set from disk
 */
export function loadFixtureSet(name: string): FixtureSet | null {
  const filePath = path.join(FIXTURES_DIR, 'sets', `${name}.json`);
  if (!fs.existsSync(filePath)) {
    console.warn(`Fixture set not found: ${filePath}`);
    return null;
  }
  const content = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(content) as FixtureSet;
}

/**
 * Load all approved fixtures from the approved directory
 */
export function loadApprovedFixtures(): Record<string, ApiFixture> {
  const approvedDir = path.join(FIXTURES_DIR, 'approved');
  const fixtures: Record<string, ApiFixture> = {};

  if (!fs.existsSync(approvedDir)) {
    console.warn(`Approved fixtures directory not found: ${approvedDir}`);
    return fixtures;
  }

  const files = fs.readdirSync(approvedDir).filter(f => f.endsWith('.json'));
  for (const file of files) {
    const content = fs.readFileSync(path.join(approvedDir, file), 'utf-8');
    const fixture = JSON.parse(content) as ApiFixture;
    // Key by method + path for lookup
    const key = `${fixture.request.method}:${fixture.request.path}`;
    fixtures[key] = fixture;
  }

  return fixtures;
}

/**
 * API Mock Server class for replaying fixtures in tests
 */
export class ApiMockServer {
  private fixtures: Record<string, ApiFixture> = {};
  private fixtureSet: FixtureSet | null = null;
  private unmatchedRequests: Array<{ method: string; url: string }> = [];

  /**
   * Load fixtures from a named fixture set
   */
  loadFixtureSet(name: string): this {
    this.fixtureSet = loadFixtureSet(name);
    if (this.fixtureSet) {
      for (const [pattern, fixture] of Object.entries(this.fixtureSet.fixtures)) {
        this.fixtures[pattern] = fixture;
      }
      console.log(`📦 Loaded fixture set: ${name} (${Object.keys(this.fixtureSet.fixtures).length} fixtures)`);
    }
    return this;
  }

  /**
   * Load all approved fixtures
   */
  loadApprovedFixtures(): this {
    const approved = loadApprovedFixtures();
    for (const [key, fixture] of Object.entries(approved)) {
      this.fixtures[key] = fixture;
    }
    console.log(`✅ Loaded ${Object.keys(approved).length} approved fixtures`);
    return this;
  }

  /**
   * Add a single fixture manually
   */
  addFixture(fixture: ApiFixture): this {
    const key = `${fixture.request.method}:${fixture.request.path}`;
    this.fixtures[key] = fixture;
    return this;
  }

  /**
   * Add an inline fixture for a specific route
   */
  mockRoute(
    method: string,
    path: string,
    response: { status?: number; body: any }
  ): this {
    const fixture: ApiFixture = {
      id: `inline-${method}-${path.replace(/\//g, '-')}`,
      description: `Inline mock for ${method} ${path}`,
      capturedAt: new Date().toISOString(),
      request: { method, url: path, path },
      response: {
        status: response.status || 200,
        statusText: response.status === 200 ? 'OK' : 'Error',
        body: response.body,
      },
      reviewed: true,
    };
    this.addFixture(fixture);
    return this;
  }

  /**
   * Install the mock server on a Playwright page
   */
  async install(page: Page): Promise<void> {
    await page.route(API_PATH_PATTERN, async (route: Route, request: Request) => {
      const url = request.url();
      const method = request.method();
      const urlObj = new URL(url);
      const urlPath = urlObj.pathname;

      // Try exact match first
      let fixture = this.fixtures[`${method}:${urlPath}`];

      // Then try pattern matching
      if (!fixture) {
        for (const [pattern, f] of Object.entries(this.fixtures)) {
          const [fMethod, fPath] = pattern.includes(':')
            ? pattern.split(':')
            : [f.request.method, pattern];

          if (fMethod === method && matchPath(fPath, urlPath)) {
            fixture = f;
            break;
          }
        }
      }

      if (fixture) {
        console.log(`🎭 [MOCK] ${method} ${urlPath} -> ${fixture.response.status}`);
        await route.fulfill({
          status: fixture.response.status,
          contentType: 'application/json',
          body: JSON.stringify(fixture.response.body),
        });
      } else {
        console.warn(`⚠️ [MOCK] No fixture for ${method} ${urlPath}`);
        this.unmatchedRequests.push({ method, url });

        // Return a clear error response
        await route.fulfill({
          status: 501,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'No fixture available',
            message: `No mock fixture found for ${method} ${urlPath}`,
            hint: 'Run tests with RECORD_FIXTURES=true to capture this endpoint',
          }),
        });
      }
    });

    console.log(`🎭 Mock server installed with ${Object.keys(this.fixtures).length} fixtures`);
  }

  /**
   * Get list of requests that had no matching fixture
   */
  getUnmatchedRequests(): Array<{ method: string; url: string }> {
    return this.unmatchedRequests;
  }

  /**
   * Check if all requests were handled
   */
  allRequestsHandled(): boolean {
    return this.unmatchedRequests.length === 0;
  }
}

/**
 * Create a mock server with common test fixtures pre-loaded
 */
export function createMockServer(): ApiMockServer {
  return new ApiMockServer();
}

/**
 * Quick helper to mock common auth scenarios
 */
export function createAuthenticatedMock(): ApiMockServer {
  return new ApiMockServer()
    .mockRoute('GET', '/api/v1/me', {
      body: { authenticated: true, user: { id: 'test-user' } },
    })
    .mockRoute('GET', '/api/v1/jobs', {
      body: [],
    });
}

/**
 * Quick helper for unauthenticated scenario
 */
export function createUnauthenticatedMock(): ApiMockServer {
  return new ApiMockServer()
    .mockRoute('GET', '/api/v1/me', {
      status: 401,
      body: { detail: 'Not authenticated' },
    });
}
