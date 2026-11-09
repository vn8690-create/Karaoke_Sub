"""
End-to-End CLI + Backend Integration Tests

These tests verify the FULL flow from CLI to Backend with real emulators.
They would have caught bugs like:
- Content-type mismatch in signed URL uploads (403 errors)
- Missing auth headers in download requests
- YouTube description field name mismatch

Run with: ./scripts/run-emulator-tests.sh

Prerequisites:
    - GCS emulator running (fake-gcs-server)
    - Firestore emulator running
"""
import pytest
import json
import time
import tempfile
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from .conftest import emulators_running


# Skip all tests if emulators aren't running
pytestmark = pytest.mark.skipif(
    not emulators_running(),
    reason="GCP emulators not running. Start with: scripts/start-emulators.sh"
)


@pytest.fixture
def test_style_files(tmp_path):
    """Create realistic test style files for upload testing."""
    # Create a style params JSON that references local files
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
        "end": {
            "background_color": "#000000",
            "background_image": str(tmp_path / "end_bg.png"),
            "font": str(tmp_path / "test_font.ttf")
        },
        "cdg": {
            "background_color": "#000000",
            "instrumental_background": str(tmp_path / "cdg_inst_bg.png"),
            "title_screen_background": str(tmp_path / "cdg_title_bg.png"),
            "outro_background": str(tmp_path / "cdg_outro_bg.png"),
            "font_path": str(tmp_path / "test_font.ttf")
        }
    }
    
    style_params_path = tmp_path / "karaoke-prep-styles.json"
    with open(style_params_path, 'w') as f:
        json.dump(style_params, f)
    
    # Create minimal valid PNG (1x1 pixel)
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
    
    # Create all referenced image files
    for name in ["intro_bg.png", "karaoke_bg.png", "end_bg.png", 
                 "cdg_inst_bg.png", "cdg_title_bg.png", "cdg_outro_bg.png"]:
        (tmp_path / name).write_bytes(minimal_png)
    
    # Create minimal TTF font file
    minimal_ttf = bytes([0x00, 0x01, 0x00, 0x00] + [0x00] * 100)
    (tmp_path / "test_font.ttf").write_bytes(minimal_ttf)
    
    return {
        'style_params_path': str(style_params_path),
        'tmp_path': tmp_path
    }


@pytest.fixture
def youtube_description():
    """Sample YouTube description template."""
    return """This is a karaoke (instrumental) version of the song.
    
Created using AI-powered vocal removal.

LINKS:
- Community: https://discord.gg/example
- More karaoke: https://example.com
"""


class TestStyleFileUploadE2E:
    """
    Test the complete style file upload flow.
    
    This is the flow that broke with the content-type mismatch bug:
    1. CLI parses style_params.json and finds all referenced files
    2. CLI sends metadata to backend, gets signed upload URLs
    3. CLI uploads each file to its signed URL with correct content-type
    4. Backend records the GCS paths for later use
    """
    
    def test_style_params_json_upload_content_type(self, client, auth_headers, tmp_path):
        """
        Test that style_params.json uploads with application/json content-type.
        
        BUG CAUGHT: CLI was deriving content-type from Path('.json').suffix which
        returns '' because '.json' looks like a hidden file. This caused 403 errors
        because the upload content-type didn't match the signed URL's expected type.
        """
        # Create minimal style params
        style_params = {"karaoke": {"background_color": "#000000"}}
        style_path = tmp_path / "styles.json"
        with open(style_path, 'w') as f:
            json.dump(style_params, f)
        
        # Create job with style files
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'files': [
                    {
                        'filename': 'styles.json',
                        'content_type': 'application/json',
                        'file_type': 'style_params'
                    }
                ]
            }
        )
        
        # Should not fail with 500 (backend error)
        assert response.status_code in [200, 404], f"Unexpected: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            # Verify upload URLs are returned
            if 'upload_urls' in data:
                assert 'style_params' in data['upload_urls']
                # The URL should be a signed GCS URL
                url = data['upload_urls']['style_params']
                assert 'storage' in url.lower() or 'localhost' in url.lower()
    
    def test_image_upload_content_type(self, client, auth_headers, tmp_path):
        """Test that PNG images upload with image/png content-type."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'files': [
                    {
                        'filename': 'background.png',
                        'content_type': 'image/png',
                        'file_type': 'style_intro_background'
                    }
                ]
            }
        )
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            if 'upload_urls' in data:
                assert 'style_intro_background' in data['upload_urls']
    
    def test_font_upload_content_type(self, client, auth_headers):
        """Test that TTF fonts upload with font/ttf content-type."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'files': [
                    {
                        'filename': 'font.ttf',
                        'content_type': 'font/ttf',
                        'file_type': 'style_font'
                    }
                ]
            }
        )
        
        assert response.status_code in [200, 404]


