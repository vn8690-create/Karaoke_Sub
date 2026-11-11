"""Japanese (ja) language support in local transcription/alignment API.

No AI weights or FFmpeg required. Check request schema and the real
FastAPI job dispatch with deterministic model adapters.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

_IMPORT = tempfile.TemporaryDirectory(prefix="karaoke-ja-import-")
with patch.dict(os.environ, {"KARAOKE_DATA_DIR": _IMPORT.name}):
    studio = importlib.import_module("local_studio.app")


class JapaneseApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="karaoke-ja-test-")
        self.root = Path(self.temp.name)
        self.projects = self.root / "projects"
        self.projects.mkdir()
        self.paths = patch.multiple(studio, ROOT=self.root, PROJECTS=self.projects)
        self.paths.start()
        self.client = TestClient(studio.app)
        self.project_id = uuid.uuid4().hex
        self.folder = self.projects / self.project_id
        self.folder.mkdir()
        (self.folder / "audio.wav").write_bytes(b"mock audio")
        (self.folder / "source.wav").write_bytes(b"mock source")
        studio.save(self.folder, {
            "id": self.project_id, "title": "お母さんは怖いですね",
            "duration": 10.0, "status": "ready", "progress": 100,
            "error": None, "message": "ready", "version": 1,
            "files": {"audio": "audio.wav", "source": "source.wav"},
            "segments": [], "created_at": time.time(),
        })

    def tearDown(self):
        self.client.close()
        self.paths.stop()
        self.temp.cleanup()

    def wait(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = self.client.get(f"/api/projects/{self.project_id}").json()
            if result["status"] not in studio.ACTIVE:
                return result
            time.sleep(.025)
        self.fail("async job did not finish")

    def test_schema_accepts_ja_preserves_other_languages_and_rejects_unknown(self):
        for cls in (studio.Transcribe, studio.Align):
            values = {"text": "お母さん は 怖い ですね"} if cls is studio.Align else {}
            for language in ("vi", "en", "ja", "auto"):
                with self.subTest(model=cls.__name__, language=language):
                    self.assertEqual(cls.model_validate({**values, "language": language}).language, language)
            with self.assertRaises(ValidationError):
                cls.model_validate({**values, "language": "zz"})

    def test_transcribe_dispatches_japanese_to_whisper_engine(self):
        segments = [{"start": .2, "end": 1.1, "words": [
            {"text": "お母さん", "start": .2, "end": 1.1},
        ]}]
        with patch.object(studio, "require_tools"), patch.object(
            studio.pipeline, "transcribe_audio", return_value=segments
        ) as engine:
            response = self.client.post(f"/api/projects/{self.project_id}/transcribe",
                                        json={"language": "ja", "model": "base", "device": "cpu",
                                              "separate": False})
            self.assertEqual(response.status_code, 202, response.text)
            result = self.wait()
        self.assertEqual(result["status"], "ready", result.get("error"))
        self.assertEqual(result["segments"], segments)
        self.assertEqual(engine.call_args.args[2], "ja")

    def test_forced_alignment_preserves_japanese_reference_and_language(self):
        source = "[Intro]\nお母さん は 怖い ですね"
        words = [
            {"text": "お母さん", "start": .2, "end": .6},
            {"text": "は", "start": .6, "end": .8},
            {"text": "怖い", "start": .8, "end": 1.1},
            {"text": "ですね", "start": 1.1, "end": 1.5},
        ]
        payload = {"segments": [{"start": .2, "end": 1.5, "words": words}],
                   "engine": "stable-ts", "language": "ja", "warnings": []}
        with patch.object(studio, "require_tools"), patch.object(
            studio.alignment, "align_lyrics", return_value=payload
        ) as engine:
            response = self.client.post(f"/api/projects/{self.project_id}/align",
                                        json={"text": source, "language": "ja",
                                              "model": "small", "device": "cpu",
                                              "separate": False})
            self.assertEqual(response.status_code, 202, response.text)
            result = self.wait()
        self.assertEqual(result["status"], "ready", result.get("error"))
        self.assertEqual(result["segments"][0]["words"], words)
        self.assertEqual(result["alignment"]["language"], "ja")
        self.assertEqual(engine.call_args.args[3], "ja")


if __name__ == "__main__":
    unittest.main()
