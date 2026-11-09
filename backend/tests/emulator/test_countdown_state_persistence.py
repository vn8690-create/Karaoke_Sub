"""
Tests that countdown state survives worker boundaries and job reloads.

These tests verify that countdown state persists correctly in Firestore
and can be read across different worker invocations.

Run with: scripts/run-emulator-tests.sh
"""

import pytest
import os
from datetime import datetime, UTC
from unittest.mock import MagicMock, AsyncMock, patch
import time

# Import base fixtures from conftest
from backend.tests.emulator.conftest import emulators_running

# Skip all tests if emulators aren't running
pytestmark = pytest.mark.skipif(
    not emulators_running(),
    reason="GCP emulators not running. Start with: scripts/start-emulators.sh"
)

# Only import if emulators are running
if emulators_running():
    from backend.models.job import Job, JobStatus
    from backend.services.job_manager import JobManager
    from backend.services.firestore_service import FirestoreService


class TestCountdownStatePersistence:
    """Tests that countdown state persists between worker boundaries."""

    @pytest.fixture
    def job_manager(self):
        """Create a real JobManager using emulator."""
        return JobManager()

    @pytest.fixture
    def firestore_service(self):
        """Create a real FirestoreService using emulator for direct job operations."""
        return FirestoreService()

    @pytest.mark.asyncio
    async def test_state_persists_between_render_and_video_workers(self, job_manager, firestore_service):
        """
        State set by render_video_worker is readable by video_worker.

        Simulates:
        1. render_video_worker completes, sets has_countdown_padding=True
        2. Some time passes (worker boundary)
        3. video_worker starts, reads has_countdown_padding
        """
        job_id = f"persist-test-{datetime.now(UTC).timestamp()}"

        try:
            # Create initial job (as lyrics_worker would leave it)
            job = Job(
                job_id=job_id,
                status=JobStatus.RENDERING_VIDEO,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                artist="Test",
                title="Test",
                state_data={
                    'lyrics_metadata': {
                        'has_countdown_padding': False,
                        'countdown_padding_seconds': 0.0,
                    }
                }
            )
            firestore_service.create_job(job)

            # === render_video_worker completes ===
            job_manager.update_state_data(job_id, 'lyrics_metadata', {
                'has_countdown_padding': True,
                'countdown_padding_seconds': 3.0,
            })

            # Simulate worker boundary (job is re-fetched from Firestore)
            # Create a NEW JobManager instance to simulate video_worker starting
            video_job_manager = JobManager()

            # === video_worker starts ===
            job_from_video_worker = video_job_manager.get_job(job_id)

            # video_worker reads countdown state
            lyrics_metadata = job_from_video_worker.state_data.get('lyrics_metadata', {})
            countdown_padding_seconds = None
            if lyrics_metadata.get('has_countdown_padding'):
                countdown_padding_seconds = lyrics_metadata.get('countdown_padding_seconds', 3.0)

            assert countdown_padding_seconds == 3.0, (
                "Countdown state did not persist between workers"
            )

        finally:
            try:
                firestore_service.delete_job(job_id)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_state_survives_job_reload(self, job_manager, firestore_service):
        """
        State persists when job is reloaded from Firestore multiple times.
        """
        job_id = f"reload-test-{datetime.now(UTC).timestamp()}"

        try:
            # Create job with countdown state
            job = Job(
                job_id=job_id,
                status=JobStatus.ENCODING,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                artist="Test",
                title="Test",
                state_data={
                    'lyrics_metadata': {
                        'has_countdown_padding': True,
                        'countdown_padding_seconds': 3.0,
                    }
                }
            )
            firestore_service.create_job(job)

            # Reload job multiple times
            for i in range(3):
                reloaded_job = job_manager.get_job(job_id)

                lyrics_metadata = reloaded_job.state_data.get('lyrics_metadata', {})
                assert lyrics_metadata.get('has_countdown_padding') is True, (
                    f"Countdown state lost after reload #{i+1}"
                )
                assert lyrics_metadata.get('countdown_padding_seconds') == 3.0, (
                    f"Countdown duration changed after reload #{i+1}"
                )

        finally:
            try:
                firestore_service.delete_job(job_id)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_partial_state_update_preserves_other_fields(self, job_manager, firestore_service):
        """
        Updating one field in state_data doesn't affect other fields.
        """
        job_id = f"partial-test-{datetime.now(UTC).timestamp()}"

        try:
            # Create job with multiple state fields
            job = Job(
                job_id=job_id,
                status=JobStatus.ENCODING,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                artist="Test",
                title="Test",
                state_data={
                    'lyrics_metadata': {
                        'has_countdown_padding': True,
                        'countdown_padding_seconds': 3.0,
                        'original_field': 'should_be_preserved',
                    },
                    'audio_complete': True,
                }
            )
            firestore_service.create_job(job)

            # Update video_worker state (different key)
            job_manager.update_state_data(job_id, 'video_worker', {
                'encoding_started': True,
            })

            # Verify lyrics_metadata is completely preserved
            reloaded_job = job_manager.get_job(job_id)
            lyrics_metadata = reloaded_job.state_data.get('lyrics_metadata', {})

            assert lyrics_metadata.get('has_countdown_padding') is True
            assert lyrics_metadata.get('countdown_padding_seconds') == 3.0
            assert lyrics_metadata.get('original_field') == 'should_be_preserved'
            assert reloaded_job.state_data.get('audio_complete') is True

        finally:
            try:
                firestore_service.delete_job(job_id)
            except Exception:
                pass


