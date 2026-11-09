---
name: Instrumental Review UI
overview: Add an intelligent instrumental selection workflow with audio analysis, waveform visualization, playback controls, and the ability to mute sections of backing vocals to create custom instrumentals. This replaces the current text-only CLI prompt with a web UI that works for both local and remote workflows, with shared core logic for DRY/maintainable code.
todos:
  - id: shared-core-module
    content: Create karaoke_gen/instrumental_review/ shared module with AudioAnalyzer and AudioEditor classes (used by both local and remote)
    status: completed
  - id: shared-core-tests
    content: Add comprehensive unit tests for shared module with >80% coverage (tests/unit/test_instrumental_review.py)
    status: completed
  - id: backend-services
    content: Create backend service wrappers that use shared core module (audio_analysis_service.py, audio_editing_service.py)
    status: completed
  - id: backend-services-tests
    content: Add unit tests for backend services with mocked GCS interactions (backend/tests/test_audio_services.py)
    status: completed
  - id: api-endpoints
    content: Add new API endpoints for analysis, audio streaming, and custom instrumental creation
    status: completed
  - id: api-endpoints-tests
    content: Add API endpoint tests with >80% coverage (backend/tests/test_instrumental_api.py)
    status: completed
  - id: render-worker-integration
    content: Integrate audio analysis into render_video_worker before transitioning to awaiting_instrumental_selection
    status: completed
  - id: render-worker-tests
    content: Add/update render_video_worker tests to cover new analysis integration
    status: completed
  - id: frontend-components
    content: Create React components (WaveformDisplay, AudioPlayer, RegionSelector, InstrumentalReviewPage)
    status: completed
  - id: local-cli-integration
    content: Update local gen_cli.py to use shared core module with local file paths (feature parity with remote)
    status: completed
  - id: local-cli-review-server
    content: Add lightweight review server to local CLI for browser-based review (similar to lyrics review pattern)
    status: completed
  - id: remote-cli-update
    content: Update remote_cli.py to use new analysis API and open browser for review
    status: completed
  - id: cli-tests
    content: Add CLI tests verifying feature parity between local and remote modes
    status: completed
  - id: integration-tests
    content: Add end-to-end integration tests for the full instrumental review workflow
    status: completed
---

# Intelligent Instrumental Selection Plan

## Current State

The instrumental selection workflow currently:

- Presents a simple 1/2 choice in the CLI (clean vs. with_backing)
- Requires manual inspection in Audacity to evaluate backing vocals quality
- Cannot handle the common "Scenario 3" where backing vocals need partial muting
- Has no audio preview capability in remote mode

## Target Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    INSTRUMENTAL REVIEW WORKFLOW                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  1. AUDIO ANALYSIS (automatic after render_video completes)               │
│     │                                                                      │
│     ├── Analyze backing vocals stem for amplitude                         │
│     ├── Detect audible segments (> -40dB threshold)                       │
│     ├── Generate waveform visualization image                             │
│     └── Store analysis results in job state_data                          │
│                                                                            │
│  2. AUTO-DECISION CHECK                                                    │
│     │                                                                      │
│     └── IF no audible segments detected:                                  │
│            ├── Set recommended_selection = "clean"                         │
│            └── Skip to step 4 (or show minimal UI with suggestion)         │
│                                                                            │
│  3. HUMAN REVIEW (Web UI)                                                  │
│     │                                                                      │
│     ├── Display waveform with time axis                                   │
│     ├── Show audible segment markers                                       │
│     ├── Audio playback with waveform-click seeking                         │
│     ├── Toggle between: clean / with_backing / preview-custom             │
│     ├── Select regions to mute (click/drag on waveform)                   │
│     └── Create custom instrumental if regions selected                    │
│                                                                            │
│  4. SELECTION SUBMISSION                                                   │
│     │                                                                      │
│     └── POST /api/jobs/{job_id}/select-instrumental                        │
│            with selection = "clean" | "with_backing" | "custom"           │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

## Architecture: Shared Core for DRY/SOLID

