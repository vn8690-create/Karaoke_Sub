"""
Integration tests using local GCP emulators.

These tests use real Firestore and GCS emulators running locally,
providing true integration testing without cloud resources or costs.

Run with: ./scripts/run-emulator-tests.sh

NOTE: These are simplified integration tests that focus on the most critical
paths. They mock background workers to avoid race conditions and network issues.
"""
import pytest
import os
import time
from unittest.mock import AsyncMock, patch
from datetime import datetime, UTC
import requests


def emulators_running() -> bool:
    """Check if GCP emulators are running."""
    try:
        requests.get("http://127.0.0.1:8080", timeout=1)
        requests.get("http://127.0.0.1:4443", timeout=1)
        return True
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False


# Skip all tests in this module if emulators aren't running
pytestmark = pytest.mark.skipif(
    not emulators_running(),
    reason="GCP emulators not running. Start with: scripts/start-emulators.sh"
)

# Set emulator environment variables before any imports (use 127.0.0.1 for IPv4)
os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
os.environ["STORAGE_EMULATOR_HOST"] = "http://127.0.0.1:4443"
os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
os.environ["GCS_BUCKET_NAME"] = "test-bucket"
os.environ["FIRESTORE_COLLECTION"] = "test-jobs"  # Use separate collection for tests
os.environ["ENVIRONMENT"] = "test"
os.environ["ADMIN_TOKENS"] = "test-admin-token"

# Only import if emulators are running
if emulators_running():
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.models.job import JobStatus
else:
    TestClient = None
    app = None
    JobStatus = None


@pytest.fixture(scope="module", autouse=True)
def setup_gcs_bucket():
    """Create GCS bucket in emulator before tests."""
    try:
        response = requests.post(
            "http://localhost:4443/storage/v1/b",
            json={"name": "test-bucket"},
            params={"project": "test-project"}
        )
        if response.status_code in [200, 409]:
            print(f"✅ GCS bucket 'test-bucket' ready")
    except Exception as e:
        print(f"⚠️  GCS bucket setup failed: {e}")
    yield


@pytest.fixture(scope="module")
def mock_worker_service():
    """Mock the worker service to prevent background tasks."""
    with patch("backend.api.routes.jobs.worker_service") as mock:
        mock.trigger_audio_worker = AsyncMock(return_value=True)
        mock.trigger_lyrics_worker = AsyncMock(return_value=True)
        mock.trigger_screens_worker = AsyncMock(return_value=True)
        mock.trigger_video_worker = AsyncMock(return_value=True)
        yield mock


@pytest.fixture(scope="module")
def client(mock_worker_service):
    """Create FastAPI test client with mocked workers."""
    with patch("backend.api.routes.file_upload.worker_service", mock_worker_service):
        return TestClient(app)


@pytest.fixture
def auth_headers():
    """Auth headers for testing."""
    return {"Authorization": "Bearer test-admin-token"}


class TestEmulatorBasics:
    """Basic emulator connectivity tests."""
    
    def test_health_endpoint(self, client, auth_headers):
        """Test health endpoint works."""
        response = client.get("/api/health", )
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_root_endpoint(self, client, auth_headers):
        """Test root endpoint works."""
        response = client.get("/", )
        assert response.status_code == 200
        assert response.json()["service"] == "karaoke-gen-backend"


class TestJobCreation:
    """Test job creation with Firestore emulator."""
    
    def test_create_job_simple(self, client, auth_headers):
        """Test creating a simple job."""
        response = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "job_id" in data
        
    def test_create_job_with_metadata(self, client, auth_headers):
        """Test creating a job with artist/title."""
        response = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "url": "https://youtube.com/watch?v=test",
                "artist": "Test Artist",
                "title": "Test Song"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data


