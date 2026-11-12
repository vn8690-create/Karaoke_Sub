"""Karaoke 3-2-1 count-in: time-safe ASS overlay and export API regression."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from local_studio.subtitles import countdown_cues, write_subtitles


def lyric(start, end, text):
    return {"start": start, "end": end, "words": [
        {"text": text, "start": start, "end": end}
    ]}


class CountdownTests(unittest.TestCase):
    def test_only_full_three_second_gaps_countdown(self):
        segments = [
            lyric(5, 7, "Câu đầu"),
            lyric(8.8, 10, "Không nghỉ đủ"),
            lyric(13, 14, "Nghỉ đủ ba"),
            lyric(14.1, 16, "Sát câu trước"),
            lyric(19.8, 21, "Sau nghỉ"),
        ]
        cues = countdown_cues(segments, True)
        self.assertEqual(cues, [
            (2.0, 3.0, "3"), (3.0, 4.0, "2"), (4.0, 5.0, "1"),
            (10.0, 11.0, "3"), (11.0, 12.0, "2"), (12.0, 13.0, "1"),
            (16.8, 17.8, "3"), (17.8, 18.8, "2"), (18.8, 19.8, "1"),
        ])
        self.assertEqual(countdown_cues(segments, False), [])
        self.assertEqual(countdown_cues([], True), [])
        self.assertEqual(countdown_cues([lyric(.1, 2, "No count")], True), [])

    def test_countdown_ass_has_correct_times_and_keeps_srt_lrc_unchanged(self):
        segments = [lyric(5, 7, "Xin"), lyric(7.7, 8.3, "chào"),
                    lyric(12, 13, "bạn")]
        before_segments = repr(segments)
        with TemporaryDirectory() as temp:
            root = Path(temp)
            write_subtitles(segments, root, countdown=False)
            default_ass = (root / "lyrics.ass").read_text("utf-8")
            srt = (root / "lyrics.srt").read_bytes()
            lrc = (root / "lyrics.lrc").read_bytes()
            self.assertNotIn("Style: Countdown", default_ass)
            write_subtitles(segments, root, countdown=True)
            ass = (root / "lyrics.ass").read_text("utf-8")
            self.assertIn("Style: Countdown,", ass)
            self.assertIn("♪  ", ass)
            self.assertIn("♪", ass)
            self.assertNotIn("}}3", ass)
            self.assertNotIn("}}2", ass)
            self.assertNotIn("}}1", ass)
            styles = [line for line in ass.splitlines() if line.startswith("Style: Countdown,")]
            self.assertEqual(len(styles), 1)
            # Musical cues stay smaller than ordinary karaoke lyric lettering.
            self.assertLess(int(styles[0].split(",")[2]), 54)
            self.assertIn("Dialogue: 1,0:00:02.00,0:00:03.00,Countdown", ass)
            self.assertIn("Dialogue: 1,0:00:04.00,0:00:05.00,Countdown", ass)
            self.assertIn("Dialogue: 1,0:00:09.00,0:00:10.00,Countdown", ass)
            self.assertIn("Dialogue: 1,0:00:11.00,0:00:12.00,Countdown", ass)
            self.assertEqual(ass.count("Dialogue: 1,"), 6)
            self.assertEqual(ass.count("Dialogue: 0,"), default_ass.count("Dialogue: 0,"))
            self.assertEqual(srt, (root / "lyrics.srt").read_bytes())
            self.assertEqual(lrc, (root / "lyrics.lrc").read_bytes())
            self.assertEqual(before_segments, repr(segments))

    def test_no_countdown_mid_lyric_or_at_tight_phrases(self):
        segments = [lyric(0, 3, "A"), lyric(4, 6, "B"), lyric(9, 12, "C")]
        self.assertEqual(countdown_cues(segments, True),
                         [(6.0, 7.0, "3"), (7.0, 8.0, "2"), (8.0, 9.0, "1")])


if __name__ == "__main__":
    unittest.main()