To ensure feature parity between local and remote CLIs while keeping code maintainable, we use a **shared core module** pattern:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SHARED CORE ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  karaoke_gen/instrumental_review/           <── SHARED CORE MODULE         │
│  ├── __init__.py                                                           │
│  ├── analyzer.py         # AudioAnalyzer class (pure Python, no GCS)       │
│  ├── editor.py           # AudioEditor class (pure Python, no GCS)         │
│  ├── waveform.py         # WaveformGenerator class (matplotlib)            │
│  └── models.py           # Pydantic models: AnalysisResult, MuteRegion     │
│                                                                             │
│  ┌─────────────────────┐              ┌──────────────────────┐             │
│  │   LOCAL CLI         │              │   REMOTE BACKEND     │             │
│  │   (karaoke-gen)     │              │   (Cloud Run)        │             │
│  ├─────────────────────┤              ├──────────────────────┤             │
│  │                     │              │                      │             │
│  │  gen_cli.py         │              │  audio_analysis_     │             │
│  │  └── uses shared ───┼──────────────┼──► service.py        │             │
│  │      core directly  │              │      └── wraps shared│             │
│  │      with local     │              │          core with   │             │
│  │      file paths     │              │          GCS I/O     │             │
│  │                     │              │                      │             │
│  │  local_review_      │              │  audio_editing_      │             │
│  │  server.py          │              │  service.py          │             │
│  │  └── serves same ───┼──────────────┼──► (same pattern)    │             │
│  │      React UI       │              │                      │             │
│  │                     │              │                      │             │
│  └─────────────────────┘              └──────────────────────┘             │
│                                                                             │
│  BENEFITS:                                                                  │
│  ✓ Single source of truth for analysis logic                               │
│  ✓ Bug fixes apply to both local and remote                                │
│  ✓ Easy to test core logic without GCS mocks                               │
│  ✓ Backend services are thin wrappers (Single Responsibility)              │
│  ✓ Same React UI served by both local server and Cloud Run                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Shared Core Module Design

```python
# karaoke_gen/instrumental_review/analyzer.py
class AudioAnalyzer:
    """
    Analyzes audio files for backing vocals content.
    Pure Python - no cloud dependencies. Works with local file paths.
    """
    def __init__(self, silence_threshold_db: float = -40.0, 
                 min_segment_duration_ms: int = 100):
        self.silence_threshold_db = silence_threshold_db
        self.min_segment_duration_ms = min_segment_duration_ms
    
    def analyze(self, audio_path: str) -> AnalysisResult:
        """Analyze audio file and return structured result."""
        ...
    
    def get_amplitude_envelope(self, audio_path: str, 
                               window_ms: int = 100) -> List[float]:
        """Get amplitude envelope for waveform rendering."""
        ...

# karaoke_gen/instrumental_review/editor.py  
class AudioEditor:
    """
    Creates custom instrumentals by muting regions of backing vocals.
    Pure Python - no cloud dependencies.
    """
    def create_custom_instrumental(
        self,
        clean_instrumental_path: str,
        backing_vocals_path: str,
        mute_regions: List[MuteRegion],
        output_path: str
    ) -> str:
        """Create custom instrumental with muted regions."""
        ...

# karaoke_gen/instrumental_review/waveform.py
class WaveformGenerator:
    """Generates waveform visualization images."""
    def generate(self, audio_path: str, output_path: str,
                 segments: List[AudibleSegment] = None,
                 width: int = 1200, height: int = 200) -> str:
        """Generate waveform PNG with optional segment highlighting."""
        ...
```

## Implementation Components

### 1. Shared Core Module (karaoke_gen/instrumental_review/)

Create the shared module first - this is the foundation:

```python
# karaoke_gen/instrumental_review/models.py
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class RecommendedSelection(str, Enum):
    CLEAN = "clean"
    WITH_BACKING = "with_backing"
    REVIEW_NEEDED = "review_needed"

class AudibleSegment(BaseModel):
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    avg_amplitude_db: float

class MuteRegion(BaseModel):
    start_seconds: float
    end_seconds: float

class AnalysisResult(BaseModel):
    has_audible_content: bool
    total_duration_seconds: float
    audible_segments: List[AudibleSegment]
    recommended_selection: RecommendedSelection
    waveform_data: Optional[List[float]] = None  # For JSON API response
```

### 2. Backend Service Wrappers

Create `backend/services/audio_analysis_service.py`:

