"""Real FFmpeg progress and cancellation regression tests; no AI model required."""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from local_studio.render_control import RenderCancelled, parse_ffmpeg_time
from local_studio.pipeline import render_video
from local_studio.subtitles import write_subtitles

_IMPORT = tempfile.TemporaryDirectory(prefix="karaoke-progress-import-")
with patch.dict(os.environ, {"KARAOKE_DATA_DIR": _IMPORT.name}):
    studio = importlib.import_module("local_studio.app")


class ProgressParserTests(unittest.TestCase):
    def test_timecodes_and_invalid_values(self):
        self.assertAlmostEqual(parse_ffmpeg_time("00:01:02.125000"), 62.125)
        self.assertAlmostEqual(parse_ffmpeg_time("01:00:00.000001"), 3600.000001)
        for invalid in ("N/A", "00:61:20", "NaN", "-01:00:00", "00:00:NaN", "00:00:-1"):
            with self.subTest(invalid=invalid):
                self.assertIsNone(parse_ffmpeg_time(invalid))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class RealFFmpegProgressTests(unittest.TestCase):
    def test_encoder_reports_progress_without_claiming_100_before_completion(self):
        with tempfile.TemporaryDirectory(prefix="karaoke-progress-") as tmp:
            root = Path(tmp)
            audio = root / "tone.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "sine=frequency=700:duration=2.5", str(audio)], check=True)
            write_subtitles([{"start": 0.1, "end": 1.2, "words": [
                {"start": 0.1, "end": 1.2, "text": "Xin chào"},
            ]}], root, resolution=(1280, 720))
            pct = []
            output = root / "render.mp4"
            render_video(audio, None, root / "lyrics.ass", output, 2.5, (1280, 720),
                         on_progress=pct.append)
            self.assertTrue(output.exists())
            self.assertTrue(pct)
            self.assertEqual(pct, sorted(set(pct)))
            self.assertTrue(all(0 <= p <= 99 for p in pct))
            self.assertEqual(pct[-1], 99)

    def test_cancel_before_start_preserves_existing_output(self):
        with tempfile.TemporaryDirectory(prefix="karaoke-cancel-") as tmp:
            root = Path(tmp)
            ass = root / "lyrics.ass"
            ass.write_text("[Script Info]\nScriptType: v4.00+\n", encoding="utf-8")
            output = root / "render.mp4"
            cancel = threading.Event()
            cancel.set()
            with self.assertRaises(RenderCancelled):
                render_video(None, None, ass, output, 20, (1280, 720),
                             cancel_event=cancel)
            self.assertFalse(output.exists())


class CancelApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="karaoke-cancel-api-")
        self.root = Path(self.temp.name)
        self.projects = self.root / "projects"
        self.projects.mkdir()
        self.paths = patch.multiple(studio, ROOT=self.root, PROJECTS=self.projects)
        self.paths.start()
        self.client = TestClient(studio.app)
        self.project_id = uuid.uuid4().hex
        self.folder = self.projects / self.project_id
        self.folder.mkdir()
        (self.folder / "audio.wav").write_bytes(b"fake audio; renderer mocked")
        (self.folder / "source.wav").write_bytes(b"fake source")
        studio.save(self.folder, {
            "id": self.project_id, "title": "Test hủy render", "duration": 2.0,
            "status": "ready", "progress": 100, "message": "ready", "error": None,
            "files": {"source": "source.wav", "audio": "audio.wav"},
            "segments": [{"start": 0.1, "end": 1.0, "words": [
                {"start": 0.1, "end": 1.0, "text": "Xin chào"},
            ]}],
        })

    def tearDown(self):
        self.client.close()
        self.paths.stop()
        self.temp.cleanup()

    def test_live_cancel_stops_job_without_publishing_video(self):
        started = threading.Event()

        def fake_render(*args, on_progress=None, cancel_event=None, **kwargs):
            on_progress(50)
            started.set()
            if not cancel_event.wait(timeout=5):
                raise RuntimeError("Không nhận được yêu cầu hủy.")
            raise RenderCancelled("Đã hủy.")

        endpoint = f"/api/projects/{self.project_id}"
        with patch.object(studio, "require_tools"), patch.object(studio.pipeline, "render_video", fake_render):
            response = self.client.post(endpoint + "/render", json={"audio_mode": "original"})
            self.assertEqual(response.status_code, 202, response.text)
            self.assertTrue(started.wait(5))
            active = self.client.get(endpoint).json()
            self.assertEqual(active["status"], "rendering")
            self.assertGreaterEqual(active["progress"], 54)
            cancel = self.client.post(endpoint + "/render/cancel")
            self.assertEqual(cancel.status_code, 200, cancel.text)
            for _ in range(100):
                state = self.client.get(endpoint).json()
                if state["status"] not in studio.ACTIVE:
                    break
                time.sleep(0.02)
            self.assertEqual(state["status"], "cancelled", state)
            self.assertNotIn("video", state["files"])
            self.assertFalse((self.folder / "rendering.mp4").exists())
            self.assertFalse((self.folder / "karaoke.mp4").exists())
            self.assertEqual(self.client.post(endpoint + "/render/cancel").status_code, 409)

    def test_cannot_cancel_when_no_render_active(self):
        endpoint = f"/api/projects/{self.project_id}"
        response = self.client.post(endpoint + "/render/cancel")
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
