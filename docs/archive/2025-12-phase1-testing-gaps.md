# Backend Testing Gaps Analysis

**Created:** 2025-12-22  
**Updated:** 2025-12-22  
**Status:** Mostly Complete ✅  
**Priority:** High

## Background

During end-to-end testing of the remote karaoke-gen CLI, multiple bugs were discovered:

### Bug #1: Missing `extra_info` Attribute (Fixed 2025-12-22)
```
Error: 'AudioSearchResult' object has no attribute 'extra_info'
```

This bug existed in production code but wasn't caught by automated tests because the remote download code path had no test coverage.

### Bug #2: Missing `gcs_path` Parameter in API Route (Fixed 2025-12-22)
```
Error handling audio selection: Error selecting audio: {'detail': "Download failed: [Errno 2] No such file or directory: '/var/lib/transmission-daemon/downloads/Avril Lavigne - Unwanted (Album, 2002, CD, 16bit, RED).flac'"}
```

The backend API route `_download_and_start_processing` in `audio_search.py` was not passing the `gcs_path` parameter to `audio_search_service.download()`. Without this parameter, the remote `flacfetch` VM would download the file locally but not upload it to GCS. The backend then tried to open the VM's local path (`/var/lib/transmission-daemon/downloads/...`) which doesn't exist on Cloud Run.

**Why this wasn't caught:**
- Service-level tests for `AudioSearchService.download()` existed and tested `gcs_path` parameter
- But the **API route caller** (`_download_and_start_processing`) that invokes this service was never tested
- Tests validated the service layer but not the route layer's usage of the service

## Root Cause Analysis

1. **Missing remote code path tests**: The download routing logic for `provider in ["RED", "OPS"]` was never exercised
2. **State not set up for remote scenario**: Tests never configured `_remote_search_id` and `_remote_client` together  
3. **`FlacfetchClient` had zero tests**: The entire HTTP client was untested
4. **Tests mocked at wrong level**: Tests mocked `service._fetcher` completely, bypassing the routing logic
5. **API route orchestration untested**: The `_download_and_start_processing` function in `api/routes/audio_search.py` orchestrates multiple services but had no dedicated tests verifying correct parameter passing

## Services Testing Status

### ✅ Fully Tested

| Service | Test File | Test Count | Notes |
|---------|-----------|------------|-------|
| `credential_manager.py` | `test_credential_manager.py` | 27 | Good coverage |
| `job_manager.py` | `test_job_manager.py` | 15 | Good coverage |
| `flacfetch_client.py` | `test_flacfetch_client.py` | 26 | **Added 2025-12-22** |
| `audio_search_service.py` | `test_audio_search.py` | 43 | **+11 tests 2025-12-22** |
| `api/routes/audio_search.py` | `test_audio_search.py` | 4 | **API route tests added 2025-12-22** |
| `storage_service.py` | `test_storage_service.py` | 17 | **Added 2025-12-22** |
| `audio_analysis_service.py` | `test_audio_analysis_service.py` | 9 | **Added 2025-12-22** |
| `audio_editing_service.py` | `test_audio_editing_service.py` | 13 | **Added 2025-12-22** |
| `youtube_service.py` | `test_youtube_service.py` | 12 | **Added 2025-12-22** |
| `dropbox_service.py` | `test_dropbox_service.py` | 14 | **Added 2025-12-22** |
| `gdrive_service.py` | `test_gdrive_service.py` | 13 | **Added 2025-12-22** |

### ❌ No Dedicated Test File (Lower Priority)

| Service | Priority | Complexity | Notes |
|---------|----------|------------|-------|
| `rclone_service.py` | Low | Low | Wrapper around rclone CLI |
| `firestore_service.py` | Low | Medium | Firestore operations |
| `auth_service.py` | Low | Low | Auth utilities |
| `job_logging.py` | Low | Low | Logging utilities |
| `tracing.py` | Low | Low | OpenTelemetry setup |
| `worker_service.py` | Medium | High | Worker orchestration |

## Implementation Plan

### Phase 1: Core Audio Services (High Priority) ✅

- [x] `flacfetch_client.py` - Remote audio download client
- [x] `audio_search_service.py` - Remote download path tests

### Phase 2: Audio Processing Services (High Priority) ✅

- [x] `audio_analysis_service.py` - Waveform analysis, peak detection
- [x] `audio_editing_service.py` - Mute regions, audio manipulation

### Phase 3: Distribution Services (Medium Priority) ✅

- [x] `youtube_service.py` - YouTube credential management
- [x] `dropbox_service.py` - Dropbox upload API
- [x] `gdrive_service.py` - Google Drive upload API
- [x] `storage_service.py` - GCS operations

### Phase 4: Infrastructure Services (Low Priority)

- [ ] `worker_service.py` - Worker orchestration
- [ ] `firestore_service.py` - Firestore operations
- [ ] `rclone_service.py` - Rclone wrapper
- [ ] `auth_service.py` - Auth utilities
- [ ] `job_logging.py` - Logging
- [ ] `tracing.py` - Tracing

## Test Coverage Goals

