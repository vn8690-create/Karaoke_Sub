"""Conservative TXT corrections against existing Karaoke word timings.

No AI/GPU. Exact time stamps survive word substitutions. Missing tokens may
be interpolated only in the corresponding local time region and require user
review; unrelated intro ASR hallucinations are never silently removed.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from difflib import SequenceMatcher
from hashlib import sha256
import json
import unicodedata

from .reference_timing import _fit_on_speech, _safe_words

MAX_SYNC_LINES = 240


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn" and ch.isalnum())


def _similarity(old: list[str], new: list[str]) -> float:
    a, b = [_norm(x) for x in old], [_norm(x) for x in new]
    a, b = [x for x in a if x], [x for x in b if x]
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    char_ratio = SequenceMatcher(None, " ".join(a), " ".join(b), autojunk=False).ratio()
    overlap = sum((Counter(a) & Counter(b)).values())
    return 0.7 * char_ratio + 0.3 * (2 * overlap / (len(a) + len(b)))


def revision_for(segments: list[dict], reference_text: str) -> str:
    payload = json.dumps([segments, reference_text], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def segments_revision(segments: list[dict]) -> str:
    return revision_for(segments, "")


def _align_lines(old_tokens: list[list[str]], new_tokens: list[list[str]]) -> dict[int, int]:
    n, m = len(old_tokens), len(new_tokens)
    similarity = [[_similarity(a, b) for b in new_tokens] for a in old_tokens]
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    moves = [[""] * (m + 1) for _ in range(n + 1)]
    for i in range(n, -1, -1):
        for j in range(m, -1, -1):
            if i == n and j == m:
                continue
            options = []
            if i < n:
                options.append((dp[i + 1][j] - 0.23, "skip_old"))
            if j < m:
                options.append((dp[i][j + 1] - 0.23, "skip_new"))
            if i < n and j < m and similarity[i][j] >= 0.61:
                options.append((dp[i + 1][j + 1] + similarity[i][j] - 0.46, "match"))
            score, move = max(options, key=lambda x: (x[0], x[1] == "match"))
            dp[i][j], moves[i][j] = score, move
    matched, i, j = {}, 0, 0
    while i < n or j < m:
        move = moves[i][j]
        if move == "match":
            matched[i] = j
            i, j = i + 1, j + 1
        elif move == "skip_old":
            i += 1
        elif move == "skip_new":
            j += 1
        else:
            raise AssertionError("Invalid lyric alignment state")
    return matched


def _remap_line(old_words: list[dict], target: list[str]) -> tuple[list[dict], int]:
    """Preserve known-word timing and estimate unmatched islands only."""
    if len(old_words) == len(target):
        return [{**w, "text": token} for w, token in zip(old_words, target)], 0
    old_tokens = [_norm(w["text"]) for w in old_words]
    new_tokens = [_norm(token) for token in target]
    diff = SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    anchors = [(match.a + k, match.b + k)
               for match in diff.get_matching_blocks() for k in range(match.size)]

    def must_borrow(left: tuple[int, int], right: tuple[int, int]) -> bool:
        previous_words = right[0] - left[0] - 1
        new_words = right[1] - left[1] - 1
        if previous_words or not new_words:
            return False
        if left[0] < 0 or right[0] == len(old_words):
            return True
        gap = old_words[right[0]]["start"] - old_words[left[0]]["end"]
        return gap < new_words * 0.065

    # For an inserted word with no silent gap, borrow the closest anchor's
    # voiced interval. This retimes only that tiny local island, never the song.
    while anchors:
        chain = [(-1, -1), *anchors, (len(old_words), len(target))]
        gap = next(((a, b) for a, b in zip(chain, chain[1:]) if must_borrow(a, b)), None)
        if not gap:
            break
        left, right = gap
        if left[0] >= 0:
            anchors.remove(left)
        elif right[0] < len(old_words):
            anchors.remove(right)
        else:
            break

    words, estimated = [], 0
    previous = (-1, -1)
    for nxt in [*anchors, (len(old_words), len(target))]:
        source = old_words[previous[0] + 1:nxt[0]]
        wanted = target[previous[1] + 1:nxt[1]]
        if wanted:
            if source:
                patch = _fit_on_speech(source, wanted)
            else:
                if previous[0] < 0 or nxt[0] >= len(old_words):
                    raise ValueError("Không có mốc để chèn từ ở đầu/cuối câu.")
                left = old_words[previous[0]]["end"]
                right = old_words[nxt[0]]["start"]
                interval = (right - left) / len(wanted)
                if interval < 0.065:
                    raise ValueError("Khoảng thời gian giữa các từ quá ngắn để chèn.")
                patch = [{"text": token, "start": round(left + k * interval, 3),
                          "end": round(left + (k + 1) * interval, 3)}
                         for k, token in enumerate(wanted)]
            words.extend(patch)
            estimated += len(patch)
        if nxt[0] < len(old_words):
            words.append({**old_words[nxt[0]], "text": target[nxt[1]]})
        previous = nxt
    if len(words) != len(target):
        raise ValueError("Không ghép đủ từ từ TXT.")
    for i, word in enumerate(words):
        if word["end"] <= word["start"] or (i and word["start"] < words[i - 1]["end"] - 0.001):
            raise ValueError("Thời gian thiếu hoặc chồng nhau. Câu này cần sửa tay.")
    return words, estimated


def build_preview(segments: list[dict], reference_lines: list[str], reference_text: str) -> dict:
    if not segments:
        raise ValueError("Chưa có mốc thời gian. Hãy căn hoặc chỉnh lời trước.")
    if len(segments) > MAX_SYNC_LINES or len(reference_lines) > MAX_SYNC_LINES:
        raise ValueError("Smart Sync hỗ trợ tối đa 240 câu mỗi lần.")
    reference = _safe_words(reference_lines)
    old_lines = [[word["text"] for word in seg["words"]] for seg in segments]
    matched = _align_lines(old_lines, reference)
    used = set(matched.values())
    rows, candidates = [], {}
    for i, (seg, old) in enumerate(zip(segments, old_lines)):
        base = {"id": f"line-{i}", "old_index": i, "start": seg["start"], "end": seg["end"],
                "old_text": " ".join(old), "old_count": len(old)}
        if i not in matched:
            rows.append({**base, "reference_index": None, "new_text": "", "new_count": 0,
                         "status": "blocked", "score": 0,
                         "reason": "Không tìm thấy câu tương ứng trong TXT. Có thể là nhạc dạo hoặc lời AI bịa. Không tự xóa."})
            continue
        j = matched[i]
        similarity = _similarity(old, reference[j])
        target = " ".join(reference[j])
        row = {**base, "reference_index": j, "new_text": target,
               "new_count": len(reference[j]), "score": round(similarity * 100)}
        if old == reference[j]:
            rows.append({**row, "status": "same", "reason": "Lời đã đúng, không cần sửa."})
            continue
        try:
            mapped, estimated = _remap_line(seg["words"], reference[j])
            proposed = {"start": mapped[0]["start"], "end": mapped[-1]["end"], "words": mapped}
        except ValueError as exc:
            rows.append({**row, "status": "blocked", "reason": str(exc)})
            continue
        # Same-count text corrections preserve every original word timestamp.
        status = "safe" if similarity >= 0.83 and not estimated else "review"
        reason = ("Giữ nguyên toàn bộ mốc từng từ; chỉ sửa chữ." if not estimated else
                  f"Giữ các từ khớp, ước lượng cục bộ {estimated} từ. Nghe lại sau khi áp dụng.")
        candidates[row["id"]] = proposed
        rows.append({**row, "status": status, "estimated_words": estimated, "reason": reason})
    for j, tokens in enumerate(reference):
        if j not in used:
            rows.append({"id": f"missing-{j}", "old_index": None, "reference_index": j,
                         "old_text": "", "new_text": " ".join(tokens), "new_count": len(tokens),
                         "status": "blocked", "score": 0,
                         "reason": "TXT có câu nhưng chưa có mốc hát tương ứng. Cần thêm câu/căn thủ công."})
    counts = {kind: sum(row["status"] == kind for row in rows)
              for kind in ("safe", "review", "blocked", "same")}
    return {"revision": revision_for(segments, reference_text),
            "items": rows, "counts": counts, "candidates": candidates}


def apply_selection(segments: list[dict], preview: dict, selected: list[str]) -> list[dict]:
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("Hãy chọn ít nhất một câu, không chọn trùng.")
    candidates = preview["candidates"]
    if any(item not in candidates for item in selected):
        raise ValueError("Có câu chưa được phép tự sửa. Hãy kiểm tra những dòng màu đỏ.")
    result = deepcopy(segments)
    for item_id in selected:
        index = int(item_id.split("-")[1])
        result[index] = deepcopy(candidates[item_id])
    return result
