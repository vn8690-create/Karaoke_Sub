# Refactor: Unify Audio Fetcher Code

**Created:** 2025-12-20  
**Completed:** 2025-12-20  
**Priority:** MEDIUM (prevents future bugs like YouTubeProvider -> YoutubeProvider)  
**Status:** ✅ Completed

## Problem

The codebase has **two separate implementations** of flacfetch integration:
1. `karaoke_gen/audio_fetcher.py` - Used by local CLI
2. `backend/services/audio_search_service.py` - Used by cloud backend

This violates DRY and caused a bug where the backend's import wasn't updated when flacfetch renamed `YouTubeProvider` to `YoutubeProvider`.

## Current State

### Duplicated Code

| Component | Local (`audio_fetcher.py`) | Backend (`audio_search_service.py`) |
|-----------|---------------------------|-------------------------------------|
| `_get_manager()` | ✅ 40 lines | ❌ 35 lines (copy) |
| Provider setup | ✅ RED, OPS, YouTube | ❌ Same, diverged |
| `search()` | ✅ Full implementation | ❌ Similar, diverged |
| `download()` | ✅ With downloaders | ⚠️ Different, simpler |
| `AudioSearchResult` | ✅ Dataclass | ❌ Duplicate, different fields |
| `AudioDownloadResult` | ✅ (`AudioFetchResult`) | ❌ Duplicate |
| Exceptions | ✅ 4 types | ❌ 3 types, different names |

### Drift Examples
- Backend missing `raw_result` field on `AudioSearchResult`
- Backend has `index` field, local doesn't
- Backend exceptions inherit from `AudioSearchError`, local from `AudioFetcherError`
- Backend missing `UserCancelledError`
- Backend missing downloader registration (TorrentDownloader, YoutubeDownloader)

## Proposed Solution

### Option 1: Backend imports from karaoke_gen (Recommended)

The backend already depends on `karaoke_gen` (installed via `pip install -e .` in Dockerfile).

```python
# backend/services/audio_search_service.py - REFACTORED

from karaoke_gen.audio_fetcher import (
    FlacFetcher,
    AudioSearchResult,
    AudioFetchResult,
    AudioFetcherError,
    NoResultsError,
    DownloadError,
)

class AudioSearchService:
    """
    Thin wrapper around karaoke_gen.audio_fetcher.FlacFetcher.
    
    Adds backend-specific functionality:
    - Firestore serialization (to_dict/from_dict)
    - GCS integration for downloads
    - Job state management
    """
    
    def __init__(
        self,
        red_api_key: Optional[str] = None,
        red_api_url: Optional[str] = None,
        ops_api_key: Optional[str] = None,
    ):
        self._fetcher = FlacFetcher(
            red_api_key=red_api_key,
            red_api_url=red_api_url,
            ops_api_key=ops_api_key,
        )
    
    def search(self, artist: str, title: str) -> List[AudioSearchResult]:
        """Delegate to FlacFetcher.search()."""
        return self._fetcher.search(artist, title)
    
    def select_best(self, results: List[AudioSearchResult]) -> int:
        """Delegate to FlacFetcher.select_best()."""
        return self._fetcher.select_best(results)
    
    def download(
        self,
        result: AudioSearchResult,
        output_dir: str,
        output_filename: Optional[str] = None,
    ) -> AudioFetchResult:
        """Delegate to FlacFetcher.download()."""
        return self._fetcher.download(result, output_dir, output_filename)
```

### Changes Required to karaoke_gen.audio_fetcher

1. **Add `to_dict()` method to `AudioSearchResult`** - For Firestore serialization
2. **Add `from_dict()` classmethod** - For deserialization
3. **Ensure `select_best()` is a standalone method** - Currently buried in interactive flow
4. **Export all public classes from `__init__.py`**

### Changes Required to backend

1. **Remove duplicate dataclasses** - Use imports from karaoke_gen
2. **Remove duplicate `_get_manager()`** - Delegate to FlacFetcher
3. **Remove duplicate exception classes** - Use karaoke_gen exceptions
4. **Update tests** - Point to real classes, not mocks

## Benefits

1. **Single source of truth** - Bug fixes apply everywhere
2. **No more drift** - Dataclasses, exceptions stay in sync
3. **Better test coverage** - karaoke_gen has integration tests for flacfetch imports
4. **Less code to maintain** - Backend becomes thin wrapper

## Migration Steps

1. [x] Add `to_dict()` / `from_dict()` to `AudioSearchResult` in karaoke_gen
2. [x] Extract `select_best()` as standalone method in FlacFetcher
3. [x] Update karaoke_gen `__init__.py` exports (with lazy imports)
4. [x] Refactor backend to import from karaoke_gen
5. [x] Update backend tests
6. [x] Delete duplicate code from backend (~150 lines removed)
7. [x] Add integration test that catches import divergence

## Related Files

- `karaoke_gen/audio_fetcher.py` - Source of truth (keep)
- `backend/services/audio_search_service.py` - Refactor to thin wrapper
- `backend/api/routes/audio_search.py` - Update imports
- `backend/tests/test_audio_search.py` - Update tests

## Estimated Effort

- **Time:** 2-4 hours
- **Risk:** Low (well-defined changes, good test coverage)
- **Dependencies:** None

## Related Architecture Docs

- `docs/01-reference/ARCHITECTURE.md` - "LyricsTranscriber Integration" section shows similar pattern
- `docs/00-current-plan/SCALABLE-ARCHITECTURE-PLAN.md` - "Shared pipeline architecture" goal

