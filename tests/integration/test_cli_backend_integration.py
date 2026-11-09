"""
CLI + Backend Integration Tests

These tests run the ACTUAL CLI code against a LOCAL backend with emulators.
This catches bugs like content-type mismatches that unit tests with mocks miss.

Run with:
    ./scripts/run-cli-integration-tests.sh

Prerequisites:
    - GCS emulator running (fake-gcs-server)
    - Firestore emulator running  
    - Backend running locally against emulators
"""
import os
import sys
import json
import pytest
import tempfile
import requests
from pathlib import Path
from unittest.mock import patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def emulators_and_backend_running() -> bool:
    """Check if emulators and local backend are running."""
    try:
        # Check GCS emulator
        gcs_response = requests.get("http://localhost:4443/storage/v1/b", timeout=2)
        if gcs_response.status_code != 200:
            return False
        
        # Check Firestore emulator
        firestore_response = requests.get("http://localhost:8080", timeout=2)
        
        # Check local backend
        backend_response = requests.get("http://localhost:8000/api/health", timeout=2)
        if backend_response.status_code != 200:
            return False
        
        return True
    except requests.exceptions.RequestException:
        return False


# Skip all tests if infrastructure isn't running
pytestmark = pytest.mark.skipif(
    not emulators_and_backend_running(),
    reason="Emulators and local backend not running. Run: ./scripts/start-local-test-env.sh"
)


@pytest.fixture
def test_style_files(tmp_path):
    """Create test style files for upload testing."""
    # Create a minimal style params JSON
    style_params = {
        "intro": {
            "background_color": "#000000",
            "background_image": str(tmp_path / "intro_bg.png"),
            "font": str(tmp_path / "test_font.ttf"),
            "title_color": "#ffffff",
            "artist_color": "#ffdf6b"
        },
        "karaoke": {
            "background_color": "#000000",
            "background_image": str(tmp_path / "karaoke_bg.png"),
            "font_path": str(tmp_path / "test_font.ttf"),
            "primary_color": "112, 112, 247, 255",
            "secondary_color": "255, 255, 255, 255"
        },
        "cdg": {
            "background_color": "#000000",
            "instrumental_background": str(tmp_path / "cdg_inst_bg.png"),
            "title_screen_background": str(tmp_path / "cdg_title_bg.png"),
            "font_path": str(tmp_path / "test_font.ttf")
        }
    }
    
    style_params_path = tmp_path / "styles.json"
    with open(style_params_path, 'w') as f:
        json.dump(style_params, f)
    
    # Create minimal test image (1x1 pixel PNG)
    # PNG header + minimal IHDR + IDAT + IEND
    minimal_png = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
        0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
        0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
        0x44, 0xAE, 0x42, 0x60, 0x82
    ])
    
    # Create test images
    for name in ["intro_bg.png", "karaoke_bg.png", "cdg_inst_bg.png", "cdg_title_bg.png"]:
        (tmp_path / name).write_bytes(minimal_png)
    
    # Create minimal TTF font (just header)
    minimal_ttf = bytes([0x00, 0x01, 0x00, 0x00] + [0x00] * 100)
    (tmp_path / "test_font.ttf").write_bytes(minimal_ttf)
    
    return {
        'style_params_path': str(style_params_path),
        'tmp_path': tmp_path
    }


@pytest.fixture
def cli_config():
    """Configuration for CLI to connect to local backend."""
    return {
        'service_url': 'http://localhost:8000',
        'auth_token': 'test-admin-token',
    }


