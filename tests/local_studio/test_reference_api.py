"""Reference-text and timing API regressions, without downloading AI models."""
from __future__ import annotations

import copy
import importlib
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

_IMPORT_DATA = tempfile.TemporaryDirectory(prefix="karaoke-reference-import-")
with patch.dict(os.environ, {"KARAOKE_DATA_DIR": _IMPORT_DATA.name}):
    studio = importlib.import_module("local_studio.app")

REFERENCE = "\ufeff[Intro]\r\n[Sound of rain]\r\n[Verse 1]\r\nXin chào...\r\n[Chorus]\r\nngười ơi!\r\n"
CLEAN_TEXT = "Xin chào...\nngười ơi!"
SEGMENTS = [
    {"start": 0.4, "end": 1.1, "words": [
        {"text": "Xin", "start": 0.4, "end": 0.6},
        {"text": "chào...", "start": 0.8, "end": 1.1},
    ]},
    {"start": 1.6, "end": 2.2, "words": [
        {"text": "người", "start": 1.6, "end": 1.9},
        {"text": "ơi!", "start": 2.0, "end": 2.2},
    ]},
]
OLD_SEGMENTS = [{"start": 0.3, "end": 1.0, "words": [
    {"text": "Lời", "start": 0.3, "end": 0.5},
    {"text": "cũ", "start": 0.6, "end": 1.0},
]}]


