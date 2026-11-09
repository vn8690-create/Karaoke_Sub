"""
Unit tests for the annotations endpoint in review.py.

Tests the actual storage logic (not the stub version).
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_storage():
    """Create a mock StorageService that tracks calls."""
    storage = MagicMock()
    storage.upload_json = MagicMock()
    # Default: no existing annotations
    storage.download_json = MagicMock(side_effect=Exception("Not found"))
    return storage


@pytest.fixture
def client(mock_storage):
    """Create TestClient with mocked dependencies for review routes."""
    mock_creds = MagicMock()
    mock_creds.universe_domain = 'googleapis.com'

    mock_jm = MagicMock()
    mock_jm.get_job.return_value = MagicMock(
        job_id="test-job",
        status="in_review",
        review_token="test-review-token"
    )

    def mock_jm_factory(*args, **kwargs):
        return mock_jm

    # Override review auth to bypass complex auth chain
    async def fake_review_auth():
        return ("test-job", "full")

    with patch('backend.api.routes.jobs.job_manager', mock_jm), \
         patch('backend.services.job_manager.JobManager', mock_jm_factory), \
         patch('backend.services.firestore_service.firestore'), \
         patch('backend.services.storage_service.storage'), \
         patch('google.auth.default', return_value=(mock_creds, 'test-project')):

        from backend.main import app
        from backend.api.dependencies import require_review_auth

        # Override review auth dependency (must use the same function object used by routes)
        app.dependency_overrides[require_review_auth] = fake_review_auth

        # Patch StorageService inside the review module
        with patch('backend.api.routes.review.StorageService', return_value=mock_storage):
            yield TestClient(app)

        app.dependency_overrides.clear()


class TestSubmitAnnotations:
    """Tests for POST /api/review/{job_id}/v1/annotations."""

    def test_submit_single_annotation(self, client, mock_storage):
        """Test submitting a single annotation stores to GCS."""
        annotation = {"annotation_type": "SOUND_ALIKE", "original_text": "helo", "corrected_text": "hello"}
        response = client.post("/api/review/test-job/v1/annotations", json=annotation)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["saved_count"] == 1

    def test_submit_batch_annotations(self, client, mock_storage):
        """Test submitting a batch of annotations."""
        payload = {
            "annotations": [
                {"annotation_type": "SOUND_ALIKE", "original_text": "a"},
                {"annotation_type": "EXTRA_WORDS", "original_text": "b"},
            ]
        }
        response = client.post("/api/review/test-job/v1/annotations", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["saved_count"] == 2
        assert data["total_count"] == 2

    def test_annotations_stored_to_correct_gcs_path(self, client, mock_storage):
        """Test annotations are stored at jobs/{job_id}/lyrics/annotations.json."""
        client.post(
            "/api/review/test-job/v1/annotations",
            json={"annotation_type": "MANUAL_EDIT"}
        )
        mock_storage.upload_json.assert_called_once()
        gcs_path = mock_storage.upload_json.call_args[0][0]
        assert gcs_path == "jobs/test-job/lyrics/annotations.json"

    def test_annotations_merged_with_existing(self, client, mock_storage):
        """Test new annotations are merged with existing ones."""
        # Set up existing annotations
        mock_storage.download_json.side_effect = None
        mock_storage.download_json.return_value = {
            "annotations": [{"annotation_type": "SOUND_ALIKE", "original_text": "existing"}]
        }

        payload = {"annotations": [{"annotation_type": "EXTRA_WORDS", "original_text": "new"}]}
        response = client.post("/api/review/test-job/v1/annotations", json=payload)

        data = response.json()
        assert data["saved_count"] == 1
        assert data["total_count"] == 2  # 1 existing + 1 new

        # Verify merged data was uploaded
        uploaded_data = mock_storage.upload_json.call_args[0][1]
        assert len(uploaded_data["annotations"]) == 2

    def test_annotations_fresh_when_no_existing(self, client, mock_storage):
        """Test annotations start fresh when no existing file."""
        payload = {"annotations": [{"annotation_type": "NO_ERROR"}]}
        response = client.post("/api/review/test-job/v1/annotations", json=payload)
        assert response.json()["total_count"] == 1
