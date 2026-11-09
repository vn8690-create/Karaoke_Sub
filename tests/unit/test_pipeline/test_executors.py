"""
Tests for pipeline executors.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestLocalExecutor:
    """Tests for LocalExecutor."""

    def test_executor_imports(self):
        """Test that the executor can be imported."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor, create_local_executor
        assert LocalExecutor is not None
        assert create_local_executor is not None

    def test_create_executor(self):
        """Test creating an executor."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor
        
        executor = LocalExecutor()
        assert executor is not None
        assert executor.stop_on_failure is True

    def test_create_executor_with_options(self):
        """Test creating an executor with options."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor
        import logging
        
        logger = logging.getLogger("test")
        executor = LocalExecutor(logger=logger, stop_on_failure=False)
        
        assert executor.logger is logger
        assert executor.stop_on_failure is False

    def test_factory_function(self):
        """Test the factory function."""
        from karaoke_gen.pipeline.executors.local import create_local_executor
        
        executor = create_local_executor()
        assert executor is not None

    @pytest.mark.asyncio
    async def test_run_stage_validates_inputs(self):
        """Test that run_stage validates inputs."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        class TestStage(PipelineStage):
            @property
            def name(self):
                return "test"
            
            @property
            def required_inputs(self):
                return ["missing_stage"]
            
            async def execute(self, context):
                return StageResult(status=StageStatus.COMPLETED)
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        executor = LocalExecutor()
        result = await executor.run_stage(TestStage(), context)
        
        assert result.failed is True
        assert "missing required inputs" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_run_stage_success(self):
        """Test running a successful stage."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        class TestStage(PipelineStage):
            @property
            def name(self):
                return "test"
            
            async def execute(self, context):
                return StageResult(
                    status=StageStatus.COMPLETED,
                    outputs={"result": "success"},
                )
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        executor = LocalExecutor()
        result = await executor.run_stage(TestStage(), context)
        
        assert result.success is True
        assert result.outputs == {"result": "success"}
        # Outputs should be stored in context
        assert context.stage_outputs.get("test") == {"result": "success"}

    @pytest.mark.asyncio
    async def test_run_pipeline_executes_stages_in_order(self):
        """Test that run_pipeline executes stages in order."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        execution_order = []
        
        class Stage1(PipelineStage):
            @property
            def name(self):
                return "stage1"
            
            async def execute(self, context):
                execution_order.append("stage1")
                return StageResult(status=StageStatus.COMPLETED)
        
        class Stage2(PipelineStage):
            @property
            def name(self):
                return "stage2"
            
            async def execute(self, context):
                execution_order.append("stage2")
                return StageResult(status=StageStatus.COMPLETED)
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        executor = LocalExecutor()
        results = await executor.run_pipeline([Stage1(), Stage2()], context)
        
        assert execution_order == ["stage1", "stage2"]
        assert results["stage1"].success
        assert results["stage2"].success

    @pytest.mark.asyncio
    async def test_run_pipeline_stops_on_failure(self):
        """Test that run_pipeline stops on failure when configured."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        execution_order = []
        
        class Stage1(PipelineStage):
            @property
            def name(self):
                return "stage1"
            
            async def execute(self, context):
                execution_order.append("stage1")
                return StageResult(
                    status=StageStatus.FAILED,
                    error_message="Stage 1 failed",
                )
        
        class Stage2(PipelineStage):
            @property
            def name(self):
                return "stage2"
            
            async def execute(self, context):
                execution_order.append("stage2")
                return StageResult(status=StageStatus.COMPLETED)
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        executor = LocalExecutor(stop_on_failure=True)
        results = await executor.run_pipeline([Stage1(), Stage2()], context)
        
        # Stage2 should not have executed
        assert execution_order == ["stage1"]
        assert results["stage1"].failed
        assert "stage2" not in results


