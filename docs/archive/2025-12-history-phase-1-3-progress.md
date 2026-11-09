# Phase 1.3: Video Generation & Finalization - Progress Tracker

**Phase:** 1.3 - Video Generation & Finalization  
**Started:** 2025-12-01  
**Status:** 🚧 IN PROGRESS (~60% complete)

---

## Overview

Phase 1.3 focuses on implementing the final video generation stage, including:
1. Video remuxing with selected instrumental
2. Concatenation with title/end screens
3. Multi-format encoding (4K lossless, 4K lossy, 720p)
4. CDG/TXT package generation
5. Integration with KaraokeFinalise

---

## Progress Checklist

### ✅ Completed

- [x] **Video worker structure** (`backend/workers/video_worker.py`)
  - Complete async workflow
  - Prerequisites validation
  - Asset downloading
  - State transitions
  - Error handling
  - Cleanup

- [x] **KaraokeFinalise integration**
  - Instance creation with server-side mode
  - Video remuxing with instrumental
  - Concatenation + encoding in one step
  - CDG package generation
  - TXT package generation

- [x] **Internal API endpoint** (`/internal/workers/video`)
  - POST endpoint for triggering
  - Background task execution
  - Response model

- [x] **Job model updates**
  - `INSTRUMENTAL_SELECTED` → `GENERATING_VIDEO` transition
  - `GENERATING_VIDEO` → `ENCODING` transition
  - `ENCODING` → `PACKAGING` transition
  - `PACKAGING` → `COMPLETE` transition

- [x] **Worker service integration**
  - `trigger_video_worker()` method
  - HTTP-based triggering

### 🚧 In Progress

- [ ] **Testing with real audio files**
  - End-to-end workflow test
  - Verify all formats encode correctly
  - Check CDG/TXT packages
  - Validate file uploads to GCS

### ⏭️ Remaining

- [ ] **Cloud Build integration** (Optional optimization)
  - Parallel format encoding
  - Faster processing (5-10 min vs 15-20 min)
  - Cost-effective for high volume

- [ ] **Countdown padding application**
  - Detect if vocals have countdown
  - Apply matching padding to instrumentals
  - Re-upload padded versions

- [ ] **Progress percentage refinement**
  - More granular progress updates during encoding
  - Estimated time remaining

- [ ] **Error recovery**
  - Retry logic for transient failures
  - Checkpoint/resume support

---

## Implementation Details

### Video Worker (`backend/workers/video_worker.py`)

**File:** 470 lines of production code

**Key Functions:**

1. `generate_video(job_id)` - Main entry point
   - Downloads all assets from GCS
   - Creates KaraokeFinalise instance
   - Orchestrates remux, concatenation, encoding
   - Uploads results to GCS
   - Updates job state

2. `_validate_prerequisites(job)` - Ensures ready for video generation
   - Instrumental selected
   - Screens generated
   - Lyrics video exists
   - All required assets available

3. `_download_assets(job_id, job, temp_dir, storage)` - Downloads from GCS
   - Lyrics video (with_vocals.mkv)
   - Selected instrumental (clean or with_backing)
   - Title screen (title.mov)
   - End screen (end.mov)
   - LRC file (if available)

4. `_create_finalise_instance(job, temp_dir)` - Creates KaraokeFinalise
   - Server-side mode enabled
   - Non-interactive mode
   - CDG/TXT configuration

5. `_remux_video_with_instrumental(...)` - Remuxes video with audio
   - Uses `KaraokeFinalise.remux_with_instrumental()`
   - Replaces original audio with instrumental
   - Outputs karaoke.mp4

6. `_concatenate_with_screens(...)` - Concatenates and encodes
   - Uses `KaraokeFinalise.remux_and_encode_output_video_files()`
   - Concatenates: Title (5s) + Karaoke + End (5s)
   - Encodes to all 4 formats in one pass:
     * Lossless 4K MP4 (H.264 + PCM audio)
     * Lossless 4K MKV (H.264 + FLAC audio)
     * Lossy 4K MP4 (H.264 + AAC audio)
     * Lossy 720p MP4 (H.264 720p + AAC audio)

7. `_upload_videos(...)` - Uploads encoded videos to GCS
   - Uploads all 4 formats
   - Updates job.file_urls
   - Signed URLs for download

8. `_generate_packages(...)` - Generates CDG/TXT packages
   - Uses `KaraokeFinalise.create_cdg_zip_file()`
   - Uses `KaraokeFinalise.create_txt_zip_file()`
   - Requires LRC file
   - Optional based on job settings

9. `_upload_packages(...)` - Uploads packages to GCS
   - CDG ZIP (CDG + MP3)
   - TXT ZIP (TXT + MP3)

**State Transitions:**

```
INSTRUMENTAL_SELECTED
    ↓ (user selects instrumental)
GENERATING_VIDEO (progress: 70%)
    ↓ (remux + concatenate + encode)
ENCODING (progress: 75%)
    ↓ (formats complete)
PACKAGING (progress: 95%) [if CDG/TXT enabled]
    ↓ (packages complete)
COMPLETE (progress: 100%)
```

