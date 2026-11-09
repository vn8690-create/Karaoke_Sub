#!/usr/bin/env node
/**
 * Fetch Audio Search Fixtures from Production
 *
 * Queries the production API for the most recently completed karaoke jobs,
 * then re-runs the audio search for each (artist, title) pair and stores
 * the raw search results as JSON fixtures.
 *
 * These fixtures let us iterate on confidence tier logic and UI without
 * needing to hit the backend again after the initial fetch.
 *
 * Usage:
 *   cd frontend
 *
 *   # Fetch 50 fixtures (default)
 *   node e2e/fixtures/fetch-search-fixtures.mjs
 *
 *   # Fetch a specific number
 *   node e2e/fixtures/fetch-search-fixtures.mjs --count 20
 *
 *   # Skip jobs already fetched (resume mode)
 *   node e2e/fixtures/fetch-search-fixtures.mjs --resume
 *
 * Prerequisites:
 *   - Admin token via: gcloud secrets versions access latest --secret=admin-tokens --project=nomadkaraoke
 *   - Or set KARAOKE_ADMIN_TOKEN env var
 *
 * Output: e2e/fixtures/data/search-results/
 *   - index.json (manifest of all fixtures with metadata)
 *   - {artist}--{title}.json (individual search result files)
 */

import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = path.join(__dirname, 'data', 'search-results');
const INDEX_PATH = path.join(OUTPUT_DIR, 'index.json');
const API_URL = 'https://api.nomadkaraoke.com';

// Parse CLI args
const args = process.argv.slice(2);
const countIdx = args.indexOf('--count');
const FETCH_COUNT = countIdx !== -1 ? parseInt(args[countIdx + 1]) : 50;
const RESUME = args.includes('--resume');

function getAdminToken() {
  if (process.env.KARAOKE_ADMIN_TOKEN) {
    return process.env.KARAOKE_ADMIN_TOKEN;
  }
  try {
    const token = execSync(
      'gcloud secrets versions access latest --secret=admin-tokens --project=nomadkaraoke',
      { encoding: 'utf-8' }
    ).trim().split(',')[0];
    return token;
  } catch {
    console.error('Could not get admin token. Set KARAOKE_ADMIN_TOKEN or configure gcloud.');
    process.exit(1);
  }
}

function slugify(artist, title) {
  const slug = `${artist}--${title}`
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 100);
  return slug;
}

/**
 * Fetch recently completed jobs from the admin API.
 * Uses the /api/admin/jobs endpoint with status filter.
 */
async function fetchRecentJobs(token, count) {
  console.log(`Fetching ${count} most recently completed jobs from API...`);

  const res = await fetch(
    `${API_URL}/api/admin/jobs?status=complete&limit=${count + 20}&sort=created_at:desc`,
    {
      headers: { 'X-Admin-Token': token },
    }
  );

  if (!res.ok) {
    // Fallback: try the regular jobs list endpoint
    console.log(`Admin jobs endpoint returned ${res.status}, trying regular endpoint...`);
    const fallbackRes = await fetch(`${API_URL}/api/jobs?limit=${count + 20}`, {
      headers: { 'X-Admin-Token': token },
    });

    if (!fallbackRes.ok) {
      throw new Error(`Failed to fetch jobs: ${fallbackRes.status} ${await fallbackRes.text()}`);
    }

    const jobs = await fallbackRes.json();
    return processJobs(Array.isArray(jobs) ? jobs : jobs.jobs || [], count);
  }

  const data = await res.json();
  const jobs = Array.isArray(data) ? data : data.jobs || [];
  return processJobs(jobs, count);
}

function processJobs(jobs, count) {
  const seen = new Set();
  const results = [];

  // Filter to completed jobs and deduplicate by artist+title
  for (const job of jobs) {
    if (job.status && job.status !== 'complete') continue;

    const artist = job.artist?.trim();
    const title = job.title?.trim();
    if (!artist || !title) continue;

    const key = `${artist.toLowerCase()}|${title.toLowerCase()}`;
    if (seen.has(key)) continue;
    seen.add(key);

    results.push({
      jobId: job.job_id,
      artist,
      title,
      createdAt: job.created_at,
    });

    if (results.length >= count) break;
  }

  console.log(`Found ${results.length} unique (artist, title) pairs`);
  return results;
}

