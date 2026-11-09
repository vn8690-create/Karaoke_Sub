"""Check rendered pixels and audio, rather than just generated ASS strings."""

from array import array
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from local_studio.pipeline import render_video, write_subtitles


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class RenderedTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="karaoke-timing-")
        cls.root = Path(cls.temp.name)
        cls.audio = cls.root / "timed-tone.wav"
        # An independent audible landmark at 0.75s detects any export shift.
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
            "sine=frequency=700:sample_rate=44100:duration=0.4", "-af",
            "adelay=750,apad=whole_dur=3", str(cls.audio),
        ], check=True)
        write_subtitles([{"start": 0.5, "end": 2.5, "words": [
            {"text": "MMMM", "start": 0.5, "end": 1.0},
            {"text": "MMMM", "start": 2.0, "end": 2.5},
        ]}], cls.root, resolution=(1280, 720))
        cls.video = cls.root / "timing.mp4"
        render_video(cls.audio, None, cls.root / "lyrics.ass", cls.video, 3, (1280, 720))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def yellow_pixels(self, position):
        result = subprocess.run([
            "ffmpeg", "-v", "error", "-ss", str(position), "-i", str(self.video),
            "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ], check=True, capture_output=True)
        frame = result.stdout
        self.assertEqual(len(frame), 1280 * 720 * 3)
        left = right = 0
        for index, (red, green, blue) in enumerate(zip(frame[::3], frame[1::3], frame[2::3])):
            # Export's sung color is yellow. White lyrics and the navy background
            # are excluded; compression noise around glyph edges is tolerated.
            if red > 160 and green > 130 and blue < 100:
                if index % 1280 < 640:
                    left += 1
                else:
                    right += 1
        return left, right

    def test_word_sweep_holds_during_pause_before_next_word(self):
        before = self.yellow_pixels(0.3)
        first_mid = self.yellow_pixels(0.75)
        gap_start = self.yellow_pixels(1.25)
        gap_end = self.yellow_pixels(1.75)
        second_mid = self.yellow_pixels(2.25)
        after = self.yellow_pixels(2.75)
        self.assertEqual(before, (0, 0))
        self.assertGreater(first_mid[0], 100)
        self.assertGreater(gap_start[0], first_mid[0])
        self.assertLessEqual(gap_start[1], 20)
        self.assertLessEqual(gap_end[1], 20)
        self.assertAlmostEqual(gap_start[0], gap_end[0], delta=30)
        self.assertGreater(second_mid[1], 100)
        self.assertEqual(after, (0, 0))

    def test_export_preserves_audible_landmark_time(self):
        result = subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(self.video), "-map", "0:a:0",
            "-ac", "1", "-ar", "16000", "-f", "s16le", "-",
        ], check=True, capture_output=True)
        samples = array("h")
        samples.frombytes(result.stdout)
        # A high threshold avoids interpreting AAC's tiny pre-echo as the tone.
        onset = next(index / 16000 for index, value in enumerate(samples) if abs(value) > 1500)
        self.assertAlmostEqual(onset, 0.75, delta=0.04)


if __name__ == "__main__":
    unittest.main()