```python
# Key functionality:
- analyze_backing_vocals(audio_path) -> AnalysisResult
  - Uses pydub for audio loading
  - Calculates RMS amplitude in dB across time windows
  - Detects audible segments (contiguous regions > threshold)
  - Returns: {
      "has_audible_content": bool,
      "total_duration_seconds": float,
      "audible_segments": [
        {"start_seconds": float, "end_seconds": float, 
         "duration_seconds": float, "avg_amplitude_db": float}
      ],
      "recommended_selection": "clean" | "with_backing" | "review_needed"
    }

- generate_waveform_image(audio_path, output_path, segments=None) -> str
  - Uses matplotlib to render amplitude envelope over time
  - Highlights audible segments with different colors
  - Returns path to generated PNG image
```

### 2. Audio Editing Service

Create `backend/services/audio_editing_service.py`:

```python
# Key functionality:
- create_custom_instrumental(
    clean_instrumental_path: str,
    backing_vocals_path: str,
    mute_regions: List[Tuple[float, float]],  # [(start_s, end_s), ...]
    output_path: str
  ) -> str
  - Loads backing vocals
  - Applies silence to mute_regions
  - Mixes with clean instrumental
  - Saves as new FLAC file
```

### 3. Backend API Endpoints

Add to `backend/api/routes/jobs.py`:

```python
GET /api/jobs/{job_id}/instrumental-analysis
  # Returns analysis data + waveform URL
  
GET /api/jobs/{job_id}/audio-stream/{stem_type}
  # Stream audio for playback (clean, backing_vocals, combined)
  
POST /api/jobs/{job_id}/create-custom-instrumental
  # Body: {"mute_regions": [[0.5, 2.3], [45.0, 48.5]]}
  # Creates custom instrumental, updates job state
  
POST /api/jobs/{job_id}/select-instrumental
  # Extended to accept: "clean" | "with_backing" | "custom"
```

### 4. Frontend Web UI

Create `frontend/app/jobs/[id]/instrumental-review/page.tsx`:

```
Components needed:
- WaveformDisplay: SVG/Canvas waveform with time axis
- AudioPlayer: HTML5 audio with controls + waveform sync
- RegionSelector: Click/drag to select mute regions
- InstrumentalOptions: Radio buttons for clean/backing/custom
- SegmentList: Table showing detected audible segments
```

Key interactions:

- Click on waveform to seek playback position
- Drag on waveform to select mute region
- Toggle audio source (clean/backing/preview)
- Submit selection

### 5. Backend Worker Updates

Modify `backend/workers/render_video_worker.py`:

```python
# After video render completes, before transitioning to AWAITING_INSTRUMENTAL_SELECTION:
1. Download backing_vocals stem
2. Run audio analysis
3. Generate waveform image
4. Upload waveform to GCS
5. Store analysis results in job.state_data
6. If no audible content: set recommended_selection = "clean"
7. Transition to AWAITING_INSTRUMENTAL_SELECTION
```

### 6. CLI Updates

Modify `karaoke_gen/utils/remote_cli.py`:

```python
def handle_instrumental_selection(self, job_id: str):
    # Get analysis data
    analysis = self.client.get_instrumental_analysis(job_id)
    
    # If no backing vocals detected, suggest auto-select
    if analysis['recommended_selection'] == 'clean':
        if self.config.non_interactive:
            # Auto-select clean
            self.client.select_instrumental(job_id, 'clean')
            return
        else:
            # Show suggestion, offer to open browser for verification
            self.logger.info("No backing vocals detected - recommending clean instrumental")
            # Open browser anyway so user can verify if desired
    
    # Open browser to instrumental review UI
    self.open_instrumental_review_ui(job_id)
    
    # Poll until selection made
    while job.status == 'awaiting_instrumental_selection':
        time.sleep(self.config.poll_interval)
```

### 7. Local CLI Integration (Feature Parity)

The local CLI (`karaoke-gen`) uses the **same shared core module** as the backend:

