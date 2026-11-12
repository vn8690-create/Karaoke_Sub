"""Real FFmpeg smoke for optional motion composition; no Node or HyperFrames needed.

Clips stand in for pre-rendered HyperFrames intro/outro, proving that the
existing karaoke MP4 can be crossfaded with intact delayed audio.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from motion_engine.compositor import compose_argv
from local_studio.pipeline import probe
from local_studio.render_control import render_with_progress
from local_studio.render_quality import verify_output


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class RealMotionCompositorTest(unittest.TestCase):
    def test_intro_outro_crossfade_preserves_song_audio_and_expected_duration(self):
        with tempfile.TemporaryDirectory(prefix="karaoke-motion-ffmpeg-") as tmp:
            root = Path(tmp)
            intro = root / "intro.mp4"
            song = root / "song.mp4"
            outro = root / "outro.mp4"
            output = root / "result.mp4"
            size = "640x360"
            for color, target in (("purple", intro), ("blue", outro)):
                subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                    "-y", "-f", "lavfi", "-i", f"color=c={color}:s={size}:r=30:d=3",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    str(target),
                ], check=True, timeout=60)
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", f"color=c=green:s={size}:r=30:d=2.5",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2.5:sample_rate=44100",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest", str(song),
            ], check=True, timeout=60)
            args, duration = compose_argv(
                song, intro, outro, output, 2.5, (1280, 720), True, "fade")
            render_with_progress(args, cwd=root, duration=duration)
            verify_output(output, duration, (1280, 720), True, probe)
            info = probe(output)
            self.assertAlmostEqual(info["duration"], duration, delta=0.2)
            self.assertTrue(any(s["codec_type"] == "audio" for s in info["streams"]))


if __name__ == "__main__":
    unittest.main()
