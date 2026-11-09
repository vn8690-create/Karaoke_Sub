"""
Base classes and protocols for the pipeline architecture.

This module defines the interfaces that all pipeline stages must implement,
ensuring consistent behavior across different execution contexts.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from karaoke_gen.pipeline.context import PipelineContext


class StageStatus(str, Enum):
    """Status of a pipeline stage execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """
    Result of a pipeline stage execution.
    
    Contains the outputs produced by the stage, any error information,
    and metadata about the execution.
    """
    status: StageStatus
    outputs: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    duration_seconds: Optional[float] = None
    
    @property
    def success(self) -> bool:
        """Check if the stage completed successfully."""
        return self.status == StageStatus.COMPLETED
    
    @property
    def failed(self) -> bool:
        """Check if the stage failed."""
        return self.status == StageStatus.FAILED


class PipelineStage(ABC):
    """
    Abstract base class for pipeline stages.
    
    Each stage represents a discrete unit of work in the karaoke generation
    pipeline. Stages declare their dependencies (required inputs) and outputs,
    allowing the pipeline executor to validate data flow.
    
    Stages should be stateless - all state is passed through PipelineContext.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique name for this stage.
        
        Used for logging, progress tracking, and output dictionary keys.
        """
        ...
    
    @property
    def required_inputs(self) -> List[str]:
        """
        List of required input keys from previous stages.
        
        Override this to declare dependencies on outputs from other stages.
        The pipeline executor will validate that these keys exist in
        context.stage_outputs before running this stage.
        
        Returns:
            List of required input keys (empty by default)
        """
        return []
    
    @property
    def optional_inputs(self) -> List[str]:
        """
        List of optional input keys from previous stages.
        
        These inputs will be used if available but are not required.
        
        Returns:
            List of optional input keys (empty by default)
        """
        return []
    
    @property
    def output_keys(self) -> List[str]:
        """
        List of output keys this stage produces.
        
        Override this to declare what outputs this stage will add to
        context.stage_outputs. This is used for documentation and
        validation purposes.
        
        Returns:
            List of output keys this stage produces
        """
        return []
    
    def validate_inputs(self, context: "PipelineContext") -> bool:
        """
        Validate that all required inputs are present.
        
        Args:
            context: Pipeline context with stage outputs from previous stages
            
        Returns:
            True if all required inputs are present, False otherwise
        """
        for key in self.required_inputs:
            if key not in context.stage_outputs:
                return False
        return True
    
    def get_missing_inputs(self, context: "PipelineContext") -> List[str]:
        """
        Get list of missing required inputs.
        
        Args:
            context: Pipeline context to check
            
        Returns:
            List of missing input keys
        """
        return [key for key in self.required_inputs if key not in context.stage_outputs]
    
    @abstractmethod
    async def execute(self, context: "PipelineContext") -> StageResult:
        """
        Execute the stage.
        
        This is the main entry point for stage execution. Implementations
        should:
        1. Read inputs from context.stage_outputs (using keys from required_inputs)
        2. Perform the stage's work
        3. Return a StageResult with outputs (using keys from output_keys)
        
        Args:
            context: Pipeline context with all job parameters and stage outputs
            
        Returns:
            StageResult containing outputs or error information
        """
        ...
    
    async def cleanup(self, context: "PipelineContext") -> None:
        """
        Clean up any resources after stage execution.
        
        Override this to perform cleanup operations like removing
        temporary files. Called by the executor after stage completion.
        
        Args:
            context: Pipeline context
        """
        pass
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name})>"


class PipelineExecutor(ABC):
    """
    Abstract base class for pipeline executors.
    
    Executors are responsible for running pipeline stages in a specific
    context (local in-process, remote via API, etc.).
    """
    
    @abstractmethod
    async def run_stage(
        self,
        stage: PipelineStage,
        context: "PipelineContext",
    ) -> StageResult:
        """
        Execute a single pipeline stage.
        
        Args:
            stage: The stage to execute
            context: Pipeline context
            
        Returns:
            Result of stage execution
        """
        ...
    
    @abstractmethod
    async def run_pipeline(
        self,
        stages: List[PipelineStage],
        context: "PipelineContext",
    ) -> Dict[str, StageResult]:
        """
        Execute a full pipeline of stages.
        
        Args:
            stages: List of stages to execute in order
            context: Pipeline context
            
        Returns:
            Dictionary mapping stage names to their results
        """
        ...