```python
# karaoke_gen/utils/gen_cli.py - Updated instrumental selection flow

def handle_instrumental_selection(self, output_dir: str, base_name: str):
    """Handle instrumental selection using shared core module."""
    from karaoke_gen.instrumental_review import AudioAnalyzer, WaveformGenerator
    
    # Paths to local files (already exist from audio separation)
    backing_vocals_path = os.path.join(output_dir, "stems", 
        f"{base_name} (Backing Vocals ...).flac")
    clean_instrumental_path = os.path.join(output_dir, "stems",
        f"{base_name} (Instrumental ...).flac")
    
    # Use SAME analyzer as backend
    analyzer = AudioAnalyzer(silence_threshold_db=-40.0)
    analysis = analyzer.analyze(backing_vocals_path)
    
    # Generate waveform locally
    waveform_path = os.path.join(output_dir, "backing_vocals_waveform.png")
    WaveformGenerator().generate(backing_vocals_path, waveform_path, 
                                  analysis.audible_segments)
    
    if not analysis.has_audible_content:
        self.logger.info("No backing vocals detected - using clean instrumental")
        if not self.non_interactive:
            # Offer to open browser for verification
            ...
        return "clean"
    
    # Start local review server (serves same React UI)
    from karaoke_gen.instrumental_review.server import InstrumentalReviewServer
    server = InstrumentalReviewServer(
        output_dir=output_dir,
        base_name=base_name,
        analysis=analysis,
        waveform_path=waveform_path,
    )
    server.start_and_open_browser()  # Blocking until user submits selection
    
    return server.get_selection()
```

### 8. Local Review Server

Create `karaoke_gen/instrumental_review/server.py`:

```python
"""
Lightweight local server for instrumental review.
Serves the same React frontend used by the cloud backend.
Similar pattern to LyricsTranscriber's ReviewServer.
"""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import threading

class InstrumentalReviewServer:
    """
    Local HTTP server for instrumental review UI.
    
    Endpoints:
    - GET /api/analysis - Returns analysis data
    - GET /api/audio/{type} - Streams audio files
    - GET /api/waveform - Returns waveform image
    - POST /api/create-custom - Creates custom instrumental
    - POST /api/select - Submits selection
    - GET /* - Serves React frontend static files
    """
    def __init__(self, output_dir: str, base_name: str, 
                 analysis: AnalysisResult, waveform_path: str):
        ...
    
    def start_and_open_browser(self, port: int = 8765):
        """Start server, open browser, block until selection submitted."""
        ...
    
    def get_selection(self) -> str:
        """Get the user's selection after browser submission."""
        ...
```

## Testing Strategy

### Test Coverage Requirements

All new code must meet the project's **70% minimum coverage** requirement, with critical paths targeting **>80%**:

| Module | Target Coverage | Test File |

|--------|----------------|-----------|

| `karaoke_gen/instrumental_review/analyzer.py` | >90% | `tests/unit/test_instrumental_analyzer.py` |

| `karaoke_gen/instrumental_review/editor.py` | >90% | `tests/unit/test_instrumental_editor.py` |

| `karaoke_gen/instrumental_review/waveform.py` | >80% | `tests/unit/test_instrumental_waveform.py` |

| `karaoke_gen/instrumental_review/server.py` | >70% | `tests/unit/test_instrumental_server.py` |

| `backend/services/audio_analysis_service.py` | >80% | `backend/tests/test_audio_analysis_service.py` |

| `backend/services/audio_editing_service.py` | >80% | `backend/tests/test_audio_editing_service.py` |

| `backend/api/routes/jobs.py` (new endpoints) | >80% | `backend/tests/test_instrumental_api.py` |

### Test Categories

**1. Unit Tests (Shared Core) - tests/unit/test_instrumental_*.py**

```python
# tests/unit/test_instrumental_analyzer.py
class TestAudioAnalyzer:
    def test_analyze_silent_audio_returns_no_audible_content(self):
        """Silent audio should return has_audible_content=False."""
        
    def test_analyze_audio_with_content_detects_segments(self):
        """Audio with content should detect audible segments."""
        
    def test_segment_detection_respects_threshold(self):
        """Segments below threshold should not be detected."""
        
    def test_segment_merging_for_close_segments(self):
        """Close segments should be merged into one."""
        
    def test_recommended_selection_clean_for_silent(self):
        """Silent audio should recommend 'clean'."""
        
    def test_recommended_selection_review_for_content(self):
        """Audio with content should recommend 'review_needed'."""

# tests/unit/test_instrumental_editor.py
class TestAudioEditor:
    def test_mute_single_region(self):
        """Single mute region should be applied correctly."""
        
    def test_mute_multiple_regions(self):
        """Multiple mute regions should all be applied."""
        
    def test_mute_region_boundaries(self):
        """Mute region at start/end of audio should work."""
        
    def test_output_format_is_flac(self):
        """Output should be FLAC format."""
        
    def test_combines_with_clean_instrumental(self):
        """Result should be backing vocals mixed with clean instrumental."""
```

