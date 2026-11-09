# Phase 4: Instrumental Review - UX Plan

> **Status**: User feedback captured, ready for detailed design
> **Screenshots**: `phase4-instrumental-review.png`

## Current State

The instrumental review page at `/app/jobs#/{jobId}/instrumental` is the final human review stage before the video is generated. It's a significantly simpler interface than the lyrics review.

### Header Bar
- Track name (e.g., "Coldplay - Parachutes")
- Three stat badges:
  - **Segments count** (e.g., "1 segments")
  - **Backing vocals percentage** (e.g., "4% backing vocals")
  - **Recommendation badge** (e.g., "Clean recommended" in pink)

### Audio Player Controls
- Play button with current time / total duration
- **4 audio toggle buttons**: Original, Backing Vocals Only, Pure Instrumental, Instrumental + Backing
- Upload button (for uploading a custom instrumental)
- Zoom levels: 1x, 2x, 4x
- Keyboard shortcuts: Shift+drag (select region), Space (play/pause)

### Waveform Visualization
- Two waveform tracks displayed with timeline markers
- Shows the audio waveform across the full track duration
- Interactive - users can click/drag to select regions

### Mute Regions Panel (Bottom Left)
- "Click segments below or Shift + drag on waveform"
- Shows detected backing vocal segments as clickable buttons (e.g., "0:38 - 0:40")
- Users can add custom mute regions by shift+dragging on the waveform

### Final Selection Panel (Bottom Right)
Three options:
1. **Clean Instrumental** - "No backing vocals" - shown with "Recommended" badge when backing vocals % is low
2. **With Backing Vocals** - "All backing vocals included"
3. **Original Audio** - "Full original with lead vocals"
- **"Confirm & Continue"** button to finalize and proceed to video generation

## User Feedback

### No explanation of what this page is or how to use it
> "The page doesn't explain to the user what it is and how to use it."

The page drops users in with no context about what they're looking at or what they should do.

### The Primary Workflow Users Should Follow

> "The primary thing they should start with is clicking on any pink sections in the waveform to listen to how the backing vocals sound, decide if the backing vocals should be kept or if we should use the clean instrumental, and if they want the backing vocals but they're mixed in with lead vocals for some sections of the song, they need to create a custom instrumental by shift-dragging on the waveform to mark sections for muting, clicking 'Create Custom', then selecting that."

The intended workflow is:
1. **Listen to pink sections** - Click on any pink (backing vocal) segments in the waveform to hear what they sound like
2. **Decide: keep or remove?** - Do the backing vocals add to the karaoke experience, or should they be removed?
3. **If keeping backing vocals but some sections have lead vocal bleed**: Create a custom instrumental by shift+dragging on the waveform to mark problem sections for muting, click "Create Custom", then select that custom version
4. **Confirm selection** and proceed to video generation

### Three Possible Outcomes

**Simple case (clean)**: Backing vocals are minimal or unwanted → select "Clean Instrumental" → Confirm

**Simple case (keep backing vocals)**: Backing vocals sound good throughout → select "With Backing Vocals" → Confirm

**Complex case (custom)**: Want backing vocals but some sections have lead vocal bleed → mute problem sections → "Create Custom" → select custom version → Confirm

## Observations

### What's Working Well
- The page is much simpler than lyrics review - clear, focused decision
- The recommendation badge ("Clean recommended") is helpful
- Audio toggle buttons let users A/B test between instrumental options
- Waveform visualization with pink backing vocal highlights is intuitive once you know what to do

### Potential Issues for New Users

#### 1. No onboarding or explanation
- Users don't know what "backing vocals" are or why this review exists
- No guidance on what to do first (click pink sections to listen)
- The whole purpose of the page needs a brief introduction

#### 2. The workflow isn't communicated
- Users should start by listening to backing vocal segments, but nothing tells them this
- The decision tree (clean vs backing vocals vs custom) isn't explained
- "Create Custom" workflow (shift+drag → mute → create) is completely hidden

#### 3. Mute Regions / Custom Instrumental flow is opaque
- "Click segments below or Shift + drag on waveform" is the only guidance
- Users don't know WHEN they'd want to mute regions (answer: when backing vocals are mixed with lead vocal bleed in specific sections)
- The connection between muting sections and creating a "Custom" instrumental option isn't clear

#### 4. What does "Upload" do?
- The Upload button near the audio toggles isn't explained
- Needs a tooltip or brief explanation

#### 5. Stats badges are jargon-heavy
- "1 segments" and "4% backing vocals" - what do these mean to a new user?
- The recommendation badge is good, but the numbers without context may confuse

## Proposed Design

### Replace Stats Bar with Guided Onboarding (Consistent with Phase 3 Approach)
Replace the stats badges area with a guidance panel that explains:
- **What this page is**: "This is where you choose your karaoke backing track. The AI has separated the vocals from the music - now you decide which version sounds best."
- **What backing vocals are**: "Backing vocals are the harmony/chorus voices that sing along with the lead singer. Some karaoke singers prefer to keep them for guidance, others prefer a pure instrumental."
- **What to do first**: "Start by clicking the pink highlighted sections in the waveform to listen to the backing vocals. Then decide if you want to keep them or use a clean instrumental."
- Collapsible/dismissible for returning users (localStorage)

### Guided Workflow Steps
Present the decision as a clear flow:

**Step 1: Listen** - "Click the pink sections in the waveform to hear the backing vocals"

**Step 2: Decide** - "Do you want to keep the backing vocals?"
- If no → "Select Clean Instrumental and confirm"
- If yes → "Select With Backing Vocals. If some sections have unwanted lead vocal bleed, continue to Step 3"

**Step 3 (if needed): Customize** - "Shift+drag on the waveform to mark sections where lead vocals bleed through, then click Create Custom to generate a custom instrumental with those sections muted"

### Contextual Recommendations
The system already recommends "Clean" when backing vocals are low (4%). Enhance this with:
- Clear reasoning: "We recommend Clean Instrumental because this track has very few backing vocals (4%)"
- For tracks with high backing vocal %, recommend "With Backing Vocals" and explain why

### Simplify for Default Users
- For tracks where the recommendation is clear, the guidance could suggest just confirming
- "This track has very little backing vocal content. We recommend the Clean Instrumental - confirm below to proceed!"
- The "Confirm & Continue" button could be more prominent

### Improve Mute Regions / Custom Instrumental UX
- Explain WHEN users need this: "If you want backing vocals but notice lead vocal bleed in certain sections, you can mute those sections to create a custom mix"
- Make the shift+drag → Create Custom flow more discoverable
- Consider a more guided approach: "Hear something that shouldn't be there? Shift+drag over that section to mark it for muting"

## Flow After Confirmation

After clicking "Confirm & Continue":
- The job progresses to video generation
- This is the final human review step
- User then waits for the video to be rendered and can download it

## Components Affected

- Need to explore the instrumental review components in detail
- Key route: `/app/jobs#/{jobId}/instrumental` (hash-based routing)
- The audio player with waveform visualization
- The backing vocal detection/mute regions system
- The final selection radio group
