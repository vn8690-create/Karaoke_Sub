"""
Unit tests for file_upload.py API routes using FastAPI TestClient.
"""
import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from io import BytesIO

from backend.models.job import Job, JobStatus


@pytest.fixture
def upload_auth_headers():
    """Auth headers for file upload tests (no Content-Type, let multipart work)."""
    return {
        "Authorization": "Bearer test-admin-token"
    }


@pytest.fixture
def mock_job():
    """Create a standard mock job."""
    return Job(
        job_id="test123",
        status=JobStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        artist="Test Artist",
        title="Test Song",
        input_media_gcs_path="uploads/test123/song.flac"
    )


@pytest.fixture
def mock_services(mock_job):
    """Create all mocked services needed for upload."""
    mock_job_manager = MagicMock()
    mock_job_manager.create_job.return_value = mock_job
    mock_job_manager.get_job.return_value = mock_job
    mock_job_manager.update_job.return_value = None
    
    mock_storage = MagicMock()
    mock_storage.upload_fileobj.return_value = "gs://bucket/uploads/test123/song.flac"
    
    mock_worker_service = MagicMock()
    mock_worker_service.trigger_audio_worker = AsyncMock(return_value=True)
    mock_worker_service.trigger_lyrics_worker = AsyncMock(return_value=True)
    
    return {
        'job_manager': mock_job_manager,
        'storage': mock_storage,
        'worker_service': mock_worker_service
    }


@pytest.fixture
def client(mock_services):
    """Create TestClient with mocked dependencies."""
    mock_creds = MagicMock()
    mock_creds.universe_domain = 'googleapis.com'
    
    with patch('backend.api.routes.file_upload.job_manager', mock_services['job_manager']), \
         patch('backend.api.routes.file_upload.storage_service', mock_services['storage']), \
         patch('backend.api.routes.file_upload.worker_service', mock_services['worker_service']), \
         patch('backend.services.firestore_service.firestore'), \
         patch('backend.services.storage_service.storage'), \
         patch('google.auth.default', return_value=(mock_creds, 'test-project')):
        from backend.main import app
        yield TestClient(app)


class TestFileUploadEndpoint:
    """Tests for POST /api/jobs/upload."""
    
    def test_upload_flac_returns_200(self, client, mock_services, upload_auth_headers):
        """Test uploading FLAC file returns 200."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("test.flac", BytesIO(b"fake audio"), "audio/flac")},
            data={"artist": "Test Artist", "title": "Test Song"}
        )
        assert response.status_code == 200
    
    def test_upload_mp3_returns_200(self, client, mock_services, upload_auth_headers):
        """Test uploading MP3 file returns 200."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("test.mp3", BytesIO(b"fake audio"), "audio/mpeg")},
            data={"artist": "Test Artist", "title": "Test Song"}
        )
        assert response.status_code == 200
    
    def test_upload_wav_returns_200(self, client, mock_services, upload_auth_headers):
        """Test uploading WAV file returns 200."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("test.wav", BytesIO(b"fake audio"), "audio/wav")},
            data={"artist": "Test Artist", "title": "Test Song"}
        )
        assert response.status_code == 200
    
    def test_upload_returns_job_id(self, client, mock_services, upload_auth_headers):
        """Test upload response contains job_id."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("test.flac", BytesIO(b"fake audio"), "audio/flac")},
            data={"artist": "Test", "title": "Song"}
        )
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "success"
    
    def test_upload_returns_filename(self, client, mock_services, upload_auth_headers):
        """Test upload response contains original filename."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("my_song.flac", BytesIO(b"fake audio"), "audio/flac")},
            data={"artist": "Test", "title": "Song"}
        )
        data = response.json()
        assert "filename" in data
        assert data["filename"] == "my_song.flac"
    
    def test_upload_rejects_txt_file(self, client, mock_services, upload_auth_headers):
        """Test upload rejects text files."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("test.txt", BytesIO(b"not audio"), "text/plain")},
            data={"artist": "Test", "title": "Song"}
        )
        assert response.status_code == 400
    
    def test_upload_rejects_pdf_file(self, client, mock_services, upload_auth_headers):
        """Test upload rejects PDF files."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("doc.pdf", BytesIO(b"pdf content"), "application/pdf")},
            data={"artist": "Test", "title": "Song"}
        )
        assert response.status_code == 400
    
    def test_upload_rejects_exe_file(self, client, mock_services, upload_auth_headers):
        """Test upload rejects executable files."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("app.exe", BytesIO(b"exe content"), "application/octet-stream")},
            data={"artist": "Test", "title": "Song"}
        )
        assert response.status_code == 400
    
    def test_upload_requires_artist(self, client, mock_services, upload_auth_headers):
        """Test upload requires artist field."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("test.flac", BytesIO(b"audio"), "audio/flac")},
            data={"title": "Song"}  # Missing artist
        )
        assert response.status_code == 422
    
    def test_upload_requires_title(self, client, mock_services, upload_auth_headers):
        """Test upload requires title field."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("test.flac", BytesIO(b"audio"), "audio/flac")},
            data={"artist": "Artist"}  # Missing title
        )
        assert response.status_code == 422
    
    def test_upload_requires_file(self, client, mock_services, upload_auth_headers):
        """Test upload requires file."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            data={"artist": "Artist", "title": "Song"}
            # Missing file
        )
        assert response.status_code == 422
    
    def test_upload_triggers_workers(self, client, mock_services, upload_auth_headers):
        """Test upload triggers audio and lyrics workers."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("test.flac", BytesIO(b"audio"), "audio/flac")},
            data={"artist": "Test", "title": "Song"}
        )
        assert response.status_code == 200
        # Workers should be triggered in background
    
    def test_upload_creates_job(self, client, mock_services, upload_auth_headers):
        """Test upload creates job in job manager."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("test.flac", BytesIO(b"audio"), "audio/flac")},
            data={"artist": "Test", "title": "Song"}
        )
        assert response.status_code == 200
        mock_services['job_manager'].create_job.assert_called()
    
    def test_upload_stores_file_to_gcs(self, client, mock_services, upload_auth_headers):
        """Test upload stores file to GCS."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("test.flac", BytesIO(b"audio"), "audio/flac")},
            data={"artist": "Test", "title": "Song"}
        )
        assert response.status_code == 200
        mock_services['storage'].upload_fileobj.assert_called()


class TestUploadValidation:
    """Tests for upload validation logic."""
    
    def test_upload_accepts_m4a(self, client, mock_services, upload_auth_headers):
        """Test upload accepts M4A files."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("test.m4a", BytesIO(b"audio"), "audio/mp4")},
            data={"artist": "Test", "title": "Song"}
        )
        assert response.status_code == 200
    
    def test_upload_accepts_ogg(self, client, mock_services, upload_auth_headers):
        """Test upload accepts OGG files."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("test.ogg", BytesIO(b"audio"), "audio/ogg")},
            data={"artist": "Test", "title": "Song"}
        )
        assert response.status_code == 200
    
    def test_upload_accepts_aac(self, client, mock_services, upload_auth_headers):
        """Test upload accepts AAC files."""
        response = client.post(
            "/api/jobs/upload",
            headers=upload_auth_headers,
            files={"file": ("test.aac", BytesIO(b"audio"), "audio/aac")},
            data={"artist": "Test", "title": "Song"}
        )
        assert response.status_code == 200

