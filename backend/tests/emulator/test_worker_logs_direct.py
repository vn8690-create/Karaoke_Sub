"""
Direct tests for worker logging Firestore operations.

These tests bypass the full app/worker imports and test the Firestore
operations directly, avoiding dependency issues.

Run with: ./scripts/run-emulator-tests.sh
"""
import pytest
import time
import requests
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime


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


class TestWorkerLogsFirestoreDirect:
    """Direct Firestore tests for worker logs - no app imports needed."""
    
    @pytest.fixture(autouse=True)
    def setup_firestore(self):
        """Set up Firestore client for each test."""
        from google.cloud import firestore
        self.db = firestore.Client(project="test-project")
        self.collection = "test-worker-logs"
        yield
    
    def _create_test_job(self):
        """Create a test job document."""
        job_id = f"test-{int(time.time() * 1000)}"
        doc_ref = self.db.collection(self.collection).document(job_id)
        doc_ref.set({
            "job_id": job_id,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "worker_logs": []
        })
        return job_id
    
    def _append_log_read_modify_write(self, job_id: str, worker: str, message: str):
        """
        OLD METHOD: Read-modify-write (has race condition).
        This is what we were doing before.
        """
        doc_ref = self.db.collection(self.collection).document(job_id)
        doc = doc_ref.get()
        if not doc.exists:
            return
        
        data = doc.to_dict()
        logs = data.get("worker_logs", [])
        logs.append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "worker": worker,
            "message": message
        })
        doc_ref.update({"worker_logs": logs})
    
    def _append_log_array_union(self, job_id: str, worker: str, message: str):
        """
        NEW METHOD: ArrayUnion (atomic, no race condition).
        This is what we're doing now.
        """
        from google.cloud import firestore
        doc_ref = self.db.collection(self.collection).document(job_id)
        doc_ref.update({
            "worker_logs": firestore.ArrayUnion([{
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "INFO",
                "worker": worker,
                "message": message
            }])
        })
    
    def _get_logs(self, job_id: str):
        """Get logs from job document."""
        doc_ref = self.db.collection(self.collection).document(job_id)
        doc = doc_ref.get()
        if not doc.exists:
            return []
        return doc.to_dict().get("worker_logs", [])
    
    def test_array_union_single_write(self):
        """Test ArrayUnion works for single write."""
        job_id = self._create_test_job()
        
        self._append_log_array_union(job_id, "test", "Single log message")
        
        time.sleep(0.1)
        logs = self._get_logs(job_id)
        
        assert len(logs) == 1
        assert logs[0]["message"] == "Single log message"
        assert logs[0]["worker"] == "test"
    
    def test_array_union_sequential_writes(self):
        """Test ArrayUnion preserves all sequential writes."""
        job_id = self._create_test_job()
        
        for i in range(10):
            self._append_log_array_union(job_id, "test", f"Log {i}")
        
        time.sleep(0.2)
        logs = self._get_logs(job_id)
        
        assert len(logs) == 10, f"Expected 10 logs, got {len(logs)}"
    
    def test_read_modify_write_race_condition(self):
        """
        Demonstrate the race condition with read-modify-write.
        This test shows WHY we needed ArrayUnion.
        """
        job_id = self._create_test_job()
        num_writes = 20
        
        def write_log(index):
            self._append_log_read_modify_write(job_id, "worker", f"RMW Log {index}")
        
        # Write concurrently - should lose some logs due to race condition
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(write_log, i) for i in range(num_writes)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    pass  # Ignore errors for this test
        
        time.sleep(0.5)
        logs = self._get_logs(job_id)
        
        # With read-modify-write, we likely lose some logs
        # This is expected - the test documents the problem
        rmw_count = len([l for l in logs if "RMW Log" in l.get("message", "")])
        print(f"\nRead-modify-write: {rmw_count}/{num_writes} logs preserved")
        
        # We expect to lose some logs (this is the bug we're fixing)
        # If all 20 are there, the race condition didn't trigger (which is fine)
        # The important thing is that ArrayUnion test below ALWAYS preserves all
    
    def test_array_union_no_race_condition(self):
        """
        Verify ArrayUnion preserves ALL concurrent writes.
        This is the critical test.
        """
        job_id = self._create_test_job()
        num_writes = 20
        
        def write_log(index):
            self._append_log_array_union(job_id, "worker", f"ArrayUnion Log {index}")
        
        # Write concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(write_log, i) for i in range(num_writes)]
            for future in as_completed(futures):
                future.result()  # Raise any exceptions
        
        time.sleep(0.5)
        logs = self._get_logs(job_id)
        
        # With ArrayUnion, ALL logs should be preserved
        au_count = len([l for l in logs if "ArrayUnion Log" in l.get("message", "")])
        print(f"\nArrayUnion: {au_count}/{num_writes} logs preserved")
        
        assert au_count == num_writes, \
            f"ArrayUnion should preserve all {num_writes} logs, got {au_count}"
    
    def test_concurrent_workers_array_union(self):
        """
        Test simulating audio and lyrics workers writing concurrently.
        """
        job_id = self._create_test_job()
        
        def audio_worker():
            for i in range(10):
                self._append_log_array_union(job_id, "audio", f"Audio log {i}")
                time.sleep(0.01)
        
        def lyrics_worker():
            for i in range(10):
                self._append_log_array_union(job_id, "lyrics", f"Lyrics log {i}")
                time.sleep(0.01)
        
        # Start both workers
        audio_thread = threading.Thread(target=audio_worker)
        lyrics_thread = threading.Thread(target=lyrics_worker)
        
        audio_thread.start()
        lyrics_thread.start()
        
        audio_thread.join()
        lyrics_thread.join()
        
        time.sleep(0.5)
        logs = self._get_logs(job_id)
        
        audio_logs = [l for l in logs if l.get("worker") == "audio"]
        lyrics_logs = [l for l in logs if l.get("worker") == "lyrics"]
        
        print(f"\nConcurrent workers: {len(audio_logs)} audio + {len(lyrics_logs)} lyrics")
        
        assert len(audio_logs) == 10, f"Expected 10 audio logs, got {len(audio_logs)}"
        assert len(lyrics_logs) == 10, f"Expected 10 lyrics logs, got {len(lyrics_logs)}"
        
        print("✅ All logs from both workers preserved!")


print("✅ Direct Firestore worker logs tests ready")
