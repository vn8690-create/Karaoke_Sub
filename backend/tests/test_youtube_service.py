"""
Tests for youtube_service.py - YouTube credential management.

These tests mock Secret Manager to verify:
- Credential loading and parsing
- Validation of required fields
- Error handling for missing/invalid credentials
"""
import json
import pytest
from unittest.mock import Mock, patch


class TestYouTubeServiceInit:
    """Test YouTubeService initialization."""
    
    @patch("backend.services.youtube_service.get_settings")
    def test_init_creates_service(self, mock_get_settings):
        """Test initialization creates service with settings."""
        from backend.services.youtube_service import YouTubeService
        
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings
        
        service = YouTubeService()
        
        assert service.settings == mock_settings
        assert service._credentials is None
        assert service._loaded is False


class TestLoadCredentials:
    """Test load_credentials method."""
    
    @patch("backend.services.youtube_service.get_settings")
    def test_load_credentials_success(self, mock_get_settings):
        """Test successful credential loading from Secret Manager."""
        from backend.services.youtube_service import YouTubeService
        
        mock_settings = Mock()
        mock_settings.get_secret.return_value = json.dumps({
            "token": "access-token-123",
            "refresh_token": "refresh-token-456",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client-id.apps.googleusercontent.com",
            "client_secret": "client-secret-789",
            "scopes": ["https://www.googleapis.com/auth/youtube.upload"],
        })
        mock_get_settings.return_value = mock_settings
        
        service = YouTubeService()
        result = service.load_credentials()
        
        assert result is True
        assert service._credentials is not None
        assert service._credentials["refresh_token"] == "refresh-token-456"
        mock_settings.get_secret.assert_called_once_with("youtube-oauth-credentials")
    
    @patch("backend.services.youtube_service.get_settings")
    def test_load_credentials_not_found(self, mock_get_settings):
        """Test handling when credentials are not in Secret Manager."""
        from backend.services.youtube_service import YouTubeService
        
        mock_settings = Mock()
        mock_settings.get_secret.return_value = None
        mock_get_settings.return_value = mock_settings
        
        service = YouTubeService()
        result = service.load_credentials()
        
        assert result is False
        assert service._credentials is None
        assert service._loaded is True
    
    @patch("backend.services.youtube_service.get_settings")
    def test_load_credentials_missing_required_fields(self, mock_get_settings):
        """Test handling when credentials are missing required fields."""
        from backend.services.youtube_service import YouTubeService
        
        mock_settings = Mock()
        mock_settings.get_secret.return_value = json.dumps({
            "token": "access-token",
            # Missing: refresh_token, token_uri, client_id, client_secret
        })
        mock_get_settings.return_value = mock_settings
        
        service = YouTubeService()
        result = service.load_credentials()
        
        assert result is False
        assert service._credentials is None
    
    @patch("backend.services.youtube_service.get_settings")
    def test_load_credentials_invalid_json(self, mock_get_settings):
        """Test handling of invalid JSON in credentials."""
        from backend.services.youtube_service import YouTubeService
        
        mock_settings = Mock()
        mock_settings.get_secret.return_value = "not valid json {"
        mock_get_settings.return_value = mock_settings
        
        service = YouTubeService()
        result = service.load_credentials()
        
        assert result is False
        assert service._credentials is None
    
    @patch("backend.services.youtube_service.get_settings")
    def test_load_credentials_exception(self, mock_get_settings):
        """Test handling of exceptions during credential loading."""
        from backend.services.youtube_service import YouTubeService
        
        mock_settings = Mock()
        mock_settings.get_secret.side_effect = Exception("Secret Manager error")
        mock_get_settings.return_value = mock_settings
        
        service = YouTubeService()
        result = service.load_credentials()
        
        assert result is False
        assert service._loaded is True
    
    @patch("backend.services.youtube_service.get_settings")
    def test_load_credentials_cached(self, mock_get_settings):
        """Test that credentials are cached after first load."""
        from backend.services.youtube_service import YouTubeService
        
        mock_settings = Mock()
        mock_settings.get_secret.return_value = json.dumps({
            "refresh_token": "token",
            "token_uri": "uri",
            "client_id": "id",
            "client_secret": "secret",
        })
        mock_get_settings.return_value = mock_settings
        
        service = YouTubeService()
        
        # First call
        result1 = service.load_credentials()
        # Second call
        result2 = service.load_credentials()
        
        assert result1 is True
        assert result2 is True
        # Secret Manager should only be called once
        assert mock_settings.get_secret.call_count == 1


class TestGetCredentialsDict:
    """Test get_credentials_dict method."""
    
    @patch("backend.services.youtube_service.get_settings")
    def test_get_credentials_dict_loads_if_needed(self, mock_get_settings):
        """Test get_credentials_dict loads credentials if not already loaded."""
        from backend.services.youtube_service import YouTubeService
        
        mock_settings = Mock()
        mock_settings.get_secret.return_value = json.dumps({
            "refresh_token": "token",
            "token_uri": "uri",
            "client_id": "id",
            "client_secret": "secret",
        })
        mock_get_settings.return_value = mock_settings
        
        service = YouTubeService()
        
        # Don't explicitly call load_credentials
        result = service.get_credentials_dict()
        
        assert result is not None
        assert result["refresh_token"] == "token"
    
    @patch("backend.services.youtube_service.get_settings")
    def test_get_credentials_dict_returns_none_if_not_configured(
        self, mock_get_settings
    ):
        """Test get_credentials_dict returns None when not configured."""
        from backend.services.youtube_service import YouTubeService
        
        mock_settings = Mock()
        mock_settings.get_secret.return_value = None
        mock_get_settings.return_value = mock_settings
        
        service = YouTubeService()
        result = service.get_credentials_dict()
        
        assert result is None


class TestIsConfigured:
    """Test is_configured property."""
    
    @patch("backend.services.youtube_service.get_settings")
    def test_is_configured_true(self, mock_get_settings):
        """Test is_configured returns True when credentials exist."""
        from backend.services.youtube_service import YouTubeService
        
        mock_settings = Mock()
        mock_settings.get_secret.return_value = json.dumps({
            "refresh_token": "token",
            "token_uri": "uri",
            "client_id": "id",
            "client_secret": "secret",
        })
        mock_get_settings.return_value = mock_settings
        
        service = YouTubeService()
        
        assert service.is_configured is True
    
    @patch("backend.services.youtube_service.get_settings")
    def test_is_configured_false(self, mock_get_settings):
        """Test is_configured returns False when credentials missing."""
        from backend.services.youtube_service import YouTubeService
        
        mock_settings = Mock()
        mock_settings.get_secret.return_value = None
        mock_get_settings.return_value = mock_settings
        
        service = YouTubeService()
        
        assert service.is_configured is False


class TestGetYouTubeService:
    """Test get_youtube_service singleton."""
    
    @patch("backend.services.youtube_service.get_settings")
    def test_get_youtube_service_singleton(self, mock_get_settings):
        """Test get_youtube_service returns singleton instance."""
        from backend.services.youtube_service import get_youtube_service
        import backend.services.youtube_service as youtube_module
        
        # Reset singleton
        youtube_module._youtube_service = None
        
        mock_settings = Mock()
        mock_settings.get_secret.return_value = None
        mock_get_settings.return_value = mock_settings
        
        service1 = get_youtube_service()
        service2 = get_youtube_service()
        
        assert service1 is service2

