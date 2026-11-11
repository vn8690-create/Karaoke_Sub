"""Smart Lyrics Sync: realistic ASR hallucinations, word anchors, and undo safety.

All tests use existing timestamps. No AI model, CUDA, or network required.
"""
from copy import deepcopy
import unittest

from local_studio.smart_sync import (
    _remap_line, apply_selection, build_preview, revision_for,
)


def line(text: str, start: float, step: float = 0.27) -> dict:
    words = [
        {"text": token, "start": round(start + i * step, 3),
         "end": round(start + (i + 1) * step, 3)}
        for i, token in enumerate(text.split())
    ]
    return {"start": words[0]["start"], "end": words[-1]["end"], "words": words}


class SmartSyncTests(unittest.TestCase):
    def test_repeated_intro_hallucinations_stay_red_not_silently_deleted(self):
        original = [
            line("Vì vậy hãy đoán cho chúng ta một lần nữa", 0),
            line("Vì vậy hãy đoán cho chúng ta một lần nữa", 5),
            line("Vì vậy hãy đoán cho chúng ta một lần nữa", 11),
            line("Vì vậy hãy đoán cho chúng ta một lần nữa", 19),
            line("Em là người tôi yêu", 28),
            line("Đừng bỏ anh đi nhé", 36),
        ]
        before = deepcopy(original)
        reference = ["Em là người anh yêu", "Đừng vội bỏ anh đi nhé"]
        result = build_preview(original, reference, "\n".join(reference))
        rows = result["items"]
        self.assertEqual([row["status"] for row in rows[:4]], ["blocked"] * 4)
        self.assertEqual([row["reference_index"] for row in rows[4:]], [0, 1])
        self.assertEqual(rows[4]["status"], "review")
        self.assertEqual(rows[4]["estimated_words"], 0)
        self.assertEqual(rows[5]["status"], "review")
        self.assertGreater(rows[5]["estimated_words"], 0)
        self.assertEqual(before, original)
        selected = apply_selection(original, result, ["line-4", "line-5"])
        self.assertEqual(selected[:4], before[:4])
        self.assertEqual(selected[4]["words"][3]["text"], "anh")
        self.assertEqual(
            [(w["start"], w["end"]) for w in selected[4]["words"]],
            [(w["start"], w["end"]) for w in before[4]["words"]]
        )
        self.assertEqual([w["text"] for w in selected[5]["words"]],
                         ["Đừng", "vội", "bỏ", "anh", "đi", "nhé"])
        self.assertEqual(selected[5]["start"], before[5]["start"])
        self.assertEqual(selected[5]["end"], before[5]["end"])

    def test_high_similarity_spelling_and_diacritics_is_green(self):
        old = [line("Hẹn gặp ngày mai", 5.2)]
        new = ["Hẹn gặp ngày mai!"]
        proposal = build_preview(old, new, new[0])
        self.assertEqual(proposal["counts"]["safe"], 1)
        selected = apply_selection(old, proposal, ["line-0"])
        self.assertEqual(selected[0]["words"][-1]["text"], "mai!")
        self.assertEqual([(w["start"], w["end"]) for w in selected[0]["words"]],
                         [(w["start"], w["end"]) for w in old[0]["words"]])

    def test_missing_txt_line_unmatched_and_not_auto_timed(self):
        old = [line("Mùa xuân về trên phố", 4)]
        new = ["Mùa xuân về trên phố", "Trời xanh bình yên"]
        result = build_preview(old, new, "\n".join(new))
        self.assertEqual(result["counts"]["blocked"], 1)
        missing = next(item for item in result["items"] if item["id"].startswith("missing-"))
        self.assertIsNone(missing["old_index"])
        with self.assertRaisesRegex(ValueError, "chưa được phép"):
            apply_selection(old, result, [missing["id"]])

    def test_repeated_chorus_respects_order(self):
        old = [line("Anh nhớ em", 1), line("Hãy quay về", 4),
               line("Anh nhớ em", 10), line("Hãy quay về", 14)]
        reference = ["Anh nhớ em", "Hãy quay về", "Anh nhớ em", "Hãy quay về"]
        result = build_preview(old, reference, "\n".join(reference))
        self.assertEqual(result["counts"], {"safe": 0, "review": 0, "blocked": 0, "same": 4})

    def test_inserted_word_uses_local_interval_preserving_outside_anchors(self):
        original = line("Đừng bỏ anh đi nhé", 7)
        words, estimated = _remap_line(original["words"], ["Đừng", "vội", "bỏ", "anh", "đi", "nhé"])
        self.assertGreater(estimated, 0)
        self.assertEqual(words[-1]["end"], original["end"])
        self.assertEqual(words[2]["start"], original["words"][1]["start"])
        self.assertEqual(words[3]["start"], original["words"][2]["start"])
        self.assertEqual(words[4]["start"], original["words"][3]["start"])

    def test_preview_has_revision_and_rejects_duplicate_or_red_selection(self):
        old = [line("Mùa thu bay", 0), line("Xin chào!", 2)]
        reference = ["Xin chào!"]
        result = build_preview(old, reference, "Xin chào!")
        self.assertEqual(len(result["revision"]), 64)
        self.assertNotEqual(result["revision"], revision_for(old, "Xin chào khác!"))
        with self.assertRaises(ValueError):
            apply_selection(old, result, [])
        with self.assertRaises(ValueError):
            apply_selection(old, result, ["line-0", "line-0"])

    def test_preview_caps_expensive_matrix_and_never_mutates_original(self):
        old = [line("Xin chào bạn", i * 2) for i in range(241)]
        with self.assertRaisesRegex(ValueError, "240"):
            build_preview(old, ["Xin chào bạn"], "Xin chào bạn")
        reference = ["Xin chào bạn"]
        small = deepcopy(old[:2])
        build_preview(small, reference, reference[0])
        self.assertEqual(small, old[:2])


if __name__ == "__main__":
    unittest.main()
