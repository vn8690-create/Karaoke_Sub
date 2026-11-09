#!/usr/bin/env node
/**
 * Fixture Review Tool — Quick Reference
 *
 * Opens each search result fixture in the guided flow UI so you can
 * manually verify how each tier looks and behaves.
 *
 * Usage:
 *   cd frontend
 *   npm run fixtures:review-ui
 *
 * Filters (env vars):
 *   FIXTURE_START=10                     Start from fixture 10
 *   FIXTURE_SLUG=bon-jovi-it-s-my-life   Review only this fixture
 *   FIXTURE_TIER=3                       Only review tier 3 fixtures
 *
 * Example:
 *   FIXTURE_TIER=1 npm run fixtures:review-ui    # Review only Tier 1
 *   FIXTURE_START=20 npm run fixtures:review-ui   # Start from fixture 20
 *
 * In the Playwright Inspector, click ▶ Resume to advance to the next fixture.
 */

console.log('Fixture Review — Interactive Tier Verification');
console.log('');
console.log('Usage:');
console.log('  cd frontend');
console.log('  npm run fixtures:review-ui');
console.log('');
console.log('Filters (pass as env vars):');
console.log('  FIXTURE_START=N   Start from fixture N (1-indexed)');
console.log('  FIXTURE_SLUG=x    Review only the fixture with this slug');
console.log('  FIXTURE_TIER=N    Only review fixtures classified as tier N (1, 2, or 3)');
console.log('');
console.log('Examples:');
console.log('  FIXTURE_TIER=1 npm run fixtures:review-ui');
console.log('  FIXTURE_SLUG=bon-jovi-it-s-my-life npm run fixtures:review-ui');
