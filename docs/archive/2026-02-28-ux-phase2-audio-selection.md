# Phase 2: Audio Source Selection - UX Plan

> **Status**: Implemented and verified with 41 production fixtures
> **Screenshots**: `phase2-audio-search-results.png`, `phase2-audio-search-bottom.png`, `phase2-pony-bradshaw-results.png`

## Implementation Summary (2026-02-28)

### 3-Tier Confidence System
Built in `frontend/lib/audio-search-utils.ts` and `frontend/components/job/steps/AudioSourceStep.tsx`:

- **Tier 1 ("Perfect match found")**: Green card, best result is lossless with 50+ seeders and no filename mismatch
- **Tier 2 ("Recommended")**: Amber card with reasoning — has lossless options but not clearly ideal
- **Tier 3 ("Limited sources found")**: Guidance-first layout — upload/URL fallback shown above search results

### Key Features
- **Filename mismatch detection**: Compares search title against `target_file` (torrent/Spotify) or `title` (YouTube). Handles underscores as word separators, skips non-Latin scripts gracefully. Shows "Title match" / "Wrong track?" badges.
- **Spotify separated from YouTube**: Own category with green styling, higher priority than YouTube in best-result selection
- **Dynamic guidance tips**: The "Limited sources found" box only shows tips relevant to the actual result types found
- **Color-coded view counts**: Green (1M+), amber (100K+), neutral for YouTube/Spotify results
- **Availability tooltips**: User-friendly language ("may take a bit more time to prepare")

### Testing
- 75 unit tests for `audio-search-utils.ts` (96%+ coverage)
- 47 fixture confidence tests against 41 production search results
- Fixture review tooling: `npm run fixtures:review-ui` for visual verification
- E2E regression tests (25 tests) and production E2E tests (7 tests)

## Current State

The "Select Audio Source" modal dialog shows:
- **Title**: "Select Audio Source v0.119.8 (N results across M categories)"
- **Categories** (up to 9): BEST CHOICE, HI-RES 24-BIT, STUDIO ALBUMS, SINGLES, LIVE VERSIONS, COMPILATIONS, VINYL RIPS, YOUTUBE/LOSSY, OTHER
- Each result shows: index number, quality badges (LOSSLESS, VINYL, YouTube), artist, title, format details, file size, availability badge (High/Medium/Low color-coded), album metadata, target filename
- Each category shows 2-3 results by default with "+N more" expand button
- Each result has a "Select" button

## Problems Identified

### Too much information / too much choice
> "It's just too much information and probably too much choice for most users who just know what song they want a karaoke version of."

### Wrong songs appear in results
- Coldplay "Parachutes" search returned "Everything's Not Lost", "High Speed", "Spies" (other songs from the same album or artist)
- Pony Bradshaw "Jehovah" search returned "Van Gogh", "Josephine" (other songs by same artist)
- The compilation results (#27, #28 for Coldplay) showed filename "Parachutes/03 - Spies.flac" - a different track entirely
- Users need domain knowledge to evaluate these

### Availability badges unexplained
- High (green), Medium (yellow/orange), Low (red) availability badges are shown but never explained
- Users don't know that availability directly affects download success rate

### No guidance on what matters for karaoke
- 24-bit vs 16-bit doesn't matter much for karaoke (vocals get removed anyway)
- Vinyl rips may have surface noise that affects separation quality
- Availability matters more than bit depth for reliability
- Live versions will sound different from studio versions

## User Feedback

### Auto-select for simple cases
> "For those simple/standard users who are making karaoke tracks which have commercially available releases which are easy to download (like this Coldplay example), we should probably just make the choice for the user and only show them this more complex set of alternate options if they explicitly click something to show more advanced options."

### Better guidance for advanced view
> "There's also several gotchas which aren't communicated on this view at all, e.g. the fact that vinyl versions, live versions, or other songs entirely may show up (you have to check the filename makes sense for the song you wanted) so even if we keep this view as an 'advanced' or 'show more options' view in the UX rework, we should add better guidance to it to help users know what to look for."

### Obscure tracks are trickier
For Pony Bradshaw - Jehovah (less popular track):
- No "BEST CHOICE" section appeared
- Only 3 categories: HI-RES 24-BIT (1, Low availability), STUDIO ALBUMS (4, Medium/Low), YOUTUBE/LOSSY (5)
- User's choice: Studio Album #1 (Medium availability, 16bit CD) because "it's the most available (and thus will download the fastest) and 24bit input audio is overkill for karaoke"

### Build auto-select heuristics from real data
> "In order to make the system reliably make a good default choice for the user, we probably ought to run searches for a bunch of input tracks with a variety of popularities (we could just look at the last 50 tracks I've actually made through this karaoke generator as they're already a pretty diverse mix) and for every track, capture what audio I would choose in this 'Select Audio Source' modal AND WHY, then use that reasoning information to build a system which auto-chooses for the user."

## Proposed Design

### Tier 1: Auto-Select (Simple Cases)
When there's a clear winner (BEST CHOICE category with High availability):
- **Auto-select it** and show the user a simple confirmation:
  - "We found a high-quality lossless version of this track from [Album / Year / Label]"
  - Small "See all options" or "Choose a different version" link for power users
- This covers the majority of popular/commercially available tracks

### Tier 2: Recommended Pick (Medium Confidence)
When there's no BEST CHOICE but there are reasonable lossless options:
- **Highlight the recommended pick** with clear reasoning: "Recommended: Studio album version with reliable availability"
- Show the recommendation prominently, with other options below in a collapsed "Other options" section
- Add brief explanation of why this was chosen

### Tier 3: Manual Selection Required (Low Confidence)
When results are very limited, all low availability, or no lossless options:
- Show all results with guidance
- Add contextual tips at the top:
  - "Check the filename matches your song title"
  - "Higher availability = more reliable download"
  - "Studio album versions typically produce the best karaoke results"
  - "Vinyl rips may have surface noise"
  - "YouTube is lower quality but works for rare/live tracks"

### Advanced View (Always Accessible)
Keep the current full category view as an "Advanced options" panel:
- Add guidance header explaining the gotchas
- Add tooltips on availability badges explaining what they mean
- Flag potentially wrong tracks (filename doesn't match search title)
- Consider dimming or warning on results where the filename suggests a different song

## Auto-Select Heuristics Training Plan

### Data Collection
1. Pull the last ~50 completed jobs from Firestore
2. For each job that went through audio search:
   - Retrieve the cached search results (what options were available)
   - Record which result index was selected
   - Have the user annotate WHY that choice was made
3. Categorize by popularity/availability patterns

### Heuristic Rules to Codify
Based on walkthrough observations:
1. **Availability > bit depth** for karaoke (failed download = start over, 24-bit is wasted)
2. **Filename must match song title** (compilation results often have wrong tracks)
3. **Prefer studio albums** over compilations, vinyl rips, live versions
4. **Avoid vinyl rips** for karaoke (surface noise affects vocal separation)
5. **YouTube/lossy is last resort** (lower quality, may be different arrangements)
6. **When in doubt, pick highest availability** among lossless results

### Implementation
- Could live in flacfetch's ranking logic (already has some of this)
- Or as a frontend/backend layer that post-processes flacfetch results
- Should be testable: given a set of search results, predict the correct selection

## Components Affected

- `frontend/components/audio-search/AudioSearchDialog.tsx` - Major refactor to add tiers
- `frontend/lib/api.ts` - May need new endpoint or parameter for auto-select
- Possibly `flacfetch` ranking algorithm (separate repo/workstream)
- Backend may need a "confidence score" or "recommended index" in search results response
