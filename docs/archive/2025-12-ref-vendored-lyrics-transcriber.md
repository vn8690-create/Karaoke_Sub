# Vendored lyrics-transcriber

## Overview

The `lyrics-transcriber` package is temporarily vendored into this repository at `lyrics_transcriber_temp/`. This allows us to develop and test changes to both `karaoke-gen` and `lyrics-transcriber` together before pushing changes upstream.

## Current Setup

Instead of depending on `lyrics-transcriber` from PyPI, the package code is:

1. **Bundled directly** into `karaoke-gen` via the `packages` directive in `pyproject.toml`
2. **Dependencies included** - all deps from `lyrics-transcriber` are added to `karaoke-gen`'s dependencies

### pyproject.toml Configuration

```toml
packages = [
    { include = "karaoke_gen" },
    { include = "lyrics_transcriber", from = "lyrics_transcriber_temp" }
]
include = [
    "lyrics_transcriber_temp/lyrics_transcriber/frontend/web_assets",
    "lyrics_transcriber_temp/lyrics_transcriber/frontend/web_assets/**/*",
    "lyrics_transcriber_temp/lyrics_transcriber/output/fonts/*",
    "lyrics_transcriber_temp/lyrics_transcriber/output/cdgmaker/images/*",
    "lyrics_transcriber_temp/lyrics_transcriber/output/cdgmaker/transitions/*"
]
```

### How It Works

| Scenario | Behavior |
|----------|----------|
| `poetry install` | Installs vendored code from `./lyrics_transcriber_temp/` |
| `poetry build` | Bundles both `karaoke_gen/` and `lyrics_transcriber/` into the wheel |
| PyPI publish | Package is self-contained, no external `lyrics-transcriber` dependency |
| Imports | `from lyrics_transcriber import ...` works normally |

## Why Vendored?

This approach was chosen because:

1. **Rapid iteration** - Changes to both packages can be tested together without publishing
2. **PyPI compatibility** - Path dependencies (`{ path = "..." }`) don't work with PyPI
3. **Self-contained** - Users installing from PyPI get everything they need

## Un-vendoring Instructions

When you're ready to push changes back to the upstream `lyrics-transcriber` repository:

### Step 1: Push Changes Upstream

1. Copy changes from `lyrics_transcriber_temp/` back to the upstream repo
2. Publish a new version of `lyrics-transcriber` to PyPI (e.g., `0.83.0`)

### Step 2: Update pyproject.toml

Replace the vendored setup with a PyPI dependency:

```toml
# Change packages back to single package:
packages = [{ include = "karaoke_gen" }]

# Remove the include directive for lyrics_transcriber assets (delete these lines):
# include = [
#     "lyrics_transcriber_temp/lyrics_transcriber/...",
#     ...
# ]
```

In `[tool.poetry.dependencies]`, replace the vendored dependencies comment block:

```toml
# Remove these lines:
# # lyrics-transcriber is vendored in lyrics_transcriber_temp/ and included via packages
# # Dependencies from vendored lyrics_transcriber:
# python-slugify = ">=8"
# syrics = ">=0"
# ... (all the vendored deps)

# Add back the PyPI dependency:
lyrics-transcriber = ">=0.83.0"  # Use the version you published
```

### Step 3: Update Dockerfiles

In `backend/Dockerfile` and `backend/Dockerfile.base`, remove the line:

```dockerfile
COPY lyrics_transcriber_temp /app/lyrics_transcriber_temp
```

### Step 4: Remove Vendored Code

```bash
rm -rf lyrics_transcriber_temp/
```

### Step 5: Update Lock File

```bash
poetry lock
poetry install
```

### Step 6: Test

```bash
# Verify imports still work
poetry run python -c "from lyrics_transcriber import LyricsTranscriber; print('OK')"

# Run tests
poetry run pytest tests/unit/ -v
```

### Step 7: Commit

```bash
git add -A
git commit -m "Remove vendored lyrics-transcriber, use PyPI version 0.83.0"
```

## Docker Build

The Docker build uses a two-stage approach:

### Base Image (`Dockerfile.base`)
- Contains system deps (ffmpeg, sox) and ALL Python dependencies
- Installs from `pyproject.toml` via `pip install -e .`
- Rebuilt only when `poetry.lock` changes (CI detects this automatically)

### App Image (`Dockerfile`)  
- Built on top of base image
- Copies fresh application code (`karaoke_gen/`, `lyrics_transcriber_temp/`, `backend/`)
- Runs `pip install -e .` (fast - deps already installed in base)
- **Build time: ~1-2 minutes**

### Updating Dependencies

When you change `pyproject.toml` dependencies:

```bash
# 1. Update lock file and install locally
poetry lock && poetry install

# 2. Rebuild base image (CI does this automatically when poetry.lock changes)
gcloud builds submit --config=cloudbuild-base.yaml --project=nomadkaraoke
```

When un-vendoring, remove the `COPY lyrics_transcriber_temp` line from both Dockerfiles.

## Potential Conflicts

If a user installs both `karaoke-gen` (with vendored code) and `lyrics-transcriber` from PyPI separately, they'll have two `lyrics_transcriber` modules which could conflict. This is acceptable for now since:

- Most users install only `karaoke-gen`
- This is a temporary arrangement until upstream is updated
