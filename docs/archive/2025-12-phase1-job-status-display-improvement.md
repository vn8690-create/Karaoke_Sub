# Job Status Display Improvement Plan

**Status:** Planned
**Created:** 2025-12-27
**Priority:** HIGH - User experience improvement

## Problem Statement

Users see generic status messages like "Downloading..." that persist for too long, even after the download is complete and other processing stages are happening. This makes it hard to understand:
1. What stage the job is actually at
2. How much progress has been made
3. How much longer the job might take

## Current Implementation

### Backend Status System
The backend has 28 distinct job statuses organized into 8 processing stages:

```
Stage 1: Setup (PENDING)
Stage 2: Audio Search (SEARCHING_AUDIO, AWAITING_AUDIO_SELECTION, DOWNLOADING_AUDIO)
Stage 3: Download (DOWNLOADING)
Stage 4: Parallel Processing
  - Audio: SEPARATING_STAGE1 → SEPARATING_STAGE2 → AUDIO_COMPLETE
  - Lyrics: TRANSCRIBING → CORRECTING → LYRICS_COMPLETE
Stage 5: Screen Generation (GENERATING_SCREENS, APPLYING_PADDING)
Stage 6: Lyrics Review (AWAITING_REVIEW, IN_REVIEW, REVIEW_COMPLETE) ⚠️ BLOCKING
Stage 7: Video Rendering (RENDERING_VIDEO)
Stage 8: Instrumental Selection (AWAITING_INSTRUMENTAL_SELECTION) ⚠️ BLOCKING
Stage 9: Final Processing (INSTRUMENTAL_SELECTED, GENERATING_VIDEO, ENCODING, PACKAGING)
Stage 10: Distribution (UPLOADING, NOTIFYING, COMPLETE)
```

### Key Findings

1. **Progress field exists but unused**: The `Job` model has a `progress: number` field (0-100) that's returned by the API but NOT displayed in the frontend
2. **Parallel processing complicates status**: Audio and lyrics workers run in parallel, updating `state_data.audio_progress` and `state_data.lyrics_progress` independently
3. **Status labels are static**: Frontend shows "Downloading..." but doesn't reflect that parallel workers are running
4. **10-second polling**: Frontend polls every 10 seconds, so status updates are not real-time

## Proposed Solution

### 1. Step-Based Progress Display

Show a `[X/10] Status...` format that gives users a clear sense of overall progress:

```
[1/10] Setting up...
[2/10] Searching for audio...
[3/10] Downloading audio...
[4/10] Processing audio & lyrics...  ← Parallel stage
[5/10] Generating screens...
[6/10] Needs review  ← Blocking
[7/10] Rendering video...
[8/10] Select instrumental  ← Blocking
[9/10] Encoding final video...
[10/10] Uploading...
```

### 2. Status-to-Step Mapping

```typescript
const STATUS_STEP_MAP: Record<string, { step: number; total: number; label: string }> = {
  // Step 1: Setup
  pending: { step: 1, total: 10, label: "Setting up" },

  // Step 2: Audio Search (optional)
  searching_audio: { step: 2, total: 10, label: "Searching for audio" },
  awaiting_audio_selection: { step: 2, total: 10, label: "Select audio source" },

  // Step 3: Download
  downloading_audio: { step: 3, total: 10, label: "Downloading audio" },
  downloading: { step: 3, total: 10, label: "Downloading" },

  // Step 4: Parallel Processing (Audio + Lyrics)
  separating_stage1: { step: 4, total: 10, label: "Separating audio (1/2)" },
  separating_stage2: { step: 4, total: 10, label: "Separating audio (2/2)" },
  audio_complete: { step: 4, total: 10, label: "Audio ready" },
  transcribing: { step: 4, total: 10, label: "Transcribing lyrics" },
  correcting: { step: 4, total: 10, label: "Correcting lyrics" },
  lyrics_complete: { step: 4, total: 10, label: "Lyrics ready" },

  // Step 5: Screen Generation
  generating_screens: { step: 5, total: 10, label: "Generating screens" },
  applying_padding: { step: 5, total: 10, label: "Syncing countdown" },

  // Step 6: Review (BLOCKING)
  awaiting_review: { step: 6, total: 10, label: "Needs review" },
  in_review: { step: 6, total: 10, label: "In review" },

  // Step 7: Video Rendering
  review_complete: { step: 7, total: 10, label: "Review complete" },
  rendering_video: { step: 7, total: 10, label: "Rendering video" },

  // Step 8: Instrumental Selection (BLOCKING)
  awaiting_instrumental_selection: { step: 8, total: 10, label: "Select instrumental" },

  // Step 9: Final Encoding
  instrumental_selected: { step: 9, total: 10, label: "Instrumental selected" },
  generating_video: { step: 9, total: 10, label: "Generating final video" },
  encoding: { step: 9, total: 10, label: "Encoding video" },
  packaging: { step: 9, total: 10, label: "Packaging files" },

  // Step 10: Distribution
  uploading: { step: 10, total: 10, label: "Uploading" },
  notifying: { step: 10, total: 10, label: "Sending notifications" },
  complete: { step: 10, total: 10, label: "Complete" },

  // Terminal states
  failed: { step: 0, total: 10, label: "Failed" },
  cancelled: { step: 0, total: 10, label: "Cancelled" },
  prep_complete: { step: 10, total: 10, label: "Prep complete" },
};
```

