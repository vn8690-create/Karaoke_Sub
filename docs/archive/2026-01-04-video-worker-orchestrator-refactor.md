# Video Worker Orchestrator Refactor - 2026-01-04

## Summary

Major refactor to unify video generation pipeline with a new VideoWorkerOrchestrator. This resolves the GCE vs KaraokeFinalise code path divergence that caused features like YouTube upload, Discord notifications, and CDG/TXT packaging to be missing from the GCE encoding path.

## Problem

Job 5b78ad46 completed successfully via GCE encoding but had no YouTube URL. Investigation revealed:

1. The GCE encoding path was a completely separate code branch
2. When `USE_GCE_ENCODING=true`, the worker triggered GCE encoding and returned immediately
3. This bypassed the entire `KaraokeFinalise` class which contained:
   - YouTube upload logic
   - Discord webhook notifications
   - CDG/TXT package generation
   - Dropbox/Google Drive uploads

The root cause wasn't a bug in any individual feature - it was an architectural issue where alternative implementations didn't share common post-processing stages.

## Solution

Created a stage-based orchestrator pattern:

```
VideoWorkerOrchestrator
├── Stage 1: Packaging (CDG, TXT)
├── Stage 2: Encoding (Local or GCE - swappable)
├── Stage 3: Organization (file paths, structure)
├── Stage 4: Distribution (Dropbox, GDrive, YouTube)
└── Stage 5: Notifications (Discord)
```

The orchestrator always runs all stages. Only the encoding implementation varies based on backend selection.

## Changes

### New Service Modules

| File | Lines | Purpose |
|------|-------|---------|
| `youtube_upload_service.py` | ~445 | YouTube OAuth and upload |
| `discord_service.py` | ~172 | Discord webhook notifications |
| `packaging_service.py` | ~287 | CDG/TXT package generation |
| `local_encoding_service.py` | ~590 | FFmpeg encoding on Cloud Run |
| `encoding_interface.py` | ~418 | Abstract interface + GCE backend |
| `video_worker_orchestrator.py` | ~628 | Stage coordination |

### Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_youtube_upload_service.py` | 25 | OAuth, upload, error handling |
| `test_discord_service.py` | 18 | Webhook formatting, delivery |
| `test_packaging_service.py` | 22 | CDG/TXT generation |
| `test_local_encoding_service.py` | 24 | FFmpeg encoding variants |
| `test_encoding_interface.py` | 23 | Interface + GCE backend |
| `test_video_worker_orchestrator.py` | 27 | Full pipeline, stages |
| **Total** | **139** | |

### video_worker.py Updates

- Added `USE_NEW_ORCHESTRATOR` feature flag (default: `true`)
- `generate_video()` routes to orchestrator or legacy path
- Legacy code preserved as `generate_video_legacy()` for rollback
- New `generate_video_orchestrated()` builds config and runs orchestrator

## Feature Flag

```bash
# Enable new orchestrator (default)
USE_NEW_ORCHESTRATOR=true

# Rollback to legacy behavior
USE_NEW_ORCHESTRATOR=false
```

## Key Design Decisions

1. **Stage-based orchestration**: Each stage is independent and testable
2. **Strategy pattern for encoding**: `EncodingBackend` interface with local and GCE implementations
3. **Lazy service loading**: Services instantiated only when needed via `_get_*()` methods
4. **Dataclass configs**: `OrchestratorConfig` and `OrchestratorResult` for clear contracts
5. **Feature flag default true**: New code active immediately since tests are comprehensive

## Testing Notes

- All 976 existing tests continue to pass
- 139 new tests added across 6 test files
- E2E verification: Jobs 501258e1 and d21e6ef0 successfully processed through new pipeline
- Both jobs reached `awaiting_instrumental_selection` as expected (requires user input to complete)

## PR

- PR #182: https://github.com/nomadkaraoke/karaoke-gen/pull/182
- Merged: 2026-01-04
- Version: 0.89.0

## Lessons Learned

See [LESSONS-LEARNED.md](../LESSONS-LEARNED.md#alternative-code-paths-must-implement-all-features) for the key architectural lesson about alternative code paths.
