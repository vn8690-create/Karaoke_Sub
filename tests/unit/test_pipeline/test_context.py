"""
Tests for PipelineContext.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock


class TestPipelineContext:
    """Tests for PipelineContext dataclass."""

    def test_create_minimal_context(self):
        """Test creating a context with minimal required fields."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test-123",
            artist="Test Artist",
            title="Test Title",
            input_audio_path="/path/to/audio.flac",
            output_dir="/path/to/output",
        )
        
        assert context.job_id == "test-123"
        assert context.artist == "Test Artist"
        assert context.title == "Test Title"
        assert context.input_audio_path == "/path/to/audio.flac"
        assert context.output_dir == "/path/to/output"

    def test_base_name_property(self):
        """Test the base_name property."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="The Beatles",
            title="Hey Jude",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        assert context.base_name == "The Beatles - Hey Jude"

    def test_output_path_property(self):
        """Test the output_path property returns Path object."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/path/to/output",
        )
        
        assert isinstance(context.output_path, Path)
        assert str(context.output_path) == "/path/to/output"

    def test_input_path_property(self):
        """Test the input_path property returns Path object."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/path/to/audio.flac",
            output_dir="/output",
        )
        
        assert isinstance(context.input_path, Path)
        assert str(context.input_path) == "/path/to/audio.flac"

    def test_default_values(self):
        """Test default values for optional fields."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        assert context.style_params == {}
        assert context.enable_cdg is True
        assert context.enable_txt is True
        assert context.brand_prefix is None
        assert context.enable_youtube_upload is False
        assert context.discord_webhook_url is None
        assert context.dropbox_path is None
        assert context.gdrive_folder_id is None
        assert context.stage_outputs == {}
        assert context.current_stage is None
        assert context.progress_percent == 0
        assert context.temp_paths == []

    def test_get_stage_output(self):
        """Test getting stage output."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
            stage_outputs={
                "separation": {
                    "instrumental": "/path/to/instrumental.flac",
                    "vocals": "/path/to/vocals.flac",
                },
            },
        )
        
        # Existing key
        assert context.get_stage_output("separation", "instrumental") == "/path/to/instrumental.flac"
        
        # Missing key with default
        assert context.get_stage_output("separation", "missing", "default") == "default"
        
        # Missing stage
        assert context.get_stage_output("missing_stage", "key") is None

    def test_set_stage_output(self):
        """Test setting stage output."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        context.set_stage_output("separation", {"instrumental": "/path.flac"})
        
        assert context.stage_outputs["separation"]["instrumental"] == "/path.flac"
        
        # Update existing stage output
        context.set_stage_output("separation", {"vocals": "/vocals.flac"})
        
        assert context.stage_outputs["separation"]["instrumental"] == "/path.flac"
        assert context.stage_outputs["separation"]["vocals"] == "/vocals.flac"

    def test_update_progress(self):
        """Test progress update."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        context.update_progress("separation", 50, "Processing...")
        
        assert context.current_stage == "separation"
        assert context.progress_percent == 50

    def test_update_progress_calls_callback(self):
        """Test that update_progress calls the callback if set."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        callback_calls = []
        
        def mock_callback(stage, percent, message):
            callback_calls.append((stage, percent, message))
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
            on_progress=mock_callback,
        )
        
        context.update_progress("separation", 50, "Processing...")
        
        assert len(callback_calls) == 1
        assert callback_calls[0] == ("separation", 50, "Processing...")

    def test_add_temp_path(self):
        """Test adding temporary paths."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        context.add_temp_path("/tmp/file1.txt")
        context.add_temp_path("/tmp/file2.txt")
        
        assert len(context.temp_paths) == 2
        assert "/tmp/file1.txt" in context.temp_paths
        assert "/tmp/file2.txt" in context.temp_paths

    def test_to_dict(self):
        """Test serialization to dictionary."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test-123",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
            brand_prefix="NOMAD",
            dropbox_path="/Karaoke",
        )
        
        data = context.to_dict()
        
        assert data["job_id"] == "test-123"
        assert data["artist"] == "Artist"
        assert data["title"] == "Title"
        assert data["brand_prefix"] == "NOMAD"
        assert data["dropbox_path"] == "/Karaoke"
        # Non-serializable fields should not be included
        assert "on_progress" not in data
        assert "logger" not in data

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        data = {
            "job_id": "test-123",
            "artist": "Artist",
            "title": "Title",
            "input_audio_path": "/audio.flac",
            "output_dir": "/output",
            "brand_prefix": "NOMAD",
            "dropbox_path": "/Karaoke",
            "stage_outputs": {"separation": {"done": True}},
        }
        
        context = PipelineContext.from_dict(data)
        
        assert context.job_id == "test-123"
        assert context.artist == "Artist"
        assert context.brand_prefix == "NOMAD"
        assert context.dropbox_path == "/Karaoke"
        assert context.stage_outputs == {"separation": {"done": True}}

    def test_roundtrip_serialization(self):
        """Test that serialization and deserialization roundtrip works."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        original = PipelineContext(
            job_id="test-123",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
            brand_prefix="NOMAD",
            enable_cdg=False,
            stage_outputs={"test": {"key": "value"}},
        )
        
        data = original.to_dict()
        restored = PipelineContext.from_dict(data)
        
        assert restored.job_id == original.job_id
        assert restored.artist == original.artist
        assert restored.brand_prefix == original.brand_prefix
        assert restored.enable_cdg == original.enable_cdg
        assert restored.stage_outputs == original.stage_outputs

    def test_cleanup_temp_paths(self):
        """Test cleanup_temp_paths removes files."""
        from karaoke_gen.pipeline.context import PipelineContext
        import tempfile
        import os
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        # Create temp files
        temp_files = []
        for i in range(2):
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(b"test")
                temp_files.append(f.name)
                context.add_temp_path(f.name)
        
        # Verify files exist
        for path in temp_files:
            assert os.path.exists(path)
        
        # Cleanup
        context.cleanup_temp_paths()
        
        # Verify files are removed
        for path in temp_files:
            assert not os.path.exists(path)
        
        # Verify temp_paths is cleared
        assert context.temp_paths == []

    def test_cleanup_temp_paths_handles_missing_files(self):
        """Test cleanup_temp_paths handles missing files gracefully."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        # Add non-existent path
        context.add_temp_path("/nonexistent/path/file.txt")
        
        # Should not raise
        context.cleanup_temp_paths()
        assert context.temp_paths == []

    def test_log_with_logger(self):
        """Test log method uses logger."""
        from karaoke_gen.pipeline.context import PipelineContext
        import logging
        
        mock_logger = MagicMock()
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
            logger=mock_logger,
            current_stage="test_stage",
        )
        
        context.log("INFO", "Test message")
        mock_logger.info.assert_called()

    def test_log_with_callback(self):
        """Test log method calls callback."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        log_calls = []
        
        def mock_log(stage, level, message):
            log_calls.append((stage, level, message))
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
            on_log=mock_log,
            current_stage="test_stage",
        )
        
        context.log("INFO", "Test message")
        
        assert len(log_calls) == 1
        assert log_calls[0][0] == "test_stage"
        assert log_calls[0][1] == "INFO"
        assert log_calls[0][2] == "Test message"

    def test_from_dict_with_minimal_data(self):
        """Test from_dict with minimal data uses defaults."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        data = {
            "job_id": "test",
            "artist": "Artist",
            "title": "Title",
            "input_audio_path": "/audio.flac",
            "output_dir": "/output",
        }
        
        context = PipelineContext.from_dict(data)
        
        assert context.enable_cdg is True  # Default
        assert context.enable_txt is True  # Default
        assert context.stage_outputs == {}  # Default
