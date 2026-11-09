"""
Remote pipeline executor.

This executor runs pipeline stages via the backend API,
suitable for the remote CLI where processing happens in the cloud.

Note: This is a placeholder implementation. The actual remote
execution is handled by the existing backend workers. This executor
provides a compatible interface for potential future unified
pipeline execution.
"""
import logging
import time
from typing import Any, Dict, List, Optional

from karaoke_gen.pipeline.base import PipelineExecutor, PipelineStage, StageResult, StageStatus
from karaoke_gen.pipeline.context import PipelineContext


class RemoteExecutor(PipelineExecutor):
    """
    Runs pipeline stages via backend API.
    
    This executor is used by the remote CLI (karaoke-gen-remote) to
    submit jobs to the cloud backend and monitor their progress.
    
    Note: The current implementation is a compatibility layer.
    The actual processing is handled by the existing backend workers,
    not by executing PipelineStage instances remotely.
    """
    
    def __init__(
        self,
        service_url: str,
        auth_token: Optional[str] = None,
        logger: logging.Logger = None,
        poll_interval: int = 5,
    ):
        """
        Initialize the remote executor.
        
        Args:
            service_url: Backend service URL
            auth_token: Authentication token
            logger: Logger instance
            poll_interval: Seconds between status polls
        """
        self.service_url = service_url.rstrip('/')
        self.auth_token = auth_token
        self.logger = logger or logging.getLogger(__name__)
        self.poll_interval = poll_interval
        self._session = None
    
    @property
    def session(self):
        """Get or create HTTP session."""
        if self._session is None:
            import requests
            self._session = requests.Session()
            if self.auth_token:
                self._session.headers['Authorization'] = f'Bearer {self.auth_token}'
        return self._session
    
    async def run_stage(
        self,
        stage: PipelineStage,
        context: PipelineContext,
    ) -> StageResult:
        """
        Execute a single pipeline stage via backend.
        
        Note: This is a placeholder. The backend handles stage
        execution internally through its worker system.
        
        Args:
            stage: The stage to execute
            context: Pipeline context
            
        Returns:
            Result of stage execution
        """
        self.logger.warning(
            f"RemoteExecutor.run_stage called for {stage.name}. "
            "Remote execution is handled by backend workers, not via this interface."
        )
        
        return StageResult(
            status=StageStatus.SKIPPED,
            error_message="Remote execution handled by backend workers",
        )
    
    async def run_pipeline(
        self,
        stages: List[PipelineStage],
        context: PipelineContext,
    ) -> Dict[str, StageResult]:
        """
        Execute a full pipeline via backend.
        
        This submits a job to the backend and monitors its progress.
        The backend handles individual stage execution through its
        worker system.
        
        Args:
            stages: List of stages (used for validation only)
            context: Pipeline context with job parameters
            
        Returns:
            Dictionary mapping stage names to their results
        """
        results: Dict[str, StageResult] = {}
        
        try:
            # Submit job to backend
            job_id = await self._submit_job(context)
            context.log("INFO", f"Job submitted: {job_id}")
            
            # Monitor job progress
            final_status = await self._monitor_job(job_id, context)
            
            # Build results based on final status
            if final_status == "complete":
                # Mark all stages as completed
                for stage in stages:
                    results[stage.name] = StageResult(status=StageStatus.COMPLETED)
            else:
                # Mark stages based on where failure occurred
                for stage in stages:
                    results[stage.name] = StageResult(
                        status=StageStatus.FAILED,
                        error_message=f"Job ended with status: {final_status}",
                    )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Remote pipeline execution failed: {e}")
            for stage in stages:
                results[stage.name] = StageResult(
                    status=StageStatus.FAILED,
                    error_message=str(e),
                )
            return results
    
    async def _submit_job(self, context: PipelineContext) -> str:
        """
        Submit a job to the backend.
        
        Args:
            context: Pipeline context with job parameters
            
        Returns:
            Job ID
        """
        import os
        
        # Build form data
        data = {
            'artist': context.artist,
            'title': context.title,
            'enable_cdg': str(context.enable_cdg).lower(),
            'enable_txt': str(context.enable_txt).lower(),
        }
        
        if context.brand_prefix:
            data['brand_prefix'] = context.brand_prefix
        if context.discord_webhook_url:
            data['discord_webhook_url'] = context.discord_webhook_url
        if context.enable_youtube_upload:
            data['enable_youtube_upload'] = str(context.enable_youtube_upload).lower()
        if context.dropbox_path:
            data['dropbox_path'] = context.dropbox_path
        if context.gdrive_folder_id:
            data['gdrive_folder_id'] = context.gdrive_folder_id
        
        # Upload audio file
        files = {}
        if os.path.isfile(context.input_audio_path):
            files['file'] = (
                os.path.basename(context.input_audio_path),
                open(context.input_audio_path, 'rb'),
            )
        
        try:
            response = self.session.post(
                f"{self.service_url}/api/jobs/upload",
                data=data,
                files=files,
            )
            response.raise_for_status()
            result = response.json()
            return result['job_id']
        finally:
            # Close file handles
            for name, (filename, fh) in files.items():
                fh.close()
    
    async def _monitor_job(self, job_id: str, context: PipelineContext) -> str:
        """
        Monitor job progress until completion.
        
        Args:
            job_id: Job ID to monitor
            context: Pipeline context for progress updates
            
        Returns:
            Final job status
        """
        import asyncio
        
        while True:
            try:
                response = self.session.get(f"{self.service_url}/api/jobs/{job_id}")
                response.raise_for_status()
                job_data = response.json()
                
                status = job_data.get('status', 'unknown')
                progress = job_data.get('progress', 0)
                
                context.update_progress(status, progress, f"Status: {status}")
                
                # Check for terminal states
                if status in ['complete', 'failed', 'cancelled', 'error']:
                    return status
                
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                self.logger.warning(f"Error polling job status: {e}")
                await asyncio.sleep(self.poll_interval)
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get current job status.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job status data
        """
        response = self.session.get(f"{self.service_url}/api/jobs/{job_id}")
        response.raise_for_status()
        return response.json()


def create_remote_executor(
    service_url: str,
    auth_token: Optional[str] = None,
    logger: logging.Logger = None,
) -> RemoteExecutor:
    """Factory function to create a RemoteExecutor."""
    return RemoteExecutor(
        service_url=service_url,
        auth_token=auth_token,
        logger=logger,
    )
