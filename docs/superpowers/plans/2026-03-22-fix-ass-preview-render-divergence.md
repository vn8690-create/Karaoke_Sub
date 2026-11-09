# Fix ASS Preview/Render Divergence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the divergence between preview and final render by unifying Word text sanitization and CorrectionResult construction, preventing embedded newlines from corrupting ASS subtitle output.

**Architecture:** Strip whitespace in `Word.__post_init__` (single source of truth for Word invariants), add defensive strip in ASS output, refactor render worker to use the shared `update_correction_result_with_data()` method, and document the lesson learned.

**Tech Stack:** Python dataclasses, ASS subtitle format, FastAPI workers

**Spec:** `docs/superpowers/specs/2026-03-22-fix-ass-preview-render-divergence-design.md`

---

## File Structure

| File | Responsibility | Change |
|------|---------------|--------|
| `karaoke_gen/lyrics_transcriber/types.py` | Word/Segment data types | Add `__post_init__` to strip text |
| `karaoke_gen/lyrics_transcriber/output/ass/lyrics_line.py` | ASS dialogue event generation | Defensive strip in `_create_ass_text()` |
| `backend/workers/render_video_worker.py` | Final video render orchestration | Use `update_correction_result_with_data()` |
| `karaoke_gen/lyrics_transcriber/correction/operations.py` | Shared correction operations | Remove redundant `.strip()` calls |
| `docs/LESSONS-LEARNED.md` | Project knowledge base | Document this bug class |
| `tests/unit/test_word_text_sanitization.py` | New test file | Word stripping + ASS output tests |

---

### Task 1: Add `__post_init__` to Word dataclass

**Files:**
- Modify: `karaoke_gen/lyrics_transcriber/types.py:7-37`
- Create: `tests/unit/test_word_text_sanitization.py`

- [ ] **Step 1: Create test file with failing tests for Word text stripping**

Create `tests/unit/test_word_text_sanitization.py`:

```python
"""Tests for Word text sanitization — ensures embedded newlines never reach ASS output."""

import pytest
from karaoke_gen.lyrics_transcriber.types import Word, LyricsSegment


class TestWordTextSanitization:
    """Word.__post_init__ must strip whitespace/newlines from text."""

    def test_trailing_newline_stripped(self):
        word = Word(id="w1", text="spell\n", start_time=1.0, end_time=2.0)
        assert word.text == "spell"

    def test_trailing_double_newline_stripped(self):
        word = Word(id="w1", text="end\n\n", start_time=1.0, end_time=2.0)
        assert word.text == "end"

    def test_leading_whitespace_stripped(self):
        word = Word(id="w1", text=" hello", start_time=1.0, end_time=2.0)
        assert word.text == "hello"

    def test_mixed_whitespace_stripped(self):
        word = Word(id="w1", text="\n spell \n", start_time=1.0, end_time=2.0)
        assert word.text == "spell"

    def test_clean_text_unchanged(self):
        word = Word(id="w1", text="hello", start_time=1.0, end_time=2.0)
        assert word.text == "hello"

    def test_from_dict_strips_text(self):
        """from_dict must also strip — this was the original bug."""
        word = Word.from_dict({
            "id": "w1",
            "text": "spell\n",
            "start_time": 1.0,
            "end_time": 2.0,
        })
        assert word.text == "spell"

    def test_from_dict_with_double_newline(self):
        word = Word.from_dict({
            "id": "w1",
            "text": "broken\n\n",
            "start_time": 1.0,
            "end_time": 2.0,
        })
        assert word.text == "broken"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andrew/Projects/nomadkaraoke/karaoke-gen-fix-ass-preview-render-divergence && poetry run pytest tests/unit/test_word_text_sanitization.py -v`

Expected: 5 FAIL (trailing newlines not stripped), 2 PASS (clean text, leading whitespace might pass by accident)

- [ ] **Step 3: Add `__post_init__` to Word dataclass**

In `karaoke_gen/lyrics_transcriber/types.py`, add after line 17 (after `created_during_correction` field):

```python
    def __post_init__(self):
        """Strip whitespace/newlines from text.

        Word text from transcription pipelines may contain embedded newline
        characters at segment boundaries (e.g., "spell\\n"). These corrupt ASS
        subtitle output by splitting dialogue events across file lines, causing
        words after the newline to be silently dropped by video renderers.
        """
        self.text = self.text.strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andrew/Projects/nomadkaraoke/karaoke-gen-fix-ass-preview-render-divergence && poetry run pytest tests/unit/test_word_text_sanitization.py -v`

