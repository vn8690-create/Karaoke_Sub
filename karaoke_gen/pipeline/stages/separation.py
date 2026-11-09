"""
Audio separation pipeline stage.

This stage handles the separation of audio into stems:
- Clean instrumental (vocals removed)
- Vocals
- Backing vocals and lead vocals (optional)
- Other stems (drums, bass, guitar, etc.)
- Combined instrumental with backing vocals

The stage delegates to AudioProcessor but provides a consistent
pipeline interface.
"""
import logging
import os
from typing import Any, Dict, List, Optional

from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
from karaoke_gen.pipeline.context import PipelineContext


class SeparationStage(PipelineStage):
    """
    Audio separation stage.
    
    Separates audio into stems using configured models.
    Supports both local processing and remote API.
    """
    
    def __init__(
        self,
        model_file_dir: str = "/tmp/audio-separator-models/",
        lossless_output_format: str = "flac",
        clean_instrumental_model: str = "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
        backing_vocals_models: Optional[List[str]] = None,
        other_stems_models: Optional[List[str]] = None,
        logger: Optional[logging.Logger] = None,
        log_level: int = logging.INFO,
        skip_separation: bool = False,
    ):
        """
        Initialize the separation stage.
        
        Args:
            model_file_dir: Directory for model files
            lossless_output_format: Output format (flac, wav, etc.)
            clean_instrumental_model: Model for clean instrumental separation
            backing_vocals_models: Models for backing vocals separation
            other_stems_models: Models for other stems (drums, bass, etc.)
            logger: Logger instance
            log_level: Logging level
            skip_separation: If True, skip separation (for testing)
        """
        self.model_file_dir = model_file_dir
        self.lossless_output_format = lossless_output_format
        self.clean_instrumental_model = clean_instrumental_model
        self.backing_vocals_models = backing_vocals_models or [
            "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"
        ]
        self.other_stems_models = other_stems_models or ["htdemucs_6s.yaml"]
        self.logger = logger or logging.getLogger(__name__)
        self.log_level = log_level
        self.skip_separation = skip_separation
    
    @property
    def name(self) -> str:
        return "separation"
    
    @property
    def required_inputs(self) -> List[str]:
        # No required inputs from other stages - uses context.input_audio_path
        return []
    
    @property
    def output_keys(self) -> List[str]:
        return [
            "clean_instrumental",  # Dict with 'instrumental' and 'vocals' paths
            "other_stems",         # Dict mapping model -> stems dict
            "backing_vocals",      # Dict mapping model -> backing/lead vocals
            "combined_instrumentals",  # Dict mapping model -> combined path
        ]
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute audio separation.
        
        Args:
            context: Pipeline context with input audio path
            
        Returns:
            StageResult with separated stem paths
        """
        import time
        start_time = time.time()
        
        try:
            context.update_progress(self.name, 0, "Starting audio separation")
            context.log("INFO", f"Separating audio: {context.input_audio_path}")
            
            if self.skip_separation:
                context.log("INFO", "Skipping audio separation (skip_separation=True)")
                return StageResult(
                    status=StageStatus.SKIPPED,
                    outputs={},
                )
            
            # Create AudioProcessor instance
            from karaoke_gen.audio_processor import AudioProcessor
            
            processor = AudioProcessor(
                logger=self.logger,
                log_level=self.log_level,
                log_formatter=None,
                model_file_dir=self.model_file_dir,
                lossless_output_format=self.lossless_output_format,
                clean_instrumental_model=self.clean_instrumental_model,
                backing_vocals_models=self.backing_vocals_models,
                other_stems_models=self.other_stems_models,
                ffmpeg_base_command="ffmpeg -y -hide_banner -nostats -loglevel error",
            )
            
            context.update_progress(self.name, 10, "Processing audio separation")
            
            # Run the separation
            result = processor.process_audio_separation(
                audio_file=context.input_audio_path,
                artist_title=context.base_name,
                track_output_dir=context.output_dir,
            )
            
            context.update_progress(self.name, 90, "Audio separation complete")
            
            duration = time.time() - start_time
            context.log("INFO", f"Audio separation completed in {duration:.1f}s")
            
            return StageResult(
                status=StageStatus.COMPLETED,
                outputs=result,
                duration_seconds=duration,
            )
            
        except Exception as e:
            duration = time.time() - start_time
            context.log("ERROR", f"Audio separation failed: {str(e)}")
            return StageResult(
                status=StageStatus.FAILED,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
                duration_seconds=duration,
            )
    
    def apply_countdown_padding(
        self,
        context: PipelineContext,
        separation_result: Dict[str, Any],
        padding_seconds: float,
    ) -> Dict[str, Any]:
        """
        Apply countdown padding to instrumental files.
        
        This is called after transcription determines the padding amount
        needed to synchronize with padded vocals.
        
        Args:
            context: Pipeline context
            separation_result: Original separation result
            padding_seconds: Amount of padding to apply
            
        Returns:
            Updated separation result with padded file paths
        """
        from karaoke_gen.audio_processor import AudioProcessor
        
        processor = AudioProcessor(
            logger=self.logger,
            log_level=self.log_level,
            log_formatter=None,
            model_file_dir=self.model_file_dir,
            lossless_output_format=self.lossless_output_format,
            clean_instrumental_model=self.clean_instrumental_model,
            backing_vocals_models=self.backing_vocals_models,
            other_stems_models=self.other_stems_models,
            ffmpeg_base_command="ffmpeg -y -hide_banner -nostats -loglevel error",
        )
        
        return processor.apply_countdown_padding_to_instrumentals(
            separation_result=separation_result,
            padding_seconds=padding_seconds,
            artist_title=context.base_name,
            track_output_dir=context.output_dir,
        )