### 3. Enhanced Parallel Processing Display

When audio and lyrics are processing in parallel, show both activities:

```typescript
// Check state_data for parallel progress
if (job.state_data?.audio_progress && job.state_data?.lyrics_progress) {
  const audioStatus = job.state_data.audio_progress.stage;
  const lyricsStatus = job.state_data.lyrics_progress.stage;

  // Show combined status like "Audio: separating, Lyrics: transcribing"
  if (audioStatus !== 'audio_complete' || lyricsStatus !== 'lyrics_complete') {
    return {
      step: 4,
      total: 10,
      label: buildParallelLabel(audioStatus, lyricsStatus)
    };
  }
}
```

### 4. Visual Progress Bar (Optional Enhancement)

Add a thin progress bar below the status text:

```tsx
<div className="w-full h-1 bg-slate-700 rounded mt-1">
  <div
    className="h-full bg-blue-500 rounded transition-all"
    style={{ width: `${(step / total) * 100}%` }}
  />
</div>
```

## Implementation Steps

### Phase 1: Core Changes (MVP)

1. **Create status utility** (`frontend/lib/job-status.ts`):
   - Define `STATUS_STEP_MAP` constant
   - Create `getJobStep(job: Job)` function
   - Create `formatStepStatus(step, total, label)` function

2. **Update JobCard component**:
   - Import status utility
   - Replace static `StatusText` with step-based format
   - Keep existing color coding from `statusConfig`

3. **Add unit tests** (`frontend/__tests__/job-status.test.ts`):
   - Test all status mappings
   - Test parallel processing detection
   - Test edge cases (unknown status, null values)

### Phase 2: Enhanced Parallel Processing (Optional)

1. **Add parallel progress detection**:
   - Check `state_data.audio_progress` and `state_data.lyrics_progress`
   - Build combined label showing both activities

2. **Add visual progress bar**:
   - Thin progress indicator based on step number
   - Smooth transitions between steps

### Phase 3: Backend Improvements (Future)

1. **Add estimated time remaining**:
   - Track average duration per stage from historical data
   - Return ETA in API response

2. **WebSocket for real-time updates**:
   - Replace polling with push notifications
   - Smoother progress updates during long operations

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/lib/job-status.ts` | NEW: Status utility functions |
| `frontend/components/job/JobCard.tsx` | Update status display |
| `frontend/__tests__/job-status.test.ts` | NEW: Unit tests |
| `frontend/lib/api.ts` | Add `state_data` types (if needed) |

## Testing Plan

1. **Unit tests**:
   - All status mappings return correct step/label
   - Unknown statuses handled gracefully
   - Parallel progress detection works

2. **Integration tests** (E2E):
   - Verify status displays correctly at each stage
   - Verify step numbers increment as job progresses

3. **Manual testing**:
   - Submit a job and observe status progression
   - Verify parallel processing shows meaningful status

## Success Criteria

- [ ] All statuses show `[X/10] Label` format
- [ ] Step numbers progress logically (never decrease except on retry)
- [ ] Parallel processing shows combined activity
- [ ] Blocking statuses clearly indicated for user action
- [ ] All existing tests pass
- [ ] New unit tests have >80% coverage

## Rollback Plan

The changes are frontend-only and purely cosmetic. If issues arise:
1. Revert the JobCard changes to use the old `statusConfig` approach
2. The backend API remains unchanged

## Notes

- The 10-step system is a simplification of the 28 backend statuses for user comprehension
- Parallel processing (step 4) groups multiple backend statuses into one user-facing step
- Blocking steps (6, 8) require user action and should be visually distinct
- The `progress` field from backend could be used for sub-step progress bars in the future
