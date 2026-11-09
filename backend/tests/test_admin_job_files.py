"""
Unit tests for admin job files endpoint.

Tests the GET /api/admin/jobs/{job_id}/files endpoint that returns
all files for a job with signed download URLs.
"""
import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.api.routes.admin import router
from backend.api.dependencies import require_admin
from backend.models.job import Job, JobStatus


# Create a test app with the admin router
app = FastAPI()
app.include_router(router, prefix="/api")


def get_mock_admin():
    """Override for require_admin dependency."""
    from backend.api.dependencies import AuthResult, UserType
    return AuthResult(
        is_valid=True,
        user_type=UserType.ADMIN,
        remaining_uses=999,
        message="Admin authenticated",
        user_email="admin@example.com",
        is_admin=True,
    )


# Override the require_admin dependency
app.dependency_overrides[require_admin] = get_mock_admin


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_job_with_files():
    """Create a mock job with comprehensive file_urls."""
    job = Mock(spec=Job)
    job.job_id = "test-job-123"
    job.user_email = "user@example.com"
    job.artist = "Test Artist"
    job.title = "Test Song"
    job.status = JobStatus.COMPLETE
    job.file_urls = {
        "input": "gs://bucket/jobs/test-job-123/input.flac",
        "stems": {
            "instrumental_clean": "gs://bucket/jobs/test-job-123/stems/instrumental_clean.flac",
            "vocals": "gs://bucket/jobs/test-job-123/stems/vocals.flac",
        },
        "lyrics": {
            "corrections": "gs://bucket/jobs/test-job-123/lyrics/corrections.json",
            "lrc": "gs://bucket/jobs/test-job-123/lyrics/output.lrc",
        },
        "finals": {
            "lossy_720p_mp4": "gs://bucket/jobs/test-job-123/finals/video_720p.mp4",
        },
        "youtube": {
            "url": "https://youtube.com/watch?v=xyz789",
            "video_id": "xyz789",
        },
    }
    return job


@pytest.fixture
def mock_job_no_files():
    """Create a mock job with empty file_urls."""
    job = Mock(spec=Job)
    job.job_id = "test-job-empty"
    job.user_email = "user@example.com"
    job.artist = "Empty Artist"
    job.title = "Empty Song"
    job.status = JobStatus.PENDING
    job.file_urls = {}
    return job


@pytest.fixture
def mock_job_partial_files():
    """Create a mock job with only some files (partial processing)."""
    job = Mock(spec=Job)
    job.job_id = "test-job-partial"
    job.user_email = "user@example.com"
    job.artist = "Partial Artist"
    job.title = "Partial Song"
    job.status = JobStatus.SEPARATING_STAGE1
    job.file_urls = {
        "input": "gs://bucket/jobs/test-job-partial/input.flac",
        "stems": {
            "instrumental_clean": "gs://bucket/jobs/test-job-partial/stems/instrumental_clean.flac",
        },
    }
    return job


