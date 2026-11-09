"""Align supplied, correct lyrics to real audio using Whisper cross-attention.

The text is the reference: the model finds timestamps instead of inventing a new
transcript. Word intervals come only from stable-ts forced alignment. We reject
missing/zero-duration words rather than silently spreading text across a song.
"""
from __future__ import annotations

from bisect import bisect_left
from collections.abc import Callable
import math
from pathlib import Path
import re
import unicodedata

from .pipeline import _device, _free_cuda, _model_dir, probe

_MAX_TEXT = 100_000
_MODELS = {"tiny", "base", "small", "medium", "large-v3"}


def clean_lyrics(text: str) -> dict:
    """Remove lyric-sheet directions, retaining repeated sung lines verbatim.

    Whitespace within a line is normalized to one space. Square-bracketed tags
    and performance notes are not sung lyrics, whether alone or inline. Literal
    trailing backslashes from copied Markdown are also removed.
    """
    if not isinstance(text, str):
        raise ValueError("Lời chuẩn phải là văn bản.")
    if len(text) > _MAX_TEXT:
        raise ValueError("Lời chuẩn tối đa 100.000 ký tự.")
    lines, ignored = [], 0
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")
    for raw in text.split("\n"):
        line = re.sub(r"\\+\s*$", "", raw).strip()
        if not line:
            continue
        outside, depth = [], 0
        for char in line:
            if char == "[":
                if depth == 0:
                    outside.append(" ")
                depth += 1
            elif char == "]" and depth:
                depth -= 1
            elif depth == 0:
                outside.append(char)
        line = "".join(outside)
        line = " ".join(line.split()).strip()
        if not line:
            ignored += 1
            continue
        if not any(char.isalnum() for char in line):
            ignored += 1
            continue
        if any(len(word) > 300 for word in line.split()):
            raise ValueError("Một từ trong lời chuẩn quá dài (tối đa 300 ký tự).")
        lines.append(line)
    if not lines:
        raise ValueError("Chưa có lời được hát. Hãy nhập câu hát, không chỉ các nhãn [Verse]/[Chorus].")
    return {"text": "\n".join(lines), "lines": lines, "ignored_lines": ignored}


def _compact(text: str) -> str:
    # Tokenizers may compose Vietnamese combining marks. NFC comparison keeps
    # accent/case/punctuation identity while allowing that equivalent encoding.
    return "".join(unicodedata.normalize("NFC", text).split())


def _reference_words(line: str) -> list[str]:
    """Attach standalone punctuation to lexical words, without losing text.

    Punctuation itself has no sound interval, so `ơi ...` remains exactly that
    spelling in a single displayed word instead of receiving a fabricated time.
    """
    words, prefix = [], []
    for token in line.split():
        if any(char.isalnum() for char in token):
            words.append(" ".join(prefix + [token]))
            prefix = []
        elif words:
            words[-1] += " " + token
        else:
            prefix.append(token)
    if prefix and words:
        words[-1] += " " + " ".join(prefix)
    return words


