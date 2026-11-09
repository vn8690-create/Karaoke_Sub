"""
Integration tests for countdown padding across the full worker pipeline.

These tests use Firestore emulator to verify real state updates flow correctly
between workers. They mock only external services (Modal, AudioShake, etc.)
but use real Firestore for state persistence.

Run with: scripts/run-emulator-tests.sh
"""

import pytest
import os
from datetime import datetime, UTC
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile

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
    from backend.services.storage_service import StorageService
    from backend.services.firestore_service import FirestoreService


class TestCountdownStateFlowThroughPipeline:
    """
    Integration tests verifying countdown state flows correctly through
    the full worker pipeline: lyrics -> render_video -> video.
    """

    @pytest.fixture
    def job_manager(self):
        """Create a real JobManager using emulator."""
        return JobManager()

    @pytest.fixture
    def firestore_service(self):
        """Create a real FirestoreService using emulator for direct job operations."""
        return FirestoreService()

    @pytest.fixture
    def storage_service(self):
        """Create a real StorageService using emulator."""
        return StorageService()

    @pytest.fixture
    def job_with_early_start_song(self, job_manager, firestore_service):
        """
        Create a job where lyrics start within 3 seconds (needs countdown).

        This simulates a song where the first word appears at 0.5 seconds,
        which triggers countdown processing.
        """
        job_id = f"countdown-test-early-{datetime.now(UTC).timestamp()}"

        job = Job(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test Artist",
            title="Early Start Song",
            state_data={
                'lyrics_metadata': {
                    'has_countdown_padding': False,
                    'countdown_padding_seconds': 0.0,
                    'first_word_start_time': 0.5,  # Within 3s threshold
                }
            }
        )

        # Create job in Firestore directly
        firestore_service.create_job(job)

        yield job

        # Cleanup
        try:
            firestore_service.delete_job(job_id)
        except Exception:
            pass

    @pytest.fixture
    def job_with_late_start_song(self, job_manager, firestore_service):
        """
        Create a job where lyrics start after 3 seconds (no countdown needed).

        This simulates a song where the first word appears at 5.0 seconds,
        which does NOT trigger countdown processing.
        """
        job_id = f"countdown-test-late-{datetime.now(UTC).timestamp()}"

        job = Job(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test Artist",
            title="Late Start Song",
            state_data={
                'lyrics_metadata': {
                    'has_countdown_padding': False,
                    'countdown_padding_seconds': 0.0,
                    'first_word_start_time': 5.0,  # After 3s threshold
                }
            }
        )

        firestore_service.create_job(job)

        yield job

        try:
            firestore_service.delete_job(job_id)
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_state_update_persists_to_firestore(self, job_with_early_start_song, job_manager):
        """
        Verify that state updates via update_state_data() persist to Firestore.

        This is the foundation of the countdown state flow - if updates don't
        persist, video_worker can't read the countdown state.
        """
        job = job_with_early_start_song

        # Simulate render_video_worker updating countdown state
        new_lyrics_metadata = {
            'has_countdown_padding': True,
            'countdown_padding_seconds': 3.0,
            'first_word_start_time': 0.5,
        }

        job_manager.update_state_data(job.job_id, 'lyrics_metadata', new_lyrics_metadata)

        # Read job back from Firestore
        refreshed_job = job_manager.get_job(job.job_id)

        assert refreshed_job is not None
        lyrics_metadata = refreshed_job.state_data.get('lyrics_metadata', {})
        assert lyrics_metadata.get('has_countdown_padding') is True
        assert lyrics_metadata.get('countdown_padding_seconds') == 3.0

    @pytest.mark.asyncio
    async def test_video_worker_reads_updated_state(self, job_with_early_start_song, job_manager):
        """
        Verify that video_worker can read countdown state after render_video_worker sets it.

        This simulates the full flow:
        1. render_video_worker sets has_countdown_padding=True
        2. video_worker reads the state and extracts countdown_padding_seconds
        """
        job = job_with_early_start_song

        # Step 1: render_video_worker updates state
        new_lyrics_metadata = {
            'has_countdown_padding': True,
            'countdown_padding_seconds': 3.0,
        }
        job_manager.update_state_data(job.job_id, 'lyrics_metadata', new_lyrics_metadata)

        # Step 2: video_worker reads state (simulated)
        refreshed_job = job_manager.get_job(job.job_id)

        # video_worker extraction logic
        lyrics_metadata = refreshed_job.state_data.get('lyrics_metadata', {})
        countdown_padding_seconds = None
        if lyrics_metadata.get('has_countdown_padding'):
            countdown_padding_seconds = lyrics_metadata.get('countdown_padding_seconds', 3.0)

        assert countdown_padding_seconds == 3.0

    @pytest.mark.asyncio
    async def test_no_countdown_state_when_not_needed(self, job_with_late_start_song, job_manager):
        """
        Verify that when song doesn't need countdown, state remains False.
        """
        job = job_with_late_start_song

        # Read initial state
        current_job = job_manager.get_job(job.job_id)
        lyrics_metadata = current_job.state_data.get('lyrics_metadata', {})

        assert lyrics_metadata.get('has_countdown_padding') is False
        assert lyrics_metadata.get('countdown_padding_seconds') == 0.0

        # video_worker extraction logic
        countdown_padding_seconds = None
        if lyrics_metadata.get('has_countdown_padding'):
            countdown_padding_seconds = lyrics_metadata.get('countdown_padding_seconds', 3.0)

        assert countdown_padding_seconds is None


