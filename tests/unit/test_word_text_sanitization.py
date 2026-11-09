"""Tests for Word text sanitization — ensures embedded newlines never reach ASS output."""

import pytest
from karaoke_gen.lyrics_transcriber.types import Word, LyricsSegment
from karaoke_gen.lyrics_transcriber.output.ass.lyrics_line import LyricsLine
from karaoke_gen.lyrics_transcriber.output.ass.config import ScreenConfig


class TestWordTextSanitization:
    """Word.__post_init__ must strip whitespace/newlines from text."""

    def test_trailing_newline_stripped(self):
        word = Word(id="w1", text="spell\n", start_time=1.0, end_time=2.0)
        assert word.text == "spell"

    def test_trailing_double_newline_stripped(self):
        word = Word(id="w1", text="end\n\n", start_time=1.0, end_time=2.0)
        assert word.text == "end"

    def test_leading_whitespace_stripped(self):
        word = Word(id="w1", text=" hello", start_time=1.0, end_time=2.0)
        assert word.text == "hello"

    def test_mixed_whitespace_stripped(self):
        word = Word(id="w1", text="\n spell \n", start_time=1.0, end_time=2.0)
        assert word.text == "spell"

    def test_clean_text_unchanged(self):
        word = Word(id="w1", text="hello", start_time=1.0, end_time=2.0)
        assert word.text == "hello"

    def test_from_dict_strips_text(self):
        """from_dict must also strip — this was the original bug."""
        word = Word.from_dict({
            "id": "w1",
            "text": "spell\n",
            "start_time": 1.0,
            "end_time": 2.0,
        })
        assert word.text == "spell"

    def test_from_dict_with_double_newline(self):
        word = Word.from_dict({
            "id": "w1",
            "text": "broken\n\n",
            "start_time": 1.0,
            "end_time": 2.0,
        })
        assert word.text == "broken"


class TestASSOutputSanitization:
    """ASS output must never contain literal newlines in dialogue text."""

    def _make_segment(self, words_data):
        """Helper to create a LyricsSegment from word tuples (text, start, end)."""
        words = [
            Word(id=f"w{i}", text=text, start_time=start, end_time=end)
            for i, (text, start, end) in enumerate(words_data)
        ]
        text = " ".join(w.text for w in words)
        return LyricsSegment(
            id="seg1", text=text, words=words,
            start_time=words[0].start_time, end_time=words[-1].end_time,
        )

    def test_ass_text_no_literal_newlines(self):
        """Defensive strip in _create_ass_text catches newlines that bypass __post_init__.

        Word.__post_init__ normally strips newlines, but this test verifies the
        defensive strip at the ASS output boundary by injecting newlines directly
        into Word.text after construction (bypassing __post_init__).
        """
        from datetime import timedelta

        # Build words normally first (clean text)
        words = [
            Word(id="w0", text="the", start_time=54.11, end_time=54.26),
            Word(id="w1", text="spell", start_time=54.30, end_time=55.14),
            Word(id="w2", text="we're", start_time=55.18, end_time=55.83),
            Word(id="w3", text="under", start_time=55.93, end_time=57.24),
        ]
        # Inject newlines directly, bypassing __post_init__
        object.__setattr__(words[1], "text", "spell\n")
        object.__setattr__(words[3], "text", "under\n")

        segment = LyricsSegment(
            id="seg1", text="the spell we're under",
            words=words, start_time=54.11, end_time=57.24,
        )
        config = ScreenConfig(line_height=50)
        line = LyricsLine(segment=segment, screen_config=config)
        ass_text = line._create_ass_text(timedelta(seconds=54.0))
        assert "\n" not in ass_text, f"ASS text contains literal newline: {repr(ass_text)}"
        assert "the" in ass_text
        assert "spell" in ass_text
        assert "we're" in ass_text
        assert "under" in ass_text
