"""Local-only karaoke processing. Heavy AI packages are imported on demand.

No cloud account, external transcription API or upstream cloud backend is used.
Whisper and Demucs download their model weights on first use, then reuse a local
cache. All subprocesses use argument arrays rather than a shell.
"""

from collections.abc import Callable
import gc
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .subtitles import write_subtitles
from .model_cache import is_corrupt_checkpoint, load_whisper_with_repair


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", **kwargs)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Không tìm thấy {args[0]}. Hãy chạy windows/setup.bat và kiểm tra FFmpeg.") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "Không có thông tin lỗi.")[-6000:]
        raise RuntimeError(f"{Path(args[0]).name} thất bại (mã {result.returncode}):\n{detail}")
    return result


def probe(path: Path) -> dict:
    result = _run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams", "-of", "json", str(Path(path).resolve())])
    data = json.loads(result.stdout)
    try:
        duration = float(data.get("format", {}).get("duration", 0))
    except (TypeError, ValueError):
        duration = 0
    if not math.isfinite(duration) or duration < 0:
        duration = 0
    data["duration"] = duration
    return data


def extract_audio(source: Path, output: Path) -> float:
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-protocol_whitelist", "file,pipe", "-i", str(Path(source).resolve()),
          "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(output)])
    duration = probe(output)["duration"]
    if duration <= 0:
        raise ValueError("Tệp không có âm thanh hợp lệ hoặc thời lượng bằng 0.")
    return duration


def _device(device: str = "auto") -> str:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Thiếu PyTorch. Hãy chạy windows/setup.bat trước.") from exc
    if device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if device not in ("cuda", "cpu"):
        raise ValueError("Thiết bị phải là auto, cuda hoặc cpu.")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA chưa sẵn sàng. Cập nhật driver NVIDIA và chạy lại bộ cài GPU, hoặc chọn CPU.")
    return device


def _model_dir() -> Path:
    path = Path(os.environ.get("KARAOKE_MODEL_DIR", Path(__file__).resolve().parents[1] / ".local-data" / "models"))
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _free_cuda():
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def separate_audio(audio: Path, output_dir: Path, device: str = "auto", progress: Callable[[str], None] = lambda _: None) -> Path:
    """Produce stereo instrumental/vocals WAV files using local Demucs."""
    device = _device(device)
    audio = Path(audio).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    progress(f"Đang tách giọng hát bằng Demucs ({device}); lần đầu cần tải model.")
    environment = os.environ.copy()
    environment["TORCH_HOME"] = str(_model_dir() / "torch")
    # A separate process returns all model VRAM to the OS before transcription.
    with tempfile.TemporaryDirectory(prefix="separate-", dir=output_dir) as scratch:
        try:
            _run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "-d", device,
                  "--segment", "5", "--shifts", "1", "-o", scratch, str(audio)], env=environment)
        except RuntimeError as exc:
            if is_corrupt_checkpoint(exc):
                cache = _model_dir() / "torch" / "hub" / "checkpoints"
                raise RuntimeError(
                    "Checkpoint model tách giọng Demucs bị hỏng hoặc tải thiếu. "
                    "Đóng ứng dụng, kiểm tra các file .th trong: " + str(cache)
                    + ". Chỉ xóa cache model lỗi rồi chạy lại để tải mới; "
                    "không xóa dự án, lời TXT hay cài lại PyTorch."
                ) from exc
            raise
        stems = Path(scratch) / "htdemucs" / audio.stem
        instrumental = stems / "no_vocals.wav"
        vocals = stems / "vocals.wav"
        if not instrumental.is_file() or not vocals.is_file():
            raise RuntimeError("Demucs không tạo đủ hai tệp instrumental và vocals.")
        shutil.copy2(instrumental, output_dir / "instrumental.wav")
        shutil.copy2(vocals, output_dir / "vocals.wav")
    progress("Đã tách xong nhạc nền và giọng hát.")
    return output_dir / "instrumental.wav"