Expected: All 7 PASS

- [ ] **Step 5: Commit**

```bash
git add karaoke_gen/lyrics_transcriber/types.py tests/unit/test_word_text_sanitization.py
git commit -m "fix: strip whitespace/newlines from Word text in __post_init__

Embedded newlines in word text (e.g. 'spell\n') corrupt ASS subtitle
dialogue events by splitting them across file lines. Words after the
newline are silently dropped by the video renderer.

This was the root cause of lyrics missing in final renders but
appearing correctly in previews (job 0d4b550c)."
```

---

### Task 2: Add defensive strip in ASS output

**Files:**
- Modify: `karaoke_gen/lyrics_transcriber/output/ass/lyrics_line.py:237-262`
- Modify: `tests/unit/test_word_text_sanitization.py`

- [ ] **Step 1: Add test for ASS text generation with newline words**

Append to `tests/unit/test_word_text_sanitization.py`:

```python
from karaoke_gen.lyrics_transcriber.output.ass.lyrics_line import LyricsLine
from karaoke_gen.lyrics_transcriber.output.ass.config import ScreenConfig


class TestASSOutputSanitization:
    """ASS output must never contain literal newlines in dialogue text."""

    def _make_segment(self, words_data):
        """Helper to create a LyricsSegment from word tuples (text, start, end)."""
        words = [
            Word(id=f"w{i}", text=text, start_time=start, end_time=end)
            for i, (text, start, end) in enumerate(words_data)
        ]
        text = " ".join(w.text for w in words)
        return LyricsSegment(
            id="seg1", text=text, words=words,
            start_time=words[0].start_time, end_time=words[-1].end_time,
        )

    def test_ass_text_no_literal_newlines(self):
        """Even if Word.__post_init__ were bypassed, ASS output must not contain newlines."""
        segment = self._make_segment([
            ("the", 54.11, 54.26),
            ("spell", 54.30, 55.14),
            ("we're", 55.18, 55.83),
            ("under", 55.93, 57.24),
        ])
        config = ScreenConfig(line_height=50)
        line = LyricsLine(segment=segment, screen_config=config)
        # Access the private method to test ASS text generation
        from datetime import timedelta
        ass_text = line._create_ass_text(timedelta(seconds=54.0))
        assert "\n" not in ass_text, f"ASS text contains literal newline: {repr(ass_text)}"
        assert "the" in ass_text
        assert "spell" in ass_text
        assert "we're" in ass_text
        assert "under" in ass_text
```

- [ ] **Step 2: Run test to verify it passes (Word.__post_init__ already strips)**

Run: `cd /Users/andrew/Projects/nomadkaraoke/karaoke-gen-fix-ass-preview-render-divergence && poetry run pytest tests/unit/test_word_text_sanitization.py::TestASSOutputSanitization -v`

Expected: PASS (Word.__post_init__ already strips newlines, so this test passes with current code)

- [ ] **Step 3: Add defensive strip in `_create_ass_text()`**

In `karaoke_gen/lyrics_transcriber/output/ass/lyrics_line.py`, change line 257-258 from:

```python
            # Apply case transformation to the word text
            transformed_text = self._apply_case_transform(word.text)
```

to:

```python
            # Apply case transformation to the word text
            # Defensive strip: Word.__post_init__ should already handle this,
            # but embedded newlines in ASS dialogue events cause silent word
            # loss so we guard against it at the output boundary too.
            clean_word_text = word.text.replace("\n", "").strip()
            transformed_text = self._apply_case_transform(clean_word_text)
```

- [ ] **Step 4: Run all sanitization tests**

Run: `cd /Users/andrew/Projects/nomadkaraoke/karaoke-gen-fix-ass-preview-render-divergence && poetry run pytest tests/unit/test_word_text_sanitization.py -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add karaoke_gen/lyrics_transcriber/output/ass/lyrics_line.py tests/unit/test_word_text_sanitization.py
git commit -m "fix: defensive strip in ASS output as safety net

Belt-and-suspenders guard at the ASS output boundary. Even though
Word.__post_init__ strips newlines, this prevents any future bypass
from producing corrupted ASS dialogue events."
```

