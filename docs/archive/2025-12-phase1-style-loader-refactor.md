# Style Loader Consolidation Refactor

## Date: December 2024

## The Problem

During development of the cloud backend, style loading logic (loading custom backgrounds, fonts, and video styling from JSON configuration) was implemented separately in multiple places:

| Location | Purpose |
|----------|---------|
| `karaoke_gen/config.py` | Local CLI style loading |
| `backend/workers/style_helper.py` | Backend worker style loading (StyleConfig class) |
| `backend/workers/render_video_worker.py` | Final video render style loading |
| `backend/api/routes/review.py` | Preview video style loading |
| `core.py` | Old Modal serverless style loading |

Each of these had its own:
- Default style dictionaries (slightly different values!)
- Asset key mappings (`karaoke_background` → `('karaoke', 'background_image')`)
- GCS download and path update logic (for the backend)

### The Bug This Caused

In PR #[N], we discovered that preview videos in the remote backend were showing black backgrounds instead of the custom background images configured via `--style_params_json`. 

**Root cause**: The `review.py` endpoint for preview generation was using `_create_minimal_styles_json()` which hardcoded black backgrounds, while `render_video_worker.py` had the correct logic to download custom styles from GCS.

To fix this, we had to **duplicate** the correct logic from `render_video_worker.py` into `review.py` — making the duplication problem worse.

## What We Did

Created a unified `karaoke_gen/style_loader.py` module that serves as the **single source of truth** for:

### 1. Default Style Configurations
```python
DEFAULT_INTRO_STYLE = {...}
DEFAULT_END_STYLE = {...}
DEFAULT_KARAOKE_STYLE = {...}
DEFAULT_CDG_STYLE = {...}
```

### 2. Asset Key Mappings
```python
ASSET_KEY_MAPPINGS = {
    "karaoke_background": ("karaoke", "background_image"),
    "intro_background": ("intro", "background_image"),
    "font": [("intro", "font"), ("karaoke", "font_path"), ("end", "font")],
    # ... etc
}
```

### 3. Core Functions
- `load_style_params_from_file()` - Load from local JSON file
- `load_styles_from_gcs()` - Download from GCS and update paths
- `update_asset_paths()` - Update paths in style dict to local files
- `get_intro_format()`, `get_end_format()`, `get_karaoke_format()` - Extract section with defaults

### Updated Files
- `karaoke_gen/config.py` - Now delegates to `style_loader`
- `backend/workers/style_helper.py` - `StyleConfig` wraps `style_loader`
- `backend/workers/render_video_worker.py` - Uses `load_styles_from_gcs()`
- `backend/api/routes/review.py` - Uses `load_styles_from_gcs()`

## Benefits

1. **Bug Prevention**: Asset mappings and defaults are defined once — no more inconsistencies
2. **Maintainability**: Style changes only need to be made in one place
3. **Testability**: Tests can verify the unified module directly via `ASSET_KEY_MAPPINGS`
4. **Clarity**: Clear separation between local file loading and GCS downloading

## What's NOT Refactored (Future Work)

The style loader consolidation was a **targeted refactor** addressing an immediate pain point. A larger architectural refactor could address:

### 1. Video Generation Path Divergence

Currently:
- **Local CLI**: `LyricsProcessor.transcribe_lyrics()` → orchestrates everything including video
- **Backend**: Workers call `OutputGenerator` directly, bypassing `LyricsProcessor` for video

A unified approach would have both paths use the same abstraction.

### 2. LyricsProcessor Decomposition

`LyricsProcessor` currently does:
- Lyrics fetching
- Transcription orchestration  
- Video generation coordination
- File output management

This could be split into more focused, composable components.

### 3. Pipeline Architecture

Rather than having separate code paths, both local and remote could share a "pipeline" abstraction:
```
AudioInput → Separation → Transcription → Correction → VideoRender → Output
```

Each stage would be independently testable and could run locally or remotely.

## When to Do the Full Refactor

**Recommended: After completing feature parity between local and remote**

Specifically:
1. ✅ Basic job submission and processing working
2. ✅ Style configuration working end-to-end (this refactor addressed it)
3. ⬜ All CLI features available in remote mode (skip-separation, edit-lyrics, etc.)
4. ⬜ CDG generation working in remote mode
5. ⬜ Final video packaging/encoding working
6. ⬜ Notification system working (Discord, email)

**Why wait?**
- The current architecture works — it's just not ideal
- Refactoring now could introduce regressions in working features
- Understanding all use cases will inform better abstractions
- Feature parity should take priority for user value

**When to start:**
- When adding a new feature requires touching 3+ places due to duplication
- When a bug is caused by architectural inconsistency (like the style bug)
- When onboarding new contributors becomes difficult due to complexity
- Once all remote features match local, before adding major new capabilities

## Files Reference

```
karaoke_gen/
├── style_loader.py    # NEW: Unified style loading module
├── config.py          # UPDATED: Delegates to style_loader
└── ...

backend/
├── workers/
│   ├── style_helper.py         # UPDATED: StyleConfig wraps style_loader
│   └── render_video_worker.py  # UPDATED: Uses load_styles_from_gcs()
└── api/routes/
    └── review.py               # UPDATED: Uses load_styles_from_gcs()
```
