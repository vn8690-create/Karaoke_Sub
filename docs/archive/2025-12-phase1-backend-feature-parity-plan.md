# Backend Feature Parity Plan

**Last Updated:** 2024-12-11  
**Status:** ✅ Core Feature Parity Achieved (v0.71.0) | Batch 1 ✅ | Batch 2 ✅ | Batch 3 ✅ | Batch 4 ✅ | Batch 5 ✅

This document tracks the progress toward complete feature parity between the local `karaoke-gen` CLI and the cloud backend, enabling the `karaoke-gen-remote` CLI to have equivalent functionality.

### Quick Parity Summary

| Category | Supported | Needed | Parity | Notes |
|----------|-----------|--------|--------|-------|
| Core Processing | 12 | 12 | **100%** | ✅ Complete |
| Distribution | 5 | 5 | **100%** | ✅ Complete |
| Lyrics Configuration | 5 | 5 | **100%** | ✅ **Batch 1 Complete** (L1-L4) |
| Style Configuration | 1 | 4 | **25%** | S2-S4 are MEDIUM priority |
| Workflow Control | 0 | 3 | **0%** | W1/W2 HIGH, W7 MEDIUM (skip flags deferred) |
| Audio Processing | 4 | 4 | **100%** | ✅ **Batch 2 & 3 Complete** (AP1-AP3, AP5) |
| Input Modes | 3 | 3 | **100%** | ✅ **Batch 4 & 5 Complete** (P2, P3) |
| Audio Fetching | 1 | 1 | **100%** | ✅ **Batch 5 Complete** (A1) |
| Flags to Remove | - | - | - | I3-I6, AP6 (simplify codebase) |

