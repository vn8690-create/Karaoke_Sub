# Phase 1: Job Creation UX Overhaul - Implementation Record

Date: 2026-02-28

## What Was Done

### Increment 1: Quick Wins
- Removed "Skip lyrics review (non-interactive)" checkbox from all 3 tabs in `JobSubmission.tsx`
- Renamed "Private (non-published)" to "Private (no YouTube upload)" across all 3 tabs
- Removed `nonInteractive` state variable and `non_interactive` from all submit handler payloads
- Backend `non_interactive` field preserved for CLI/admin API use

### Increment 2: Guided Step Flow
Replaced the tab-based `JobSubmission` with a new `GuidedJobFlow` wizard component.

#### New Files Created
| File | Purpose |
|------|---------|
| `lib/audio-search-utils.ts` | Extracted categorization logic shared between AudioSearchDialog and new flow |
| `components/job/GuidedJobFlow.tsx` | Main orchestrator with step state management |
| `components/job/steps/SongInfoStep.tsx` | Step 1: Artist & Title input |
| `components/job/steps/AudioSourceStep.tsx` | Step 2: Auto-search + fallback upload/URL |
| `components/job/steps/CustomizeStep.tsx` | Step 3: Title card preview + options |
| `components/job/steps/ConfirmStep.tsx` | Step 4: Review & confirm |
| `components/job/TitleCardPreview.tsx` | CSS mockup of title/end screens |

#### Modified Files
| File | Change |
|------|--------|
| `components/job/JobSubmission.tsx` | Quick wins only (kept as reference) |
| `components/audio-search/AudioSearchDialog.tsx` | Refactored to import from shared utils |
| `app/app/page.tsx` | Swapped JobSubmission for GuidedJobFlow |

### Architecture Decisions

1. **Display overrides in Step 1**: The `searchAudio` API sets display_artist/display_title at creation time (not updateable after). So the display override toggle stays in Step 1 as a collapsible section, before the search is triggered.

2. **Privacy setting timing**: For search path, `is_private` is set during the `searchAudio` call in Step 2. Step 3 (Customize) shows the current value but changes there would need a backend `updateJob` call (which supports `is_private`). For upload/URL fallback paths, `is_private` is set at creation time.

3. **Upload/URL skip customize**: When users choose upload or URL fallback in Step 2, they skip directly to Step 4 (Confirm) since the title card preview is less relevant for these paths.

4. **Search polling**: AudioSourceStep polls `getAudioSearchResults` every 2 seconds (max 30 attempts = 60s) while waiting for the backend search to complete.

5. **Error handling**: Backend errors during search show the error message and immediately offer fallback options (Upload file / YouTube URL).

## Visual Testing Results

Screenshots saved in `docs/images/`:
- `phase1-step1-initial.png` - Empty step 1 form
- `phase1-step1-filled.png` - Form with "Queen - Bohemian Rhapsody"
- `phase1-step1-display-override.png` - Display override section expanded
- `phase1-step2-searching.png` - Search loading state with spinner
- `phase1-step2-error-with-fallbacks.png` - Error handling with fallback options

## Test Results
- All 323 Jest tests pass
- Next.js build succeeds with no errors
- Visual testing confirms all Step 1 and Step 2 UI renders correctly
