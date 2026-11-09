---
name: Anchor Sequence Optimization
overview: Replace the current multiprocessing-based anchor sequence algorithm with an efficient single-threaded implementation using hash-based n-gram indexing, greedy longest-first matching, and simplified scoring to achieve sub-30-second performance in both local and cloud environments.
todos:
  - id: create-golden-fixtures
    content: Create script to generate 10 golden test fixtures from representative song data (varying lengths/complexity), run current algorithm to capture expected anchor outputs
    status: completed
  - id: create-golden-test
    content: Create test_anchor_sequence_golden.py with regression tests that verify anchor finder output matches fixtures, ensure tests pass with current implementation before any changes
    status: completed
  - id: remove-multiprocessing
    content: Remove multiprocessing.Pool from find_anchors() and _remove_overlapping_sequences(), replace with single-threaded loops
    status: completed
  - id: build-ngram-index
    content: Add _build_ngram_index() method to create hash-based lookup table for O(1) n-gram matching
    status: completed
  - id: greedy-skip
    content: Add covered_positions set tracking and skip logic to avoid processing overlapping n-grams
    status: completed
  - id: simple-scoring
    content: Add _simple_score_anchor() with rule-based heuristics, make spaCy scoring optional via use_nlp_scoring flag
    status: completed
  - id: optimize-overlap
    content: Replace O(n^2) overlap removal with O(n log n) sorted single-pass algorithm
    status: completed
  - id: add-perf-tests
    content: Add performance benchmark test asserting <30 second completion for all fixture sizes
    status: pending
---

# Anchor Sequence Algorithm Optimization

## Problem Analysis

The current `AnchorSequenceFinder` has critical performance issues:

### Root Causes of Hanging

1. **Multiprocessing Pool with fork()**: Python's `Pool()` uses `fork()` on Linux, which causes deadlocks in Cloud Run containers
2. **spaCy model loading in forked processes**: The `PhraseAnalyzer` loads spaCy's `en_core_web_sm` model, which can hang when forked
3. **Pool creation blocking**: The hang occurs before job submission, so timeout checks never trigger

### Algorithmic Inefficiencies

1. **O(n^2) n-gram matching**: Linear search through references for each n-gram
2. **Redundant work**: Processes all n-gram lengths (3 to ~30) even though longer matches are preferred
3. **O(n^2) overlap removal**: Each anchor checked against all previous anchors
4. **Expensive phrase scoring**: spaCy NLP called twice per anchor (phrase + context)

## Proposed Solution: Hash-Based Greedy Algorithm

### Core Algorithm Changes

**1. Hash-Based N-gram Index (O(1) lookup instead of O(n))**

- Pre-build a dictionary mapping n-grams to their positions in each reference
- Use tuple of cleaned words as key for O(1) lookup
- Build index once during preprocessing

**2. Greedy Longest-First Matching**

- Process n-gram lengths from longest to shortest (current behavior)
- BUT: Skip positions already covered by longer anchors immediately
- Use a "covered positions" set to avoid redundant work

**3. Single-Threaded Processing**

- Remove all `multiprocessing.Pool` usage
- Use efficient algorithms instead of parallelism
- Works identically in local and cloud environments

**4. Simplified Phrase Scoring (Optional)**

- Make spaCy-based scoring optional via configuration flag
- Default to rule-based heuristic scoring:
                                                                                                                                                                                                                                                                - Prefer sequences starting/ending at word boundaries
                                                                                                                                                                                                                                                                - Prefer sequences matching more reference sources
                                                                                                                                                                                                                                                                - Prefer longer sequences
- Option to enable full NLP scoring for higher-quality results offline

**5. O(n log n) Overlap Removal**

- Sort anchors by position
- Single pass with interval tracking using sorted list
- Skip anchors that overlap with any already-selected anchor

### New Data Structures

```python
# N-gram index: maps (word1, word2, ...) -> {source: [positions]}
ngram_index: Dict[Tuple[str, ...], Dict[str, List[int]]]

# Covered positions in transcription (for greedy skip)
covered_trans_positions: Set[int]
```

### Performance Targets

- **Target**: Complete in under 30 seconds for any song
- **Typical song**: 200-400 words, 3 reference sources
- **Expected performance**: 1-5 seconds for typical inputs

## Implementation Plan

### Execution Order (Critical)

1. **Phase 0**: Create golden test fixtures and verify tests pass with current code
2. **Phase 1-5**: Implement optimizations incrementally, running golden tests after each phase
3. **Final**: Add performance benchmarks