class TestCountdownStateConsistency:
    """Tests for state consistency under concurrent access patterns."""

    @pytest.fixture
    def job_manager(self):
        return JobManager()

    @pytest.fixture
    def firestore_service(self):
        return FirestoreService()

    @pytest.mark.asyncio
    async def test_concurrent_reads_see_same_state(self, job_manager, firestore_service):
        """
        Multiple concurrent reads should see the same countdown state.
        """
        job_id = f"concurrent-test-{datetime.now(UTC).timestamp()}"

        try:
            # Create job with countdown
            job = Job(
                job_id=job_id,
                status=JobStatus.ENCODING,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                artist="Test",
                title="Test",
                state_data={
                    'lyrics_metadata': {
                        'has_countdown_padding': True,
                        'countdown_padding_seconds': 3.0,
                    }
                }
            )
            firestore_service.create_job(job)

            # Simulate concurrent reads
            reads = []
            for _ in range(5):
                reloaded = job_manager.get_job(job_id)
                lyrics_metadata = reloaded.state_data.get('lyrics_metadata', {})
                reads.append({
                    'has_countdown_padding': lyrics_metadata.get('has_countdown_padding'),
                    'countdown_padding_seconds': lyrics_metadata.get('countdown_padding_seconds'),
                })

            # All reads should be consistent
            for read in reads:
                assert read['has_countdown_padding'] is True
                assert read['countdown_padding_seconds'] == 3.0

        finally:
            try:
                firestore_service.delete_job(job_id)
            except Exception:
                pass


class TestCountdownStateMigration:
    """Tests for handling jobs with missing or old countdown state format."""

    @pytest.fixture
    def job_manager(self):
        return JobManager()

    @pytest.fixture
    def firestore_service(self):
        return FirestoreService()

    @pytest.mark.asyncio
    async def test_handles_missing_lyrics_metadata(self, job_manager, firestore_service):
        """
        Jobs without lyrics_metadata should be handled gracefully.

        This can happen for jobs created before the countdown feature.
        """
        job_id = f"migration-test-{datetime.now(UTC).timestamp()}"

        try:
            # Create job WITHOUT lyrics_metadata (old format)
            job = Job(
                job_id=job_id,
                status=JobStatus.ENCODING,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                artist="Test",
                title="Test",
                state_data={}  # No lyrics_metadata
            )
            firestore_service.create_job(job)

            # video_worker logic should handle this
            reloaded = job_manager.get_job(job_id)
            lyrics_metadata = reloaded.state_data.get('lyrics_metadata', {})
            countdown_padding_seconds = None
            if lyrics_metadata.get('has_countdown_padding'):
                countdown_padding_seconds = lyrics_metadata.get('countdown_padding_seconds', 3.0)

            # Should return None, not crash
            assert countdown_padding_seconds is None

        finally:
            try:
                firestore_service.delete_job(job_id)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_handles_missing_countdown_fields(self, job_manager, firestore_service):
        """
        Jobs with lyrics_metadata but missing countdown fields handled gracefully.
        """
        job_id = f"fields-test-{datetime.now(UTC).timestamp()}"

        try:
            # Create job with lyrics_metadata but no countdown fields
            job = Job(
                job_id=job_id,
                status=JobStatus.ENCODING,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                artist="Test",
                title="Test",
                state_data={
                    'lyrics_metadata': {
                        'some_other_field': 'value',
                        # No has_countdown_padding
                        # No countdown_padding_seconds
                    }
                }
            )
            firestore_service.create_job(job)

            reloaded = job_manager.get_job(job_id)
            lyrics_metadata = reloaded.state_data.get('lyrics_metadata', {})
            countdown_padding_seconds = None
            if lyrics_metadata.get('has_countdown_padding'):
                countdown_padding_seconds = lyrics_metadata.get('countdown_padding_seconds', 3.0)

            # Should return None when has_countdown_padding is missing/falsy
            assert countdown_padding_seconds is None

        finally:
            try:
                firestore_service.delete_job(job_id)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_handles_countdown_true_without_duration(self, job_manager, firestore_service):
        """
        If has_countdown_padding=True but duration missing, default to 3.0.
        """
        job_id = f"default-duration-test-{datetime.now(UTC).timestamp()}"

        try:
            job = Job(
                job_id=job_id,
                status=JobStatus.ENCODING,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                artist="Test",
                title="Test",
                state_data={
                    'lyrics_metadata': {
                        'has_countdown_padding': True,
                        # countdown_padding_seconds intentionally missing
                    }
                }
            )
            firestore_service.create_job(job)

            reloaded = job_manager.get_job(job_id)
            lyrics_metadata = reloaded.state_data.get('lyrics_metadata', {})
            countdown_padding_seconds = None
            if lyrics_metadata.get('has_countdown_padding'):
                countdown_padding_seconds = lyrics_metadata.get('countdown_padding_seconds', 3.0)

            # Should default to 3.0
            assert countdown_padding_seconds == 3.0

        finally:
            try:
                firestore_service.delete_job(job_id)
            except Exception:
                pass
