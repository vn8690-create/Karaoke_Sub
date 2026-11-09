"""
Title and end screen generation pipeline stage.

This stage handles the generation of:
- Title screen video (intro)
- End screen video (outro)
- Corresponding PNG/JPG images

These are generated using the video_generator module.
"""
import logging
import os
from typing import Any, Dict, List, Optional

from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
from karaoke_gen.pipeline.context import PipelineContext


class ScreensStage(PipelineStage):
    """
    Title and end screen generation stage.
    
    Generates title and end screen videos/images using configured
    style parameters.
    """
    
    def __init__(
        self,
        output_png: bool = True,
        output_jpg: bool = True,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the screens stage.
        
        Args:
            output_png: Generate PNG format images
            output_jpg: Generate JPG format images
            logger: Logger instance
        """
        self.output_png = output_png
        self.output_jpg = output_jpg
        self.logger = logger or logging.getLogger(__name__)
    
    @property
    def name(self) -> str:
        return "screens"
    
    @property
    def required_inputs(self) -> List[str]:
        return []
    
    @property
    def output_keys(self) -> List[str]:
        return [
            "title_video_path",    # Path to title screen video
            "title_png_path",      # Path to title screen PNG
            "title_jpg_path",      # Path to title screen JPG
            "end_video_path",      # Path to end screen video
            "end_png_path",        # Path to end screen PNG
            "end_jpg_path",        # Path to end screen JPG
        ]
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute screen generation.
        
        Args:
            context: Pipeline context with style params
            
        Returns:
            StageResult with screen file paths
        """
        import time
        start_time = time.time()
        
        try:
            context.update_progress(self.name, 0, "Generating title and end screens")
            context.log("INFO", f"Generating screens for: {context.artist} - {context.title}")
            
            from karaoke_gen.video_generator import VideoGenerator
            
            # Create video generator
            generator = VideoGenerator(
                artist=context.artist,
                title=context.title,
                output_dir=context.output_dir,
                style_params=context.style_params,
                logger=self.logger,
            )
            
            outputs = {}
            
            context.update_progress(self.name, 25, "Generating title screen")
            
            # Generate title screen
            title_result = generator.generate_title_screen(
                output_png=self.output_png,
                output_jpg=self.output_jpg,
            )
            
            if title_result:
                outputs["title_video_path"] = title_result.get("video_path")
                outputs["title_png_path"] = title_result.get("png_path")
                outputs["title_jpg_path"] = title_result.get("jpg_path")
            
            context.update_progress(self.name, 75, "Generating end screen")
            
            # Generate end screen
            end_result = generator.generate_end_screen(
                output_png=self.output_png,
                output_jpg=self.output_jpg,
            )
            
            if end_result:
                outputs["end_video_path"] = end_result.get("video_path")
                outputs["end_png_path"] = end_result.get("png_path")
                outputs["end_jpg_path"] = end_result.get("jpg_path")
            
            context.update_progress(self.name, 100, "Screen generation complete")
            
            duration = time.time() - start_time
            context.log("INFO", f"Screen generation completed in {duration:.1f}s")
            
            return StageResult(
                status=StageStatus.COMPLETED,
                outputs=outputs,
                duration_seconds=duration,
            )
            
        except Exception as e:
            duration = time.time() - start_time
            context.log("ERROR", f"Screen generation failed: {str(e)}")
            return StageResult(
                status=StageStatus.FAILED,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
                duration_seconds=duration,
            )
