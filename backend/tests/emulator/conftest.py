"""
Fixtures for emulator integration tests.

These tests use REAL Firestore and GCS emulators, so we DON'T mock google.cloud modules.
Run with: scripts/run-emulator-tests.sh
"""
import pytest
import os
import requests
from unittest.mock import AsyncMock, patch


def emulators_running() -> bool:
    """Check if GCP emulators are running."""
    try:
        # Check Firestore emulator
        requests.get("http://127.0.0.1:8080", timeout=1)
        # Check GCS emulator
        requests.get("http://127.0.0.1:4443", timeout=1)
        return True
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False


# Skip all tests in this module if emulators aren't running
pytestmark = pytest.mark.skipif(
    not emulators_running(),
    reason="GCP emulators not running. Start with: scripts/start-emulators.sh"
)

# Set emulator environment variables (use 127.0.0.1 to force IPv4)
os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
os.environ["STORAGE_EMULATOR_HOST"] = "http://127.0.0.1:4443"
os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
os.environ["GCS_BUCKET_NAME"] = "test-bucket"
os.environ["FIRESTORE_COLLECTION"] = "test-jobs"
os.environ["ENVIRONMENT"] = "test"
os.environ["ADMIN_TOKENS"] = "test-admin-token"

# Only import app if emulators are running
if emulators_running():
    from unittest.mock import Mock

    # Mock theme service BEFORE importing app to ensure all jobs get theme_id="nomad"
    _mock_theme_service = Mock()
    _mock_theme_service.get_default_theme_id.return_value = "nomad"
    _mock_theme_service.get_theme.return_value = None

    # Apply patch at module load time (before app imports the service)
    _theme_patches = [
        patch("backend.services.theme_service.get_theme_service", return_value=_mock_theme_service),
        patch("backend.api.routes.audio_search.get_theme_service", return_value=_mock_theme_service),
        patch("backend.api.routes.file_upload.get_theme_service", return_value=_mock_theme_service),
        patch("backend.api.routes.users.get_theme_service", return_value=_mock_theme_service),
        patch("backend.api.routes.jobs.get_theme_service", return_value=_mock_theme_service),
    ]
    for p in _theme_patches:
        p.start()

    from fastapi.testclient import TestClient
    from backend.main import app
else:
    TestClient = None
    app = None


@pytest.fixture(scope="session", autouse=True)
def setup_gcs_bucket():
    """Create GCS bucket in emulator before all tests."""
    try:
        response = requests.post(
            "http://127.0.0.1:4443/storage/v1/b",
            json={"name": "test-bucket"},
            params={"project": "test-project"},
            timeout=5
        )
        if response.status_code in [200, 409]:
            print("✅ GCS bucket 'test-bucket' ready in emulator")
    except Exception as e:
        print(f"⚠️  GCS bucket setup failed: {e}")
    yield


@pytest.fixture(scope="session")
def mock_worker_service():
    """Mock worker service to prevent background tasks."""
    with patch("backend.api.routes.jobs.worker_service") as mock:
        mock.trigger_audio_worker = AsyncMock(return_value=True)
        mock.trigger_lyrics_worker = AsyncMock(return_value=True)
        mock.trigger_screens_worker = AsyncMock(return_value=True)
        mock.trigger_video_worker = AsyncMock(return_value=True)
        yield mock


@pytest.fixture(scope="session")
def client(mock_worker_service):
    """Create FastAPI test client with mocked workers.

    Theme service is mocked at module load time (see above).
    """
    with patch("backend.api.routes.file_upload.worker_service", mock_worker_service):
        return TestClient(app)


@pytest.fixture
def auth_headers():
    """Auth headers for testing."""
    return {"Authorization": "Bearer test-admin-token"}

