"""Safe recovery for a broken *cached* Whisper model download.

This module only touches an explicitly selected Whisper checkpoint in the
project's cache; never user audio, lyrics, projects, or arbitrary .pt files.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


def is_corrupt_checkpoint(exc: BaseException) -> bool:
    """Recognize PyTorch's truncated/unreadable checkpoint archive errors."""
    message = str(exc).lower()
    return (
        ("pytorchstreamreader" in message and ("zip archive" in message or "central directory" in message))
        or "failed finding central directory" in message
        or "failed reading zip archive" in message
        or "unexpected eof" in message and ("pickle" in message or "zip" in message)
    )


def cached_whisper_checkpoints(cache: Path, model: str) -> tuple[Path, Path]:
    if model not in {"tiny", "base", "small", "medium", "large-v3"}:
        raise ValueError("Unknown Whisper checkpoint name")
    return cache / (model + ".pt"), cache / "whisper" / (model + ".pt")


def load_whisper_with_repair(
    loader: Callable,
    model: str,
    device: str,
    cache: Path,
    progress: Callable[[str], None],
):
    """Load from existing cache and retry exactly once if that cached .pt is corrupt.

    The checkpoint is downloaded by the original Whisper loader, which applies
    its built-in SHA256 verification. Only the selected model's known cache file
    is deleted after detecting the archive corruption.
    """
    cache = cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    candidates = cached_whisper_checkpoints(cache, model)
    selected = next((p for p in candidates if p.is_file() and not p.is_symlink()), None)
    source = str(selected) if selected else model
    try:
        return loader(source, device=device, download_root=str(cache))
    except (RuntimeError, OSError, EOFError, ValueError) as exc:
        if not is_corrupt_checkpoint(exc):
            raise
        # A loader invoked by model name may have just created a broken download.
        damaged = selected if selected and selected.is_file() else next(
            (p for p in candidates if p.is_file() and not p.is_symlink()), None
        )
        if damaged is None:
            raise RuntimeError(
                "Model Whisper không đọc được, nhưng không tìm thấy checkpoint trong cache. "
                "Kiểm tra lỗi tải model, ổ đĩa và file .pt trong thư mục models/whisper."
            ) from exc
        if damaged.resolve().parent not in {cache, cache / "whisper"}:
            raise RuntimeError("Không thể sửa cache model: đường dẫn checkpoint không hợp lệ.") from exc
        try:
            damaged.unlink()
        except OSError as os_error:
            raise RuntimeError(
                "Checkpoint Whisper hỏng nhưng không xóa được file cache: "
                + str(damaged) + ". Đóng ứng dụng rồi kiểm tra quyền ghi."
            ) from os_error
        progress("Phát hiện checkpoint Whisper bị hỏng: " + str(damaged)
                 + ". Đã xóa riêng file model lỗi; đang tải lại một lần.")
        try:
            return loader(model, device=device, download_root=str(cache))
        except Exception as retry_error:
            raise RuntimeError(
                "Tải lại checkpoint Whisper thất bại. Kiểm tra kết nối mạng, dung lượng ổ đĩa "
                "và thư mục: " + str(cache)
            ) from retry_error
