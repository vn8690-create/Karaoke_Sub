"""
Integration tests for the karaoke generation backend API.

These tests verify the backend works end-to-end with real Cloud Run deployment.
These tests require a deployed backend and are marked to skip unless explicitly enabled.

Run with: pytest backend/tests/test_api_integration.py -m integration
"""
import pytest
import requests
import subprocess
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any
import os


# Skip all tests unless explicitly running integration tests
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "true",
    reason="Integration tests require deployed backend. Set RUN_INTEGRATION_TESTS=true to run."
)

# Configuration
SERVICE_URL = "https://karaoke-backend-718638054799.us-central1.run.app"
TEST_YOUTUBE_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
DEFAULT_TIMEOUT = 30  # seconds


def api_get(url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> requests.Response:
    """Make a GET request with default timeout."""
    return requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT, **kwargs)


def api_post(url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> requests.Response:
    """Make a POST request with default timeout."""
    return requests.post(url, headers=headers, timeout=DEFAULT_TIMEOUT, **kwargs)


def api_delete(url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> requests.Response:
    """Make a DELETE request with default timeout."""
    return requests.delete(url, headers=headers, timeout=DEFAULT_TIMEOUT, **kwargs)


def get_auth_token() -> str:
    """Get authentication token for Cloud Run."""
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()


@pytest.fixture
def auth_headers():
    """Get authentication headers for requests."""
    token = get_auth_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self, auth_headers):
        """Test that health endpoint returns 200 OK."""
        response = api_get(f"{SERVICE_URL}/api/health", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "karaoke-gen-backend"
    
    def test_health_check_without_auth(self):
        """Test that health endpoint requires authentication."""
        response = api_get(f"{SERVICE_URL}/api/health")
        assert response.status_code == 403


class TestRootEndpoint:
    """Test root endpoint."""
    
    def test_root_endpoint(self, auth_headers):
        """Test root endpoint returns service info."""
        response = api_get(SERVICE_URL, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["service"] == "karaoke-gen-backend"
        assert data["status"] == "running"
        assert "version" in data


class TestJobSubmission:
    """Test job submission workflows."""
    
    def test_submit_job_with_youtube_url(self, auth_headers):
        """Test submitting a job with a YouTube URL."""
        payload = {"url": TEST_YOUTUBE_URL}
        response = api_post(
            f"{SERVICE_URL}/api/jobs",
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "job_id" in data
        assert len(data["job_id"]) > 0
        assert "message" in data
        
        # Store job_id for cleanup
        return data["job_id"]
    
    def test_submit_job_with_invalid_url(self, auth_headers):
        """Test that invalid URLs are rejected."""
        payload = {"url": "not-a-url"}
        response = api_post(
            f"{SERVICE_URL}/api/jobs",
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_submit_job_without_url(self, auth_headers):
        """Test that missing URL is rejected."""
        payload = {}
        response = api_post(
            f"{SERVICE_URL}/api/jobs",
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 422  # Validation error


class TestJobRetrieval:
    """Test job retrieval and status checking."""
    
    @pytest.fixture
    def test_job_id(self, auth_headers):
        """Create a test job for retrieval tests."""
        payload = {"url": TEST_YOUTUBE_URL}
        response = api_post(
            f"{SERVICE_URL}/api/jobs",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        yield job_id
        
        # Cleanup
        api_delete(
            f"{SERVICE_URL}/api/jobs/{job_id}",
            headers=auth_headers
        )
    
    def test_get_job_status(self, auth_headers, test_job_id):
        """Test retrieving job status."""
        response = api_get(
            f"{SERVICE_URL}/api/jobs/{test_job_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == test_job_id
        assert "status" in data
        # Updated to use current JobStatus enum values
        assert data["status"] in ["pending", "downloading", "separating_stage1",
                                  "separating_stage2", "audio_complete",
                                  "transcribing", "correcting", "lyrics_complete",
                                  "generating_screens", "applying_padding",
                                  "awaiting_review", "in_review", "review_complete",
                                  "rendering_video", "awaiting_instrumental_selection",
                                  "instrumental_selected", "generating_video",
                                  "encoding", "packaging", "uploading", "notifying",
                                  "complete", "failed", "cancelled"]
        assert "progress" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "timeline" in data
    
    def test_get_nonexistent_job(self, auth_headers):
        """Test that requesting nonexistent job returns 404."""
        fake_job_id = "nonexistent-job-id"
        response = api_get(
            f"{SERVICE_URL}/api/jobs/{fake_job_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_list_jobs(self, auth_headers, test_job_id):
        """Test listing all jobs."""
        response = api_get(
            f"{SERVICE_URL}/api/jobs",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # Our test job should be in the list
        job_ids = [job["job_id"] for job in data]
        assert test_job_id in job_ids
    
    def test_list_jobs_with_status_filter(self, auth_headers):
        """Test filtering jobs by status."""
        response = api_get(
            f"{SERVICE_URL}/api/jobs?status=pending",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # All returned jobs should be pending
        for job in data:
            assert job["status"] == "pending"
    
    def test_list_jobs_with_limit(self, auth_headers):
        """Test limiting number of returned jobs."""
        response = api_get(
            f"{SERVICE_URL}/api/jobs?limit=5",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 5


class TestJobDeletion:
    """Test job deletion."""
    
    def test_delete_job(self, auth_headers):
        """Test deleting a job."""
        # Create a job
        payload = {"url": TEST_YOUTUBE_URL}
        response = api_post(
            f"{SERVICE_URL}/api/jobs",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Delete the job
        response = api_delete(
            f"{SERVICE_URL}/api/jobs/{job_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify job is deleted
        response = api_get(
            f"{SERVICE_URL}/api/jobs/{job_id}",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    def test_delete_job_without_files(self, auth_headers):
        """Test deleting a job without deleting files."""
        # Create a job
        payload = {"url": TEST_YOUTUBE_URL}
        response = api_post(
            f"{SERVICE_URL}/api/jobs",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Delete job but keep files
        response = api_delete(
            f"{SERVICE_URL}/api/jobs/{job_id}?delete_files=false",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    def test_delete_nonexistent_job(self, auth_headers):
        """Test deleting nonexistent job returns 404."""
        fake_job_id = "nonexistent-job-id"
        response = api_delete(
            f"{SERVICE_URL}/api/jobs/{fake_job_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestFileUpload:
    """Test file upload endpoint."""
    
    def test_upload_audio_file(self, auth_headers, tmp_path):
        """Test uploading an audio file."""
        # Create a small test file
        test_file = tmp_path / "test_audio.mp3"
        test_file.write_bytes(b"fake audio content for testing")
        
        # Upload file
        with open(test_file, "rb") as f:
            files = {"file": ("test_audio.mp3", f, "audio/mpeg")}
            data = {
                "artist": "Test Artist",
                "title": "Test Song"
            }
            
            # Remove Content-Type header for multipart/form-data
            headers = {
                "Authorization": auth_headers["Authorization"]
            }
            
            response = api_post(
                f"{SERVICE_URL}/api/jobs/upload",
                headers=headers,
                files=files,
                data=data
            )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["status"] == "success"
        assert "job_id" in result
        
        # Cleanup
        api_delete(
            f"{SERVICE_URL}/api/jobs/{result['job_id']}",
            headers=auth_headers
        )
    
    def test_upload_invalid_file_type(self, auth_headers, tmp_path):
        """Test that invalid file types are rejected."""
        # Create a test file with invalid extension
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"not an audio file")
        
        with open(test_file, "rb") as f:
            files = {"file": ("test.txt", f, "text/plain")}
            data = {
                "artist": "Test Artist",
                "title": "Test Song"
            }
            
            headers = {
                "Authorization": auth_headers["Authorization"]
            }
            
            response = api_post(
                f"{SERVICE_URL}/api/jobs/upload",
                headers=headers,
                files=files,
                data=data
            )
        
        assert response.status_code == 400
    
    def test_upload_without_metadata(self, auth_headers, tmp_path):
        """Test that uploads without artist/title are rejected."""
        test_file = tmp_path / "test_audio.mp3"
        test_file.write_bytes(b"fake audio content")
        
        with open(test_file, "rb") as f:
            files = {"file": ("test_audio.mp3", f, "audio/mpeg")}
            
            headers = {
                "Authorization": auth_headers["Authorization"]
            }
            
            response = api_post(
                f"{SERVICE_URL}/api/jobs/upload",
                headers=headers,
                files=files
            )
        
        assert response.status_code == 422  # Validation error


class TestJobProcessing:
    """Test end-to-end job processing (long-running)."""
    
    @pytest.mark.slow
    @pytest.mark.integration
    def test_complete_job_workflow(self, auth_headers):
        """
        Test complete job workflow from submission to completion.
        
        This test is slow and requires actual processing.
        Run with: pytest -m slow
        """
        # Submit job
        payload = {"url": TEST_YOUTUBE_URL}
        response = api_post(
            f"{SERVICE_URL}/api/jobs",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Poll for completion (with timeout)
        timeout = 600  # 10 minutes
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = api_get(
                f"{SERVICE_URL}/api/jobs/{job_id}",
                headers=auth_headers
            )
            assert response.status_code == 200
            
            job = response.json()
            status = job["status"]
            
            if status == "complete":
                # Verify outputs exist
                assert "download_urls" in job
                assert len(job["download_urls"]) > 0
                break
            elif status == "failed":
                pytest.fail(f"Job failed: {job.get('error_message')}")
            
            # Wait before next poll
            time.sleep(10)
        else:
            pytest.fail(f"Job did not complete within {timeout} seconds")
        
        # Cleanup
        api_delete(
            f"{SERVICE_URL}/api/jobs/{job_id}",
            headers=auth_headers
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