def transcribe_audio(audio: Path, model: str = "small", language: str | None = "vi", device: str = "auto",
                     progress: Callable[[str], None] = lambda _: None) -> list[dict]:
    device = _device(device)
    if model not in ("tiny", "base", "small", "medium", "large-v3"):
        raise ValueError("Model Whisper không hợp lệ.")
    try:
        import whisper_timestamped as whisper
    except ImportError as exc:
        raise RuntimeError("Thiếu whisper-timestamped. Hãy chạy windows/setup.bat.") from exc
    progress(f"Đang tải Whisper {model} ({device}); lần đầu cần tải model.")
    network = None
    samples = None
    try:
        network = load_whisper_with_repair(
            whisper.load_model, model, device, _model_dir() / "whisper", progress
        )
        progress("Đang nhận diện lời hát và thời gian từng từ…")
        samples = whisper.load_audio(str(Path(audio).resolve()))
        audio_duration = len(samples) / 16000  # Whisper's loader always resamples to 16 kHz.
        result = whisper.transcribe(network, samples, language=language or None, fp16=device == "cuda",
                                    verbose=False, vad=False, condition_on_previous_text=False)
        segments = []
        previous_end = 0.0
        for raw in result.get("segments", []):
            words = []
            previous_end = max(previous_end, float(raw.get("start", 0)))
            for word in raw.get("words", []):
                text = str(word.get("text", "")).strip()
                start = max(previous_end, float(word.get("start", previous_end)))
                end = max(start + 0.01, float(word.get("end", start + 0.01)))
                if not text or not math.isfinite(start) or not math.isfinite(end):
                    continue
                if audio_duration > 0:
                    end = min(end, audio_duration)
                if round(end, 3) <= round(start, 3):
                    continue
                words.append({"text": text, "start": round(start, 3), "end": round(end, 3)})
                previous_end = end
            # Do not invent word timestamps if the model provides no alignment.
            if words:
                segments.append({"start": words[0]["start"], "end": words[-1]["end"], "words": words})
        if not segments:
            raise RuntimeError("Không nhận diện được lời hát. Thử đổi ngôn ngữ/model hoặc dùng âm thanh giọng hát rõ hơn.")
        return segments
    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            raise RuntimeError("GPU hết VRAM. Chọn model small/base hoặc thiết bị CPU rồi thử lại.") from exc
        raise
    finally:
        del network, samples
        _free_cuda()


def render_video(audio: Path | None, background: Path | None, ass: Path, output: Path, duration: float,
                 resolution: tuple = (1920, 1080), progress: Callable[[str], None] | None = None,
                 on_progress: Callable[[int], None] | None = None,
                 cancel_event=None) -> None:
    """Render a bounded MP4, looping the background and never mixing its audio."""
    duration = float(duration)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Thời lượng xuất phải lớn hơn 0.")
    if resolution not in ((1280, 720), (1920, 1080)):
        raise ValueError("Độ phân giải phải là 720p hoặc 1080p.")
    width, height = resolution
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    ass = Path(ass).resolve()
    if progress:
        progress("Đang xuất video MP4; thời gian phụ thuộc độ dài bài hát và CPU.")
    # Filter expressions have their own quoting rules beyond argv. A fixed
    # relative name and cwd eliminate drive-colon/quote/backslash problems on
    # Windows and filenames containing Vietnamese or apostrophes.
    with tempfile.TemporaryDirectory(prefix="render-", dir=output.parent) as scratch:
        shutil.copy2(ass, Path(scratch) / "lyrics.ass")
        args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
        if background:
            args += ["-protocol_whitelist", "file,pipe", "-stream_loop", "-1", "-i", str(Path(background).resolve())]
        else:
            args += ["-f", "lavfi", "-i", f"color=c=0x101426:s={width}x{height}:r=30"]
        if audio:
            args += ["-protocol_whitelist", "file,pipe", "-i", str(Path(audio).resolve())]
        filters = (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                   f"crop={width}:{height},setsar=1,fps=30,ass=lyrics.ass")
        args += ["-map", "0:v:0", "-vf", filters]
        if audio:
            args += ["-map", "1:a:0", "-af", "apad", "-c:a", "aac", "-b:a", "192k"]
        else:
            args += ["-an"]
        args += ["-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)]
        try:
            from .render_control import render_with_progress
            render_with_progress(args, cwd=scratch, duration=duration,
                                 on_progress=on_progress, cancel_event=cancel_event)
            # Never report success for a cut-off or audio-less render.
            from .render_quality import verify_output
            verify_output(output, duration, resolution, audio is not None, probe)
        except Exception:
            output.unlink(missing_ok=True)
            raise
    if progress:
        progress("Đã xuất video MP4.")
