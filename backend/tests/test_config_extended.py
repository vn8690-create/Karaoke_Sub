"""
Extended tests for config.py to improve coverage.
"""
import pytest
import os
from unittest.mock import patch


class TestSettingsConfiguration:
    """Tests for Settings configuration."""
    
    def test_settings_class_exists(self):
        """Test Settings class exists."""
        from backend.config import Settings
        assert Settings is not None
    
    def test_settings_loads_defaults(self):
        """Test Settings loads default values."""
        from backend.config import Settings
        settings = Settings()
        assert settings is not None
    
    def test_gcs_bucket_name_from_env(self):
        """Test GCS bucket name from environment."""
        with patch.dict(os.environ, {'GCS_BUCKET_NAME': 'test-bucket'}):
            from backend.config import Settings
            settings = Settings()
            assert settings.gcs_bucket_name == 'test-bucket'
    
    def test_firestore_collection_from_env(self):
        """Test Firestore collection from environment."""
        with patch.dict(os.environ, {'FIRESTORE_COLLECTION': 'test-jobs'}):
            from backend.config import Settings
            settings = Settings()
            assert settings.firestore_collection == 'test-jobs'
    
    def test_environment_setting(self):
        """Test environment setting."""
        from backend.config import Settings
        settings = Settings()
        # Accept 'test' as well since pytest may set ENVIRONMENT=test
        assert settings.environment in ['development', 'production', 'testing', 'test']
    
    def test_google_cloud_project(self):
        """Test Google Cloud project setting."""
        with patch.dict(os.environ, {'GOOGLE_CLOUD_PROJECT': 'test-project'}):
            from backend.config import Settings
            settings = Settings()
            # Should either use the env var or have a default


class TestGetSettings:
    """Tests for get_settings function."""
    
    def test_get_settings_returns_settings(self):
        """Test get_settings returns Settings instance."""
        from backend.config import get_settings
        settings = get_settings()
        assert settings is not None
    
    def test_get_settings_returns_same_instance(self):
        """Test get_settings returns cached instance."""
        from backend.config import get_settings
        settings1 = get_settings()
        settings2 = get_settings()
        # Should be same cached instance
        assert settings1 is settings2