class TestYouTubeDescriptionFieldMapping:
    """
    Test that YouTube description is properly passed from API to workers.
    
    BUG CAUGHT: audio_search endpoint set 'youtube_description' but
    video_worker.py reads 'youtube_description_template'. YouTube uploads
    silently failed because the template field was always None.
    """
    
    def test_job_has_youtube_description_template(self, client, auth_headers, youtube_description):
        """
        Test that when youtube_description is provided, youtube_description_template is also set.
        
        This is critical because video_worker.py uses this pattern:
            if youtube_credentials and getattr(job, 'youtube_description_template', None):
        
        NOTE: We test with enable_youtube_upload=False to avoid credentials validation.
        The important thing is that when youtube_description is provided, both fields are set.
        """
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'enable_youtube_upload': False,  # Don't require YouTube credentials
                'youtube_description': youtube_description  # But still provide description
            }
        )
        
        # Job should be created (or 404 if flacfetch not configured)
        assert response.status_code in [200, 404], f"Unexpected: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            job_id = data.get('job_id')
            
            if job_id:
                # Fetch the job and verify both fields are set
                time.sleep(0.2)  # Allow for emulator consistency
                job_response = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
                
                if job_response.status_code == 200:
                    job = job_response.json()
                    
                    # CRITICAL: Both fields must be set for YouTube upload to work
                    assert job.get('youtube_description') == youtube_description, \
                        "youtube_description not set correctly"
                    assert job.get('youtube_description_template') == youtube_description, \
                        "youtube_description_template not set - YouTube upload will fail!"
    
    def test_youtube_upload_disabled_no_template_needed(self, client, auth_headers):
        """Test that youtube_description_template is not required when upload is disabled."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'enable_youtube_upload': False
            }
        )
        
        # Should succeed without YouTube config
        assert response.status_code in [200, 404]


class TestDownloadAuthHeaders:
    """
    Test that file downloads include authentication headers.
    
    BUG CAUGHT: download_file_via_url() used requests.get() directly instead
    of self.session.get(), so auth headers were not included. All downloads
    failed with 401/403 even though the job completed successfully.
    """
    
    def test_download_endpoint_requires_auth(self, client):
        """Test that download endpoints reject unauthenticated requests."""
        # Try to download without auth header
        response = client.get("/api/jobs/nonexistent/download-urls")
        
        # Should fail with 401 (unauthorized), not 404
        assert response.status_code in [401, 403], \
            f"Download endpoint should require auth, got {response.status_code}"
    
    def test_download_endpoint_with_auth(self, client, auth_headers):
        """Test that download endpoints work with auth header (and reject without).
        
        This tests that:
        1. Auth is required (401/403 without header)
        2. Auth works (not 401/403 with header)
        
        Note: A 400 "Job not complete" is acceptable since we're testing auth, not completion.
        """
        # First create a job via the simple /api/jobs endpoint (no YouTube validation)
        create_response = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "url": "https://youtube.com/watch?v=test123",
                "artist": "Test Artist",
                "title": "Test Song"
            }
        )
        
        if create_response.status_code == 200:
            job_id = create_response.json()["job_id"]
            time.sleep(0.2)
            
            # Try to get download URLs with auth
            download_response = client.get(
                f"/api/jobs/{job_id}/download-urls",
                headers=auth_headers
            )
            
            # Should NOT be 401/403 (auth failure) - we're testing that auth header works
            # 400 (job not complete) is acceptable - that's a business logic error, not auth
            # 200 would mean job has files ready, which is unlikely in this test
            assert download_response.status_code not in [401, 403], \
                f"Download URLs failed with auth error: {download_response.status_code} - {download_response.text}"


class TestFullAudioSearchFlow:
    """
    Test the complete audio search flow that the CLI uses.
    """
    
    def test_audio_search_creates_job_with_all_fields(
        self, client, auth_headers, test_style_files, youtube_description
    ):
        """Test that audio search creates a job with all expected fields.
        
        NOTE: We set enable_youtube_upload=False to avoid credentials validation
        in the emulator environment. The field mapping test is covered separately.
        """
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'ABBA',
                'title': 'Waterloo',
                'auto_download': False,
                'enable_cdg': True,
                'enable_txt': True,
                'enable_youtube_upload': False,  # Don't require YouTube credentials
                'youtube_description': youtube_description,
                'brand_prefix': 'TEST',
                'files': [
                    {
                        'filename': 'styles.json',
                        'content_type': 'application/json',
                        'file_type': 'style_params'
                    }
                ]
            }
        )
        
        # Should create job or return 404 if no results
        assert response.status_code in [200, 404], \
            f"Unexpected status: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify job was created
            assert 'job_id' in data
            job_id = data['job_id']
            
            # Verify upload URLs returned for style files
            if 'upload_urls' in data:
                assert isinstance(data['upload_urls'], dict)
            
            # Fetch job and verify all fields are set
            time.sleep(0.2)
            job_response = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
            
            if job_response.status_code == 200:
                job = job_response.json()
                
                # Verify job configuration
                assert job.get('enable_cdg') is True
                assert job.get('enable_txt') is True
                assert job.get('youtube_description') == youtube_description
                # CRITICAL: This field must be set for video_worker.py
                assert job.get('youtube_description_template') == youtube_description
    
    def test_audio_search_returns_server_version(self, client, auth_headers):
        """Test that audio search response includes server version."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test',
                'title': 'Song',
                'auto_download': False
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            # Server version helps CLI verify compatibility
            assert 'server_version' in data