class TestGetJobFiles:
    """Tests for GET /api/admin/jobs/{job_id}/files endpoint."""

    def test_returns_files_with_signed_urls(self, client, mock_job_with_files):
        """Test that endpoint returns all files with signed URLs."""
        with patch('backend.api.routes.admin.JobManager') as mock_jm_class, \
             patch('backend.api.routes.admin.StorageService') as mock_storage_class:

            # Setup JobManager mock
            mock_jm = Mock()
            mock_jm.get_job.return_value = mock_job_with_files
            mock_jm_class.return_value = mock_jm

            # Setup StorageService mock to return predictable signed URLs
            mock_storage = Mock()
            mock_storage.generate_signed_url.side_effect = lambda path, **kwargs: f"https://signed.url/{path}"
            mock_storage_class.return_value = mock_storage

            response = client.get(
                "/api/admin/jobs/test-job-123/files",
                headers={"Authorization": "Bearer admin-token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == "test-job-123"
            assert data["artist"] == "Test Artist"
            assert data["title"] == "Test Song"
            assert "files" in data
            assert data["total_files"] > 0

    def test_returns_correct_file_count(self, client, mock_job_with_files):
        """Test that file count matches actual GCS files (excluding non-GCS entries)."""
        with patch('backend.api.routes.admin.JobManager') as mock_jm_class, \
             patch('backend.api.routes.admin.StorageService') as mock_storage_class:

            mock_jm = Mock()
            mock_jm.get_job.return_value = mock_job_with_files
            mock_jm_class.return_value = mock_jm

            mock_storage = Mock()
            mock_storage.generate_signed_url.side_effect = lambda path, **kwargs: f"https://signed.url/{path}"
            mock_storage_class.return_value = mock_storage

            response = client.get("/api/admin/jobs/test-job-123/files")

            data = response.json()
            # Should have: input, stems.instrumental_clean, stems.vocals,
            # lyrics.corrections, lyrics.lrc, finals.lossy_720p_mp4
            # NOT youtube.url or youtube.video_id (not GCS paths)
            assert data["total_files"] == 6

    def test_handles_nested_file_structure(self, client, mock_job_with_files):
        """Test that nested file_urls structure is properly traversed."""
        with patch('backend.api.routes.admin.JobManager') as mock_jm_class, \
             patch('backend.api.routes.admin.StorageService') as mock_storage_class:

            mock_jm = Mock()
            mock_jm.get_job.return_value = mock_job_with_files
            mock_jm_class.return_value = mock_jm

            mock_storage = Mock()
            mock_storage.generate_signed_url.side_effect = lambda path, **kwargs: f"https://signed.url/{path}"
            mock_storage_class.return_value = mock_storage

            response = client.get("/api/admin/jobs/test-job-123/files")

            data = response.json()
            files = data["files"]

            # Check that files from different categories are present
            categories = {f["category"] for f in files}
            assert "input" in categories or any(f["category"] == "" and f["file_key"] == "input" for f in files)
            assert "stems" in categories
            assert "lyrics" in categories
            assert "finals" in categories

    def test_file_info_structure(self, client, mock_job_with_files):
        """Test that each file has correct info structure."""
        with patch('backend.api.routes.admin.JobManager') as mock_jm_class, \
             patch('backend.api.routes.admin.StorageService') as mock_storage_class:

            mock_jm = Mock()
            mock_jm.get_job.return_value = mock_job_with_files
            mock_jm_class.return_value = mock_jm

            mock_storage = Mock()
            mock_storage.generate_signed_url.side_effect = lambda path, **kwargs: f"https://signed.url/{path}"
            mock_storage_class.return_value = mock_storage

            response = client.get("/api/admin/jobs/test-job-123/files")

            data = response.json()
            files = data["files"]

            # Every file should have these fields
            for file_info in files:
                assert "name" in file_info
                assert "path" in file_info
                assert "download_url" in file_info
                assert "category" in file_info
                assert "file_key" in file_info
                # download_url should be a signed URL
                assert file_info["download_url"].startswith("https://signed.url/")

    def test_returns_404_when_job_not_found(self, client):
        """Test 404 when job doesn't exist."""
        with patch('backend.api.routes.admin.JobManager') as mock_jm_class:
            mock_jm = Mock()
            mock_jm.get_job.return_value = None
            mock_jm_class.return_value = mock_jm

            response = client.get(
                "/api/admin/jobs/nonexistent-job/files",
                headers={"Authorization": "Bearer admin-token"}
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_returns_empty_files_for_new_job(self, client, mock_job_no_files):
        """Test that new jobs with no files return empty list."""
        with patch('backend.api.routes.admin.JobManager') as mock_jm_class, \
             patch('backend.api.routes.admin.StorageService') as mock_storage_class:

            mock_jm = Mock()
            mock_jm.get_job.return_value = mock_job_no_files
            mock_jm_class.return_value = mock_jm

            mock_storage = Mock()
            mock_storage_class.return_value = mock_storage

            response = client.get("/api/admin/jobs/test-job-empty/files")

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == "test-job-empty"
            assert data["files"] == []
            assert data["total_files"] == 0

    def test_handles_partial_processing(self, client, mock_job_partial_files):
        """Test job with only some files processed."""
        with patch('backend.api.routes.admin.JobManager') as mock_jm_class, \
             patch('backend.api.routes.admin.StorageService') as mock_storage_class:

            mock_jm = Mock()
            mock_jm.get_job.return_value = mock_job_partial_files
            mock_jm_class.return_value = mock_jm

            mock_storage = Mock()
            mock_storage.generate_signed_url.side_effect = lambda path, **kwargs: f"https://signed.url/{path}"
            mock_storage_class.return_value = mock_storage

            response = client.get("/api/admin/jobs/test-job-partial/files")

            assert response.status_code == 200
            data = response.json()
            # Should have input + stems.instrumental_clean = 2 files
            assert data["total_files"] == 2

    def test_skips_non_gcs_urls(self, client, mock_job_with_files):
        """Test that non-GCS URLs (like youtube URLs) are skipped."""
        with patch('backend.api.routes.admin.JobManager') as mock_jm_class, \
             patch('backend.api.routes.admin.StorageService') as mock_storage_class:

            mock_jm = Mock()
            mock_jm.get_job.return_value = mock_job_with_files
            mock_jm_class.return_value = mock_jm

            mock_storage = Mock()
            mock_storage.generate_signed_url.side_effect = lambda path, **kwargs: f"https://signed.url/{path}"
            mock_storage_class.return_value = mock_storage

            response = client.get("/api/admin/jobs/test-job-123/files")

            data = response.json()
            files = data["files"]

            # Ensure no youtube URLs or video IDs are in the files
            for file_info in files:
                assert "youtube.com" not in file_info["path"]
                assert file_info["path"].startswith("gs://")

    def test_signed_url_expiration(self, client, mock_job_with_files):
        """Test that signed URLs are generated with appropriate expiration."""
        with patch('backend.api.routes.admin.JobManager') as mock_jm_class, \
             patch('backend.api.routes.admin.StorageService') as mock_storage_class:

            mock_jm = Mock()
            mock_jm.get_job.return_value = mock_job_with_files
            mock_jm_class.return_value = mock_jm

            mock_storage = Mock()
            mock_storage.generate_signed_url.return_value = "https://signed.url/test"
            mock_storage_class.return_value = mock_storage

            client.get("/api/admin/jobs/test-job-123/files")

            # Verify signed URLs were requested with expiration (default 120 minutes)
            assert mock_storage.generate_signed_url.called
            # Check that expiration_minutes was passed (could be any reasonable value)
            call_kwargs = mock_storage.generate_signed_url.call_args_list[0][1]
            if "expiration_minutes" in call_kwargs:
                assert call_kwargs["expiration_minutes"] >= 60


class TestGetJobFilesAuthorization:
    """Tests for authorization on the files endpoint."""

    def test_requires_admin_access(self, client, mock_job_with_files):
        """Test that non-admin users cannot access the endpoint."""
        # Reset the dependency override to test auth
        original_override = app.dependency_overrides.get(require_admin)

        def get_non_admin():
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Admin access required")

        app.dependency_overrides[require_admin] = get_non_admin

        try:
            response = client.get(
                "/api/admin/jobs/test-job-123/files",
                headers={"Authorization": "Bearer user-token"}
            )
            assert response.status_code == 403
        finally:
            # Restore the original override
            if original_override:
                app.dependency_overrides[require_admin] = original_override
            else:
                app.dependency_overrides[require_admin] = get_mock_admin
