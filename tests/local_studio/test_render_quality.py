"""Render-quality metadata checks, including malformed and truncated exports."""
import tempfile
from pathlib import Path
import unittest

from local_studio.render_quality import analyze_probe, verify_output


def info(duration=60.0, video_duration=60.0, audio_duration=60.0, width=1920,
         height=1080, has_audio=True, audio_start="0", video_start="0"):
    streams = [{
        "codec_type": "video", "codec_name": "h264", "width": width,
        "height": height, "duration": str(video_duration), "start_time": video_start,
    }]
    if has_audio:
        streams.append({
            "codec_type": "audio", "codec_name": "aac", "duration": str(audio_duration),
            "start_time": audio_start,
        })
    return {"duration": duration, "format": {"duration": str(duration)}, "streams": streams}


class RenderQualityTests(unittest.TestCase):
    def test_normal_export_and_silent_mode(self):
        report = analyze_probe(info(), 60, (1920, 1080), True)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["issues"], [])
        report = analyze_probe(info(has_audio=False), 60, (1920, 1080), False)
        self.assertTrue(report["ok"], report)

    def test_truncated_file_is_rejected(self):
        report = analyze_probe(info(duration=51, video_duration=51, audio_duration=51),
                               60, (1920, 1080), True)
        self.assertFalse(report["ok"])
        codes = {issue["code"] for issue in report["issues"]}
        self.assertIn("duration_mismatch", codes)
        self.assertIn("video_duration", codes)
        self.assertIn("audio_truncated", codes)

    def test_missing_audio_resolution_and_av_offset(self):
        report = analyze_probe(info(width=1280, has_audio=False), 60, (1920, 1080), True)
        self.assertEqual({item["code"] for item in report["issues"]},
                         {"resolution_mismatch", "audio_missing"})
        report = analyze_probe(info(audio_start="1.5"), 60, (1920, 1080), True)
        self.assertIn("av_start_mismatch", {item["code"] for item in report["issues"]})

    def test_audio_not_expected_and_corrupt_probe(self):
        self.assertIn("unexpected_audio", {x["code"] for x in
                      analyze_probe(info(), 60, (1920, 1080), False)["issues"]})
        self.assertFalse(analyze_probe({"streams": []}, 60, (1920, 1080), True)["ok"])

    def test_small_encoder_rounding_is_allowed(self):
        report = analyze_probe(info(duration=1.333, video_duration=1.333,
                                    audio_duration=1.3), 1.3, (1920, 1080), True)
        self.assertTrue(report["ok"], report)

    def test_verify_output_refuses_empty_and_truncated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.mp4"
            with self.assertRaises(RuntimeError):
                verify_output(path, 60, (1920, 1080), True, lambda _: info())
            path.write_bytes(b"not real mp4 but existence can be tested")
            with self.assertRaises(RuntimeError):
                verify_output(path, 60, (1920, 1080), True, lambda _: info(duration=30))
            self.assertTrue(verify_output(path, 60, (1920, 1080), True, lambda _: info())["ok"])


if __name__ == "__main__":
    unittest.main()
