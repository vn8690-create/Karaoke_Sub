"""ASS styling validation and actual rendered placement checks."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from local_studio.pipeline import render_video
from local_studio.subtitles import write_subtitles

LYRICS = [{"start": 0, "end": 2, "words": [
    {"text": "MMMMMMMM", "start": 0, "end": 2},
]}]


def ass_style(folder):
    content = (folder / "lyrics.ass").read_text(encoding="utf-8")
    names = next(line for line in content.splitlines() if line.startswith("Format: Name,")).removeprefix("Format: ").split(", ")
    values = next(line for line in content.splitlines() if line.startswith("Style: ")).removeprefix("Style: ").split(",")
    return dict(zip(names, values))


class SubtitleStyleTests(unittest.TestCase):
    def test_rgb_colors_are_exported_as_bgr_and_plain_subtitles_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            files = write_subtitles(LYRICS, folder)
            default_style = ass_style(folder)
            self.assertEqual(default_style["PrimaryColour"], "&H0000E8FF")
            self.assertEqual(default_style["SecondaryColour"], "&H00FFFFFF")
            self.assertEqual(default_style["Alignment"], "2")
            srt = (folder / files["srt"]).read_text(encoding="utf-8")
            lrc = (folder / files["lrc"]).read_text(encoding="utf-8")
            write_subtitles(LYRICS, folder, style={
                "font_family": "Times New Roman", "text_color": "#12aB34",
                "highlight_color": "#a1B2c3", "position": "top", "margin_percent": 20,
            })
            style = ass_style(folder)
            self.assertEqual(style["Fontname"], "Times New Roman")
            self.assertEqual(style["PrimaryColour"], "&H00C3B2A1")
            self.assertEqual(style["SecondaryColour"], "&H0034AB12")
            self.assertEqual(style["Alignment"], "8")
            self.assertEqual(style["MarginV"], "216")
            self.assertEqual((folder / "lyrics.srt").read_text(encoding="utf-8"), srt)
            self.assertEqual((folder / "lyrics.lrc").read_text(encoding="utf-8"), lrc)

    def test_font_and_margin_scale_with_resolution(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            options = {"font_family": "Segoe UI", "position": "center", "margin_percent": 20}
            write_subtitles(LYRICS, folder, 60, (1920, 1080), options)
            full = ass_style(folder)
            write_subtitles(LYRICS, folder, 60, (1280, 720), options)
            small = ass_style(folder)
            self.assertEqual((full["Fontsize"], small["Fontsize"]), ("60", "40"))
            self.assertEqual((full["MarginV"], small["MarginV"]), ("216", "144"))
            self.assertEqual(small["Alignment"], "5")
            self.assertEqual(small["Fontname"], "Segoe UI")

    def test_rejects_ass_injection_and_invalid_style_before_writing(self):
        invalid = [
            {"font_family": "Arial,54,&H00FFFFFF"},
            {"font_family": "Arial\n[Events]"},
            {"font_family": "{\\an8}Arial"},
            {"font_family": ["Arial"]},
            {"position": "bottom\\N"},
            {"position": 8},
            {"text_color": "#FFFFFF\n"},
            {"highlight_color": "&H0000E8FF"},
            {"text_color": "#FFFF"},
            {"margin_percent": "9"},
            {"margin_percent": True},
            {"margin_percent": float("nan")},
            {"margin_percent": 4},
            {"margin_percent": 26},
            {"untrusted_override": "{\\pos(10,20)}"},
            "Arial",
        ]
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "not-created"
            for style in invalid:
                with self.subTest(style=style), self.assertRaises(ValueError):
                    write_subtitles(LYRICS, folder, style=style)
            self.assertFalse(folder.exists())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class RenderedStyleTests(unittest.TestCase):
    def test_top_and_bottom_placement_change_actual_pixel_position(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            centers = {}
            for position in ("top", "bottom"):
                folder = root / position
                write_subtitles(LYRICS, folder, resolution=(1280, 720), style={"position": position})
                output = folder / "styled.mp4"
                render_video(None, None, folder / "lyrics.ass", output, 2, (1280, 720))
                result = subprocess.run([
                    "ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(output),
                    "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
                ], check=True, capture_output=True)
                frame = result.stdout
                self.assertEqual(len(frame), 1280 * 720 * 3)
                # The unsung part of this word is white; the background is dark.
                rows = [index // 1280 for index, (r, g, b) in enumerate(
                    zip(frame[::3], frame[1::3], frame[2::3])) if r > 180 and g > 180 and b > 180]
                self.assertGreater(len(rows), 100)
                centers[position] = sum(rows) / len(rows)
            self.assertLess(centers["top"], 200)
            self.assertGreater(centers["bottom"], 500)
            self.assertGreater(centers["bottom"] - centers["top"], 400)


if __name__ == "__main__":
    unittest.main()