def _restore_reference(cleaned: dict, result: dict, duration: float) -> tuple[list[dict], list[str]]:
    """Map character spans, not word counts, back onto exact reference text."""
    raw_words = []
    position = 0
    for segment in result.get("segments", []):
        for raw in segment.get("words", []):
            text = _compact(str(raw.get("word", raw.get("text", ""))))
            if not text:
                continue
            try:
                start, end = float(raw["start"]), float(raw["end"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Model không trả đủ mốc thời gian. Hãy thử lại với vocal/model khác.") from exc
            if not math.isfinite(start) or not math.isfinite(end):
                raise ValueError("Model trả mốc thời gian không hợp lệ. Hãy thử lại.")
            raw_words.append({"text": text, "left": position, "right": position + len(text),
                              "start": start, "end": end, "probability": raw.get("probability")})
            position += len(text)
    expected = _compact(cleaned["text"])
    actual = "".join(w["text"] for w in raw_words)
    if not raw_words or actual != expected:
        raise ValueError("Không căn được đầy đủ lời chuẩn. Kiểm tra lời có khớp bản nhạc, đủ các đoạn điệp khúc lặp; thử tách vocal hoặc model lớn hơn.")

    segments, warnings = [], []
    right_edges = [w["right"] for w in raw_words]
    cursor, previous_end, uncertain = 0, 0.0, 0
    invalid = []
    for line_index, line in enumerate(cleaned["lines"], 1):
        line_words = []
        for text in _reference_words(line):
            left, right = cursor, cursor + len(_compact(text))
            cursor = right
            first = bisect_left(right_edges, left + 1)
            parts = []
            for raw_index in range(first, len(raw_words)):
                raw = raw_words[raw_index]
                if raw["left"] >= right:
                    break
                parts.append(raw)
            if not parts:
                invalid.append(text)
                continue
            # A tokenizer sometimes attaches a punctuation-only token to a word.
            # The character mapping tolerates that; it never guesses timing for
            # two lexical words that the model left without separate alignment.
            start, end = parts[0]["start"], parts[-1]["end"]
            if start < previous_end - 0.04 or start < -0.04 or end > duration + 0.08:
                invalid.append(text)
                continue
            start, end = max(0.0, previous_end, start), min(duration, end)
            start, end = round(start, 3), round(end, 3)
            if end <= start:
                invalid.append(text)
                continue
            probability = [float(p["probability"]) for p in parts
                           if isinstance(p.get("probability"), (int, float)) and math.isfinite(p["probability"])]
            if end - start < 0.04 or end - start > 8 or (probability and min(probability) < 0.15):
                uncertain += 1
            line_words.append({"text": text, "start": start, "end": end})
            previous_end = end
        # API segments allow at most 100 words, even if the input has a very long
        # physical line. Ordinary lyric-sheet line breaks stay intact.
        for offset in range(0, len(line_words), 100):
            words = line_words[offset:offset + 100]
            if words:
                segments.append({"start": words[0]["start"], "end": words[-1]["end"], "words": words})
    if invalid:
        example = ", ".join(repr(word) for word in invalid[:5])
        raise ValueError(f"Không căn chắc được {len(invalid)} từ (ví dụ: {example}). Lời chuẩn vẫn được giữ; hãy kiểm tra lời có đúng bản thu/đủ đoạn lặp, tách vocal hoặc thử model khác.")
    if not segments:
        raise ValueError("Không tìm được vị trí giọng hát cho lời chuẩn. Hãy kiểm tra file âm thanh.")
    if uncertain:
        warnings.append(f"{uncertain} từ có độ tin cậy thấp, quá ngắn hoặc kéo dài; hãy nghe và rà lại mốc trước khi xuất.")
    return segments, warnings


def _detect_language(network, audio: Path, device: str) -> tuple[str, float]:
    """Inspect an energetic audio window rather than a potentially silent intro."""
    import numpy as np
    import whisper

    samples = whisper.load_audio(str(audio.resolve()))
    width = 30 * 16000
    if len(samples) > width:
        cumulative = np.concatenate(([0.0], np.cumsum(np.square(samples, dtype=np.float64))))
        starts = list(range(0, len(samples) - width + 1, 5 * 16000))
        starts.append(len(samples) - width)
        begin = max(starts, key=lambda index: cumulative[index + width] - cumulative[index])
        samples = samples[begin:begin + width]
    mel = whisper.log_mel_spectrogram(whisper.pad_or_trim(samples), n_mels=network.dims.n_mels).to(device)
    _, probabilities = network.detect_language(mel)
    language = max(probabilities, key=probabilities.get)
    return language, float(probabilities[language])


def align_lyrics(audio: Path, text: str, model: str = "small", language: str = "vi", device: str = "auto",
                 progress: Callable[[str], None] = lambda _: None) -> dict:
    """Fit the reference lyrics to audio with local, multilingual forced alignment."""
    cleaned = clean_lyrics(text)
    if model not in _MODELS:
        raise ValueError("Model Whisper không hợp lệ.")
    if not language:
        language = "vi"
    device = _device(device)
    try:
        import stable_whisper
    except ImportError as exc:
        raise RuntimeError("Thiếu stable-ts. Cập nhật thư viện bằng .venv-local\\Scripts\\python.exe -m pip install -r requirements-local.txt rồi mở lại app.") from exc
    duration = float(probe(Path(audio))["duration"])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Không đọc được thời lượng âm thanh để căn lời.")
    cache = _model_dir() / "whisper"
    cache.mkdir(parents=True, exist_ok=True)
    # Older whisper-timestamped caches one extra `whisper` directory. Both use
    # the same OpenAI checkpoint; reuse it instead of downloading another copy.
    checkpoint = next((str(p) for p in (cache / f"{model}.pt", cache / "whisper" / f"{model}.pt") if p.is_file()), model)
    network = None
    try:
        progress(f"Đang tải Whisper {model} ({device}) để căn lời chuẩn; lần đầu cần mạng tải model.")
        network = stable_whisper.load_model(checkpoint, device=device, download_root=str(cache))
        detection_warning = None
        if language == "auto":
            progress("Đang nhận diện ngôn ngữ từ giọng hát…")
            language, certainty = _detect_language(network, Path(audio), device)
            detection_warning = f"Ngôn ngữ tự nhận diện: {language} ({certainty:.0%}). Nếu không đúng, chọn Tiếng Việt/English rồi căn lại."
        progress("Đang so khớp lời chuẩn với vị trí giọng hát từng từ…")
        def report(done: float, total: float):
            progress(f"Đang căn lời theo giọng hát: {min(done, total):.1f}/{total:.1f} giây")
        result = network.align(str(Path(audio).resolve()), cleaned["text"], language=language,
                               original_split=True, remove_instant_words=False,
                               token_step=200, fast_mode=False, word_dur_factor=None, max_word_dur=10.0,
                               verbose=None, vad=False, suppress_silence=True, regroup=False,
                               progress_callback=report)
        if result is None:
            raise ValueError("Không căn được lời chuẩn theo giọng hát. Kiểm tra đúng bản nhạc và thử tách vocal.")
        payload = result.to_dict()
        segments, warnings = _restore_reference(cleaned, payload, duration)
        if detection_warning:
            warnings.insert(0, detection_warning)
        return {"segments": segments, "warnings": warnings, "text": cleaned["text"],
                "ignored_lines": cleaned["ignored_lines"], "engine": "stable-ts", "language": language}
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            raise RuntimeError("GPU hết VRAM khi căn lời. Chọn Small/Base hoặc CPU rồi thử lại.") from exc
        raise
    finally:
        del network
        _free_cuda()