class TestRemoteExecutor:
    """Tests for RemoteExecutor."""

    def test_executor_imports(self):
        """Test that the executor can be imported."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor, create_remote_executor
        assert RemoteExecutor is not None
        assert create_remote_executor is not None

    def test_create_executor(self):
        """Test creating a remote executor."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        
        executor = RemoteExecutor(
            service_url="https://api.example.com",
            auth_token="test-token",
        )
        
        assert executor.service_url == "https://api.example.com"
        assert executor.auth_token == "test-token"

    def test_create_executor_strips_trailing_slash(self):
        """Test that trailing slash is stripped from service URL."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        
        executor = RemoteExecutor(service_url="https://api.example.com/")
        assert executor.service_url == "https://api.example.com"

    def test_factory_function(self):
        """Test the factory function."""
        from karaoke_gen.pipeline.executors.remote import create_remote_executor
        
        executor = create_remote_executor(
            service_url="https://api.example.com",
            auth_token="test-token",
        )
        
        assert executor is not None
        assert executor.service_url == "https://api.example.com"

    def test_executor_default_poll_interval(self):
        """Test default poll interval."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        
        executor = RemoteExecutor(service_url="https://api.example.com")
        assert executor.poll_interval == 5

    def test_executor_custom_poll_interval(self):
        """Test custom poll interval."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        
        executor = RemoteExecutor(
            service_url="https://api.example.com",
            poll_interval=10,
        )
        assert executor.poll_interval == 10

    def test_session_property_creates_session(self):
        """Test that session property creates a session."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        import requests
        
        executor = RemoteExecutor(
            service_url="https://api.example.com",
            auth_token="test-token",
        )
        
        session = executor.session
        assert session is not None
        assert isinstance(session, requests.Session)

    def test_session_includes_auth_header(self):
        """Test that session includes authorization header."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        
        executor = RemoteExecutor(
            service_url="https://api.example.com",
            auth_token="test-token",
        )
        
        session = executor.session
        assert 'Authorization' in session.headers
        assert session.headers['Authorization'] == 'Bearer test-token'

    def test_session_cached(self):
        """Test that session is cached."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        
        executor = RemoteExecutor(service_url="https://api.example.com")
        
        session1 = executor.session
        session2 = executor.session
        assert session1 is session2

    @pytest.mark.asyncio
    async def test_run_stage_returns_skipped(self):
        """Test that run_stage returns SKIPPED (handled by backend)."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        class TestStage(PipelineStage):
            @property
            def name(self):
                return "test"
            
            async def execute(self, context):
                return StageResult(status=StageStatus.COMPLETED)
        
        executor = RemoteExecutor(service_url="https://api.example.com")
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        result = await executor.run_stage(TestStage(), context)
        
        # Remote executor doesn't run stages directly
        assert result.status == StageStatus.SKIPPED

    def test_get_job_status(self):
        """Test get_job_status method."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        
        executor = RemoteExecutor(service_url="https://api.example.com")
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "complete", "progress": 100}
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        executor._session = mock_session
        
        result = executor.get_job_status("test-job-123")
        
        assert result["status"] == "complete"
        assert result["progress"] == 100

    @pytest.mark.asyncio
    async def test_run_pipeline_success(self):
        """Test run_pipeline with successful job completion."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        class TestStage(PipelineStage):
            @property
            def name(self):
                return "test"
            
            async def execute(self, context):
                return StageResult(status=StageStatus.COMPLETED)
        
        executor = RemoteExecutor(service_url="https://api.example.com")
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        # Mock _submit_job and _monitor_job
        with patch.object(executor, '_submit_job', new_callable=AsyncMock, return_value="job-123"):
            with patch.object(executor, '_monitor_job', new_callable=AsyncMock, return_value="complete"):
                results = await executor.run_pipeline([TestStage()], context)
        
        assert "test" in results
        assert results["test"].status == StageStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_pipeline_failure(self):
        """Test run_pipeline with job failure."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        class TestStage(PipelineStage):
            @property
            def name(self):
                return "test"
            
            async def execute(self, context):
                return StageResult(status=StageStatus.COMPLETED)
        
        executor = RemoteExecutor(service_url="https://api.example.com")
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        # Mock _submit_job and _monitor_job to simulate failure
        with patch.object(executor, '_submit_job', new_callable=AsyncMock, return_value="job-123"):
            with patch.object(executor, '_monitor_job', new_callable=AsyncMock, return_value="failed"):
                results = await executor.run_pipeline([TestStage()], context)
        
        assert "test" in results
        assert results["test"].status == StageStatus.FAILED
        assert "failed" in results["test"].error_message

    @pytest.mark.asyncio
    async def test_run_pipeline_exception(self):
        """Test run_pipeline handles exceptions."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        class TestStage(PipelineStage):
            @property
            def name(self):
                return "test"
            
            async def execute(self, context):
                return StageResult(status=StageStatus.COMPLETED)
        
        executor = RemoteExecutor(service_url="https://api.example.com")
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        # Mock _submit_job to raise exception
        with patch.object(executor, '_submit_job', new_callable=AsyncMock, side_effect=Exception("Connection error")):
            results = await executor.run_pipeline([TestStage()], context)
        
        assert "test" in results
        assert results["test"].status == StageStatus.FAILED
        assert "Connection error" in results["test"].error_message

    @pytest.mark.asyncio
    async def test_submit_job(self):
        """Test _submit_job method."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        from karaoke_gen.pipeline.context import PipelineContext
        import tempfile
        import os
        
        executor = RemoteExecutor(service_url="https://api.example.com")
        
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as f:
            f.write(b"fake audio data")
            audio_path = f.name
        
        try:
            context = PipelineContext(
                job_id="test",
                artist="Artist",
                title="Title",
                input_audio_path=audio_path,
                output_dir="/output",
                enable_cdg=True,
                enable_txt=True,
            )
            
            mock_response = MagicMock()
            mock_response.json.return_value = {"job_id": "job-123"}
            
            mock_session = MagicMock()
            mock_session.post.return_value = mock_response
            executor._session = mock_session
            
            result = await executor._submit_job(context)
            
            assert result == "job-123"
            mock_session.post.assert_called_once()
        finally:
            os.unlink(audio_path)

    @pytest.mark.asyncio
    async def test_submit_job_with_optional_params(self):
        """Test _submit_job with optional parameters."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        from karaoke_gen.pipeline.context import PipelineContext
        import tempfile
        import os
        
        executor = RemoteExecutor(service_url="https://api.example.com")
        
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as f:
            f.write(b"fake audio data")
            audio_path = f.name
        
        try:
            context = PipelineContext(
                job_id="test",
                artist="Artist",
                title="Title",
                input_audio_path=audio_path,
                output_dir="/output",
                brand_prefix="TestBrand",
                discord_webhook_url="https://discord.com/webhook",
                enable_youtube_upload=True,
                dropbox_path="/dropbox/path",
                gdrive_folder_id="folder123",
            )
            
            mock_response = MagicMock()
            mock_response.json.return_value = {"job_id": "job-456"}
            
            mock_session = MagicMock()
            mock_session.post.return_value = mock_response
            executor._session = mock_session
            
            result = await executor._submit_job(context)
            
            assert result == "job-456"
            # Check that optional params were included
            call_args = mock_session.post.call_args
            data = call_args.kwargs.get('data') or call_args[1].get('data')
            assert data['brand_prefix'] == "TestBrand"
        finally:
            os.unlink(audio_path)

    @pytest.mark.asyncio
    async def test_monitor_job_complete(self):
        """Test _monitor_job until job completes."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        from karaoke_gen.pipeline.context import PipelineContext
        
        executor = RemoteExecutor(service_url="https://api.example.com", poll_interval=0.01)
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        # Simulate job progression
        call_count = [0]
        def mock_get(*args, **kwargs):
            call_count[0] += 1
            mock_response = MagicMock()
            if call_count[0] < 3:
                mock_response.json.return_value = {"status": "processing", "progress": 50}
            else:
                mock_response.json.return_value = {"status": "complete", "progress": 100}
            return mock_response
        
        mock_session = MagicMock()
        mock_session.get.side_effect = mock_get
        executor._session = mock_session
        
        result = await executor._monitor_job("job-123", context)
        
        assert result == "complete"

    @pytest.mark.asyncio
    async def test_monitor_job_handles_error(self):
        """Test _monitor_job handles polling errors gracefully."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        from karaoke_gen.pipeline.context import PipelineContext
        
        executor = RemoteExecutor(service_url="https://api.example.com", poll_interval=0.01)
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        # Simulate error then success
        call_count = [0]
        def mock_get(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Network error")
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": "complete", "progress": 100}
            return mock_response
        
        mock_session = MagicMock()
        mock_session.get.side_effect = mock_get
        executor._session = mock_session
        
        result = await executor._monitor_job("job-123", context)
        
        assert result == "complete"


class TestExecutorModuleExports:
    """Tests for module exports."""

    def test_executors_init_exports(self):
        """Test that executors __init__ exports all executors."""
        from karaoke_gen.pipeline.executors import (
            LocalExecutor,
            RemoteExecutor,
            create_local_executor,
            create_remote_executor,
        )
        
        assert LocalExecutor is not None
        assert RemoteExecutor is not None
        assert create_local_executor is not None
        assert create_remote_executor is not None
