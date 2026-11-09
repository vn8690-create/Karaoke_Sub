# Countdown Padding Implementation - Summary

## Overview

Successfully integrated countdown padding support from the `lyrics-transcriber` library into the karaoke-gen codebase. This ensures that when vocals are padded with a countdown (for songs that start too quickly), all instrumental audio files are automatically synchronized with the same padding.

## Changes Implemented

### 1. LyricsProcessor (`karaoke_gen/lyrics_processor.py`)

**Changes Made:**
- Modified `transcribe_lyrics()` method to capture countdown padding information from `LyricsControllerResult`
- Added three new fields to the return dictionary:
  - `countdown_padding_added` (bool): Whether padding was applied
  - `countdown_padding_seconds` (float): Amount of padding (typically 3.0 seconds)
  - `padded_audio_filepath` (str): Path to the padded vocal audio file

**Implementation Details:**
```python
# Lines 289-298
transcriber_outputs["countdown_padding_added"] = getattr(results, "countdown_padding_added", False)
transcriber_outputs["countdown_padding_seconds"] = getattr(results, "countdown_padding_seconds", 0.0)
transcriber_outputs["padded_audio_filepath"] = getattr(results, "padded_audio_filepath", None)

if transcriber_outputs["countdown_padding_added"]:
    self.logger.info(
        f"Countdown padding detected: {transcriber_outputs['countdown_padding_seconds']}s added to vocals. "
        f"Instrumental audio will need to be padded accordingly."
    )
```

**Why getattr():** Uses `getattr()` with defaults to maintain backward compatibility with older versions of lyrics-transcriber that don't have these fields.

### 2. AudioProcessor (`karaoke_gen/audio_processor.py`)

**New Methods Added:**

#### `pad_audio_file(input_audio, output_audio, padding_seconds)`
- **Purpose:** Pads an audio file with silence at the start using ffmpeg
- **Implementation:** Uses the exact same ffmpeg approach as lyrics-transcriber
- **Error Handling:** Handles subprocess errors and timeouts gracefully
- **Lines:** 55-107

**Key Features:**
- Uses `anullsrc` to generate silence
- Uses `concat` filter to prepend silence to audio
- Preserves audio quality with lossless format
- 5-minute timeout for safety
- Comprehensive error logging

#### `apply_countdown_padding_to_instrumentals(separation_result, padding_seconds, artist_title, track_output_dir)`
- **Purpose:** Applies padding to all instrumental files in a separation result
- **Implementation:** Pads clean instrumental and all combined instrumentals
- **Lines:** 775-838

**What Gets Padded:**
1. Clean instrumental track
2. All combined instrumentals (instrumental + backing vocals for each model)

**What Doesn't Get Padded:**
- Backing vocals (not used in final output)
- Other stems (drums, bass, etc. - not used in final output)
- Vocal tracks (already padded by lyrics-transcriber)

**Naming Convention:**
- Padded files are named with "(Padded)" inserted before the file extension
- Example: `Artist - Song (Instrumental model.ckpt).flac` → `Artist - Song (Instrumental model.ckpt) (Padded).flac`

### 3. KaraokeGen (`karaoke_gen/karaoke_gen.py`)

**Changes Made:**

#### Transcription Result Handling (Lines 487-499)
- Captures countdown padding information from transcription results
- Stores padding info in `processed_track` dictionary
- Logs clear warning when countdown padding is detected

#### Skip Lyrics Edge Case (Lines 395-398)
- Initializes padding fields to False/0.0 when lyrics are skipped
- Prevents errors in downstream code

#### Existing Instrumental Handling (Lines 604-619)
- When a custom instrumental is provided AND countdown padding was detected:
  - Pads the custom instrumental with the same padding_seconds
  - Updates the path to use the padded version
  - Ensures synchronization with vocals

#### Post-Separation Padding (Lines 614-637)
- After audio separation completes, checks if countdown padding was added
- If padding was detected:
  - Calls `apply_countdown_padding_to_instrumentals()`
  - Updates `processed_track["separated_audio"]` with padded file paths
  - Ensures all downstream code uses the padded files

## Testing

### Test Coverage
Created comprehensive unit tests in `tests/unit/test_countdown_padding.py`:

**13 tests total, all passing:**

1. **TestPadAudioFile** (3 tests)
   - `test_pad_audio_file_success`: Verifies ffmpeg is called correctly
   - `test_pad_audio_file_failure`: Tests error handling
   - `test_pad_audio_file_timeout`: Tests timeout handling

2. **TestApplyCountdownPaddingToInstrumentals** (4 tests)
   - `test_apply_padding_to_clean_instrumental`: Verifies clean instrumental padding
   - `test_apply_padding_to_combined_instrumentals`: Verifies all combined instrumentals are padded
   - `test_skip_padding_if_file_exists`: Verifies idempotency (skips if already padded)
   - `test_preserve_structure_with_empty_separation`: Tests edge case with no files

3. **TestLyricsProcessorIntegration** (2 tests)
   - `test_lyrics_processor_captures_padding_info`: Verifies padding info capture
   - `test_lyrics_processor_handles_no_padding`: Tests backward compatibility