**Processing Time:**

- Remux: ~1 minute
- Concatenate + Encode: ~15-20 minutes (locally)
  - Lossless 4K MP4: ~5 min
  - Lossless 4K MKV: ~4 min
  - Lossy 4K MP4: ~5 min
  - Lossy 720p MP4: ~3 min
- CDG/TXT: ~1 minute
- **Total: ~20 minutes**

**Optimizations for Production:**

- Cloud Build: Parallel encoding (5-10 min total)
- Hardware acceleration: NVENC GPU encoding
- Caching: Reuse encoded formats if unchanged

---

## Integration with KaraokeFinalise

The video worker leverages the existing `karaoke_gen.karaoke_finalise.KaraokeFinalise` class, which is battle-tested from the CLI tool.

**Key Methods Used:**

1. `remux_with_instrumental(with_vocals_file, instrumental_audio, output_file)`
   - Remuxes video with instrumental audio
   - Uses ffmpeg with PCM audio codec

2. `remux_and_encode_output_video_files(with_vocals_file, input_files, output_files)`
   - Orchestrates entire finalization pipeline
   - Concatenates title + karaoke + end
   - Encodes to all 4 formats sequentially
   - Handles hardware acceleration detection

3. `create_cdg_zip_file(input_files, output_files, artist, title)`
   - Generates CDG from LRC using CDGGenerator
   - Converts FLAC to MP3
   - Creates ZIP package

4. `create_txt_zip_file(input_files, output_files)`
   - Converts LRC to TXT format
   - Packages with MP3
   - Creates ZIP package

**Configuration:**

```python
finalise = KaraokeFinalise(
    logger=logger,
    log_level=logging.INFO,
    dry_run=False,
    instrumental_format="flac",
    enable_cdg=job.enable_cdg,
    enable_txt=job.enable_txt,
    non_interactive=True,      # No user prompts
    server_side_mode=True,     # Cloud optimizations
)
```

**Benefits:**

- ✅ Zero code duplication
- ✅ Battle-tested logic
- ✅ Hardware acceleration support
- ✅ Comprehensive error handling
- ✅ One codebase for CLI + web

---

## File Structure

```
backend/workers/video_worker.py          470 lines
backend/api/routes/internal.py           +28 lines (video endpoint)
backend/models/job.py                    (state machine already complete)
backend/services/worker_service.py       (trigger_video_worker already added)
```

**Total New Code:** ~500 lines

---

## Testing Plan

### Manual Testing

1. **Submit a test job:**
   ```bash
   curl -X POST http://localhost:8080/api/jobs \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://youtube.com/watch?v=...",
       "artist": "ABBA",
       "title": "Waterloo"
     }'
   ```

2. **Wait for AWAITING_INSTRUMENTAL_SELECTION:**
   ```bash
   curl http://localhost:8080/api/jobs/{job_id}
   ```

3. **Select instrumental:**
   ```bash
   curl -X POST http://localhost:8080/api/jobs/{job_id}/select-instrumental \
     -H "Content-Type: application/json" \
     -d '{"selection": "clean"}'
   ```

4. **Monitor encoding progress:**
   ```bash
   watch -n 5 'curl -s http://localhost:8080/api/jobs/{job_id} | jq .status,.progress'
   ```

5. **Download final videos:**
   ```bash
   # Get signed URLs from job.file_urls.finals
   curl http://localhost:8080/api/jobs/{job_id} | jq '.file_urls.finals'
   ```

### Automated Testing

TODO: Create integration tests

- Mock GCS download/upload
- Test state transitions
- Verify error handling
- Check file existence

---

## Known Issues

1. **Encoding time:** 15-20 minutes is slow for user experience
   - **Solution:** Implement Cloud Build for parallel encoding

2. **No progress granularity:** Just "encoding" status for 20 minutes
   - **Solution:** Add per-format progress updates

3. **No retry logic:** Transient failures fail entire job
   - **Solution:** Implement checkpoint/resume

4. **CDG requires LRC:** No LRC = no CDG
   - **Solution:** Ensure LRC is always generated in lyrics worker

---

## Next Steps

1. **End-to-end testing** (HIGH PRIORITY)
   - Test with real audio file
   - Verify all formats encode
   - Check CDG/TXT packages
   - Validate GCS uploads

2. **Cloud Build integration** (MEDIUM PRIORITY)
   - Define build configuration
   - Parallel format encoding
   - Reduce processing time to 5-10 min

3. **Countdown padding** (LOW PRIORITY)
   - Detect countdown in vocals
   - Apply to instrumentals
   - Re-upload padded versions

4. **Progress refinement** (LOW PRIORITY)
   - Per-format progress
   - Estimated time remaining
   - Real-time updates

---

## Blockers

None currently. Video worker is complete and ready for testing.

---

## Estimated Completion

- **Testing:** 1 day
- **Cloud Build:** 1 day (optional)
- **Countdown padding:** 0.5 days (optional)
- **Total:** 1-2.5 days

**Phase 1.3 Status:** ~60% complete, core functionality done, testing remaining.

