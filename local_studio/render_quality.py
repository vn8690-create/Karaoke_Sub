"""Deterministic MP4 quality checks after FFmpeg render.

Metadata checks detect truncated, missing-audio and wrong-size exports.
They do not claim to detect silent passages, visual glitches or lyric accuracy.
"""
from __future__ import annotations

import math
from pathlib import Path


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def analyze_probe(info: dict, expected_duration: float, resolution: tuple[int, int],
                  expect_audio: bool | None) -> dict:
    """Return machine-readable findings without modifying source media."""
    if not math.isfinite(float(expected_duration)) or expected_duration <= 0:
        raise ValueError("Thời lượng bài hát không hợp lệ.")
    if not isinstance(info, dict):
        info = {}
    streams = info.get("streams") or []
    if not isinstance(streams, list):
        streams = []
    video = next((s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"), None)
    format_info = info.get("format") or {}
    if not isinstance(format_info, dict):
        format_info = {}
    duration = _finite(info.get("duration"))
    if duration is None:
        duration = _finite(format_info.get("duration"))
    tolerance = max(0.45, expected_duration * 0.002)
    issues = []

    def issue(code, message):
        issues.append({"severity": "error", "code": code, "message": message})

    if video is None:
        issue("video_missing", "File MP4 không có luồng hình ảnh.")
    else:
        if (video.get("width"), video.get("height")) != resolution:
            issue("resolution_mismatch", "Độ phân giải không đúng cấu hình xuất.")
        if video.get("codec_name") != "h264":
            issue("video_codec", "Video không được mã hóa H.264.")
        video_duration = _finite(video.get("duration"))
        if video_duration is not None and abs(video_duration - expected_duration) > tolerance:
            issue("video_duration", "Luồng video thiếu phút hoặc dài hơn bài hát.")
    if duration is None or abs(duration - expected_duration) > tolerance:
        issue("duration_mismatch", "Thời lượng MP4 không trùng với bài hát.")
    if expect_audio is True:
        if audio is None:
            issue("audio_missing", "Video thiếu âm thanh.")
        else:
            if audio.get("codec_name") != "aac":
                issue("audio_codec", "Âm thanh không được mã hóa AAC.")
            audio_duration = _finite(audio.get("duration"))
            if audio_duration is not None and audio_duration < expected_duration - max(0.6, tolerance):
                issue("audio_truncated", "Âm thanh bị cắt trước khi hết bài.")
            start_video = _finite(video.get("start_time")) if video else None
            start_audio = _finite(audio.get("start_time"))
            if start_video is not None and start_audio is not None and abs(start_video - start_audio) > 0.25:
                issue("av_start_mismatch", "Âm thanh và hình ảnh lệch mốc bắt đầu.")
    elif expect_audio is False and audio is not None:
        issue("unexpected_audio", "Chế độ không tiếng nhưng file vẫn có âm thanh.")
    return {
        "ok": not issues, "checked": True,
        "expected_duration": round(expected_duration, 3),
        "actual_duration": round(duration, 3) if duration is not None else None,
        "resolution": [video.get("width"), video.get("height")] if video else None,
        "video_codec": video.get("codec_name") if video else None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "issues": issues,
    }


def verify_output(path: Path, expected_duration: float, resolution: tuple[int, int],
                  expect_audio: bool | None, prober) -> dict:
    if not Path(path).is_file() or Path(path).stat().st_size == 0:
        raise RuntimeError("Video chưa được tạo hoặc file rỗng.")
    report = analyze_probe(prober(Path(path)), expected_duration, resolution, expect_audio)
    if not report["ok"]:
        summary = "; ".join(item["message"] for item in report["issues"])
        raise RuntimeError("Kiểm tra MP4 thất bại: " + summary)
    return report
