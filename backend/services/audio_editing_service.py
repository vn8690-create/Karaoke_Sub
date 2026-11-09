"""
Audio editing service for creating custom instrumentals.

This service wraps the shared karaoke_gen.instrumental_review module
to provide GCS-integrated audio editing capabilities.
"""

import logging
import os
import tempfile
from typing import List, Optional

from backend.services.storage_service import StorageService
from karaoke_gen.instrumental_review import (
    AudioEditor,
    MuteRegion,
)
from karaoke_gen.instrumental_review.models import CustomInstrumentalResult


logger = logging.getLogger(__name__)


class AudioEditingService:
    """
    Service for creating custom instrumental tracks with GCS integration.
    
    This service acts as a thin wrapper around the shared AudioEditor
    class, handling GCS download/upload operations.
    
    The actual editing logic is in the shared karaoke_gen.instrumental_review
    module, ensuring feature parity between local and remote workflows.
    """
    
    def __init__(
        self,
        storage_service: Optional[StorageService] = None,
        output_format: str = "flac",
    ):
        """
        Initialize the audio editing service.
        
        Args:
            storage_service: GCS storage service. If not provided, a new
                instance will be created.
            output_format: Output audio format. Default is "flac".
        """
        self.storage_service = storage_service or StorageService()
        self.editor = AudioEditor(output_format=output_format)
    
    def create_custom_instrumental(
        self,
        gcs_clean_instrumental_path: str,
        gcs_backing_vocals_path: str,
        mute_regions: List[MuteRegion],
        gcs_output_path: str,
        job_id: str,
    ) -> CustomInstrumentalResult:
        """
        Create a custom instrumental by muting regions of backing vocals.
        
        This method:
        1. Downloads clean instrumental and backing vocals from GCS
        2. Applies mute regions to backing vocals
        3. Combines with clean instrumental
        4. Uploads result to GCS
        
        Args:
            gcs_clean_instrumental_path: Path to clean instrumental in GCS
            gcs_backing_vocals_path: Path to backing vocals in GCS
            mute_regions: List of regions to mute in backing vocals
            gcs_output_path: Where to upload the custom instrumental in GCS
            job_id: Job ID for logging
        
        Returns:
            CustomInstrumentalResult with details about the created file
        """
        logger.info(
            f"[{job_id}] Creating custom instrumental with "
            f"{len(mute_regions)} mute regions"
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download input files
            local_clean_path = os.path.join(temp_dir, "clean_instrumental.flac")
            local_backing_path = os.path.join(temp_dir, "backing_vocals.flac")
            local_output_path = os.path.join(temp_dir, "custom_instrumental.flac")
            
            logger.debug(f"[{job_id}] Downloading clean instrumental")
            self.storage_service.download_file(
                gcs_clean_instrumental_path,
                local_clean_path
            )
            
            logger.debug(f"[{job_id}] Downloading backing vocals")
            self.storage_service.download_file(
                gcs_backing_vocals_path,
                local_backing_path
            )
            
            # Create custom instrumental using shared editor
            result = self.editor.create_custom_instrumental(
                clean_instrumental_path=local_clean_path,
                backing_vocals_path=local_backing_path,
                mute_regions=mute_regions,
                output_path=local_output_path,
            )
            
            # Upload result to GCS
            logger.debug(f"[{job_id}] Uploading custom instrumental to GCS")
            self.storage_service.upload_file(local_output_path, gcs_output_path)
            
            # Update result with GCS path
            result.output_path = gcs_output_path
            
            logger.info(
                f"[{job_id}] Custom instrumental created: {gcs_output_path}, "
                f"muted {result.total_muted_duration_seconds:.1f}s across "
                f"{len(result.mute_regions_applied)} regions"
            )
            
            return result
    
    def create_preview(
        self,
        gcs_clean_instrumental_path: str,
        gcs_backing_vocals_path: str,
        mute_regions: List[MuteRegion],
        gcs_preview_path: str,
        job_id: str,
        preview_duration_seconds: Optional[float] = None,
    ) -> str:
        """
        Create a preview of the custom instrumental.
        
        This is similar to create_custom_instrumental but optimized for
        quick preview generation (optionally truncated duration).
        
        Args:
            gcs_clean_instrumental_path: Path to clean instrumental in GCS
            gcs_backing_vocals_path: Path to backing vocals in GCS
            mute_regions: List of regions to mute
            gcs_preview_path: Where to upload the preview in GCS
            job_id: Job ID for logging
            preview_duration_seconds: Optional max duration for preview
        
        Returns:
            GCS path to the uploaded preview
        """
        logger.info(f"[{job_id}] Creating preview with {len(mute_regions)} mute regions")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download input files
            local_clean_path = os.path.join(temp_dir, "clean_instrumental.flac")
            local_backing_path = os.path.join(temp_dir, "backing_vocals.flac")
            local_preview_path = os.path.join(temp_dir, "preview.flac")
            
            self.storage_service.download_file(
                gcs_clean_instrumental_path,
                local_clean_path
            )
            self.storage_service.download_file(
                gcs_backing_vocals_path,
                local_backing_path
            )
            
            # Generate preview
            from pydub import AudioSegment
            
            preview = self.editor.preview_with_mutes(
                clean_instrumental_path=local_clean_path,
                backing_vocals_path=local_backing_path,
                mute_regions=mute_regions,
            )
            
            # Optionally truncate
            if preview_duration_seconds:
                max_ms = int(preview_duration_seconds * 1000)
                preview = preview[:max_ms]
            
            # Export and upload
            preview.export(local_preview_path, format="flac")
            self.storage_service.upload_file(local_preview_path, gcs_preview_path)
            
            logger.info(f"[{job_id}] Preview created: {gcs_preview_path}")
            
            return gcs_preview_path
    
    def mute_backing_vocals_only(
        self,
        gcs_backing_vocals_path: str,
        mute_regions: List[MuteRegion],
        gcs_output_path: str,
        job_id: str,
    ) -> str:
        """
        Apply mute regions to backing vocals without combining with instrumental.
        
        This is useful for creating an edited backing vocals track that
        can be combined with the instrumental later.
        
        Args:
            gcs_backing_vocals_path: Path to backing vocals in GCS
            mute_regions: List of regions to mute
            gcs_output_path: Where to upload the edited backing vocals
            job_id: Job ID for logging
        
        Returns:
            GCS path to the uploaded edited backing vocals
        """
        logger.info(
            f"[{job_id}] Muting backing vocals with {len(mute_regions)} regions"
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            local_backing_path = os.path.join(temp_dir, "backing_vocals.flac")
            local_output_path = os.path.join(temp_dir, "muted_backing.flac")
            
            self.storage_service.download_file(
                gcs_backing_vocals_path,
                local_backing_path
            )
            
            self.editor.apply_mute_to_single_track(
                audio_path=local_backing_path,
                mute_regions=mute_regions,
                output_path=local_output_path,
            )
            
            self.storage_service.upload_file(local_output_path, gcs_output_path)
            
            logger.info(f"[{job_id}] Muted backing vocals: {gcs_output_path}")
            
            return gcs_output_path
    
    def validate_mute_regions(
        self,
        mute_regions: List[MuteRegion],
        total_duration_seconds: float,
    ) -> List[str]:
        """
        Validate mute regions for consistency.
        
        Args:
            mute_regions: List of mute regions to validate
            total_duration_seconds: Total duration of the audio
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        for i, region in enumerate(mute_regions):
            if region.start_seconds < 0:
                errors.append(
                    f"Region {i}: start_seconds ({region.start_seconds}) cannot be negative"
                )
            
            if region.end_seconds <= region.start_seconds:
                errors.append(
                    f"Region {i}: end_seconds ({region.end_seconds}) must be after "
                    f"start_seconds ({region.start_seconds})"
                )
            
            if region.start_seconds > total_duration_seconds:
                errors.append(
                    f"Region {i}: start_seconds ({region.start_seconds}) exceeds "
                    f"audio duration ({total_duration_seconds})"
                )
            
            if region.end_seconds > total_duration_seconds:
                # Not an error, but log a warning - the region will be clamped
                logger.warning(
                    f"Region {i}: end_seconds ({region.end_seconds}) exceeds "
                    f"audio duration ({total_duration_seconds}), will be clamped"
                )
        
        return errors
