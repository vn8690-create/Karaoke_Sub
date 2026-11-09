"""
Integration tests using local GCP emulators.

These tests use real Firestore and GCS emulators running locally,
providing true integration testing without cloud resources or costs.

Run with: ./scripts/run-emulator-tests.sh

NOTE: These tests mock background workers to avoid race conditions.
The fixtures are defined in conftest.py in this directory.
"""
import pytest
import time

from .conftest import emulators_running


# Skip all tests in this module if emulators aren't running
pytestmark = pytest.mark.skipif(
    not emulators_running(),
    reason="GCP emulators not running. Start with: scripts/start-emulators.sh"
)

# Fixtures are loaded from conftest.py in this directory


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


class TestReviewEndpoints:
    """Test lyrics review API endpoints."""
    
    def test_review_ping(self, client, auth_headers):
        """Test review ping endpoint."""
        # Create a job first
        create_resp = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=review-test"}
        )
        job_id = create_resp.json()["job_id"]
        
        # Ping should work for any job
        response = client.get(f"/api/review/{job_id}/ping")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_review_correction_data_wrong_status(self, client, auth_headers):
        """Test that correction-data returns error for non-review jobs."""
        # Create a job (starts in pending status)
        create_resp = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=review-status-test"}
        )
        job_id = create_resp.json()["job_id"]
        
        time.sleep(0.2)
        
        # Should fail - job not in AWAITING_REVIEW status
        response = client.get(f"/api/review/{job_id}/correction-data", headers=auth_headers)
        assert response.status_code == 400
        assert "not ready for review" in response.json()["detail"].lower()
    
    def test_review_audio_no_job(self, client, auth_headers):
        """Test audio endpoint returns 404 for nonexistent job."""
        response = client.get("/api/review/nonexistent-job/audio/", headers=auth_headers)
        assert response.status_code == 404
    
    def test_review_preview_video_stub(self, client, auth_headers):
        """Test preview video endpoint exists."""
        # Create a job
        create_resp = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=preview-test"}
        )
        job_id = create_resp.json()["job_id"]
        
        # Preview video should return error since job not ready
        response = client.post(
            f"/api/review/{job_id}/preview-video",
            headers=auth_headers,
            json={"corrections": [], "corrected_segments": []}
        )
        # Should return 400 (job not in AWAITING_REVIEW state)
        assert response.status_code == 400
    
    def test_review_annotations_stub(self, client, auth_headers):
        """Test annotations endpoint (stub)."""
        create_resp = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=annotation-test"}
        )
        job_id = create_resp.json()["job_id"]
        
        # Annotations endpoint should accept data (even if it just logs it)
        response = client.post(
            f"/api/review/{job_id}/v1/annotations",
            headers=auth_headers,
            json={"type": "test", "data": "test annotation"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"


class TestRenderVideoWorker:
    """Test render video worker endpoint."""

    def test_render_video_worker_endpoint_exists(self, client, auth_headers):
        """Test that render-video worker endpoint exists."""
        # Create a job
        create_resp = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=render-test"}
        )
        job_id = create_resp.json()["job_id"]

        time.sleep(0.2)

        # Test render-video worker endpoint exists
        response = client.post(
            "/api/internal/workers/render-video",
            headers=auth_headers,
            json={"job_id": job_id}
        )
        # Should return 200 (endpoint exists and starts)
        assert response.status_code == 200


print("✅ Emulator integration tests ready to run")
