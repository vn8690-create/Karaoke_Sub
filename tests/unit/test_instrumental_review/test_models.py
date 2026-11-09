"""
Unit tests for instrumental_review models.

Tests cover:
- Model creation and validation
- Property methods
- Serialization/deserialization
- Edge cases
"""

import pytest
from pydantic import ValidationError

from karaoke_gen.instrumental_review import (
    AnalysisResult,
    AudibleSegment,
    MuteRegion,
    RecommendedSelection,
)
from karaoke_gen.instrumental_review.models import CustomInstrumentalResult


class TestRecommendedSelection:
    """Tests for RecommendedSelection enum."""
    
    def test_enum_values(self):
        """Test enum has expected values."""
        assert RecommendedSelection.CLEAN.value == "clean"
        assert RecommendedSelection.WITH_BACKING.value == "with_backing"
        assert RecommendedSelection.REVIEW_NEEDED.value == "review_needed"
    
    def test_enum_from_string(self):
        """Test creating enum from string value."""
        assert RecommendedSelection("clean") == RecommendedSelection.CLEAN
        assert RecommendedSelection("with_backing") == RecommendedSelection.WITH_BACKING
        assert RecommendedSelection("review_needed") == RecommendedSelection.REVIEW_NEEDED


class TestAudibleSegment:
    """Tests for AudibleSegment model."""
    
    def test_create_valid_segment(self):
        """Test creating a valid audible segment."""
        segment = AudibleSegment(
            start_seconds=1.0,
            end_seconds=3.0,
            duration_seconds=2.0,
            avg_amplitude_db=-15.0,
        )
        
        assert segment.start_seconds == 1.0
        assert segment.end_seconds == 3.0
        assert segment.duration_seconds == 2.0
        assert segment.avg_amplitude_db == -15.0
    
    def test_default_peak_amplitude(self):
        """Test default peak amplitude is 0.0."""
        segment = AudibleSegment(
            start_seconds=0.0,
            end_seconds=1.0,
            duration_seconds=1.0,
            avg_amplitude_db=-20.0,
        )
        
        assert segment.peak_amplitude_db == 0.0
    
    def test_is_loud_property_true(self):
        """Test is_loud returns True for loud segments."""
        segment = AudibleSegment(
            start_seconds=0.0,
            end_seconds=1.0,
            duration_seconds=1.0,
            avg_amplitude_db=-15.0,  # Louder than -20dB
        )
        
        assert segment.is_loud is True
    
    def test_is_loud_property_false(self):
        """Test is_loud returns False for quiet segments."""
        segment = AudibleSegment(
            start_seconds=0.0,
            end_seconds=1.0,
            duration_seconds=1.0,
            avg_amplitude_db=-25.0,  # Quieter than -20dB
        )
        
        assert segment.is_loud is False
    
    def test_negative_start_invalid(self):
        """Test negative start_seconds is invalid."""
        with pytest.raises(ValidationError):
            AudibleSegment(
                start_seconds=-1.0,
                end_seconds=1.0,
                duration_seconds=2.0,
                avg_amplitude_db=-15.0,
            )
    
    def test_negative_duration_invalid(self):
        """Test negative duration_seconds is invalid."""
        with pytest.raises(ValidationError):
            AudibleSegment(
                start_seconds=0.0,
                end_seconds=1.0,
                duration_seconds=-1.0,
                avg_amplitude_db=-15.0,
            )
    
    def test_serialization_to_dict(self):
        """Test segment can be serialized to dict."""
        segment = AudibleSegment(
            start_seconds=1.0,
            end_seconds=3.0,
            duration_seconds=2.0,
            avg_amplitude_db=-15.0,
            peak_amplitude_db=-10.0,
        )
        
        data = segment.model_dump()
        
        assert data["start_seconds"] == 1.0
        assert data["end_seconds"] == 3.0
        assert data["duration_seconds"] == 2.0
        assert data["avg_amplitude_db"] == -15.0
        assert data["peak_amplitude_db"] == -10.0


