"""
Unit tests for theme validation functionality.

Tests validate_theme_completeness() and warning behavior in getter functions.
"""
import logging
import pytest
from karaoke_gen.style_loader import (
    DEFAULT_INTRO_STYLE,
    DEFAULT_END_STYLE,
    DEFAULT_KARAOKE_STYLE,
    DEFAULT_CDG_STYLE,
    validate_theme_completeness,
    get_intro_format,
    get_end_format,
    get_karaoke_format,
    get_cdg_format,
)


class TestValidateThemeCompleteness:
    """Test validate_theme_completeness function."""

    def test_complete_theme(self, caplog):
        """Test that a complete theme passes validation."""
        complete_theme = {
            "intro": DEFAULT_INTRO_STYLE.copy(),
            "end": DEFAULT_END_STYLE.copy(),
            "karaoke": DEFAULT_KARAOKE_STYLE.copy(),
            "cdg": DEFAULT_CDG_STYLE.copy(),
        }

        is_complete, missing = validate_theme_completeness(complete_theme)

        assert is_complete is True
        assert missing == []

    def test_missing_section(self, caplog):
        """Test that missing sections are detected."""
        incomplete_theme = {
            "intro": DEFAULT_INTRO_STYLE.copy(),
            "end": DEFAULT_END_STYLE.copy(),
            # Missing karaoke and cdg sections
        }

        is_complete, missing = validate_theme_completeness(incomplete_theme)

        assert is_complete is False
        assert "Missing section: karaoke" in missing
        assert "Missing section: cdg" in missing

    def test_missing_intro_fields(self, caplog):
        """Test that missing intro fields are detected."""
        incomplete_theme = {
            "intro": {
                "video_duration": 5,
                "background_color": "#000000",
                # Missing other required fields
            },
            "end": DEFAULT_END_STYLE.copy(),
            "karaoke": DEFAULT_KARAOKE_STYLE.copy(),
            "cdg": DEFAULT_CDG_STYLE.copy(),
        }

        is_complete, missing = validate_theme_completeness(incomplete_theme)

        assert is_complete is False
        assert any("intro." in m for m in missing)
        # Check a few specific missing fields
        assert "intro.font" in missing
        assert "intro.artist_color" in missing
        assert "intro.title_color" in missing

    def test_missing_end_fields(self, caplog):
        """Test that missing end fields are detected."""
        incomplete_theme = {
            "intro": DEFAULT_INTRO_STYLE.copy(),
            "end": {
                "video_duration": 5,
                # Missing other required fields
            },
            "karaoke": DEFAULT_KARAOKE_STYLE.copy(),
            "cdg": DEFAULT_CDG_STYLE.copy(),
        }

        is_complete, missing = validate_theme_completeness(incomplete_theme)

        assert is_complete is False
        assert any("end." in m for m in missing)
        assert "end.font" in missing
        assert "end.background_color" in missing

    def test_missing_karaoke_fields(self, caplog):
        """Test that missing karaoke fields are detected."""
        incomplete_theme = {
            "intro": DEFAULT_INTRO_STYLE.copy(),
            "end": DEFAULT_END_STYLE.copy(),
            "karaoke": {
                "background_color": "#000000",
                "font": "Noto Sans",
                # Missing other required fields
            },
            "cdg": DEFAULT_CDG_STYLE.copy(),
        }

        is_complete, missing = validate_theme_completeness(incomplete_theme)

        assert is_complete is False
        assert any("karaoke." in m for m in missing)
        assert "karaoke.primary_color" in missing
        assert "karaoke.font_size" in missing

    def test_missing_cdg_fields(self, caplog):
        """Test that missing cdg fields are detected."""
        incomplete_theme = {
            "intro": DEFAULT_INTRO_STYLE.copy(),
            "end": DEFAULT_END_STYLE.copy(),
            "karaoke": DEFAULT_KARAOKE_STYLE.copy(),
            "cdg": {
                # Missing all fields
            },
        }

        is_complete, missing = validate_theme_completeness(incomplete_theme)

        assert is_complete is False
        assert any("cdg." in m for m in missing)

    def test_logs_warning_on_incomplete(self, caplog):
        """Test that validation logs a warning for incomplete themes."""
        incomplete_theme = {
            "intro": {"video_duration": 5},
            "end": DEFAULT_END_STYLE.copy(),
            "karaoke": DEFAULT_KARAOKE_STYLE.copy(),
            "cdg": DEFAULT_CDG_STYLE.copy(),
        }

        with caplog.at_level(logging.WARNING):
            is_complete, missing = validate_theme_completeness(incomplete_theme)

        assert is_complete is False
        assert "Theme validation failed" in caplog.text
        assert "Missing:" in caplog.text