def aligned_result(**changes):
    result = {"segments": copy.deepcopy(SEGMENTS), "warnings": ["Hãy nghe và kiểm tra từ kéo dài."],
              "text": CLEAN_TEXT, "ignored_lines": 4, "engine": "stable-ts"}
    result.update(changes)
    return result


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class ReferenceApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = tempfile.TemporaryDirectory(prefix="karaoke-reference-assets-")
        audio = Path(cls.assets.name) / "source.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=3", "-ac", "2", str(audio)], check=True)
        cls.audio_bytes = audio.read_bytes()
        beat = Path(cls.assets.name) / "beat.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=880:duration=3", "-ac", "2", str(beat)], check=True)
        cls.beat_bytes = beat.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.assets.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="karaoke-reference-projects-")
        self.root = Path(self.temp.name)
        self.projects = self.root / "projects"
        self.projects.mkdir()
        self.paths = patch.multiple(studio, ROOT=self.root, PROJECTS=self.projects)
        self.paths.start()
        self.client = TestClient(studio.app)

    def tearDown(self):
        self.client.close()
        self.paths.stop()
        self.temp.cleanup()

    def create(self, beat=False):
        files = {"source": ("ca khúc.wav", self.audio_bytes, "audio/wav")}
        if beat:
            files["instrumental"] = ("beat.wav", self.beat_bytes, "audio/wav")
        response = self.client.post("/api/projects", data={"title": "Lời chuẩn"}, files=files)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def endpoint(self, p):
        return f"/api/projects/{p['id']}"

    def save_timed(self, p, segments=OLD_SEGMENTS):
        response = self.client.put(self.endpoint(p) + "/lyrics", json={"segments": segments})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def wait(self, project_id):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            p = self.client.get(f"/api/projects/{project_id}").json()
            if p["status"] not in studio.ACTIVE:
                return p
            time.sleep(0.03)
        self.fail("Reference alignment worker timed out")

    def align(self, p, result=None, **options):
        with patch.object(studio.alignment, "align_lyrics", return_value=result or aligned_result()) as fit:
            response = self.client.post(self.endpoint(p) + "/align",
                                        json={"text": REFERENCE, "separate": False, **options})
            self.assertEqual(response.status_code, 202, response.text)
            done = self.wait(p["id"])
        return done, fit

    def test_reference_cleans_directions_and_keeps_existing_timed_lyrics(self):
        p = self.save_timed(self.create())
        response = self.client.put(self.endpoint(p) + "/reference", json={"text": REFERENCE})
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        self.assertEqual(saved["reference_lyrics"]["raw_text"], REFERENCE)
        self.assertEqual(saved["reference_lyrics"]["text"], CLEAN_TEXT)
        self.assertEqual(saved["reference_lyrics"]["lines"], ["Xin chào...", "người ơi!"])
        self.assertGreater(saved["reference_lyrics"]["ignored_lines"], 0)
        self.assertEqual(saved["segments"], OLD_SEGMENTS)
        self.assertTrue(saved["reference_pending"])
        self.assertEqual(studio.load(p["id"])["reference_lyrics"], saved["reference_lyrics"])
        self.assertEqual(self.client.put(self.endpoint(p) + "/reference",
                                        json={"text": "[Intro]\n[Rain]\n"}).status_code, 400)
        self.assertEqual(studio.load(p["id"])["reference_lyrics"], saved["reference_lyrics"])

    def test_alignment_uses_canonical_text_and_invalidates_old_subtitles(self):
        p = self.save_timed(self.create())
        self.assertEqual(self.client.post(self.endpoint(p) + "/subtitles", json={}).status_code, 200)
        done, fit = self.align(p, model="base", language="vi", device="cpu")
        self.assertEqual(done["status"], "ready", done.get("error"))
        self.assertEqual(done["segments"], SEGMENTS)
        self.assertEqual(done["alignment"]["source"], "reference")
        self.assertEqual(done["alignment"]["engine"], "stable-ts")
        self.assertEqual(done["alignment"]["reference_text"], CLEAN_TEXT)
        self.assertFalse(done["alignment"]["stale"])
        self.assertFalse(done["reference_pending"])
        self.assertIn("kéo dài", done["alignment"]["warnings"][0])
        self.assertEqual(Path(fit.call_args.args[0]).name, "audio.wav")
        self.assertNotIn("ass", done["files"])
        self.assertEqual(self.client.get(self.endpoint(p) + "/files/lyrics.ass").status_code, 404)
        changed = self.client.put(self.endpoint(p) + "/reference", json={"text": "Xin chào mới"})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertTrue(changed.json()["alignment"]["stale"])
        self.assertTrue(changed.json()["reference_pending"])
        self.assertEqual(changed.json()["segments"], SEGMENTS)

    def test_failed_alignment_keeps_old_timing_and_saved_reference_for_retry(self):
        p = self.save_timed(self.create())
        with patch.object(studio.alignment, "align_lyrics", side_effect=RuntimeError("No aligned words")):
            response = self.client.post(self.endpoint(p) + "/align", json={"text": REFERENCE, "separate": False})
            self.assertEqual(response.status_code, 202, response.text)
            failed = self.wait(p["id"])
        self.assertEqual(failed["status"], "error")
        self.assertIn("No aligned words", failed["error"])
        self.assertEqual(failed["segments"], OLD_SEGMENTS)
        self.assertEqual(failed["reference_lyrics"]["text"], CLEAN_TEXT)
        done, _ = self.align(p)
        self.assertEqual(done["status"], "ready", done.get("error"))
        self.assertEqual(done["segments"], SEGMENTS)

    def test_bad_model_result_cannot_change_canonical_spelling_or_old_timing(self):
        p = self.save_timed(self.create())
        altered = copy.deepcopy(SEGMENTS)
        altered[0]["words"][1]["text"] = "sai"
        overlapping = copy.deepcopy(SEGMENTS)
        overlapping[0]["words"][1]["start"] = 0.5
        outside = copy.deepcopy(SEGMENTS)
        outside[-1]["end"] = 4
        outside[-1]["words"][-1]["end"] = 4
        for segments in (altered, overlapping, outside):
            with self.subTest(segments=segments):
                failed, _ = self.align(p, result=aligned_result(segments=segments))
                self.assertEqual(failed["status"], "error")
                self.assertEqual(failed["segments"], OLD_SEGMENTS)

    def test_queued_alignment_rejects_reference_and_timing_edits(self):
        p = self.save_timed(self.create())
        entered, release = threading.Event(), threading.Event()
        def hold(*args, **kwargs):
            entered.set()
            if not release.wait(8):
                raise RuntimeError("Test job did not release")
            return aligned_result()
        with patch.object(studio.alignment, "align_lyrics", side_effect=hold):
            response = self.client.post(self.endpoint(p) + "/align", json={"text": REFERENCE, "separate": False})
            self.assertEqual(response.status_code, 202, response.text)
            self.assertTrue(entered.wait(5))
            try:
                self.assertEqual(self.client.put(self.endpoint(p) + "/reference", json={"text": "khác"}).status_code, 409)
                self.assertEqual(self.client.post(self.endpoint(p) + "/timing", json={"offset_seconds": 0.1}).status_code, 409)
                self.assertEqual(self.client.post(self.endpoint(p) + "/align",
                                                  json={"text": REFERENCE, "separate": False}).status_code, 409)
            finally:
                release.set()
            done = self.wait(p["id"])
        self.assertEqual(done["status"], "ready", done.get("error"))
        self.assertEqual(done["reference_lyrics"]["text"], CLEAN_TEXT)

    def test_global_shift_moves_subtitle_timing_and_rejects_invalid_shift_atomically(self):
        p = self.create()
        p, _ = self.align(p)
        export = self.client.post(self.endpoint(p) + "/subtitles", json={})
        self.assertEqual(export.status_code, 200, export.text)
        response = self.client.post(self.endpoint(p) + "/timing", json={"offset_seconds": 0.25})
        self.assertEqual(response.status_code, 200, response.text)
        shifted = response.json()
        self.assertEqual(shifted["segments"][0]["start"], 0.65)
        self.assertEqual(shifted["segments"][0]["words"][0]["end"], 0.85)
        self.assertEqual(shifted["segments"][-1]["end"], 2.45)
        self.assertEqual(shifted["reference_lyrics"], p["reference_lyrics"])
        self.assertEqual([w["text"] for s in shifted["segments"] for w in s["words"]],
                         [w["text"] for s in SEGMENTS for w in s["words"]])
        self.assertNotIn("srt", shifted["files"])
        self.assertEqual(self.client.post(self.endpoint(p) + "/subtitles", json={}).status_code, 200)
        srt = self.client.get(self.endpoint(p) + "/files/lyrics.srt").text
        self.assertIn("00:00:00,650 --> 00:00:01,350", srt)
        manifest = self.projects / p["id"] / "project.json"
        before = manifest.read_bytes()
        for delta in (-1, 1):
            with self.subTest(delta=delta):
                rejected = self.client.post(self.endpoint(p) + "/timing", json={"offset_seconds": delta})
                self.assertEqual(rejected.status_code, 400, rejected.text)
                self.assertEqual(manifest.read_bytes(), before)
        back = self.client.post(self.endpoint(p) + "/timing", json={"offset_seconds": -0.25})
        self.assertEqual(back.status_code, 200, back.text)
        self.assertEqual(back.json()["segments"], SEGMENTS)
        self.assertEqual(self.client.post(self.endpoint(p) + "/timing", json={"offset_seconds": 31}).status_code, 422)

    def test_alignment_separates_vocals_without_overwriting_uploaded_beat(self):
        p = self.create(beat=True)
        beat_path = self.projects / p["id"] / p["files"]["instrumental"]
        original_beat = beat_path.read_bytes()
        def separate(audio, output_dir, device, progress):
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "instrumental.wav").write_bytes(self.audio_bytes)
            (output_dir / "vocals.wav").write_bytes(self.audio_bytes)
            return output_dir / "instrumental.wav"
        with patch.object(studio.pipeline, "separate_audio", side_effect=separate) as split:
            done, fit = self.align(p, separate=True)
        self.assertEqual(done["status"], "ready", done.get("error"))
        split.assert_called_once()
        self.assertEqual(Path(fit.call_args.args[0]).name, "vocals.wav")
        self.assertEqual(beat_path.read_bytes(), original_beat)
        self.assertEqual(self.client.get(self.endpoint(p) + "/files/vocals.wav").status_code, 200)


    def test_apply_txt_exact_keeps_every_word_timestamp_without_ai(self):
        p = self.save_timed(self.create(), segments=[
            {"start": 0.4, "end": 1.1, "words": [
                {"text": "Sai", "start": 0.4, "end": 0.6},
                {"text": "chữ", "start": 0.8, "end": 1.1},
            ]},
            {"start": 1.6, "end": 2.2, "words": [
                {"text": "Lời", "start": 1.6, "end": 1.9},
                {"text": "cũ", "start": 2.0, "end": 2.2},
            ]},
        ])
        before = copy.deepcopy(p["segments"])
        saved = self.client.put(self.endpoint(p) + "/reference", json={"text": REFERENCE})
        self.assertEqual(saved.status_code, 200, saved.text)
        with patch.object(studio.alignment, "align_lyrics", side_effect=AssertionError("Should not run AI")):
            result = self.client.post(self.endpoint(p) + "/reference/apply-timing", json={"estimate": False})
        self.assertEqual(result.status_code, 200, result.text)
        final = result.json()
        self.assertEqual([w["text"] for x in final["segments"] for w in x["words"]],
                         ["Xin", "chào...", "người", "ơi!"])
        self.assertEqual([(w["start"], w["end"]) for x in final["segments"] for w in x["words"]],
                         [(w["start"], w["end"]) for x in before for w in x["words"]])
        self.assertFalse(final["reference_pending"])
        self.assertFalse(final["alignment"]["estimated"])
        self.assertEqual(final["alignment"]["engine"], "manual-preserve")
        snapshot = self.projects / p["id"] / final["files"]["lyrics_before_txt"]
        self.assertEqual(__import__("json").loads(snapshot.read_text(encoding="utf-8"))["segments"], before)

    def test_apply_txt_requires_explicit_estimation_when_lines_differ(self):
        p = self.save_timed(self.create())
        save = self.client.put(self.endpoint(p) + "/reference", json={"text": REFERENCE})
        self.assertEqual(save.status_code, 200, save.text)
        before = self.client.get(self.endpoint(p)).json()
        strict = self.client.post(self.endpoint(p) + "/reference/apply-timing", json={"estimate": False})
        self.assertEqual(strict.status_code, 409, strict.text)
        self.assertIn("ƯỚC LƯỢNG", strict.json()["detail"])
        self.assertEqual(before["segments"], self.client.get(self.endpoint(p)).json()["segments"])
        self.assertFalse((self.projects / p["id"] / "lyrics-before-txt.json").exists())
        estimate = self.client.post(self.endpoint(p) + "/reference/apply-timing", json={"estimate": True})
        self.assertEqual(estimate.status_code, 200, estimate.text)
        result = estimate.json()
        self.assertEqual(
            [w["text"] for segment in result["segments"] for w in segment["words"]],
            ["Xin", "chào...", "người", "ơi!"],
        )
        self.assertAlmostEqual(result["segments"][0]["start"], OLD_SEGMENTS[0]["start"], places=3)
        self.assertAlmostEqual(result["segments"][-1]["end"], OLD_SEGMENTS[-1]["end"], places=3)
        self.assertTrue(result["alignment"]["estimated"])
        self.assertFalse(result["reference_pending"])
        self.assertEqual(result["alignment"]["engine"], "manual-estimate")
        self.assertIn("ƯỚC LƯỢNG", result["alignment"]["warnings"][0])
        # TXT is now the display source, subtitles must export its spelling.
        export = self.client.post(self.endpoint(p) + "/subtitles", json={})
        self.assertEqual(export.status_code, 200, export.text)
        srt = self.client.get(self.endpoint(p) + "/files/lyrics.srt").text
        self.assertIn("Xin", srt)
        self.assertIn("người", srt)

    def test_apply_txt_estimation_with_same_line_count_preserves_phrase_boundaries(self):
        p = self.save_timed(self.create(), segments=SEGMENTS)
        reference = "Xin thật nhiều người ơi\nCâu thứ hai"
        self.assertEqual(self.client.put(self.endpoint(p) + "/reference", json={"text": reference}).status_code, 200)
        r = self.client.post(self.endpoint(p) + "/reference/apply-timing", json={"estimate": True})
        self.assertEqual(r.status_code, 200, r.text)
        segments = r.json()["segments"]
        self.assertEqual(len(segments), 2)
        self.assertEqual((segments[0]["start"], segments[0]["end"]),
                         (SEGMENTS[0]["start"], SEGMENTS[0]["end"]))
        self.assertEqual((segments[1]["start"], segments[1]["end"]),
                         (SEGMENTS[1]["start"], SEGMENTS[1]["end"]))
        self.assertEqual(" ".join(w["text"] for seg in segments for w in seg["words"]),
                         "Xin thật nhiều người ơi Câu thứ hai")

    def test_apply_txt_rejects_no_project_or_no_reference_or_no_timing(self):
        p = self.create()
        endpoint = self.endpoint(p) + "/reference/apply-timing"
        self.assertEqual(self.client.post(endpoint, json={}).status_code, 400)
        self.assertEqual(self.client.put(self.endpoint(p) + "/reference", json={"text": "Xin chào"}).status_code, 200)
        self.assertEqual(self.client.post(endpoint, json={"estimate": True}).status_code, 400)
        self.assertEqual(self.client.post(endpoint, json={"estimate": "invalid"}).status_code, 422)



if __name__ == "__main__":
    unittest.main(verbosity=2)
