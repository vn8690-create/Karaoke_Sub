"""Reference lyrics cleaning/alignment regressions; no model downloads in CI."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from local_studio import alignment


def result(*words):
    return {"segments": [{"words": [{"word": text, "start": start, "end": end, "probability": 0.9}
                                      for text, start, end in words]}]}


class ReferenceCleaningTests(unittest.TestCase):
    def test_markdown_directions_removed_but_repeated_chorus_retained(self):
        source = "\ufeff[Intro]\\\r\n[Rain sounds, guitar]\\\r\n[Verse 1]\\\r\nRót thêm một chén...\\\r\n[Chorus]\\\r\nNgười ơi!\\\r\n[Chorus]\\\r\nNgười ơi!\\\r\n[End]\\"
        clean = alignment.clean_lyrics(source)
        self.assertEqual(clean["lines"], ["Rót thêm một chén...", "Người ơi!", "Người ơi!"])
        self.assertEqual(clean["ignored_lines"], 6)
        self.assertEqual(clean["text"], "Rót thêm một chén...\nNgười ơi!\nNgười ơi!")

    def test_inline_directions_spaces_and_blank_lines(self):
        clean = alignment.clean_lyrics("  Xin\t  chào [whisper] người ơi...\n\n[Beat stops]\nHết thật rồi!  ")
        self.assertEqual(clean["lines"], ["Xin chào người ơi...", "Hết thật rồi!"])
        self.assertEqual(clean["ignored_lines"], 1)

    def test_nested_stage_directions_do_not_leak_into_sung_words(self):
        clean = alignment.clean_lyrics("[Intro [soft rain]]\nNgười [low [whisper]] ơi")
        self.assertEqual(clean["lines"], ["Người ơi"])
        self.assertEqual(clean["ignored_lines"], 1)

    def test_empty_directions_only_and_oversized_text_rejected(self):
        for text in ("", " [Verse 1]\n[Rain] ", "." * 100001):
            with self.subTest(text=text[:20]), self.assertRaises(ValueError):
                alignment.clean_lyrics(text)


class RestoringAlignmentTests(unittest.TestCase):
    def test_restore_exact_reference_line_spelling_with_punctuation_token_split(self):
        clean = alignment.clean_lyrics("Xin chào...\nNGƯỜI ơi!")
        aligned = result((" Xin", .5, .8), (" chào", .9, 1.2), ("...", 1.2, 1.2),
                         (" NGƯỜI", 3, 3.4), (" ơi!", 3.4, 4))
        segments, warnings = alignment._restore_reference(clean, aligned, 5)
        self.assertEqual([[w["text"] for w in s["words"]] for s in segments], [["Xin", "chào..."], ["NGƯỜI", "ơi!"]])
        self.assertEqual(segments[1]["start"], 3)
        self.assertEqual(segments[0]["words"][-1]["end"], 1.2)
        self.assertEqual(warnings, [])

    def test_equivalent_unicode_encoding_retains_original_spelling(self):
        clean = alignment.clean_lyrics("cha\u0300o")
        segments, _ = alignment._restore_reference(clean, result((" chào", .2, .8)), 1)
        self.assertEqual(segments[0]["words"][0]["text"], "cha\u0300o")

    def test_standalone_punctuation_kept_without_fake_sound_interval(self):
        clean = alignment.clean_lyrics("Người ... ơi !")
        segments, _ = alignment._restore_reference(clean, result((" Người...", 1, 2), (" ơi!", 3, 4)), 5)
        self.assertEqual([w["text"] for w in segments[0]["words"]], ["Người ...", "ơi !"])
        self.assertEqual(segments[0]["words"][1]["start"], 3)

    def test_zero_duration_and_missing_words_rejected_not_filled_uniformly(self):
        for raw in (result((" Xin", 0, .5), (" chào", 1, 1)), result((" Xin", 0, .5))):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                alignment._restore_reference(alignment.clean_lyrics("Xin chào"), raw, 2)

    def test_merged_lexical_words_without_separate_alignment_rejected(self):
        with self.assertRaises(ValueError):
            alignment._restore_reference(alignment.clean_lyrics("Xin chào"), result((" Xin chào", .2, 1)), 2)

    def test_nonfinite_and_outside_audio_times_rejected(self):
        for start, end in ((float("nan"), 1), (.1, float("inf")), (-2, 1), (.5, 3)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                alignment._restore_reference(alignment.clean_lyrics("Xin"), result((" Xin", start, end)), 2)

    def test_low_confidence_warning_and_long_line_api_limit(self):
        words = [(" từ", i * .1, (i + 1) * .1) for i in range(101)]
        raw = result(*words)
        raw["segments"][0]["words"][0]["probability"] = .02
        segments, warnings = alignment._restore_reference(alignment.clean_lyrics(" ".join(["từ"] * 101)), raw, 12)
        self.assertEqual([len(s["words"]) for s in segments], [100, 1])
        self.assertIn("1 từ", warnings[0])


class ForcedAlignmentAdapterTests(unittest.TestCase):
    def test_actual_reference_is_passed_to_forced_aligner_and_old_model_cache_reused(self):
        raw = result((" Xin", .5, .8), (" chào!", .9, 1.2))
        network = SimpleNamespace(align=lambda *args, **kwargs: SimpleNamespace(to_dict=lambda: raw))
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "whisper" / "whisper"
            cache.mkdir(parents=True)
            checkpoint = cache / "small.pt"
            checkpoint.write_bytes(b"existing checkpoint")
            fake = SimpleNamespace(load_model=lambda *args, **kwargs: network)
            with patch.dict("sys.modules", {"stable_whisper": fake}), \
                    patch.object(alignment, "_device", return_value="cpu"), \
                    patch.object(alignment, "_model_dir", return_value=Path(temp)), \
                    patch.object(alignment, "_free_cuda") as free, \
                    patch.object(alignment, "probe", return_value={"duration": 2}), \
                    patch.object(network, "align", wraps=network.align) as align, \
                    patch.object(fake, "load_model", wraps=fake.load_model) as load:
                output = alignment.align_lyrics(Path(temp) / "vocal.wav", "[Verse 1]\nXin chào!", device="cpu")
            self.assertEqual(load.call_args.args[0], str(checkpoint))
            self.assertEqual(align.call_args.args[1], "Xin chào!")
            self.assertTrue(align.call_args.kwargs["original_split"])
            self.assertFalse(align.call_args.kwargs["remove_instant_words"])
            self.assertEqual(output["engine"], "stable-ts")
            self.assertEqual(output["ignored_lines"], 1)
            self.assertEqual(output["text"], "Xin chào!")
            self.assertEqual(output["segments"][0]["start"], .5)
            free.assert_called_once()


    def test_auto_language_uses_detected_language_and_reports_choice(self):
        raw = result((" Xin", .2, .5), (" chào!", .5, 1))
        network = SimpleNamespace(align=lambda *args, **kwargs: SimpleNamespace(to_dict=lambda: raw))
        fake = SimpleNamespace(load_model=lambda *args, **kwargs: network)
        with tempfile.TemporaryDirectory() as temp, \
                patch.dict("sys.modules", {"stable_whisper": fake}), \
                patch.object(alignment, "_device", return_value="cpu"), \
                patch.object(alignment, "_model_dir", return_value=Path(temp)), \
                patch.object(alignment, "_free_cuda"), \
                patch.object(alignment, "probe", return_value={"duration": 2}), \
                patch.object(alignment, "_detect_language", return_value=("vi", .8)), \
                patch.object(network, "align", wraps=network.align) as align:
            output = alignment.align_lyrics(Path(temp) / "vocal.wav", "Xin chào!", language="auto")
        self.assertEqual(align.call_args.kwargs["language"], "vi")
        self.assertEqual(output["language"], "vi")
        self.assertIn("Ngôn ngữ tự nhận diện: vi", output["warnings"][0])

    def test_gpu_oom_is_actionable_and_memory_cleanup_runs(self):
        def fail(*args, **kwargs):
            raise RuntimeError("CUDA out of memory")
        network = SimpleNamespace(align=fail)
        fake = SimpleNamespace(load_model=lambda *args, **kwargs: network)
        with tempfile.TemporaryDirectory() as temp, \
                patch.dict("sys.modules", {"stable_whisper": fake}), \
                patch.object(alignment, "_device", return_value="cuda"), \
                patch.object(alignment, "_model_dir", return_value=Path(temp)), \
                patch.object(alignment, "_free_cuda") as free, \
                patch.object(alignment, "probe", return_value={"duration": 2}):
            with self.assertRaisesRegex(RuntimeError, "GPU hết VRAM"):
                alignment.align_lyrics(Path(temp) / "vocal.wav", "Xin chào!")
        free.assert_called_once()


if __name__ == "__main__":
    unittest.main()