class TestJobRetrieval:
    """Test job retrieval from Firestore emulator."""
    
    def test_create_and_get_job(self, client, auth_headers):
        """Test creating and then retrieving a job."""
        # Create
        create_resp = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "url": "https://youtube.com/watch?v=abc123",
                "artist": "Test Artist",
                "title": "Test Song"
            }
        )
        assert create_resp.status_code == 200
        job_id = create_resp.json()["job_id"]
        
        # Small delay for emulator consistency
        time.sleep(0.2)
        
        # Retrieve
        get_resp = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        
        if get_resp.status_code != 200:
            print(f"GET failed: {get_resp.status_code} - {get_resp.text}")
        
        assert get_resp.status_code == 200
        
        job = get_resp.json()
        assert job["job_id"] == job_id
        assert job["status"] == "pending"
        assert job["artist"] == "Test Artist"
        assert job["title"] == "Test Song"
        
    def test_get_nonexistent_job(self, client, auth_headers):
        """Test fetching a job that doesn't exist."""
        response = client.get("/api/jobs/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404


class TestJobList:
    """Test listing jobs from Firestore."""
    
    def test_list_jobs(self, client, auth_headers):
        """Test listing jobs."""
        # Create a few jobs
        for i in range(3):
            client.post(
                "/api/jobs",
                headers=auth_headers,
                json={"url": f"https://youtube.com/watch?v=list{i}"}
            )
        
        time.sleep(0.2)
        
        # List
        response = client.get("/api/jobs", headers=auth_headers)
        assert response.status_code == 200
        
        jobs = response.json()
        assert isinstance(jobs, list)
        # We should have at least the 3 we just created
        assert len(jobs) >= 3


class TestJobDeletion:
    """Test job deletion."""
    
    def test_delete_job(self, client, auth_headers):
        """Test deleting a job."""
        # Create
        create_resp = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=delete-me"}
        )
        job_id = create_resp.json()["job_id"]
        
        time.sleep(0.2)
        
        # Delete
        del_resp = client.delete(f"/api/jobs/{job_id}", headers=auth_headers)
        assert del_resp.status_code == 200
        
        # Verify deleted
        get_resp = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        assert get_resp.status_code == 404


class TestJobUpdates:
    """Test job status updates."""
    
    def test_cancel_job(self, client, auth_headers):
        """Test cancelling a job."""
        # Create
        create_resp = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=cancel-me"}
        )
        job_id = create_resp.json()["job_id"]
        
        time.sleep(0.2)
        
        # Cancel
        cancel_resp = client.post(
            f"/api/jobs/{job_id}/cancel",
            headers=auth_headers,
            json={"reason": "test cancellation"}
        )
        assert cancel_resp.status_code == 200
        
        # Verify cancelled
        get_resp = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        job = get_resp.json()
        assert job["status"] == "cancelled"


class TestFileUpload:
    """Test file upload with GCS emulator."""
    
    def test_upload_file(self, client, auth_headers):
        """Test uploading a file."""
        test_file_content = b"fake audio data for testing"
        
        response = client.post(
            "/api/jobs/upload",
            headers={"Authorization": auth_headers["Authorization"]},
            files={"file": ("test.flac", test_file_content, "audio/flac")},
            data={"artist": "Upload Artist", "title": "Upload Song"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "job_id" in data
        
        job_id = data["job_id"]
        
        time.sleep(0.2)
        
        # Verify job created with upload data
        get_resp = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        job = get_resp.json()
        assert job["artist"] == "Upload Artist"
        assert job["title"] == "Upload Song"
        assert "input_media_gcs_path" in job


class TestInternalEndpoints:
    """Test internal worker endpoints."""
    
    def test_internal_workers_exist(self, client, auth_headers):
        """Test that internal worker endpoints exist and respond."""
        # Create a job first
        create_resp = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=worker-test"}
        )
        job_id = create_resp.json()["job_id"]
        
        time.sleep(0.2)
        
        # Test audio worker endpoint exists
        response = client.post(
            "/api/internal/workers/audio",
            headers=auth_headers,
            json={"job_id": job_id}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "started"


print("✅ Emulator integration tests ready to run")
