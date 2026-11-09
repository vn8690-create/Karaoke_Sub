# Cloud Output Structure Fix

**Date**: 2025-12-30

## Summary

Fixed three issues causing cloud backend (`karaoke-gen-remote`) output to differ from local CLI (`karaoke-gen`) output:

1. **YouTube upload silent failure** - Jobs with `--enable_youtube_upload` weren't uploading
2. **Missing subdirectories** - Dropbox uploads didn't include stems/ and lyrics/ subfolders
3. **Simplified filenames** - Instrumentals named "(Instrumental Clean)" instead of "(Instrumental model_bs_roformer_ep_317_sdr_12.9755.ckpt)"

## Root Causes

### YouTube Upload

The `create-with-upload-urls` endpoint (used by remote CLI) set `youtube_description` but NOT `youtube_description_template`. The video worker checks `youtube_description_template` for YouTube uploads, so they silently failed.

```python
# BEFORE: Only youtube_description was set
job_create = JobCreate(
    youtube_description=body.youtube_description,
    # youtube_description_template NOT set!
)

# AFTER: Both fields set
job_create = JobCreate(
    youtube_description=body.youtube_description,
    youtube_description_template=body.youtube_description,
)
```

### Missing Subdirectories

`dropbox_service.upload_folder()` used `os.listdir()` + `os.path.isfile()`, which skipped directories. Changed to `os.walk()` for recursive upload.

### Simplified Filenames

Video worker hardcoded "Clean" and "Backing" suffixes instead of using actual model names. Fixed by:

1. Storing effective model names in job `state_data` during audio separation
2. Using those names in `_prepare_distribution_directory()` for proper file naming

## Files Modified

| File | Change |
|------|--------|
| `backend/api/routes/file_upload.py` | Set `youtube_description_template` |
| `backend/services/dropbox_service.py` | Recursive `upload_folder()` |
| `backend/workers/audio_worker.py` | Store model names in state_data |
| `backend/workers/video_worker.py` | Add `_prepare_distribution_directory()` |
| `backend/tests/test_dropbox_service.py` | Tests for recursive upload |
| `backend/tests/test_workers.py` | Tests for model names and distribution |

## Expected Output Structure

After this fix, cloud jobs produce identical output to local CLI:

```text
NOMAD-XXXX - Artist - Title/
├── Artist - Title (Final Karaoke Lossless 4k).mp4
├── Artist - Title (Final Karaoke Lossless 4k).mkv
├── Artist - Title (Instrumental model_bs_roformer_ep_317_sdr_12.9755.ckpt).flac
├── Artist - Title (Instrumental +BV mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt).flac
├── stems/
│   ├── Artist - Title (Instrumental model_bs_roformer_...).flac
│   ├── Artist - Title (Vocals model_bs_roformer_...).flac
│   ├── Artist - Title (Lead Vocals mel_band_roformer_...).flac
│   └── ... (all stems with model names)
└── lyrics/
    └── (intermediate lyrics files)
```

## Testing

- All 803 existing tests pass
- Added new tests for recursive upload and distribution directory preparation
