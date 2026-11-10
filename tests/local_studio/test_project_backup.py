"""Portable project ZIP: round trip, data integrity and hostile archive rejection.

No FFmpeg, GPU, AI model or frontend required.
Run: python -m unittest tests.local_studio.test_project_backup -v
"""
from __future__ import annotations

import importlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
import zipfile
from unittest.mock import patch

from fastapi.testclient import TestClient

_IMPORT_DATA = tempfile.TemporaryDirectory(prefix="karaoke-backup-import-")
with patch.dict(os.environ, {"KARAOKE_DATA_DIR": _IMPORT_DATA.name}):
    studio = importlib.import_module("local_studio.app")


class PortableBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="karaoke-backup-")
        self.root = Path(self.temp.name)
        self.projects = self.root / "projects"
        self.projects.mkdir()
        self.patched = patch.multiple(studio, ROOT=self.root, PROJECTS=self.projects)
        self.patched.start()
        self.client = TestClient(studio.app)
        self.project_id = uuid.uuid4().hex
        self.folder = self.projects / self.project_id
        self.folder.mkdir()
        self.media = {
            "source.mp3": b"MP3 demo bytes",
            "audio.wav": b"RIFF demo bytes",
            "background.png": b"\x89PNG\r\n demo",
            "lyrics.lrc": "[00:00.25]Xin chào\n".encode("utf-8"),
        }
        for name, content in self.media.items():
            (self.folder / name).write_bytes(content)
        self.project = {
            "id": self.project_id, "title": "Xin chào 日本語",
            "duration": 5.0, "status": "ready", "progress": 100,
            "message": "Sẵn sàng", "error": None, "version": 1,
            "created_at": 100.0,
            "files": {"source": "source.mp3", "audio": "audio.wav",
                      "background": "background.png", "lrc": "lyrics.lrc"},
            "segments": [{"start": 0.25, "end": 1.25, "words": [
                {"text": "Xin", "start": 0.25, "end": 0.7},
                {"text": "chào", "start": 0.75, "end": 1.25},
            ]}],
            "subtitle_style": {"position": "bottom"},
        }
        studio.save(self.folder, self.project)

    def tearDown(self):
        self.client.close()
        self.patched.stop()
        self.temp.cleanup()

    def backup(self) -> bytes:
        response = self.client.get(f"/api/projects/{self.project_id}/backup")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/zip")
        return response.content

    @staticmethod
    def repack(original: bytes, modify_manifest=None, replacements=None) -> bytes:
        target = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as old, zipfile.ZipFile(target, "w") as new:
            for item in old.infolist():
                data = old.read(item)
                if item.filename == "manifest.json" and modify_manifest:
                    manifest = json.loads(data)
                    modify_manifest(manifest)
                    data = json.dumps(manifest).encode()
                if replacements and item.filename in replacements:
                    data = replacements[item.filename]
                new.writestr(item.filename, data)
        return target.getvalue()

    def import_zip(self, data: bytes):
        return self.client.post(
            "/api/projects/import-backup",
            files={"backup": ("backup.zip", data, "application/zip")},
        )

    def test_backup_round_trip_preserves_all_media_and_lyrics_with_new_id(self):
        data = self.backup()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["schema"], 1)
            self.assertEqual(len(manifest["media"]), 4)
            self.assertEqual(archive.read("media/lyrics.lrc"), self.media["lyrics.lrc"])
            self.assertEqual(set(archive.namelist()),
                             {"manifest.json"} | {"media/" + n for n in self.media})
        response = self.import_zip(data)
        self.assertEqual(response.status_code, 201, response.text)
        restored = response.json()
        self.assertNotEqual(restored["id"], self.project_id)
        self.assertEqual(restored["title"], self.project["title"])
        self.assertEqual(restored["segments"], self.project["segments"])
        self.assertEqual(restored["status"], "ready")
        self.assertEqual(restored["files"], self.project["files"])
        for name, content in self.media.items():
            self.assertEqual((self.projects / restored["id"] / name).read_bytes(), content)
        self.assertEqual(len(self.client.get("/api/projects").json()), 2)

    def test_rejects_bad_archive_and_bad_checksum_without_partial_project(self):
        original = self.backup()
        def wrong_digest(manifest):
            manifest["media"][0]["sha256"] = "0" * 64
        corrupt = self.repack(original, modify_manifest=wrong_digest)
        for data in [b"this is not a zip", corrupt]:
            with self.subTest(data=data[:10]):
                response = self.import_zip(data)
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(len(list(self.projects.glob("*/project.json"))), 1)

    def test_rejects_unexpected_file_and_traversal_filename(self):
        original = self.backup()
        target = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as old, zipfile.ZipFile(target, "w") as new:
            for item in old.infolist():
                new.writestr(item.filename, old.read(item))
            new.writestr("../evil.py", "malicious")
        self.assertEqual(self.import_zip(target.getvalue()).status_code, 400)
        def traversal(manifest):
            manifest["project"]["files"]["source"] = "../evil.mp3"
        self.assertEqual(self.import_zip(self.repack(original, modify_manifest=traversal)).status_code, 400)
        self.assertFalse((self.root / "evil.py").exists())

    def test_rejects_unsupported_schema_and_invalid_lyrics(self):
        data = self.backup()
        self.assertEqual(self.import_zip(self.repack(
            data, modify_manifest=lambda m: m.update(schema=99)
        )).status_code, 400)
        def invalid_lyrics(manifest):
            manifest["project"]["segments"][0]["end"] = 100
        self.assertEqual(self.import_zip(self.repack(
            data, modify_manifest=invalid_lyrics
        )).status_code, 400)

    def test_rejects_archive_with_symlinks_and_duplicate_members(self):
        original = self.backup()
        target = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as old, zipfile.ZipFile(target, "w") as new:
            for item in old.infolist():
                new.writestr(item.filename, old.read(item))
            new.writestr("media/source.mp3", "duplicate")
        self.assertEqual(self.import_zip(target.getvalue()).status_code, 400)
        target = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as old, zipfile.ZipFile(target, "w") as new:
            for item in old.infolist():
                if item.filename == "media/source.mp3":
                    link = zipfile.ZipInfo(item.filename)
                    link.create_system = 3
                    link.external_attr = (0o120777 << 16)
                    new.writestr(link, "elsewhere")
                else:
                    new.writestr(item.filename, old.read(item))
        self.assertEqual(self.import_zip(target.getvalue()).status_code, 400)

    def test_missing_media_refuses_backup_and_busy_project_cannot_be_exported(self):
        (self.folder / "source.mp3").unlink()
        response = self.client.get(f"/api/projects/{self.project_id}/backup")
        self.assertEqual(response.status_code, 400)
        (self.folder / "source.mp3").write_bytes(self.media["source.mp3"])
        self.project["status"] = "processing"
        studio.save(self.folder, self.project)
        self.assertEqual(self.client.get(f"/api/projects/{self.project_id}/backup").status_code, 409)


if __name__ == "__main__":
    unittest.main()
