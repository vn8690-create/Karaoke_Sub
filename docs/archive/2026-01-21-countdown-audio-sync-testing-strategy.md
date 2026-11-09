# Countdown Audio Sync - Testing Strategy Plan

## Problem Summary

The countdown padding sync bug has been fixed and re-introduced multiple times:
- **PR #35** (Dec 19) - Fixed by storing `lyrics_metadata.has_countdown_padding` in job state
- **Commit 989abeaf + PR #64** (Dec 27) - Re-broken by deferring countdown to render phase without updating state sync

**Root cause:** `render_video_worker.py` adds countdown but doesn't update `job.state_data.lyrics_metadata.has_countdown_padding`, so `video_worker.py` doesn't know to pad the instrumental.

## Testing Strategy Overview

We need **multiple layers of tests** to catch this regression at different points:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TEST PYRAMID                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Layer 4: E2E / Acceptance                                          │
│  ─────────────────────────                                          │
│  • Verify final video has correct audio sync (< 100ms drift)        │
│  • Run against real backend or emulators                            │
│  • Slow but catches integration issues                              │
│                                                                      │
│  Layer 3: Pipeline Integration                                       │
│  ─────────────────────────────                                       │
│  • Test full worker sequence: lyrics → render → video               │
│  • Verify state propagation between workers                         │
│  • Use emulators for Firestore                                      │
│                                                                      │
│  Layer 2: Contract Tests                                            │
│  ───────────────────────                                            │
│  • Verify render_video_worker WRITES countdown state                │
│  • Verify video_worker READS and USES countdown state               │
│  • Fast, mock-based, run on every PR                                │
│                                                                      │
│  Layer 1: Unit Tests                                                │
│  ──────────────────                                                 │
│  • Test CountdownProcessor logic                                    │
│  • Test state update function                                       │
│  • Test each code path in isolation                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Unit Tests

### 1.1 Test: render_video_worker updates countdown state

**File:** `backend/tests/test_workers.py` (extend `TestRenderVideoWorkerCountdownPadding`)

**Purpose:** Verify that when countdown is added, state is updated

```python
class TestRenderVideoWorkerCountdownStateSync:
    """Tests that render_video_worker correctly updates job state when countdown is added."""

    def test_updates_lyrics_metadata_when_countdown_added(self):
        """When CountdownProcessor.process() returns padding_added=True,
        job.state_data.lyrics_metadata.has_countdown_padding must be set to True."""

    def test_updates_countdown_padding_seconds_in_state(self):
        """When countdown is added, the padding_seconds value must be stored."""

    def test_no_state_update_when_countdown_not_needed(self):
        """When song starts after 3 seconds, has_countdown_padding stays False."""
```

### 1.2 Test: video_worker reads and uses countdown state

**File:** `backend/tests/test_workers.py` (extend `TestVideoWorker`)

**Purpose:** Verify video_worker correctly reads state and passes to encoding

```python
class TestVideoWorkerCountdownSync:
    """Tests that video_worker reads countdown state and applies instrumental padding."""

    def test_reads_countdown_padding_from_lyrics_metadata(self):
        """When has_countdown_padding=True, countdown_padding_seconds is extracted."""

    def test_passes_countdown_to_karaoke_finalise(self):
        """Legacy path: countdown_padding_seconds passed to KaraokeFinalise constructor."""

    def test_passes_countdown_to_orchestrator(self):
        """Orchestrator path: countdown info passed through encoding input."""

    def test_passes_countdown_to_gce_encoding(self):
        """GCE path: countdown_padding_seconds included in encoding_config."""
```

### 1.3 Test: All encoding paths handle countdown padding

**File:** `backend/tests/test_encoding_countdown.py` (new file)

```python
class TestEncodingCountdownPadding:
    """Tests that all encoding backends correctly pad instrumental when countdown present."""

    def test_local_encoding_pads_instrumental(self):
        """LocalEncodingService pads instrumental when countdown_padding_seconds set."""

    def test_gce_encoding_config_includes_countdown(self):
        """GCE encoding config dict includes countdown_padding_seconds field."""

    def test_karaoke_finalise_pads_instrumental(self):
        """KaraokeFinalise.remux_with_instrumental() creates padded instrumental."""
```

---

## Layer 2: Contract Tests

**Purpose:** Ensure the data contract between workers is maintained. These tests explicitly verify the "handshake" between components.

### 2.1 State Contract Test

**File:** `backend/tests/test_countdown_state_contract.py` (new file)

