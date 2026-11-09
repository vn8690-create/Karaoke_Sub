"""
Local pipeline executor.

This executor runs pipeline stages directly in-process,
suitable for CLI usage where all processing happens locally.
"""
import logging
import time
from typing import Dict, List

from karaoke_gen.pipeline.base import PipelineExecutor, PipelineStage, StageResult, StageStatus
from karaoke_gen.pipeline.context import PipelineContext


class LocalExecutor(PipelineExecutor):
    """
    Runs pipeline stages directly in-process.
    
    This executor is used by the local CLI (karaoke-gen) to run
    all processing stages sequentially on the local machine.
    """
    
    def __init__(
        self,
        logger: logging.Logger = None,
        stop_on_failure: bool = True,
    ):
        """
        Initialize the local executor.
        
        Args:
            logger: Logger instance
            stop_on_failure: If True, stop pipeline on first failure
        """
        self.logger = logger or logging.getLogger(__name__)
        self.stop_on_failure = stop_on_failure
    
    async def run_stage(
        self,
        stage: PipelineStage,
        context: PipelineContext,
    ) -> StageResult:
        """
        Execute a single pipeline stage.
        
        Args:
            stage: The stage to execute
            context: Pipeline context
            
        Returns:
            Result of stage execution
        """
        self.logger.info(f"Starting stage: {stage.name}")
        context.update_progress(stage.name, 0, f"Starting {stage.name}")
        
        # Validate inputs
        if not stage.validate_inputs(context):
            missing = stage.get_missing_inputs(context)
            error_msg = f"Stage {stage.name} missing required inputs: {missing}"
            self.logger.error(error_msg)
            return StageResult(
                status=StageStatus.FAILED,
                error_message=error_msg,
            )
        
        start_time = time.time()
        
        try:
            # Execute the stage
            result = await stage.execute(context)
            
            # Store outputs in context
            if result.success and result.outputs:
                context.set_stage_output(stage.name, result.outputs)
            
            # Log result
            duration = time.time() - start_time
            if result.success:
                self.logger.info(f"Stage {stage.name} completed in {duration:.1f}s")
            elif result.status == StageStatus.SKIPPED:
                self.logger.info(f"Stage {stage.name} skipped")
            else:
                self.logger.error(f"Stage {stage.name} failed: {result.error_message}")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Stage {stage.name} raised exception: {e}", exc_info=True)
            return StageResult(
                status=StageStatus.FAILED,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
                duration_seconds=duration,
            )
        finally:
            # Run cleanup
            try:
                await stage.cleanup(context)
            except Exception as e:
                self.logger.warning(f"Stage {stage.name} cleanup failed: {e}")
    
    async def run_pipeline(
        self,
        stages: List[PipelineStage],
        context: PipelineContext,
    ) -> Dict[str, StageResult]:
        """
        Execute a full pipeline of stages.
        
        Runs stages sequentially in order, stopping on failure
        if stop_on_failure is True.
        
        Args:
            stages: List of stages to execute in order
            context: Pipeline context
            
        Returns:
            Dictionary mapping stage names to their results
        """
        results: Dict[str, StageResult] = {}
        
        self.logger.info(f"Starting pipeline with {len(stages)} stages")
        pipeline_start = time.time()
        
        for i, stage in enumerate(stages):
            self.logger.info(f"Running stage {i+1}/{len(stages)}: {stage.name}")
            
            # Calculate overall progress
            base_progress = int((i / len(stages)) * 100)
            context.update_progress(stage.name, base_progress, f"Starting {stage.name}")
            
            # Run the stage
            result = await self.run_stage(stage, context)
            results[stage.name] = result
            
            # Check for failure
            if result.failed and self.stop_on_failure:
                self.logger.error(f"Pipeline stopped due to failure in stage: {stage.name}")
                break
        
        pipeline_duration = time.time() - pipeline_start
        
        # Count results
        completed = sum(1 for r in results.values() if r.status == StageStatus.COMPLETED)
        failed = sum(1 for r in results.values() if r.status == StageStatus.FAILED)
        skipped = sum(1 for r in results.values() if r.status == StageStatus.SKIPPED)
        
        self.logger.info(
            f"Pipeline completed in {pipeline_duration:.1f}s: "
            f"{completed} completed, {failed} failed, {skipped} skipped"
        )
        
        return results


def create_local_executor(logger: logging.Logger = None) -> LocalExecutor:
    """Factory function to create a LocalExecutor."""
    return LocalExecutor(logger=logger)