4. **TestKaraokeGenIntegration** (3 tests)
   - `test_karaoke_gen_applies_padding_when_detected`: End-to-end padding application
   - `test_karaoke_gen_skips_padding_when_not_needed`: Verifies no unnecessary padding
   - `test_skip_lyrics_initializes_padding_fields`: Tests edge case

5. **TestExistingInstrumentalPadding** (1 test)
   - `test_custom_instrumental_padding_logic`: Tests custom instrumental padding

### Running Tests
```bash
cd /Users/andrew/Projects/karaoke-gen
python -m pytest tests/unit/test_countdown_padding.py -v
```

## Workflow

### Normal Flow (No Countdown Padding)
1. Transcribe lyrics → No padding detected
2. Separate audio → Original instrumental files created
3. Use original files in final output

### With Countdown Padding
1. Transcribe lyrics → Countdown padding detected (3 seconds added to vocals)
2. Separate audio → Original instrumental files created
3. **Apply padding** → Create padded versions of all instrumentals
4. Update file paths → Point to padded versions
5. Use padded files in final output → Everything stays synchronized

### Edge Cases Handled
1. **Lyrics Skipped:** Padding fields initialized to False/0.0
2. **Custom Instrumental:** Padded along with vocals
3. **Files Already Exist:** Skips re-padding (idempotent)
4. **Backward Compatibility:** Works with old lyrics-transcriber versions

## File Naming

### Before Padding
```
Artist - Song (Instrumental model.ckpt).flac
Artist - Song (Instrumental +BV model.ckpt).flac
```

### After Padding
```
Artist - Song (Instrumental model.ckpt) (Padded).flac
Artist - Song (Instrumental +BV model.ckpt) (Padded).flac
```

**Original files are preserved** - padded versions are created as new files.

## Benefits

1. **Automatic Synchronization:** No manual intervention needed
2. **Audio Quality Preservation:** Uses lossless formats throughout
3. **Comprehensive:** Pads all instrumental variants
4. **Idempotent:** Safe to run multiple times
5. **Backward Compatible:** Works with old lyrics-transcriber versions
6. **Well Tested:** 13 comprehensive unit tests
7. **Well Logged:** Clear logging at every step

## Integration with Downstream Tools

### KaraokeFinalise
The `remux_with_instrumental()` method in `karaoke_finalise.py` will automatically use the padded instrumental files when they exist, since the paths in `processed_track["separated_audio"]` are updated to point to the padded versions.

### Manual Usage
Users can also manually select the padded instrumental files (identifiable by "(Padded)" in the filename) when creating final videos.

## Troubleshooting

### Issue: Countdown in video but instrumental out of sync
**Solution:** Verify that padded instrumental files were created. Check logs for:
```
=== COUNTDOWN PADDING DETECTED ===
Applying Xs padding to all instrumental files
```

### Issue: Padding applied when it shouldn't be
**Solution:** Check that `countdown_padding_added` is being set correctly by lyrics-transcriber. This is a boolean flag that should only be True when vocals actually start within 3 seconds.

### Issue: Padded files not being used
**Solution:** Verify that the `processed_track["separated_audio"]` dictionary contains paths with "(Padded)" in them after the padding step runs.

## Code Quality

### SOLID Principles Applied

1. **Single Responsibility Principle (SRP)**
   - `pad_audio_file()`: Only handles audio padding
   - `apply_countdown_padding_to_instrumentals()`: Only orchestrates padding application
   - Each method has a clear, single purpose

2. **Open/Closed Principle (OCP)**
   - New functionality added without modifying existing separation logic
   - Padding is applied as a post-processing step
   - Existing code works unchanged if padding is not needed

3. **Liskov Substitution Principle (LSP)**
   - Padded audio files are drop-in replacements for original files
   - Same format, same structure, just with added silence at start

4. **Interface Segregation Principle (ISP)**
   - Each method has a focused interface with only necessary parameters
   - Callers don't need to know about internal padding implementation

5. **Dependency Inversion Principle (DIP)**
   - Uses ffmpeg abstraction (subprocess) rather than direct file manipulation
   - AudioProcessor methods can be mocked/stubbed for testing

### Best Practices

- **Error Handling:** Comprehensive try/catch blocks with clear error messages
- **Logging:** Detailed logging at INFO level for user visibility
- **Type Safety:** Clear parameter types in docstrings
- **Idempotency:** Safe to run multiple times (checks for existing files)
- **Testability:** All methods are easily testable with mocks
- **Documentation:** Clear docstrings explaining purpose and behavior

## Future Enhancements (Optional)

1. **Configurable Padding Amount:** Allow users to specify padding amount
2. **Padding Other Stems:** Option to pad backing vocals, drums, bass, etc.
3. **Padding Verification:** Automated check that padded files have correct duration
4. **Padding Metadata:** Store padding info in a metadata file for reference

## References

- Implementation guide: `COUNTDOWN_INTEGRATION_EXAMPLE.md`
- Test file: `tests/unit/test_countdown_padding.py`
- Modified files:
  - `karaoke_gen/lyrics_processor.py`
  - `karaoke_gen/audio_processor.py`
  - `karaoke_gen/karaoke_gen.py`

