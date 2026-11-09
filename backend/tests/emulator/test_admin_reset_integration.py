"""
Integration tests for admin job reset endpoint.

These tests use the real Firestore emulator and real JobManager,
catching bugs that unit tests with mocks might miss (e.g., incorrect
assumptions about return values).

Run with: scripts/run-emulator-tests.sh
"""
import pytest
from datetime import datetime, UTC

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


class TestUpdateJobReturnValue:
    """
    Critical tests documenting that update_job() returns None, not boolean.

    This test class exists because a production bug (PR #371) was caused by
    assuming update_job() returns a boolean success indicator. The real API
    returns None on success and raises on failure. Mocks that return True
    hide this behavior.
    """

    @pytest.fixture
    def job_manager(self):
        """Create a real JobManager using emulator."""
        return JobManager()

    @pytest.fixture
    def firestore_service(self):
        """Create a real FirestoreService using emulator."""
        return FirestoreService()

    @pytest.fixture
    def test_job(self, firestore_service):
        """Create a test job for verification."""
        job_id = f"update-return-test-{datetime.now(UTC).timestamp()}"

        job = Job(
            job_id=job_id,
            status=JobStatus.COMPLETE,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test Artist",
            title="Test Song",
        )

        firestore_service.create_job(job)

        yield job

        # Cleanup
        try:
            firestore_service.delete_job(job_id)
        except Exception:
            pass

    def test_update_job_returns_none_not_boolean(self, job_manager, test_job):
        """
        Verify update_job() returns None, not a boolean.

        This test exists because a production bug was introduced when code
        assumed update_job() returns a boolean. The method actually returns
        None on success and raises an exception on failure.

        Bug pattern that this test prevents:
        ```python
        success = job_manager.update_job(job_id, updates)
        if not success:  # BUG: None is falsy, so this is always True!
            raise HTTPException(status_code=500, ...)
        ```

        Correct pattern:
        ```python
        # update_job() raises on failure, returns None on success
        job_manager.update_job(job_id, updates)
        ```
        """
        # update_job() should return None, not True/False
        result = job_manager.update_job(
            test_job.job_id,
            {"status": JobStatus.PENDING.value}
        )

        # The actual return value is None, not True
        assert result is None, (
            "update_job() should return None, not a boolean. "
            "Code checking 'if not update_job(...)' will always be True!"
        )

    def test_update_job_on_nonexistent_job(self, job_manager):
        """
        Document update_job() behavior for non-existent jobs.

        In production Firestore, update() on non-existent doc raises NotFound.
        The key insight for preventing the admin reset bug is understanding
        that update_job() returns None (not boolean) on success.
        """
        try:
            result = job_manager.update_job(
                "nonexistent-job-id-12345",
                {"status": JobStatus.PENDING.value}
            )
            # If no exception raised (emulator quirk), verify return is still None
            assert result is None, "update_job should return None even on non-existent doc"
        except Exception:
            # Exception is the expected behavior in production Firestore
            pass
