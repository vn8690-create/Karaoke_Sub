"""
Tests for the cleanup-distribution endpoint in jobs.py.

Verifies:
- GDrive cleanup uses tracked file IDs from state_data when available (fast path)
- GDrive cleanup falls back to brand_code search when gdrive_files is empty (fallback path)
- Brand code is recycled ONLY after both Dropbox AND GDrive are confirmed clean
- Brand code is NOT recycled when GDrive cleanup fails or is skipped
- Endpoint returns correct status for each distribution service

The cleanup-distribution endpoint is used by the E2E happy-path test (Step 12)
to remove test job files from YouTube, Dropbox, and Google Drive after the test.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from datetime import datetime, UTC

from backend.api.routes.jobs import router
from backend.api.dependencies import require_admin, require_auth, AuthResult, UserType
from backend.models.job import Job, JobStatus


# ─── Test App ────────────────────────────────────────────────────────────────

def get_mock_admin():
    return AuthResult(
        is_valid=True,
        user_type=UserType.ADMIN,
        remaining_uses=999,
        message="Admin authenticated",
        user_email="admin@example.com",
        is_admin=True,
    )


app = FastAPI()
app.include_router(router, prefix="/api")
app.dependency_overrides[require_admin] = get_mock_admin
app.dependency_overrides[require_auth] = get_mock_admin


@pytest.fixture
def client():
    return TestClient(app)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_job(
    *,
    brand_code="NOMAD-1271",
    gdrive_files=None,
    gdrive_folder_id="root-folder-id",
    dropbox_path="/Tracks-PublicShare",
    artist="piri",
    title="dog",
):
    """Make a mock Job in COMPLETE state with the given distribution data."""
    job = Mock(spec=Job)
    job.job_id = "test-job-id"
    job.status = JobStatus.COMPLETE
    job.artist = artist
    job.title = title
    job.dropbox_path = dropbox_path
    job.gdrive_folder_id = gdrive_folder_id
    job.state_data = {
        "brand_code": brand_code,
        "gdrive_files": gdrive_files if gdrive_files is not None else {},
    }
    return job


# ─── GDrive Cleanup — Fast Path (tracked file IDs) ───────────────────────────

class TestCleanupDistributionGDriveTrackedFileIDs:
    """GDrive cleanup uses tracked file IDs from state_data when available."""

    def test_gdrive_cleanup_uses_tracked_file_ids(self, client):
        """When gdrive_files has file IDs, delete_files is called with those IDs."""
        job = _make_job(gdrive_files={"mp4": "file-id-mp4", "cdg": "file-id-cdg"})

        mock_dropbox = Mock()
        mock_dropbox.is_configured = True
        mock_dropbox.delete_folder.return_value = True

        mock_gdrive = Mock()
        mock_gdrive.is_configured = True
        mock_gdrive.delete_files.return_value = {"file-id-mp4": True, "file-id-cdg": True}

        mock_brand_service = Mock()

        with patch("backend.api.routes.jobs.job_manager") as mock_jm, \
             patch("backend.services.dropbox_service.get_dropbox_service", return_value=mock_dropbox), \
             patch("backend.services.gdrive_service.get_gdrive_service", return_value=mock_gdrive), \
             patch("backend.services.brand_code_service.get_brand_code_service", return_value=mock_brand_service):
            mock_jm.get_job.return_value = job
            mock_jm.delete_job.return_value = None

            response = client.post("/api/jobs/test-job-id/cleanup-distribution")

        assert response.status_code == 200
        data = response.json()

        # Should have used the tracked file IDs (fast path)
        mock_gdrive.delete_files.assert_called_once_with(["file-id-mp4", "file-id-cdg"])
        # Should NOT have searched by brand code
        mock_gdrive.find_files_by_brand_code.assert_not_called()

        assert data["gdrive"]["status"] == "success"

    def test_gdrive_cleanup_reports_partial_when_some_deletes_fail(self, client):
        """When some file deletes fail, status is 'partial'."""
        job = _make_job(gdrive_files={"mp4": "file-id-mp4", "cdg": "file-id-cdg"})

        mock_dropbox = Mock()
        mock_dropbox.is_configured = True
        mock_dropbox.delete_folder.return_value = True

        mock_gdrive = Mock()
        mock_gdrive.is_configured = True
        mock_gdrive.delete_files.return_value = {
            "file-id-mp4": True,
            "file-id-cdg": False,  # This one failed
        }

        mock_brand_service = Mock()

        with patch("backend.api.routes.jobs.job_manager") as mock_jm, \
             patch("backend.services.dropbox_service.get_dropbox_service", return_value=mock_dropbox), \
             patch("backend.services.gdrive_service.get_gdrive_service", return_value=mock_gdrive), \
             patch("backend.services.brand_code_service.get_brand_code_service", return_value=mock_brand_service):
            mock_jm.get_job.return_value = job
            mock_jm.delete_job.return_value = None

            response = client.post("/api/jobs/test-job-id/cleanup-distribution")

        assert response.status_code == 200
        data = response.json()
        assert data["gdrive"]["status"] == "partial"


# ─── GDrive Cleanup — Fallback Path (brand_code search) ──────────────────────

class TestCleanupDistributionGDriveFallback:
    """GDrive cleanup searches by brand_code when gdrive_files is empty."""

    def test_falls_back_to_brand_code_search_when_gdrive_files_empty(self, client):
        """When gdrive_files={}, search GDrive by brand_code and delete found files."""
        job = _make_job(gdrive_files={})  # Empty — simulates old jobs / silently-failed uploads

        mock_dropbox = Mock()
        mock_dropbox.is_configured = True
        mock_dropbox.delete_folder.return_value = True

        mock_gdrive = Mock()
        mock_gdrive.is_configured = True
        # find_files_by_brand_code returns file IDs found by searching GDrive
        mock_gdrive.find_files_by_brand_code.return_value = ["old-file-id-cdg", "old-file-id-mp4"]
        mock_gdrive.delete_files.return_value = {
            "old-file-id-cdg": True,
            "old-file-id-mp4": True,
        }

        mock_brand_service = Mock()

        with patch("backend.api.routes.jobs.job_manager") as mock_jm, \
             patch("backend.services.dropbox_service.get_dropbox_service", return_value=mock_dropbox), \
             patch("backend.services.gdrive_service.get_gdrive_service", return_value=mock_gdrive), \
             patch("backend.services.brand_code_service.get_brand_code_service", return_value=mock_brand_service):
            mock_jm.get_job.return_value = job
            mock_jm.delete_job.return_value = None

            response = client.post("/api/jobs/test-job-id/cleanup-distribution")

        assert response.status_code == 200
        data = response.json()

        # Should have searched by brand code (fallback path)
        mock_gdrive.find_files_by_brand_code.assert_called_once_with(
            "root-folder-id", "NOMAD-1271"
        )
        # Should have deleted the found files
        mock_gdrive.delete_files.assert_called_once()
        assert data["gdrive"]["status"] == "success"

    def test_falls_back_to_brand_code_search_when_gdrive_files_none(self, client):
        """When gdrive_files not in state_data (old job), search by brand_code."""
        job = _make_job(gdrive_files=None)
        job.state_data = {"brand_code": "NOMAD-1271"}  # No gdrive_files key at all

        mock_dropbox = Mock()
        mock_dropbox.is_configured = True
        mock_dropbox.delete_folder.return_value = True

        mock_gdrive = Mock()
        mock_gdrive.is_configured = True
        mock_gdrive.find_files_by_brand_code.return_value = ["legacy-file-id"]
        mock_gdrive.delete_files.return_value = {"legacy-file-id": True}

        mock_brand_service = Mock()

        with patch("backend.api.routes.jobs.job_manager") as mock_jm, \
             patch("backend.services.dropbox_service.get_dropbox_service", return_value=mock_dropbox), \
             patch("backend.services.gdrive_service.get_gdrive_service", return_value=mock_gdrive), \
             patch("backend.services.brand_code_service.get_brand_code_service", return_value=mock_brand_service):
            mock_jm.get_job.return_value = job
            mock_jm.delete_job.return_value = None

            response = client.post("/api/jobs/test-job-id/cleanup-distribution")

        assert response.status_code == 200
        mock_gdrive.find_files_by_brand_code.assert_called_once()

    def test_reports_skipped_when_no_files_found_by_brand_code(self, client):
        """When brand_code search finds nothing, GDrive status is 'skipped'."""
        job = _make_job(gdrive_files={})

        mock_dropbox = Mock()
        mock_dropbox.is_configured = True
        mock_dropbox.delete_folder.return_value = True

        mock_gdrive = Mock()
        mock_gdrive.is_configured = True
        mock_gdrive.find_files_by_brand_code.return_value = []  # Nothing found

        mock_brand_service = Mock()

        with patch("backend.api.routes.jobs.job_manager") as mock_jm, \
             patch("backend.services.dropbox_service.get_dropbox_service", return_value=mock_dropbox), \
             patch("backend.services.gdrive_service.get_gdrive_service", return_value=mock_gdrive), \
             patch("backend.services.brand_code_service.get_brand_code_service", return_value=mock_brand_service):
            mock_jm.get_job.return_value = job
            mock_jm.delete_job.return_value = None

            response = client.post("/api/jobs/test-job-id/cleanup-distribution")

        assert response.status_code == 200
        data = response.json()
        assert data["gdrive"]["status"] == "skipped"
        assert "no files found" in data["gdrive"]["reason"]


# ─── Brand Code Recycling — Gated on GDrive Success ──────────────────────────

class TestCleanupDistributionBrandCodeRecycling:
    """Brand code is recycled only after BOTH Dropbox AND GDrive are confirmed clean."""

    def test_brand_code_recycled_when_both_dropbox_and_gdrive_cleaned(self, client):
        """Brand code is recycled when Dropbox delete succeeds and GDrive cleanup succeeds."""
        job = _make_job(gdrive_files={"cdg": "file-id"})

        mock_dropbox = Mock()
        mock_dropbox.is_configured = True
        mock_dropbox.delete_folder.return_value = True  # Dropbox success

        mock_gdrive = Mock()
        mock_gdrive.is_configured = True
        mock_gdrive.delete_files.return_value = {"file-id": True}  # GDrive success

        mock_brand_service = Mock()

        with patch("backend.api.routes.jobs.job_manager") as mock_jm, \
             patch("backend.services.dropbox_service.get_dropbox_service", return_value=mock_dropbox), \
             patch("backend.services.gdrive_service.get_gdrive_service", return_value=mock_gdrive), \
             patch("backend.services.brand_code_service.BrandCodeService") as mock_bcs_class, \
             patch("backend.services.brand_code_service.get_brand_code_service", return_value=mock_brand_service):
            mock_jm.get_job.return_value = job
            mock_jm.delete_job.return_value = None
            mock_bcs_class.parse_brand_code.return_value = ("NOMAD", 1271)

            response = client.post("/api/jobs/test-job-id/cleanup-distribution")

        assert response.status_code == 200
        data = response.json()

        # Brand code should be recycled
        mock_brand_service.recycle_brand_code.assert_called_once()
        assert data["dropbox"].get("recycled_brand_code") is True

    def test_brand_code_not_recycled_when_gdrive_cleanup_partial(self, client):
        """Brand code is NOT recycled when GDrive delete only partially succeeded.

        If GDrive still has files with this brand code, recycling would allow a new
        job to get the same brand code, creating a duplicate in the public share.
        """
        job = _make_job(gdrive_files={"mp4": "file-id-mp4", "cdg": "file-id-cdg"})

        mock_dropbox = Mock()
        mock_dropbox.is_configured = True
        mock_dropbox.delete_folder.return_value = True  # Dropbox success

        mock_gdrive = Mock()
        mock_gdrive.is_configured = True
        mock_gdrive.delete_files.return_value = {
            "file-id-mp4": True,
            "file-id-cdg": False,  # CDG file still on GDrive
        }

        mock_brand_service = Mock()

        with patch("backend.api.routes.jobs.job_manager") as mock_jm, \
             patch("backend.services.dropbox_service.get_dropbox_service", return_value=mock_dropbox), \
             patch("backend.services.gdrive_service.get_gdrive_service", return_value=mock_gdrive), \
             patch("backend.services.brand_code_service.get_brand_code_service", return_value=mock_brand_service):
            mock_jm.get_job.return_value = job
            mock_jm.delete_job.return_value = None

            response = client.post("/api/jobs/test-job-id/cleanup-distribution")

        assert response.status_code == 200
        data = response.json()

        # Brand code should NOT be recycled because GDrive still has a file
        mock_brand_service.recycle_brand_code.assert_not_called()
        # recycled_brand_code key should be absent (recycling never attempted)
        assert "recycled_brand_code" not in data.get("dropbox", {})

    def test_brand_code_not_recycled_when_gdrive_not_configured(self, client):
        """Brand code is NOT recycled when GDrive is not configured.

        Without GDrive credentials, we cannot confirm that GDrive was cleaned.
        A previous upload may have succeeded (e.g., different credentials rotation).
        """
        job = _make_job(gdrive_files={"cdg": "file-id"})

        mock_dropbox = Mock()
        mock_dropbox.is_configured = True
        mock_dropbox.delete_folder.return_value = True

        mock_gdrive = Mock()
        mock_gdrive.is_configured = False  # GDrive not configured

        mock_brand_service = Mock()

        with patch("backend.api.routes.jobs.job_manager") as mock_jm, \
             patch("backend.services.dropbox_service.get_dropbox_service", return_value=mock_dropbox), \
             patch("backend.services.gdrive_service.get_gdrive_service", return_value=mock_gdrive), \
             patch("backend.services.brand_code_service.get_brand_code_service", return_value=mock_brand_service):
            mock_jm.get_job.return_value = job
            mock_jm.delete_job.return_value = None

            response = client.post("/api/jobs/test-job-id/cleanup-distribution")

        assert response.status_code == 200

        # Brand code NOT recycled — GDrive might still have files
        mock_brand_service.recycle_brand_code.assert_not_called()

    def test_brand_code_recycled_when_gdrive_finds_nothing_to_delete(self, client):
        """Brand code IS recycled when GDrive search finds nothing (already clean)."""
        job = _make_job(gdrive_files={})  # Empty — no tracked IDs

        mock_dropbox = Mock()
        mock_dropbox.is_configured = True
        mock_dropbox.delete_folder.return_value = True

        mock_gdrive = Mock()
        mock_gdrive.is_configured = True
        mock_gdrive.find_files_by_brand_code.return_value = []  # GDrive already clean

        mock_brand_service = Mock()

        with patch("backend.api.routes.jobs.job_manager") as mock_jm, \
             patch("backend.services.dropbox_service.get_dropbox_service", return_value=mock_dropbox), \
             patch("backend.services.gdrive_service.get_gdrive_service", return_value=mock_gdrive), \
             patch("backend.services.brand_code_service.BrandCodeService") as mock_bcs_class, \
             patch("backend.services.brand_code_service.get_brand_code_service", return_value=mock_brand_service):
            mock_jm.get_job.return_value = job
            mock_jm.delete_job.return_value = None
            mock_bcs_class.parse_brand_code.return_value = ("NOMAD", 1271)

            response = client.post("/api/jobs/test-job-id/cleanup-distribution")

        assert response.status_code == 200
        data = response.json()

        # GDrive was confirmed clean (nothing found), so brand code IS recycled
        mock_brand_service.recycle_brand_code.assert_called_once()
        assert data["dropbox"].get("recycled_brand_code") is True
