# Phase 3: Lyrics Review - UX Plan

> **Status**: Implemented
> **Screenshots**: `phase3-lyrics-review-top.png`, `phase3-lyrics-review-bottom.png`

## Implementation Summary (2026-03-01)

### Guidance Panel (replaces stats bar)
- `GuidancePanel.tsx` — collapsible panel with color coding legend, workflow tips
- Stats hidden behind toggle (previously always visible, overwhelming for new users)
- Contextual tips for common correction types (phantom words, mis-heard words, etc.)

### Gap Navigator
- `GapNavigator.tsx` — "Gap 3 of 9" with prev/next buttons
- Keyboard shortcuts: J (next gap), K (previous gap)
- Auto-scrolls to gap and flashes the relevant words
- Scoped to uncorrected gaps only

### Simplified Toolbar
- Advanced Mode toggle (persisted in localStorage)
- Default: hides line numbers, delete icons, power-user tools
- Advanced: shows Find/Replace, Edit All, Undo Auto Corrections, Timing Offset

### Edit Tracking & Feedback System
- `editLog.ts` — session-based edit log capturing all user edits (word changes, deletions, additions, find/replace, segment operations, reverts)
- `EditFeedbackBar.tsx` — slim feedback bar above sticky footer, appears after single-word edits with contextual "why?" buttons (Mis-heard word, Wrong lyrics, Spelling/punctuation, etc.)
- Auto-dismisses after 10 seconds, pauses timer while hovered
- Edit logs submitted to backend on review completion for transcription model improvement
- Replaces the old high-friction `CorrectionAnnotationModal` (9 categories, confidence slider — nobody used it)
- Backend endpoints: `POST /api/jobs/{job_id}/edit-log` (GCS storage), `POST /api/review/{job_id}/v1/annotations` (fixed from stub)
- 40 tests across frontend and backend

### Word Component Improvements
- Active gap ring indicator (persistent highlight for currently navigated gap)
- Color coding preserved: blue = matched/confident, orange = needs review

## Current State

The lyrics review page at `/app/jobs#/{jobId}/review` is the most complex screen in the app. It's a combined review flow (lyrics + instrumental selection in one session).

### Top Stats Bar
Four cards showing:
- **Correction Handlers** - collapsed section (unclear what this means)
- **Anchor Sequences: 19 (94%)** - "Matched sections between transcription and reference", sub-stats: "Words in Anchors: 266", "Multi-source Matches: 19"
- **Corrected Gaps: 0 (0%)** - "Successfully corrected sections", sub-stats: "Words Replaced: 0", "Words Added/Deleted: +0/-0"
- **Uncorrected Gaps: 9 (6%)** - "Sections that may need manual review", sub-stats: "Words Uncorrected: 18", "Number of Gaps: 9"

### Toolbar
- **Mode buttons**: Edit (selected), Highlight, Delete
- **Actions**: Undo All, undo/redo arrows, Find/Replace, Edit All
- **Secondary row**: Undo Auto Corrections, Timing Offset, Feedback On
- **Playback**: Play button with timeline slider (0:00 to 3:44)

### Left Panel: Corrected Transcription
- Numbered lines (0-49 for Bon Jovi example)
- Each line has: line number, delete icon, play icon, lyrics text
- **Text/Timeline toggle** at top
- Words are color-coded (see Color Coding section below)

### Right Panel: Reference Lyrics
- **Source tabs**: Lrclib (selected), Genius, Spotify, + New
- Copy button next to "Reference Lyrics" heading
- Reference text with color-coded highlights matching the left panel

### Bottom Bar (Sticky)
- "Lyrics look good?" text
- **"Preview Video"** pink button
- After preview, user clicks "Proceed to Instrumental Review" (green button) to move to Phase 4

### Flow: Lyrics → Preview → Instrumental
The combined review flow is:
1. User reviews/corrects lyrics on this page
2. User clicks "Preview Video" to generate a preview with their corrections
3. User watches preview to verify sync
4. User clicks "Proceed to Instrumental Review" to move to instrumental selection (Phase 4)

## User Feedback

### Stats Bar
> "This whole section could probably be removed or hidden behind a 'Stats' toggle button or something. Maybe we could use the space in this section to give the user guidance on how to use the tool instead?"

### Toolbar
> "Agreed re. 'no guidance on when to use which' but I'm not really sure how best to resolve that without making the UI even more cluttered/overwhelming. Maybe the section above could be sufficient to give the user guidance on these buttons too, if we can make smart/efficient use of the space. We should also ensure all buttons have really rich, helpful tooltips (but also consider mobile users who may not have access to tooltips)."

### Left Panel
> "All users definitely need the play button beside lines, but the line numbers and delete icons should probably be hidden unless the user enables 'Advanced Mode' or something"

### Color Coding (User's Explanation)
> "Blue means 'matched with reference lyrics, so most likely correct'. Orange means 'unable to match with reference lyrics, so needs to be reviewed and either edited or deleted'."
>
> "Generally the user should be focusing on the Corrected Transcription panel. Words which are highlighted in blue are highly likely to be correct, so the user should focus on the words which are highlighted in orange (the 'gaps')."

