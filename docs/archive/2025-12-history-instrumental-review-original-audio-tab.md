# Instrumental Review: Original Audio Tab Support

**Date:** 2025-12-22  
**Version:** 0.75.12

## Summary

Added support for an "Original Audio" tab in the Instrumental Review UI, allowing users to compare the original audio (with lead vocals) alongside the backing vocals, clean instrumental, and instrumental with backing vocals options. This helps users make better decisions about whether certain audio regions are actually backing vocals or need to be muted.

## Problem

When reviewing backing vocals in the Instrumental Review UI, users couldn't hear the original full song to compare and determine whether detected regions were actually backing vocals or if they needed to be muted. This made it difficult to make informed decisions about the instrumental selection.

## Solution

The Instrumental Review HTML UI already had built-in support for displaying an "Original Audio" tab when `hasOriginal` flag was set, but this feature was not being activated because the `original_audio_path` parameter was not being passed to the `InstrumentalReviewServer`.

### Changes Made

1. **`karaoke_gen/utils/gen_cli.py`** (lines 203-217, 239):
   - Added code to locate the original audio file from the track data (`track.get("input_audio_wav")`)
   - Resolved the path relative to the track directory
   - Passed `original_audio_path` parameter when initializing `InstrumentalReviewServer`

2. **`scripts/test-instrumental-review.py`**:
   - Added optional `--original` command-line argument
   - Added validation for the original audio file path
   - Passed `original_audio_path` parameter to `InstrumentalReviewServer`

3. **`tests/unit/test_instrumental_review/test_server.py`**:
   - Added `test_server_initialization_with_original_audio()` to verify server properly stores the original audio path
   - Added `test_get_analysis_with_original_audio()` to verify the API properly exposes `has_original` flag and original audio URL

4. **`pyproject.toml`**:
   - Bumped version from 0.75.11 to 0.75.12

## How It Works

### Backend Flow

1. When the instrumental review is triggered, the system:
   - Locates the original audio file (`input_audio_wav` from the track data)
   - Resolves the path relative to the working directory
   - Passes it to `InstrumentalReviewServer` as `original_audio_path`

2. The server exposes the original audio through:
   - `/api/audio/original` endpoint (serves the audio file)
   - `has_original: true` flag in the analysis response

### Frontend Flow

The HTML UI (already implemented in `karaoke_gen/instrumental_review/static/index.html`):
- Checks `hasOriginal` flag from the API
- Conditionally shows "Original" tab in the audio toggle group (line 697-699)
- Provides audio player that switches between:
  - **Original Audio** - Full song with lead vocals
  - **Backing Vocals Only** - Isolated backing vocals
  - **Pure Instrumental** - Clean instrumental (no vocals)
  - **Instrumental + Backing** - Instrumental with backing vocals included
  - **Custom** - User-created muted regions

### Usage

When running the local CLI:
```bash
karaoke-gen "Artist" "Song Title"
```

During the instrumental review phase, the UI will now automatically show the "Original Audio" tab if the original audio file is available.

For testing:
```bash
python scripts/test-instrumental-review.py \
  backing_vocals.flac \
  clean_instrumental.flac \
  --with_backing instrumental_with_backing.flac \
  --original original.wav
```

## Files Modified

- `karaoke_gen/utils/gen_cli.py` - Added original audio path detection and passing
- `scripts/test-instrumental-review.py` - Added --original argument support
- `tests/unit/test_instrumental_review/test_server.py` - Added tests for original audio functionality
- `pyproject.toml` - Version bump

## Testing

All 139 tests in `tests/unit/test_instrumental_review/` pass, including:
- `TestServerInitialization::test_server_initialization_with_original_audio` - Verifies server stores original audio path
- `TestServerAPIEndpoints::test_get_analysis_with_original_audio` - Verifies API exposes original audio properly

## Benefits

1. **Better Decision Making**: Users can hear the full original song to compare against backing vocals
2. **Improved Accuracy**: Easier to identify if detected regions are truly backing vocals or artifacts
3. **No UI Changes Required**: Leveraged existing UI capabilities that were already built-in
4. **Backward Compatible**: If no original audio is provided, the tab simply doesn't appear

## Implementation Notes

- The original audio feature is optional - if the file is not available, the tab won't appear
- The server already had the route handler for serving original audio (`/api/audio/original`)
- The HTML UI already had the conditional rendering logic for the "Original" tab
- The main change was ensuring the `original_audio_path` parameter was properly populated and passed through

