"""
Pipeline context for passing state through pipeline stages.

The PipelineContext is the central data structure that flows through
all pipeline stages, carrying:
- Job metadata (ID, artist, title)
- File paths (input audio, output directory)
- Style configuration
- Outputs from each stage
- Logging and progress callbacks
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import logging


@dataclass
class PipelineContext:
    """
    Shared state passed through pipeline stages.
    
    This context object carries all information needed by pipeline stages
    to perform their work, and accumulates outputs from each stage.
    """
    
    # Job identification
    job_id: str
    artist: str
    title: str
    
    # File paths
    input_audio_path: str
    output_dir: str
    
    # Style configuration (loaded from style_params.json)
    style_params: Dict[str, Any] = field(default_factory=dict)
    
    # Processing options
    enable_cdg: bool = True
    enable_txt: bool = True
    brand_prefix: Optional[str] = None
    enable_youtube_upload: bool = False
    discord_webhook_url: Optional[str] = None
    
    # Distribution options (native API for remote, rclone for local)
    dropbox_path: Optional[str] = None
    gdrive_folder_id: Optional[str] = None
    organised_dir_rclone_root: Optional[str] = None
    rclone_destination: Optional[str] = None
    
    # Accumulated outputs from each stage
    # Keys are typically: separation, transcription, screens, render, finalize
    stage_outputs: Dict[str, Any] = field(default_factory=dict)
    
    # Progress tracking
    current_stage: Optional[str] = None
    progress_percent: int = 0
    
    # Callbacks for progress updates and logging
    on_progress: Optional[Callable[[str, int, str], None]] = None
    on_log: Optional[Callable[[str, str, str], None]] = None
    
    # Logger instance
    logger: Optional[logging.Logger] = None
    
    # Temporary files/directories to clean up
    temp_paths: List[str] = field(default_factory=list)
    
    @property
    def base_name(self) -> str:
        """Standard base name for output files: 'Artist - Title'"""
        return f"{self.artist} - {self.title}"
    
    @property
    def output_path(self) -> Path:
        """Output directory as Path object."""
        return Path(self.output_dir)
    
    @property
    def input_path(self) -> Path:
        """Input audio path as Path object."""
        return Path(self.input_audio_path)
    
    def get_stage_output(self, stage: str, key: str, default: Any = None) -> Any:
        """
        Get a specific output from a stage.
        
        Args:
            stage: Stage name
            key: Output key within that stage
            default: Default value if not found
            
        Returns:
            The output value, or default if not found
        """
        stage_data = self.stage_outputs.get(stage, {})
        if isinstance(stage_data, dict):
            return stage_data.get(key, default)
        return default
    
    def set_stage_output(self, stage: str, outputs: Dict[str, Any]) -> None:
        """
        Set outputs for a stage.
        
        Args:
            stage: Stage name
            outputs: Dictionary of outputs to store
        """
        if stage not in self.stage_outputs:
            self.stage_outputs[stage] = {}
        
        if isinstance(self.stage_outputs[stage], dict):
            self.stage_outputs[stage].update(outputs)
        else:
            self.stage_outputs[stage] = outputs
    
    def update_progress(self, stage: str, percent: int, message: str = "") -> None:
        """
        Update progress and notify callback if set.
        
        Args:
            stage: Current stage name
            percent: Progress percentage (0-100)
            message: Optional progress message
        """
        self.current_stage = stage
        self.progress_percent = percent
        
        if self.on_progress:
            self.on_progress(stage, percent, message)
    
    def log(self, level: str, message: str) -> None:
        """
        Log a message using the configured logger or callback.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR)
            message: Message to log
        """
        if self.logger:
            log_method = getattr(self.logger, level.lower(), self.logger.info)
            log_method(f"[{self.current_stage or 'pipeline'}] {message}")
        
        if self.on_log:
            self.on_log(self.current_stage or "pipeline", level, message)
    
    def add_temp_path(self, path: str) -> None:
        """
        Register a temporary path for cleanup.
        
        Args:
            path: Path to temporary file or directory
        """
        self.temp_paths.append(path)
    
    def cleanup_temp_paths(self) -> None:
        """Remove all registered temporary paths."""
        import shutil
        import os
        
        for path in self.temp_paths:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                elif os.path.isfile(path):
                    os.remove(path)
            except Exception:
                pass  # Best effort cleanup
        
        self.temp_paths.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert context to a dictionary for serialization.
        
        Excludes non-serializable fields (callbacks, logger).
        """
        return {
            "job_id": self.job_id,
            "artist": self.artist,
            "title": self.title,
            "input_audio_path": self.input_audio_path,
            "output_dir": self.output_dir,
            "style_params": self.style_params,
            "enable_cdg": self.enable_cdg,
            "enable_txt": self.enable_txt,
            "brand_prefix": self.brand_prefix,
            "enable_youtube_upload": self.enable_youtube_upload,
            "discord_webhook_url": self.discord_webhook_url,
            "dropbox_path": self.dropbox_path,
            "gdrive_folder_id": self.gdrive_folder_id,
            "organised_dir_rclone_root": self.organised_dir_rclone_root,
            "rclone_destination": self.rclone_destination,
            "stage_outputs": self.stage_outputs,
            "current_stage": self.current_stage,
            "progress_percent": self.progress_percent,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineContext":
        """
        Create a context from a dictionary.
        
        Args:
            data: Dictionary with context fields
            
        Returns:
            New PipelineContext instance
        """
        return cls(
            job_id=data.get("job_id", ""),
            artist=data.get("artist", ""),
            title=data.get("title", ""),
            input_audio_path=data.get("input_audio_path", ""),
            output_dir=data.get("output_dir", ""),
            style_params=data.get("style_params", {}),
            enable_cdg=data.get("enable_cdg", True),
            enable_txt=data.get("enable_txt", True),
            brand_prefix=data.get("brand_prefix"),
            enable_youtube_upload=data.get("enable_youtube_upload", False),
            discord_webhook_url=data.get("discord_webhook_url"),
            dropbox_path=data.get("dropbox_path"),
            gdrive_folder_id=data.get("gdrive_folder_id"),
            organised_dir_rclone_root=data.get("organised_dir_rclone_root"),
            rclone_destination=data.get("rclone_destination"),
            stage_outputs=data.get("stage_outputs", {}),
            current_stage=data.get("current_stage"),
            progress_percent=data.get("progress_percent", 0),
        )
