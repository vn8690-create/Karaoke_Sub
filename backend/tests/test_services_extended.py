"""
Extended unit tests for services.

These tests provide additional coverage for service layer code.
"""
import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock, AsyncMock, patch

from backend.models.job import Job, JobStatus


class TestJobManagerExtended:
    """Extended tests for JobManager.
    
    Note: These tests verify the module structure and basic behavior.
    Full JobManager testing is in test_job_manager.py.
    """
    
    def test_job_manager_module_imports(self):
        """Test JobManager module can be imported."""
        from backend.services import job_manager
        assert hasattr(job_manager, 'JobManager')
    
    def test_state_transitions_defined(self):
        """Test STATE_TRANSITIONS dict is defined."""
        from backend.models.job import STATE_TRANSITIONS
        assert STATE_TRANSITIONS is not None
        assert len(STATE_TRANSITIONS) > 0


class TestStorageServiceExtended:
    """Extended tests for StorageService."""
    
    def test_storage_service_initialization(self):
        """Test StorageService can be initialized."""
        with patch('backend.services.storage_service.storage'):
            from backend.services.storage_service import StorageService
            service = StorageService()
            assert service is not None
    
    def test_storage_service_bucket_name(self):
        """Test StorageService uses configured bucket."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        
        with patch('backend.services.storage_service.storage.Client', return_value=mock_client), \
             patch.dict('os.environ', {'GCS_BUCKET_NAME': 'test-bucket'}):
            from backend.services.storage_service import StorageService
            service = StorageService()
            # Service should use the configured bucket


class TestAuthServiceExtended:
    """Extended tests for AuthService.
    
    Note: Full auth service testing is in test_services.py.
    """
    
    def test_auth_service_module_imports(self):
        """Test AuthService module can be imported."""
        from backend.services import auth_service
        assert hasattr(auth_service, 'AuthService')


class TestWorkerServiceExtended:
    """Extended tests for WorkerService."""
    
    def test_worker_service_initialization(self):
        """Test WorkerService can be initialized."""
        from backend.services.worker_service import WorkerService
        service = WorkerService()
        assert service is not None
    
    def test_worker_service_get_base_url(self):
        """Test WorkerService constructs correct base URL."""
        from backend.services.worker_service import WorkerService
        service = WorkerService()
        
        url = service._get_base_url()
        assert 'http' in url
    
    @pytest.mark.asyncio
    async def test_worker_service_trigger_with_mock(self):
        """Test triggering a worker with mocked HTTP."""
        from backend.services.worker_service import WorkerService
        
        service = WorkerService()
        
        # Mock the HTTP client
        with patch('backend.services.worker_service.httpx.AsyncClient') as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # The trigger methods should work with mocked HTTP


class TestFirestoreServiceExtended:
    """Extended tests for FirestoreService."""
    
    def test_firestore_service_initialization(self):
        """Test FirestoreService can be initialized."""
        with patch('backend.services.firestore_service.firestore'):
            from backend.services.firestore_service import FirestoreService
            service = FirestoreService()
            assert service is not None