async function searchAudio(token, artist, title) {
  // Step 1: Initiate search
  const searchRes = await fetch(`${API_URL}/api/audio-search/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Token': token,
    },
    body: JSON.stringify({
      artist,
      title,
      auto_download: false,
    }),
  });

  if (!searchRes.ok) {
    const text = await searchRes.text();
    throw new Error(`Search failed (${searchRes.status}): ${text}`);
  }

  const searchData = await searchRes.json();
  const jobId = searchData.job_id;

  // If results are already in the response
  if (searchData.results && searchData.results.length > 0) {
    return { jobId, results: searchData.results, status: searchData.status };
  }

  // Step 2: Poll for results
  const maxAttempts = 30;
  const interval = 2000;

  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(resolve => setTimeout(resolve, interval));

    const resultsRes = await fetch(`${API_URL}/api/audio-search/${jobId}/results`, {
      headers: { 'X-Admin-Token': token },
    });

    if (!resultsRes.ok) continue;

    const resultsData = await resultsRes.json();
    if (resultsData.results && resultsData.results.length > 0) {
      return { jobId, results: resultsData.results, status: resultsData.status };
    }

    if (resultsData.status === 'search_complete' || resultsData.status === 'audio_search_complete') {
      return { jobId, results: [], status: resultsData.status };
    }
  }

  return { jobId, results: [], status: 'timeout' };
}

async function cleanupJob(token, jobId) {
  try {
    await fetch(`${API_URL}/api/jobs/${jobId}`, {
      method: 'DELETE',
      headers: { 'X-Admin-Token': token },
    });
  } catch {
    // Best-effort cleanup
  }
}

async function main() {
  const token = getAdminToken();
  console.log(`Token: ${token.substring(0, 8)}...`);

  // Ensure output directory exists
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  // Load existing index if resuming
  let existingIndex = [];
  if (RESUME && fs.existsSync(INDEX_PATH)) {
    existingIndex = JSON.parse(fs.readFileSync(INDEX_PATH, 'utf-8'));
    console.log(`Resume mode: ${existingIndex.length} fixtures already exist`);
  }
  const existingSlugs = new Set(existingIndex.map(f => f.slug));

  // Fetch recent completed jobs
  const jobs = await fetchRecentJobs(token, FETCH_COUNT + existingSlugs.size);
  const toFetch = jobs.filter(j => !existingSlugs.has(slugify(j.artist, j.title)));

  if (toFetch.length === 0) {
    console.log('All fixtures already exist. Nothing to fetch.');
    return;
  }

  const limit = Math.min(toFetch.length, FETCH_COUNT - existingIndex.length);
  console.log(`\nWill fetch search results for ${limit} jobs...\n`);
  console.log(`Estimated time: ~${Math.ceil(limit * 0.7)} minutes (10s between each + search time)\n`);

  const results = [...existingIndex];
  let successCount = 0;
  let failCount = 0;

  for (let i = 0; i < limit; i++) {
    const job = toFetch[i];
    const slug = slugify(job.artist, job.title);
    const outPath = path.join(OUTPUT_DIR, `${slug}.json`);

    process.stdout.write(`[${i + 1}/${limit}] ${job.artist} - ${job.title}... `);

    try {
      const searchResult = await searchAudio(token, job.artist, job.title);

      const fixture = {
        artist: job.artist,
        title: job.title,
        originalJobId: job.jobId,
        createdAt: job.createdAt,
        fetchedAt: new Date().toISOString(),
        searchJobId: searchResult.jobId,
        status: searchResult.status,
        resultCount: searchResult.results.length,
        results: searchResult.results,
      };

      fs.writeFileSync(outPath, JSON.stringify(fixture, null, 2));

      results.push({
        slug,
        artist: job.artist,
        title: job.title,
        resultCount: searchResult.results.length,
        status: searchResult.status,
        file: `${slug}.json`,
      });

      console.log(`${searchResult.results.length} results`);
      successCount++;

      // Clean up the search job (don't leave stale jobs)
      await cleanupJob(token, searchResult.jobId);
    } catch (err) {
      console.log(`FAILED: ${err.message}`);
      failCount++;
    }

    // Write index after each successful fetch (so --resume works if interrupted)
    fs.writeFileSync(INDEX_PATH, JSON.stringify(results, null, 2));

    // 10s delay between searches to avoid rate limits
    if (i < limit - 1) {
      process.stdout.write('  Waiting 10s before next search...');
      await new Promise(resolve => setTimeout(resolve, 10000));
      console.log(' done');
    }
  }

  console.log(`\n=== Done ===`);
  console.log(`Success: ${successCount}`);
  console.log(`Failed: ${failCount}`);
  console.log(`Total fixtures: ${results.length}`);
  console.log(`Output: ${OUTPUT_DIR}`);
  console.log(`Index: ${INDEX_PATH}`);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
