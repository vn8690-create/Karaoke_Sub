"""FFmpeg-only benchmark smoke tests without user media or AI downloads."""
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from local_studio.benchmark import benchmark, main


class RenderBenchmarkValidationTests(unittest.TestCase):
    def test_validation_rejects_invalid_durations_and_resolutions(self):
        for value in (-2, 0, float("nan"), float("inf"), 1201):
            with self.subTest(value=value), self.assertRaises(ValueError):
                benchmark(duration=value)
        with self.assertRaises(ValueError):
            benchmark(duration=5, resolution="4K")

    def test_cli_rejects_invalid_duration(self):
        self.assertEqual(main(["--seconds", "0"]), 1)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class RenderBenchmarkRealMediaTests(unittest.TestCase):
    def test_short_benchmark_produces_valid_mp4(self):
        report = benchmark(1.5, "720p", quiet=True)
        self.assertTrue(report["ok"])
        self.assertEqual(report["resolution"], "1280x720")
        self.assertTrue(report["has_audio"])
        self.assertLess(abs(report["actual_seconds"] - 1.5), 0.15)
        self.assertGreater(report["relative_speed_x"], 0)
        self.assertGreater(report["output_mb"], 0)

    def test_looped_background_and_optional_saved_output(self):
        with tempfile.TemporaryDirectory(prefix="nvs-benchmark-test-") as tmp:
            path = Path(tmp) / "report-video.mp4"
            report = benchmark(1.5, "720p", loop_background=True,
                               save_output=path, quiet=True)
            self.assertTrue(report["ok"])
            self.assertTrue(report["loop_background"])
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