```python
class TestCountdownStateContract:
    """
    Contract tests for countdown padding state synchronization.

    These tests verify the data contract between:
    - render_video_worker (WRITER) - must set has_countdown_padding after adding countdown
    - video_worker (READER) - must read and use has_countdown_padding

    If either side changes its behavior, these tests will fail,
    alerting us to a potential sync issue.
    """

    # Contract: State schema
    def test_lyrics_metadata_schema_has_countdown_fields(self):
        """lyrics_metadata must have has_countdown_padding (bool) and countdown_padding_seconds (float)."""

    # Contract: Writer (render_video_worker)
    def test_render_video_worker_sets_countdown_state_when_padding_added(self):
        """WRITER CONTRACT: render_video_worker MUST call update_state_data with countdown info."""

    # Contract: Reader (video_worker)
    def test_video_worker_reads_countdown_state(self):
        """READER CONTRACT: video_worker MUST read lyrics_metadata.has_countdown_padding."""

    def test_video_worker_applies_padding_when_state_true(self):
        """READER CONTRACT: video_worker MUST pass countdown_padding_seconds when state is True."""

    # Contract: End-to-end state flow
    def test_state_written_by_render_can_be_read_by_video(self):
        """State written by render_video_worker can be correctly read by video_worker."""
```

### 2.2 Encoding Interface Contract

**File:** `backend/tests/test_encoding_interface_contract.py` (new file)

```python
class TestEncodingInterfaceContract:
    """Contract tests for encoding interface countdown support."""

    def test_encoding_input_supports_countdown_field(self):
        """EncodingInput dataclass must have countdown_padding_seconds field."""

    def test_all_backends_accept_countdown_parameter(self):
        """All encoding backends (local, GCE) must accept countdown parameter."""
```

---

## Layer 3: Pipeline Integration Tests

**Purpose:** Test the full worker sequence with real Firestore emulator to verify state flows correctly.

### 3.1 Worker Pipeline Test

**File:** `backend/tests/emulator/test_countdown_pipeline_integration.py` (new file)

```python
class TestCountdownPipelineIntegration:
    """
    Integration tests for countdown padding across the full worker pipeline.

    Uses Firestore emulator to test real state updates.
    Mocks only external services (Modal, AudioShake, etc.)
    """

    @pytest.fixture
    def job_with_early_start_song(self, db_client):
        """Create a job where lyrics start within 3 seconds (needs countdown)."""

    @pytest.fixture
    def job_with_late_start_song(self, db_client):
        """Create a job where lyrics start after 3 seconds (no countdown needed)."""

    async def test_countdown_state_flows_through_pipeline(self, job_with_early_start_song):
        """
        Full pipeline test:
        1. Run lyrics_worker (sets has_countdown_padding=False due to deferred countdown)
        2. Run render_video_worker (adds countdown, MUST set has_countdown_padding=True)
        3. Verify state_data has correct countdown info
        4. Run video_worker (MUST read state and pad instrumental)
        5. Verify countdown_padding_seconds was passed to encoding
        """

    async def test_no_countdown_state_when_not_needed(self, job_with_late_start_song):
        """When song doesn't need countdown, state remains False throughout pipeline."""

    async def test_orchestrator_path_receives_countdown(self, job_with_early_start_song):
        """Orchestrator path correctly receives and uses countdown info."""

    async def test_gce_encoding_path_receives_countdown(self, job_with_early_start_song):
        """GCE encoding path correctly receives countdown in config."""
```

### 3.2 State Persistence Test

**File:** `backend/tests/emulator/test_countdown_state_persistence.py` (new file)

```python
class TestCountdownStatePersistence:
    """Tests that countdown state survives worker boundaries."""

    async def test_state_persists_between_render_and_video_workers(self):
        """State set by render_video_worker is readable by video_worker."""

    async def test_state_survives_job_reload(self):
        """State persists when job is reloaded from Firestore."""
```

---

## Layer 4: E2E / Acceptance Tests

**Purpose:** Verify the actual output - that the final video has correctly synced audio.

### 4.1 Audio Sync Verification Test

**File:** `backend/tests/e2e/test_countdown_audio_sync.py` (new file)

```python
class TestCountdownAudioSync:
    """
    E2E tests that verify actual audio synchronization in generated videos.

    These tests generate real (short) videos and verify the audio offset.
    Uses ffprobe to analyze video/audio streams.
    """

    @pytest.fixture
    def short_test_audio_early_start(self, tmp_path):
        """Generate a short test audio file where 'lyrics' start at 0.5 seconds."""
        # Use ffmpeg to create a test audio file with a distinctive marker

    def test_countdown_video_has_correct_instrumental_offset(self, short_test_audio_early_start):
        """
        Given: Audio where content starts at 0.5 seconds
        When: Full pipeline runs with countdown enabled
        Then: Final video has instrumental starting at 3.5 seconds (0.5 + 3.0 padding)

        Verification:
        - Use ffprobe to get audio stream start time
        - Verify offset matches expected padding
        """

    def test_no_countdown_video_has_zero_offset(self):
        """
        Given: Audio where content starts at 4.0 seconds
        When: Full pipeline runs (no countdown needed)
        Then: Final video has instrumental starting at 0 seconds (no padding)
        """
```

