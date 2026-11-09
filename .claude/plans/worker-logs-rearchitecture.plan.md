# Plan: Worker Logs Rearchitecture

**Created:** 2026-01-04
**Branch:** `feat/sess-20260104-1931-logs-research`
**Status:** Implementation Complete - Pending PR Merge & Deployment

## Overview

Move `worker_logs` from embedded array in job documents to a Firestore subcollection to avoid the 1MB document size limit. The current approach caused job 501258e1 to fail when logs reached 1.26 MB (98.6% of document size).

## Problem Statement

- Firestore documents have a 1 MB size limit
- `worker_logs` is stored as an array field within job documents
- Long-running jobs (especially video encoding) can generate thousands of log entries
- When the limit is exceeded, job updates fail with: `Document cannot be written because its size exceeds the maximum allowed size`

## Requirements

- [x] Logs must remain associated with their job
- [x] Logs should be queryable by job_id, worker type, timestamp
- [x] Old logs should auto-cleanup (TTL: 30 days)
- [x] Existing API endpoint (`GET /api/jobs/{id}/logs`) must continue to work
- [x] Frontend must continue to display logs without changes
- [x] Migration path for existing jobs (optional - can just start fresh)

## Technical Approach

### Option A: Subcollection (Recommended)
Store logs in `jobs/{job_id}/logs/{log_id}` subcollection.

**Pros:**
- Natural association with job (delete job = delete logs with cascading)
- Each log entry is its own document (no size limit concerns)
- Can add TTL via Firestore TTL policies
- Efficient queries with composite indexes

**Cons:**
- More Firestore read operations for paginated log fetching
- Slightly more complex write logic

### Option B: Separate Collection
Store logs in `job_logs` collection with `job_id` field.

**Pros:**
- Can query across all jobs
- Simpler TTL management

**Cons:**
- Orphaned logs if job deleted (need cleanup logic)
- Extra index needed for job_id queries

### Decision: Option A (Subcollection)

## Implementation Steps

### Phase 1: Backend Changes

1. [x] **Create log entry model** - `backend/models/worker_log.py`
   - `WorkerLogEntry` dataclass with: id, job_id, timestamp, level, worker, message, metadata, ttl_expiry
   - Factory method `create()` for easy instantiation
   - `to_dict()` for Firestore storage
   - `to_legacy_dict()` for API compatibility
   - `from_dict()` for Firestore retrieval

2. [x] **Update FirestoreService** - `backend/services/firestore_service.py`
   - Added `append_log_to_subcollection(job_id, log_entry)` method
   - Added `get_logs_from_subcollection(job_id, limit, since_timestamp, worker, offset)` method
   - Added `get_logs_count_from_subcollection(job_id)` method
   - Added `delete_logs_subcollection(job_id, batch_size)` method
   - Old `append_worker_log` marked as deprecated

3. [x] **Update JobManager** - `backend/services/job_manager.py`
   - Modified `append_worker_log()` to use subcollection when `USE_LOG_SUBCOLLECTION=true`
   - Modified `get_worker_logs()` to read from subcollection with fallback to embedded array
   - Added `get_worker_logs_count()` for total count
   - Updated `delete_job()` to clean up logs subcollection

4. [x] **Update jobs API** - `backend/api/routes/jobs.py`
   - `GET /api/jobs/{id}/logs` - Updated to use new methods
   - Response format stays the same (backward compatible)
   - Fixed `next_index` calculation

5. [x] **Add feature flag** - `backend/config.py`
   - Added `USE_LOG_SUBCOLLECTION` environment variable (default: true)

6. [x] **Add TTL configuration** - `infrastructure/__main__.py`
   - Added Firestore TTL policy for logs subcollection (30 days)
   - Added composite index for worker + timestamp queries

### Phase 2: Testing

7. [x] **Unit tests** - `backend/tests/test_worker_log_subcollection.py`
   - 24 tests covering:
     - WorkerLogEntry model creation and conversion
     - FirestoreService subcollection methods
     - JobManager logging with feature flag
     - Edge cases (unicode, long messages, empty messages)

