"""
Tests for audio_editing_service.py - Custom instrumental creation.

These tests mock the storage service and shared karaoke_gen modules to verify:
- GCS file download/upload operations
- Audio editing delegation to shared AudioEditor
- Mute region validation
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, ANY


class TestAudioEditingServiceInit:
    """Test AudioEditingService initialization."""
    
    @patch("backend.services.audio_editing_service.StorageService")
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_init_creates_dependencies(self, mock_editor_class, mock_storage_class):
        """Test initialization creates storage service and editor."""
        from backend.services.audio_editing_service import AudioEditingService
        
        service = AudioEditingService()
        
        mock_storage_class.assert_called_once()
        mock_editor_class.assert_called_once_with(output_format="flac")
    
    @patch("backend.services.audio_editing_service.StorageService")
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_init_with_custom_format(self, mock_editor_class, mock_storage_class):
        """Test initialization with custom output format."""
        from backend.services.audio_editing_service import AudioEditingService
        
        service = AudioEditingService(output_format="wav")
        
        mock_editor_class.assert_called_once_with(output_format="wav")
    
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_init_with_provided_storage_service(self, mock_editor_class):
        """Test initialization with externally provided storage service."""
        from backend.services.audio_editing_service import AudioEditingService
        
        mock_storage = Mock()
        service = AudioEditingService(storage_service=mock_storage)
        
        assert service.storage_service is mock_storage


class TestCreateCustomInstrumental:
    """Test create_custom_instrumental method."""
    
    @patch("backend.services.audio_editing_service.StorageService")
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_create_custom_instrumental_success(
        self, mock_editor_class, mock_storage_class
    ):
        """Test creating a custom instrumental successfully."""
        from backend.services.audio_editing_service import AudioEditingService
        
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage
        
        mock_result = Mock()
        mock_result.total_muted_duration_seconds = 15.5
        mock_result.mute_regions_applied = [Mock(), Mock(), Mock()]
        mock_result.output_path = None  # Will be set by service
        
        mock_editor = Mock()
        mock_editor.create_custom_instrumental.return_value = mock_result
        mock_editor_class.return_value = mock_editor
        
        service = AudioEditingService()
        
        # Create mock mute regions
        mock_mute1 = Mock()
        mock_mute2 = Mock()
        mute_regions = [mock_mute1, mock_mute2]
        
        result = service.create_custom_instrumental(
            gcs_clean_instrumental_path="uploads/job123/clean.flac",
            gcs_backing_vocals_path="uploads/job123/backing.flac",
            mute_regions=mute_regions,
            gcs_output_path="uploads/job123/custom.flac",
            job_id="job123",
        )
        
        # Verify downloads
        assert mock_storage.download_file.call_count == 2
        
        # Verify editor was called
        mock_editor.create_custom_instrumental.assert_called_once()
        call_kwargs = mock_editor.create_custom_instrumental.call_args.kwargs
        assert call_kwargs["mute_regions"] == mute_regions
        
        # Verify upload
        mock_storage.upload_file.assert_called_once()
        
        # Verify result path was updated
        assert result.output_path == "uploads/job123/custom.flac"
    
    @patch("backend.services.audio_editing_service.StorageService")
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_create_custom_instrumental_downloads_both_files(
        self, mock_editor_class, mock_storage_class
    ):
        """Test that both input files are downloaded."""
        from backend.services.audio_editing_service import AudioEditingService
        
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage
        
        mock_result = Mock()
        mock_result.total_muted_duration_seconds = 0
        mock_result.mute_regions_applied = []
        
        mock_editor = Mock()
        mock_editor.create_custom_instrumental.return_value = mock_result
        mock_editor_class.return_value = mock_editor
        
        service = AudioEditingService()
        
        service.create_custom_instrumental(
            gcs_clean_instrumental_path="uploads/job123/clean.flac",
            gcs_backing_vocals_path="uploads/job123/backing.flac",
            mute_regions=[],
            gcs_output_path="uploads/job123/output.flac",
            job_id="job123",
        )
        
        # Verify both files were downloaded
        download_calls = mock_storage.download_file.call_args_list
        assert len(download_calls) == 2
        
        # First call should be clean instrumental
        assert download_calls[0][0][0] == "uploads/job123/clean.flac"
        # Second call should be backing vocals
        assert download_calls[1][0][0] == "uploads/job123/backing.flac"


class TestCreatePreview:
    """Test create_preview method."""
    
    @patch("pydub.AudioSegment")
    @patch("backend.services.audio_editing_service.StorageService")
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_create_preview_success(
        self, mock_editor_class, mock_storage_class, mock_audio_segment
    ):
        """Test creating a preview successfully."""
        from backend.services.audio_editing_service import AudioEditingService
        
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage
        
        mock_preview = Mock()
        mock_preview.export = Mock()
        mock_preview.__getitem__ = Mock(return_value=mock_preview)
        
        mock_editor = Mock()
        mock_editor.preview_with_mutes.return_value = mock_preview
        mock_editor_class.return_value = mock_editor
        
        service = AudioEditingService()
        
        result = service.create_preview(
            gcs_clean_instrumental_path="uploads/job123/clean.flac",
            gcs_backing_vocals_path="uploads/job123/backing.flac",
            mute_regions=[Mock(), Mock()],
            gcs_preview_path="uploads/job123/preview.flac",
            job_id="job123",
        )
        
        # Verify editor was called
        mock_editor.preview_with_mutes.assert_called_once()
        
        # Verify result
        assert result == "uploads/job123/preview.flac"
    
    @patch("pydub.AudioSegment")
    @patch("backend.services.audio_editing_service.StorageService")
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_create_preview_with_duration_limit(
        self, mock_editor_class, mock_storage_class, mock_audio_segment
    ):
        """Test creating a preview with duration limit."""
        from backend.services.audio_editing_service import AudioEditingService
        
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage
        
        mock_preview = Mock()
        mock_truncated = Mock()
        mock_preview.__getitem__ = Mock(return_value=mock_truncated)
        mock_truncated.export = Mock()
        
        mock_editor = Mock()
        mock_editor.preview_with_mutes.return_value = mock_preview
        mock_editor_class.return_value = mock_editor
        
        service = AudioEditingService()
        
        service.create_preview(
            gcs_clean_instrumental_path="uploads/job123/clean.flac",
            gcs_backing_vocals_path="uploads/job123/backing.flac",
            mute_regions=[],
            gcs_preview_path="uploads/job123/preview.flac",
            job_id="job123",
            preview_duration_seconds=30.0,
        )
        
        # Verify preview was truncated (30 seconds = 30000ms)
        mock_preview.__getitem__.assert_called_once_with(slice(None, 30000))


class TestMuteBackingVocalsOnly:
    """Test mute_backing_vocals_only method."""
    
    @patch("backend.services.audio_editing_service.StorageService")
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_mute_backing_vocals_only(self, mock_editor_class, mock_storage_class):
        """Test muting backing vocals without combining."""
        from backend.services.audio_editing_service import AudioEditingService
        
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage
        
        mock_editor = Mock()
        mock_editor_class.return_value = mock_editor
        
        service = AudioEditingService()
        
        mute_regions = [Mock(), Mock()]
        
        result = service.mute_backing_vocals_only(
            gcs_backing_vocals_path="uploads/job123/backing.flac",
            mute_regions=mute_regions,
            gcs_output_path="uploads/job123/muted_backing.flac",
            job_id="job123",
        )
        
        # Verify only one file was downloaded
        mock_storage.download_file.assert_called_once()
        assert mock_storage.download_file.call_args[0][0] == "uploads/job123/backing.flac"
        
        # Verify editor method was called
        mock_editor.apply_mute_to_single_track.assert_called_once()
        call_kwargs = mock_editor.apply_mute_to_single_track.call_args.kwargs
        assert call_kwargs["mute_regions"] == mute_regions
        
        # Verify upload
        mock_storage.upload_file.assert_called_once()
        
        # Verify result
        assert result == "uploads/job123/muted_backing.flac"


class TestValidateMuteRegions:
    """Test validate_mute_regions method.
    
    Note: MuteRegion uses pydantic validation that rejects invalid values at
    creation time. These tests use Mock objects to test the validation logic
    in the service, simulating edge cases that would normally be rejected.
    """
    
    @patch("backend.services.audio_editing_service.StorageService")
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_valid_mute_regions(self, mock_editor_class, mock_storage_class):
        """Test validation passes for valid mute regions."""
        from backend.services.audio_editing_service import AudioEditingService
        from karaoke_gen.instrumental_review import MuteRegion
        
        service = AudioEditingService()
        
        mute_regions = [
            MuteRegion(start_seconds=10.0, end_seconds=15.0),
            MuteRegion(start_seconds=30.0, end_seconds=45.0),
        ]
        
        errors = service.validate_mute_regions(mute_regions, total_duration_seconds=180.0)
        
        assert errors == []
    
    @patch("backend.services.audio_editing_service.StorageService")
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_negative_start_seconds(self, mock_editor_class, mock_storage_class):
        """Test validation catches negative start time.
        
        Uses Mock since MuteRegion pydantic model rejects negative values.
        """
        from backend.services.audio_editing_service import AudioEditingService
        
        service = AudioEditingService()
        
        # Use mock to simulate invalid region (pydantic would reject this)
        mock_region = Mock()
        mock_region.start_seconds = -5.0
        mock_region.end_seconds = 10.0
        
        errors = service.validate_mute_regions([mock_region], total_duration_seconds=180.0)
        
        assert len(errors) == 1
        assert "cannot be negative" in errors[0]
    
    @patch("backend.services.audio_editing_service.StorageService")
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_end_before_start(self, mock_editor_class, mock_storage_class):
        """Test validation catches end time before start time."""
        from backend.services.audio_editing_service import AudioEditingService
        
        service = AudioEditingService()
        
        # Use mock to simulate invalid region
        mock_region = Mock()
        mock_region.start_seconds = 30.0
        mock_region.end_seconds = 20.0
        
        errors = service.validate_mute_regions([mock_region], total_duration_seconds=180.0)
        
        assert len(errors) == 1
        assert "must be after" in errors[0]
    
    @patch("backend.services.audio_editing_service.StorageService")
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_start_exceeds_duration(self, mock_editor_class, mock_storage_class):
        """Test validation catches start time exceeding audio duration."""
        from backend.services.audio_editing_service import AudioEditingService
        from karaoke_gen.instrumental_review import MuteRegion
        
        service = AudioEditingService()
        
        mute_regions = [
            MuteRegion(start_seconds=200.0, end_seconds=210.0),
        ]
        
        errors = service.validate_mute_regions(mute_regions, total_duration_seconds=180.0)
        
        assert len(errors) == 1
        assert "exceeds audio duration" in errors[0]
    
    @patch("backend.services.audio_editing_service.StorageService")
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_end_exceeds_duration_is_warning_not_error(
        self, mock_editor_class, mock_storage_class
    ):
        """Test that end time exceeding duration is logged as warning, not error."""
        from backend.services.audio_editing_service import AudioEditingService
        from karaoke_gen.instrumental_review import MuteRegion
        
        service = AudioEditingService()
        
        mute_regions = [
            MuteRegion(start_seconds=170.0, end_seconds=200.0),  # End exceeds 180s
        ]
        
        errors = service.validate_mute_regions(mute_regions, total_duration_seconds=180.0)
        
        # Should not be an error (will be clamped)
        assert len(errors) == 0
    
    @patch("backend.services.audio_editing_service.StorageService")
    @patch("backend.services.audio_editing_service.AudioEditor")
    def test_multiple_errors(self, mock_editor_class, mock_storage_class):
        """Test validation reports multiple errors."""
        from backend.services.audio_editing_service import AudioEditingService
        from karaoke_gen.instrumental_review import MuteRegion
        
        service = AudioEditingService()
        
        # Use mocks for invalid regions
        mock_region1 = Mock()
        mock_region1.start_seconds = -5.0
        mock_region1.end_seconds = 10.0
        
        mock_region2 = Mock()
        mock_region2.start_seconds = 30.0
        mock_region2.end_seconds = 20.0  # End before start
        
        mock_region3 = Mock()
        mock_region3.start_seconds = 200.0  # Exceeds duration
        mock_region3.end_seconds = 210.0
        
        mute_regions = [mock_region1, mock_region2, mock_region3]
        
        errors = service.validate_mute_regions(mute_regions, total_duration_seconds=180.0)
        
        assert len(errors) == 3

