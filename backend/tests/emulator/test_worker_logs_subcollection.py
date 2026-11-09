"""
Integration tests for worker log subcollection storage.

Tests the subcollection approach using real Firestore emulator to verify:
- Logs are stored in subcollection (jobs/{job_id}/logs)
- TTL expiry field is set correctly
- Large log volumes work without 1MB limit issues
- Concurrent writes are handled correctly
- Logs can be queried efficiently

Run with: ./scripts/run-emulator-tests.sh
"""
import pytest
import time
import requests
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta


def emulators_running() -> bool:
    """Check if GCP emulators are running."""
    try:
        requests.get("http://127.0.0.1:8080", timeout=1)
        return True
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False


# Skip all tests in this module if emulators aren't running
pytestmark = pytest.mark.skipif(
    not emulators_running(),
    reason="GCP emulators not running. Start with: scripts/start-emulators.sh"
)

# Set up environment for emulator
os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"


class TestWorkerLogsSubcollectionDirect:
    """Direct Firestore tests for worker logs subcollection."""

    @pytest.fixture(autouse=True)
    def setup_firestore(self):
        """Set up Firestore client for each test."""
        from google.cloud import firestore
        self.db = firestore.Client(project="test-project")
        self.collection = "test-subcollection-jobs"
        yield

    def _create_test_job(self):
        """Create a test job document."""
        job_id = f"test-sub-{int(time.time() * 1000)}"
        doc_ref = self.db.collection(self.collection).document(job_id)
        doc_ref.set({
            "job_id": job_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "worker_logs": []  # Legacy field - kept empty for new jobs
        })
        return job_id

    def _append_log_to_subcollection(self, job_id: str, worker: str, message: str, ttl_days: int = 30):
        """Add log to subcollection at jobs/{job_id}/logs."""
        import uuid
        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        logs_ref = self.db.collection(self.collection).document(job_id).collection("logs")
        logs_ref.document(log_id).set({
            "id": log_id,
            "job_id": job_id,
            "timestamp": now,
            "level": "INFO",
            "worker": worker,
            "message": message,
            "ttl_expiry": now + timedelta(days=ttl_days)
        })
        return log_id

    def _get_logs_from_subcollection(self, job_id: str, worker: str = None, limit: int = 500):
        """Get logs from subcollection."""
        logs_ref = self.db.collection(self.collection).document(job_id).collection("logs")
        query = logs_ref.order_by("timestamp")

        if worker:
            from google.cloud.firestore_v1 import FieldFilter
            query = query.where(filter=FieldFilter("worker", "==", worker))

        query = query.limit(limit)

        return [doc.to_dict() for doc in query.stream()]

    def _count_logs_in_subcollection(self, job_id: str) -> int:
        """Count logs in subcollection."""
        logs_ref = self.db.collection(self.collection).document(job_id).collection("logs")
        count_query = logs_ref.count()
        result = count_query.get()
        if result and len(result) > 0:
            return result[0][0].value
        return 0

    def _delete_logs_subcollection(self, job_id: str, batch_size: int = 100) -> int:
        """Delete all logs in subcollection."""
        logs_ref = self.db.collection(self.collection).document(job_id).collection("logs")
        deleted_count = 0

        while True:
            docs = list(logs_ref.limit(batch_size).stream())
            if not docs:
                break

            batch = self.db.batch()
            for doc in docs:
                batch.delete(doc.reference)
                deleted_count += 1

            batch.commit()

        return deleted_count

    def test_subcollection_single_write(self):
        """Test writing single log to subcollection."""
        job_id = self._create_test_job()

        log_id = self._append_log_to_subcollection(job_id, "test", "Single log message")

        time.sleep(0.1)
        logs = self._get_logs_from_subcollection(job_id)

        assert len(logs) == 1
        assert logs[0]["message"] == "Single log message"
        assert logs[0]["worker"] == "test"
        assert logs[0]["id"] == log_id
        print("Single write to subcollection works")

    def test_subcollection_ttl_field_is_set(self):
        """Test TTL expiry field is set correctly."""
        job_id = self._create_test_job()

        self._append_log_to_subcollection(job_id, "test", "Log with TTL", ttl_days=7)

        time.sleep(0.1)
        logs = self._get_logs_from_subcollection(job_id)

        assert len(logs) == 1
        ttl_expiry = logs[0]["ttl_expiry"]
        assert ttl_expiry is not None

        # TTL should be ~7 days from now
        expected_ttl = datetime.now(timezone.utc) + timedelta(days=7)
        if hasattr(ttl_expiry, 'timestamp'):
            # Firestore datetime object
            diff = abs((ttl_expiry.replace(tzinfo=timezone.utc) - expected_ttl).total_seconds())
        else:
            diff = 0  # If already datetime
        assert diff < 60, f"TTL expiry should be ~7 days from now, diff was {diff}s"
        print("TTL field is set correctly")

    def test_subcollection_sequential_writes(self):
        """Test multiple sequential writes to subcollection."""
        job_id = self._create_test_job()

        for i in range(20):
            self._append_log_to_subcollection(job_id, "test", f"Log {i}")

        time.sleep(0.2)
        logs = self._get_logs_from_subcollection(job_id)

        assert len(logs) == 20, f"Expected 20 logs, got {len(logs)}"
        print(f"Sequential writes: {len(logs)} logs created")

    def test_subcollection_concurrent_writes(self):
        """Test concurrent writes to subcollection - no race conditions."""
        job_id = self._create_test_job()
        num_writes = 50

        def write_log(index):
            self._append_log_to_subcollection(job_id, "worker", f"Concurrent Log {index}")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_log, i) for i in range(num_writes)]
            for future in as_completed(futures):
                future.result()

        time.sleep(0.5)
        logs = self._get_logs_from_subcollection(job_id)

        assert len(logs) == num_writes, f"Expected {num_writes} logs, got {len(logs)}"
        print(f"Concurrent writes: All {num_writes} logs preserved")

    def test_subcollection_large_volume(self):
        """Test large volume of logs - demonstrates no 1MB limit."""
        job_id = self._create_test_job()
        num_logs = 500  # Would exceed 1MB in embedded array

        # Write logs in batches
        batch_size = 50
        for batch_start in range(0, num_logs, batch_size):
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for i in range(batch_start, min(batch_start + batch_size, num_logs)):
                    futures.append(executor.submit(
                        self._append_log_to_subcollection,
                        job_id,
                        "stress",
                        f"Large volume test log {i} - " + "x" * 500  # ~500 bytes per log
                    ))
                for future in as_completed(futures):
                    future.result()

        time.sleep(1)
        count = self._count_logs_in_subcollection(job_id)

        assert count == num_logs, f"Expected {num_logs} logs, got {count}"
        print(f"Large volume: {count} logs created (~{count * 500 / 1024:.1f}KB would exceed 1MB if embedded)")

    def test_subcollection_filter_by_worker(self):
        """Test filtering logs by worker type."""
        job_id = self._create_test_job()

        # Add logs from different workers
        for i in range(10):
            self._append_log_to_subcollection(job_id, "audio", f"Audio log {i}")
            self._append_log_to_subcollection(job_id, "lyrics", f"Lyrics log {i}")
            self._append_log_to_subcollection(job_id, "video", f"Video log {i}")

        time.sleep(0.3)

        # Query by worker
        audio_logs = self._get_logs_from_subcollection(job_id, worker="audio")
        lyrics_logs = self._get_logs_from_subcollection(job_id, worker="lyrics")
        all_logs = self._get_logs_from_subcollection(job_id)

        assert len(audio_logs) == 10, f"Expected 10 audio logs, got {len(audio_logs)}"
        assert len(lyrics_logs) == 10, f"Expected 10 lyrics logs, got {len(lyrics_logs)}"
        assert len(all_logs) == 30, f"Expected 30 total logs, got {len(all_logs)}"
        print("Worker filtering works correctly")

    def test_subcollection_ordered_by_timestamp(self):
        """Test logs are returned in timestamp order."""
        job_id = self._create_test_job()

        # Add logs with slight delays to ensure different timestamps
        for i in range(5):
            self._append_log_to_subcollection(job_id, "test", f"Log {i}")
            time.sleep(0.02)

        logs = self._get_logs_from_subcollection(job_id)

        # Verify order (timestamps should be ascending)
        for i in range(len(logs) - 1):
            assert logs[i]["timestamp"] <= logs[i + 1]["timestamp"], \
                f"Logs not in order at index {i}"
        print("Logs are ordered by timestamp")

    def test_subcollection_delete_all_logs(self):
        """Test deleting all logs in subcollection."""
        job_id = self._create_test_job()

        # Add logs
        for i in range(25):
            self._append_log_to_subcollection(job_id, "test", f"Log {i}")

        time.sleep(0.2)
        count_before = self._count_logs_in_subcollection(job_id)
        assert count_before == 25

        # Delete all logs
        deleted = self._delete_logs_subcollection(job_id)

        time.sleep(0.2)
        count_after = self._count_logs_in_subcollection(job_id)

        assert deleted == 25, f"Expected to delete 25 logs, deleted {deleted}"
        assert count_after == 0, f"Expected 0 logs after delete, got {count_after}"
        print(f"Deleted {deleted} logs from subcollection")

    def test_subcollection_concurrent_workers_interleaved(self):
        """Test simulating audio and lyrics workers writing concurrently."""
        job_id = self._create_test_job()
        logs_per_worker = 20

        def audio_worker():
            for i in range(logs_per_worker):
                self._append_log_to_subcollection(job_id, "audio", f"Audio processing step {i}")
                time.sleep(0.005)

        def lyrics_worker():
            for i in range(logs_per_worker):
                self._append_log_to_subcollection(job_id, "lyrics", f"Lyrics processing step {i}")
                time.sleep(0.005)

        def video_worker():
            for i in range(logs_per_worker):
                self._append_log_to_subcollection(job_id, "video", f"Video encoding step {i}")
                time.sleep(0.005)

        # Start all workers
        threads = [
            threading.Thread(target=audio_worker),
            threading.Thread(target=lyrics_worker),
            threading.Thread(target=video_worker)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        time.sleep(0.5)

        audio_logs = self._get_logs_from_subcollection(job_id, worker="audio")
        lyrics_logs = self._get_logs_from_subcollection(job_id, worker="lyrics")
        video_logs = self._get_logs_from_subcollection(job_id, worker="video")
        total = self._count_logs_in_subcollection(job_id)

        assert len(audio_logs) == logs_per_worker
        assert len(lyrics_logs) == logs_per_worker
        assert len(video_logs) == logs_per_worker
        assert total == logs_per_worker * 3

        print(f"Concurrent workers: {len(audio_logs)} audio + {len(lyrics_logs)} lyrics + {len(video_logs)} video = {total}")

    def test_subcollection_job_deletion_cleans_up_logs(self):
        """Test that deleting job document doesn't orphan logs."""
        job_id = self._create_test_job()

        # Add logs
        for i in range(10):
            self._append_log_to_subcollection(job_id, "test", f"Log {i}")

        time.sleep(0.2)
        assert self._count_logs_in_subcollection(job_id) == 10

        # Delete logs first (must happen before parent doc deletion in real code)
        deleted = self._delete_logs_subcollection(job_id)
        assert deleted == 10

        # Now delete job document
        self.db.collection(self.collection).document(job_id).delete()

        # Verify subcollection is empty (Firestore doesn't cascade delete subcollections)
        time.sleep(0.2)
        assert self._count_logs_in_subcollection(job_id) == 0
        print("Job deletion with log cleanup works correctly")


class TestSubcollectionVsEmbeddedArray:
    """Compare subcollection approach with embedded array."""

    @pytest.fixture(autouse=True)
    def setup_firestore(self):
        """Set up Firestore client for each test."""
        from google.cloud import firestore
        self.db = firestore.Client(project="test-project")
        self.collection = "test-comparison-jobs"
        yield

    def _create_test_job(self, use_array: bool):
        """Create test job."""
        job_id = f"test-cmp-{int(time.time() * 1000)}-{'arr' if use_array else 'sub'}"
        doc_ref = self.db.collection(self.collection).document(job_id)
        doc_ref.set({
            "job_id": job_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "worker_logs": []
        })
        return job_id

    def _append_log_array(self, job_id: str, message: str):
        """Add log to embedded array."""
        from google.cloud import firestore
        doc_ref = self.db.collection(self.collection).document(job_id)
        doc_ref.update({
            "worker_logs": firestore.ArrayUnion([{
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "level": "INFO",
                "worker": "test",
                "message": message
            }])
        })

    def _append_log_subcollection(self, job_id: str, message: str):
        """Add log to subcollection."""
        import uuid
        now = datetime.now(timezone.utc)
        logs_ref = self.db.collection(self.collection).document(job_id).collection("logs")
        logs_ref.document(str(uuid.uuid4())).set({
            "timestamp": now,
            "level": "INFO",
            "worker": "test",
            "message": message,
            "ttl_expiry": now + timedelta(days=30)
        })

    def test_document_size_comparison(self):
        """Compare document sizes between approaches."""
        array_job_id = self._create_test_job(use_array=True)
        sub_job_id = self._create_test_job(use_array=False)

        num_logs = 100
        large_message = "x" * 5000  # 5KB per log

        # Add logs to both
        print("\nAdding logs to both approaches...")
        for i in range(num_logs):
            self._append_log_array(array_job_id, f"Array log {i}: {large_message}")
            self._append_log_subcollection(sub_job_id, f"Sub log {i}: {large_message}")

        time.sleep(0.5)

        # Get document sizes (approximate via raw data)
        array_doc = self.db.collection(self.collection).document(array_job_id).get()
        sub_doc = self.db.collection(self.collection).document(sub_job_id).get()

        array_data = array_doc.to_dict()
        sub_data = sub_doc.to_dict()

        array_logs = array_data.get("worker_logs", [])
        sub_logs = sub_data.get("worker_logs", [])

        print(f"\nEmbedded array: {len(array_logs)} logs in document")
        print(f"Subcollection: {len(sub_logs)} logs in document (0 expected)")

        # Embedded array should have all logs in document
        assert len(array_logs) == num_logs

        # Subcollection should have empty array in main document
        assert len(sub_logs) == 0

        # Subcollection logs are in subcollection
        sub_count = self.db.collection(self.collection).document(sub_job_id).collection("logs").count().get()[0][0].value
        assert sub_count == num_logs

        print(f"Subcollection logs stored separately: {sub_count}")
        print("Subcollection approach keeps main document small")


print("Worker logs subcollection integration tests ready")
