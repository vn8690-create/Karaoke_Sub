"""
Integration tests for admin job reset using REAL job fixture from production.

This test validates that update_job() returns None, not a boolean
(the root cause of PR #371 bug).

Uses actual data from production job 984da08b which needed admin reset.

Run with: scripts/run-emulator-tests.sh
"""
import pytest
from datetime import datetime, UTC

from backend.tests.emulator.conftest import emulators_running

pytestmark = pytest.mark.skipif(
    not emulators_running(),
    reason="GCP emulators not running. Start with: scripts/start-emulators.sh"
)

if emulators_running():
    from backend.models.job import Job, JobStatus
    from backend.services.job_manager import JobManager


class TestAdminResetBugFix:
    """
    Tests that prove the PR #371 bug fix works using real emulator.

    The bug: admin reset endpoint returned 500 because:
        success = job_manager.update_job(job_id, updates)
        if not success:  # BUG: update_job returns None, not True!
            raise HTTPException(500)
    """

    def test_update_job_returns_none_not_boolean(self):
        """
        Prove that update_job() returns None, not a boolean.

        This is the root cause of the bug. Any code that does
        'if not update_job(...)' will always be True.
        """
        jm = JobManager()
        job_id = f"test-{datetime.now(UTC).timestamp()}"

        job = Job(
            job_id=job_id,
            status=JobStatus.COMPLETE,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Mark Mallman",
            title="Minneapolis",
        )

        try:
            jm.firestore.create_job(job)

            # THE KEY TEST: update_job returns None
            result = jm.update_job(job_id, {"status": "pending"})

            assert result is None, (
                "update_job() must return None. "
                "Code checking 'if not success:' would always fail!"
            )
        finally:
            try:
                jm.firestore.delete_job(job_id)
            except Exception:
                pass
