# Plan: Video Worker Stage Refactor

**Created:** 2026-01-03
**Branch:** feat/sess-20260103-2250-investigate-youtube-upload
**Status:** COMPLETE - Ready for PR
**Last Updated:** 2026-01-04

## Overview

Refactor `video_worker.py` and `KaraokeFinalise` into separate, composable stages following SOLID principles. This eliminates the GCE vs KaraokeFinalise code path divergence that causes features like YouTube upload to be missing from the GCE encoding path.

## Three Execution Modes

Understanding the three ways this system runs is critical to the refactor:

### 1. Local CLI (`karaoke-gen`)
- Runs entirely on user's machine
- KaraokeFinalise.process() orchestrates everything
- Writes directly to local Dropbox sync folder (e.g., `~/Dropbox/Karaoke/Tracks-Organized/`)
- **Produces full output structure** with stems/, lyrics/, visualizations/, etc.
- **This is the source of truth for output format**

### 2. Remote CLI (`karaoke-gen-remote`)
- User's CLI talks to cloud backend (api.nomadkaraoke.com)
- Cloud does ALL processing (audio, lyrics, video encoding)
- CLI just monitors job status and downloads final outputs
- With Dropbox configured: cloud uploads full structure to user's Dropbox
- Without Dropbox: user downloads individual files

### 3. Web Frontend (`gen.nomadkaraoke.com`)
- Same cloud backend as remote CLI
- User sees:
  - YouTube video link
  - Dropbox folder link
  - Direct download: final karaoke video (720p)
  - Direct download: 4K video
  - Direct download: "with vocals" video
  - Direct download: CDG zip (if enabled)

## Problem Statement

Currently, `video_worker.py` has two completely divergent code paths:

```python
if use_gce_encoding:
    # GCE PATH: Only encoding, missing YouTube/Discord/CDG/TXT
    result = await _encode_via_gce(...)
    # result DOES NOT include youtube_url!
else:
    # STANDARD PATH: KaraokeFinalise does everything
    finalise = KaraokeFinalise(...)
    result = finalise.process()
    # result includes youtube_url from upload
```

### What GCE Encoding Broke

| Feature | KaraokeFinalise Path | GCE Path |
|---------|---------------------|----------|
| Video encoding | ✅ 4 formats | ✅ 4 formats |
| YouTube upload | ✅ | ❌ **BROKEN** |
| Discord notification | ✅ | ❌ **BROKEN** |
| CDG/TXT packaging | ✅ | ❌ **BROKEN** |
| Brand code generation | ✅ | ✅ (via Dropbox service) |
| Dropbox upload | ✅ (rclone) | ✅ (native SDK) |
| Google Drive upload | ❌ | ✅ (native SDK) |

### Root Cause

`KaraokeFinalise.process()` is a monolith that handles:
1. CDG/TXT packaging
2. Video encoding (the CPU-intensive part)
3. YouTube upload
4. Discord notifications
5. Folder organization

The GCE encoding was added as a bypass around the entire class, rather than replacing just the encoding step.

## Requirements

### Functional Requirements
- [ ] YouTube upload works regardless of encoding backend (GCE or local)
- [ ] Discord notifications work regardless of encoding backend
- [ ] CDG/TXT packaging works regardless of encoding backend
- [ ] Brand code generation works consistently
- [ ] Dropbox/Google Drive upload works (already works in both paths)
- [ ] All existing CLI functionality continues to work
- [ ] Output structure matches local CLI exactly

### Output Structure Parity

Cloud backend must produce identical output to local CLI:

```
NOMAD-XXXX - Artist - Title/
├── Artist - Title (Title).mov
├── Artist - Title (Title).jpg
├── Artist - Title (End).mov
├── Artist - Title (End).jpg
├── Artist - Title (Final Karaoke Lossless 4k).mp4
├── Artist - Title (Final Karaoke Lossless 4k).mkv
├── Artist - Title (Final Karaoke Lossy 4k).mp4
├── Artist - Title (Final Karaoke Lossy 720p).mp4
├── Artist - Title (Final Karaoke CDG).zip
├── Artist - Title (Final Karaoke TXT).zip
├── Artist - Title (Instrumental {model}).flac
├── Artist - Title (Instrumental +BV {model}).flac
├── Artist - Title (Karaoke).mp4
├── Artist - Title (Karaoke).cdg
├── Artist - Title (Karaoke).mp3
├── Artist - Title (Karaoke).lrc
├── Artist - Title (With Vocals).mp4
├── stems/
│   ├── Artist - Title (Instrumental {model}).flac
│   ├── Artist - Title (Vocals {model}).flac
│   ├── Artist - Title (Lead Vocals {model}).flac
│   ├── Artist - Title (Backing Vocals {model}).flac
│   └── ... (other stems)
├── lyrics/
│   ├── Artist - Title (Karaoke).lrc
│   ├── Artist - Title (Karaoke).ass
│   ├── Artist - Title (Karaoke).srt
│   └── ... (corrections JSONs)
├── previews/
├── visualizations/
└── styles_assets/
```