**Overall:** Core workflow complete. See [CLI Parameter Parity Analysis](#-cli-parameter-parity-analysis) for detailed parameter list with implementation plans.

**Priority Summary:**
- **HIGH**: L1-L4 ✅, AP1-AP5 ✅, P3 ✅, A1 ✅ | P2 (YouTube URLs), W1/W2 (prep/finalise phases), F15 (keep-brand-code)
- **MEDIUM**: S2-S4 (style overrides/video bg), W7 (edit-lyrics), F14 (email template)
- **LOW/DEFERRED**: W3-W6 (skip flags), D2-D3 (debugging)
- **REMOVE**: I3, I4, I5, I6, AP6 (unnecessary options)

---

## 🎉 Milestone: First Successful End-to-End Run

On December 10, 2024, we completed the first successful end-to-end karaoke track generation using `karaoke-gen-remote` with the cloud backend:

```bash
karaoke-gen-remote \
  --style_params_json="./karaoke-prep-styles-nomad.json" \
  --enable_cdg \
  --enable_txt \
  --brand_prefix=NOMAD \
  --enable_youtube_upload \
  --youtube_description_file="./youtube-video-description.txt" \
  ./waterloo1min.flac ABBA "Waterloo Test 3"
```

**Results:**
- ✅ Audio separation via Modal API
- ✅ Lyrics transcription via AudioShake
- ✅ Custom style assets uploaded and applied
- ✅ Lyrics review UI workflow
- ✅ Instrumental selection prompt
- ✅ Video rendering with corrected lyrics
- ✅ Final video encoding (4 formats)
- ✅ CDG/TXT package generation
- ✅ YouTube upload
- ✅ Dropbox upload with brand code (NOMAD-1163)
- ✅ Google Drive upload
- ✅ Discord notification
- ✅ All files downloaded locally

---

## 📊 CLI Parameter Parity Analysis

This section provides a comprehensive comparison of all CLI parameters between `karaoke-gen` (local) and `karaoke-gen-remote`, including detailed explanations of what each parameter does and how it could work remotely.

**Legend:**
- ✅ Fully supported
- ⚠️ Partially supported (limited functionality)
- ❌ Not supported (ignored or errors)
- 🔹 Remote-only (not applicable to local CLI)
- N/A Not applicable to this mode

---

### Positional Arguments

| # | Parameter | Local | Remote | Description |
|---|-----------|-------|--------|-------------|
| P1 | `<file>` | ✅ | ✅ | **Local audio file path.** Copies file to output directory, converts to WAV for processing. Supports MP3, FLAC, WAV, M4A, OGG, AAC. |
| P2 | `<url>` (YouTube) | ✅ | ✅ | **YouTube/online URL.** Uses yt-dlp to download audio and extract metadata (artist/title from video title). |
| P3 | `<artist> <title>` | ✅ | ✅ | **Audio search mode.** When no file is provided, uses flacfetch to search Deezer/Tidal/etc for high-quality audio and downloads it. |
| P4 | `<folder>` | ✅ | ❌ | **Batch folder processing.** Process all audio files in a folder, using `--filename_pattern` to extract track titles from filenames. |

**Remote Implementation Status:** ✅ **BATCH 4 & 5 COMPLETE** (v0.71.42)
- **P2 YouTube URLs**: ✅ IMPLEMENTED. Backend accepts URL via `/api/jobs/create-from-url` endpoint. Uses yt-dlp to download audio and extract metadata (artist/title). Remote CLI detects URLs and routes to URL endpoint.
- **P3 Flacfetch search**: ✅ IMPLEMENTED. Remote CLI submits artist+title, backend searches via flacfetch. Returns results for interactive selection (or auto-selects with `-y`/`--auto-download`). New job statuses: `searching_audio`, `awaiting_audio_selection`, `downloading_audio`.
- **P4 Folder batch**: LOW PRIORITY. Could accept ZIP upload, process each as separate job. Defer for now.

---

### Workflow Control

| # | Parameter | Local | Remote | Description |
|---|-----------|-------|--------|-------------|
| W1 | `--prep-only` | ✅ | ❌ | **Stop after preparation phase.** Downloads audio, separates stems, transcribes lyrics, creates title/end screens, but does NOT run finalisation (encoding, YouTube upload, etc.). Useful for reviewing intermediate outputs before committing to final render. |
| W2 | `--finalise-only` | ✅ | ❌ | **Run only finalisation phase.** Must be run from a directory that was previously prepared with `--prep-only`. Picks up where prep left off: encodes videos, creates CDG/TXT packages, uploads to YouTube/Dropbox, etc. |
| W3 | `--skip-transcription` | ✅ | ❌ | **Skip automatic lyrics transcription.** Skips the AudioShake transcription and auto-correction steps. Use this if you want to manually provide lyrics or if transcription keeps failing. Lyrics review UI will still open if you have existing lyrics files. |
| W4 | `--skip-separation` | ✅ | ❌ | **Skip audio separation.** Skips the AI-powered stem separation (Modal API). Useful when re-processing a track where you already have the stems from a previous run, or when combined with `--existing_instrumental`. |
| W5 | `--skip-lyrics` | ✅ | ❌ | **Skip all lyrics processing.** Skips fetching lyrics from Genius/Spotify, transcription, and review. Output will have no lyrics overlay - just instrumental video with title/end screens. |
| W6 | `--lyrics-only` | ✅ | ❌ | **Process only lyrics.** Sets `--skip-separation` and skips title/end screen generation. Useful for re-doing just the lyrics on an existing track without re-running expensive audio separation. |
| W7 | `--edit-lyrics` | ✅ | ❌ | **Edit lyrics of existing track.** Run from inside an existing track directory (e.g., `NOMAD-1234 - Artist - Title/`). Backs up existing outputs, re-runs lyrics transcription with the existing audio, then re-renders and re-uploads. Uses `--keep-brand-code` implicitly. |
| W8 | `--resume` | N/A | 🔹 | **Resume monitoring a job.** Reconnects to an existing remote job and continues monitoring its progress, handling review/instrumental selection if needed. |
| W9 | `--cancel` | N/A | 🔹 | **Cancel a running job.** Stops processing but keeps the job record in Firestore. Useful for aborting stuck jobs. |
| W10 | `--retry` | N/A | 🔹 | **Retry a failed job.** Restarts processing from the last successful checkpoint. Only works on jobs with `failed` status. |
| W11 | `--delete` | N/A | 🔹 | **Delete a job.** Permanently removes job record from Firestore and all associated files from GCS. |
| W12 | `--list` | N/A | 🔹 | **List all jobs.** Shows all jobs with their status, artist, title. Supports filtering with `--filter-environment` and `--filter-client-id`. |

**Remote Implementation Plan:**
- **W1 `--prep-only`**: HIGH PRIORITY. Remote CLI submits job with `prep_only=true`. Backend runs all prep tasks (audio separation, lyrics transcription with review UI, initial render). After completion, CLI downloads the entire output folder and exits. No finalisation (encoding, YouTube, Dropbox, etc.) runs. Use case: Client needs custom edits to stems or lyrics before final render.
- **W2 `--finalise-only`**: HIGH PRIORITY. Remote CLI checks current directory for expected prep output files. Uploads ALL files from that folder to backend (including any manual customizations user made since prep). Backend runs finalisation and distribution steps. Use case: User edited instrumental manually, now wants cloud to handle encoding/distribution.
- **W3-W6 Skip flags**: LOW PRIORITY. Rarely used; typically all together to regenerate title/end screens with different artist/title. Defer until pipeline refactor provides cleaner stage-targeting.
- **W7 `--edit-lyrics`**: MEDIUM PRIORITY. Re-runs lyrics worker with existing audio/stems. Creates NEW YouTube upload (doesn't delete/replace existing). Backend should handle gracefully if video with identical title already exists (user will have manually deleted old one). Use case: Customer found typo in published video.

---

### Logging & Debugging

| # | Parameter | Local | Remote | Description |
|---|-----------|-------|--------|-------------|
| D1 | `--log_level` | ✅ | ✅ | **Set logging verbosity.** Options: `debug`, `info`, `warning`, `error`. Default: `info`. Affects console output detail level. |
| D2 | `--dry_run` | ✅ | ❌ | **Simulate without changes.** Runs through the workflow logic but doesn't actually download, process, or create files. Useful for testing argument combinations. |
| D3 | `--render_bounding_boxes` | ✅ | ❌ | **Debug text positioning.** Renders red bounding boxes around text regions in title/end screen images. Helps debug custom style configurations. |

**Remote Implementation Plan:**
- **D2 `--dry_run`**: LOW PRIORITY. Backend could accept `dry_run=true`, validate inputs and return what WOULD happen without processing. Nice to have for testing.
- **D3 `--render_bounding_boxes`**: LOW PRIORITY. Backend could enable this, useful for testing styles before full render. Nice to have for debugging style configs.

---

### Input/Output Configuration

| # | Parameter | Local | Remote | Description |
|---|-----------|-------|--------|-------------|
| I1 | `--filename_pattern` | ✅ | N/A | **Regex for batch processing.** Python regex with named group `(?P<title>...)` to extract track title from filenames. Used with folder input. Example: `'(?P<index>\d+) - (?P<title>.+).mp3'` |
| I2 | `--output_dir` | ✅ | ✅ | **Output directory.** Where to write output files. Local: creates subdirectory per track. Remote: where to download completed files. Default: current directory. |
| I3 | `--no_track_subfolders` | 🗑️ | N/A | **REMOVE FROM LOCAL CLI.** Flat output structure. Not needed - always create subfolders. |
| I4 | `--lossless_output_format` | 🗑️ | N/A | **REMOVE FROM LOCAL CLI.** Stem audio format. FLAC is always fine, no need for WAV option. |
| I5 | `--output_png` | 🗑️ | N/A | **REMOVE FROM LOCAL CLI.** Always output both PNG and JPG, no need for flag. |
| I6 | `--output_jpg` | 🗑️ | N/A | **REMOVE FROM LOCAL CLI.** Always output both PNG and JPG, no need for flag. |

**Remote Implementation Plan:**
- **I3, I4, I5, I6**: REMOVE from local CLI entirely. Not worth maintaining. Backend always uses FLAC, outputs both PNG+JPG, creates subfolders.

---

### Audio Fetching Configuration

| # | Parameter | Local | Remote | Description |
|---|-----------|-------|--------|-------------|
| A1 | `--auto-download` | ✅ | ✅ | **Auto-select audio source.** When using artist+title search mode (flacfetch), automatically select the best quality source instead of prompting for manual selection. Useful for scripted/batch processing. |

**Remote Implementation Status:** ✅ **BATCH 5 COMPLETE** (v0.71.28)
- **A1 `--auto-download`**: ✅ IMPLEMENTED. Backend supports BOTH modes:
  - **Interactive (default)**: API returns search results to client. Client displays options, user selects via `/api/audio-search/{job_id}/select` endpoint.
  - **Auto-download (`--auto-download` or `-y`)**: Backend auto-selects best quality source using flacfetch's ranking.

---

### Audio Processing Configuration

| # | Parameter | Local | Remote | Description |
|---|-----------|-------|--------|-------------|
| AP1 | `--clean_instrumental_model` | ✅ | ✅ | **Stage 1 separation model.** AI model for initial vocal/instrumental separation. Default: `model_bs_roformer_ep_317_sdr_12.9755.ckpt`. Different models have different quality/speed tradeoffs. |
| AP2 | `--backing_vocals_models` | ✅ | ✅ | **Stage 2 separation model(s).** AI model(s) for separating lead vocals from backing vocals. Default: `mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt`. |
| AP3 | `--other_stems_models` | ✅ | ✅ | **Multi-stem separation model.** AI model for separating drums, bass, guitar, piano, other. Default: `htdemucs_6s.yaml`. |
| AP4 | `--model_file_dir` | ✅ | N/A | **Model cache directory.** Where to store/load AI model files. Default: `/tmp/audio-separator-models/`. |
| AP5 | `--existing_instrumental` | ✅ | ✅ | **Use pre-made instrumental.** Path to an existing instrumental file to use instead of running AI separation. Useful when you have a better instrumental from another source (official instrumental release, manual editing, etc.). Backend still runs separation for stems, but uses provided instrumental for final video. |
| AP6 | `--instrumental_format` | 🗑️ | N/A | **REMOVE FROM LOCAL CLI.** FLAC is always fine, no need for format option. |

**Remote Implementation Status:** ✅ **BATCH 2 & 3 COMPLETE** (PR #9 v0.71.24, PR #10 v0.71.26)
- **AP1 `--clean_instrumental_model`**: ✅ IMPLEMENTED. Sent as form field to backend. Audio worker passes to Modal API.
- **AP2 `--backing_vocals_models`**: ✅ IMPLEMENTED. Sent as comma-separated list, parsed and passed to Modal API.
- **AP3 `--other_stems_models`**: ✅ IMPLEMENTED. Sent as comma-separated list, parsed and passed to Modal API.
- **AP4 `--model_file_dir`**: N/A for remote - Modal API handles model caching internally.
- **AP5 `--existing_instrumental`**: ✅ IMPLEMENTED (Batch 3). User uploads instrumental file with job. Backend validates duration match (±0.5s), still runs separation for stems, but uses provided instrumental for final video encoding.
- **AP6**: REMOVE from local CLI - FLAC is always fine.

---

### Lyrics Configuration

| # | Parameter | Local | Remote | Description |
|---|-----------|-------|--------|-------------|
| L1 | `--lyrics_artist` | ✅ | ✅ | **Override artist for lyrics search.** Use different artist name when searching Genius/Spotify/Musixmatch for lyrics. Useful for covers, remixes, or when artist name differs in lyrics databases. Example: `--lyrics_artist="The Beatles"` when your file says "Beatles, The". |
| L2 | `--lyrics_title` | ✅ | ✅ | **Override title for lyrics search.** Use different song title when searching for lyrics. Useful for songs with alternate titles, subtitle variations, or "(Remastered)" suffixes. Example: `--lyrics_title="Hey Jude"` when file says "Hey Jude - 2009 Remaster". |
| L3 | `--lyrics_file` | ✅ | ✅ | **Use existing lyrics file.** Path to a text file containing lyrics to use instead of fetching from online sources. Supports TXT, DOCX, RTF formats. Useful when online lyrics are wrong or unavailable. Transcription still runs to generate timestamps. |
| L4 | `--subtitle_offset_ms` | ✅ | ✅ | **Adjust subtitle timing.** Shift all subtitle timestamps by N milliseconds. Positive values delay subtitles, negative values advance them. Useful when audio has intro padding or sync drift. Example: `--subtitle_offset_ms=500` delays by 0.5 seconds. |
| L5 | `--skip_transcription_review` | ✅ | ⚠️ | **Skip review UI.** Don't open the browser-based lyrics review interface after transcription. Use existing auto-corrected lyrics as-is. Remote: use `-y` flag instead for non-interactive mode. |

**Remote Implementation Status:** ✅ **BATCH 1 COMPLETE** (PR #8, v0.71.22)
- **L1 `--lyrics_artist`**: ✅ IMPLEMENTED. Sent as form field to backend. Lyrics worker uses for Genius/Spotify/AudioShake queries.
- **L2 `--lyrics_title`**: ✅ IMPLEMENTED. Sent as form field to backend. Lyrics worker uses for search instead of main title.
- **L3 `--lyrics_file`**: ✅ IMPLEMENTED. Uploaded with job, stored in GCS. Lyrics worker reads it instead of fetching online.
- **L4 `--subtitle_offset_ms`**: ✅ IMPLEMENTED. Sent to backend, render worker applies offset when burning subtitles.
- **L5 `--skip_transcription_review`**: Already works via `-y` flag which auto-accepts corrections.

---

### Style Configuration

| # | Parameter | Local | Remote | Description |
|---|-----------|-------|--------|-------------|
| S1 | `--style_params_json` | ✅ | ✅ | **Style configuration file.** Path to JSON file defining visual style: background images, fonts, colors, text positioning for intro/karaoke/end screens and CDG. All referenced image/font files are auto-uploaded in remote mode. |
| S2 | `--style_override` | ✅ | ❌ | **Quick style tweaks.** Override specific style parameters without editing JSON. Can be used multiple times. Format: `section.key=value`. Example: `--style_override 'intro.background_image=/path/to/new_bg.png'`. Creates a temp JSON file with overrides merged. |
| S3 | `--background_video` | ✅ | ❌ | **Video background for karaoke.** Path to video file to use as animated background instead of static image for the karaoke section. Video is looped/trimmed to match audio duration, with lyrics overlaid. |
| S4 | `--background_video_darkness` | ✅ | ❌ | **Dim video background.** Darkness overlay percentage (0-100) applied to video background so lyrics are more readable. 0 = no darkening, 100 = completely black. Default: 0. |

**Remote Implementation Plan:**
- **S2 `--style_override`**: MEDIUM PRIORITY. Send override strings to backend, merge server-side before passing to workers. Works same as local (creates merged config). Use case: Web UI will let users tweak font colors etc., needs to pass adjustments to backend.
- **S3 `--background_video`**: MEDIUM PRIORITY. Upload video file with job. Backend processes with VideoBackgroundProcessor (loop/trim to audio duration). Requires larger file upload limits. Future: Web UI could allow YouTube URL or direct upload for video background.
- **S4 `--background_video_darkness`**: Depends on S3. Send percentage to backend, apply overlay during video processing.

---

### Finalisation Configuration

| # | Parameter | Local | Remote | Description |
|---|-----------|-------|--------|-------------|
| F1 | `--enable_cdg` | ✅ | ✅ | **Generate CDG+MP3 package.** Create CD+Graphics karaoke format files (used by karaoke machines). Produces ZIP containing `.cdg` and `.mp3` files. Requires `cdg` section in style_params_json. |
| F2 | `--enable_txt` | ✅ | ✅ | **Generate TXT+MP3 package.** Create text-based karaoke format with timed lyrics. Produces ZIP containing `.txt` (with timestamps) and `.mp3` files. |
| F3 | `--brand_prefix` | ✅ | ✅ | **Brand code prefix.** Your brand identifier for sequential numbering. When set, output folder is renamed to `PREFIX-XXXX - Artist - Title` where XXXX is the next sequential number found in `organised_dir` or Dropbox. Example: `NOMAD` produces `NOMAD-1234`. |
| F4 | `--organised_dir` | ✅ | N/A | **Local organized output.** Local filesystem path where final track folders are moved after processing. Used with `--brand_prefix` to maintain organized library. Example: `/Volumes/Media/Karaoke/Tracks-Organized/`. |
| F5 | `--organised_dir_rclone_root` | ✅ | ✅ | **Rclone path for Dropbox.** Rclone remote path that maps to your organised_dir. Used to calculate next brand code number and for rclone-based uploads. Example: `dropbox:Media/Karaoke/Tracks-Organized`. |
| F6 | `--public_share_dir` | ✅ | N/A | **Local public share folder.** Local filesystem path where shareable versions (720p video, CDG, TXT) are copied for public distribution. |
| F7 | `--enable_youtube_upload` | ✅ | ✅ | **Upload to YouTube.** After encoding, upload the lossy 4K video to YouTube. Local: uses OAuth flow with client secrets. Remote: uses server-side stored credentials. |
| F8 | `--youtube_client_secrets_file` | ✅ | N/A | **YouTube OAuth credentials.** Local path to Google OAuth client secrets JSON file for YouTube API. Only needed for local mode - remote uses server-stored credentials. |
| F9 | `--youtube_description_file` | ✅ | ✅ | **YouTube video description.** Path to text file containing YouTube video description template. Supports placeholders like `{artist}`, `{title}`, `{brand_code}`. |
| F10 | `--rclone_destination` | ✅ | N/A | **Rclone sync destination.** Rclone remote path to sync public_share_dir to. Used for Google Drive public sharing. Example: `googledrive:KaraokePublic`. |
| F11 | `--dropbox_path` | N/A | 🔹 | **Dropbox folder (native API).** Remote-only: Dropbox folder path for organized output upload using native Dropbox API. Example: `/Karaoke/Tracks-Organized`. |
| F12 | `--gdrive_folder_id` | N/A | 🔹 | **Google Drive folder (native API).** Remote-only: Google Drive folder ID for public share uploads using native API. Example: `1abc123xyz`. |
| F13 | `--discord_webhook_url` | ✅ | ✅ | **Discord notification.** Webhook URL for sending completion notifications to Discord. Posts message with track info, brand code, and links. |
| F14 | `--email_template_file` | ✅ | ❌ | **Email draft template.** Path to email template file for creating Gmail drafts with track info. Supports placeholders. Uses pyperclip for manual email composition. |
| F15 | `--keep-brand-code` | ✅ | ❌ | **Preserve existing brand code.** When run from an existing track directory (with brand code in folder name), use that brand code instead of calculating a new one. Implicitly enabled with `--edit-lyrics`. |
| F16 | `-y` / `--yes` | ✅ | ✅ | **Non-interactive mode.** Auto-accept all prompts: lyrics corrections, instrumental selection, confirmations. Useful for automated/CI pipelines. Remote: auto-completes review, selects clean instrumental. |
| F17 | `--test_email_template` | ✅ | N/A | **Test email template.** Debug mode: test the email template rendering with fake data without processing any track. |

**Remote Implementation Plan:**
- **F14 `--email_template_file`**: MEDIUM PRIORITY. Two behaviors needed:
  1. **Finalisation**: Same as local - use template to create Gmail draft (requires Gmail API OAuth). User just changes recipient and sends.
  2. **API endpoint**: Expose endpoint to fetch templated message text for a job. Use case: Web frontend button to copy message for pasting into Fiverr, etc.
- **F15 `--keep-brand-code`**: HIGH PRIORITY (for `--finalise-only` workflow). When using `--finalise-only` remotely, user may be re-processing an already-published track. Must preserve existing brand code so updated files overwrite in Dropbox/GDrive rather than creating new sequence number. Implementation: Remote CLI reads brand code from local folder name, sends to backend.

---

### Remote CLI Specific Options

| # | Parameter | Local | Remote | Description |
|---|-----------|-------|--------|-------------|
| R1 | `--service-url` | N/A | 🔹 | **Backend service URL.** URL of the karaoke-gen cloud backend. Can also be set via `KARAOKE_GEN_URL` environment variable. Required for remote mode. |
| R2 | `--review-ui-url` | N/A | 🔹 | **Lyrics review UI URL.** URL of the hosted lyrics review web application. Default: `https://gen.nomadkaraoke.com/lyrics/`. |
| R3 | `--poll-interval` | N/A | 🔹 | **Status poll frequency.** Seconds between job status checks while monitoring. Default: 5 seconds. |
| R4 | `--environment` | N/A | 🔹 | **Job environment tag.** Tag jobs with environment label (test/production/development) for filtering and cleanup. Sent as `X-Environment` header. |
| R5 | `--client-id` | N/A | 🔹 | **Client identifier tag.** Tag jobs with client/user identifier for filtering. Sent as `X-Client-ID` header. |
| R6 | `--filter-environment` | N/A | 🔹 | **Filter by environment.** When using `--list` or `--bulk-delete`, only show/delete jobs matching this environment. |
| R7 | `--filter-client-id` | N/A | 🔹 | **Filter by client ID.** When using `--list` or `--bulk-delete`, only show/delete jobs matching this client ID. |
| R8 | `--bulk-delete` | N/A | 🔹 | **Bulk delete jobs.** Delete all jobs matching filter criteria. Requires at least one filter (`--filter-environment` or `--filter-client-id`). |

---

## 🚀 Implementation Batches

The following batches are ordered by priority and grouped by similar functionality. Each batch is designed to be a self-contained unit of work that can be tackled by a single agent session.

### 📋 Instructions for Implementing a Batch

**Before starting a batch, ensure you follow these steps:**

#### 1. Test Coverage Requirements
All code changes must have **>70% test coverage** on modified files. Run:
```bash
python -m pytest backend/tests/ --cov=backend.models.job --cov=backend.api.routes.file_upload --cov=backend.workers.<worker_name> --cov-report=term-missing
```

**Required tests for each batch:**
- **Model changes:** Test new fields exist, have correct defaults, serialize properly
- **API changes:** Test form validation (valid/invalid inputs), file upload handling
- **Worker changes:** Test parameter passing, configuration, error handling
- **CLI changes:** Test submit_job() passes parameters correctly

#### 2. Documentation Updates (REQUIRED)
As part of your PR, you MUST update this document:
- [ ] Update the **Quick Parity Summary** table to reflect new parity percentages
- [ ] Mark parameters as ✅ in the relevant **CLI Parameter Parity Analysis** section
- [ ] Update **Remote Implementation Plan/Status** to show ✅ IMPLEMENTED
- [ ] Mark the batch as **✅ COMPLETE** with PR number in the **Summary Table**
- [ ] Add entry to **Recently Completed** table with version and PR number
- [ ] Remove items from **Not Yet Implemented** list

#### 3. Version Bump
Bump the patch version in `pyproject.toml` before committing.

#### 4. PR Requirements
- Title: `feat: Batch N - <description>`
- Include: Summary of changes, files modified, tests added
- Link to this document in PR description

---

### Batch 1: Lyrics Configuration (HIGH) ✅ COMPLETE
**Parameters:** L1 `--lyrics_artist`, L2 `--lyrics_title`, L3 `--lyrics_file`, L4 `--subtitle_offset_ms`

**Status:** ✅ **IMPLEMENTED** - PR #8 merged (v0.71.22)

**Implementation Summary:**
- Remote CLI: Added 4 form fields to `submit_job()`, uploads lyrics file if provided
- Backend: Added 4 Form parameters to `/api/jobs/upload` endpoint
- Backend: Lyrics worker downloads user lyrics file, passes overrides to LyricsProcessor
- Backend: Render worker applies subtitle offset via OutputConfig

**Files modified:**
- `karaoke_gen/utils/remote_cli.py` - submit_job() with lyrics params
- `backend/api/routes/file_upload.py` - Form fields + lyrics file upload
- `backend/models/job.py` - lyrics_artist, lyrics_title, lyrics_file_gcs_path, subtitle_offset_ms fields
- `backend/workers/lyrics_worker.py` - override values passed to LyricsProcessor
- `backend/workers/render_video_worker.py` - subtitle_offset_ms applied

**Tests added:** 25+ unit tests covering lyrics file validation, Job model fields, worker configuration

**Complexity:** Low-Medium (straightforward form fields + file upload)

---

### Batch 2: Audio Separation Model Selection (HIGH) ✅ COMPLETE
**Parameters:** AP1 `--clean_instrumental_model`, AP2 `--backing_vocals_models`, AP3 `--other_stems_models`

**Status:** ✅ **IMPLEMENTED** - PR #9 merged (v0.71.24)

**Implementation Summary:**
- Remote CLI: Added 3 form fields to `submit_job()`, sends models as comma-separated strings
- Backend: Added 3 Form parameters to `/api/jobs/upload` endpoint, parses comma-separated lists
- Backend: Job model stores model configuration as optional fields
- Backend: Audio worker passes model names to AudioProcessor which uses Modal API

**Files modified:**
- `karaoke_gen/utils/remote_cli.py` - submit_job() with model params
- `backend/api/routes/file_upload.py` - Form fields + comma parsing
- `backend/models/job.py` - clean_instrumental_model, backing_vocals_models, other_stems_models fields
- `backend/workers/audio_worker.py` - create_audio_processor() accepts model params from job

**Tests added:** 15+ unit tests covering Job model fields, form parsing, AudioProcessor configuration

**Complexity:** Low (Modal API already supports dynamic model selection)

---

### Batch 3: Existing Instrumental Support (HIGH) ✅ COMPLETE
**Parameters:** AP5 `--existing_instrumental`

**Status:** ✅ **IMPLEMENTED** - PR #10 merged (v0.71.26)

**Implementation Summary:**
- Remote CLI: Added `--existing_instrumental` parameter, uploads file as `existing_instrumental` type
- Backend: Added `existing_instrumental` to VALID_FILE_TYPES with audio extension validation
- Backend: Duration validation (±0.5s tolerance) at uploads-complete endpoint using pydub
- Backend: Job model has `existing_instrumental_gcs_path` field
- Backend: Video worker downloads user-provided instrumental if present, uses it for final encoding

**Files modified:**
- `karaoke_gen/utils/remote_cli.py` - submit_job() with existing_instrumental param
- `backend/api/routes/file_upload.py` - VALID_FILE_TYPES, GCS path generation, duration validation
- `backend/models/job.py` - existing_instrumental_gcs_path field
- `backend/workers/video_worker.py` - downloads and uses user-provided instrumental

**Tests added:** 20+ unit tests covering model fields, file type validation, GCS path generation, duration validation

**Complexity:** Medium (file upload + validation + conditional logic)

---

### Batch 4: YouTube URL Input (HIGH) ✅ COMPLETE
**Parameters:** P2 `<url>` (YouTube/online URL)

**Status:** ✅ **IMPLEMENTED** (v0.71.26)

**Implementation Summary:**
- Remote CLI: Detects URLs via `is_url()`, routes to `submit_job_from_url()` method
- Backend: New `/api/jobs/create-from-url` endpoint accepts URL and optional artist/title
- Backend: Audio worker downloads from URL using yt-dlp, auto-detects artist/title from metadata
- FileHandler: Added `download_video()` and `extract_metadata_from_url()` methods
- Dependencies: yt-dlp added to pyproject.toml

**Files modified:**
- `karaoke_gen/utils/remote_cli.py` - URL detection, new `submit_job_from_url()` method
- `karaoke_gen/file_handler.py` - `download_video()` and `extract_metadata_from_url()` methods
- `backend/api/routes/file_upload.py` - `CreateJobFromUrlRequest`, `CreateJobFromUrlResponse`, `/api/jobs/create-from-url` endpoint
- `backend/workers/audio_worker.py` - Enhanced `download_from_url()` with metadata extraction
- `pyproject.toml` - Added yt-dlp dependency

**Tests added:** 20+ unit tests covering URL validation, request/response models, Job URL field

**Complexity:** Medium-High (new input mode, yt-dlp integration)

---

### Batch 5: Flacfetch Audio Search (HIGH) ✅ COMPLETE
**Parameters:** P3 `<artist> <title>` (search mode), A1 `--auto-download`

**Status:** ✅ **IMPLEMENTED** - PR #13 merged (v0.71.28)

**Implementation Summary:**
- Remote CLI: Detects artist+title without file, calls `/api/audio-search/search` endpoint
- Backend: New `AudioSearchService` integrates flacfetch for searching
- Backend: New job statuses `searching_audio`, `awaiting_audio_selection`, `downloading_audio`
- Backend: Returns search results for interactive selection, or auto-selects with `auto_download=true`
- Remote CLI: Displays results interactively, user selects, sends to `/api/audio-search/{job_id}/select`
- Backend: Downloads selected audio to GCS, proceeds with normal job flow
- Support `--auto-download` / `-y` for non-interactive auto-selection

**Files modified:**
- `karaoke_gen/utils/remote_cli.py` - search flow, display results, `search_audio()`, `select_audio_source()`, `handle_audio_selection()`
- `backend/api/routes/audio_search.py` - NEW: search and select endpoints
- `backend/services/audio_search_service.py` - NEW: flacfetch integration service
- `backend/models/job.py` - New statuses and fields (`audio_search_artist`, `audio_search_title`, `auto_download`)
- `backend/main.py` - Register audio_search router

**Tests added:** 20+ unit tests covering Job model fields, AudioSearchService, state transitions

**Complexity:** High (new interactive API flow, new service integration)

---

### Batch 6: Two-Phase Workflow (HIGH) ✅ COMPLETE
**Parameters:** W1 `--prep-only`, W2 `--finalise-only`, F15 `--keep-brand-code`

**Status:** ✅ Complete (2025-12-11)

**Implementation Summary:**
- **prep-only:** Added `prep_only` field to Job model. When set, backend transitions to new `PREP_COMPLETE` status after review and video rendering (with_vocals.mkv). CLI downloads all prep outputs.
- **finalise-only:** Added new endpoint `/api/jobs/create-finalise-only` for uploading prep outputs. Remote CLI detects files in prep folder, uploads them via signed URLs, and monitors finalisation.
- **keep-brand-code:** Remote CLI extracts brand code from folder name (e.g., "NOMAD-1234 - Artist - Title"), sends to backend. Video worker uses preserved brand code for distribution.

**Files modified:**
- `backend/models/job.py` - Added `PREP_COMPLETE` status, `prep_only`, `finalise_only`, `keep_brand_code` fields, updated state transitions
- `backend/api/routes/file_upload.py` - Added `prep_only`, `keep_brand_code` to job creation, new finalise-only endpoints
- `backend/workers/render_video_worker.py` - Conditional transition to PREP_COMPLETE for prep-only jobs
- `backend/workers/video_worker.py` - Use preserved brand code when set
- `backend/services/job_manager.py` - Pass new fields through job creation
- `karaoke_gen/utils/remote_cli.py` - Full implementation of prep-only, finalise-only, and keep-brand-code flows

**Tests added:**
- `backend/tests/test_models.py` - Tests for new fields and PREP_COMPLETE status
- `backend/tests/test_file_upload.py` - Tests for finalise-only models and endpoints

**Complexity:** High (significant workflow changes, new upload flow)

---

### Batch 7: Style Overrides (MEDIUM)
**Parameters:** S2 `--style_override`

**Scope:**
- Remote CLI: Parse override strings, send as array to backend
- Backend: Accept style_override array
- Backend: Merge overrides with uploaded style JSON before processing
- Handle asset references in overrides (upload referenced files)

**Files to modify:**
- `karaoke_gen/utils/remote_cli.py` - parse and send overrides
- `backend/api/routes/file_upload.py` - accept overrides
- `backend/services/style_service.py` or similar - merge logic

**Complexity:** Medium (string parsing, merge logic, asset handling)

---

### Batch 8: Video Background (MEDIUM)
**Parameters:** S3 `--background_video`, S4 `--background_video_darkness`

**Scope:**
- Remote CLI: Upload video file (larger file support needed)
- Backend: Accept video upload, store in GCS
- Backend: Render worker uses VideoBackgroundProcessor
- Backend: Apply darkness overlay

**Files to modify:**
- `karaoke_gen/utils/remote_cli.py` - upload video file
- `backend/api/routes/file_upload.py` - accept video upload (larger limits)
- `backend/workers/render_worker.py` - integrate VideoBackgroundProcessor

**Complexity:** Medium (large file upload, video processing)

---

### Batch 9: Edit Lyrics Mode (MEDIUM)
**Parameters:** W7 `--edit-lyrics`

**Scope:**
- Remote CLI: Accept job_id for existing job, trigger edit mode
- Backend: Load existing job's audio/stems from GCS
- Backend: Re-run lyrics worker only
- Backend: Re-render with new lyrics
- Backend: Create NEW YouTube upload (handle duplicate title gracefully)

**Files to modify:**
- `karaoke_gen/utils/remote_cli.py` - edit mode flow
- `backend/api/routes/` - edit endpoint or flag
- `backend/workers/orchestrator.py` - partial re-processing logic

**Complexity:** Medium-High (partial re-processing, state management)

---

### Batch 10: Email Template + Cleanup (LOW)
**Parameters:** F14 `--email_template_file`, D2 `--dry_run`, D3 `--render_bounding_boxes`
**Removal:** I3 `--no_track_subfolders`, I4 `--lossless_output_format`, I5 `--output_png`, I6 `--output_jpg`, AP6 `--instrumental_format`

**Scope:**
- **Email template:** Upload template, backend creates Gmail draft + new API endpoint to fetch formatted text
- **Dry run:** Backend validates inputs, returns plan without executing
- **Bounding boxes:** Enable debug rendering in screens worker
- **Removal:** Remove 5 unnecessary CLI flags from local CLI

**Files to modify:**
- `karaoke_gen/utils/cli_args.py` - remove flags
- `karaoke_gen/utils/remote_cli.py` - email template upload
- `backend/api/routes/` - email template endpoint
- `backend/services/email_service.py` - Gmail API integration

**Complexity:** Mixed (Gmail OAuth is complex, removals are simple)

---

### Summary Table

| Batch | Parameters | Priority | Complexity | Status |
|-------|------------|----------|------------|--------|
| 1 | L1-L4 (lyrics config) | HIGH | Low-Medium | ✅ **COMPLETE** (PR #8) |
| 2 | AP1-AP3 (model selection) | HIGH | Low | ✅ **COMPLETE** (PR #9) |
| 3 | AP5 (existing instrumental) | HIGH | Medium | ✅ **COMPLETE** (PR #10) |
| 4 | P2 (YouTube URLs) | HIGH | Medium-High | ✅ **COMPLETE** |
| 5 | P3, A1 (flacfetch search) | HIGH | High | ✅ **COMPLETE** (PR #13) |
| 6 | W1, W2, F15 (two-phase) | HIGH | High | ⏳ Pending |
| 7 | S2 (style overrides) | MEDIUM | Medium | ⏳ Pending |
| 8 | S3, S4 (video background) | MEDIUM | Medium | ⏳ Pending |
| 9 | W7 (edit-lyrics) | MEDIUM | Medium-High | ⏳ Pending |
| 10 | F14, D2, D3, removals | LOW | Mixed | ⏳ Pending |

**Recommended Order:** ~~1~~ → ~~2~~ → ~~3~~ → ~~4~~ → ~~5~~ → 6 → 7 → 8 → 9 → 10

Batches 1-4 are quick wins that add significant value. Batches 5-6 are larger but high priority. Batches 7-10 can be done as time permits.

---

## ✅ Implementation Decisions (Answered 2024-12-10)

All questions have been answered and incorporated into the "Remote Implementation Plan" sections above. Summary of key decisions:

### Workflow Control
- **W1/W2**: YES, two-phase workflow needed. `--prep-only` downloads all prep outputs after review, `--finalise-only` uploads local folder (with any manual edits) for cloud finalisation.
- **W3-W6 Skip flags**: LOW PRIORITY - rarely used, defer until pipeline refactor provides cleaner stage-targeting.
- **W7 Edit-lyrics**: Creates NEW YouTube upload (user deletes old one manually). Backend handles duplicate title gracefully.

### Input Modes
- **P2 YouTube**: HIGH PRIORITY - needed for niche live versions only on YouTube.
- **P3 Flacfetch**: HIGH PRIORITY - MUST be interactive via API (not auto-select) for future web UI audio source picker.

### Audio Processing
- **AP1-AP3 Models**: HIGH PRIORITY - all model options must work remotely (Modal API can load any model on demand).
- **AP5 Existing Instrumental**: Still run separation (for consistent stem downloads), but use provided instrumental for final video. Validate duration match (±0.5s) at job start before proceeding.

### I/O & Audio Format Options
- **I3, I4, I5, I6, AP6**: REMOVE from local CLI entirely - unnecessary options, simplifies codebase.

### Audio Fetching
- **A1 `--auto-download`**: Backend must support BOTH interactive (default, for web UI) AND auto-select (with `-y` flag) modes.

### Style
- **S2 Style Override**: MEDIUM PRIORITY - needed for web UI style tweaks (font colors, etc.).
- **S3/S4 Background Video**: MEDIUM PRIORITY - implement, will eventually allow YouTube URL or direct upload in web UI.

### Finalisation
- **F14 Email Template**: BOTH - create Gmail draft (like local) AND expose API endpoint to fetch templated text (for Fiverr copy-paste).
- **F15 Keep-brand-code**: HIGH PRIORITY for `--finalise-only` workflow - preserves brand code so updates overwrite existing Dropbox/GDrive files.

---

## Vision

The karaoke-gen system supports multiple interfaces to the same core functionality:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KARAOKE-GEN ECOSYSTEM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   INTERFACES                          BACKEND                               │
│   ──────────                          ───────                               │
│                                                                             │
│   ┌─────────────────┐                                                       │
│   │ karaoke-gen CLI │ ──── Local Processing (CPU/GPU) ────────┐            │
│   │ (local mode)    │                                          │            │
│   └─────────────────┘                                          │            │
│                                                                │            │
│   ┌─────────────────┐     ┌──────────────────────────────┐    │            │
│   │ karaoke-gen-    │     │  Cloud Backend (Cloud Run)   │    │            │
│   │ remote CLI      │ ──► │  • FastAPI                   │    ▼            │
│   └─────────────────┘     │  • Modal GPU for separation  │                 │
│                           │  • AudioShake for lyrics     │   OUTPUTS       │
│   ┌─────────────────┐     │  • KaraokeFinalise for video │   ───────       │
│   │ Web UI          │ ──► │                              │                 │
│   │ (future)        │     │  DISTRIBUTION:               │   • YouTube     │
│   └─────────────────┘     │  • YouTube upload ✅         │   • Dropbox     │
│                           │  • Dropbox (native API) ✅   │   • Google Drive│
│                           │  • Google Drive (native) ✅  │   • Discord     │
│                           │  • Discord notification ✅   │                 │
│                           └──────────────────────────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Status

### ✅ Core Processing (Complete)

| Feature | Status | Implementation |
|---------|--------|----------------|
| File upload | ✅ | `backend/api/routes/file_upload.py` |
| Audio separation | ✅ | `backend/workers/audio_worker.py` (Modal API) |
| Lyrics transcription | ✅ | `backend/workers/lyrics_worker.py` (AudioShake) |
| Human lyrics review | ✅ | `backend/api/routes/review.py` + hosted UI |
| Custom styles (video) | ✅ | `karaoke_gen/style_loader.py` unified module |
| Custom styles (CDG) | ✅ | Passed through to KaraokeFinalise |
| Title/End screens | ✅ | `backend/workers/screens_worker.py` |
| Video rendering | ✅ | `backend/workers/render_video_worker.py` |
| Instrumental selection | ✅ | API endpoint + CLI prompt |
| Video encoding (4 formats) | ✅ | `backend/workers/video_worker.py` |
| CDG/TXT packages | ✅ | KaraokeFinalise via video_worker |
| Non-interactive mode | ✅ | `-y` flag for automated testing |
| Output file download | ✅ | Streaming download endpoint |

### ✅ Distribution Features (Complete)

| Feature | Status | Notes |
|---------|--------|-------|
| YouTube upload | ✅ | Server-side OAuth credentials |
| Dropbox upload | ✅ | Native API (via refresh token) |
| Brand code calculation | ✅ | Sequential from existing folders |
| Google Drive upload | ✅ | Service account credentials |
| Discord notification | ✅ | Webhook URL from job or default |

### ✅ Recently Completed

| Feature | Version | PR | Notes |
|---------|---------|-----|-------|
| Flacfetch audio search | v0.71.42 | #13 | `artist title` (search mode), `--auto-download` - search and download audio by artist+title |
| YouTube URL input | v0.71.26 | - | `<url>` positional argument for YouTube/online URLs |
| Existing instrumental | v0.71.26 | #10 | `--existing_instrumental` - upload and use user-provided instrumental |
| Audio model selection | v0.71.24 | #9 | `--clean_instrumental_model`, `--backing_vocals_models`, `--other_stems_models` |
| Lyrics override params | v0.71.22 | #8 | `--lyrics_artist`, `--lyrics_title`, `--lyrics_file`, `--subtitle_offset_ms` |

### ⏳ Not Yet Implemented

| Feature | Priority | Notes |
|---------|----------|-------|
| Style override | MEDIUM | `--style_override` for quick tweaks |
| Skip separation/transcription | MEDIUM | Workflow control for re-processing |
| Edit lyrics mode | MEDIUM | `--edit-lyrics` for fixing existing tracks |
| Background video | MEDIUM | `--background_video` requires video upload |
| Two-phase workflow | HIGH | `--prep-only`, `--finalise-only` |
| Batch folder processing | LOW | Process multiple files at once |
| Gmail draft creation | LOW | Nice-to-have, not blocking |

---

## Required Secrets Configuration

### Secret Manager Secrets (All Configured)

| Secret Name | Status | Description |
|-------------|--------|-------------|
| `audioshake-api-key` | ✅ | AudioShake API key |
| `genius-api-key` | ✅ | Genius lyrics API |
| `audio-separator-api-url` | ✅ | Modal API URL |
| `spotify-cookie` | ✅ | Spotify lyrics access |
| `rapidapi-key` | ✅ | Musixmatch via RapidAPI |
| `youtube-oauth-credentials` | ✅ | YouTube upload OAuth tokens |
| `dropbox-oauth-credentials` | ✅ | Dropbox API OAuth tokens |
| `gdrive-service-account` | ✅ | Google Drive service account |
| `discord-webhook-url` | ✅ | Default Discord webhook |
| `red-api-key` | ⏳ | RED tracker API key (flacfetch audio search) |
| `red-api-url` | ⏳ | RED tracker base URL (flacfetch audio search) |
| `ops-api-key` | ⏳ | OPS tracker API key (flacfetch audio search) |
| `ops-api-url` | ⏳ | OPS tracker base URL (flacfetch audio search) |

### Default Distribution Settings

The backend supports default distribution settings via environment variables:

| Environment Variable | Description |
|---------------------|-------------|
| `DEFAULT_DROPBOX_PATH` | Default Dropbox folder path |
| `DEFAULT_GDRIVE_FOLDER_ID` | Default Google Drive folder ID |
| `DEFAULT_DISCORD_WEBHOOK_URL` | Default Discord webhook URL |

These can be overridden per-job via CLI arguments.

---

## Remote CLI Options

The `karaoke-gen-remote` CLI supports the following distribution options:

```bash
karaoke-gen-remote \
  --style_params_json="/path/to/styles.json" \
  --enable_cdg \
  --enable_txt \
  --brand_prefix=NOMAD \
  --enable_youtube_upload \
  --youtube_description_file="/path/to/description.txt" \
  ./audio.flac "Artist" "Title"
```

**Notes:**
- `--style_params_json`: All referenced images/fonts are auto-uploaded
- Distribution uses server-side credentials (no local secrets needed)
- `--dropbox_path` and `--gdrive_folder_id` can override defaults

---

## Future Architecture

For the comprehensive architecture plan covering both **horizontal scalability** (Cloud Tasks, Cloud Run Jobs) and **software architecture** (shared pipeline, SOLID, DRY), see:

**[SCALABLE-ARCHITECTURE-PLAN.md](./SCALABLE-ARCHITECTURE-PLAN.md)**

Key goals:
- **100+ concurrent jobs** with no performance degradation
- **Dedicated resources per job** (no CPU/memory contention)
- **Shared pipeline architecture** - single source of truth for business logic
- **DRY codebase** - bug fixes apply to both local and remote execution

---

## Testing

### Running Tests

```bash
# All tests
pytest tests/ backend/tests/ -v

# Backend tests only
pytest backend/tests/ -v

# With coverage
pytest tests/unit/ -v --cov=karaoke_gen --cov-report=term-missing
```

### Test Coverage Requirements

- Minimum 70% coverage enforced in CI
- All new features must have tests
- Integration tests for critical paths

---

## Deployment

### Environment Variables (Cloud Run)

```
GOOGLE_CLOUD_PROJECT=karaoke-gen
GCS_BUCKET_NAME=karaoke-gen-storage
MODAL_API_URL=https://modal-api-url
AUDIOSHAKE_API_TOKEN=xxx
GENIUS_API_TOKEN=xxx
DEFAULT_DROPBOX_PATH=/path/to/dropbox/folder
DEFAULT_GDRIVE_FOLDER_ID=folder-id
DEFAULT_DISCORD_WEBHOOK_URL=https://discord.com/...
```

### CI/CD Pipeline

- **Test Workflow**: Runs on all PRs
- **Build Workflow**: Builds Docker image on push to main
- **Deploy**: Manual trigger to Cloud Run

---

## Files Reference

### Core Backend Files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app entry point |
| `backend/config.py` | Environment configuration |
| `backend/models/job.py` | Job data model (Firestore) |
| `backend/services/job_manager.py` | Job state management |
| `backend/services/storage_service.py` | GCS operations |
| `backend/services/credential_manager.py` | OAuth credential management |
| `backend/services/dropbox_service.py` | Native Dropbox API |
| `backend/services/gdrive_service.py` | Native Google Drive API |
| `backend/services/youtube_service.py` | YouTube upload service |

### Worker Files

| File | Purpose |
|------|---------|
| `backend/workers/audio_worker.py` | Modal API audio separation |
| `backend/workers/lyrics_worker.py` | AudioShake transcription |
| `backend/workers/screens_worker.py` | Title/end screen generation |
| `backend/workers/render_video_worker.py` | Post-review video with lyrics |
| `backend/workers/video_worker.py` | Final encoding via KaraokeFinalise |
| `backend/workers/style_helper.py` | Style config loading from GCS |

### API Routes

| File | Purpose |
|------|---------|
| `backend/api/routes/file_upload.py` | Job submission with file upload |
| `backend/api/routes/jobs.py` | Job status/management |
| `backend/api/routes/review.py` | Lyrics review endpoints |
| `backend/api/routes/internal.py` | Worker callback endpoints |
| `backend/api/routes/auth.py` | OAuth flow for distribution services |

### Remote CLI

| File | Purpose |
|------|---------|
| `karaoke_gen/utils/remote_cli.py` | Remote CLI implementation |
| `karaoke_gen/utils/cli_args.py` | Shared CLI argument definitions |

---

## Recent Changes Log

### 2024-12-11: v0.71.28 - Batch 5 Complete (Flacfetch Audio Search)

**PR #13: Flacfetch Audio Search for Remote CLI**

- ✅ `artist title` (search mode) - Search for audio by artist and title without providing a file
- ✅ `--auto-download` - Auto-select best audio source (skip interactive selection)
- New job statuses: `searching_audio`, `awaiting_audio_selection`, `downloading_audio`
- New API endpoints: `POST /api/audio-search/search`, `GET /api/audio-search/{job_id}/results`, `POST /api/audio-search/{job_id}/select`
- Interactive mode: Returns search results for user selection
- Auto mode: Uses flacfetch's quality ranking to auto-select best source
- Added 20+ unit tests for new functionality
- Files: `remote_cli.py`, `audio_search.py` (new route), `audio_search_service.py` (new service), `job.py`

### 2024-12-11: v0.71.26 - Batch 3 Complete (Existing Instrumental Support)

**PR #10: Existing Instrumental Support for Remote CLI**

- ✅ `--existing_instrumental` - Upload and use user-provided instrumental file
- Duration validation (±0.5s tolerance) before processing starts
- Backend still runs AI separation for stem downloads, but uses provided instrumental for final video
- Added 20+ unit tests for new functionality
- Files: `remote_cli.py`, `file_upload.py`, `job.py`, `video_worker.py`

### 2024-12-11: v0.71.24 - Batch 2 Complete (Audio Model Selection)

**PR #9: Audio Model Selection for Remote CLI**

- ✅ `--clean_instrumental_model` - Custom Stage 1 separation model
- ✅ `--backing_vocals_models` - Custom backing vocals separation models
- ✅ `--other_stems_models` - Custom multi-stem separation models (bass, drums, etc.)
- Added 15+ unit tests for new functionality
- Files: `remote_cli.py`, `file_upload.py`, `job.py`, `audio_worker.py`

### 2024-12-10: v0.71.22 - Batch 1 Complete (Lyrics Configuration)

**PR #8: Lyrics Configuration for Remote CLI**

- ✅ `--lyrics_artist` - Override artist name for lyrics search
- ✅ `--lyrics_title` - Override title for lyrics search
- ✅ `--lyrics_file` - Upload custom lyrics file (TXT, DOCX, RTF)
- ✅ `--subtitle_offset_ms` - Adjust subtitle timing offset
- Added 25+ unit tests for new functionality
- Files: `remote_cli.py`, `file_upload.py`, `job.py`, `lyrics_worker.py`, `render_video_worker.py`

### 2024-12-10: v0.71.0 - Core Feature Parity Complete

**First successful end-to-end remote run!**

- All core processing working (audio, lyrics, screens, video)
- All distribution features working (YouTube, Dropbox, Google Drive, Discord)
- Native API integration for Dropbox and Google Drive (no rclone dependency)
- Comprehensive documentation updates
- Ready for merge to main

### 2024-12-09: Distribution Services Integration

- Added native Dropbox API service with OAuth refresh
- Added native Google Drive API with service account
- Added YouTube upload with OAuth credentials
- Added credential validation on job submission
- Added default distribution settings from environment

### 2024-12-09: Download Fix

- Added streaming download endpoint `/api/jobs/{job_id}/download/{category}/{file_key}`
- Removed dependency on signed URLs (simpler, works without special IAM permissions)
- CLI downloads via HTTP through backend

### 2024-12-09: Non-Interactive Mode

- Added `-y` flag for automated testing
- Auto-completes lyrics review
- Auto-selects clean instrumental

### 2024-12-08: Style Loader Consolidation

- Created `karaoke_gen/style_loader.py` as single source of truth
- Updated all workers to use unified style loading
- Style assets properly uploaded and applied

---

## Next Steps

### Immediate (Post-Merge)
1. ✅ Merge `replace-modal-with-google-cloud` branch to main
2. ✅ Tag v0.71.0 release
3. Update PyPI package

### Short-Term: Feature Parity (Priority Order)

1. ✅ **Lyrics Configuration** (Batch 1 - COMPLETE)
   - `--lyrics_artist`, `--lyrics_title`, `--lyrics_file`, `--subtitle_offset_ms`
   - PR #8, v0.71.22

2. ✅ **Audio Model Selection** (Batch 2 - COMPLETE)
   - `--clean_instrumental_model`, `--backing_vocals_models`, `--other_stems_models`
   - PR #9, v0.71.24

3. ✅ **Existing Instrumental** (Batch 3 - COMPLETE)
   - Added `--existing_instrumental` upload support
   - PR #10, v0.71.26

4. **YouTube URL Input** (Batch 4 - NEXT)
   - Accept YouTube URLs as input
   - Requires: yt-dlp in container
   - Enables: Processing niche live versions only on YouTube

5. ✅ **Flacfetch Audio Search** (Batch 5 - COMPLETE)
   - Interactive audio source selection via API
   - v0.71.28

### Medium-Term: Workflow Features

1. **Two-Phase Workflow** (Batch 6) ✅ COMPLETE
   - `--prep-only` and `--finalise-only` modes

3. **Style Override** (Batch 7)
   - Quick style tweaks without editing JSON

4. **Background Video Support** (Batch 8)
   - Upload and use video backgrounds

5. **Edit Lyrics Mode** (Batch 9)
   - Allow fixing lyrics on completed jobs

### Long-Term (Scalable Architecture)

See **[SCALABLE-ARCHITECTURE-PLAN.md](./SCALABLE-ARCHITECTURE-PLAN.md)** for the comprehensive plan covering:
1. Cloud Tasks integration for horizontal scalability
2. Cloud Run Jobs for long-running video encoding
3. Shared pipeline architecture for code reuse
4. Implementation roadmap and migration strategy
