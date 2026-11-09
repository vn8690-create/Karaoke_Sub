"""
LyricsTranscriber cache synchronization with GCS.

This service persists LyricsTranscriber's cache files to GCS so that
cloud workers (Cloud Run instances) can share cache across containers.

Cache files are stored flat in GCS under lyrics-transcriber-cache/ prefix:
- Transcription: {provider}_{audio_hash}_raw.json, {provider}_{audio_hash}_converted.json
- Lyrics: {provider}_{artist_title_hash}_raw.json, {provider}_{artist_title_hash}_converted.json

Hash computation matches LyricsTranscriber's implementation exactly:
- Audio hash: MD5 of audio file bytes
- Lyrics hash: MD5 of "{artist.lower()}_{title.lower()}"
"""
import hashlib
import logging
import os
from typing import Dict, List, Optional

from backend.services.storage_service import StorageService

logger = logging.getLogger(__name__)


# Providers that use audio file hash as cache key
TRANSCRIPTION_PROVIDERS = ["audioshake", "whisper", "localwhisper"]

# Providers that use artist+title hash as cache key
LYRICS_PROVIDERS = ["genius", "spotify", "lrclib", "musixmatch"]

# Cache file suffixes
CACHE_SUFFIXES = ["raw", "converted"]


class LyricsCacheService:
    """Service to sync LyricsTranscriber cache with GCS."""

    GCS_CACHE_PREFIX = "lyrics-transcriber-cache/"

    def __init__(self, storage: Optional[StorageService] = None):
        """Initialize the cache service.

        Args:
            storage: StorageService instance. If None, creates a new one.
        """
        self.storage = storage or StorageService()

    def compute_audio_hash(self, audio_path: str) -> str:
        """Compute MD5 hash of audio file bytes.

        This matches LyricsTranscriber's _get_file_hash() method exactly.

        Args:
            audio_path: Path to the audio file.

        Returns:
            MD5 hex digest of the file contents.
        """
        md5_hash = hashlib.md5()
        with open(audio_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()

    def compute_lyrics_hash(self, artist: str, title: str) -> str:
        """Compute MD5 hash of artist and title.

        This matches LyricsTranscriber's _get_artist_title_hash() method exactly.

        Args:
            artist: Artist name.
            title: Track title.

        Returns:
            MD5 hex digest of "{artist.lower()}_{title.lower()}".
        """
        combined = f"{artist.lower()}_{title.lower()}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _get_cache_filenames(
        self, providers: List[str], hash_value: str
    ) -> List[str]:
        """Generate list of possible cache filenames for given providers and hash.

        Args:
            providers: List of provider names (e.g., ["audioshake", "whisper"]).
            hash_value: The hash to use in filenames.

        Returns:
            List of filenames like ["audioshake_abc123_raw.json", ...].
        """
        filenames = []
        for provider in providers:
            for suffix in CACHE_SUFFIXES:
                filenames.append(f"{provider}_{hash_value}_{suffix}.json")
        return filenames

    def sync_cache_from_gcs(
        self,
        local_cache_dir: str,
        audio_hash: str,
        lyrics_hash: str,
    ) -> Dict[str, int]:
        """Download relevant cache files from GCS to local directory.

        Downloads cache files for both transcription (audio hash) and
        lyrics (artist+title hash) providers.

        Args:
            local_cache_dir: Local directory to download cache files to.
            audio_hash: MD5 hash of audio file.
            lyrics_hash: MD5 hash of artist+title.

        Returns:
            Dict with counts: {"downloaded": N, "not_found": M, "errors": E}
        """
        os.makedirs(local_cache_dir, exist_ok=True)

        stats = {"downloaded": 0, "not_found": 0, "errors": 0}

        # Get all possible cache filenames
        transcription_files = self._get_cache_filenames(
            TRANSCRIPTION_PROVIDERS, audio_hash
        )
        lyrics_files = self._get_cache_filenames(LYRICS_PROVIDERS, lyrics_hash)
        all_files = transcription_files + lyrics_files

        for filename in all_files:
            gcs_path = f"{self.GCS_CACHE_PREFIX}{filename}"
            local_path = os.path.join(local_cache_dir, filename)

            try:
                if self.storage.file_exists(gcs_path):
                    self.storage.download_file(gcs_path, local_path)
                    logger.info(f"Cache hit: downloaded {filename}")
                    stats["downloaded"] += 1
                else:
                    logger.debug(f"Cache miss: {filename} not in GCS")
                    stats["not_found"] += 1
            except Exception as e:
                logger.warning(f"Error downloading cache file {filename}: {e}")
                stats["errors"] += 1

        logger.info(
            f"Cache sync from GCS complete: "
            f"{stats['downloaded']} downloaded, "
            f"{stats['not_found']} not found, "
            f"{stats['errors']} errors"
        )
        return stats

    def sync_cache_to_gcs(
        self,
        local_cache_dir: str,
        audio_hash: str,
        lyrics_hash: str,
    ) -> Dict[str, int]:
        """Upload new cache files from local directory to GCS.

        Only uploads files that match expected cache patterns for the given
        hashes and don't already exist in GCS.

        Args:
            local_cache_dir: Local directory with cache files.
            audio_hash: MD5 hash of audio file.
            lyrics_hash: MD5 hash of artist+title.

        Returns:
            Dict with counts: {"uploaded": N, "skipped": M, "errors": E}
        """
        stats = {"uploaded": 0, "skipped": 0, "errors": 0}

        if not os.path.exists(local_cache_dir):
            logger.warning(f"Local cache dir does not exist: {local_cache_dir}")
            return stats

        # Get all possible cache filenames we're interested in
        transcription_files = self._get_cache_filenames(
            TRANSCRIPTION_PROVIDERS, audio_hash
        )
        lyrics_files = self._get_cache_filenames(LYRICS_PROVIDERS, lyrics_hash)
        expected_files = set(transcription_files + lyrics_files)

        # Check each file in local cache dir
        for filename in os.listdir(local_cache_dir):
            # Only process files we expect (matching our hash patterns)
            if filename not in expected_files:
                continue

            local_path = os.path.join(local_cache_dir, filename)
            if not os.path.isfile(local_path):
                continue

            gcs_path = f"{self.GCS_CACHE_PREFIX}{filename}"

            try:
                # Skip if already exists in GCS (same hash = same content)
                if self.storage.file_exists(gcs_path):
                    logger.debug(f"Cache file already in GCS: {filename}")
                    stats["skipped"] += 1
                    continue

                self.storage.upload_file(local_path, gcs_path)
                logger.info(f"Uploaded cache file: {filename}")
                stats["uploaded"] += 1
            except Exception as e:
                logger.warning(f"Error uploading cache file {filename}: {e}")
                stats["errors"] += 1

        logger.info(
            f"Cache sync to GCS complete: "
            f"{stats['uploaded']} uploaded, "
            f"{stats['skipped']} skipped (already exist), "
            f"{stats['errors']} errors"
        )
        return stats