- **Target:** 80%+ line coverage for high-priority services
- **Minimum:** Key code paths tested (happy path + error handling)
- **Integration:** Mock external APIs (YouTube, Dropbox, GCS, etc.)

## Testing Patterns to Follow

### 1. Mock External Services

```python
@patch("backend.services.youtube_service.build")
def test_upload_video(self, mock_build):
    mock_service = Mock()
    mock_build.return_value = mock_service
    # ...
```

### 2. Test Error Handling

```python
def test_upload_handles_network_error(self):
    with pytest.raises(ServiceError) as exc_info:
        service.upload(...)
    assert "network" in str(exc_info.value).lower()
```

### 3. Test State Transitions

```python
def test_download_routes_to_remote_for_torrent_providers(self):
    service._remote_client = Mock()
    service._remote_search_id = "search_123"
    service._cached_results = [result_with_provider_red]
    
    service.download(0, "/tmp")
    
    service._download_remote.assert_called_once()
```

### 4. Verify Request/Response Format

```python
def test_search_sends_correct_payload(self):
    # ...
    call_args = mock_client.post.call_args
    assert call_args.kwargs["json"] == {"artist": "ABBA", "title": "Waterloo"}
```

### 5. Test API Route Orchestration (CRITICAL)

**Key Lesson from Bug #2:** Service-level tests are not sufficient. API routes that orchestrate multiple services must also be tested to verify correct parameter passing.

```python
class TestAudioSearchApiRouteDownload:
    """Tests for the _download_and_start_processing function in audio_search.py."""
    
    @pytest.mark.asyncio
    async def test_remote_download_passes_gcs_path(self):
        """Verify that gcs_path is passed to audio_search_service.download for torrent providers."""
        # Mock the audio_search_service.download to capture the call
        mock_audio_search_service = Mock()
        mock_audio_search_service.download.return_value = AudioDownloadResult(
            filepath="gs://bucket/path.flac", artist="A", title="T", provider="RED", quality="FLAC"
        )
        
        result = await _download_and_start_processing(job_id="job1", ...)
        
        # Assert gcs_path was passed
        call_kwargs = mock_audio_search_service.download.call_args.kwargs
        assert call_kwargs.get('gcs_path') is not None  # CRITICAL check!
        assert call_kwargs['gcs_path'].startswith('uploads/')
```

This pattern ensures that when service APIs change or new required parameters are added, API route tests will catch missing parameter passing.

## Files Changed

**Bug Fixes:**
- `backend/services/audio_search_service.py` - Removed `extra_info` attribute access (Bug #1)
- `backend/api/routes/audio_search.py` - Added `gcs_path` parameter to `audio_search_service.download()` call (Bug #2)

**Tests Added (2025-12-22):**
- `backend/tests/test_audio_search.py` - +11 tests for service + 4 tests for API route orchestration
- `backend/tests/test_flacfetch_client.py` - 26 new tests (new file)
- `backend/tests/test_storage_service.py` - 17 new tests (new file)
- `backend/tests/test_audio_analysis_service.py` - 9 new tests (new file)
- `backend/tests/test_audio_editing_service.py` - 13 new tests (new file)
- `backend/tests/test_youtube_service.py` - 12 new tests (new file)
- `backend/tests/test_dropbox_service.py` - 14 new tests (new file)
- `backend/tests/test_gdrive_service.py` - 13 new tests (new file)

**Total New Tests:** 119 tests added

**Version:** 0.74.3

## Running Tests

```bash
# All backend tests
cd backend && python -m pytest tests/ -v

# Specific service tests
python -m pytest tests/test_flacfetch_client.py -v
python -m pytest tests/test_audio_search.py -v

# With coverage
python -m pytest tests/ -v --cov=services --cov-report=term-missing
```

## Notes for Future Sessions

When continuing this work:

1. **Test API route orchestration, not just services**: Bug #2 showed that service tests alone don't catch parameter passing bugs at the route level
2. Distribution services need OAuth mocking - check existing patterns in `test_credential_manager.py`
3. Use `pytest.mark.asyncio` for async service methods
4. Follow existing test patterns in `test_flacfetch_client.py` for HTTP client mocking
5. **For remote operations**: Always verify that `gcs_path` parameters are passed when code paths involve remote VM operations

## Lessons Learned

### Testing Layers Matter

```
┌─────────────────────────────────────────────────────────────────┐
│  API Routes (api/routes/*.py)                                   │
│  └─> These orchestrate services and MUST be tested separately  │
│      to verify correct parameter passing                        │
├─────────────────────────────────────────────────────────────────┤
│  Services (services/*.py)                                       │
│  └─> Business logic with proper unit tests                      │
├─────────────────────────────────────────────────────────────────┤
│  Clients (FlacfetchClient, etc.)                                │
│  └─> HTTP/external API interactions                             │
└─────────────────────────────────────────────────────────────────┘
```

Bug #2 was missed because:
- `FlacfetchClient` tests ✅ verified `gcs_path` is sent in HTTP requests
- `AudioSearchService` tests ✅ verified `gcs_path` is passed to client
- **API route tests ❌ didn't exist** - so nobody verified the route passes `gcs_path` to the service

Now we have `TestAudioSearchApiRouteDownload` to catch this class of bugs.

