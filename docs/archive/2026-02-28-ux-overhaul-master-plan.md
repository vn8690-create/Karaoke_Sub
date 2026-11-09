# UX Overhaul - Master Plan

> **Status**: Phases 1-3 complete, Phase 4 remaining
> **Created**: 2026-02-28
> **Branch**: feat/sess-20260227-1637-ux-overhaul
> **Worktree**: /Users/andrew/Projects/nomadkaraoke/karaoke-gen-ux-overhaul

## Overview

The karaoke generation platform was built for personal/power-user use. New users lack guidance at each stage of the multi-step process. This UX overhaul will improve guidance, simplify choices, and steer users toward the best outcomes.

## Phased Approach

The system has several distinct stages of human interaction, each requiring dedicated UX thought. We're breaking this into phases, with a detailed plan for each phase created through live UI walkthrough with screenshots and user feedback.

### Phase 1: Job Creation & Audio Input ✅
**Plan**: [2026-02-28-ux-phase1-job-creation.md](2026-02-28-ux-phase1-job-creation.md)
**Implementation**: [2026-02-28-ux-phase1-implementation.md](2026-02-28-ux-phase1-implementation.md)
**Scope**: Restructure the job creation form as a guided flow. Steer users toward Search as the default path, with Upload/URL as fallbacks.
**Done**: Removed "Skip lyrics review" checkbox, renamed Private label, built 3-step GuidedJobFlow wizard, title card preview, production E2E tests. Renamed "Find Audio" → "Choose Audio".

### Phase 2: Audio Source Selection ✅
**Plan**: [2026-02-28-ux-phase2-audio-selection.md](2026-02-28-ux-phase2-audio-selection.md)
**Scope**: Auto-select audio for simple cases, improve guidance for complex cases, build heuristics from real usage data.
**Done**: 3-tier confidence system (perfect match / recommended / limited sources), guidance-first layout for Tier 3, validated against 41 production fixtures with unit tests.

### Phase 3: Lyrics Review ✅
**Plan**: [2026-02-28-ux-phase3-lyrics-review.md](2026-02-28-ux-phase3-lyrics-review.md)
**Scope**: Add onboarding, explain color coding, guide users through the correction workflow. This is the most complex screen.
**Done**: Guidance panel replacing stats bar (collapsible, color coding legend, workflow tips), gap navigator with keyboard shortcuts (J/K), simplified toolbar with Advanced Mode toggle, hidden line numbers/delete icons by default, edit tracking system with low-friction feedback bar for transcription improvement data collection. 40 tests.

### Phase 4: Instrumental Review ← REMAINING
**Plan**: [2026-02-28-ux-phase4-instrumental-review.md](2026-02-28-ux-phase4-instrumental-review.md)
**Scope**: Explain what backing vocals are, guide the listen/decide flow, simplify the default case.

## Cross-Cutting Concerns

- **Remove "Skip lyrics review" checkbox** from UI (keep backend field for API/admin use)
- **Rename "Private (non-published)"** to something clearer like "Private (no YouTube upload)"
- **Auto-select heuristics training** - Pull last ~50 jobs, capture what audio the user would choose and why, codify into algorithm (may be a separate workstream touching flacfetch)

## Screenshots Captured

All screenshots saved in the worktree root during the walkthrough session:

### Phase 1: Job Creation
- `phase1-job-creation-current.png` - Current job creation form
- `phase1-filled-form.png` - Form filled with Coldplay - Parachutes
- `phase1-job-created-awaiting-audio.png` - Job created, awaiting audio selection

### Phase 2: Audio Source Selection
- `phase2-audio-search-results.png` - Audio search results dialog (Coldplay, top)
- `phase2-audio-search-bottom.png` - Audio search results dialog (Coldplay, bottom)
- `phase2-pony-bradshaw-results.png` - Audio search results for obscure track (Pony Bradshaw)

### Phase 3: Lyrics Review (Difficulty Spectrum)
- `phase3-lyrics-review.png` / `phase3-lyrics-review-top.png` - Bon Jovi lyrics review (easy-medium, 94% anchored)
- `phase3-lyrics-review-bottom.png` - Bon Jovi lyrics review (bottom/end of lyrics)
- `phase3-bon-jovi-review.png` - Bon Jovi "It's My Life" (easy-medium: 94% anchored, 9 gaps, 18 words)
- `phase3-silversun-pickups-review.png` - Silversun Pickups (medium: 84% anchored, 8 gaps, 32 words)
- `phase3-steve-taylor-review.png` - Steve Taylor live (hard: 42% anchored, 20 gaps, 194 words, wrong reference lyrics)
- `phase3-preview-dialog.png` - Preview Video dialog (transition from lyrics to instrumental review)

### Phase 4: Instrumental Review
- `phase4-instrumental-review.png` - Instrumental review page (Coldplay - Parachutes, 4% backing vocals, Clean recommended)

## Test Jobs Used

| Track | ID | Difficulty | Stage |
|-------|-----|-----------|-------|
| Coldplay - Parachutes | a95023e8 | Easy | Progressed to instrumental review |
| Bon Jovi - It's My Life | c235f6bd | Easy-Medium | At lyrics review |
| Silversun Pickups - Well Thought Out Twinkles | 41026cfe | Medium | At lyrics review |
| Pony Bradshaw - Jehovah | 3552d63d | Medium | At lyrics review |
| Steve Taylor - Jim Morrisons Grave - Live | ce8f2901 | Hard | At lyrics review |