class TestSignedUrlUploadRoundTrip:
    """
    Test the full signed URL upload flow:
    1. CLI requests signed URLs from backend
    2. CLI uploads files directly to GCS using signed URLs
    3. Backend can read the uploaded files
    
    This is the flow that broke with the content-type mismatch bug.
    """
    
    def test_style_params_json_upload(self, test_style_files, cli_config):
        """Test uploading style_params.json via signed URL."""
        from karaoke_gen.utils.remote_cli import RemoteKaraokeClient, RemoteConfig
        import logging
        
        logger = logging.getLogger("test")
        config = RemoteConfig(
            service_url=cli_config['service_url'],
            auth_token=cli_config['auth_token'],
            environment='test'
        )
        client = RemoteKaraokeClient(config, logger)
        
        # This should:
        # 1. Send request with style_files metadata
        # 2. Get back signed URLs
        # 3. Upload files to those URLs
        # 4. Return job info
        try:
            result = client.search_audio(
                artist="Test Artist",
                title="Test Song",
                style_params_path=test_style_files['style_params_path'],
                auto_download=False
            )
            
            # If we get here without 403, the upload worked!
            assert 'job_id' in result
            
        except Exception as e:
            # Check if it's a content-type mismatch (403)
            if '403' in str(e):
                pytest.fail(f"Signed URL upload failed with 403 - likely content-type mismatch: {e}")
            raise
    
    def test_image_file_upload(self, test_style_files, cli_config):
        """Test uploading PNG image via signed URL."""
        from karaoke_gen.utils.remote_cli import RemoteKaraokeClient, RemoteConfig
        import logging
        
        logger = logging.getLogger("test")
        config = RemoteConfig(
            service_url=cli_config['service_url'],
            auth_token=cli_config['auth_token'],
            environment='test'
        )
        client = RemoteKaraokeClient(config, logger)
        
        try:
            result = client.search_audio(
                artist="Test Artist",
                title="Test Song",
                style_params_path=test_style_files['style_params_path'],
                auto_download=False
            )
            
            # Verify job was created
            assert 'job_id' in result
            
            # Verify style assets were recorded
            job_id = result['job_id']
            job_response = requests.get(
                f"{cli_config['service_url']}/api/jobs/{job_id}",
                headers={'Authorization': f"Bearer {cli_config['auth_token']}"}
            )
            assert job_response.status_code == 200
            job = job_response.json()
            
            # Check style assets exist
            assert 'style_assets' in job or job.get('style_params_gcs_path')
            
        except Exception as e:
            if '403' in str(e):
                pytest.fail(f"Image upload failed with 403 - content-type mismatch: {e}")
            raise
    
    def test_font_file_upload(self, test_style_files, cli_config):
        """Test uploading TTF font via signed URL."""
        from karaoke_gen.utils.remote_cli import RemoteKaraokeClient, RemoteConfig
        import logging
        
        logger = logging.getLogger("test")
        config = RemoteConfig(
            service_url=cli_config['service_url'],
            auth_token=cli_config['auth_token'],
            environment='test'
        )
        client = RemoteKaraokeClient(config, logger)
        
        try:
            result = client.search_audio(
                artist="Test Artist",
                title="Test Song",
                style_params_path=test_style_files['style_params_path'],
                auto_download=False
            )
            assert 'job_id' in result
            
        except Exception as e:
            if '403' in str(e):
                pytest.fail(f"Font upload failed with 403 - content-type mismatch: {e}")
            raise


class TestContentTypeMatching:
    """
    Direct tests for content-type handling.
    These catch the specific bug we found.
    """
    
    def test_get_content_type_with_full_path(self):
        """Test _get_content_type works with full paths."""
        from karaoke_gen.utils.remote_cli import RemoteKaraokeClient, RemoteConfig
        import logging
        
        logger = logging.getLogger("test")
        config = RemoteConfig(
            service_url='http://localhost:8000',
            auth_token='test',
            environment='test'
        )
        client = RemoteKaraokeClient(config, logger)
        
        # Test various file paths
        assert client._get_content_type('/path/to/file.json') == 'application/json'
        assert client._get_content_type('/path/to/file.png') == 'image/png'
        assert client._get_content_type('/path/to/file.ttf') == 'font/ttf'
        assert client._get_content_type('/path/to/file.flac') == 'audio/flac'
    
    def test_get_content_type_with_extension_only_bug(self):
        """
        Test that passing just an extension doesn't work.
        This documents the bug we found.
        """
        from pathlib import Path
        
        # This is the bug: Path('.json').suffix returns empty string!
        assert Path('.json').suffix == ''
        assert Path('.png').suffix == ''
        
        # But full paths work correctly
        assert Path('/path/to/file.json').suffix == '.json'
        assert Path('/path/to/file.png').suffix == '.png'


class TestAudioSearchWithStyles:
    """Test audio search endpoint with style file handling."""
    
    def test_audio_search_returns_style_upload_urls(self, cli_config, tmp_path):
        """Test that audio search returns signed URLs for style files."""
        # Create minimal style params
        style_params = {"karaoke": {"background_color": "#000000"}}
        style_path = tmp_path / "styles.json"
        with open(style_path, 'w') as f:
            json.dump(style_params, f)
        
        # Make direct API call to check response format
        response = requests.post(
            f"{cli_config['service_url']}/api/audio-search/search",
            headers={'Authorization': f"Bearer {cli_config['auth_token']}"},
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'style_files': [
                    {
                        'filename': 'styles.json',
                        'content_type': 'application/json',
                        'file_type': 'style_params'
                    }
                ]
            }
        )
        
        # Should get 200 or 404 (no results), not 500
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            # If style files were provided, should get upload URLs back
            if 'style_upload_urls' in data:
                assert len(data['style_upload_urls']) > 0
                for url_info in data['style_upload_urls']:
                    assert 'upload_url' in url_info
                    assert 'file_type' in url_info