class TestMuteRegion:
    """Tests for MuteRegion model."""
    
    def test_create_valid_region(self):
        """Test creating a valid mute region."""
        region = MuteRegion(start_seconds=1.0, end_seconds=3.0)
        
        assert region.start_seconds == 1.0
        assert region.end_seconds == 3.0
    
    def test_duration_property(self):
        """Test duration_seconds property."""
        region = MuteRegion(start_seconds=1.0, end_seconds=3.0)
        
        assert region.duration_seconds == 2.0
    
    def test_overlaps_method(self):
        """Test overlaps method with overlapping regions."""
        region1 = MuteRegion(start_seconds=1.0, end_seconds=3.0)
        region2 = MuteRegion(start_seconds=2.0, end_seconds=4.0)
        
        assert region1.overlaps(region2) is True
    
    def test_overlaps_method_no_overlap(self):
        """Test overlaps method with non-overlapping regions."""
        region1 = MuteRegion(start_seconds=1.0, end_seconds=2.0)
        region2 = MuteRegion(start_seconds=3.0, end_seconds=4.0)
        
        assert region1.overlaps(region2) is False
    
    def test_overlaps_contained(self):
        """Test overlaps when one region contains another."""
        region1 = MuteRegion(start_seconds=1.0, end_seconds=5.0)
        region2 = MuteRegion(start_seconds=2.0, end_seconds=3.0)
        
        assert region1.overlaps(region2) is True
        assert region2.overlaps(region1) is True
    
    def test_merge_method(self):
        """Test merge method creates combined region."""
        region1 = MuteRegion(start_seconds=1.0, end_seconds=3.0)
        region2 = MuteRegion(start_seconds=2.0, end_seconds=4.0)
        
        merged = region1.merge(region2)
        
        assert merged.start_seconds == 1.0
        assert merged.end_seconds == 4.0
    
    def test_negative_start_invalid(self):
        """Test negative start_seconds is invalid."""
        with pytest.raises(ValidationError):
            MuteRegion(start_seconds=-1.0, end_seconds=1.0)
    
    def test_serialization_to_dict(self):
        """Test region can be serialized to dict."""
        region = MuteRegion(start_seconds=1.0, end_seconds=3.0)
        
        data = region.model_dump()
        
        assert data["start_seconds"] == 1.0
        assert data["end_seconds"] == 3.0