### Non-Functional Requirements
- [ ] Single Responsibility: Each stage has one job
- [ ] Open/Closed: Easy to add new encoding backends without modifying stages
- [ ] Testable: Each stage can be unit tested in isolation
- [ ] No duplicate code between paths
- [ ] Backwards compatible with existing KaraokeFinalise CLI usage

## Technical Approach

### Architecture: Stage-Based Pipeline

```
video_worker.py (VideoWorkerOrchestrator)
│
├── 1. EncodingStage (interface)
│   ├── LocalEncodingService (wraps KaraokeFinalise encoding methods)
│   └── GCEEncodingService (existing encoding_service.py)
│
├── 2. PackagingStage
│   ├── CDGPackager (extracts from KaraokeFinalise)
│   └── TXTPackager (extracts from KaraokeFinalise)
│
├── 3. DistributionStage
│   ├── YouTubeUploadService (extracts from KaraokeFinalise)
│   ├── DropboxService (existing)
│   ├── GoogleDriveService (existing)
│   └── DiscordService (extracts from KaraokeFinalise)
│
└── 4. OrganizationStage
    └── BrandCodeService (extracts from KaraokeFinalise + DropboxService)
```

### Key Design Decisions

1. **Extract, Don't Rewrite**: Pull methods out of KaraokeFinalise into services, don't rewrite from scratch
2. **Keep KaraokeFinalise for CLI**: Local CLI still uses KaraokeFinalise.process() - we extract services that it can also use
3. **Interface-Based Encoding**: EncodingStage interface allows swapping GCE/local without changing orchestration
4. **Existing Service Pattern**: Follow singleton + factory pattern already used in codebase
5. **Local CLI stays sync**: Local karaoke-gen CLI remains synchronous as it is today

### Data Flow

```
JobConfig (from Firestore)
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  VideoWorkerOrchestrator                                        │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 1. Setup: Download files, prepare directories               ││
│  │    - Download title.mov, end.mov, with_vocals.mkv           ││
│  │    - Download instrumental audio                            ││
│  │    - Prepare temp directory                                 ││
│  └─────────────────────────────────────────────────────────────┘│
│                      │                                          │
│                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 2. Packaging: CDG/TXT (if enabled) - runs BEFORE encoding   ││
│  │    Reason: CDG depends on LRC file which is available       ││
│  │    Input: LRC file, instrumental audio                      ││
│  │    Output: CDG.zip, TXT.zip, .cdg, .mp3                     ││
│  └─────────────────────────────────────────────────────────────┘│
│                      │                                          │
│                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 3. Encoding: GCE or Local (via interface)                   ││
│  │    Input: title.mov, karaoke.mov, end.mov                   ││
│  │    Output: 4K lossless, 4K lossy, 720p, MKV                 ││
│  └─────────────────────────────────────────────────────────────┘│
│                      │                                          │
│                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 4. Organization: Brand code, folder structure               ││
│  │    - Generate brand code (NOMAD-XXXX)                       ││
│  │    - Prepare full output directory structure                ││
│  └─────────────────────────────────────────────────────────────┘│
│                      │                                          │
│                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 5. Distribution: Upload to destinations                     ││
│  │    - YouTube upload (if enabled)                            ││
│  │    - Dropbox upload (if configured)                         ││
│  │    - Google Drive upload (if configured)                    ││
│  └─────────────────────────────────────────────────────────────┘│
│                      │                                          │
│                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 6. Notification: Discord, Email                             ││
│  │    Input: YouTube URL, brand code, Dropbox link             ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
Result (youtube_url, brand_code, dropbox_link, file_paths, etc.)
```

## Implementation Steps

