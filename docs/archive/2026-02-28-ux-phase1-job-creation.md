# Phase 1: Job Creation & Audio Input - UX Plan

> **Status**: Feedback captured, ready for detailed design
> **Screenshots**: `phase1-job-creation-current.png`, `phase1-filled-form.png`

## Current State

The job creation form at `/app` has:
- **Three equal tabs**: Search / Upload / URL - no indication which is preferred or when to use each
- **"Search For Audio Online"** heading with Artist/Title fields
- **Note**: "Format these exactly as you want them on the title card and video filename" - confusing for users who don't know what "title card" means
- **"Use different artist/title for title screen"** - collapsible, but unclear what it does
- **"Skip lyrics review (non-interactive)"** - admin-only but visible, confusing
- **"Private (non-published)"** - useful but wording is unclear
- **"Search & Create Job"** button - creates job AND searches, then user must find the job in Recent Jobs and click "Select Audio" separately (split interaction)

## User Feedback

### Search should be strongly preferred
> "We need to strongly steer users towards trying Search first as it provides high quality lossless audio which makes for a better karaoke track. Ideally they should only use Upload for tracks which aren't commercially/generally available online, and they should only use YouTube if the specific version they want a karaoke track for doesn't come up in the Search results (e.g. if it's a bootleg or specific live version or something indie which is only on YouTube)"

### Title card note is confusing
> "Honestly I'd imagine this is kinda confusing to new users who may not even know what 'title screen' means."

### Restructure as guided flow
> "I'm now wondering if it would be better to restructure it as a series of questions which leads the user to the job creation. That way we could give the user clearer guidance for each step and make the order make sense (e.g. do the audio search first, only fall back to youtube/upload if they couldn't find the exact version in the search results). If we did that the question about whether there should be a different artist/title for the title card could be answered as a separate question in this flow, with a dynamically generated preview image showing roughly what the title card would look like to help the user understand what it is."

### Remove "Skip lyrics review"
> "Honestly I can't even remember why I added 'Skip lyrics review' as an option, we should probably remove that as I don't really think there's ever a legit reason for anyone to use that."

**Investigation result**: Added Dec 25, 2025 as CLI `-y` equivalent, refined to admin-only per-job option Jan 3, 2026 (PR #162). It's an admin/testing power tool that auto-completes review stages. The backend `non_interactive` field should stay for API/admin use, but the checkbox should be removed from the job creation form.

### Rename "Private" option
> "The 'Private' option is definitely useful and important, we can probably make it even easier to understand by changing '(non-published)' to '(no public upload on YouTube)' or something"

## Proposed Design: Guided Step Flow

Replace the current tab-based form with a step-by-step guided flow:

### Step 1: "What song do you want to make a karaoke track for?"
- Artist & Title fields (simple, friendly)
- This is the same regardless of input method

### Step 2: "Find the audio"
- Auto-search runs immediately with the artist/title from Step 1
- Results appear inline (not in a separate modal after job creation)
- "Best Choice" is prominently recommended (or auto-selected - see Phase 2)
- If nothing found or wrong version: "Can't find it? Try a YouTube URL or upload your own audio file"
- Upload and URL become **fallback options**, not equal peers

### Step 3: "How should it look?"
- Title card preview (dynamically rendered) showing roughly what the title/end screens will look like
- Option to override artist/title for display
- Private toggle with clearer label: "Private (no YouTube upload)"
- This step gives context for what "title card" actually means

### Step 4: Confirm & Create

## Key Technical Considerations

### Current flow (split interaction):
```
Form → "Search & Create Job" → Job created in backend → Job appears in Recent Jobs list
→ User clicks "Select Audio" on job card → Modal dialog opens → User picks result → Job progresses
```

### Proposed flow (unified):
```
Step 1 (artist/title) → Step 2 (search results inline, or fallback to upload/URL)
→ Step 3 (title card preview, private toggle) → Step 4 (confirm) → Job created & processing
```

The key complexity: currently the backend creates the job when the search is initiated. The guided flow might need to either:
1. Still create the job early but hide that from the user (keep current backend flow, change frontend presentation)
2. Defer job creation until the user confirms everything (would require backend changes)

Option 1 is probably simpler and lower-risk.

### Components affected:
- `frontend/components/job/JobSubmission.tsx` - Main form (3 tab state objects, submit handlers)
- `frontend/components/audio-search/AudioSearchDialog.tsx` - Currently a modal, would become inline
- `frontend/components/job/JobCard.tsx` - Currently shows "Select Audio" button for awaiting jobs
- `frontend/app/app/page.tsx` - Main dashboard layout (2-column: form + recent jobs)
- `frontend/lib/api.ts` - `searchAudio()`, `getAudioSearchResults()`, `selectAudioResult()`

## Changes to Ship

1. **Remove "Skip lyrics review" checkbox** from all 3 tabs in JobSubmission.tsx (lines 325-348, 447-470, 607-630). Keep backend `non_interactive` field.
2. **Rename "Private (non-published)"** to "Private (no YouTube upload)" or similar
3. **Restructure form** as guided step flow (major change - needs detailed component design)
4. **Title card preview** - dynamically generated preview showing what title screen looks like
5. **Inline audio search results** - move from modal dialog to inline step in guided flow
6. **Fallback positioning** - Upload/URL presented as fallbacks when Search doesn't find the right track
