"""Cached Whisper .pt repair regressions, no model downloads or PyTorch dependency."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from local_studio.model_cache import (
    cached_whisper_checkpoints,
    is_corrupt_checkpoint,
    load_whisper_with_repair,
)


BROKEN_ARCHIVE = RuntimeError(
    "PytorchStreamReader failed reading zip archive: failed finding central directory"
)


class CachedWhisperRepairTests(unittest.TestCase):
    def test_recognizes_specific_archive_corruption_only(self):
        self.assertTrue(is_corrupt_checkpoint(BROKEN_ARCHIVE))
        self.assertTrue(is_corrupt_checkpoint(RuntimeError("failed reading zip archive")))
        self.assertFalse(is_corrupt_checkpoint(RuntimeError("CUDA out of memory")))
        self.assertFalse(is_corrupt_checkpoint(RuntimeError("No module named whisper")))
        self.assertFalse(is_corrupt_checkpoint(RuntimeError("invalid lyrics alignment")))

    def test_cached_nested_checkpoint_is_repaired_and_downloaded_once(self):
        with TemporaryDirectory() as directory:
            cache = Path(directory) / "whisper"
            normal, nested = cached_whisper_checkpoints(cache, "small")
            nested.parent.mkdir(parents=True)
            nested.write_bytes(b"damaged partial model")
            messages = []
            calls = []

            def loader(model, **kw):
                calls.append((model, kw))
                if len(calls) == 1:
                    raise BROKEN_ARCHIVE
                return "OK"

            loaded = load_whisper_with_repair(loader, "small", "cpu", cache, messages.append)
            self.assertEqual(loaded, "OK")
            self.assertFalse(nested.exists())
            self.assertEqual(calls[0][0], str(nested))
            self.assertEqual(calls[1][0], "small")
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[1][1]["download_root"], str(cache.resolve()))
            self.assertIn("đang tải lại", messages[0])
            self.assertFalse(normal.exists())

    def test_failed_first_download_is_retried_after_detected_partial_cache(self):
        with TemporaryDirectory() as directory:
            cache = Path(directory) / "whisper"
            cache.mkdir(parents=True)
            checkpoint = cache / "base.pt"
            calls = []

            def loader(model, **kw):
                calls.append(model)
                if len(calls) == 1:
                    checkpoint.write_bytes(b"partial download")
                    raise BROKEN_ARCHIVE
                self.assertFalse(checkpoint.exists())
                return "OK"

            self.assertEqual(load_whisper_with_repair(loader, "base", "cpu", cache, lambda _: None), "OK")
            self.assertEqual(calls, ["base", "base"])

    def test_gpu_oom_never_deletes_checkpoint_and_does_not_retry(self):
        with TemporaryDirectory() as directory:
            cache = Path(directory)
            checkpoint = cache / "small.pt"
            checkpoint.write_bytes(b"keep this file")
            loader = Mock(side_effect=RuntimeError("CUDA out of memory"))
            with self.assertRaisesRegex(RuntimeError, "out of memory"):
                load_whisper_with_repair(loader, "small", "cuda", cache, lambda _: None)
            self.assertTrue(checkpoint.exists())
            loader.assert_called_once()

    def test_corrupt_cache_with_failed_retry_has_actionable_error(self):
        with TemporaryDirectory() as directory:
            cache = Path(directory)
            (cache / "tiny.pt").write_bytes(b"damaged")
            loader = Mock(side_effect=[BROKEN_ARCHIVE, OSError("internet unavailable")])
            with self.assertRaisesRegex(RuntimeError, "Tải lại checkpoint Whisper thất bại"):
                load_whisper_with_repair(loader, "tiny", "cpu", cache, lambda _: None)
            self.assertEqual(loader.call_count, 2)

    def test_no_unrelated_files_or_invalid_model_names_touched(self):
        with TemporaryDirectory() as directory:
            cache = Path(directory) / "whisper"
            cache.mkdir()
            unrelated = cache / "large-v3.pt"
            unrelated.write_bytes(b"keep")
            loader = Mock(side_effect=BROKEN_ARCHIVE)
            with self.assertRaisesRegex(RuntimeError, "không tìm thấy checkpoint"):
                load_whisper_with_repair(loader, "small", "cpu", cache, lambda _: None)
            self.assertEqual(unrelated.read_bytes(), b"keep")
            with self.assertRaises(ValueError):
                cached_whisper_checkpoints(cache, "../other")



class DemucsArchiveDiagnosticsTests(unittest.TestCase):
    def test_demucs_corrupt_checkpoint_explains_cache_location_without_deleting(self):
        from local_studio import pipeline
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            checkpoints = folder / "models" / "torch" / "hub" / "checkpoints"
            checkpoints.mkdir(parents=True)
            old_model = checkpoints / "cached-demucs.th"
            old_model.write_bytes(b"damaged")
            with patch.object(pipeline, "_device", return_value="cpu"), \
                 patch.object(pipeline, "_model_dir", return_value=folder / "models"), \
                 patch.object(pipeline, "_run", side_effect=BROKEN_ARCHIVE):
                with self.assertRaisesRegex(RuntimeError, "Checkpoint model tách giọng Demucs bị hỏng"):
                    pipeline.separate_audio(folder / "song.wav", folder / "stems")
            self.assertEqual(old_model.read_bytes(), b"damaged")


if __name__ == "__main__":
    unittest.main()
