"""Background router integration: real local media, deterministic provider calls."""
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

_IMPORT = tempfile.TemporaryDirectory(prefix="karaoke-media-import-")
with patch.dict(os.environ, {"KARAOKE_DATA_DIR": _IMPORT.name}):
    studio = importlib.import_module("local_studio.app")


@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
class BackgroundApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = tempfile.TemporaryDirectory(prefix="karaoke-media-assets-")
        cls.video = Path(cls.assets.name) / "forest.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x120:d=1:r=10",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(cls.video)], check=True)
        cls.audio = Path(cls.assets.name) / "tone.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(cls.audio)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.assets.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="karaoke-media-api-")
        self.root = Path(self.temp.name)
        (self.root / "projects").mkdir()
        self.paths = patch.multiple(studio, ROOT=self.root, PROJECTS=self.root / "projects")
        self.paths.start()
        self.env = patch.dict(os.environ, {"PEXELS_API_KEY": ""})
        self.env.start()
        self.client = TestClient(studio.app)

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.paths.stop()
        self.temp.cleanup()

    def project(self):
        response = self.client.post("/api/projects", data={"title": "Nền thử"},
                                    files={"source": ("tone.wav", self.audio.read_bytes(), "audio/wav")})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def wait(self, project_id):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            p = self.client.get(f"/api/projects/{project_id}").json()
            if p["status"] not in studio.ACTIVE:
                return p
            time.sleep(.03)
        self.fail("Media job did not finish")

    def scan(self):
        response = self.client.post("/api/backgrounds/local/scan", json={"folder": self.assets.name})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["assets"][0]

    def test_key_settings_never_echo_secret_in_responses_or_errors(self):
        key = "a-private-key-123"
        response = self.client.put("/api/backgrounds/settings", json={"pexels_api_key": key})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(key, response.text)
        self.assertTrue(response.json()["providers"][1]["configured"])
        self.assertEqual(json.loads((self.root / "settings.json").read_text())["pexels_api_key"], key)
        response = self.client.put("/api/backgrounds/settings", json={"pexels_api_key": key * 100})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(key, response.text)
        with patch("local_studio.backgrounds.search_online", side_effect=ValueError("Invalid secret " + key)):
            response = self.client.post("/api/backgrounds/search", json={"query": "rain", "provider": "pexels"})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(key, response.text)
        self.assertNotIn(key, self.client.get("/api/backgrounds/providers").text)

    def test_local_preview_and_apply_preserve_lyrics_invalidate_only_video(self):
        p = self.project()
        folder = studio.project_dir(p["id"])
        words = [{"start": .1, "end": 1.5, "words": [{"text": "Xin chào", "start": .1, "end": 1.5}]}]
        p["segments"] = words
        for key, name in {"video": "old.mp4", "ass": "lyrics.ass"}.items():
            (folder / name).write_bytes(b"old")
            p["files"][key] = name
        studio.save(folder, p)
        asset = self.scan()
        self.assertNotIn("path", asset)
        preview = self.client.get(asset["preview_url"])
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.content, self.video.read_bytes())
        response = self.client.post(f"/api/projects/{p['id']}/background", json={"mode": "selected", "asset_id": asset["id"]})
        self.assertEqual(response.status_code, 202, response.text)
        result = self.wait(p["id"])
        self.assertEqual(result["status"], "ready", result)
        self.assertEqual(result["segments"], words)
        self.assertEqual((folder / result["files"]["background"]).read_bytes(), self.video.read_bytes())
        self.assertNotIn("video", result["files"])
        self.assertIn("ass", result["files"])
        self.assertEqual(result["background_info"]["provider"], "local")

    def test_automatic_local_and_failed_replacement_keep_last_background(self):
        p = self.project()
        endpoint = f"/api/projects/{p['id']}/background"
        response = self.client.post(endpoint, json={"mode": "local", "folder": self.assets.name})
        self.assertEqual(response.status_code, 202)
        ready = self.wait(p["id"])
        self.assertEqual(ready["status"], "ready", ready)
        old = ready["files"]["background"]
        with patch("local_studio.backgrounds.fetch_background", side_effect=ValueError("download failed")):
            self.assertEqual(self.client.post(endpoint, json={"mode": "selected", "asset_id": self.scan()["id"]}).status_code, 202)
            failed = self.wait(p["id"])
        self.assertEqual(failed["status"], "error")
        self.assertEqual(failed["files"]["background"], old)
        self.assertTrue((studio.project_dir(p["id"]) / old).is_file())

    def test_online_search_retains_license_preview_and_rejects_unregistered_urls(self):
        asset = {"provider": "commons", "title": "Rain", "preview_url": "https://upload.wikimedia.org/rain.jpg",
                 "download_url": "https://upload.wikimedia.org/rain.webm", "author": "Author", "license": "CC BY 4.0",
                 "license_url": "https://creativecommons.org/licenses/by/4.0/", "source_url": "https://commons.wikimedia.org/wiki/File:Rain.webm"}
        with patch("local_studio.backgrounds.search_online", return_value=[asset]):
            response = self.client.post("/api/backgrounds/search", json={"query": "rain"})
        result = response.json()["assets"][0]
        self.assertEqual(result["preview_url"], asset["preview_url"])
        self.assertEqual(result["author"], "Author")
        self.assertEqual(result["license_url"], asset["license_url"])
        self.assertNotIn("download_url", result)
        p = self.project()
        endpoint = f"/api/projects/{p['id']}/background"
        self.assertEqual(self.client.post(endpoint, json={"mode": "selected", "asset_id": "unknown"}).status_code, 404)
        self.assertEqual(self.client.post(endpoint, json={"mode": "selected", "asset_id": result["id"], "download_url": "http://127.0.0.1/private"}).status_code, 422)
        self.assertEqual(self.client.post(endpoint, json={"mode": "online", "provider": "pexels", "query": "rain"}).status_code, 400)

    def test_busy_project_rejects_media_mutations(self):
        p = self.project()
        studio.update(p["id"], status="processing")
        response = self.client.post(f"/api/projects/{p['id']}/background", json={"mode": "local", "folder": self.assets.name})
        self.assertEqual(response.status_code, 409)
        studio.update(p["id"], status="ready")
