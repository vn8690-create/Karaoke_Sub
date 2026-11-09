"""
Rclone configuration service for cloud storage integration.

This service manages the rclone configuration needed for Dropbox
and other cloud storage uploads from the backend workers.
"""
import logging
import os
import tempfile
from typing import Optional

from backend.config import get_settings

logger = logging.getLogger(__name__)


class RcloneService:
    """Service for managing rclone configuration."""
    
    # Secret Manager secret name for rclone config
    RCLONE_CONFIG_SECRET = "rclone-config"
    
    def __init__(self):
        self.settings = get_settings()
        self._config_file: Optional[str] = None
        self._config_loaded = False
    
    def setup_rclone_config(self) -> bool:
        """
        Load rclone config from Secret Manager and set up environment.
        
        Writes the config to a temp file and sets RCLONE_CONFIG env var.
        
        Returns:
            True if successful, False otherwise
        """
        if self._config_loaded:
            logger.debug("Rclone config already loaded")
            return True
        
        try:
            # Get rclone config from Secret Manager
            config_content = self.settings.get_secret(self.RCLONE_CONFIG_SECRET)
            
            if not config_content:
                logger.warning("Rclone config not found in Secret Manager")
                return False
            
            # Write to a temp file
            fd, config_path = tempfile.mkstemp(prefix="rclone_", suffix=".conf")
            try:
                with os.fdopen(fd, 'w') as f:
                    f.write(config_content)
                
                self._config_file = config_path
                
                # Set environment variable for rclone to find the config
                os.environ["RCLONE_CONFIG"] = config_path
                
                logger.info(f"Rclone config loaded and written to {config_path}")
                self._config_loaded = True
                return True
                
            except Exception:
                # Clean up the temp file on error
                # Note: os.fdopen() takes ownership of fd, so it's already closed
                # We only need to remove the temp file if it exists
                if os.path.exists(config_path):
                    os.unlink(config_path)
                raise
                
        except Exception as e:
            logger.error(f"Failed to setup rclone config: {e}")
            return False
    
    def cleanup(self) -> None:
        """Remove the temporary config file."""
        if self._config_file and os.path.exists(self._config_file):
            try:
                os.unlink(self._config_file)
                logger.debug(f"Cleaned up rclone config file: {self._config_file}")
            except Exception as e:
                logger.warning(f"Failed to cleanup rclone config: {e}")
        
        # Always reset internal state and environment, even if the file was missing
        if self._config_file is not None:
            os.environ.pop("RCLONE_CONFIG", None)
        self._config_file = None
        self._config_loaded = False
    
    @property
    def is_configured(self) -> bool:
        """Check if rclone is configured and ready to use."""
        return self._config_loaded and self._config_file is not None


# Singleton instance
_rclone_service: Optional[RcloneService] = None


def get_rclone_service() -> RcloneService:
    """Get the singleton rclone service instance."""
    global _rclone_service
    if _rclone_service is None:
        _rclone_service = RcloneService()
    return _rclone_service