---

### Task 3: Refactor render worker to use shared CorrectionResult construction

**Files:**
- Modify: `backend/workers/render_video_worker.py:153-188`

- [ ] **Step 1: Refactor the merge logic**

In `backend/workers/render_video_worker.py`, add the import at the top (after existing lyrics_transcriber imports around line 47):

```python
from karaoke_gen.lyrics_transcriber.correction.operations import CorrectionOperations
```

Then replace the merge logic at lines 164-188. Change from:

```python
                    # 3. Check if there are updated corrections (from review UI)
                    # The frontend sends only partial data: {corrections, corrected_segments}
                    updated_corrections_gcs = f"jobs/{job_id}/lyrics/corrections_updated.json"

                    if storage.file_exists(updated_corrections_gcs):
                        job_log.info("Found updated corrections from review, merging")
                        logger.info(f"Job {job_id}: Found updated corrections, merging")
                        updated_path = os.path.join(temp_dir, "corrections_updated.json")
                        storage.download_file(updated_corrections_gcs, updated_path)

                        with open(updated_path, 'r', encoding='utf-8') as f:
                            updated_data = json.load(f)

                        # Merge: update the original with the user's corrections
                        if 'corrections' in updated_data:
                            original_data['corrections'] = updated_data['corrections']
                        if 'corrected_segments' in updated_data:
                            original_data['corrected_segments'] = updated_data['corrected_segments']

                        job_log.info("Merged user corrections into original data")
                        logger.info(f"Job {job_id}: Merged user corrections into original data")

                    # 4. Convert to CorrectionResult
                    correction_result = CorrectionResult.from_dict(original_data)
                    job_log.info(f"Loaded CorrectionResult with {len(correction_result.corrected_segments)} segments")
                    logger.info(f"Job {job_id}: Loaded CorrectionResult with {len(correction_result.corrected_segments)} segments")
```

to:

```python
                    # 3. Load base CorrectionResult from original data
                    base_result = CorrectionResult.from_dict(original_data)

                    # 4. Apply user corrections if available (from review UI)
                    # Uses the same method as preview generation to ensure
                    # identical CorrectionResult construction (DRY).
                    updated_corrections_gcs = f"jobs/{job_id}/lyrics/corrections_updated.json"

                    if storage.file_exists(updated_corrections_gcs):
                        job_log.info("Found updated corrections from review, applying via shared method")
                        logger.info(f"Job {job_id}: Found updated corrections, applying via shared method")
                        updated_path = os.path.join(temp_dir, "corrections_updated.json")
                        storage.download_file(updated_corrections_gcs, updated_path)

                        with open(updated_path, 'r', encoding='utf-8') as f:
                            updated_data = json.load(f)

                        # Same construction path as preview — prevents divergence
                        correction_result = CorrectionOperations.update_correction_result_with_data(
                            base_result, updated_data
                        )
                        job_log.info("Applied user corrections via CorrectionOperations")
                        logger.info(f"Job {job_id}: Applied user corrections via CorrectionOperations")
                    else:
                        correction_result = base_result

                    job_log.info(f"Loaded CorrectionResult with {len(correction_result.corrected_segments)} segments")
                    logger.info(f"Job {job_id}: Loaded CorrectionResult with {len(correction_result.corrected_segments)} segments")
```

- [ ] **Step 2: Run existing tests to check for regressions**

Run: `cd /Users/andrew/Projects/nomadkaraoke/karaoke-gen-fix-ass-preview-render-divergence && poetry run pytest tests/ -v --timeout=60 -x -q 2>&1 | tail -30`

Expected: All existing tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/workers/render_video_worker.py
git commit -m "refactor: use shared CorrectionResult construction in render worker

Replace manual dict merge + from_dict() with the same
update_correction_result_with_data() method used by preview generation.
This eliminates the code path divergence that caused the preview/render
ASS subtitle discrepancy."
```

---

### Task 4: Clean up redundant `.strip()` in `update_correction_result_with_data()`

**Files:**
- Modify: `karaoke_gen/lyrics_transcriber/correction/operations.py:39-99`

- [ ] **Step 1: Remove redundant `.strip()` from Word text construction only**

In `karaoke_gen/lyrics_transcriber/correction/operations.py`, the `update_correction_result_with_data` method (lines 39-99) has `.strip()` on several text fields. Only the `Word` text strip (line 74) is now redundant thanks to `Word.__post_init__`. The others operate on `WordCorrection` fields or `LyricsSegment` text which don't have `__post_init__` — those must stay.

Change line 74 from:
```python
                            text=w["text"].strip(),
