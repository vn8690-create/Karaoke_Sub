"""
YouTube credential service for server-side video uploads.

This service manages YouTube OAuth credentials stored in Secret Manager
for non-interactive uploads from backend workers.
"""
import json
import logging
from typing import Optional, Dict, Any

from backend.config import get_settings

logger = logging.getLogger(__name__)


class YouTubeService:
    """Service for managing YouTube OAuth credentials."""
    
    # Secret Manager secret name for YouTube credentials
    YOUTUBE_CREDENTIALS_SECRET = "youtube-oauth-credentials"
    
    def __init__(self):
        self.settings = get_settings()
        self._credentials: Optional[Dict[str, Any]] = None
        self._loaded = False
    
    def load_credentials(self) -> bool:
        """
        Load YouTube OAuth credentials from Secret Manager.
        
        The secret should contain a JSON object with:
        - token: Current access token (may be expired)
        - refresh_token: Refresh token for getting new access tokens
        - token_uri: Token endpoint URL
        - client_id: OAuth client ID
        - client_secret: OAuth client secret
        - scopes: List of OAuth scopes
        
        Returns:
            True if credentials were loaded successfully, False otherwise
        """
        if self._loaded:
            return self._credentials is not None
        
        try:
            # Get credentials from Secret Manager
            creds_json = self.settings.get_secret(self.YOUTUBE_CREDENTIALS_SECRET)
            
            if not creds_json:
                logger.warning("YouTube credentials not found in Secret Manager")
                self._loaded = True
                return False
            
            # Parse the credentials JSON
            self._credentials = json.loads(creds_json)
            
            # Validate required fields
            required_fields = ['refresh_token', 'token_uri', 'client_id', 'client_secret']
            missing = [f for f in required_fields if not self._credentials.get(f)]
            
            if missing:
                logger.error(f"YouTube credentials missing required fields: {missing}")
                self._credentials = None
                self._loaded = True
                return False
            
            logger.info("YouTube credentials loaded successfully from Secret Manager")
            self._loaded = True
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse YouTube credentials JSON: {e}")
            self._loaded = True
            return False
        except Exception as e:
            logger.error(f"Failed to load YouTube credentials: {e}")
            self._loaded = True
            return False
    
    def get_credentials_dict(self) -> Optional[Dict[str, Any]]:
        """
        Get the YouTube credentials as a dictionary.
        
        This format is compatible with KaraokeFinalise's user_youtube_credentials
        parameter, which creates a google.oauth2.credentials.Credentials object.
        
        Returns:
            Dictionary with credential data, or None if not available
        """
        if not self._loaded:
            self.load_credentials()
        
        return self._credentials
    
    @property
    def is_configured(self) -> bool:
        """Check if YouTube credentials are configured and ready to use."""
        if not self._loaded:
            self.load_credentials()
        return self._credentials is not None


# Singleton instance
_youtube_service: Optional[YouTubeService] = None


def get_youtube_service() -> YouTubeService:
    """Get the singleton YouTube service instance."""
    global _youtube_service
    if _youtube_service is None:
        _youtube_service = YouTubeService()
    return _youtube_service
