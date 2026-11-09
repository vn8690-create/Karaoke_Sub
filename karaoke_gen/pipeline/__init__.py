"""
Shared pipeline architecture for karaoke-gen.

This module provides a unified pipeline abstraction that can be executed
either locally (in-process) or remotely (via backend workers).

The pipeline consists of stages:
- Separation: Audio separation into stems
- Transcription: Lyrics transcription and synchronization
- Screens: Title and end screen generation
- Render: Video rendering with synchronized lyrics
- Finalize: Encoding, packaging, and distribution

Each stage can be executed by either a LocalExecutor or RemoteExecutor,
allowing the same pipeline definition to work in both CLI and cloud contexts.

Example usage:
    from karaoke_gen.pipeline import (
        PipelineContext,
        LocalExecutor,
        SeparationStage,
        TranscriptionStage,
    )
    
    # Create context
    context = PipelineContext(
        job_id="my-job",
        artist="Artist Name",
        title="Song Title",
        input_audio_path="/path/to/audio.flac",
        output_dir="/path/to/output",
    )
    
    # Create stages
    stages = [
        SeparationStage(),
        TranscriptionStage(),
    ]
    
    # Run pipeline
    executor = LocalExecutor()
    results = await executor.run_pipeline(stages, context)
"""
from karaoke_gen.pipeline.base import (
    PipelineStage,
    PipelineExecutor,
    StageResult,
    StageStatus,
)
from karaoke_gen.pipeline.context import PipelineContext

# Import stages
from karaoke_gen.pipeline.stages import (
    SeparationStage,
    TranscriptionStage,
    ScreensStage,
    RenderStage,
    FinalizeStage,
)

# Import executors
from karaoke_gen.pipeline.executors import (
    LocalExecutor,
    RemoteExecutor,
    create_local_executor,
    create_remote_executor,
)

__all__ = [
    # Base classes
    "PipelineStage",
    "PipelineExecutor",
    "StageResult",
    "StageStatus",
    "PipelineContext",
    # Stages
    "SeparationStage",
    "TranscriptionStage",
    "ScreensStage",
    "RenderStage",
    "FinalizeStage",
    # Executors
    "LocalExecutor",
    "RemoteExecutor",
    "create_local_executor",
    "create_remote_executor",
]
