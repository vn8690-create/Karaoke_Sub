"""
Pipeline stages for karaoke generation.

Each stage represents a discrete unit of work in the karaoke generation
process. Stages are designed to be composable and can be executed either
locally or remotely.

Available stages:
- SeparationStage: Audio separation into stems
- TranscriptionStage: Lyrics transcription and synchronization
- ScreensStage: Title and end screen generation
- RenderStage: Video rendering with synchronized lyrics
- FinalizeStage: Encoding, packaging, and distribution
"""
from karaoke_gen.pipeline.stages.separation import SeparationStage
from karaoke_gen.pipeline.stages.transcription import TranscriptionStage
from karaoke_gen.pipeline.stages.screens import ScreensStage
from karaoke_gen.pipeline.stages.render import RenderStage
from karaoke_gen.pipeline.stages.finalize import FinalizeStage

__all__ = [
    "SeparationStage",
    "TranscriptionStage",
    "ScreensStage",
    "RenderStage",
    "FinalizeStage",
]
