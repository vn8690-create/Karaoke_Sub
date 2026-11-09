"""
Unit tests for metadata module.

Tests cover the metadata extraction and parsing functions after flacfetch integration.
"""

import pytest
from unittest.mock import MagicMock, patch
from karaoke_gen.karaoke_gen import KaraokePrep
from karaoke_gen.metadata import extract_info_for_online_media, parse_track_metadata


class TestExtractInfoForOnlineMedia:
    """Tests for extract_info_for_online_media function."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    def test_url_raises_value_error(self, mock_logger):
        """Test that providing a URL raises ValueError since URLs are no longer supported."""
        with pytest.raises(ValueError) as exc_info:
            extract_info_for_online_media(
                input_url="https://example.com/video",
                input_artist="Test Artist",
                input_title="Test Title",
                logger=mock_logger,
            )
        
        assert "URL-based audio fetching has been replaced" in str(exc_info.value)
        assert "flacfetch" in str(exc_info.value)

    def test_artist_title_creates_metadata(self, mock_logger):
        """Test that artist and title create synthetic metadata dict."""
        result = extract_info_for_online_media(
            input_url=None,
            input_artist="Test Artist",
            input_title="Test Title",
            logger=mock_logger,
        )

        assert result is not None
        assert result["title"] == "Test Artist - Test Title"
        assert result["artist"] == "Test Artist"
        assert result["track_title"] == "Test Title"
        assert result["extractor_key"] == "flacfetch"
        assert result["source"] == "flacfetch"
        assert result["url"] is None

    def test_missing_artist_raises_value_error(self, mock_logger):
        """Test that missing artist raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            extract_info_for_online_media(
                input_url=None,
                input_artist=None,
                input_title="Test Title",
                logger=mock_logger,
            )
        
        assert "Artist and title are required" in str(exc_info.value)

    def test_missing_title_raises_value_error(self, mock_logger):
        """Test that missing title raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            extract_info_for_online_media(
                input_url=None,
                input_artist="Test Artist",
                input_title=None,
                logger=mock_logger,
            )
        
        assert "Artist and title are required" in str(exc_info.value)

    def test_cookies_str_deprecated(self, mock_logger):
        """Test that cookies_str parameter is accepted but ignored."""
        # Should not raise an error even with cookies_str
        result = extract_info_for_online_media(
            input_url=None,
            input_artist="Test Artist",
            input_title="Test Title",
            logger=mock_logger,
            cookies_str="some_cookies",
        )
        
        assert result is not None
        assert result["artist"] == "Test Artist"


class TestParseTrackMetadata:
    """Tests for parse_track_metadata function."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    def test_flacfetch_metadata(self, mock_logger):
        """Test parsing flacfetch-style metadata."""
        extracted_info = {
            "title": "Test Artist - Test Title",
            "artist": "Test Artist",
            "track_title": "Test Title",
            "extractor_key": "flacfetch",
            "id": "flacfetch_test",
            "url": None,
            "source": "flacfetch",
        }

        result = parse_track_metadata(
            extracted_info,
            current_artist=None,
            current_title=None,
            persistent_artist=None,
            logger=mock_logger,
        )

        assert result["artist"] == "Test Artist"
        assert result["title"] == "Test Title"
        assert result["extractor"] == "flacfetch"
        assert result["url"] is None

    def test_flacfetch_with_persistent_artist(self, mock_logger):
        """Test flacfetch metadata with persistent artist override."""
        extracted_info = {
            "title": "Original Artist - Test Title",
            "artist": "Original Artist",
            "track_title": "Test Title",
            "extractor_key": "flacfetch",
            "id": "flacfetch_test",
            "url": None,
            "source": "flacfetch",
        }

        result = parse_track_metadata(
            extracted_info,
            current_artist=None,
            current_title=None,
            persistent_artist="Persistent Artist",
            logger=mock_logger,
        )

        assert result["artist"] == "Persistent Artist"
        assert result["title"] == "Test Title"

    def test_legacy_metadata_with_url(self, mock_logger):
        """Test parsing legacy-style metadata with URL (backward compatibility)."""
        extracted_info = {
            "title": "Test Artist - Test Title",
            "extractor_key": "Youtube",
            "id": "12345",
            "url": "https://example.com/video",
        }

        result = parse_track_metadata(
            extracted_info,
            current_artist=None,
            current_title=None,
            persistent_artist=None,
            logger=mock_logger,
        )

        assert result["url"] == "https://example.com/video"
        assert result["extractor"] == "Youtube"
        assert result["media_id"] == "12345"
        assert result["artist"] == "Test Artist"
        assert result["title"] == "Test Title"

    def test_legacy_metadata_with_webpage_url(self, mock_logger):
        """Test parsing metadata with webpage_url instead of url."""
        extracted_info = {
            "title": "Test Artist - Test Title",
            "extractor_key": "Youtube",
            "id": "12345",
            "webpage_url": "https://example.com/video",
        }

        result = parse_track_metadata(
            extracted_info,
            current_artist=None,
            current_title=None,
            persistent_artist=None,
            logger=mock_logger,
        )

        assert result["url"] == "https://example.com/video"

    def test_metadata_with_ie_key(self, mock_logger):
        """Test parsing metadata with ie_key instead of extractor_key."""
        extracted_info = {
            "title": "Test Artist - Test Title",
            "ie_key": "Youtube",
            "id": "12345",
            "url": "https://example.com/video",
        }

        result = parse_track_metadata(
            extracted_info,
            current_artist=None,
            current_title=None,
            persistent_artist=None,
            logger=mock_logger,
        )

        assert result["extractor"] == "Youtube"

    def test_metadata_with_input_values(self, mock_logger):
        """Test parsing metadata preserves input artist/title."""
        extracted_info = {
            "title": "Wrong Artist - Wrong Title",
            "extractor_key": "flacfetch",
            "id": "12345",
            "source": "flacfetch",
        }

        result = parse_track_metadata(
            extracted_info,
            current_artist="Input Artist",
            current_title="Input Title",
            persistent_artist=None,
            logger=mock_logger,
        )

        assert result["artist"] == "Input Artist"
        assert result["title"] == "Input Title"

    def test_metadata_with_uploader_fallback(self, mock_logger):
        """Test parsing metadata uses uploader as artist fallback."""
        extracted_info = {
            "title": "Test Title",  # No artist in title
            "extractor_key": "Youtube",
            "id": "12345",
            "url": "https://example.com/video",
            "uploader": "Test Uploader",
        }

        result = parse_track_metadata(
            extracted_info,
            current_artist=None,
            current_title=None,
            persistent_artist=None,
            logger=mock_logger,
        )

        assert result["artist"] == "Test Uploader"
        assert result["title"] == "Test Title"

    def test_metadata_missing_artist_title_raises(self, mock_logger):
        """Test parsing metadata raises when artist/title cannot be extracted."""
        extracted_info = {
            "extractor_key": "Youtube",
            "id": "12345",
            "url": "https://example.com/video",
            # No title, no uploader
        }

        with pytest.raises(Exception) as exc_info:
            parse_track_metadata(
                extracted_info,
                current_artist=None,
                current_title=None,
                persistent_artist=None,
                logger=mock_logger,
            )

        assert "Failed to extract artist and title" in str(exc_info.value)

    def test_no_url_defaults_to_none(self, mock_logger):
        """Test metadata without URL defaults to None (for flacfetch)."""
        extracted_info = {
            "title": "Test Artist - Test Title",
            "extractor_key": "flacfetch",
            "id": "12345",
            # No url or webpage_url
        }

        result = parse_track_metadata(
            extracted_info,
            current_artist=None,
            current_title=None,
            persistent_artist=None,
            logger=mock_logger,
        )

        assert result["url"] is None

    def test_no_extractor_defaults_to_flacfetch(self, mock_logger):
        """Test metadata without extractor defaults to flacfetch."""
        extracted_info = {
            "title": "Test Artist - Test Title",
            "id": "12345",
            # No extractor_key or ie_key
        }

        result = parse_track_metadata(
            extracted_info,
            current_artist=None,
            current_title=None,
            persistent_artist=None,
            logger=mock_logger,
        )

        assert result["extractor"] == "flacfetch"


