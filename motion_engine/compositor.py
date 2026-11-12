"""Optional intro/outro composition while preserving original FFmpeg karaoke render.

The main song is rendered by the existing pipeline first. This module then
crossfades pre-rendered HyperFrames clips around that MP4. Audio starts at the
song's first visible frame; original lyric timestamps are never modified.
"""
from __future__ import annotations
import math
from pathlib import Path
import tempfile

from .core import DURATION, TRANSITION_DURATION, PRESETS, TRANSITIONS, render_clip


def compose_argv(song: Path, intro: Path | None, outro: Path | None, output: Path,
                 song_duration: float, resolution: tuple[int, int], has_audio: bool,
                 transition: str) -> tuple[list[str], float]:
    """Return safe FFmpeg argv and final duration without shell interpolation."""
    if transition not in TRANSITIONS:
        raise ValueError("Kiểu chuyển cảnh không hợp lệ.")
    if not (intro or outro):
        raise ValueError("Không có intro hoặc outro được chọn.")
    if not math.isfinite(song_duration) or song_duration <= 0:
        raise ValueError("Thời lượng bài hát không hợp lệ.")
    if resolution not in {(1280, 720), (1920, 1080)}:
        raise ValueError("Chỉ hỗ trợ 720p và 1080p.")
    w, h = resolution
    inputs = [p for p in (intro, song, outro) if p is not None]
    song_i = 1 if intro else 0
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    for value in inputs:
        args += ["-i", str(Path(value).resolve())]
    filters = []
    for i in range(len(inputs)):
        filters.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},fps=30,setsar=1,format=yuv420p,"
            f"settb=AVTB,setpts=PTS-STARTPTS[v{i}]"
        )
    offset = 0.0
    head = f"v{song_i}"
    if intro:
        offset = DURATION - TRANSITION_DURATION
        filters.append(
            f"[v0][v{song_i}]xfade=transition={transition}:duration={TRANSITION_DURATION}:"
            f"offset={offset:.3f}[head]"
        )
        head = "head"
    if outro:
        outro_i = len(inputs) - 1
        out_at = (DURATION - TRANSITION_DURATION if intro else 0) + song_duration - TRANSITION_DURATION
        filters.append(
            f"[{head}][v{outro_i}]xfade=transition={transition}:duration={TRANSITION_DURATION}:"
            f"offset={out_at:.3f}[final]"
        )
        head = "final"
    total = song_duration + (DURATION - TRANSITION_DURATION if intro else 0) + (
        DURATION - TRANSITION_DURATION if outro else 0)
    args += ["-filter_complex", ";".join(filters), "-map", f"[{head}]"]
    if has_audio:
        delay = int(round(offset * 1000))
        args += ["-map", f"{song_i}:a:0", "-af", f"adelay={delay}:all=1,apad",
                 "-c:a", "aac", "-b:a", "192k"]
    else:
        args += ["-an"]
    args += ["-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "fast", "-crf", "22",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(Path(output).resolve())]
    return args, total


def add_motion(song: Path, output: Path, *, project_title: str, subtitle: str,
               intro: str, outro: str, transition: str, song_duration: float,
               resolution: tuple[int, int], has_audio: bool,
               on_progress=None, cancel_event=None) -> float:
    """Add intro and/or outro to the original MP4, using temp assets safely."""
    if intro != "none" and intro not in PRESETS:
        raise ValueError("Mẫu intro không hợp lệ.")
    if outro != "none" and outro not in PRESETS:
        raise ValueError("Mẫu outro không hợp lệ.")
    if intro == outro == "none":
        raise ValueError("Chưa chọn hiệu ứng intro/outro.")
    if transition not in TRANSITIONS:
        raise ValueError("Hiệu ứng chuyển cảnh không hợp lệ.")
    song = Path(song).resolve()
    output = Path(output).resolve()
    with tempfile.TemporaryDirectory(prefix="nvs-motion-", dir=output.parent) as scratch:
        scratch = Path(scratch)
        intro_video = render_clip(scratch / "intro", "intro", intro, project_title, subtitle) if intro != "none" else None
        outro_video = render_clip(scratch / "outro", "outro", outro, project_title, subtitle) if outro != "none" else None
        args, total = compose_argv(song, intro_video, outro_video, output, song_duration,
                                   resolution, has_audio, transition)
        # Reuse existing cancellable FFmpeg runner; no shell invocation.
        from local_studio.render_control import render_with_progress
        from local_studio.pipeline import probe
        from local_studio.render_quality import verify_output
        try:
            render_with_progress(args, cwd=str(scratch), duration=total,
                                 on_progress=on_progress, cancel_event=cancel_event)
            verify_output(output, total, resolution, has_audio, probe)
        except Exception:
            output.unlink(missing_ok=True)
            raise
        return total
