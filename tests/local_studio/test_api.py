"""Real-media local API regression tests; no AI downloads or cloud calls.

Run independently of the upstream cloud pytest fixtures:
    python -m unittest discover -s tests/local_studio -p test_api.py -v
"""
from __future__ import annotations

import copy
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

# Avoid creating user/project data outside the test sandbox when importing app.
_IMPORT_DATA = tempfile.TemporaryDirectory(prefix="karaoke-api-import-")
with patch.dict(os.environ, {"KARAOKE_DATA_DIR": _IMPORT_DATA.name}):
    studio = importlib.import_module("local_studio.app")

LYRICS = {"segments": [{"start": 0.1, "end": 1.8, "words": [
    {"text": "Xin", "start": 0.1, "end": 0.7},
    {"text": "chào", "start": 1.0, "end": 1.8},
]}]}


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class LocalApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = tempfile.TemporaryDirectory(prefix="karaoke-api-assets-")
        cls.audio = Path(cls.assets.name) / "tone.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=2", "-ac", "2", str(cls.audio)], check=True)
        cls.audio_bytes = cls.audio.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.assets.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="karaoke-api-projects-")
        self.root = Path(self.temp.name)
        self.project_root = self.root / "projects"
        self.project_root.mkdir()
        self.paths = patch.multiple(studio, ROOT=self.root, PROJECTS=self.project_root)
        self.paths.start()
        self.client = TestClient(studio.app)

    def tearDown(self):
        # All asynchronous assertions wait for terminal status before returning.
        self.client.close()
        self.paths.stop()
        self.temp.cleanup()

    def create(self, **extra_files):
        files = {"source": ("ca khúc.wav", self.audio_bytes, "audio/wav"), **extra_files}
        response = self.client.post("/api/projects", data={"title": "Xin chào Việt Nam"}, files=files)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def save_lyrics(self, project):
        response = self.client.put(f"/api/projects/{project['id']}/lyrics", json=LYRICS)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def wait(self, project_id, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = self.client.get(f"/api/projects/{project_id}")
            self.assertEqual(response.status_code, 200, response.text)
            project = response.json()
            if project["status"] not in studio.ACTIVE:
                return project
            time.sleep(0.04)
        self.fail("Local worker did not finish before timeout")

    def test_upload_persistence_download_and_allowlisted_files(self):
        p = self.create()
        self.assertAlmostEqual(p["duration"], 2, places=2)
        self.assertEqual(p["title"], "Xin chào Việt Nam")
        self.assertEqual(p["status"], "ready")
        self.assertIn("audio", p["files"])
        self.assertEqual(self.client.get("/api/projects").json()[0]["id"], p["id"])
        self.assertEqual(studio.load(p["id"])["title"], p["title"])
        audio = self.client.get(f"/api/projects/{p['id']}/files/audio.wav")
        self.assertEqual(audio.status_code, 200)
        self.assertTrue(audio.content.startswith(b"RIFF"))
        forbidden = self.client.get(f"/api/projects/{p['id']}/files/project.json")
        self.assertEqual(forbidden.status_code, 404)
        self.assertEqual(self.client.get("/api/projects/not-a-project").status_code, 404)
        download = self.client.get(f"/api/projects/{p['id']}/download")
        self.assertEqual(download.json()["id"], p["id"])
        self.assertIn("attachment", download.headers["content-disposition"])

    def test_bad_media_is_rejected_and_partial_project_removed(self):
        response = self.client.post("/api/projects", files={"source": ("bad.wav", b"not audio", "audio/wav")})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.project_root.iterdir()), [])
        response = self.client.post("/api/projects", files={"source": ("unsafe.exe", b"x")})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.project_root.iterdir()), [])

    def test_lyrics_reject_overlap_reversal_and_out_of_song_bounds(self):
        p = self.create()
        endpoint = f"/api/projects/{p['id']}/lyrics"
        self.save_lyrics(p)
        invalid = copy.deepcopy(LYRICS)
        invalid["segments"][0]["words"][1]["start"] = 0.5
        self.assertEqual(self.client.put(endpoint, json=invalid).status_code, 422)
        invalid = copy.deepcopy(LYRICS)
        invalid["segments"][0]["words"][0]["end"] = 0.01
        self.assertEqual(self.client.put(endpoint, json=invalid).status_code, 422)
        invalid = copy.deepcopy(LYRICS)
        invalid["segments"][0]["end"] = 8
        self.assertEqual(self.client.put(endpoint, json=invalid).status_code, 400)
        invalid = copy.deepcopy(LYRICS)
        invalid["segments"].append(invalid["segments"][0])
        self.assertEqual(self.client.put(endpoint, json=invalid).status_code, 422)
        self.assertEqual(studio.load(p["id"])["segments"], LYRICS["segments"])

    def test_subtitle_export_and_edits_remove_obsolete_downloads(self):
        p = self.save_lyrics(self.create())
        endpoint = f"/api/projects/{p['id']}"
        exported = self.client.post(endpoint + "/subtitles", json={"resolution": "720p", "font_size": 54})
        self.assertEqual(exported.status_code, 200, exported.text)
        p = exported.json()
        for key in ("ass", "srt", "lrc"):
            self.assertIn(key, p["files"])
            self.assertEqual(self.client.get(endpoint + "/files/" + p["files"][key]).status_code, 200)
        ass = self.client.get(endpoint + "/files/lyrics.ass").text
        self.assertIn("PlayResX: 1280", ass)
        self.assertIn("\\kf60", ass)
        self.assertIn("chào", ass)
        srt = self.client.get(endpoint + "/files/lyrics.srt").text
        self.assertIn("00:00:00,100 --> 00:00:01,800", srt)
        changed = self.save_lyrics(p)
        self.assertNotIn("ass", changed["files"])
        self.assertEqual(self.client.get(endpoint + "/files/lyrics.ass").status_code, 404)

    def test_export_prerequisites(self):
        p = self.create()
        endpoint = f"/api/projects/{p['id']}"
        self.assertEqual(self.client.post(endpoint + "/subtitles", json={}).status_code, 400)
        self.assertEqual(self.client.post(endpoint + "/render", json={"audio_mode": "original"}).status_code, 400)
        self.save_lyrics(p)
        self.assertEqual(self.client.post(endpoint + "/render", json={"audio_mode": "instrumental"}).status_code, 400)
        self.assertEqual(self.client.post(endpoint + "/render", json={"resolution": "4k"}).status_code, 422)

    def test_real_render_original_then_silent_and_stale_video_invalidation(self):
        p = self.save_lyrics(self.create())
        endpoint = f"/api/projects/{p['id']}"
        for mode, expect_audio in (("original", True), ("silent", False)):
            response = self.client.post(endpoint + "/render", json={"audio_mode": mode, "resolution": "720p"})
            self.assertEqual(response.status_code, 202, response.text)
            finished = self.wait(p["id"])
            self.assertEqual(finished["status"], "ready", finished.get("error"))
            path = self.project_root / p["id"] / finished["files"]["video"]
            media = studio.pipeline.probe(path)
            self.assertAlmostEqual(media["duration"], 2, delta=0.15)
            videos = [s for s in media["streams"] if s["codec_type"] == "video"]
            self.assertEqual((videos[0]["width"], videos[0]["height"]), (1280, 720))
            self.assertEqual(any(s["codec_type"] == "audio" for s in media["streams"]), expect_audio)
            self.assertEqual(self.client.get(endpoint + "/files/karaoke.mp4").status_code, 200)
        changed = self.save_lyrics(p)
        self.assertNotIn("video", changed["files"])
        self.assertFalse((self.project_root / p["id"] / "karaoke.mp4").exists())

    def test_queued_work_rejects_concurrent_edits_and_persists_asr(self):
        p = self.create()
        endpoint = f"/api/projects/{p['id']}"
        entered, release = threading.Event(), threading.Event()
        def recognition(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("Test timed out")
            return copy.deepcopy(LYRICS["segments"])
        with patch.object(studio.pipeline, "transcribe_audio", side_effect=recognition):
            response = self.client.post(endpoint + "/transcribe", json={"separate": False})
            self.assertEqual(response.status_code, 202, response.text)
            self.assertTrue(entered.wait(5))
            try:
                self.assertEqual(self.client.put(endpoint + "/lyrics", json=LYRICS).status_code, 409)
                self.assertEqual(self.client.post(endpoint + "/separate", json={}).status_code, 409)
                self.assertEqual(self.client.post(endpoint + "/transcribe", json={"separate": False}).status_code, 409)
            finally:
                release.set()
            finished = self.wait(p["id"])
        self.assertEqual(finished["status"], "ready", finished.get("error"))
        self.assertEqual(finished["segments"], LYRICS["segments"])
        self.assertEqual(studio.load(p["id"])["segments"], LYRICS["segments"])

    def test_asr_error_is_persisted_and_retry_succeeds(self):
        p = self.create()
        endpoint = f"/api/projects/{p['id']}/transcribe"
        with patch.object(studio.pipeline, "transcribe_audio", side_effect=RuntimeError("model unavailable")):
            self.assertEqual(self.client.post(endpoint, json={"separate": False}).status_code, 202)
            finished = self.wait(p["id"])
        self.assertEqual(finished["status"], "error")
        self.assertIn("model unavailable", finished["error"])
        with patch.object(studio.pipeline, "transcribe_audio", return_value=copy.deepcopy(LYRICS["segments"])):
            self.assertEqual(self.client.post(endpoint, json={"separate": False}).status_code, 202)
            finished = self.wait(p["id"])
        self.assertEqual(finished["status"], "ready", finished.get("error"))
        self.assertIsNone(finished["error"])

    def test_cross_site_and_untrusted_hosts_are_rejected(self):
        self.assertEqual(self.client.get("/api/health", headers={"Host": "attacker.example"}).status_code, 400)
        files = {"source": ("tone.wav", self.audio_bytes, "audio/wav")}
        response = self.client.post("/api/projects", files=files, headers={"Origin": "https://attacker.example"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(list(self.project_root.iterdir()), [])
        response = self.client.post("/api/projects", files=files, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(response.status_code, 403)
        response = self.client.post("/api/projects", files=files, headers={"Origin": "http://testserver"})
        self.assertEqual(response.status_code, 201, response.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