class TestGetterFunctionErrors:
    """Test that getter functions raise errors for incomplete themes (Phase 2)."""

    def test_get_intro_format_complete(self):
        """Test get_intro_format with complete intro section."""
        style_params = {"intro": DEFAULT_INTRO_STYLE.copy()}

        result = get_intro_format(style_params)

        # Should return the intro params as-is
        assert result == DEFAULT_INTRO_STYLE

    def test_get_intro_format_incomplete_raises(self):
        """Test get_intro_format raises error for incomplete intro section."""
        style_params = {
            "intro": {
                "video_duration": 5,
                "background_color": "#000000",
                # Missing other fields
            }
        }

        with pytest.raises(ValueError, match="Incomplete 'intro' section"):
            get_intro_format(style_params)

    def test_get_intro_format_missing_section_raises(self):
        """Test get_intro_format raises error when intro section is missing."""
        style_params = {}

        with pytest.raises(ValueError, match="Missing 'intro' section"):
            get_intro_format(style_params)

    def test_get_end_format_incomplete_raises(self):
        """Test get_end_format raises error for incomplete end section."""
        style_params = {"end": {"video_duration": 3}}

        with pytest.raises(ValueError, match="Incomplete 'end' section"):
            get_end_format(style_params)

    def test_get_end_format_missing_section_raises(self):
        """Test get_end_format raises error when end section is missing."""
        style_params = {}

        with pytest.raises(ValueError, match="Missing 'end' section"):
            get_end_format(style_params)

    def test_get_karaoke_format_incomplete_raises(self):
        """Test get_karaoke_format raises error for incomplete karaoke section."""
        style_params = {"karaoke": {"background_color": "#FF0000"}}

        with pytest.raises(ValueError, match="Incomplete 'karaoke' section"):
            get_karaoke_format(style_params)

    def test_get_karaoke_format_missing_section_raises(self):
        """Test get_karaoke_format raises error when karaoke section is missing."""
        style_params = {}

        with pytest.raises(ValueError, match="Missing 'karaoke' section"):
            get_karaoke_format(style_params)

    def test_get_cdg_format_incomplete_raises(self):
        """Test get_cdg_format raises error for incomplete cdg section."""
        style_params = {"cdg": {"font_path": "/custom/font.ttf"}}

        with pytest.raises(ValueError, match="Incomplete 'cdg' section"):
            get_cdg_format(style_params)

    def test_get_cdg_format_missing_section_returns_none(self):
        """Test get_cdg_format returns None when cdg section is missing."""
        style_params = {"intro": DEFAULT_INTRO_STYLE.copy()}

        result = get_cdg_format(style_params)

        assert result is None

    def test_empty_theme_sections_raise(self):
        """Test that empty theme sections (empty dicts) raise errors."""
        style_params = {
            "intro": {},
            "end": {},
            "karaoke": {},
            "cdg": {},
        }

        with pytest.raises(ValueError, match="Incomplete 'intro' section"):
            get_intro_format(style_params)

        with pytest.raises(ValueError, match="Incomplete 'end' section"):
            get_end_format(style_params)

        with pytest.raises(ValueError, match="Incomplete 'karaoke' section"):
            get_karaoke_format(style_params)

        with pytest.raises(ValueError, match="Incomplete 'cdg' section"):
            get_cdg_format(style_params)


class TestCompleteThemes:
    """Test behavior with complete themes (Phase 2)."""

    def test_complete_intro_returns_as_is(self):
        """Test that complete themes are returned as-is without merging."""
        style_params = {
            "intro": DEFAULT_INTRO_STYLE.copy()
        }
        # Modify some values
        style_params["intro"]["video_duration"] = 10
        style_params["intro"]["background_color"] = "#FF0000"

        result = get_intro_format(style_params)

        # Should return exactly what was provided
        assert result["video_duration"] == 10
        assert result["background_color"] == "#FF0000"
        assert result == style_params["intro"]

    def test_none_fields_preserved(self):
        """Test that None/null fields are preserved."""
        style_params = {
            "intro": DEFAULT_INTRO_STYLE.copy()
        }
        # Explicitly set some optional fields to None
        style_params["intro"]["background_image"] = None
        style_params["intro"]["artist_gradient"] = None

        result = get_intro_format(style_params)

        assert result["background_image"] is None
        assert result["artist_gradient"] is None
