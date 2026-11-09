"""
Unit tests for LyricsCacheService.

Tests the GCS cache synchronization service for LyricsTranscriber.
"""
import hashlib
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from backend.services.lyrics_cache_service import (
    LyricsCacheService,
    TRANSCRIPTION_PROVIDERS,
    LYRICS_PROVIDERS,
    CACHE_SUFFIXES,
)


class TestHashComputation:
    """Tests for hash computation methods."""

    def test_compute_audio_hash_matches_lyrics_transcriber(self, temp_dir):
        """Audio hash should match LyricsTranscriber's _get_file_hash implementation."""
        # Create a test audio file
        audio_path = os.path.join(temp_dir, "test_audio.wav")
        test_content = b"fake audio content for testing hash computation"
        with open(audio_path, "wb") as f:
            f.write(test_content)

        # Compute hash using our service
        mock_storage = MagicMock()
        service = LyricsCacheService(storage=mock_storage)
        computed_hash = service.compute_audio_hash(audio_path)

        # Compute expected hash (same algorithm as LyricsTranscriber)
        md5_hash = hashlib.md5()
        with open(audio_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        expected_hash = md5_hash.hexdigest()

        assert computed_hash == expected_hash

    def test_compute_lyrics_hash_matches_lyrics_transcriber(self):
        """Lyrics hash should match LyricsTranscriber's _get_artist_title_hash implementation."""
        mock_storage = MagicMock()
        service = LyricsCacheService(storage=mock_storage)

        artist = "Test Artist"
        title = "Test Song"

        computed_hash = service.compute_lyrics_hash(artist, title)

        # Expected hash (same algorithm as LyricsTranscriber)
        combined = f"{artist.lower()}_{title.lower()}"
        expected_hash = hashlib.md5(combined.encode()).hexdigest()

        assert computed_hash == expected_hash

    def test_compute_lyrics_hash_case_insensitive(self):
        """Lyrics hash should be case-insensitive."""
        mock_storage = MagicMock()
        service = LyricsCacheService(storage=mock_storage)

        hash1 = service.compute_lyrics_hash("Artist", "Title")
        hash2 = service.compute_lyrics_hash("ARTIST", "TITLE")
        hash3 = service.compute_lyrics_hash("artist", "title")

        assert hash1 == hash2 == hash3


class TestCacheFilenames:
    """Tests for cache filename generation."""

    def test_get_cache_filenames_transcription_providers(self):
        """Should generate correct filenames for transcription providers."""
        mock_storage = MagicMock()
        service = LyricsCacheService(storage=mock_storage)

        filenames = service._get_cache_filenames(TRANSCRIPTION_PROVIDERS, "abc123")

        expected = []
        for provider in TRANSCRIPTION_PROVIDERS:
            for suffix in CACHE_SUFFIXES:
                expected.append(f"{provider}_abc123_{suffix}.json")

        assert sorted(filenames) == sorted(expected)

    def test_get_cache_filenames_lyrics_providers(self):
        """Should generate correct filenames for lyrics providers."""
        mock_storage = MagicMock()
        service = LyricsCacheService(storage=mock_storage)

        filenames = service._get_cache_filenames(LYRICS_PROVIDERS, "def456")

        expected = []
        for provider in LYRICS_PROVIDERS:
            for suffix in CACHE_SUFFIXES:
                expected.append(f"{provider}_def456_{suffix}.json")

        assert sorted(filenames) == sorted(expected)


class TestSyncCacheFromGCS:
    """Tests for downloading cache from GCS."""

    def test_sync_cache_from_gcs_downloads_existing_files(self, temp_dir):
        """Should download files that exist in GCS."""
        mock_storage = MagicMock()
        service = LyricsCacheService(storage=mock_storage)

        # Configure mock to simulate some files exist in GCS
        def file_exists(path):
            # Simulate audioshake_abc123_raw.json exists
            return "audioshake_abc123_raw.json" in path

        mock_storage.file_exists.side_effect = file_exists

        stats = service.sync_cache_from_gcs(
            local_cache_dir=temp_dir,
            audio_hash="abc123",
            lyrics_hash="def456",
        )

        # Should have downloaded 1 file (audioshake_abc123_raw.json)
        assert stats["downloaded"] == 1
        # Should have not found the rest
        assert stats["not_found"] > 0
        assert stats["errors"] == 0

        # Verify download_file was called for the existing file
        mock_storage.download_file.assert_called_once()

    def test_sync_cache_from_gcs_creates_directory(self, temp_dir):
        """Should create the local cache directory if it doesn't exist."""
        mock_storage = MagicMock()
        mock_storage.file_exists.return_value = False
        service = LyricsCacheService(storage=mock_storage)

        cache_dir = os.path.join(temp_dir, "new_cache_dir")
        assert not os.path.exists(cache_dir)

        service.sync_cache_from_gcs(
            local_cache_dir=cache_dir,
            audio_hash="abc123",
            lyrics_hash="def456",
        )

        assert os.path.exists(cache_dir)

    def test_sync_cache_from_gcs_handles_errors(self, temp_dir):
        """Should handle download errors gracefully."""
        mock_storage = MagicMock()
        mock_storage.file_exists.return_value = True
        mock_storage.download_file.side_effect = Exception("Network error")
        service = LyricsCacheService(storage=mock_storage)

        stats = service.sync_cache_from_gcs(
            local_cache_dir=temp_dir,
            audio_hash="abc123",
            lyrics_hash="def456",
        )

        # All files should have errors
        assert stats["errors"] > 0
        assert stats["downloaded"] == 0


class TestSyncCacheToGCS:
    """Tests for uploading cache to GCS."""

    def test_sync_cache_to_gcs_uploads_new_files(self, temp_dir):
        """Should upload files that don't exist in GCS."""
        mock_storage = MagicMock()
        mock_storage.file_exists.return_value = False
        service = LyricsCacheService(storage=mock_storage)

        # Create a cache file in temp_dir
        cache_file = os.path.join(temp_dir, "audioshake_abc123_raw.json")
        with open(cache_file, "w") as f:
            json.dump({"test": "data"}, f)

        stats = service.sync_cache_to_gcs(
            local_cache_dir=temp_dir,
            audio_hash="abc123",
            lyrics_hash="def456",
        )

        assert stats["uploaded"] == 1
        mock_storage.upload_file.assert_called_once()

    def test_sync_cache_to_gcs_skips_existing_files(self, temp_dir):
        """Should skip files that already exist in GCS."""
        mock_storage = MagicMock()
        mock_storage.file_exists.return_value = True
        service = LyricsCacheService(storage=mock_storage)

        # Create a cache file in temp_dir
        cache_file = os.path.join(temp_dir, "audioshake_abc123_raw.json")
        with open(cache_file, "w") as f:
            json.dump({"test": "data"}, f)

        stats = service.sync_cache_to_gcs(
            local_cache_dir=temp_dir,
            audio_hash="abc123",
            lyrics_hash="def456",
        )

        assert stats["uploaded"] == 0
        assert stats["skipped"] == 1
        mock_storage.upload_file.assert_not_called()

    def test_sync_cache_to_gcs_ignores_unexpected_files(self, temp_dir):
        """Should ignore files that don't match expected cache patterns."""
        mock_storage = MagicMock()
        mock_storage.file_exists.return_value = False
        service = LyricsCacheService(storage=mock_storage)

        # Create an unexpected file
        unexpected_file = os.path.join(temp_dir, "random_file.txt")
        with open(unexpected_file, "w") as f:
            f.write("not a cache file")

        # Create a file with wrong hash
        wrong_hash_file = os.path.join(temp_dir, "audioshake_wrong_hash_raw.json")
        with open(wrong_hash_file, "w") as f:
            json.dump({"test": "data"}, f)

        stats = service.sync_cache_to_gcs(
            local_cache_dir=temp_dir,
            audio_hash="abc123",
            lyrics_hash="def456",
        )

        # Should not upload any files
        assert stats["uploaded"] == 0
        mock_storage.upload_file.assert_not_called()

    def test_sync_cache_to_gcs_handles_missing_directory(self, temp_dir):
        """Should handle missing cache directory gracefully."""
        mock_storage = MagicMock()
        service = LyricsCacheService(storage=mock_storage)

        stats = service.sync_cache_to_gcs(
            local_cache_dir=os.path.join(temp_dir, "nonexistent"),
            audio_hash="abc123",
            lyrics_hash="def456",
        )

        assert stats["uploaded"] == 0
        assert stats["skipped"] == 0
        assert stats["errors"] == 0

    def test_sync_cache_to_gcs_handles_upload_errors(self, temp_dir):
        """Should handle upload errors gracefully."""
        mock_storage = MagicMock()
        mock_storage.file_exists.return_value = False
        mock_storage.upload_file.side_effect = Exception("Upload failed")
        service = LyricsCacheService(storage=mock_storage)

        # Create a cache file
        cache_file = os.path.join(temp_dir, "audioshake_abc123_raw.json")
        with open(cache_file, "w") as f:
            json.dump({"test": "data"}, f)

        stats = service.sync_cache_to_gcs(
            local_cache_dir=temp_dir,
            audio_hash="abc123",
            lyrics_hash="def456",
        )

        assert stats["errors"] == 1
        assert stats["uploaded"] == 0


class TestGCSPathStructure:
    """Tests for GCS path structure."""

    def test_gcs_cache_prefix(self):
        """GCS cache prefix should be correct."""
        assert LyricsCacheService.GCS_CACHE_PREFIX == "lyrics-transcriber-cache/"

    def test_sync_uses_correct_gcs_paths(self, temp_dir):
        """Should use correct GCS paths when downloading/uploading."""
        mock_storage = MagicMock()
        mock_storage.file_exists.return_value = True
        service = LyricsCacheService(storage=mock_storage)

        service.sync_cache_from_gcs(
            local_cache_dir=temp_dir,
            audio_hash="abc123",
            lyrics_hash="def456",
        )

        # Check that file_exists was called with correct GCS path prefix
        calls = mock_storage.file_exists.call_args_list
        for call in calls:
            gcs_path = call[0][0]
            assert gcs_path.startswith("lyrics-transcriber-cache/")


class TestEndToEnd:
    """End-to-end tests for cache sync workflow."""

    def test_round_trip_cache_sync(self, temp_dir):
        """Test uploading and then downloading the same cache file."""
        # We'll simulate this with two separate temp dirs
        upload_dir = os.path.join(temp_dir, "upload")
        download_dir = os.path.join(temp_dir, "download")
        os.makedirs(upload_dir)
        os.makedirs(download_dir)

        # Create a test cache file
        test_data = {"transcription": "test data", "words": [1, 2, 3]}
        cache_filename = "audioshake_abc123_raw.json"
        upload_path = os.path.join(upload_dir, cache_filename)
        with open(upload_path, "w") as f:
            json.dump(test_data, f)

        # Create mock that tracks uploaded files
        uploaded_files = {}

        def mock_upload(local_path, gcs_path):
            with open(local_path, "r") as f:
                uploaded_files[gcs_path] = f.read()
            return gcs_path

        def mock_download(gcs_path, local_path):
            if gcs_path in uploaded_files:
                with open(local_path, "w") as f:
                    f.write(uploaded_files[gcs_path])
            return local_path

        def mock_exists(gcs_path):
            return gcs_path in uploaded_files

        mock_storage = MagicMock()
        mock_storage.upload_file.side_effect = mock_upload
        mock_storage.download_file.side_effect = mock_download
        mock_storage.file_exists.side_effect = mock_exists

        service = LyricsCacheService(storage=mock_storage)

        # Upload
        upload_stats = service.sync_cache_to_gcs(upload_dir, "abc123", "def456")
        assert upload_stats["uploaded"] == 1

        # Download to new location
        download_stats = service.sync_cache_from_gcs(download_dir, "abc123", "def456")
        assert download_stats["downloaded"] == 1

        # Verify downloaded content matches
        downloaded_path = os.path.join(download_dir, cache_filename)
        with open(downloaded_path, "r") as f:
            downloaded_data = json.load(f)
        assert downloaded_data == test_data