class TestKaraokePrepMetadataIntegration:
    """Integration tests for KaraokePrep metadata methods."""

    @pytest.fixture
    def basic_karaoke_gen(self, tmp_path):
        """Create a basic KaraokePrep instance for testing."""
        return KaraokePrep(
            input_media=None,
            artist="Test Artist",
            title="Test Title",
            output_dir=str(tmp_path),
        )

    def test_extract_info_for_online_media_with_artist_title(self, basic_karaoke_gen):
        """Test extracting info creates flacfetch metadata."""
        result = basic_karaoke_gen.extract_info_for_online_media(
            input_artist="Test Artist",
            input_title="Test Title",
        )

        assert result["source"] == "flacfetch"
        assert result["artist"] == "Test Artist"
        assert result["track_title"] == "Test Title"
        assert basic_karaoke_gen.extracted_info == result

    def test_extract_info_with_url_raises(self, basic_karaoke_gen):
        """Test extracting info with URL raises ValueError."""
        with pytest.raises(ValueError):
            basic_karaoke_gen.extract_info_for_online_media(
                input_url="https://example.com/video",
            )

    def test_parse_single_track_metadata_complete(self, basic_karaoke_gen):
        """Test parsing metadata from flacfetch-style extracted info."""
        basic_karaoke_gen.extracted_info = {
            "title": "Test Artist - Test Title",
            "artist": "Test Artist",
            "track_title": "Test Title",
            "extractor_key": "flacfetch",
            "id": "flacfetch_test",
            "url": None,
            "source": "flacfetch",
        }

        basic_karaoke_gen.parse_single_track_metadata(None, None)

        assert basic_karaoke_gen.url is None
        assert basic_karaoke_gen.extractor == "flacfetch"
        assert basic_karaoke_gen.artist == "Test Artist"
        assert basic_karaoke_gen.title == "Test Title"

    def test_parse_single_track_metadata_with_input_values(self, basic_karaoke_gen):
        """Test parsing metadata with provided input values."""
        basic_karaoke_gen.extracted_info = {
            "title": "Wrong Artist - Wrong Title",
            "extractor_key": "flacfetch",
            "id": "12345",
            "source": "flacfetch",
        }

        input_artist = "Input Artist"
        input_title = "Input Title"

        basic_karaoke_gen.artist = input_artist
        basic_karaoke_gen.title = input_title

        basic_karaoke_gen.parse_single_track_metadata(input_artist, input_title)

        assert basic_karaoke_gen.artist == input_artist
        assert basic_karaoke_gen.title == input_title

    def test_parse_single_track_metadata_with_persistent_artist(self, basic_karaoke_gen):
        """Test parsing metadata with persistent artist."""
        basic_karaoke_gen.extracted_info = {
            "title": "Test Artist - Test Title",
            "artist": "Test Artist",
            "track_title": "Test Title",
            "extractor_key": "flacfetch",
            "id": "12345",
            "source": "flacfetch",
        }

        basic_karaoke_gen.persistent_artist = "Persistent Artist"

        basic_karaoke_gen.parse_single_track_metadata(None, None)

        assert basic_karaoke_gen.artist == "Persistent Artist"
        assert basic_karaoke_gen.title == "Test Title"