8. [x] **Integration tests** - `backend/tests/emulator/test_worker_logs_subcollection.py`
   - 11 tests using real Firestore emulator:
     - Single and sequential writes
     - TTL field verification
     - Concurrent writes (no race conditions)
     - Large volume (500 logs)
     - Worker filtering
     - Timestamp ordering
     - Subcollection deletion
     - Concurrent workers interleaved
     - Job deletion cleanup
     - Comparison with embedded array

### Phase 3: Deployment & Migration

9. [ ] **Deploy with feature flag**
   - Add `USE_LOG_SUBCOLLECTION=true` env var (default is true)
   - Deploy to production

10. [ ] **Monitor**
    - Watch for errors in Cloud Logging
    - Verify logs appear in frontend

11. [x] **Backward compatibility**
    - Old jobs with embedded arrays still work (fallback in get_worker_logs)
    - No migration needed - new jobs use subcollection, old jobs use array

### Phase 4: Cleanup (Future)

12. [ ] **Remove old code path** (after confidence period)
    - Remove `worker_logs` field from job model
    - Remove old `append_worker_log` method
    - Remove feature flag

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `backend/models/worker_log.py` | Created | WorkerLogEntry dataclass |
| `backend/services/firestore_service.py` | Modified | Added subcollection methods |
| `backend/services/job_manager.py` | Modified | Switch to subcollection with fallback |
| `backend/api/routes/jobs.py` | Modified | Updated logs endpoint |
| `backend/config.py` | Modified | Added USE_LOG_SUBCOLLECTION setting |
| `backend/tests/test_worker_log_subcollection.py` | Created | Unit tests (24 tests) |
| `backend/tests/emulator/test_worker_logs_subcollection.py` | Created | Integration tests (11 tests) |
| `infrastructure/__main__.py` | Modified | Added TTL policy and index |

## Log Entry Schema

```python
@dataclass
class WorkerLogEntry:
    timestamp: datetime
    level: str  # "DEBUG", "INFO", "WARNING", "ERROR"
    worker: str  # "audio", "lyrics", "video", "render", "screens", "distribution"
    message: str
    id: str  # Auto-generated UUID
    job_id: str
    ttl_expiry: datetime  # timestamp + 30 days
    metadata: Optional[Dict[str, Any]] = None
```

## Firestore Structure

```
jobs/
  {job_id}/
    ... (job fields, worker_logs still present for old jobs)
    logs/  # subcollection for new jobs
      {log_id}/
        id: string
        job_id: string
        timestamp: datetime
        level: string
        worker: string
        message: string
        metadata: map (optional)
        ttl_expiry: datetime
```

## API Response (Unchanged)

```json
{
  "logs": [
    {
      "timestamp": "2026-01-04T12:00:00Z",
      "level": "INFO",
      "worker": "video",
      "message": "Starting video generation"
    }
  ],
  "next_index": 42,
  "total_logs": 150
}
```

## Testing Results

All tests pass:
- 24 unit tests in `test_worker_log_subcollection.py`
- 11 emulator integration tests in `test_worker_logs_subcollection.py`
- 68 total tests in emulator suite pass

## Rollback Plan

1. Set `USE_LOG_SUBCOLLECTION=false` env var
2. Redeploy backend
3. New logs will go back to embedded array
4. Subcollection logs will remain but won't be read

## Answers to Open Questions

- [x] **Should we paginate logs in the API?** - Yes, added `offset` parameter support
- [x] **What's the optimal TTL period?** - 30 days (configurable via DEFAULT_LOG_TTL_DAYS)
- [x] **Should we index by timestamp for efficient range queries?** - Yes, added composite index (worker + timestamp)

## References

- [Firestore TTL](https://cloud.google.com/firestore/docs/ttl)
- [Firestore Subcollections](https://firebase.google.com/docs/firestore/data-model#subcollections)
- [Firestore Limits](https://firebase.google.com/docs/firestore/quotas#limits)
- [Pulumi Firestore Field](https://www.pulumi.com/registry/packages/gcp/api-docs/firestore/field/)