class TestAnalysisResult:
    """Tests for AnalysisResult model."""
    
    def test_create_valid_result(self):
        """Test creating a valid analysis result."""
        result = AnalysisResult(
            has_audible_content=True,
            total_duration_seconds=120.0,
            audible_segments=[],
            recommended_selection=RecommendedSelection.REVIEW_NEEDED,
        )
        
        assert result.has_audible_content is True
        assert result.total_duration_seconds == 120.0
        assert result.recommended_selection == RecommendedSelection.REVIEW_NEEDED
    
    def test_default_values(self):
        """Test default values are set correctly."""
        result = AnalysisResult(
            has_audible_content=False,
            total_duration_seconds=60.0,
            recommended_selection=RecommendedSelection.CLEAN,
        )
        
        assert result.audible_segments == []
        assert result.silence_threshold_db == -40.0
        assert result.total_audible_duration_seconds == 0.0
        assert result.audible_percentage == 0.0
        assert result.waveform_data is None
    
    def test_segment_count_property(self):
        """Test segment_count property."""
        segments = [
            AudibleSegment(
                start_seconds=0.0, end_seconds=1.0,
                duration_seconds=1.0, avg_amplitude_db=-15.0
            ),
            AudibleSegment(
                start_seconds=2.0, end_seconds=3.0,
                duration_seconds=1.0, avg_amplitude_db=-15.0
            ),
        ]
        
        result = AnalysisResult(
            has_audible_content=True,
            total_duration_seconds=10.0,
            audible_segments=segments,
            recommended_selection=RecommendedSelection.REVIEW_NEEDED,
        )
        
        assert result.segment_count == 2
    
    def test_get_segments_in_range(self):
        """Test get_segments_in_range method."""
        segments = [
            AudibleSegment(
                start_seconds=1.0, end_seconds=2.0,
                duration_seconds=1.0, avg_amplitude_db=-15.0
            ),
            AudibleSegment(
                start_seconds=5.0, end_seconds=6.0,
                duration_seconds=1.0, avg_amplitude_db=-15.0
            ),
            AudibleSegment(
                start_seconds=8.0, end_seconds=9.0,
                duration_seconds=1.0, avg_amplitude_db=-15.0
            ),
        ]
        
        result = AnalysisResult(
            has_audible_content=True,
            total_duration_seconds=10.0,
            audible_segments=segments,
            recommended_selection=RecommendedSelection.REVIEW_NEEDED,
        )
        
        # Get segments between 0-3 seconds
        in_range = result.get_segments_in_range(0.0, 3.0)
        
        assert len(in_range) == 1
        assert in_range[0].start_seconds == 1.0
    
    def test_get_segments_in_range_partial_overlap(self):
        """Test get_segments_in_range with partial overlap."""
        segments = [
            AudibleSegment(
                start_seconds=2.0, end_seconds=6.0,
                duration_seconds=4.0, avg_amplitude_db=-15.0
            ),
        ]
        
        result = AnalysisResult(
            has_audible_content=True,
            total_duration_seconds=10.0,
            audible_segments=segments,
            recommended_selection=RecommendedSelection.REVIEW_NEEDED,
        )
        
        # Segment overlaps with range [4, 8]
        in_range = result.get_segments_in_range(4.0, 8.0)
        
        assert len(in_range) == 1
    
    def test_audible_percentage_validation(self):
        """Test audible_percentage must be 0-100."""
        with pytest.raises(ValidationError):
            AnalysisResult(
                has_audible_content=True,
                total_duration_seconds=60.0,
                recommended_selection=RecommendedSelection.CLEAN,
                audible_percentage=150.0,  # Invalid
            )
    
    def test_serialization_to_dict(self):
        """Test result can be serialized to dict."""
        segments = [
            AudibleSegment(
                start_seconds=1.0, end_seconds=2.0,
                duration_seconds=1.0, avg_amplitude_db=-15.0
            ),
        ]
        
        result = AnalysisResult(
            has_audible_content=True,
            total_duration_seconds=60.0,
            audible_segments=segments,
            recommended_selection=RecommendedSelection.REVIEW_NEEDED,
            total_audible_duration_seconds=1.0,
            audible_percentage=1.67,
        )
        
        data = result.model_dump()
        
        assert data["has_audible_content"] is True
        assert data["total_duration_seconds"] == 60.0
        assert len(data["audible_segments"]) == 1
        assert data["recommended_selection"] == "review_needed"
    
    def test_serialization_to_json(self):
        """Test result can be serialized to JSON."""
        result = AnalysisResult(
            has_audible_content=False,
            total_duration_seconds=60.0,
            recommended_selection=RecommendedSelection.CLEAN,
        )
        
        json_str = result.model_dump_json()
        
        assert '"has_audible_content":false' in json_str.lower().replace(" ", "")
        assert '"recommended_selection":"clean"' in json_str.lower().replace(" ", "")


class TestCustomInstrumentalResult:
    """Tests for CustomInstrumentalResult model."""
    
    def test_create_valid_result(self):
        """Test creating a valid custom instrumental result."""
        mute_regions = [
            MuteRegion(start_seconds=1.0, end_seconds=2.0),
        ]
        
        result = CustomInstrumentalResult(
            output_path="/path/to/custom.flac",
            mute_regions_applied=mute_regions,
            total_muted_duration_seconds=1.0,
            output_duration_seconds=60.0,
        )
        
        assert result.output_path == "/path/to/custom.flac"
        assert len(result.mute_regions_applied) == 1
        assert result.total_muted_duration_seconds == 1.0
        assert result.output_duration_seconds == 60.0
    
    def test_default_values(self):
        """Test default values are set correctly."""
        result = CustomInstrumentalResult(
            output_path="/path/to/output.flac",
        )
        
        assert result.mute_regions_applied == []
        assert result.total_muted_duration_seconds == 0.0
        assert result.output_duration_seconds == 0.0
    
    def test_serialization_to_dict(self):
        """Test result can be serialized to dict."""
        result = CustomInstrumentalResult(
            output_path="/path/to/custom.flac",
            mute_regions_applied=[
                MuteRegion(start_seconds=1.0, end_seconds=2.0),
            ],
            total_muted_duration_seconds=1.0,
            output_duration_seconds=60.0,
        )
        
        data = result.model_dump()
        
        assert data["output_path"] == "/path/to/custom.flac"
        assert len(data["mute_regions_applied"]) == 1
