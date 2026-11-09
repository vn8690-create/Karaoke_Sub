# Implementation Plan: SpaCy Preloading at Container Startup

**Date**: 2026-01-08
**Status**: Ready for implementation
**Related Issue**: Job `2ccbdf6b` slow execution investigation
**Related PR**: #232 (thread-safety fix - already merged)

## Background

Job `2ccbdf6b` (ABBA - Waterloo) took 17 minutes instead of ~5 minutes expected. Investigation revealed two issues:

1. **FIXED (PR #232)**: Race condition in `LangChainBridge` where 5 parallel threads all tried to initialize the AI model simultaneously, causing 6+ minute delays.

2. **PENDING (this plan)**: SpaCy model loading takes ~63 seconds even on warm Cloud Run instances. This happens when `PhraseAnalyzer` is first instantiated during request processing.

## Problem Details

From job `2ccbdf6b` worker logs:

- `04:10:21` - "Initializing PhraseAnalyzer with language model: en_core_web_sm"
- `04:11:24` - "Initialized AnchorSequenceFinder" (63 seconds later)

Key observations:
- **SpaCy model**: `en_core_web_sm` (~14MB) is already pre-downloaded in `backend/Dockerfile.base` line 64
- **Cloud Run config**: `min-instances: 4` configured - instances are warm
- **Root cause**: SpaCy loads lazily when first needed during request processing, not at container startup
- **Cloud Run I/O**: Filesystem access on Cloud Run can be slow, causing extended load times

## Solution: Preload SpaCy at Container Startup

Load SpaCy during FastAPI lifespan handler (before accepting requests) and make it available as a singleton for reuse.

## Files to Create/Modify

### 1. NEW: `backend/services/spacy_preloader.py`

Create a new module to handle SpaCy preloading:

```python
"""SpaCy model preloader for container startup.

Loads SpaCy models at container startup to avoid slow loading during request processing.
Cloud Run filesystem I/O can cause 60+ second delays when loading SpaCy models lazily.
"""
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Singleton storage for preloaded models
_preloaded_models: dict = {}


def preload_spacy_model(model_name: str = "en_core_web_sm") -> None:
    """Preload a SpaCy model at startup.

    Args:
        model_name: The SpaCy model to load (default: en_core_web_sm)
    """
    global _preloaded_models

    if model_name in _preloaded_models:
        logger.info(f"SpaCy model '{model_name}' already preloaded")
        return

    logger.info(f"Preloading SpaCy model '{model_name}'...")
    start_time = time.time()

    try:
        import spacy
        nlp = spacy.load(model_name)
        _preloaded_models[model_name] = nlp

        elapsed = time.time() - start_time
        logger.info(f"SpaCy model '{model_name}' preloaded in {elapsed:.2f}s")
    except Exception as e:
        logger.error(f"Failed to preload SpaCy model '{model_name}': {e}")
        raise


def get_preloaded_model(model_name: str = "en_core_web_sm") -> Optional[object]:
    """Get a preloaded SpaCy model if available.

    Args:
        model_name: The SpaCy model name

    Returns:
        The preloaded SpaCy Language object, or None if not preloaded
    """
    return _preloaded_models.get(model_name)


def is_model_preloaded(model_name: str = "en_core_web_sm") -> bool:
    """Check if a SpaCy model has been preloaded."""
    return model_name in _preloaded_models
```

### 2. MODIFY: `backend/main.py`

Add SpaCy preloading to the lifespan handler. Current code is at lines 62-80.

**Add import at top of file:**
```python
from backend.services.spacy_preloader import preload_spacy_model
```

**Modify lifespan function (around line 62):**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    logger.info("Starting karaoke generation backend")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"GCS Bucket: {settings.gcs_bucket_name}")
    logger.info(f"Tracing enabled: {tracing_enabled}")

    # Preload SpaCy model to avoid 60+ second delay on first request
    try:
        preload_spacy_model("en_core_web_sm")
    except Exception as e:
        logger.warning(f"SpaCy preload failed (will load lazily): {e}")

    # Validate OAuth credentials (non-blocking)
    try:
        await validate_credentials_on_startup()
    except Exception as e:
        logger.error(f"Credential validation failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down karaoke generation backend")
```

### 3. MODIFY: `lyrics_transcriber_temp/lyrics_transcriber/correction/phrase_analyzer.py`

The `PhraseAnalyzer` class loads SpaCy in its `__init__` method. Modify to use preloaded model if available.

**Add imports at top:**
```python
# Try to import preloader (may not exist in standalone library usage)
try:
    from backend.services.spacy_preloader import get_preloaded_model
    _HAS_PRELOADER = True