### Files to Create/Modify

- `lyrics_transcriber_temp/scripts/generate_anchor_fixtures.py` (new)
- `lyrics_transcriber_temp/tests/fixtures/anchor_golden/*.json` (new)
- `lyrics_transcriber_temp/tests/unit/correction/test_anchor_sequence_golden.py` (new)
- `lyrics_transcriber_temp/lyrics_transcriber/correction/anchor_sequence.py` (modify)

### Key Changes

**Phase 0: Golden Test Setup** (MUST complete and pass before any algorithm changes)

- Create fixture generation script with 10 representative test cases
- Run script to generate fixtures using current implementation
- Create golden test file that loads fixtures and verifies outputs
- Verify all golden tests pass with current code

**Phase 1: Remove Multiprocessing**

- Replace `Pool().apply_async()` with direct function calls
- Remove all pool creation, cleanup, and timeout handling
- Single-threaded loop through n-gram lengths

**Phase 2: Add Hash-Based Index**

- New method `_build_ngram_index()` that builds lookup table during preprocessing
- Modify `_find_matching_sources()` to use O(1) index lookup
- Index built once, shared across all n-gram length iterations

**Phase 3: Greedy Position Skipping**

- Track covered transcription positions in a set
- Skip n-grams that start in already-covered positions
- Reduces redundant work significantly for songs with good matches

**Phase 4: Simplify Scoring**

- Add `use_nlp_scoring: bool = False` parameter to constructor
- New method `_simple_score_anchor()` using rule-based heuristics
- Keep spaCy scoring available for offline/high-quality mode

**Phase 5: Optimize Overlap Removal**

- Sort anchors by (start_position, -length) 
- Single pass: keep anchor if no overlap with last kept anchor
- O(n log n) total instead of O(n^2)

## API Compatibility

The public interface remains unchanged:

- `find_anchors(transcribed, references, transcription_result) -> List[ScoredAnchor]`
- `find_gaps(transcribed, anchors, references, transcription_result) -> List[GapSequence]`

New optional constructor parameters:

- `use_nlp_scoring: bool = False` - Enable spaCy-based phrase scoring (slower but higher quality)
- Timeout parameter retained but less critical with efficient algorithm

## Fallback Strategy

If performance is still insufficient for edge cases:

1. **Early termination**: Stop after finding sufficient coverage (e.g., 80% of words anchored)
2. **Adaptive n-gram range**: Start with medium lengths (8-15), expand only if needed
3. **Sampling**: For very long songs, sample n-gram positions instead of exhaustive search

## Phase 0: Golden Test Setup (BEFORE any algorithm changes)

### Goal

Create regression tests using REAL song data from local cache to verify the optimized algorithm produces equivalent results.

### Cache File Structure (Understanding)

The local cache at `~/lyrics-transcriber-cache/` contains:

- **Reference lyrics**: `{provider}_{hash}_converted.json` where provider is spotify/genius/lrclib/musixmatch
                                - Hash is based on (artist, title) lookup - same song shares same hash across providers
                                - `_raw.json` contains metadata (track name, artist)
                                - `_converted.json` contains LyricsData structure with segments/words
- **Transcriptions**: `audioshake_{hash}_converted.json`
                                - Hash is based on audio file content (different from reference hash)
                                - Contains TranscriptionData structure
- **Anchor results**: `anchors_{hash}.json`
                                - Hash is computed from combined inputs (transcription + all references)

### Manual Song Selection

Identify 10 songs from cache with good coverage. Search raw files for track names:

### Finding Song Mappings

To link audioshake transcriptions to reference lyrics, search cache files:

```bash
# Find songs by searching raw files for track names
grep -h "trackName" ~/lyrics-transcriber-cache/spotify_*_raw.json | head -20

# Find audioshake files for a known song (e.g., search for filename patterns)
ls ~/lyrics-transcriber-cache/audioshake_*_raw.json | head -20

# Search converted files for specific lyrics text
grep -l "Napoleon did surrender" ~/lyrics-transcriber-cache/*_converted.json
```

**Target song list** (reference_hash to be paired with audioshake_hash):

1. ABBA - Waterloo (refs: 3365f6a1e42388d84bcbfc0ac6f8aa6c) - short, repetitive chorus
2. The Format - Time Bomb (refs: 3a3802ec28c4ab6689909b7ef784bb6f) - medium length
3. Rancid - Time Bomb (refs: d02d20b854cbc6b890f274bd6c278752) - fast punk lyrics
4. Minutemen - Storm in My House (refs: bc625704b26b307d8680ae5235b74994) - short
5. + 6 more songs to be identified during fixture generation by exploring cache

