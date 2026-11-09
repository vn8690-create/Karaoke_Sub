"""
Finalization pipeline stage.

This stage handles the final processing:
- Multi-format video encoding (4K lossless, 4K lossy, 720p)
- CDG/TXT package generation
- Distribution (YouTube, Dropbox, Google Drive)
- Discord notifications

This wraps the existing KaraokeFinalise module.
"""
import logging
import os
from typing import Any, Dict, List, Optional

from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
from karaoke_gen.pipeline.context import PipelineContext


class FinalizeStage(PipelineStage):
    """
    Finalization stage.
    
    Handles encoding, packaging, and distribution of the final
    karaoke video and related files.
    """
    
    def __init__(
        self,
        enable_cdg: bool = True,
        enable_txt: bool = True,
        non_interactive: bool = False,
        server_side_mode: bool = False,
        youtube_credentials: Optional[Dict[str, Any]] = None,
        youtube_description_template: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the finalize stage.
        
        Args:
            enable_cdg: Generate CDG+MP3 package
            enable_txt: Generate TXT+MP3 package
            non_interactive: Run without user prompts
            server_side_mode: Running on server (disables local-only features)
            youtube_credentials: Pre-loaded YouTube OAuth credentials
            youtube_description_template: YouTube video description template
            logger: Logger instance
        """
        self.enable_cdg = enable_cdg
        self.enable_txt = enable_txt
        self.non_interactive = non_interactive
        self.server_side_mode = server_side_mode
        self.youtube_credentials = youtube_credentials
        self.youtube_description_template = youtube_description_template
        self.logger = logger or logging.getLogger(__name__)
    
    @property
    def name(self) -> str:
        return "finalize"
    
    @property
    def required_inputs(self) -> List[str]:
        # Requires render output (with_vocals video)
        return ["render", "screens"]
    
    @property
    def optional_inputs(self) -> List[str]:
        return ["separation"]
    
    @property
    def output_keys(self) -> List[str]:
        return [
            "final_video_lossless_4k_mp4",
            "final_video_lossless_4k_mkv",
            "final_video_lossy_4k_mp4",
            "final_video_lossy_720p_mp4",
            "cdg_zip_path",
            "txt_zip_path",
            "brand_code",
            "youtube_url",
            "dropbox_link",
        ]
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute finalization.
        
        Args:
            context: Pipeline context with render outputs
            
        Returns:
            StageResult with final file paths
        """
        import time
        start_time = time.time()
        
        try:
            context.update_progress(self.name, 0, "Starting finalization")
            context.log("INFO", f"Finalizing: {context.artist} - {context.title}")
            
            from karaoke_gen.karaoke_finalise.karaoke_finalise import KaraokeFinalise
            
            # Get the selected instrumental path
            separation = context.stage_outputs.get("separation", {})
            
            # Prefer combined instrumental with backing if available
            instrumental_path = None
            combined = separation.get("combined_instrumentals", {})
            if combined:
                # Get first combined instrumental
                instrumental_path = list(combined.values())[0]
            elif separation.get("clean_instrumental", {}).get("instrumental"):
                instrumental_path = separation["clean_instrumental"]["instrumental"]
            
            if not instrumental_path or not os.path.exists(instrumental_path):
                return StageResult(
                    status=StageStatus.FAILED,
                    error_message="No instrumental audio file found",
                )
            
            # Build CDG styles from context style_params
            cdg_styles = None
            if context.style_params and context.style_params.get("cdg"):
                cdg_styles = context.style_params["cdg"]
            
            context.update_progress(self.name, 10, "Initializing KaraokeFinalise")
            
            # Create KaraokeFinalise instance
            finalise = KaraokeFinalise(
                logger=self.logger,
                log_level=logging.INFO,
                dry_run=False,
                instrumental_format="flac",
                enable_cdg=self.enable_cdg or context.enable_cdg,
                enable_txt=self.enable_txt or context.enable_txt,
                cdg_styles=cdg_styles,
                brand_prefix=context.brand_prefix,
                organised_dir=None,  # Not used directly
                organised_dir_rclone_root=context.organised_dir_rclone_root,
                public_share_dir=None,
                discord_webhook_url=context.discord_webhook_url,
                youtube_client_secrets_file=None,
                youtube_description_file=None,  # Use template instead
                user_youtube_credentials=self.youtube_credentials,
                rclone_destination=context.rclone_destination,
                email_template_file=None,
                non_interactive=self.non_interactive,
                server_side_mode=self.server_side_mode,
                selected_instrumental_file=instrumental_path,
            )
            
            # Change to output directory for KaraokeFinalise
            original_cwd = os.getcwd()
            try:
                os.chdir(context.output_dir)
                
                context.update_progress(self.name, 20, "Processing finalization")
                
                # Run finalization
                result = finalise.process()
                
            finally:
                os.chdir(original_cwd)
            
            # Build outputs from result
            outputs = {
                "final_video_lossless_4k_mp4": result.get("final_video"),
                "final_video_lossless_4k_mkv": result.get("final_video_mkv"),
                "final_video_lossy_4k_mp4": result.get("final_video_lossy"),
                "final_video_lossy_720p_mp4": result.get("final_video_720p"),
                "cdg_zip_path": result.get("final_karaoke_cdg_zip"),
                "txt_zip_path": result.get("final_karaoke_txt_zip"),
                "brand_code": result.get("brand_code"),
                "youtube_url": result.get("youtube_url"),
            }
            
            context.update_progress(self.name, 100, "Finalization complete")
            
            duration = time.time() - start_time
            context.log("INFO", f"Finalization completed in {duration:.1f}s")
            
            if outputs.get("brand_code"):
                context.log("INFO", f"Brand code: {outputs['brand_code']}")
            if outputs.get("youtube_url"):
                context.log("INFO", f"YouTube URL: {outputs['youtube_url']}")
            
            return StageResult(
                status=StageStatus.COMPLETED,
                outputs=outputs,
                duration_seconds=duration,
            )
            
        except Exception as e:
            duration = time.time() - start_time
            context.log("ERROR", f"Finalization failed: {str(e)}")
            return StageResult(
                status=StageStatus.FAILED,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
                duration_seconds=duration,
            )