```
to:
```python
                            text=w["text"],
```

**Keep** `.strip()` on lines 47, 48, and 70 — those are `WordCorrection.original_word`, `WordCorrection.corrected_word`, and `LyricsSegment.text` respectively, which are not protected by `Word.__post_init__`.

- [ ] **Step 2: Run all tests**

Run: `cd /Users/andrew/Projects/nomadkaraoke/karaoke-gen-fix-ass-preview-render-divergence && poetry run pytest tests/unit/test_word_text_sanitization.py -v && poetry run pytest tests/ -v --timeout=60 -x -q 2>&1 | tail -30`

Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add karaoke_gen/lyrics_transcriber/correction/operations.py
git commit -m "refactor: remove redundant .strip() from update_correction_result_with_data

Word.__post_init__ now handles text stripping. Removing the redundant
calls makes it clear that sanitization is Word's responsibility, not
the caller's."
```

---

### Task 5: Document lesson learned

**Files:**
- Modify: `docs/LESSONS-LEARNED.md`

- [ ] **Step 1: Add the lesson to the Architecture Decisions section**

In `docs/LESSONS-LEARNED.md`, add a new subsection after the existing "Architecture Decisions" entries (after line ~58). Insert:

```markdown
### Data Types Must Enforce Their Own Invariants (Mar 2026)
When a data type has constraints on its fields (e.g., "word text must not contain newlines"), enforce them in the type's constructor (`__post_init__`), not in callers. This bug was caused by `Word` objects being constructed via two different code paths — one that stripped newlines (preview) and one that didn't (final render). The preview accidentally worked while final renders had corrupted subtitles with silently dropped lyrics. The fix: `Word.__post_init__` strips whitespace so ALL construction paths are safe, plus a defensive strip at the ASS output boundary.

**Key principles:**
- **Single source of truth for data invariants** — the type, not the caller, is responsible for field constraints
- **Defensive output boundaries** — even with clean inputs, validate at system boundaries (ASS file writing) as a safety net
- **Two code paths doing "the same thing" will diverge** — if preview and render both construct CorrectionResult, they must use the same method, not reimplementations

**Detection clue:** If `corrected.txt` shows correct lyrics but the video is missing words, check for embedded newlines in Word text corrupting ASS dialogue events.
```

- [ ] **Step 2: Commit**

```bash
git add docs/LESSONS-LEARNED.md
git commit -m "docs: document data type invariant enforcement lesson

Records the Word text newline bug, the architectural principle it
violated, and detection clues for similar issues."
```

---

### Task 6: Run full test suite and verify

- [ ] **Step 1: Run the full test suite**

Run: `cd /Users/andrew/Projects/nomadkaraoke/karaoke-gen-fix-ass-preview-render-divergence && poetry run pytest tests/ -v --timeout=120 -q 2>&1 | tail -40`

Expected: All tests pass, no regressions

- [ ] **Step 2: Verify the fix would solve the original bug**

Run a quick sanity check that Word objects with the problematic data from job `0d4b550c` are now clean:

```python
cd /Users/andrew/Projects/nomadkaraoke/karaoke-gen-fix-ass-preview-render-divergence && poetry run python -c "
from karaoke_gen.lyrics_transcriber.types import Word
# Simulate the exact data from the buggy job
w1 = Word(id='test', text='spell\n', start_time=54.30, end_time=55.14)
w2 = Word.from_dict({'id': 'test', 'text': 'broken\n\n', 'start_time': 59.98, 'end_time': 61.54})
assert w1.text == 'spell', f'Expected spell, got {repr(w1.text)}'
assert w2.text == 'broken', f'Expected broken, got {repr(w2.text)}'
print('PASS: Word text sanitization works correctly')
"
```

Expected: `PASS: Word text sanitization works correctly`

- [ ] **Step 3: Bump version**

In `pyproject.toml`, bump the patch version (this is a bugfix).

- [ ] **Step 4: Final commit with version bump**

```bash
git add pyproject.toml
git commit -m "chore: bump version for ASS preview/render divergence fix"
```
