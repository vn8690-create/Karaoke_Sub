"""
Tests for pipeline module initialization and exports.
"""
import pytest


class TestPipelineModuleExports:
    """Tests for the main pipeline module exports."""

    def test_import_base_classes(self):
        """Test importing base classes from pipeline module."""
        from karaoke_gen.pipeline import (
            PipelineStage,
            PipelineExecutor,
            StageResult,
            StageStatus,
            PipelineContext,
        )
        
        assert PipelineStage is not None
        assert PipelineExecutor is not None
        assert StageResult is not None
        assert StageStatus is not None
        assert PipelineContext is not None

    def test_import_stages(self):
        """Test importing stages from pipeline module."""
        from karaoke_gen.pipeline import (
            SeparationStage,
            TranscriptionStage,
            ScreensStage,
            RenderStage,
            FinalizeStage,
        )
        
        assert SeparationStage is not None
        assert TranscriptionStage is not None
        assert ScreensStage is not None
        assert RenderStage is not None
        assert FinalizeStage is not None

    def test_import_executors(self):
        """Test importing executors from pipeline module."""
        from karaoke_gen.pipeline import (
            LocalExecutor,
            RemoteExecutor,
            create_local_executor,
            create_remote_executor,
        )
        
        assert LocalExecutor is not None
        assert RemoteExecutor is not None
        assert create_local_executor is not None
        assert create_remote_executor is not None

    def test_all_exports_accessible(self):
        """Test that all __all__ exports are accessible."""
        from karaoke_gen import pipeline
        
        for name in pipeline.__all__:
            assert hasattr(pipeline, name), f"Missing export: {name}"

    def test_create_simple_pipeline(self):
        """Test creating a simple pipeline configuration."""
        from karaoke_gen.pipeline import (
            PipelineContext,
            LocalExecutor,
            SeparationStage,
        )
        
        # Create context
        context = PipelineContext(
            job_id="test-123",
            artist="Test Artist",
            title="Test Title",
            input_audio_path="/path/to/audio.flac",
            output_dir="/path/to/output",
        )
        
        # Create stages
        stages = [
            SeparationStage(skip_separation=True),  # Skip for testing
        ]
        
        # Create executor
        executor = LocalExecutor()
        
        # Verify everything is set up correctly
        assert context.job_id == "test-123"
        assert len(stages) == 1
        assert stages[0].name == "separation"
        assert executor is not None
