"""
Pydantic models for the instrumental review module.

These models define the data structures used for audio analysis results,
mute regions, and recommendations. They're designed to be serializable
to JSON for API responses.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class RecommendedSelection(str, Enum):
    """Recommendation for which instrumental to use."""
    
    CLEAN = "clean"
    """Use clean instrumental - no backing vocals detected or recommended."""
    
    WITH_BACKING = "with_backing"
    """Use instrumental with backing vocals - backing vocals sound good."""
    
    REVIEW_NEEDED = "review_needed"
    """Human review needed - backing vocals detected but quality uncertain."""


class AudibleSegment(BaseModel):
    """A detected segment of audible content in the backing vocals."""
    
    start_seconds: float = Field(
        ...,
        ge=0,
        description="Start time of the segment in seconds"
    )
    end_seconds: float = Field(
        ...,
        ge=0,
        description="End time of the segment in seconds"
    )
    duration_seconds: float = Field(
        ...,
        ge=0,
        description="Duration of the segment in seconds"
    )
    avg_amplitude_db: float = Field(
        ...,
        description="Average amplitude of the segment in dB"
    )
    peak_amplitude_db: float = Field(
        default=0.0,
        description="Peak amplitude of the segment in dB"
    )
    
    @property
    def is_loud(self) -> bool:
        """Check if this segment is relatively loud (> -20dB average)."""
        return self.avg_amplitude_db > -20.0


class MuteRegion(BaseModel):
    """A region to mute in the backing vocals audio."""
    
    start_seconds: float = Field(
        ...,
        ge=0,
        description="Start time of the region to mute in seconds"
    )
    end_seconds: float = Field(
        ...,
        ge=0,
        description="End time of the region to mute in seconds"
    )
    
    @property
    def duration_seconds(self) -> float:
        """Duration of the mute region in seconds."""
        return self.end_seconds - self.start_seconds
    
    def overlaps(self, other: "MuteRegion") -> bool:
        """Check if this region overlaps with another."""
        return not (self.end_seconds <= other.start_seconds or 
                    self.start_seconds >= other.end_seconds)
    
    def merge(self, other: "MuteRegion") -> "MuteRegion":
        """Merge this region with another overlapping region."""
        return MuteRegion(
            start_seconds=min(self.start_seconds, other.start_seconds),
            end_seconds=max(self.end_seconds, other.end_seconds)
        )


class AnalysisResult(BaseModel):
    """Result of analyzing backing vocals audio for audible content."""
    
    has_audible_content: bool = Field(
        ...,
        description="Whether any audible content was detected"
    )
    total_duration_seconds: float = Field(
        ...,
        ge=0,
        description="Total duration of the audio file in seconds"
    )
    audible_segments: List[AudibleSegment] = Field(
        default_factory=list,
        description="List of detected audible segments"
    )
    recommended_selection: RecommendedSelection = Field(
        ...,
        description="Recommended instrumental selection based on analysis"
    )
    silence_threshold_db: float = Field(
        default=-40.0,
        description="Threshold used to detect silence (in dB)"
    )
    total_audible_duration_seconds: float = Field(
        default=0.0,
        ge=0,
        description="Total duration of all audible segments combined"
    )
    audible_percentage: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Percentage of audio that is audible"
    )
    waveform_data: Optional[List[float]] = Field(
        default=None,
        description="Amplitude envelope data for waveform rendering (optional)"
    )
    
    @property
    def segment_count(self) -> int:
        """Number of audible segments detected."""
        return len(self.audible_segments)
    
    def get_segments_in_range(
        self, 
        start_seconds: float, 
        end_seconds: float
    ) -> List[AudibleSegment]:
        """Get segments that overlap with the given time range."""
        return [
            seg for seg in self.audible_segments
            if not (seg.end_seconds <= start_seconds or 
                    seg.start_seconds >= end_seconds)
        ]


class CustomInstrumentalResult(BaseModel):
    """Result of creating a custom instrumental with muted regions."""
    
    output_path: str = Field(
        ...,
        description="Path to the created custom instrumental file"
    )
    mute_regions_applied: List[MuteRegion] = Field(
        default_factory=list,
        description="List of mute regions that were applied"
    )
    total_muted_duration_seconds: float = Field(
        default=0.0,
        ge=0,
        description="Total duration of muted audio in seconds"
    )
    output_duration_seconds: float = Field(
        default=0.0,
        ge=0,
        description="Duration of the output file in seconds"
    )