### Fixture Generation Script

Create `lyrics_transcriber_temp/scripts/generate_anchor_fixtures.py`:

```python
# Input: List of (name, audioshake_hash, reference_hash) tuples
# For each:
#   1. Load audioshake_{hash}_converted.json as transcription
#   2. Load {spotify,genius,lrclib}_{hash}_converted.json as references  
#   3. Run current AnchorSequenceFinder
#   4. Save complete fixture with inputs + outputs
```

The script will:

1. Accept a config file listing the 10 song mappings
2. Load real LyricsData from cache files
3. Run the CURRENT AnchorSequenceFinder implementation
4. Save fixtures that capture the real behavior

### Fixture Format

```
lyrics_transcriber_temp/tests/fixtures/anchor_golden/
  - waterloo_abba.json
  - time_bomb_format.json
  - time_bomb_rancid.json
  - ...
```

Each fixture contains REAL data:

```json
{
  "name": "waterloo_abba",
  "description": "ABBA - Waterloo, short song with repetitive chorus",
  "source_hashes": {
    "audioshake": "1654b7c0755fad7f23bc888308f274de",
    "references": "3365f6a1e42388d84bcbfc0ac6f8aa6c"
  },
  "transcription": {
    "segments": [...],  // Full LyricsData from audioshake cache
    "word_count": 150
  },
  "references": {
    "spotify": { "segments": [...] },
    "genius": { "segments": [...] },
    "lrclib": { "segments": [...] }
  },
  "expected_anchors": [
    {
      "text": "My my at Waterloo Napoleon did surrender",
      "transcription_position": 0,
      "length": 7,
      "reference_positions": {"spotify": 0, "genius": 0, "lrclib": 0},
      "confidence": 1.0
    },
    // ... all anchors from current implementation
  ],
  "expected_anchor_count": 25,
  "expected_word_coverage": 142,
  "expected_coverage_percent": 94.6
}
```

### Golden Test

Create `lyrics_transcriber_temp/tests/unit/correction/test_anchor_sequence_golden.py`:

```python
import pytest
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "anchor_golden"

@pytest.fixture(params=list(FIXTURES_DIR.glob("*.json")))
def golden_fixture(request):
    with open(request.param) as f:
        return json.load(f)

def test_anchor_count_matches(golden_fixture, anchor_finder):
    """Anchor count should be within 10% of expected."""
    anchors = run_anchor_finder(golden_fixture)
    expected = golden_fixture["expected_anchor_count"]
    assert abs(len(anchors) - expected) <= expected * 0.1

def test_key_anchors_match(golden_fixture, anchor_finder):
    """First, last, and longest anchors should match exactly."""
    anchors = run_anchor_finder(golden_fixture)
    expected = golden_fixture["expected_anchors"]
    # Compare first anchor
    assert anchors[0].text == expected[0]["text"]
    # Compare positions match
    ...

def test_word_coverage(golden_fixture, anchor_finder):
    """Total word coverage should be within 5% of expected."""
    anchors = run_anchor_finder(golden_fixture)
    coverage = calculate_coverage(anchors, golden_fixture)
    expected = golden_fixture["expected_coverage_percent"]
    assert abs(coverage - expected) <= 5.0

def test_no_invalid_positions(golden_fixture, anchor_finder):
    """All anchor positions should be valid."""
    anchors = run_anchor_finder(golden_fixture)
    word_count = golden_fixture["transcription"]["word_count"]
    for anchor in anchors:
        assert 0 <= anchor.transcription_position < word_count
```

### Validation Steps

1. **Generate fixtures from current implementation**:
```bash
cd lyrics_transcriber_temp
python scripts/generate_anchor_fixtures.py
```

2. **Verify fixtures were created**:
```bash
ls tests/fixtures/anchor_golden/
# Should show 10 .json files
```

3. **Run golden tests with CURRENT implementation**:
```bash
pytest tests/unit/correction/test_anchor_sequence_golden.py -v
```

4. **All tests MUST pass before any algorithm changes**

5. **After each optimization phase, re-run golden tests**:
```bash
pytest tests/unit/correction/test_anchor_sequence_golden.py -v
# Must still pass!
```


## Testing (Post-Optimization)

- Golden tests verify correctness (same outputs as before)
- Existing unit tests verify API compatibility
- Performance benchmark test with 30-second timeout assertion
- Test with various song lengths via golden fixtures