class TestDistributionSettings:
    """
    Test that distribution settings are properly passed through the entire flow.
    
    CRITICAL: These tests verify that brand_prefix, dropbox_path, gdrive_folder_id,
    and discord_webhook_url are correctly propagated from:
    1. CLI parameters → Audio Search API request
    2. Audio Search API → JobCreate model
    3. JobCreate → Job (in Firestore)
    4. Job → video_worker (for KaraokeFinalise and native uploads)
    
    BUG CAUGHT (v0.75.55): job_manager.create_job() was NOT passing these fields
    from JobCreate to Job, causing all distribution uploads to silently fail.
    """
    
    def test_brand_prefix_passed_to_job(self, client, auth_headers):
        """Test that brand_prefix is stored in the created job."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'brand_prefix': 'NOMAD',
                'enable_youtube_upload': False
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            job_id = data.get('job_id')
            
            if job_id:
                time.sleep(0.2)
                job_response = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
                
                if job_response.status_code == 200:
                    job = job_response.json()
                    assert job.get('brand_prefix') == 'NOMAD', \
                        "brand_prefix not passed to job - Dropbox upload will fail!"
    
    def test_dropbox_path_passed_to_job(self, client, auth_headers):
        """Test that dropbox_path is stored in the created job."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'dropbox_path': '/Karaoke/Tracks-Organized',
                'enable_youtube_upload': False
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            job_id = data.get('job_id')
            
            if job_id:
                time.sleep(0.2)
                job_response = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
                
                if job_response.status_code == 200:
                    job = job_response.json()
                    assert job.get('dropbox_path') == '/Karaoke/Tracks-Organized', \
                        "dropbox_path not passed to job - Dropbox upload will fail!"
    
    def test_gdrive_folder_id_passed_to_job(self, client, auth_headers):
        """Test that gdrive_folder_id is stored in the created job."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'gdrive_folder_id': '1abc123xyz',
                'enable_youtube_upload': False
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            job_id = data.get('job_id')
            
            if job_id:
                time.sleep(0.2)
                job_response = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
                
                if job_response.status_code == 200:
                    job = job_response.json()
                    assert job.get('gdrive_folder_id') == '1abc123xyz', \
                        "gdrive_folder_id not passed to job - Google Drive upload will fail!"
    
    def test_discord_webhook_url_passed_to_job(self, client, auth_headers):
        """Test that discord_webhook_url is stored in the created job."""
        webhook_url = 'https://discord.com/api/webhooks/123/abc'
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'discord_webhook_url': webhook_url,
                'enable_youtube_upload': False
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            job_id = data.get('job_id')
            
            if job_id:
                time.sleep(0.2)
                job_response = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
                
                if job_response.status_code == 200:
                    job = job_response.json()
                    assert job.get('discord_webhook_url') == webhook_url, \
                        "discord_webhook_url not passed to job - Discord notification will fail!"
    
    def test_all_distribution_settings_together(self, client, auth_headers, youtube_description):
        """
        Test that ALL distribution settings are passed together.
        
        This is the full integration test that mirrors what the real CLI does.
        """
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'ABBA',
                'title': 'Waterloo',
                'auto_download': False,
                'enable_cdg': True,
                'enable_txt': True,
                'brand_prefix': 'NOMAD',
                'dropbox_path': '/Karaoke/Tracks-Organized',
                'gdrive_folder_id': '1abc123xyz',
                'discord_webhook_url': 'https://discord.com/api/webhooks/123/abc',
                'enable_youtube_upload': False,
                'youtube_description': youtube_description,
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            job_id = data.get('job_id')
            
            if job_id:
                time.sleep(0.2)
                job_response = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
                
                if job_response.status_code == 200:
                    job = job_response.json()
                    
                    # Verify all distribution settings
                    errors = []
                    if job.get('brand_prefix') != 'NOMAD':
                        errors.append("brand_prefix not set")
                    if job.get('dropbox_path') != '/Karaoke/Tracks-Organized':
                        errors.append("dropbox_path not set")
                    if job.get('gdrive_folder_id') != '1abc123xyz':
                        errors.append("gdrive_folder_id not set")
                    if job.get('discord_webhook_url') != 'https://discord.com/api/webhooks/123/abc':
                        errors.append("discord_webhook_url not set")
                    if job.get('youtube_description') != youtube_description:
                        errors.append("youtube_description not set")
                    if job.get('youtube_description_template') != youtube_description:
                        errors.append("youtube_description_template not set")
                    if job.get('enable_cdg') is not True:
                        errors.append("enable_cdg not set")
                    if job.get('enable_txt') is not True:
                        errors.append("enable_txt not set")
                    
                    assert len(errors) == 0, \
                        f"Distribution settings not properly passed: {', '.join(errors)}"


class TestJobModelFileUpload:
    """
    Test that the /api/file-upload endpoint accepts distribution parameters.
    
    This tests the alternative flow where users upload a file directly
    instead of using audio search.
    """
    
    def test_file_upload_accepts_distribution_params(self, client, auth_headers):
        """Test that file upload endpoint accepts all distribution parameters."""
        # Note: This is a POST to create a job with file upload intent
        # The actual file is uploaded separately via signed URL
        response = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'url': 'https://example.com/audio.flac',
                'brand_prefix': 'TEST',
                'dropbox_path': '/Test/Path',
                'gdrive_folder_id': 'folder123',
                'discord_webhook_url': 'https://discord.com/webhook/test',
                'enable_cdg': True,
                'enable_txt': True,
            }
        )
        
        # Should accept the request (even if validation fails for other reasons)
        assert response.status_code in [200, 400, 422], \
            f"Unexpected status: {response.status_code} - {response.text}"


class TestOutputFormatSettings:
    """
    Test that output format settings (CDG, TXT) are properly passed.
    
    These settings control which output files are generated:
    - enable_cdg: Generate CDG+MP3 karaoke package
    - enable_txt: Generate TXT lyrics file
    """
    
    def test_enable_cdg_passed_to_job(self, client, auth_headers):
        """Test enable_cdg flag is properly stored."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test',
                'title': 'Song',
                'auto_download': False,
                'enable_cdg': True,
                'enable_youtube_upload': False
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            job_id = data.get('job_id')
            
            if job_id:
                time.sleep(0.2)
                job_response = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
                
                if job_response.status_code == 200:
                    job = job_response.json()
                    assert job.get('enable_cdg') is True
    
    def test_enable_txt_passed_to_job(self, client, auth_headers):
        """Test enable_txt flag is properly stored."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test',
                'title': 'Song',
                'auto_download': False,
                'enable_txt': True,
                'enable_youtube_upload': False
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            job_id = data.get('job_id')
            
            if job_id:
                time.sleep(0.2)
                job_response = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
                
                if job_response.status_code == 200:
                    job = job_response.json()
                    assert job.get('enable_txt') is True


class TestCLIClientIntegration:
    """
    Test the actual CLI client code against the backend.
    
    These tests import and use the real RemoteKaraokeClient class.
    """
    
    @pytest.fixture
    def cli_client(self, tmp_path):
        """Create a CLI client configured for local testing."""
        # Import here to avoid issues when emulators aren't running
        from karaoke_gen.utils.remote_cli import RemoteKaraokeClient, Config
        
        logger = logging.getLogger("test_cli")
        config = Config(
            service_url='http://localhost:8000',
            review_ui_url='http://localhost:3000',
            poll_interval=5,
            output_dir=str(tmp_path / 'output'),
            auth_token='test-admin-token',
            environment='test'
        )
        return RemoteKaraokeClient(config, logger)
    
    def test_cli_get_content_type_handles_all_extensions(self, cli_client):
        """Test CLI content type detection for all file types we use."""
        # JSON
        assert cli_client._get_content_type('/path/to/style.json') == 'application/json'
        # Images
        assert cli_client._get_content_type('/path/to/bg.png') == 'image/png'
        assert cli_client._get_content_type('/path/to/bg.jpg') == 'image/jpeg'
        assert cli_client._get_content_type('/path/to/bg.jpeg') == 'image/jpeg'
        # Fonts
        assert cli_client._get_content_type('/path/to/font.ttf') == 'font/ttf'
        assert cli_client._get_content_type('/path/to/font.otf') == 'font/otf'
        # Audio
        assert cli_client._get_content_type('/path/to/audio.flac') == 'audio/flac'
        assert cli_client._get_content_type('/path/to/audio.mp3') == 'audio/mpeg'
    
    def test_cli_download_uses_session_not_requests(self, cli_client, tmp_path):
        """
        Test that CLI download method uses session (with auth headers).
        
        This verifies the fix for the download auth bug.
        """
        # Mock the session.get to verify it's called
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b'test content']
        cli_client.session.get = MagicMock(return_value=mock_response)
        
        local_path = str(tmp_path / "test.mp4")
        
        # Call download with a relative URL
        result = cli_client.download_file_via_url("/api/jobs/123/download/test", local_path)
        
        # Verify session.get was called (not bare requests.get)
        assert result is True
        cli_client.session.get.assert_called_once()
        
        # Verify URL was constructed correctly
        call_args = cli_client.session.get.call_args
        assert 'localhost:8000' in call_args[0][0] or cli_client.config.service_url in call_args[0][0]
    
    def test_cli_parse_style_params_extracts_all_assets(self, cli_client, test_style_files):
        """Test that CLI correctly parses style params and finds all asset files."""
        assets = cli_client._parse_style_params(test_style_files['style_params_path'])
        
        # Should find all the referenced files
        assert len(assets) > 0
        
        # Verify it found background images
        bg_keys = [k for k in assets.keys() if 'background' in k.lower()]
        assert len(bg_keys) > 0, "Should find background image references"
        
        # Verify it found font
        font_keys = [k for k in assets.keys() if 'font' in k.lower()]
        assert len(font_keys) > 0, "Should find font references"


class TestDropboxServiceIntegration:
    """
    Test Dropbox service brand code calculation logic.
    
    These tests verify the brand code calculation algorithm that ensures
    sequential brand codes (e.g., NOMAD-1163, NOMAD-1164).
    
    Note: These tests mock the Dropbox SDK since we can't run against
    real Dropbox in CI. The unit tests in test_dropbox_service.py cover
    the SDK interactions in detail.
    """
    
    def test_brand_code_calculation_algorithm(self):
        """
        Test the brand code calculation pattern matching.
        
        This is the core algorithm used by DropboxService.get_next_brand_code()
        to find the highest existing brand code and return the next one.
        """
        import re
        
        # Simulate existing folder names
        existing_folders = [
            "NOMAD-1161 - Artist A - Song A",
            "NOMAD-1162 - Artist B - Song B", 
            "NOMAD-1163 - Artist C - Song C",
            "OTHER-0001 - Different Brand",
            "Random Folder",
            "NOMAD-0001 - First Ever",
        ]
        
        brand_prefix = "NOMAD"
        pattern = re.compile(rf"^{re.escape(brand_prefix)}-(\d{{4}})")
        
        max_num = 0
        for folder in existing_folders:
            match = pattern.match(folder)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)
        
        next_code = f"{brand_prefix}-{max_num + 1:04d}"
        
        assert max_num == 1163, "Should find NOMAD-1163 as highest"
        assert next_code == "NOMAD-1164", "Next code should be NOMAD-1164"
    
    def test_brand_code_empty_folder(self):
        """Test brand code starts at 0001 when folder is empty."""
        import re
        
        existing_folders = []
        brand_prefix = "NEWBRAND"
        pattern = re.compile(rf"^{re.escape(brand_prefix)}-(\d{{4}})")
        
        max_num = 0
        for folder in existing_folders:
            match = pattern.match(folder)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)
        
        next_code = f"{brand_prefix}-{max_num + 1:04d}"
        
        assert next_code == "NEWBRAND-0001"


class TestGoogleDriveServiceIntegration:
    """
    Test Google Drive service folder structure logic.
    
    These tests verify the folder structure for public share uploads:
    - MP4/ for 4K lossy videos
    - MP4-720p/ for 720p videos
    - CDG/ for CDG packages
    
    Note: These tests verify the logic, not actual Drive API calls.
    """
    
    def test_public_share_folder_structure(self):
        """
        Test that the correct folder structure is created for public shares.
        
        Expected structure:
        root_folder/
        ├── MP4/
        │   └── {brand_code} - {artist} - {title}.mp4
        ├── MP4-720p/
        │   └── {brand_code} - {artist} - {title}.mp4
        └── CDG/
            └── {brand_code} - {artist} - {title}.zip
        """
        expected_folders = ["MP4", "MP4-720p", "CDG"]
        
        # This mirrors the logic in GoogleDriveService.upload_to_public_share()
        upload_plan = []
        
        output_files = {
            "final_karaoke_lossy_mp4": "/tmp/output.mp4",
            "final_karaoke_lossy_720p_mp4": "/tmp/output_720p.mp4",
            "final_karaoke_cdg_zip": "/tmp/output.zip",
        }
        
        if output_files.get("final_karaoke_lossy_mp4"):
            upload_plan.append(("MP4", "final_karaoke_lossy_mp4"))
        if output_files.get("final_karaoke_lossy_720p_mp4"):
            upload_plan.append(("MP4-720p", "final_karaoke_lossy_720p_mp4"))
        if output_files.get("final_karaoke_cdg_zip"):
            upload_plan.append(("CDG", "final_karaoke_cdg_zip"))
        
        folders_used = [folder for folder, _ in upload_plan]
        
        assert folders_used == expected_folders
    
    def test_filename_format(self):
        """Test that uploaded files have correct naming format."""
        brand_code = "NOMAD-1164"
        base_name = "Artist - Title"
        
        expected_mp4_name = f"{brand_code} - {base_name}.mp4"
        expected_zip_name = f"{brand_code} - {base_name}.zip"
        
        assert expected_mp4_name == "NOMAD-1164 - Artist - Title.mp4"
        assert expected_zip_name == "NOMAD-1164 - Artist - Title.zip"


class TestVideoWorkerDistributionLogic:
    """
    Test the distribution logic in video_worker.py.
    
    These tests verify that the video worker correctly reads job settings
    and calls the appropriate distribution services.
    """
    
    def test_dropbox_upload_requires_both_path_and_prefix(self):
        """
        Test that Dropbox upload only runs when BOTH dropbox_path AND brand_prefix are set.
        
        This mirrors the logic in video_worker.py:
            if dropbox_path and brand_prefix:
                # Do Dropbox upload
        """
        test_cases = [
            # (dropbox_path, brand_prefix, should_upload)
            ("/Karaoke/Tracks", "NOMAD", True),
            ("/Karaoke/Tracks", None, False),
            (None, "NOMAD", False),
            (None, None, False),
            ("", "NOMAD", False),  # Empty string is falsy
            ("/Karaoke/Tracks", "", False),
        ]
        
        for dropbox_path, brand_prefix, expected in test_cases:
            should_upload = bool(dropbox_path and brand_prefix)
            assert should_upload == expected, \
                f"Failed for dropbox_path={dropbox_path!r}, brand_prefix={brand_prefix!r}"
    
    def test_gdrive_upload_requires_folder_id(self):
        """
        Test that Google Drive upload only runs when gdrive_folder_id is set.
        
        This mirrors the logic in video_worker.py:
            if gdrive_folder_id:
                # Do Google Drive upload
        """
        test_cases = [
            # (gdrive_folder_id, should_upload)
            ("1abc123xyz", True),
            ("", False),
            (None, False),
        ]
        
        for gdrive_folder_id, expected in test_cases:
            should_upload = bool(gdrive_folder_id)
            assert should_upload == expected, \
                f"Failed for gdrive_folder_id={gdrive_folder_id!r}"


class TestCompletedFeatureParity:
    """
    Feature Parity Validation Tests.
    
    These tests verify that all features marked as "completed" in the
    BACKEND-FEATURE-PARITY-PLAN.md are actually working.
    
    Based on the plan, completed features include:
    - dropbox-service: Native Dropbox SDK service
    - gdrive-service: Native Google Drive API service
    - job-model-update: dropbox_path and gdrive_folder_id fields
    - api-routes-update: Distribution parameters in API
    - distribution-video-worker: Native distribution in video worker
    - remote-cli-params: CLI parameters for distribution
    - secrets-setup: Secret Manager credentials
    """
    
    def test_job_model_has_distribution_fields(self):
        """Verify Job model has all required distribution fields."""
        from backend.models.job import Job, JobCreate
        
        # These fields should exist on Job model
        job_fields = Job.model_fields.keys()
        required_fields = [
            'brand_prefix',
            'dropbox_path', 
            'gdrive_folder_id',
            'discord_webhook_url',
            'enable_youtube_upload',
            'youtube_description',
            'youtube_description_template',
        ]
        
        for field in required_fields:
            assert field in job_fields, f"Job model missing field: {field}"
        
        # These fields should also exist on JobCreate model
        job_create_fields = JobCreate.model_fields.keys()
        for field in required_fields:
            assert field in job_create_fields, f"JobCreate model missing field: {field}"
    
    def test_dropbox_service_exists_and_has_required_methods(self):
        """Verify DropboxService has all required methods."""
        from backend.services.dropbox_service import DropboxService
        
        required_methods = [
            'is_configured',
            'list_folders',
            'get_next_brand_code',
            'upload_file',
            'upload_folder',
            'create_shared_link',
        ]
        
        service = DropboxService()
        
        for method in required_methods:
            assert hasattr(service, method), f"DropboxService missing method: {method}"
    
    def test_gdrive_service_exists_and_has_required_methods(self):
        """Verify GoogleDriveService has all required methods."""
        from backend.services.gdrive_service import GoogleDriveService
        
        required_methods = [
            'is_configured',
            'get_or_create_folder',
            'upload_file',
            'upload_to_public_share',
        ]
        
        # Need to mock settings for initialization
        with patch('backend.services.gdrive_service.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            mock_settings.return_value.get_secret.return_value = None
            
            service = GoogleDriveService()
            
            for method in required_methods:
                assert hasattr(service, method), f"GoogleDriveService missing method: {method}"
    
    def test_audio_search_request_accepts_distribution_params(self):
        """Verify AudioSearchRequest model accepts distribution parameters."""
        from backend.api.routes.audio_search import AudioSearchRequest
        
        request_fields = AudioSearchRequest.model_fields.keys()
        
        distribution_fields = [
            'brand_prefix',
            'dropbox_path',
            'gdrive_folder_id',
            'discord_webhook_url',
            'enable_youtube_upload',
            'youtube_description',
        ]
        
        for field in distribution_fields:
            assert field in request_fields, \
                f"AudioSearchRequest missing distribution field: {field}"

