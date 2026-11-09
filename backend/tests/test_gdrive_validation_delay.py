"""
Tests for delayed GDrive validation trigger.

The post-job GDrive validation was firing immediately after upload, before E2E
test cleanup could run. This caused false "all clear" reports when the validator
checked sequence gaps while test files still existed in GDrive.

Fix: Use Cloud Tasks to delay the validation by 5 minutes.
"""
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch


class TestGdriveValidationEndpoint:
    """Tests for POST /api/internal/trigger-gdrive-validation."""

    @pytest.fixture
    def client_and_mocks(self):
        """Create TestClient with mocked dependencies."""
        import os
        os.environ.setdefault('ADMIN_TOKENS', 'test-admin-token')

        mock_creds = MagicMock()
        mock_creds.universe_domain = 'googleapis.com'

        mock_job_manager = MagicMock()

        with patch('backend.api.routes.internal.JobManager', return_value=mock_job_manager), \
             patch('backend.services.firestore_service.firestore'), \
             patch('backend.services.storage_service.storage'), \
             patch('google.auth.default', return_value=(mock_creds, 'test-project')):
            from backend.main import app
            from fastapi.testclient import TestClient
            yield TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test-admin-token"}

    def test_endpoint_returns_200(self, client_and_mocks, auth_headers):
        """Test gdrive validation endpoint returns 200 with auth."""
        with patch(
            'backend.services.gdrive_validator_client.trigger_gdrive_validation',
            return_value={"status": "ok", "total_files": 1276}
        ):
            response = client_and_mocks.post(
                "/api/internal/trigger-gdrive-validation",
                headers=auth_headers,
                json={},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"

    def test_endpoint_returns_skipped_when_url_not_set(self, client_and_mocks, auth_headers):
        """Test endpoint returns skipped when GDRIVE_VALIDATOR_URL is not configured."""
        with patch(
            'backend.services.gdrive_validator_client.trigger_gdrive_validation',
            return_value=None
        ):
            response = client_and_mocks.post(
                "/api/internal/trigger-gdrive-validation",
                headers=auth_headers,
                json={},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "skipped"

    def test_endpoint_handles_issues_found(self, client_and_mocks, auth_headers):
        """Test endpoint properly relays issues_found status."""
        with patch(
            'backend.services.gdrive_validator_client.trigger_gdrive_validation',
            return_value={"status": "issues_found", "issues": ["NOMAD-1276 missing"]}
        ):
            response = client_and_mocks.post(
                "/api/internal/trigger-gdrive-validation",
                headers=auth_headers,
                json={},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "issues_found"

    def test_endpoint_handles_exception(self, client_and_mocks, auth_headers):
        """Test endpoint returns error status on exception."""
        with patch(
            'backend.services.gdrive_validator_client.trigger_gdrive_validation',
            side_effect=Exception("Connection refused")
        ):
            response = client_and_mocks.post(
                "/api/internal/trigger-gdrive-validation",
                headers=auth_headers,
                json={},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error"
            assert "Connection refused" in data["message"]


class TestScheduleGdriveValidation:
    """Tests for WorkerService.schedule_gdrive_validation()."""

    def test_skips_when_cloud_tasks_disabled(self):
        """Test validation scheduling is skipped in dev mode (no Cloud Tasks)."""
        import asyncio

        with patch('backend.services.worker_service.get_settings') as mock_settings:
            mock_settings.return_value.enable_cloud_tasks = False
            mock_settings.return_value.google_cloud_project = "test-project"
            mock_settings.return_value.gcp_region = "us-central1"
            mock_settings.return_value.admin_tokens = "test-token"

            from backend.services.worker_service import WorkerService
            service = WorkerService()

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(service.schedule_gdrive_validation())
            finally:
                loop.close()

            # Should return True (success) even though it didn't schedule
            assert result is True

    def test_schedules_with_correct_url(self):
        """Test that validation is scheduled targeting the right endpoint."""
        import asyncio

        mock_tasks_client = MagicMock()
        mock_response = MagicMock()
        mock_response.name = "projects/test/queues/gdrive-validation-queue/tasks/abc123"
        mock_tasks_client.create_task.return_value = mock_response
        mock_tasks_client.queue_path.return_value = "projects/test/locations/us-central1/queues/gdrive-validation-queue"

        with patch('backend.services.worker_service.get_settings') as mock_settings:
            mock_settings.return_value.enable_cloud_tasks = True
            mock_settings.return_value.google_cloud_project = "test-project"
            mock_settings.return_value.gcp_region = "us-central1"
            mock_settings.return_value.admin_tokens = "test-token"
            mock_settings.return_value.cloud_run_url = "https://api.nomadkaraoke.com"

            from backend.services.worker_service import WorkerService
            service = WorkerService()
            # Override the lazy property by setting the private attribute
            service._tasks_client = mock_tasks_client

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(service.schedule_gdrive_validation())
            finally:
                loop.close()

            assert result is True
            mock_tasks_client.create_task.assert_called_once()

            # Verify the task targets the right endpoint
            create_call = mock_tasks_client.create_task.call_args
            task_payload = create_call.kwargs.get('task', {})
            url = task_payload.get('http_request', {}).get('url', '')
            assert 'trigger-gdrive-validation' in url

    def test_returns_false_on_error(self):
        """Test that scheduling failure returns False (non-fatal)."""
        import asyncio

        mock_tasks_client = MagicMock()
        mock_tasks_client.create_task.side_effect = Exception("Queue not found")
        mock_tasks_client.queue_path.return_value = "projects/test/queues/gdrive-validation-queue"

        with patch('backend.services.worker_service.get_settings') as mock_settings:
            mock_settings.return_value.enable_cloud_tasks = True
            mock_settings.return_value.google_cloud_project = "test-project"
            mock_settings.return_value.gcp_region = "us-central1"
            mock_settings.return_value.admin_tokens = "test-token"
            mock_settings.return_value.cloud_run_url = "https://api.nomadkaraoke.com"

            from backend.services.worker_service import WorkerService
            service = WorkerService()
            service._tasks_client = mock_tasks_client

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(service.schedule_gdrive_validation())
            finally:
                loop.close()

            assert result is False


class TestOrchestratorUsesDelayedValidation:
    """Test that the orchestrator uses delayed validation instead of immediate."""

    def test_orchestrator_schedules_delayed_validation(self):
        """Test _trigger_gdrive_validation uses schedule_gdrive_validation."""
        import asyncio

        mock_worker_service = MagicMock()
        mock_worker_service.schedule_gdrive_validation = AsyncMock(return_value=True)

        with patch(
            'backend.services.worker_service.get_worker_service',
            return_value=mock_worker_service
        ):
            from backend.workers.video_worker_orchestrator import VideoWorkerOrchestrator

            # Create a minimal orchestrator instance
            mock_config = MagicMock()
            mock_job_log = MagicMock()
            orchestrator = VideoWorkerOrchestrator.__new__(VideoWorkerOrchestrator)
            orchestrator.config = mock_config
            orchestrator.job_log = mock_job_log
            orchestrator.result = MagicMock()

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(orchestrator._trigger_gdrive_validation())
            finally:
                loop.close()

            mock_worker_service.schedule_gdrive_validation.assert_called_once()
            mock_job_log.info.assert_called_once()
            assert "5 min" in mock_job_log.info.call_args[0][0]

    def test_orchestrator_falls_back_to_immediate_on_failure(self):
        """Test _trigger_gdrive_validation falls back to immediate call if scheduling fails."""
        import asyncio

        mock_worker_service = MagicMock()
        mock_worker_service.schedule_gdrive_validation = AsyncMock(return_value=False)

        mock_validator = MagicMock(return_value={"status": "ok"})

        with patch(
            'backend.services.worker_service.get_worker_service',
            return_value=mock_worker_service
        ), patch(
            'backend.services.gdrive_validator_client.trigger_gdrive_validation',
            mock_validator
        ):
            from backend.workers.video_worker_orchestrator import VideoWorkerOrchestrator

            mock_config = MagicMock()
            mock_job_log = MagicMock()
            orchestrator = VideoWorkerOrchestrator.__new__(VideoWorkerOrchestrator)
            orchestrator.config = mock_config
            orchestrator.job_log = mock_job_log
            orchestrator.result = MagicMock()

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(orchestrator._trigger_gdrive_validation())
            finally:
                loop.close()

            # Should have called the fallback immediate trigger
            mock_validator.assert_called_once()
            # Should have logged a warning about the fallback
            mock_job_log.warning.assert_called_once()

    def test_orchestrator_handles_exception_gracefully(self):
        """Test _trigger_gdrive_validation never crashes the pipeline."""
        import asyncio

        with patch(
            'backend.services.worker_service.get_worker_service',
            side_effect=Exception("Service unavailable")
        ):
            from backend.workers.video_worker_orchestrator import VideoWorkerOrchestrator

            mock_config = MagicMock()
            mock_job_log = MagicMock()
            orchestrator = VideoWorkerOrchestrator.__new__(VideoWorkerOrchestrator)
            orchestrator.config = mock_config
            orchestrator.job_log = mock_job_log
            orchestrator.result = MagicMock()

            loop = asyncio.new_event_loop()
            try:
                # Should not raise - non-fatal
                loop.run_until_complete(orchestrator._trigger_gdrive_validation())
            finally:
                loop.close()

            mock_job_log.warning.assert_called_once()


class TestGdriveValidationConstants:
    """Test that the delay constant is correctly set."""

    def test_delay_is_five_minutes(self):
        """Verify GDRIVE_VALIDATION_DELAY_SECONDS is 300 (5 minutes)."""
        from backend.services.worker_service import GDRIVE_VALIDATION_DELAY_SECONDS
        assert GDRIVE_VALIDATION_DELAY_SECONDS == 300

    def test_queue_is_configured(self):
        """Verify gdrive-validation queue is in WORKER_QUEUES."""
        from backend.services.worker_service import WORKER_QUEUES
        assert "gdrive-validation" in WORKER_QUEUES
        assert WORKER_QUEUES["gdrive-validation"] == "gdrive-validation-queue"

    def test_dispatch_deadline_is_configured(self):
        """Verify gdrive-validation dispatch deadline is set."""
        from backend.services.worker_service import WORKER_DISPATCH_DEADLINES
        assert "gdrive-validation" in WORKER_DISPATCH_DEADLINES
        assert WORKER_DISPATCH_DEADLINES["gdrive-validation"] == 120