**2. Unit Tests (Backend Services) - backend/tests/test_audio_*_service.py**

```python
# backend/tests/test_audio_analysis_service.py
class TestAudioAnalysisService:
    @pytest.fixture
    def mock_storage(self):
        """Mock GCS storage service."""
        
    def test_analyze_downloads_from_gcs(self, mock_storage):
        """Service should download audio from GCS before analysis."""
        
    def test_analyze_uploads_waveform_to_gcs(self, mock_storage):
        """Service should upload waveform image to GCS."""
        
    def test_analyze_updates_job_state_data(self, mock_storage):
        """Service should store analysis in job.state_data."""
```

**3. API Endpoint Tests - backend/tests/test_instrumental_api.py**

```python
# backend/tests/test_instrumental_api.py
class TestInstrumentalAnalysisEndpoint:
    def test_get_analysis_returns_data(self, client, mock_job):
        """GET /instrumental-analysis should return analysis data."""
        
    def test_get_analysis_requires_correct_status(self, client, mock_job):
        """Should return 400 if job not in correct status."""

class TestAudioStreamEndpoint:
    def test_stream_backing_vocals(self, client, mock_job):
        """Should stream backing vocals audio."""
        
    def test_stream_clean_instrumental(self, client, mock_job):
        """Should stream clean instrumental audio."""

class TestCreateCustomInstrumental:
    def test_create_with_mute_regions(self, client, mock_job):
        """Should create custom instrumental with mute regions."""
        
    def test_validates_mute_regions(self, client, mock_job):
        """Should validate mute region boundaries."""
```

**4. Integration Tests - tests/integration/test_instrumental_review.py**

```python
# tests/integration/test_instrumental_review_flow.py
class TestInstrumentalReviewFlow:
    """End-to-end tests for instrumental review workflow."""
    
    def test_full_flow_clean_selection(self):
        """Test complete flow: analysis -> review -> select clean."""
        
    def test_full_flow_with_backing_selection(self):
        """Test complete flow: analysis -> review -> select with_backing."""
        
    def test_full_flow_custom_creation(self):
        """Test complete flow: analysis -> mute regions -> custom."""
        
    def test_auto_recommend_clean_for_silent_backing(self):
        """When no backing vocals, should recommend clean."""
```

**5. CLI Feature Parity Tests - tests/unit/test_cli_feature_parity.py**

```python
# tests/unit/test_cli_feature_parity.py
class TestCLIFeatureParity:
    """Verify local and remote CLIs have equivalent functionality."""
    
    def test_both_clis_use_same_analyzer(self):
        """Both CLIs should use AudioAnalyzer from shared module."""
        
    def test_both_clis_support_custom_instrumental(self):
        """Both CLIs should support creating custom instrumentals."""
        
    def test_analysis_results_identical(self):
        """Same audio should produce identical analysis from both CLIs."""
```

### Test Data

Create test fixtures in `tests/data/instrumental_review/`:

- `silent_backing_vocals.flac` - Silent/near-silent audio (~10s)
- `backing_vocals_with_content.flac` - Audio with clear backing vocals (~30s)
- `backing_vocals_mixed_quality.flac` - Audio with some good/some bad sections (~30s)

Use pydub to programmatically generate these in `tests/conftest.py` fixtures.

## File Changes Summary

| Category | Files to Create/Modify |

|----------|------------------------|

| **Shared Core** | `karaoke_gen/instrumental_review/__init__.py` (new) |

| Shared Core | `karaoke_gen/instrumental_review/models.py` (new) |

| Shared Core | `karaoke_gen/instrumental_review/analyzer.py` (new) |

