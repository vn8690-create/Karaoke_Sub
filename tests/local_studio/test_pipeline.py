"""Run independently: python -m unittest discover -s tests/local_studio -v."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from local_studio.pipeline import extract_audio, probe, render_video, transcribe_audio, write_subtitles


class SubtitleTests(unittest.TestCase):
    def test_word_sweep_preserves_gaps_and_escapes_user_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = write_subtitles([
                {"start": 1, "end": 2.1, "words": [
                    {"text": "Xin", "start": 1, "end": 1.2},
                    {"text": "{\\an8}chào", "start": 1.5, "end": 2.1},
                ]},
            ], Path(tmp))
            ass = (Path(tmp) / files["ass"]).read_text("utf-8")
            self.assertIn("{\\kf20}Xin {\\k30}", ass)
            self.assertIn("{\\kf60}｛＼an8｝chào", ass)
            self.assertNotIn("{\\an8}", ass)
            self.assertIn("00:00:01,000 --> 00:00:02,100", (Path(tmp) / files["srt"]).read_text("utf-8"))
            self.assertIn("<00:01.50>", (Path(tmp) / files["lrc"]).read_text("utf-8"))

    def test_rounding_carries_seconds_into_minutes(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_subtitles([{"start": 59.999, "end": 61, "words": [
                {"text": "hello", "start": 59.999, "end": 61},
            ]}], Path(tmp))
            self.assertIn("0:01:00.00,0:01:01.00", (Path(tmp) / "lyrics.ass").read_text("utf-8"))

    def test_asr_overlap_is_normalized_across_segment_boundaries(self):
        fake_whisper = SimpleNamespace(
            load_model=lambda *a, **kw: object(), load_audio=lambda p: [0] * 32000,
            transcribe=lambda *a, **kw: {"segments": [
                {"start": 0, "words": [{"text": "Xin", "start": 0.1, "end": 1.0}]},
                {"start": 0.9, "words": [{"text": "chào", "start": 0.9, "end": 1.5}]},
            ]},
        )
        with tempfile.TemporaryDirectory() as tmp, patch.dict("sys.modules", {"whisper_timestamped": fake_whisper}), \
                patch("local_studio.pipeline._device", return_value="cpu"), \
                patch("local_studio.pipeline._model_dir", return_value=Path(tmp)), \
                patch("local_studio.pipeline._free_cuda"):
            segments = transcribe_audio(Path(tmp) / "audio.wav")
        self.assertEqual(segments[1]["start"], 1.0)
        self.assertGreaterEqual(segments[1]["words"][0]["start"], segments[0]["words"][-1]["end"])

    def test_asr_word_end_is_clamped_to_audio_length(self):
        fake_whisper = SimpleNamespace(
            load_model=lambda *a, **kw: object(), load_audio=lambda p: [0] * 16000,
            transcribe=lambda *a, **kw: {"segments": [
                {"start": 0, "words": [
                    {"text": "Chào", "start": 0.1, "end": 1.3},
                    {"text": "bạn", "start": 1.3, "end": 2.0},
                ]},
            ]},
        )
        with tempfile.TemporaryDirectory() as tmp, patch.dict("sys.modules", {"whisper_timestamped": fake_whisper}), \
                patch("local_studio.pipeline._device", return_value="cpu"), \
                patch("local_studio.pipeline._model_dir", return_value=Path(tmp)), \
                patch("local_studio.pipeline._free_cuda"):
            segments = transcribe_audio(Path(tmp) / "audio.wav")
        self.assertEqual(segments[0]["end"], 1.0)
        self.assertEqual(len(segments[0]["words"]), 1)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class RealMediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="karaoke-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "nhạc của tôi's bài hát"
        self.root.mkdir()
        self.source = self.root / "gốc.wav"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=1.3", "-y", str(self.source)], check=True)
        self.audio = self.root / "audio.wav"
        self.duration = extract_audio(self.source, self.audio)
        write_subtitles([{"start": 0.1, "end": 1.1, "words": [
            {"text": "Xin", "start": 0.1, "end": 0.4},
            {"text": "chào", "start": 0.6, "end": 1.1},
        ]}], self.root, resolution=(1280, 720))

    def test_render_with_audio_and_background_loop(self):
        background = self.root / "nền.mp4"
        # Short blue clip carries its own tone; renderer must select song audio.
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=blue:s=320x240:d=0.4:r=25", "-f", "lavfi", "-i",
                        "sine=frequency=880:duration=0.4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-y", str(background)], check=True)
        output = self.root / "karaoke.mp4"
        render_video(self.audio, background, self.root / "lyrics.ass", output, self.duration, (1280, 720))
        info = probe(output)
        self.assertAlmostEqual(info["duration"], self.duration, delta=0.1)
        video = next(stream for stream in info["streams"] if stream["codec_type"] == "video")
        self.assertEqual((video["width"], video["height"]), (1280, 720))
        self.assertEqual(sum(s["codec_type"] == "audio" for s in info["streams"]), 1)
        self.assertGreater(info["duration"], probe(background)["duration"])

    def test_silent_render_has_no_audio_stream(self):
        output = self.root / "silent.mp4"
        render_video(None, None, self.root / "lyrics.ass", output, self.duration, (1280, 720))
        info = probe(output)
        self.assertFalse(any(s["codec_type"] == "audio" for s in info["streams"]))
        self.assertAlmostEqual(info["duration"], self.duration, delta=0.1)

    def test_still_image_background_repeats_for_song_duration(self):
        image = self.root / "nền ảnh.png"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=green:s=320x240", "-frames:v", "1", str(image)], check=True)
        output = self.root / "still.mp4"
        render_video(self.audio, image, self.root / "lyrics.ass", output, self.duration, (1280, 720))
        self.assertAlmostEqual(probe(output)["duration"], self.duration, delta=0.1)


if __name__ == "__main__":
    unittest.main()