class TestCountdownStateTransitions:
    """Tests for state transitions during countdown processing."""

    @pytest.fixture
    def job_manager(self):
        return JobManager()

    @pytest.fixture
    def firestore_service(self):
        return FirestoreService()

    @pytest.mark.asyncio
    async def test_state_transitions_preserve_countdown_info(self, job_manager, firestore_service):
        """
        Countdown state should survive job state transitions.

        When job moves from GENERATING_VIDEO to ENCODING,
        the lyrics_metadata should remain intact.
        """
        job_id = f"transition-test-{datetime.now(UTC).timestamp()}"

        try:
            # Create job in GENERATING_VIDEO state (valid predecessor to ENCODING)
            job = Job(
                job_id=job_id,
                status=JobStatus.GENERATING_VIDEO,
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

            # Transition to ENCODING (valid transition from GENERATING_VIDEO)
            job_manager.transition_to_state(
                job_id=job_id,
                new_status=JobStatus.ENCODING,
                progress=75,
                message="Starting encoding"
            )

            # Read job and verify countdown state preserved
            refreshed_job = job_manager.get_job(job_id)
            lyrics_metadata = refreshed_job.state_data.get('lyrics_metadata', {})

            assert lyrics_metadata.get('has_countdown_padding') is True
            assert lyrics_metadata.get('countdown_padding_seconds') == 3.0

        finally:
            try:
                firestore_service.delete_job(job_id)
            except Exception:
                pass


class TestWorkerStateDataIsolation:
    """Tests that different workers don't overwrite each other's state data."""

    @pytest.fixture
    def job_manager(self):
        return JobManager()

    @pytest.fixture
    def firestore_service(self):
        return FirestoreService()

    @pytest.mark.asyncio
    async def test_lyrics_metadata_not_overwritten_by_other_updates(self, job_manager, firestore_service):
        """
        Updating video_worker state should NOT overwrite lyrics_metadata.

        Each worker stores its state in separate keys within state_data.
        """
        job_id = f"isolation-test-{datetime.now(UTC).timestamp()}"

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

            # Update video_worker state (different key)
            job_manager.update_state_data(job_id, 'video_worker', {
                'instrumental_source': 'clean',
                'encoding_started': True,
            })

            # Verify lyrics_metadata preserved
            refreshed_job = job_manager.get_job(job_id)
            lyrics_metadata = refreshed_job.state_data.get('lyrics_metadata', {})

            assert lyrics_metadata.get('has_countdown_padding') is True
            assert lyrics_metadata.get('countdown_padding_seconds') == 3.0

            # Verify video_worker state also present
            video_worker_state = refreshed_job.state_data.get('video_worker', {})
            assert video_worker_state.get('instrumental_source') == 'clean'

        finally:
            try:
                firestore_service.delete_job(job_id)
            except Exception:
                pass


class TestCountdownStateUpdateCodeExists:
    """
    Verify the render_video_worker code contains the state update logic.

    This is a code inspection test rather than an execution test, since running
    the actual worker requires too much complex setup (audio files, corrections, etc.).
    The actual state update behavior is verified by the unit tests.
    """

    def test_render_video_worker_has_state_update_code(self):
        """
        Verify render_video_worker.py contains the code to update lyrics_metadata
        when countdown padding is added.

        This ensures the fix hasn't been accidentally removed.
        """
        import inspect
        from backend.workers import render_video_worker

        source = inspect.getsource(render_video_worker)

        # The fix should include updating lyrics_metadata when padding_added is True
        assert "update_state_data" in source, (
            "render_video_worker must call update_state_data"
        )
        assert "has_countdown_padding" in source, (
            "render_video_worker must set has_countdown_padding"
        )
        assert "countdown_padding_seconds" in source, (
            "render_video_worker must set countdown_padding_seconds"
        )
        assert "lyrics_metadata" in source, (
            "render_video_worker must update lyrics_metadata"
        )
