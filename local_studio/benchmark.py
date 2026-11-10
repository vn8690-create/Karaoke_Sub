"""Local FFmpeg-only render benchmark for 7-10 minute karaoke projects.

No AI model, user media, credentials or cloud API required.

Examples:
    python -m local_studio.benchmark --seconds 15
    python -m local_studio.benchmark --minutes 8 --resolution 1080p --loop-background
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from .pipeline import probe, render_video
from .subtitles import write_subtitles


RESOLUTIONS = {"720p": (1280, 720), "1080p": (1920, 1080)}


def _ffmpeg(args: list[str]) -> None:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args],
        text=True, capture_output=True, encoding="utf-8", errors="replace",
        timeout=90,
    )
    if result.returncode:
        raise RuntimeError("Không tạo được dữ liệu benchmark: " + result.stderr[-2000:])


def benchmark(duration: float = 15.0, resolution: str = "720p",
              loop_background: bool = False, save_output: str | Path | None = None,
              quiet: bool = False) -> dict:
    """Measure the real render engine using generated sine wave and optional loop clip.

    The output is removed unless save_output is provided. Returns timing,
    output media details and throughput; this is not a GPU VRAM benchmark.
    """
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration):
        raise ValueError("Thời lượng benchmark phải là số hữu hạn.")
    if not 1 <= duration <= 1200:
        raise ValueError("Thời lượng benchmark phải từ 1 đến 1200 giây.")
    if resolution not in RESOLUTIONS:
        raise ValueError("Độ phân giải chỉ hỗ trợ 720p hoặc 1080p.")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("Thiếu FFmpeg/FFprobe trên PATH.")
    with tempfile.TemporaryDirectory(prefix="nvs-render-benchmark-") as tmp:
        folder = Path(tmp)
        audio = folder / "generated-tone.wav"
        _ffmpeg([
            "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=44100:duration={duration:.3f}",
            "-ac", "2", "-c:a", "pcm_s16le", str(audio),
        ])
        background = None
        if loop_background:
            background = folder / "test-pattern.mp4"
            _ffmpeg([
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=2",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", str(background),
            ])
        word_end = min(duration - 0.1, 1.2)
        if word_end <= 0.1:
            raise ValueError("Thời lượng benchmark quá ngắn.")
        write_subtitles([{
            "start": 0.1, "end": word_end,
            "words": [{"text": "NVS Karaoke Studio PRO", "start": 0.1, "end": word_end}],
        }], folder, resolution=RESOLUTIONS[resolution])
        output = folder / "karaoke-benchmark.mp4"
        last_reported = [-10]

        def on_progress(percent: int):
            group = percent // 10 * 10
            if not quiet and group >= last_reported[0] + 10:
                print(f"Render: {group}% (FFmpeg báo tiến độ)", flush=True)
                last_reported[0] = group

        started = time.perf_counter()
        render_video(
            audio, background, folder / "lyrics.ass", output,
            duration, resolution=RESOLUTIONS[resolution],
            on_progress=on_progress,
        )
        elapsed = time.perf_counter() - started
        media = probe(output)
        video = next(stream for stream in media["streams"] if stream.get("codec_type") == "video")
        audio_streams = [s for s in media["streams"] if s.get("codec_type") == "audio"]
        report = {
            "ok": True,
            "requested_seconds": round(duration, 3),
            "actual_seconds": round(media["duration"], 3),
            "elapsed_seconds": round(elapsed, 3),
            "relative_speed_x": round(duration / max(elapsed, 0.001), 2),
            "resolution": f"{video['width']}x{video['height']}",
            "has_audio": bool(audio_streams),
            "loop_background": loop_background,
            "output_mb": round(output.stat().st_size / (1024 * 1024), 2),
        }
        if save_output:
            destination = Path(save_output).expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.suffix.lower() != ".mp4":
                raise ValueError("File đích phải có đuôi .mp4.")
            shutil.copy2(output, destination)
            report["saved_to"] = str(destination)
        return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Đo hiệu năng xuất Karaoke MP4 của NVS Studio")
    duration = parser.add_mutually_exclusive_group()
    duration.add_argument("--seconds", type=float, help="Thời lượng thử theo giây (mặc định: 15)")
    duration.add_argument("--minutes", type=float, help="Thời lượng thử theo phút, ví dụ: --minutes 8")
    parser.add_argument("--resolution", choices=tuple(RESOLUTIONS), default="720p")
    parser.add_argument("--loop-background", action="store_true",
                        help="Tạo clip nền 2 giây và lặp đến hết bài")
    parser.add_argument("--save", metavar="PATH", help="Tùy chọn lưu MP4 thử nghiệm")
    args = parser.parse_args(argv)
    seconds = args.minutes * 60 if args.minutes is not None else (
        args.seconds if args.seconds is not None else 15.0
    )
    try:
        print("Đang kiểm thử engine FFmpeg; không tải model AI hoặc dùng nhạc người dùng.")
        report = benchmark(seconds, args.resolution, args.loop_background, args.save)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
