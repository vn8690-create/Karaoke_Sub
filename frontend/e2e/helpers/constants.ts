/**
 * Shared constants for E2E tests
 */

/**
 * Test song - uses cached flacfetch results for speed and cost savings.
 * "piri - dog" is the designated test song that has cached results in production.
 */
export const TEST_SONG = {
  artist: 'piri',
  title: 'dog',
} as const;

/**
 * URLs for different environments
 */
export const URLS = {
  production: {
    frontend: 'https://gen.nomadkaraoke.com',
    api: 'https://api.nomadkaraoke.com',
  },
  local: {
    frontend: 'http://localhost:3000',
    api: 'http://localhost:8000',
  },
} as const;

/**
 * Timeout values for different operations
 */
export const TIMEOUTS = {
  /** 30s for UI actions like clicks, fills */
  action: 30_000,
  /** 60s for expect assertions */
  expect: 60_000,
  /** 2min for API calls that may take a while */
  apiCall: 120_000,
  /** 10min for job processing (transcription, rendering) */
  jobProcessing: 600_000,
  /** 15min for full test run */
  fullTest: 900_000,
} as const;

/**
 * Common job statuses
 */
export const JOB_STATUS = {
  PENDING: 'pending',
  AUDIO_SEARCH: 'audio_search',
  AWAITING_AUDIO_SELECTION: 'awaiting_audio_selection',
  DOWNLOADING: 'downloading',
  SEPARATING: 'separating',
  TRANSCRIBING: 'transcribing',
  AGENTIC_CORRECTION: 'agentic_correction',
  IN_REVIEW: 'in_review',
  AWAITING_INSTRUMENTAL: 'awaiting_instrumental_selection',
  RENDERING: 'rendering',
  ENCODING: 'encoding',
  DISTRIBUTING: 'distributing',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const;

/**
 * LocalStorage keys
 */
export const STORAGE_KEYS = {
  accessToken: 'karaoke_access_token',
} as const;
