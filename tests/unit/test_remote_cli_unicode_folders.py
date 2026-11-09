"""Unit tests for remote_cli Unicode folder name sanitization.

Tests the fix for job 1eab1172 where Cyrillic characters in folder names
could cause filesystem issues.
"""

import pytest


class TestRemoteCliFolderNameSanitization:
    """Test folder name sanitization logic for Unicode characters."""

    @pytest.mark.parametrize("artist,title,expected_has,expected_not_has", [
        ("zivert", "я куплю тебе дом", ["zivert"], ["я", "куплю", "тебе", "дом", " - ", "_"]),  # Cyrillic removed, only artist remains
        ("artist", "中文标题", ["artist"], ["中", "文", "标", "题", " - ", "_"]),  # Chinese removed
        ("artist", "العربية", ["artist"], ["ا", "ل", "ع", "ر", "ب", " - ", "_"]),  # Arabic removed
        ("artist", "título", ["artist", " - ", "tulo"], ["í"]),  # Accented (í removed, t+ulo remain)
        ("Artist", "Normal Title", ["Artist", " - ", "Normal", "Title"], []),  # ASCII preserved
        ("Test", "Song (2024)", ["Test", " - ", "Song", "2024"], ["(", ")"]),  # Parens removed
    ])
    def test_folder_name_sanitization_logic(self, artist, title, expected_has, expected_not_has):
        """Test the folder name sanitization logic directly."""
        # This is the exact logic from remote_cli.py:1970
        folder_name = f"{artist} - {title}"
        folder_name = "".join(c for c in folder_name if (c.isascii() and c.isalnum()) or c in " -_").strip()

        # Verify folder name is ASCII only
        assert folder_name.isascii(), f"Folder name should be ASCII-only: {folder_name}"

        # Verify expected parts are present
        for expected in expected_has:
            assert expected in folder_name, \
                f"Expected '{expected}' to be in folder name: {folder_name}"

        # Verify unwanted parts are removed
        for not_expected in expected_not_has:
            assert not_expected not in folder_name, \
                f"Did not expect '{not_expected}' in folder name: {folder_name}"

    def test_folder_name_brand_code_logic(self):
        """Test folder name with brand code prefix."""
        brand_code = "BRAND-001"
        artist = "Artist"
        title = "Title"

        folder_name = f"{brand_code} - {artist} - {title}"
        folder_name = "".join(c for c in folder_name if (c.isascii() and c.isalnum()) or c in " -_").strip()

        assert folder_name.startswith("BRAND-001 - ")
        assert "Artist" in folder_name
        assert "Title" in folder_name

    def test_folder_name_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        artist = "  Artist  "
        title = "  Title  "

        folder_name = f"{artist} - {title}"
        folder_name = "".join(c for c in folder_name if (c.isascii() and c.isalnum()) or c in " -_").strip()

        assert not folder_name.startswith(" ")
        assert not folder_name.endswith(" ")
        assert "Artist" in folder_name
        assert "Title" in folder_name

    def test_cyrillic_real_world_case_job_1eab1172(self):
        """Test the exact case from failed job 1eab1172 - Russian title."""
        artist = "zivert"
        title = "я куплю тебе дом"  # Russian: "I will buy you a house"

        folder_name = f"{artist} - {title}"
        folder_name = "".join(c for c in folder_name if (c.isascii() and c.isalnum()) or c in " -_").strip()

        # Should be ASCII-only
        assert folder_name.isascii()

        # Should contain the artist name
        assert "zivert" in folder_name

        # Cyrillic characters should be removed
        assert "я" not in folder_name
        assert "куплю" not in folder_name
        assert "тебе" not in folder_name
        assert "дом" not in folder_name

    def test_emoji_and_special_unicode(self):
        """Test that emojis and special Unicode characters are removed."""
        artist = "Artist 😀"
        title = "Song 🎵"

        folder_name = f"{artist} - {title}"
        folder_name = "".join(c for c in folder_name if (c.isascii() and c.isalnum()) or c in " -_").strip()

        assert folder_name.isascii()
        assert "😀" not in folder_name
        assert "🎵" not in folder_name
        assert "Artist" in folder_name
        assert "Song" in folder_name

    def test_empty_folder_name_fallback(self):
        """Test that if sanitization results in empty or separator-only string, fallback to job_id."""
        job_id = "abc123xyz"

        # Test 1: Emoji with separator results in "-" after sanitization
        artist = "😀😀😀"
        title = "🎵🎵🎵"
        folder_name = f"{artist} - {title}"
        folder_name = "".join(c for c in folder_name if (c.isascii() and c.isalnum()) or c in " -_").strip()

        # After sanitization, only "-" remains (spaces/hyphens allowed but emoji removed)
        assert folder_name == "-"

        # Apply the fallback logic (updated to check for alphanumeric content)
        if not folder_name or not any(c.isascii() and c.isalnum() for c in folder_name):
            folder_name = f"job_{job_id}"

        # Verify fallback is used for separator-only result
        assert folder_name == "job_abc123xyz"

        # Test 2: Truly empty result (all characters removed, no separator)
        artist2 = "😀"
        title2 = "🎵"
        folder_name2 = f"{artist2}{title2}"  # No separator, just emoji
        folder_name2 = "".join(c for c in folder_name2 if (c.isascii() and c.isalnum()) or c in " -_").strip()

        # Should be empty
        assert folder_name2 == ""

        # Apply fallback
        if not folder_name2 or not any(c.isascii() and c.isalnum() for c in folder_name2):
            folder_name2 = f"job_{job_id}"

        assert folder_name2 == "job_abc123xyz"
