"""Cancellable, progress-reporting FFmpeg subprocess for local video exports.

Safe subprocess argv, bounded stderr capture on disk, no process shell.
"""
from __future__ import annotations

import math
import subprocess
import tempfile
import threading
from pathlib import Path
from collections.abc import Callable


class RenderCancelled(RuntimeError):
    """An explicit cancellation, not an FFmpeg encode error."""


def parse_ffmpeg_time(text: str) -> float | None:
    """Parse FFmpeg -progress 'out_time=HH:MM:SS.microseconds' values."""
    try:
        hours, minutes, seconds = text.strip().split(":")
        values = (int(hours), int(minutes), float(seconds))
        if (values[0] < 0 or not 0 <= values[1] < 60
                or not 0 <= values[2] < 60 or not all(math.isfinite(float(v)) for v in values)):
            return None
        return values[0] * 3600 + values[1] * 60 + values[2]
    except (ValueError, OverflowError):
        return None


def render_with_progress(
    args: list[str], cwd: str | Path, duration: float,
    on_progress: Callable[[int], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> None:
    """Run FFmpeg; deliver clamped integer progress 0-99 and support cancellation.

    FFmpeg progress arrives over stdout. stderr is redirected to a local tempfile
    to avoid deadlocks on pipe saturation and to avoid unbounded RAM consumption.
    """
    if not args or Path(args[0]).name.lower() not in {"ffmpeg", "ffmpeg.exe"}:
        raise ValueError("Chỉ hỗ trợ tiến độ cho FFmpeg.")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Thời lượng video không hợp lệ.")
    if cancel_event is not None and cancel_event.is_set():
        raise RenderCancelled("Đã hủy tác vụ xuất video.")
    command = [args[0], "-progress", "pipe:1", "-nostats", *args[1:]]
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8", errors="replace") as errors:
        try:
            process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=errors,
                                       text=True, encoding="utf-8", errors="replace", bufsize=1)
        except FileNotFoundError as exc:
            raise RuntimeError("Không tìm thấy FFmpeg. Hãy chạy windows/setup.bat.") from exc
        done = threading.Event()
        watcher = None

        def cancel_watcher():
            while not done.wait(0.1):
                if cancel_event is not None and cancel_event.is_set():
                    if process.poll() is None:
                        try:
                            process.terminate()
                        except ProcessLookupError:
                            pass
                    return

        if cancel_event is not None:
            watcher = threading.Thread(target=cancel_watcher, daemon=True,
                                       name="karaoke-ffmpeg-cancel")
            watcher.start()
        last = -1
        try:
            assert process.stdout is not None
            for raw in process.stdout:
                if cancel_event is not None and cancel_event.is_set():
                    raise RenderCancelled("Đã hủy tác vụ xuất video.")
                if on_progress is None or not raw.startswith("out_time="):
                    continue
                current = parse_ffmpeg_time(raw.partition("=")[2])
                if current is None:
                    continue
                progress = min(99, max(0, int(100 * current / duration)))
                if progress > last:
                    on_progress(progress)
                    last = progress
            result = process.wait()
            if cancel_event is not None and cancel_event.is_set():
                raise RenderCancelled("Đã hủy tác vụ xuất video.")
            if result != 0:
                errors.flush()
                errors.seek(0)
                details = errors.read()[-6000:]
                raise RuntimeError(f"FFmpeg thất bại (mã {result}): {details}")
            if on_progress is not None and last < 99:
                on_progress(99)
        finally:
            done.set()
            if process.stdout is not None:
                process.stdout.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            if watcher is not None:
                watcher.join(timeout=1)
