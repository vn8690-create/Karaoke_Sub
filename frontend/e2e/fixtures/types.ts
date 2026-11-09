/**
 * Types for API fixture recording and playback
 */

export interface ApiFixture {
  /** Unique identifier for this fixture */
  id: string;
  /** Human-readable description of what this fixture represents */
  description: string;
  /** When this fixture was captured */
  capturedAt: string;
  /** The request that was made */
  request: {
    method: string;
    url: string;
    /** URL path without query string */
    path: string;
    /** Query parameters */
    query?: Record<string, string>;
    /** Request body (for POST/PUT/PATCH) */
    body?: any;
    /** Relevant headers (auth token redacted) */
    headers?: Record<string, string>;
  };
  /** The response received */
  response: {
    status: number;
    statusText: string;
    headers?: Record<string, string>;
    body: any;
  };
  /** Optional notes from reviewer */
  reviewNotes?: string;
  /** Whether this fixture has been reviewed and approved */
  reviewed: boolean;
}

export interface RecordingSession {
  /** Session identifier */
  sessionId: string;
  /** When recording started */
  startedAt: string;
  /** Test file that generated this recording */
  testFile?: string;
  /** All API calls captured in this session */
  calls: ApiFixture[];
}

export interface FixtureSet {
  /** Name of this fixture set (e.g., "authenticated-user", "empty-jobs") */
  name: string;
  /** Description of the scenario this fixture set represents */
  description: string;
  /** Fixtures in this set, keyed by a route pattern */
  fixtures: Record<string, ApiFixture>;
}
