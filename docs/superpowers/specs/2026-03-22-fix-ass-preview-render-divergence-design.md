# Fix ASS Preview/Render Divergence

**Date:** 2026-03-22
**Status:** Approved
**Job that exposed bug:** `0d4b550c` (The Ataris - All Souls Day)

## Problem

Lyrics that render correctly in the preview video are missing words in the final (with_vocals / final) video output. The root cause is that Word objects contain embedded newline characters (e.g., `"spell\n"`, `"broken\n"`) inherited from the transcription pipeline's segment boundary markers. These newlines corrupt ASS subtitle dialogue events by splitting them across file lines, causing the video renderer to silently drop words after the newline.

The preview path accidentally avoids this bug because `CorrectionOperations.update_correction_result_with_data()` calls `.strip()` on word text, while the final render path uses `Word.from_dict()` which does not strip.

## Root Cause Analysis

### Two divergent CorrectionResult construction paths

**Preview** (`review.py` → `CorrectionOperations.generate_preview_video()`):
1. Downloads `corrections.json` → `CorrectionResult.from_dict()`
2. Calls `update_correction_result_with_data(result, updated_data)` which constructs new Word objects with `text=w["text"].strip()` — newlines removed

**Final render** (`render_video_worker.py`):
1. Downloads `corrections.json` + `corrections_updated.json`
2. Manually merges dicts: replaces `corrections` and `corrected_segments` keys
3. Calls `CorrectionResult.from_dict(merged_data)` which constructs Word objects with `text=data["text"]` — newlines preserved
4. Newlines in word text corrupt ASS output in `LyricsLine._create_ass_text()`

### Why only some segments are affected

Newlines appear on words at segment boundaries from the original transcription (e.g., `"spell\n"` where a line break was detected). When the segment resizer splits a long segment, a word with an embedded newline may end up in the middle of a resized segment rather than at the end. When it's at the end, the newline is harmless trailing whitespace. When it's in the middle, it splits the ASS dialogue event.

## Design

### 1. Strip in `Word.__post_init__`

Add text stripping to the Word dataclass `__post_init__` so ALL Word objects are guaranteed clean regardless of construction method:

```python
@dataclass
class Word:
    ...
    def __post_init__(self):
        # Strip whitespace/newlines — embedded newlines corrupt ASS subtitle output
        self.text = self.text.strip()
```

This is the single-responsibility fix: Word is responsible for its own invariants.

### 2. Defensive strip in `_create_ass_text()`

Belt-and-suspenders safety net in the ASS output layer:

```python
# In LyricsLine._create_ass_text():
transformed_text = self._apply_case_transform(word.text.replace("\n", "").strip())
```

### 3. Refactor render_video_worker to use shared construction method

Replace the manual dict merge + `from_dict()` with `CorrectionOperations.update_correction_result_with_data()` — the same method the preview uses:

```python
# Before (render_video_worker.py):
if 'corrections' in updated_data:
    original_data['corrections'] = updated_data['corrections']
if 'corrected_segments' in updated_data:
    original_data['corrected_segments'] = updated_data['corrected_segments']
correction_result = CorrectionResult.from_dict(original_data)

# After:
base_result = CorrectionResult.from_dict(original_data)
correction_result = CorrectionOperations.update_correction_result_with_data(
    base_result, updated_data
)
```

### 4. Clean up redundant `.strip()` in `update_correction_result_with_data()`

Since `Word.__post_init__` now handles stripping, remove the explicit `.strip()` calls in `update_correction_result_with_data()` to avoid giving the impression that stripping is the caller's responsibility.

### 5. Document the lesson learned

Add to `docs/LESSONS-LEARNED.md` documenting this class of bug and the architectural principle that prevented its recurrence.

## Files Changed

| File | Change |
|------|--------|
| `karaoke_gen/lyrics_transcriber/types.py` | Add `__post_init__` to Word, strip text |
| `karaoke_gen/lyrics_transcriber/output/ass/lyrics_line.py` | Defensive strip in `_create_ass_text()` |
| `backend/workers/render_video_worker.py` | Use `update_correction_result_with_data()` instead of manual merge |
| `karaoke_gen/lyrics_transcriber/correction/operations.py` | Remove redundant `.strip()` calls |
| `docs/LESSONS-LEARNED.md` | Document the bug and fix |
| Tests | Unit tests for Word stripping, integration test for ASS output |

## What This Does NOT Change

- The preview and final render still generate separate ASS files (necessary due to resolution-dependent positioning: 360p vs 4K)
- The data flow: frontend → GCS → worker remains the same
- No changes to the frontend
