"""Use authoritative TXT lyrics with already-verified karaoke timing, without AI.

Preserve exact word timestamps only when both line and word counts match.
An explicit estimate mode maps new words across the existing speech-time axis;
these new per-word timestamps MUST be labeled approximate, not AI-aligned.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite

from .alignment import _reference_words


def _safe_words(lines: list[str]) -> list[list[str]]:
    tokens = [_reference_words(line) for line in lines]
    if not tokens or any(not row for row in tokens):
        raise ValueError("TXT không chứa đủ câu hát hợp lệ.")
    if sum(map(len, tokens)) > 20000:
        raise ValueError("TXT quá dài, tối đa 20.000 từ.")
    if any(len(w) > 300 for row in tokens for w in row):
        raise ValueError("TXT có từ dài quá 300 ký tự.")
    return tokens


def _flatten(segments: list[dict]) -> list[dict]:
    return [w for segment in segments for w in segment["words"]]


def _fit_on_speech(old_words: list[dict], new_words: list[str]) -> list[dict]:
    """Project character-weighted word boundaries onto real voiced intervals.

    Silent gaps between existing words remain unassigned to any new word. This
    retains the start/end of the original song's timed span and rough pauses.
    """
    if not old_words or not new_words:
        raise ValueError("Không có từ hoặc mốc âm thanh để ghép TXT.")
    lengths = [float(w["end"]) - float(w["start"]) for w in old_words]
    if any(not isfinite(x) or x <= 0 for x in lengths):
        raise ValueError("Mốc thời gian cũ không hợp lệ. Hãy lưu lại lời trước.")
    active = sum(lengths)
    weights = [max(1, len(word)) for word in new_words]
    total_weight = sum(weights)

    def locate(position: float, start_boundary: bool) -> float:
        wanted = active * position / total_weight
        cursor = 0.0
        for i, (word, duration) in enumerate(zip(old_words, lengths)):
            upper = cursor + duration
            if wanted < upper - 1e-9:
                return float(word["start"]) + max(0.0, wanted - cursor)
            if abs(wanted - upper) <= 1e-9:
                # At an exact old-word boundary preserve gaps rather than
                # extending one word through the silence.
                if start_boundary and i + 1 < len(old_words):
                    return float(old_words[i + 1]["start"])
                return float(word["end"])
            cursor = upper
        return float(old_words[-1]["end"])

    words: list[dict] = []
    weighted = 0
    for word, weight in zip(new_words, weights):
        start = locate(weighted, start_boundary=True)
        weighted += weight
        end = locate(weighted, start_boundary=False)
        start, end = round(start, 3), round(end, 3)
        if end <= start:
            raise ValueError(
                "Quá nhiều từ TXT so với thời lượng hát. "
                "Không thể ước lượng an toàn; cần căn lại bằng AI hoặc sửa thủ công."
            )
        words.append({"text": word, "start": start, "end": end})
    return words


def _as_segments(words_by_line: list[list[dict]]) -> list[dict]:
    out: list[dict] = []
    for line in words_by_line:
        for start in range(0, len(line), 100):
            group = line[start:start + 100]
            if group:
                out.append({
                    "start": group[0]["start"], "end": group[-1]["end"],
                    "words": group,
                })
    return out


def apply_reference_to_existing(
    segments: list[dict], lines: list[str], *, estimate: bool = False,
) -> tuple[list[dict], bool]:
    """Return (new segments, was_estimated) without mutating input.

    In exact mode, preserve every start/end and segment boundary.
    In explicit estimate mode, preserve reliable phrase times if line counts
    match; otherwise remap over all voiced word intervals globally.
    """
    reference = _safe_words(lines)
    old = deepcopy(segments)
    if not old or not _flatten(old):
        raise ValueError("Dự án chưa có mốc thời gian. Hãy nhận diện/căn lời trước.")

    exact = len(old) == len(reference) and all(
        len(segment["words"]) == len(tokens) for segment, tokens in zip(old, reference)
    )
    if exact:
        for segment, tokens in zip(old, reference):
            for word, text in zip(segment["words"], tokens):
                word["text"] = text
        return old, False

    if not estimate:
        old_count = sum(len(s["words"]) for s in old)
        new_count = sum(map(len, reference))
        raise ValueError(
            f"TXT có {len(reference)} câu / {new_count} từ; phụ đề hiện có "
            f"{len(old)} câu / {old_count} từ. Không thể giữ nguyên từng mốc khi "
            "số câu hoặc từ khác nhau. Chọn tùy chọn ƯỚC LƯỢNG nếu muốn "
            "ghép lời TXT ngay, hoặc dùng Căn lời theo giọng hát để có mốc chính xác."
        )

    if len(old) == len(reference):
        # Prefer phrase-level original timing: old sentence start/end unchanged.
        remapped = [
            _fit_on_speech(segment["words"], tokens)
            for segment, tokens in zip(old, reference)
        ]
    else:
        # ASR sometimes splits lines differently from the TXT lyric sheet.
        # Map all text across the existing voiced intervals in sequence.
        flat = _fit_on_speech(_flatten(old), [w for line in reference for w in line])
        remapped = []
        cursor = 0
        for tokens in reference:
            remapped.append(flat[cursor:cursor + len(tokens)])
            cursor += len(tokens)
    return _as_segments(remapped), True
