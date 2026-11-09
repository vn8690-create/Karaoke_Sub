"""Small, dependency-free subtitle writers for the local desktop workflow."""

from pathlib import Path
import re


def _clock(seconds: float, milliseconds: bool = False) -> str:
    scale = 1000 if milliseconds else 100
    value = max(0, round(float(seconds) * scale))
    whole, fraction = divmod(value, scale)
    hours, rem = divmod(whole, 3600)
    minutes, seconds = divmod(rem, 60)
    if milliseconds:
        return f"{hours:02}:{minutes:02}:{seconds:02},{fraction:03}"
    return f"{hours}:{minutes:02}:{seconds:02}.{fraction:02}"


def _text(value: str) -> str:
    # ASS override braces and backslash escape sequences must never be interpreted
    # as instructions when a user edits a lyric. These readable full-width forms
    # preserve the content without introducing overrides or forced line breaks.
    return re.sub(r"\s+", " ", str(value)).strip().replace("\\", "＼").replace("{", "｛").replace("}", "｝")


def _lines(segments: list[dict]):
    """Wrap long transcription segments into readable, separately timed lines."""
    for segment in segments:
        words = segment.get("words", [])
        chunk = []
        for word in words:
            text = str(word.get("text", "")).strip()
            if not text:
                continue
            if chunk and (len(chunk) >= 8 or len(" ".join(w["text"] for w in chunk)) + len(text) > 50):
                yield {"start": chunk[0]["start"], "end": chunk[-1]["end"], "words": chunk}
                chunk = []
            chunk.append({"text": text, "start": float(word["start"]), "end": float(word["end"])})
        if chunk:
            yield {"start": chunk[0]["start"], "end": chunk[-1]["end"], "words": chunk}


def write_subtitles(segments: list, output_dir: Path, font_size: int = 54,
                    resolution: tuple = (1920, 1080)) -> dict:
    """Write UTF-8 ASS (word sweep), SRT and word-enhanced LRC exports.

    Times are seconds. Words are expected to be validated and monotonically
    ordered by the API. Line breaks are automatically added to long segments.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    width, height = resolution
    margin = max(24, round(height * 0.09))
    # Scale the UI's 1080p font-size setting together with output dimensions.
    size = max(14, round(font_size * height / 1080))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial,{size},&H0000E8FF,&H00FFFFFF,&H00101020,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,60,60,{margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass_lines, srt_lines = [], []
    lrc_lines = ["[re:Karaoke Sub Local Studio]", "[ve:1.0]"]
    for number, line in enumerate(_lines(segments), 1):
        start, end = line["start"], line["end"]
        if end <= start:
            continue
        # Use rounded absolute centiseconds so rounding cannot accumulate drift.
        cursor = round(start * 100)
        karaoke = []
        for index, word in enumerate(line["words"]):
            word_start = max(cursor, round(word["start"] * 100))
            word_end = max(word_start + 1, round(word["end"] * 100))
            gap = word_start - cursor
            if gap:
                # A zero-width timed syllable preserves pauses between words.
                karaoke.append(f"{{\\k{gap}}}\u200b")
            karaoke.append(f"{{\\kf{word_end - word_start}}}{_text(word['text'])}")
            if index != len(line["words"]) - 1:
                karaoke.append(" ")
            cursor = word_end
        ass_lines.append(f"Dialogue: 0,{_clock(start)},{_clock(end)},Karaoke,,0,0,0,,{''.join(karaoke)}")
        plain = " ".join(str(word["text"]).strip() for word in line["words"])
        srt_lines.append(f"{number}\n{_clock(start, True)} --> {_clock(end, True)}\n{plain}\n")

        def lrc_time(time):
            total = max(0, round(time * 100))
            minutes, remainder = divmod(total, 6000)
            seconds, cents = divmod(remainder, 100)
            return f"{minutes:02}:{seconds:02}.{cents:02}"

        enhanced = " ".join(f"<{lrc_time(word['start'])}>{str(word['text']).strip()}" for word in line["words"])
        lrc_lines.append(f"[{lrc_time(start)}]{enhanced}<{lrc_time(end)}>")
    (output_dir / "lyrics.ass").write_text(header + "\n".join(ass_lines) + "\n", encoding="utf-8")
    (output_dir / "lyrics.srt").write_text("\n".join(srt_lines), encoding="utf-8")
    (output_dir / "lyrics.lrc").write_text("\n".join(lrc_lines) + "\n", encoding="utf-8")
    return {"ass": "lyrics.ass", "srt": "lyrics.srt", "lrc": "lyrics.lrc"}
