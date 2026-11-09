import os
import pytest
import tempfile
import subprocess
from unittest.mock import Mock, patch, MagicMock, call
from karaoke_gen.video_background_processor import VideoBackgroundProcessor


class TestVideoBackgroundProcessor:
    """Test suite for VideoBackgroundProcessor class."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger for testing."""
        return Mock()

    @pytest.fixture
    def processor(self, mock_logger):
        """Create a VideoBackgroundProcessor instance with mocked NVENC detection."""
        with patch.object(VideoBackgroundProcessor, 'detect_nvenc_support', return_value=False):
            return VideoBackgroundProcessor(
                logger=mock_logger,
                ffmpeg_base_command="ffmpeg -hide_banner"
            )

    @pytest.fixture
    def processor_with_nvenc(self, mock_logger):
        """Create a VideoBackgroundProcessor instance with NVENC enabled."""
        with patch.object(VideoBackgroundProcessor, 'detect_nvenc_support', return_value=True):
            return VideoBackgroundProcessor(
                logger=mock_logger,
                ffmpeg_base_command="ffmpeg -hide_banner"
            )

    def test_init_without_nvenc(self, mock_logger):
        """Test initialization without NVENC support."""
        with patch.object(VideoBackgroundProcessor, 'detect_nvenc_support', return_value=False):
            processor = VideoBackgroundProcessor(
                logger=mock_logger,
                ffmpeg_base_command="ffmpeg -hide_banner"
            )
            
            assert processor.logger == mock_logger
            assert processor.ffmpeg_base_command == "ffmpeg -hide_banner"
            assert processor.nvenc_available is False
            assert processor.video_encoder == "libx264"
            assert processor.hwaccel_decode_flags == ""

    def test_init_with_nvenc(self, mock_logger):
        """Test initialization with NVENC support."""
        with patch.object(VideoBackgroundProcessor, 'detect_nvenc_support', return_value=True):
            processor = VideoBackgroundProcessor(
                logger=mock_logger,
                ffmpeg_base_command="ffmpeg -hide_banner"
            )
            
            assert processor.nvenc_available is True
            assert processor.video_encoder == "h264_nvenc"
            assert processor.hwaccel_decode_flags == "-hwaccel cuda"

    @patch('subprocess.run')
    def test_detect_nvenc_support_no_gpu(self, mock_run, mock_logger):
        """Test NVENC detection when no GPU is available."""
        # Simulate nvidia-smi failure
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="")
        
        processor = VideoBackgroundProcessor(
            logger=mock_logger,
            ffmpeg_base_command="ffmpeg -hide_banner"
        )
        
        assert processor.nvenc_available is False

    @patch('subprocess.run')
    def test_detect_nvenc_support_success(self, mock_run, mock_logger):
        """Test NVENC detection when all checks pass."""
        # Setup mock responses for all detection steps
        mock_responses = [
            Mock(returncode=0, stdout="NVIDIA GeForce RTX 3080, 515.65.01\n", stderr=""),  # nvidia-smi
            Mock(returncode=0, stdout="h264_nvenc\nh265_nvenc\n", stderr=""),  # encoders check
            Mock(returncode=0, stdout="libcuda.so.1 => /usr/lib/x86_64-linux-gnu/libcuda.so.1\n", stderr=""),  # ldconfig
            Mock(returncode=0, stdout="", stderr=""),  # test encode
        ]
        mock_run.side_effect = mock_responses
        
        processor = VideoBackgroundProcessor(
            logger=mock_logger,
            ffmpeg_base_command="ffmpeg -hide_banner"
        )
        
        assert processor.nvenc_available is True

    def test_get_nvenc_quality_settings(self, processor_with_nvenc):
        """Test NVENC quality settings generation."""
        settings = processor_with_nvenc.get_nvenc_quality_settings()
        
        assert "-preset p4" in settings
        assert "-tune hq" in settings
        assert "-rc vbr" in settings
        assert "-cq 18" in settings

    @patch('subprocess.run')
    def test_get_audio_duration_success(self, mock_run, processor, mock_logger):
        """Test successful audio duration extraction."""
        mock_run.return_value = Mock(returncode=0, stdout="123.456\n", stderr="")
        
        duration = processor.get_audio_duration("/path/to/audio.wav")
        
        assert duration == 123.456
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "ffprobe" in args
        assert "/path/to/audio.wav" in args

    @patch('subprocess.run')
    def test_get_audio_duration_failure(self, mock_run, processor, mock_logger):
        """Test audio duration extraction with ffprobe failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe")
        
        with pytest.raises(subprocess.CalledProcessError):
            processor.get_audio_duration("/path/to/audio.wav")

    def test_escape_filter_path(self, processor):
        """Test path escaping for ffmpeg filters using single-quote wrapping."""
        # Test simple path (wrapped in single quotes)
        assert processor.escape_filter_path("/path/to/file.ass") == "'/path/to/file.ass'"

        # Test path with spaces (protected by single quotes)
        assert processor.escape_filter_path("/path/with spaces/file.ass") == "'/path/with spaces/file.ass'"

        # Test apostrophe escaping (fixes paths like "I'm With You")
        # Single quote becomes '\'' (end quote, escaped quote, start quote)
        assert processor.escape_filter_path("./Avril Lavigne - I'm With You/file.ass") == "'./Avril Lavigne - I'\\''m With You/file.ass'"

        # Test path with colons (protected by single quotes)
        assert processor.escape_filter_path("C:/path/file.ass") == "'C:/path/file.ass'"

        # Test Windows-style path (backslashes preserved, wrapped in quotes)
        assert processor.escape_filter_path("C:\\Users\\test\\file.ass") == "'C:\\Users\\test\\file.ass'"

        # Test multiple apostrophes
        assert processor.escape_filter_path("It's Bob's file.ass") == "'It'\\''s Bob'\\''s file.ass'"

    def test_build_video_filter_no_darkness(self, processor):
        """Test video filter building without darkness overlay."""
        vf_filter = processor.build_video_filter(
            ass_subtitles_path="/path/to/subs.ass",
            darkness_percent=0,
            fonts_dir=None
        )

        # Should contain scale and crop
        assert "scale=w=3840:h=2160:force_original_aspect_ratio=increase,crop=3840:2160" in vf_filter

        # Should contain ASS filter with single-quoted path
        assert "ass='/path/to/subs.ass'" in vf_filter

        # Should NOT contain darkening
        assert "drawbox" not in vf_filter

    def test_build_video_filter_with_darkness(self, processor):
        """Test video filter building with darkness overlay."""
        vf_filter = processor.build_video_filter(
            ass_subtitles_path="/path/to/subs.ass",
            darkness_percent=50,
            fonts_dir=None
        )

        # Should contain darkening with correct alpha
        assert "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.50:t=fill" in vf_filter

        # Should contain ASS filter after darkening
        assert vf_filter.index("drawbox") < vf_filter.index("ass=")

    def test_build_video_filter_with_fonts_dir(self, processor):
        """Test video filter building with fonts directory."""
        with patch('os.path.isdir', return_value=True):
            vf_filter = processor.build_video_filter(
                ass_subtitles_path="/path/to/subs.ass",
                darkness_percent=0,
                fonts_dir="/path/to/fonts"
            )

        # Should contain fonts directory in ASS filter (single-quoted)
        assert "fontsdir='/path/to/fonts'" in vf_filter

    def test_build_video_filter_path_escaping(self, processor):
        """Test video filter building with special characters in paths."""
        # Test with apostrophe in path
        vf_filter = processor.build_video_filter(
            ass_subtitles_path="./Avril Lavigne - I'm With You/subs.ass",
            darkness_percent=0,
            fonts_dir=None
        )

        # Paths should be single-quoted with apostrophes escaped as '\''
        assert "'./Avril Lavigne - I'\\''m With You/subs.ass'" in vf_filter

    @patch('subprocess.run')
    def test_execute_command_with_fallback_gpu_success(self, mock_run, processor_with_nvenc, mock_logger):
        """Test command execution with successful GPU encoding."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        processor_with_nvenc.execute_command_with_fallback(
            gpu_command="ffmpeg -hwaccel cuda -i input.mp4 -c:v h264_nvenc output.mp4",
            cpu_command="ffmpeg -i input.mp4 -c:v libx264 output.mp4",
            description="Test encoding"
        )
        
        # Should only call GPU command once
        assert mock_run.call_count == 1
        # Check the command contains h264_nvenc (the GPU command was called)
        called_command = str(mock_run.call_args)
        assert "h264_nvenc" in called_command

    @patch('subprocess.run')
    def test_execute_command_with_fallback_gpu_failure(self, mock_run, processor_with_nvenc, mock_logger):
        """Test command execution with GPU failure and CPU fallback."""
        # GPU command fails, CPU command succeeds
        mock_run.side_effect = [
            Mock(returncode=1, stdout="", stderr="NVENC error"),  # GPU fails
            Mock(returncode=0, stdout="", stderr=""),  # CPU succeeds
        ]
        
        processor_with_nvenc.execute_command_with_fallback(
            gpu_command="ffmpeg -hwaccel cuda -i input.mp4 -c:v h264_nvenc output.mp4",
            cpu_command="ffmpeg -i input.mp4 -c:v libx264 output.mp4",
            description="Test encoding"
        )
        
        # Should call both GPU and CPU commands
        assert mock_run.call_count == 2

    @patch('subprocess.run')
    def test_execute_command_with_fallback_both_fail(self, mock_run, processor, mock_logger):
        """Test command execution when both GPU and CPU fail."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error")
        
        with pytest.raises(Exception) as exc_info:
            processor.execute_command_with_fallback(
                gpu_command="ffmpeg -i input.mp4 output.mp4",
                cpu_command="ffmpeg -i input.mp4 output.mp4",
                description="Test encoding"
            )
        
        assert "Software encoding failed" in str(exc_info.value)

    @patch('subprocess.run')
    def test_execute_command_with_fallback_timeout(self, mock_run, processor, mock_logger):
        """Test command execution with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 600)
        
        with pytest.raises(Exception) as exc_info:
            processor.execute_command_with_fallback(
                gpu_command="ffmpeg -i input.mp4 output.mp4",
                cpu_command="ffmpeg -i input.mp4 output.mp4",
                description="Test encoding"
            )
        
        assert "timed out" in str(exc_info.value)

    @patch.object(VideoBackgroundProcessor, 'execute_command_with_fallback')
    @patch.object(VideoBackgroundProcessor, 'get_audio_duration')
    @patch('os.path.isfile')
    def test_process_video_background_success(self, mock_isfile, mock_get_duration, mock_execute, processor, mock_logger):
        """Test successful video background processing."""
        # Setup mocks
        mock_isfile.return_value = True
        mock_get_duration.return_value = 180.5
        mock_execute.return_value = None
        
        result = processor.process_video_background(
            video_path="/path/to/video.mp4",
            audio_path="/path/to/audio.wav",
            ass_subtitles_path="/path/to/subs.ass",
            output_path="/path/to/output.mkv",
            darkness_percent=30,
            audio_duration=180.5
        )
        
        assert result == "/path/to/output.mkv"
        mock_execute.assert_called_once()
        
        # Verify the command contains expected elements
        call_args = mock_execute.call_args
        gpu_cmd = call_args[0][0]
        cpu_cmd = call_args[0][1]
        
        assert "-stream_loop -1" in gpu_cmd
        assert "/path/to/video.mp4" in gpu_cmd
        assert "/path/to/audio.wav" in gpu_cmd
        assert "-shortest" in gpu_cmd

    @patch('os.path.isfile')
    def test_process_video_background_missing_video(self, mock_isfile, processor, mock_logger):
        """Test video background processing with missing video file."""
        mock_isfile.side_effect = lambda path: path != "/path/to/video.mp4"
        
        with pytest.raises(FileNotFoundError) as exc_info:
            processor.process_video_background(
                video_path="/path/to/video.mp4",
                audio_path="/path/to/audio.wav",
                ass_subtitles_path="/path/to/subs.ass",
                output_path="/path/to/output.mkv",
                darkness_percent=0
            )
        
        assert "Video file not found" in str(exc_info.value)

    @patch('os.path.isfile')
    def test_process_video_background_missing_audio(self, mock_isfile, processor, mock_logger):
        """Test video background processing with missing audio file."""
        mock_isfile.side_effect = lambda path: path != "/path/to/audio.wav"
        
        with pytest.raises(FileNotFoundError) as exc_info:
            processor.process_video_background(
                video_path="/path/to/video.mp4",
                audio_path="/path/to/audio.wav",
                ass_subtitles_path="/path/to/subs.ass",
                output_path="/path/to/output.mkv",
                darkness_percent=0
            )
        
        assert "Audio file not found" in str(exc_info.value)

    @patch('os.path.isfile')
    def test_process_video_background_missing_subtitles(self, mock_isfile, processor, mock_logger):
        """Test video background processing with missing subtitle file."""
        mock_isfile.side_effect = lambda path: path != "/path/to/subs.ass"
        
        with pytest.raises(FileNotFoundError) as exc_info:
            processor.process_video_background(
                video_path="/path/to/video.mp4",
                audio_path="/path/to/audio.wav",
                ass_subtitles_path="/path/to/subs.ass",
                output_path="/path/to/output.mkv",
                darkness_percent=0
            )
        
        assert "ASS subtitle file not found" in str(exc_info.value)

    @patch('os.path.isfile')
    def test_process_video_background_invalid_darkness(self, mock_isfile, processor, mock_logger):
        """Test video background processing with invalid darkness percentage."""
        # Mock all files exist to get past file validation
        mock_isfile.return_value = True
        
        with pytest.raises(ValueError) as exc_info:
            processor.process_video_background(
                video_path="/path/to/video.mp4",
                audio_path="/path/to/audio.wav",
                ass_subtitles_path="/path/to/subs.ass",
                output_path="/path/to/output.mkv",
                darkness_percent=150  # Invalid: > 100
            )
        
        assert "between 0 and 100" in str(exc_info.value)

    @patch.object(VideoBackgroundProcessor, 'execute_command_with_fallback')
    @patch.object(VideoBackgroundProcessor, 'get_audio_duration')
    @patch('os.path.isfile')
    def test_process_video_background_with_fonts_dir(self, mock_isfile, mock_get_duration, mock_execute, processor, mock_logger):
        """Test video background processing with KARAOKE_FONTS_DIR environment variable."""
        mock_isfile.return_value = True
        mock_get_duration.return_value = 180.5
        mock_execute.return_value = None
        
        with patch.dict(os.environ, {'KARAOKE_FONTS_DIR': '/path/to/fonts'}):
            with patch('os.path.isdir', return_value=True):
                processor.process_video_background(
                    video_path="/path/to/video.mp4",
                    audio_path="/path/to/audio.wav",
                    ass_subtitles_path="/path/to/subs.ass",
                    output_path="/path/to/output.mkv",
                    darkness_percent=0
                )
        
        # Verify fonts directory was included in command
        call_args = mock_execute.call_args
        gpu_cmd = call_args[0][0]
        assert "fontsdir=" in gpu_cmd

    @patch.object(VideoBackgroundProcessor, 'execute_command_with_fallback')
    @patch.object(VideoBackgroundProcessor, 'get_audio_duration')
    @patch('os.path.isfile')
    def test_process_video_background_calculates_duration_if_not_provided(self, mock_isfile, mock_get_duration, mock_execute, processor, mock_logger):
        """Test that audio duration is calculated if not provided."""
        mock_isfile.return_value = True
        mock_get_duration.return_value = 180.5
        mock_execute.return_value = None
        
        processor.process_video_background(
            video_path="/path/to/video.mp4",
            audio_path="/path/to/audio.wav",
            ass_subtitles_path="/path/to/subs.ass",
            output_path="/path/to/output.mkv",
            darkness_percent=0,
            audio_duration=None  # Not provided
        )
        
        # Should call get_audio_duration
        mock_get_duration.assert_called_once_with("/path/to/audio.wav")

    @patch.object(VideoBackgroundProcessor, 'execute_command_with_fallback')
    @patch('os.path.isfile')
    def test_process_video_background_uses_provided_duration(self, mock_isfile, mock_execute, processor, mock_logger):
        """Test that provided audio duration is used without recalculation."""
        mock_isfile.return_value = True
        mock_execute.return_value = None
        
        with patch.object(processor, 'get_audio_duration') as mock_get_duration:
            processor.process_video_background(
                video_path="/path/to/video.mp4",
                audio_path="/path/to/audio.wav",
                ass_subtitles_path="/path/to/subs.ass",
                output_path="/path/to/output.mkv",
                darkness_percent=0,
                audio_duration=180.5  # Provided
            )
            
            # Should NOT call get_audio_duration
            mock_get_duration.assert_not_called()

    @patch.object(VideoBackgroundProcessor, 'execute_command_with_fallback')
    @patch.object(VideoBackgroundProcessor, 'get_audio_duration')
    @patch('os.path.isfile')
    def test_process_video_background_output_verification(self, mock_isfile, mock_get_duration, mock_execute, processor, mock_logger):
        """Test that output file existence is verified after processing."""
        # Setup: all input files exist, but output does NOT exist after processing
        def isfile_side_effect(path):
            if path == "/path/to/output.mkv":
                return False  # Output doesn't exist
            return True  # All inputs exist
        
        mock_isfile.side_effect = isfile_side_effect
        mock_get_duration.return_value = 180.5
        mock_execute.return_value = None
        
        with pytest.raises(Exception) as exc_info:
            processor.process_video_background(
                video_path="/path/to/video.mp4",
                audio_path="/path/to/audio.wav",
                ass_subtitles_path="/path/to/subs.ass",
                output_path="/path/to/output.mkv",
                darkness_percent=0
            )
        
        assert "Output video file was not created" in str(exc_info.value)