### Phase 1: Extract Services from KaraokeFinalise (Non-Breaking) ✅ COMPLETE

These services can be used by both the cloud orchestrator AND KaraokeFinalise.

1. [x] **Create `backend/services/youtube_upload_service.py`** ✅
   - Extract YouTube upload logic from KaraokeFinalise
   - Methods: `upload_video()`, `check_duplicate()`, `delete_video()`, `truncate_title()`
   - Supports pre-loaded credentials (server-side) or client secrets file (CLI)
   - 23 unit tests with mocked YouTube API

2. [x] **Create `backend/services/discord_service.py`** ✅
   - Extract Discord notification from KaraokeFinalise
   - Methods: `post_message()`, `post_video_notification()`, `is_enabled()`
   - Simple HTTP POST to webhook with validation
   - 20 unit tests with mocked requests

3. [x] **Create `backend/services/packaging_service.py`** ✅
   - Extract CDG/TXT generation from KaraokeFinalise
   - Methods: `create_cdg_package()`, `create_txt_package()`
   - Uses lyrics_converter and CDGGenerator (existing dependencies)
   - 18 unit tests with temp files

4. [x] **Create `backend/services/local_encoding_service.py`** ✅
   - Extract encoding methods from KaraokeFinalise
   - Methods: `encode_all_formats()`, individual encoding methods
   - Hardware acceleration detection with software fallback
   - 28 unit tests with mocked subprocess

### Phase 2: Create Encoding Interface ✅ COMPLETE

5. [x] **Create `backend/services/encoding_interface.py`** ✅
   - Define ABC `EncodingBackend` with methods: `encode()`, `is_available()`, `get_status()`
   - `EncodingInput` and `EncodingOutput` dataclasses for config/results
   - Factory function `get_encoding_backend()` with "local", "gce", "auto" options

6. [x] **`LocalEncodingBackend`** ✅
   - Implements `EncodingBackend` interface
   - Wraps `LocalEncodingService` with `asyncio.to_thread()`
   - 17 unit tests

7. [x] **`GCEEncodingBackend`** ✅
   - Implements `EncodingBackend` interface
   - Wraps existing `EncodingService` (encoding_service.py)
   - Requires GCS paths in options for cloud execution
   - 6 additional unit tests

### Phase 3: Create Orchestrator ✅ COMPLETE

8. [x] **Create `backend/workers/video_worker_orchestrator.py`** ✅
   - New class that coordinates all stages
   - Replaces the branching logic in `generate_video()`
   - Methods:
     - `__init__(config, job_manager, storage, job_logger)`
     - `async run() -> OrchestratorResult`
     - `_run_packaging()` - CDG/TXT
     - `_run_encoding()` - GCE or local via EncodingBackend interface
     - `_run_organization()` - Brand code, folder structure
     - `_run_distribution()` - YouTube, Dropbox, GDrive
     - `_run_notifications()` - Discord
   - 27 unit tests (test_video_worker_orchestrator.py)

9. [x] **Update `backend/workers/video_worker.py`** ✅
   - Added `USE_NEW_ORCHESTRATOR` feature flag (default: true)
   - `generate_video()` routes to orchestrator or legacy path
   - `generate_video_orchestrated()` - new unified pipeline
   - `generate_video_legacy()` - original code for rollback
   - Legacy GCE and KaraokeFinalise paths preserved for safety

### Phase 4: Update KaraokeFinalise to Use Services (OPTIONAL)

10. [ ] **Update `karaoke_gen/karaoke_finalise/karaoke_finalise.py`**
    - Import and use the new services
    - Replace inline YouTube/Discord/CDG code with service calls
    - Keep process() working for CLI backwards compatibility
    - Services become the single source of truth
    - **NOTE**: This is optional for MVP - the orchestrator already uses the extracted services directly

### Phase 5: Testing & Validation ✅ COMPLETE

11. [x] **Add unit tests for each service** ✅
    - test_youtube_upload_service.py (23 tests)
    - test_discord_service.py (20 tests)
    - test_packaging_service.py (18 tests)
    - test_local_encoding_service.py (28 tests)
    - test_encoding_interface.py (23 tests)
    - test_video_worker_orchestrator.py (27 tests)
    - **Total: 139 new tests**

12. [x] **Full test suite passes** ✅
    - 976 tests passed (86 skipped - emulator/integration tests)
    - No regressions from changes