| Shared Core | `karaoke_gen/instrumental_review/editor.py` (new) |

| Shared Core | `karaoke_gen/instrumental_review/waveform.py` (new) |

| Shared Core | `karaoke_gen/instrumental_review/server.py` (new) |

| **Backend Services** | `backend/services/audio_analysis_service.py` (new) |

| Backend Services | `backend/services/audio_editing_service.py` (new) |

| **API** | `backend/api/routes/jobs.py` (modify - add endpoints) |

| API | `backend/api/routes/instrumental.py` (new - if endpoints get large) |

| **Workers** | `backend/workers/render_video_worker.py` (modify) |

| **Models** | `backend/models/job.py` (add analysis fields to state_data) |

| **Frontend** | `frontend/app/jobs/[id]/instrumental-review/page.tsx` (new) |

| Frontend | `frontend/components/waveform-display.tsx` (new) |

| Frontend | `frontend/components/audio-player-with-waveform.tsx` (new) |

| Frontend | `frontend/components/region-selector.tsx` (new) |

| **Local CLI** | `karaoke_gen/utils/gen_cli.py` (modify) |

| **Remote CLI** | `karaoke_gen/utils/remote_cli.py` (modify) |

| **Tests - Shared** | `tests/unit/test_instrumental_analyzer.py` (new) |

| Tests - Shared | `tests/unit/test_instrumental_editor.py` (new) |

| Tests - Shared | `tests/unit/test_instrumental_waveform.py` (new) |

| Tests - Shared | `tests/unit/test_instrumental_server.py` (new) |

| **Tests - Backend** | `backend/tests/test_audio_analysis_service.py` (new) |

| Tests - Backend | `backend/tests/test_audio_editing_service.py` (new) |

| Tests - Backend | `backend/tests/test_instrumental_api.py` (new) |

| **Tests - Parity** | `tests/unit/test_cli_feature_parity.py` (new) |

| **Tests - Integration** | `tests/integration/test_instrumental_review.py` (new) |

| **Test Data** | `tests/conftest.py` (modify - add fixtures) |

## Dependencies

Already available in `pyproject.toml`:

- `pydub>=0.25.1` - Audio loading and manipulation
- `matplotlib>=3` - Waveform visualization
- `numpy>=2` - Audio array processing

Frontend:

- React/Next.js (existing)
- HTML5 Audio API (native)
- Canvas or SVG for waveform (native)

## Implementation Order

Execute in this order to enable incremental testing:

### Phase 1: Shared Core Module (Foundation)

1. Create `karaoke_gen/instrumental_review/` package with models, analyzer, editor, waveform
2. Add comprehensive unit tests for shared core (>90% coverage)
3. Create test audio fixtures in `tests/conftest.py`

### Phase 2: Backend Integration

4. Create backend service wrappers with GCS integration
5. Add backend service unit tests with mocked GCS
6. Add new API endpoints to `backend/api/routes/jobs.py`
7. Add API endpoint tests
8. Integrate analysis into `render_video_worker.py`
9. Update render worker tests

### Phase 3: Frontend

10. Create React components (WaveformDisplay, AudioPlayer, RegionSelector)
11. Create instrumental review page
12. Test frontend manually with backend

### Phase 4: CLI Integration

13. Update `remote_cli.py` to use new analysis API and open browser
14. Create local review server `karaoke_gen/instrumental_review/server.py`
15. Update `gen_cli.py` to use shared core and local server
16. Add CLI feature parity tests

### Phase 5: Integration Testing

17. Add end-to-end integration tests
18. Manual testing of full workflow (local and remote)

### Verification Checklist

- [ ] All unit tests pass: `pytest tests/unit/ -v`
- [ ] All backend tests pass: `pytest backend/tests/ -v`
- [ ] Coverage meets 70% minimum: `pytest --cov=karaoke_gen --cov-fail-under=70`
- [ ] Local CLI works: `karaoke-gen "Artist" "Title"` (reaches instrumental selection)
- [ ] Remote CLI works: `karaoke-gen-remote ./audio.flac "Artist" "Title"`
- [ ] Both CLIs produce identical analysis for same audio
- [ ] Custom instrumental creation works in both modes
- [ ] Version bumped in `pyproject.toml`