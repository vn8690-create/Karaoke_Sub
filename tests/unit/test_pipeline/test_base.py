"""
Tests for pipeline base classes.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestStageStatus:
    """Tests for StageStatus enum."""

    def test_stage_status_values(self):
        """Test that StageStatus has expected values."""
        from karaoke_gen.pipeline.base import StageStatus
        
        assert StageStatus.PENDING.value == "pending"
        assert StageStatus.RUNNING.value == "running"
        assert StageStatus.COMPLETED.value == "completed"
        assert StageStatus.FAILED.value == "failed"
        assert StageStatus.SKIPPED.value == "skipped"


class TestStageResult:
    """Tests for StageResult dataclass."""

    def test_create_completed_result(self):
        """Test creating a completed stage result."""
        from karaoke_gen.pipeline.base import StageResult, StageStatus
        
        result = StageResult(
            status=StageStatus.COMPLETED,
            outputs={"key": "value"},
            duration_seconds=5.0,
        )
        
        assert result.status == StageStatus.COMPLETED
        assert result.outputs == {"key": "value"}
        assert result.duration_seconds == 5.0
        assert result.success is True
        assert result.failed is False

    def test_create_failed_result(self):
        """Test creating a failed stage result."""
        from karaoke_gen.pipeline.base import StageResult, StageStatus
        
        result = StageResult(
            status=StageStatus.FAILED,
            error_message="Something went wrong",
            error_details={"code": 500},
        )
        
        assert result.status == StageStatus.FAILED
        assert result.error_message == "Something went wrong"
        assert result.error_details == {"code": 500}
        assert result.success is False
        assert result.failed is True

    def test_create_skipped_result(self):
        """Test creating a skipped stage result."""
        from karaoke_gen.pipeline.base import StageResult, StageStatus
        
        result = StageResult(status=StageStatus.SKIPPED)
        
        assert result.status == StageStatus.SKIPPED
        assert result.success is False
        assert result.failed is False

    def test_result_default_outputs(self):
        """Test that outputs defaults to empty dict."""
        from karaoke_gen.pipeline.base import StageResult, StageStatus
        
        result = StageResult(status=StageStatus.COMPLETED)
        assert result.outputs == {}


class TestPipelineStage:
    """Tests for PipelineStage abstract base class."""

    def test_cannot_instantiate_directly(self):
        """Test that PipelineStage cannot be instantiated directly."""
        from karaoke_gen.pipeline.base import PipelineStage
        
        with pytest.raises(TypeError):
            PipelineStage()

    def test_concrete_implementation(self):
        """Test creating a concrete stage implementation."""
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        class TestStage(PipelineStage):
            @property
            def name(self):
                return "test_stage"
            
            async def execute(self, context):
                return StageResult(
                    status=StageStatus.COMPLETED,
                    outputs={"test": "output"},
                )
        
        stage = TestStage()
        assert stage.name == "test_stage"
        assert stage.required_inputs == []
        assert stage.optional_inputs == []
        assert stage.output_keys == []

    def test_validate_inputs_with_no_requirements(self):
        """Test validate_inputs when no inputs are required."""
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        class TestStage(PipelineStage):
            @property
            def name(self):
                return "test"
            
            async def execute(self, context):
                return StageResult(status=StageStatus.COMPLETED)
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/path/to/audio.flac",
            output_dir="/path/to/output",
        )
        
        stage = TestStage()
        assert stage.validate_inputs(context) is True

    def test_validate_inputs_with_missing_requirements(self):
        """Test validate_inputs when required inputs are missing."""
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        class TestStage(PipelineStage):
            @property
            def name(self):
                return "test"
            
            @property
            def required_inputs(self):
                return ["previous_stage"]
            
            async def execute(self, context):
                return StageResult(status=StageStatus.COMPLETED)
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/path/to/audio.flac",
            output_dir="/path/to/output",
        )
        
        stage = TestStage()
        assert stage.validate_inputs(context) is False
        assert stage.get_missing_inputs(context) == ["previous_stage"]

    def test_validate_inputs_with_satisfied_requirements(self):
        """Test validate_inputs when required inputs are present."""
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        class TestStage(PipelineStage):
            @property
            def name(self):
                return "test"
            
            @property
            def required_inputs(self):
                return ["previous_stage"]
            
            async def execute(self, context):
                return StageResult(status=StageStatus.COMPLETED)
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/path/to/audio.flac",
            output_dir="/path/to/output",
            stage_outputs={"previous_stage": {"data": "value"}},
        )
        
        stage = TestStage()
        assert stage.validate_inputs(context) is True
        assert stage.get_missing_inputs(context) == []


class TestPipelineExecutor:
    """Tests for PipelineExecutor abstract base class."""

    def test_cannot_instantiate_directly(self):
        """Test that PipelineExecutor cannot be instantiated directly."""
        from karaoke_gen.pipeline.base import PipelineExecutor
        
        with pytest.raises(TypeError):
            PipelineExecutor()
