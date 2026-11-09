"""
Lyrics transcription pipeline stage.

This stage handles:
- Transcription of lyrics from audio (using AudioShake API)
- Fetching lyrics from online sources (Genius, Spotify, etc.)
- Synchronization of lyrics with audio timing
- Generation of LRC, ASS, and corrected text files

Note: Video rendering is handled by the RenderStage, not here.
"""
import logging
import os
from typing import Any, Dict, List, Optional

from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
from karaoke_gen.pipeline.context import PipelineContext


class TranscriptionStage(PipelineStage):
    """
    Lyrics transcription stage.
    
    Transcribes and synchronizes lyrics from audio.
    Does NOT render video - that's handled by RenderStage.
    """
    
    def __init__(
        self,
        style_params_json: Optional[str] = None,
        lyrics_file: Optional[str] = None,
        skip_transcription: bool = False,
        skip_transcription_review: bool = False,
        subtitle_offset_ms: int = 0,
        lyrics_artist: Optional[str] = None,
        lyrics_title: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the transcription stage.
        
        Args:
            style_params_json: Path to style parameters JSON file
            lyrics_file: Path to existing lyrics file (optional)
            skip_transcription: If True, skip automatic transcription
            skip_transcription_review: If True, skip interactive review
            subtitle_offset_ms: Offset for subtitle timing in milliseconds
            lyrics_artist: Override artist name for lyrics search
            lyrics_title: Override title for lyrics search
            logger: Logger instance
        """
        self.style_params_json = style_params_json
        self.lyrics_file = lyrics_file
        self.skip_transcription = skip_transcription
        self.skip_transcription_review = skip_transcription_review
        self.subtitle_offset_ms = subtitle_offset_ms
        self.lyrics_artist = lyrics_artist
        self.lyrics_title = lyrics_title
        self.logger = logger or logging.getLogger(__name__)
    
    @property
    def name(self) -> str:
        return "transcription"
    
    @property
    def required_inputs(self) -> List[str]:
        # No required inputs from other stages - uses context.input_audio_path
        return []
    
    @property
    def optional_inputs(self) -> List[str]:
        # Can use separation output for vocals-only transcription
        return ["separation"]
    
    @property
    def output_keys(self) -> List[str]:
        return [
            "lrc_filepath",        # Path to LRC lyrics file
            "ass_filepath",        # Path to ASS subtitle file
            "corrected_txt_path",  # Path to corrected text file
            "corrections_result",  # Full corrections JSON data
            "countdown_padding_seconds",  # Countdown padding applied (if any)
        ]
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute lyrics transcription.
        
        Args:
            context: Pipeline context with input audio path
            
        Returns:
            StageResult with lyrics file paths
        """
        import time
        start_time = time.time()
        
        try:
            context.update_progress(self.name, 0, "Starting lyrics transcription")
            context.log("INFO", f"Transcribing lyrics for: {context.artist} - {context.title}")
            
            if self.skip_transcription:
                context.log("INFO", "Skipping transcription (skip_transcription=True)")
                return StageResult(
                    status=StageStatus.SKIPPED,
                    outputs={},
                )
            
            # Get style params from context or use instance value
            style_params_json = self.style_params_json
            if not style_params_json and context.style_params:
                # Write style params to temp file
                import json
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(context.style_params, f)
                    style_params_json = f.name
                    context.add_temp_path(style_params_json)
            
            # Create LyricsProcessor instance
            # Note: render_video=False because we handle rendering in RenderStage
            from karaoke_gen.lyrics_processor import LyricsProcessor
            
            processor = LyricsProcessor(
                logger=self.logger,
                style_params_json=style_params_json,
                lyrics_file=self.lyrics_file,
                skip_transcription=self.skip_transcription,
                skip_transcription_review=self.skip_transcription_review,
                render_video=False,  # Don't render video here
                subtitle_offset_ms=self.subtitle_offset_ms,
            )
            
            context.update_progress(self.name, 20, "Running transcription")
            
            # Run transcription
            result = processor.transcribe_lyrics(
                input_audio_wav=context.input_audio_path,
                artist=context.artist,
                title=context.title,
                track_output_dir=context.output_dir,
                lyrics_artist=self.lyrics_artist or context.artist,
                lyrics_title=self.lyrics_title or context.title,
            )
            
            # Build output dictionary
            outputs = {}
            
            if result.get("lrc_filepath"):
                outputs["lrc_filepath"] = result["lrc_filepath"]
                
            if result.get("ass_filepath"):
                outputs["ass_filepath"] = result["ass_filepath"]
                
            if result.get("corrected_txt_path"):
                outputs["corrected_txt_path"] = result["corrected_txt_path"]
                
            # Get corrections data if available
            if hasattr(processor, 'corrections_result'):
                outputs["corrections_result"] = processor.corrections_result
                
            # Check for countdown padding
            lyrics_dir = os.path.join(context.output_dir, "lyrics")
            countdown_file = os.path.join(lyrics_dir, "countdown_padding_seconds.txt")
            if os.path.exists(countdown_file):
                with open(countdown_file, 'r') as f:
                    try:
                        outputs["countdown_padding_seconds"] = float(f.read().strip())
                    except ValueError:
                        pass
            
            context.update_progress(self.name, 100, "Transcription complete")
            
            duration = time.time() - start_time
            context.log("INFO", f"Lyrics transcription completed in {duration:.1f}s")
            
            return StageResult(
                status=StageStatus.COMPLETED,
                outputs=outputs,
                duration_seconds=duration,
            )
            
        except Exception as e:
            duration = time.time() - start_time
            context.log("ERROR", f"Lyrics transcription failed: {str(e)}")
            return StageResult(
                status=StageStatus.FAILED,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
                duration_seconds=duration,
            )
