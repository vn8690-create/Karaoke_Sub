/**
 * Test Cleanup Helpers for E2E Testing
 *
 * Provides utilities for cleaning up test data created during E2E tests.
 * Uses admin API endpoints to delete jobs and other test artifacts.
 *
 * Usage:
 *   const createdJobIds: string[] = [];
 *   // ... create jobs during test ...
 *   test.afterEach(async () => {
 *     for (const jobId of createdJobIds) {
 *       await deleteTestJob(jobId, adminToken);
 *     }
 *   });
 */

import { URLS } from './constants';

/**
 * Delete a test job by ID.
 *
 * Uses the admin API to delete the job and optionally clean up
 * associated distribution (YouTube, Dropbox, GDrive).
 *
 * @param jobId - Job ID to delete
 * @param adminToken - Admin token for authentication
 * @param options - Cleanup options
 * @param apiUrl - API URL (defaults to production)
 */
export async function deleteTestJob(
  jobId: string,
  adminToken: string,
  options: {
    cleanupDistribution?: boolean;
  } = {},
  apiUrl: string = URLS.production.api
): Promise<{ deleted: boolean; message: string }> {
  const { cleanupDistribution = true } = options;

  // If cleanup distribution is requested, use the cleanup-distribution endpoint
  if (cleanupDistribution) {
    const response = await fetch(`${apiUrl}/api/jobs/${jobId}/cleanup-distribution`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${adminToken}`,
      },
      body: JSON.stringify({ delete_job: true }),
    });

    if (response.ok) {
      const data = await response.json();
      return {
        deleted: data.job_deleted === true,
        message: `Job ${jobId} deleted with distribution cleanup`,
      };
    }

    // If cleanup-distribution failed, try direct delete
    if (response.status === 404) {
      return { deleted: false, message: `Job ${jobId} not found` };
    }
  }

  // Fall back to direct job delete via admin endpoint
  const response = await fetch(`${apiUrl}/api/admin/jobs/${jobId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${adminToken}`,
    },
  });

  if (response.ok) {
    return { deleted: true, message: `Job ${jobId} deleted` };
  }

  if (response.status === 404) {
    return { deleted: false, message: `Job ${jobId} not found` };
  }

  const errorText = await response.text();
  throw new Error(`Failed to delete job ${jobId}: ${response.status} ${errorText}`);
}

/**
 * Clean up stale E2E test jobs.
 *
 * Finds and deletes jobs with IDs starting with "e2e-test-" that are older
 * than the specified age. This is useful for periodic maintenance.
 *
 * @param adminToken - Admin token for authentication
 * @param maxAgeMinutes - Maximum age in minutes (default: 60)
 * @param apiUrl - API URL (defaults to production)
 * @returns Number of jobs cleaned up
 */
export async function cleanupStaleTestJobs(
  adminToken: string,
  maxAgeMinutes: number = 60,
  apiUrl: string = URLS.production.api
): Promise<number> {
  // Fetch jobs list from admin API
  const response = await fetch(`${apiUrl}/api/admin/jobs?limit=100`, {
    headers: {
      'Authorization': `Bearer ${adminToken}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch jobs: ${response.status}`);
  }

  const data = await response.json();
  const jobs = data.jobs || [];

  const now = Date.now();
  const maxAgeMs = maxAgeMinutes * 60 * 1000;
  let cleanedCount = 0;

  for (const job of jobs) {
    // Check if this is a test job (customer_email contains test patterns or job created via test-webhook)
    const isTestJob =
      job.customer_email?.includes('@inbox.testmail.app') ||
      job.job_id?.startsWith('e2e-test-');

    if (!isTestJob) continue;

    // Check age
    const createdAt = new Date(job.created_at).getTime();
    const age = now - createdAt;

    if (age > maxAgeMs) {
      console.log(`Cleaning up stale test job: ${job.job_id} (age: ${Math.round(age / 60000)}m)`);
      try {
        await deleteTestJob(job.job_id, adminToken, {}, apiUrl);
        cleanedCount++;
      } catch (e) {
        console.warn(`Failed to clean up job ${job.job_id}: ${e}`);
      }
    }
  }

  return cleanedCount;
}

/**
 * Create a cleanup tracker for use in test suites.
 *
 * Provides methods to track created resources and clean them up after tests.
 *
 * Usage:
 *   const cleanup = createCleanupTracker(adminToken);
 *   // ... create job ...
 *   cleanup.trackJob(jobId);
 *   // After test:
 *   await cleanup.cleanupAll();
 */
export function createCleanupTracker(adminToken: string, apiUrl: string = URLS.production.api) {
  const jobIds: string[] = [];

  return {
    /**
     * Track a job for cleanup.
     */
    trackJob(jobId: string) {
      if (jobId && !jobIds.includes(jobId)) {
        jobIds.push(jobId);
      }
    },

    /**
     * Get all tracked job IDs.
     */
    getTrackedJobs(): string[] {
      return [...jobIds];
    },

    /**
     * Clean up all tracked resources.
     */
    async cleanupAll(): Promise<{ deleted: number; failed: number }> {
      let deleted = 0;
      let failed = 0;

      for (const jobId of jobIds) {
        try {
          const result = await deleteTestJob(jobId, adminToken, {}, apiUrl);
          if (result.deleted) {
            deleted++;
            console.log(`  Cleaned up test job: ${jobId}`);
          } else {
            console.log(`  Job not found (may already be deleted): ${jobId}`);
          }
        } catch (e) {
          failed++;
          console.warn(`  Failed to clean up job ${jobId}: ${e}`);
        }
      }

      // Clear the tracked list
      jobIds.length = 0;

      return { deleted, failed };
    },
  };
}