except ImportError:
    _HAS_PRELOADER = False
```

**Modify `__init__` method:**
```python
def __init__(self, logger: logging.Logger, language_code: str = "en_core_web_sm"):
    self.logger = logger

    # Try to use preloaded model first (avoids 60+ second load on Cloud Run)
    if _HAS_PRELOADER:
        preloaded = get_preloaded_model(language_code)
        if preloaded is not None:
            self.logger.info(f"Using preloaded SpaCy model: {language_code}")
            self.nlp = preloaded
            return

    # Fall back to loading model directly
    self.logger.info(f"Initializing PhraseAnalyzer with language model: {language_code}")
    try:
        self.nlp = spacy.load(language_code)
    except OSError:
        # ... keep existing download fallback code ...
```

### 4. MODIFY: `lyrics_transcriber_temp/lyrics_transcriber/correction/handlers/syllables_match.py`

This file also loads SpaCy. Apply the same pattern.

**Add imports at top:**
```python
try:
    from backend.services.spacy_preloader import get_preloaded_model
    _HAS_PRELOADER = True
except ImportError:
    _HAS_PRELOADER = False
```

**Modify the SpaCy loading section in `__init__`:**
```python
# Try to use preloaded model first
if _HAS_PRELOADER:
    preloaded = get_preloaded_model("en_core_web_sm")
    if preloaded is not None:
        self.logger.info("Using preloaded SpaCy model for syllable analysis")
        self.nlp = preloaded
        # Still need to add syllables component if not present
        if "syllables" not in self.nlp.pipe_names:
            self.nlp.add_pipe("syllables", after="tagger")
        return

# ... existing loading code as fallback ...
```

## Testing Approach

### Unit Tests for Preloader

See `backend/tests/test_spacy_preloader.py` for the actual implementation. Key tests:

- `test_preload_spacy_model_loads_and_stores` - Verifies model is loaded and stored
- `test_preload_is_idempotent` - Verifies repeated calls don't reload
- `test_get_preloaded_model_returns_none_if_not_loaded` - Verifies None returned when not preloaded
- `test_preload_different_models` - Verifies multiple models can be preloaded
- `test_clear_preloaded_models` - Verifies clearing works
- `test_preload_failure_raises_exception` - Verifies errors propagate
- `test_preload_uses_default_model_name` - Verifies default is en_core_web_sm

All tests use `clear_preloaded_models()` in setup/teardown for isolation.

### Integration Verification

After deployment, check Cloud Run logs:

1. **At startup**: Look for "SpaCy model 'en_core_web_sm' preloaded in X.XXs"
2. **During job processing**: Look for "Using preloaded SpaCy model: en_core_web_sm"
3. **Timing**: Verify no 60+ second gaps in agentic correction phase

## Expected Outcomes

1. **Startup time**: SpaCy load time (~60s) moves from request processing to container startup
2. **Request latency**: First agentic correction request no longer has 60+ second SpaCy delay
3. **Visibility**: Clear logs showing preload time at startup
4. **Total job time**: Agentic correction phase should complete in ~5 minutes instead of ~17 minutes

## Implementation Steps

1. Create new worktree:
   ```bash
   cd /Users/andrew/Projects/karaoke-gen-multiagent/karaoke-gen
   git worktree add -b feat/spacy-preload ../karaoke-gen-spacy-preload origin/main
   cd ../karaoke-gen-spacy-preload
   ```

2. Create `backend/services/spacy_preloader.py`

3. Modify `backend/main.py` to add preloading in lifespan

4. Modify `lyrics_transcriber_temp/lyrics_transcriber/correction/phrase_analyzer.py`

5. Modify `lyrics_transcriber_temp/lyrics_transcriber/correction/handlers/syllables_match.py`

6. Create unit tests for the preloader

7. Run tests:
   ```bash
   make test 2>&1 | tail -n 500
   ```

8. Bump version in `pyproject.toml`

9. Follow standard PR workflow: `/docs-review` -> `/coderabbit` -> `/pr`

## Risk Considerations

- **Startup time increase**: Container startup will take ~60s longer, but this happens once per container lifecycle, not per request
- **Memory usage**: SpaCy model (~50MB in memory) will persist for container lifetime - acceptable tradeoff
- **Import error handling**: Graceful fallback if preloader module unavailable (library standalone use case)

## Related Files Reference

- `backend/Dockerfile.base:64` - SpaCy model download at build time
- `infrastructure/cloudrun.ts` - Cloud Run configuration (min-instances: 4)
- `docs/LESSONS-LEARNED.md` - Contains thread-safety lesson from related fix