### Correction Workflow
> "I immediately focus on the gaps (highlighted in orange), typically I click the play icon beside those lines to listen to what the singer actually sings in each segment, while visually trying to find the relevant part of the reference lyrics to advise me on what action to take. Then I'll click on the segment and either edit, merge, delete words as necessary, adjust word timings etc. till the lyrics in that segment are correct and well synced, then press enter/click save. I'll repeat that for every gap until I'm confident I've reviewed and corrected (where necessary) all gaps, then I'll hit preview and listen to the whole track once to ensure the sync is fine before proceeding to instrumental review."

### Common Types of Corrections Needed

**1. Phantom words (delete)**
> "The transcription very commonly puts 'And' at the start of lines during an instrumental section, in which case that word just needs to be deleted by clicking on the segment and clicking the delete icon beside the word."

**2. Mis-heard words (edit)**
> "In many cases, the transcription just has some mistakes where it mis-heard things."

**3. Stylistic differences (no action needed)**
> "In some cases, they may notice it's just a stylistic difference (e.g. the transcription writes '22' whereas reference lyrics write 'twenty two') and there's no action required."

**4. Reference lyrics are imperfect too**
> "Lyrics fetched from the internet are also not 100% accurate, and in some cases are not available at all, so the user should use their best judgement when making these corrections."

### Difficulty Varies Hugely by Track

**Easy tracks** (acoustic, country, clear vocals):
> "Acoustic or country tracks or pretty much anything with simple clear vocals tend to be transcribed really well and there may be no gaps / corrections to be made at all, or only a couple."

**Hard tracks** (rock, screamo, unclear vocals):
> "Hard rock, screamo, or anything where the vocals aren't super clear can be a challenge - in some bad cases the transcription may be more than 50% incorrect and there can be quite a lot of work to do to get it corrected."

### Concrete Examples from Walkthrough

5 tracks at lyrics review stage, showing the full difficulty spectrum:

| Track | ID | Difficulty | Notes |
|-------|-----|-----------|-------|
| Coldplay - Parachutes | a95023e8 | Easy | Short song, only 2 mistakes: phantom "And" to delete, "I" → "I'll" |
| Bon Jovi - It's My Life | c235f6bd | Easy-Medium | Few gaps, some need no action ("wanna", "calling"), but "Love can't even look, you gotta" is clearly mis-heard |
| Silversun Pickups - Well Thought Out Twinkles | 41026cfe | Medium | Several clear transcription errors, e.g. "Share about elliptic views" → "We share apocalyptic views" |
| Pony Bradshaw - Jehovah | 3552d63d | Medium | Several clear errors, e.g. "In Dilla, town on fire" → "A dilettante on fire" |
| Steve Taylor - Jim Morrisons Grave - Live | ce8f2901 | Hard | Live version from YouTube, whole spoken section at start before singing begins (needs bulk deletion), plus many transcription mistakes e.g. "Jim Morrison, cryin'" → "Jim Morrison's Grave" |

## Proposed Design

### Replace Stats Bar with Guidance Panel
Use the stats bar space for user guidance instead:
- Brief explanation of what this page is for
- Color coding legend (blue = matched/confident, orange = needs review)
- Quick workflow tip: "Focus on the orange highlighted words. Click the play button to listen, then click the word to edit."
- Collapsible "Stats" section for power users who want the numbers
- Consider making this dismissible after first visit (remember in localStorage)

### Toolbar Improvements
- Rich, helpful tooltips on all buttons (important: also consider mobile users who can't hover)
- Consider "Advanced Mode" toggle that shows/hides power-user tools
- Default view: Edit mode, play button, undo/redo, Preview Video
- Advanced view: adds Highlight, Delete, Find/Replace, Timing Offset, Edit All

### Left Panel Simplification
- **Hide by default**: Line numbers, delete icons
- **Show by default**: Play button, lyrics text with color coding
- **Advanced Mode**: Shows line numbers, delete icons, and other power tools
- Play button is essential for all users (core to the correction workflow)

### Guided Gap Review Mode
Based on the user's workflow of stepping through gaps:
- "Jump to next gap" button/shortcut
- Auto-scroll to the next uncorrected gap
- Highlight the corresponding section in reference lyrics
- Show a count: "Gap 3 of 9" with prev/next navigation

### Color Coding Legend
Persistent but minimal:
- Small bar or badge near the top: "🔵 Matched with reference lyrics" | "🟠 Needs your review"
- Or integrated into the guidance panel

### Contextual Tips for Common Corrections
Based on the user's experience, show tips like:
- "Phantom words: If you see an extra word like 'And' at the start of a line during music, delete it"
- "Listen first: Click the play button to hear what's actually sung before editing"
- "Reference lyrics aren't perfect either - use your best judgement"
- "Stylistic differences (e.g. '22' vs 'twenty two') don't need correcting"

### Preview & Submit Flow
- After correcting gaps, user clicks "Preview Video"
- Preview plays; user verifies sync
- "Proceed to Instrumental Review" button moves to Phase 4
- This flow is already in place - just needs clearer labeling/guidance

## Components Affected

- `frontend/components/` - Need to explore the review components in detail
- The review UI was originally a separate React+Vite+MUI app (~14k lines) consolidated into the main Next.js frontend in Jan 2026
- Key route: `/app/jobs#/{jobId}/review` (hash-based routing)
- Stats panel component (replace with guidance panel)
- Toolbar component (add tooltips, advanced mode toggle)
- Transcription line component (hide line numbers/delete by default)
- Need to identify the "gap navigation" mechanism if one exists