13. [ ] **Manual E2E testing** (After deployment)
    - [ ] GCE encoding job with YouTube upload enabled
    - [ ] Local encoding job with YouTube upload enabled
    - [ ] CLI karaoke-gen with all features
    - [ ] Job with CDG/TXT enabled
    - [ ] Verify output structure matches local CLI

## Files Created/Modified

| File | Action | Description | Status |
|------|--------|-------------|--------|
| `backend/services/youtube_upload_service.py` | Create | YouTube upload logic (~446 lines) | ✅ |
| `backend/services/discord_service.py` | Create | Discord notification service (~167 lines) | ✅ |
| `backend/services/packaging_service.py` | Create | CDG/TXT package generation (~266 lines) | ✅ |
| `backend/services/local_encoding_service.py` | Create | Local FFmpeg encoding service (~512 lines) | ✅ |
| `backend/services/encoding_interface.py` | Create | Abstract interface + backends (~418 lines) | ✅ |
| `backend/workers/video_worker_orchestrator.py` | Create | Stage orchestration logic (~550 lines) | ✅ |
| `backend/workers/video_worker.py` | Modify | Added orchestrator path + feature flag | ✅ |
| `backend/tests/test_youtube_upload_service.py` | Create | 23 unit tests | ✅ |
| `backend/tests/test_discord_service.py` | Create | 20 unit tests | ✅ |
| `backend/tests/test_packaging_service.py` | Create | 18 unit tests | ✅ |
| `backend/tests/test_local_encoding_service.py` | Create | 28 unit tests | ✅ |
| `backend/tests/test_encoding_interface.py` | Create | 23 unit tests | ✅ |
| `backend/tests/test_video_worker_orchestrator.py` | Create | 27 unit tests | ✅ |
| `karaoke_gen/karaoke_finalise/karaoke_finalise.py` | Modify | Use extracted services (optional) | Deferred |

## Testing Strategy

### Unit Tests
- **youtube_upload_service**: Mock YouTube API, test upload/delete/duplicate check
- **discord_service**: Mock requests, test webhook POST
- **packaging_service**: Use temp files, test CDG/TXT generation
- **local_encoding_service**: Mock subprocess, test FFmpeg command construction

### Integration Tests
- **video_worker_orchestrator**: Mock all services, test stage sequencing
- **video_worker**: Test with mocked orchestrator

### E2E Verification
- [ ] GCE encoding job with YouTube upload enabled → YouTube link appears
- [ ] Local encoding job with YouTube upload enabled → Same behavior
- [ ] CLI `karaoke-gen` with all features → No regression
- [ ] Job with CDG/TXT enabled → Packages generated
- [ ] Dropbox output structure → Matches local CLI exactly

## Open Questions

- [x] Should we keep KaraokeFinalise.process() or deprecate it?
  - **Decision**: Keep it for CLI backwards compatibility. It will use the new services internally.

- [x] Should local_encoding_service run FFmpeg sync or async?
  - **Decision**: Sync implementation, async wrapper via `asyncio.to_thread()` for interface compatibility.

- [x] Order of packaging vs encoding?
  - **Decision**: CDG/TXT runs BEFORE encoding (depends on LRC file, not videos). KaraokeFinalise does it this way too.

## Rollback Plan

1. The refactor is additive - new services don't replace old code until orchestrator is wired up
2. Feature flag: `USE_NEW_ORCHESTRATOR=true` to enable new code path
3. If issues found in production:
   - Set `USE_NEW_ORCHESTRATOR=false` to revert to old behavior
   - Old `generate_video()` code preserved behind feature flag
4. After 1 week stable, remove feature flag and old code

## Success Criteria

1. Job `5b78ad46` scenario (GCE + YouTube) would upload to YouTube
2. All 803+ existing tests pass
3. E2E happy path test passes
4. No regression in local CLI functionality
5. Output structure matches local CLI exactly
6. Code coverage maintained or improved

## Estimated Scope

- **Phase 1** (Extract Services): 4 new service files + tests (~400-600 lines each)
- **Phase 2** (Interface): 1 new file, 2 modifications (~100 lines)
- **Phase 3** (Orchestrator): 2 files (~300-400 lines)
- **Phase 4** (KaraokeFinalise): 1 modification (~100 lines of changes)
- **Phase 5** (Testing): Integration tests + manual verification

This is a medium-sized refactor that can be done incrementally. Each phase produces working, tested code.