### 4.2 CLI E2E Test

**File:** `tests/integration/test_countdown_cli_e2e.py` (new file)

```python
class TestCountdownCLIE2E:
    """E2E tests for countdown sync in CLI workflow."""

    def test_cli_produces_synced_output(self, tmp_path):
        """Running full CLI pipeline produces video with correct sync."""
```

---

## Implementation Order

### Phase 1: Contract Tests (catches regression immediately)
1. `test_countdown_state_contract.py` - Verify writer/reader contract
2. `test_encoding_interface_contract.py` - Verify encoding interface

### Phase 2: Unit Tests (detailed coverage)
3. Extend `test_workers.py` with state sync tests
4. Create `test_encoding_countdown.py`

### Phase 3: Integration Tests (verify full flow)
5. `test_countdown_pipeline_integration.py` - Full worker pipeline
6. `test_countdown_state_persistence.py` - State survives boundaries

### Phase 4: E2E Tests (acceptance criteria)
7. `test_countdown_audio_sync.py` - Actual audio verification

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `backend/tests/test_countdown_state_contract.py` | Create | Contract tests for state sync |
| `backend/tests/test_encoding_interface_contract.py` | Create | Contract tests for encoding |
| `backend/tests/test_encoding_countdown.py` | Create | Unit tests for encoding paths |
| `backend/tests/test_workers.py` | Extend | Add state sync unit tests |
| `backend/tests/emulator/test_countdown_pipeline_integration.py` | Create | Integration tests with emulator |
| `backend/tests/emulator/test_countdown_state_persistence.py` | Create | State persistence tests |
| `backend/tests/e2e/test_countdown_audio_sync.py` | Create | Audio sync verification |
| `tests/integration/test_countdown_cli_e2e.py` | Create | CLI E2E tests |

---

## Test Execution

```bash
# Run all countdown-related tests
pytest -v -k "countdown" backend/tests/ tests/

# Run contract tests only (fast, every PR)
pytest -v backend/tests/test_countdown_state_contract.py

# Run integration tests (requires emulators)
make emulators-start && pytest -v backend/tests/emulator/test_countdown_pipeline_integration.py

# Run E2E tests (slow, on-demand)
pytest -v backend/tests/e2e/test_countdown_audio_sync.py
```

---

## Key Test Assertions

The tests must verify these critical invariants:

1. **INVARIANT 1:** If `CountdownProcessor.process()` returns `padding_added=True`, then `job.state_data.lyrics_metadata.has_countdown_padding` MUST be set to `True`

2. **INVARIANT 2:** If `lyrics_metadata.has_countdown_padding=True`, then `video_worker` MUST pass `countdown_padding_seconds` to the encoding backend

3. **INVARIANT 3:** All encoding backends (KaraokeFinalise, Orchestrator, GCE) MUST pad instrumental when `countdown_padding_seconds > 0`

4. **INVARIANT 4:** Final video instrumental start time MUST equal original start time + countdown_padding_seconds

---

## Verification Strategy

After implementing tests:

1. **Run tests against current code** - Should FAIL (bug exists)
2. **Implement the fix** - Add state update to render_video_worker
3. **Run tests again** - Should PASS
4. **Create regression test script** that runs countdown tests before every merge

---

## CI Integration

Add to `.github/workflows/test.yml`:

```yaml
# Countdown sync tests (contract layer - every PR)
- name: Run countdown contract tests
  run: pytest -v backend/tests/test_countdown_state_contract.py

# Countdown integration tests (weekly or on-demand)
- name: Run countdown integration tests
  run: |
    make emulators-start
    pytest -v backend/tests/emulator/test_countdown_*
    make emulators-stop
```

---

## Fix Implementation

The fix was implemented in `backend/workers/render_video_worker.py` after line 201.

After the existing countdown processing code:
```python
if padding_added:
    job_log.info(f"Countdown added: {padding_seconds}s padding applied to audio and timestamps shifted")
else:
    job_log.info("No countdown needed - song starts after 3 seconds")
```

Added state update to communicate countdown info to video_worker:
```python
# Update lyrics_metadata with countdown info so video_worker knows to pad instrumental
# This is critical for audio sync - without this, instrumental won't match padded vocals
if padding_added:
    existing_lyrics_metadata = job.state_data.get('lyrics_metadata', {})
    existing_lyrics_metadata['has_countdown_padding'] = True
    existing_lyrics_metadata['countdown_padding_seconds'] = padding_seconds
    job_manager.update_state_data(job_id, 'lyrics_metadata', existing_lyrics_metadata)
    job_log.info(f"Updated lyrics_metadata: has_countdown_padding=True, countdown_padding_seconds={padding_seconds}")
```

This ensures **INVARIANT 1** is satisfied: If `CountdownProcessor.process()` returns `padding_added=True`, then `job.state_data.lyrics_metadata.has_countdown_padding` is set to `True`.
