"""Small standalone local API. No upstream cloud services or API keys required."""
from __future__ import annotations

import json
import logging
import math
import mimetypes
import os
import re
import shutil
import sys
import threading
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import APP_ID, alignment, pipeline
from .reference_timing import apply_reference_to_existing
from .smart_sync import build_preview, apply_selection, revision_for, segments_revision
from motion_engine import core as motion_core
from motion_engine.compositor import add_motion

log = logging.getLogger("local_studio")
ROOT = Path(os.environ.get("KARAOKE_DATA_DIR", Path(__file__).resolve().parents[1] / ".local-data")).resolve()
PROJECTS = ROOT / "projects"
PROJECTS.mkdir(parents=True, exist_ok=True)
ACTIVE = {"queued", "processing", "rendering"}
LOCK = threading.RLock()
WORKER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="karaoke")
# Render cancellation is independent of the AI task queue.
RENDER_CANCEL: dict[str, threading.Event] = {}
AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma"}
VIDEO_EXT = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
UPLOAD_LIMIT = 4 * 1024**3  # Per file; streamed rather than read into RAM.
RESOLUTIONS = {"1080p": (1920, 1080), "720p": (1280, 720)}


def project_dir(project_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", project_id):
        raise HTTPException(404, "Không tìm thấy dự án.")
    folder = PROJECTS / project_id
    if not (folder / "project.json").is_file():
        raise HTTPException(404, "Không tìm thấy dự án.")
    return folder


def load(project_id: str) -> dict:
    with LOCK:
        return json.loads((project_dir(project_id) / "project.json").read_text(encoding="utf-8"))


def save(folder: Path, project: dict):
    with LOCK:
        project["updated_at"] = time.time()
        temp = folder / (".project-" + uuid.uuid4().hex + ".tmp")
        temp.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(folder / "project.json")


def update(project_id: str, **changes) -> dict:
    with LOCK:
        p = load(project_id)
        p.update(changes)
        save(project_dir(project_id), p)
        return p


# An interrupted process cannot resume GPU work. Keep files/lyrics for retry.
for manifest in PROJECTS.glob("*/project.json"):
    try:
        p = json.loads(manifest.read_text(encoding="utf-8"))
        if p.get("status") in ACTIVE:
            p.update(status="error", progress=0, error="Tác vụ bị ngắt khi đóng ứng dụng. Hãy chạy lại.")
            save(manifest.parent, p)
    except (ValueError, OSError):
        log.warning("Cannot read project %s", manifest.parent.name)

app = FastAPI(title="Karaoke Sub Local", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])


@app.middleware("http")
async def local_origin(request: Request, call_next):
    # Prevent other websites from submitting work to the local process.
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != f"{request.url.scheme}://{request.headers.get('host')}":
            return JSONResponse({"detail": "Origin không được phép."}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Yêu cầu từ website khác bị chặn."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Word(StrictModel):
    text: str = Field(min_length=1, max_length=300)
    start: float = Field(ge=0)
    end: float = Field(gt=0)

    @model_validator(mode="after")
    def valid(self):
        self.text = self.text.strip()
        if not self.text or "\n" in self.text or "\r" in self.text or self.end <= self.start:
            raise ValueError("Từ phải có nội dung và thời gian kết thúc lớn hơn bắt đầu.")
        return self


class Segment(StrictModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    words: list[Word] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def valid(self):
        cursor = self.start
        for word in self.words:
            if word.start < cursor - 0.001 or word.end > self.end + 0.001:
                raise ValueError("Thời gian các từ phải theo thứ tự và nằm trong câu.")
            cursor = word.end
        if self.end <= self.start:
            raise ValueError("Thời gian kết thúc câu phải lớn hơn bắt đầu.")
        return self


class Lyrics(StrictModel):
    segments: list[Segment] = Field(max_length=5000)

    @model_validator(mode="after")
    def valid(self):
        cursor = 0.0
        for segment in self.segments:
            if segment.start < cursor - 0.001:
                raise ValueError("Các câu không được chồng thời gian.")
            cursor = segment.end
        return self


class Device(StrictModel):
    device: Literal["auto", "cuda", "cpu"] = "auto"


class Transcribe(Device):
    model: Literal["tiny", "base", "small", "medium", "large-v3"] = "small"
    language: Literal["vi", "en", "ja", "auto"] = "vi"
    separate: bool = True


class ReferenceText(StrictModel):
    text: str = Field(min_length=1, max_length=100000)


class ApplyReference(StrictModel):
    estimate: bool = False  # True only after an explicit UI opt-in.


class SmartSyncApply(StrictModel):
    revision: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    selected: list[str] = Field(min_length=1, max_length=240)


class Align(Transcribe):
    text: str = Field(min_length=1, max_length=100000)


class Timing(StrictModel):
    offset_seconds: float = Field(ge=-30, le=30)


class SubtitleOptions(StrictModel):
    resolution: Literal["720p", "1080p"] = "1080p"
    font_size: int = Field(default=54, ge=24, le=100)
    font_family: Literal["Arial", "Tahoma", "Segoe UI", "Times New Roman"] = "Arial"
    text_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    highlight_color: str = Field(default="#FFE800", pattern=r"^#[0-9A-Fa-f]{6}$")
    position: Literal["bottom", "center", "top"] = "bottom"
    margin_percent: int = Field(default=9, ge=5, le=25)
    countdown: bool = False


class Render(SubtitleOptions):
    audio_mode: Literal["original", "instrumental", "silent"] = "instrumental"
    motion_intro: Literal["none", "neon", "cinematic", "minimal", "retro"] = "none"
    motion_outro: Literal["none", "neon", "cinematic", "minimal", "retro"] = "none"
    motion_transition: Literal["fade", "wipeleft", "smoothleft"] = "fade"


def idle(project_id: str) -> dict:
    p = load(project_id)
    if p["status"] in ACTIVE:
        raise HTTPException(409, "Dự án đang xử lý. Vui lòng chờ tác vụ hiện tại.")
    return p


def require_lyrics(p: dict):
    if not p["segments"]:
        raise HTTPException(400, "Hãy tạo hoặc nhập lời trước khi xuất phụ đề/video.")


def require_tools():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise HTTPException(503, "Thiếu FFmpeg/ffprobe. Chạy windows\\setup.bat rồi mở lại ứng dụng.")


def discard_exports(folder: Path, p: dict):
    for key in ("video", "ass", "srt", "lrc"):
        filename = p["files"].pop(key, None)
        if filename:
            (folder / filename).unlink(missing_ok=True)


def submit(project_id: str, operation, cancel_event: threading.Event | None = None):
    from .render_control import RenderCancelled
    with LOCK:
        idle(project_id)
        result = update(project_id, status="queued", progress=0, error=None, message="Đang chờ xử lý…")
        def execute():
            try:
                if cancel_event is not None and cancel_event.is_set():
                    raise RenderCancelled("Đã hủy tác vụ xuất video.")
                operation()
                if cancel_event is not None and cancel_event.is_set():
                    raise RenderCancelled("Đã hủy tác vụ xuất video.")
                update(project_id, status="ready", progress=100, error=None, message="Hoàn tất")
            except RenderCancelled:
                update(project_id, status="cancelled", progress=0, error=None,
                       message="Đã hủy xuất video. Có thể xuất lại bất cứ lúc nào.")
            except Exception as exc:
                log.exception("Local job failed: %s", project_id)
                update(project_id, status="error", message="Xử lý thất bại", error=str(exc)[:2000])
            finally:
                if cancel_event is not None:
                    with LOCK:
                        if RENDER_CANCEL.get(project_id) is cancel_event:
                            RENDER_CANCEL.pop(project_id, None)
        WORKER.submit(execute)
        return result


@app.get("/api/health")
def health():
    return {"ok": True, "app": APP_ID, "instance": os.environ.get("KARAOKE_INSTANCE_ID", "")}


@app.get("/api/system")
def system_info():
    info = {"ffmpeg": bool(shutil.which("ffmpeg")), "ffprobe": bool(shutil.which("ffprobe")),
            "torch": False, "cuda": False, "gpu": None, "model_cache": str(Path(os.environ.get("KARAOKE_MODEL_DIR", Path(__file__).resolve().parents[1] / ".local-data" / "models")).resolve())}
    try:
        import torch
        info.update(torch=True, cuda=torch.cuda.is_available())
        if info["cuda"]:
            info["gpu"] = torch.cuda.get_device_name(0)
    except (ImportError, OSError):
        pass
    return info


@app.get("/api/projects")
def list_projects():
    results = []
    with LOCK:
        for manifest in PROJECTS.glob("*/project.json"):
            try:
                results.append(json.loads(manifest.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                pass
    return sorted(results, key=lambda p: p["updated_at"], reverse=True)


async def store_upload(upload: UploadFile, folder: Path, stem: str, extensions: set[str]) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in extensions:
        raise HTTPException(400, f"Định dạng {stem} không hỗ trợ: {suffix}")
    destination = folder / (stem + suffix)
    total = 0
    try:
        with destination.open("wb") as stream:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > UPLOAD_LIMIT:
                    raise HTTPException(413, "Mỗi tệp tối đa 4 GB.")
                stream.write(chunk)
        if not total:
            raise HTTPException(400, "Tệp tải lên rỗng.")
        return destination.name
    finally:
        await upload.close()


@app.post("/api/projects", status_code=201)
async def create_project(title: str = Form("Bài hát mới"), source: UploadFile = File(...),
                         background: UploadFile | None = File(None), instrumental: UploadFile | None = File(None)):
    require_tools()
    project_id = uuid.uuid4().hex
    folder = PROJECTS / project_id
    folder.mkdir()
    try:
        files = {"source": await store_upload(source, folder, "source", AUDIO_EXT | VIDEO_EXT)}
        if background and background.filename:
            files["background"] = await store_upload(background, folder, "background", VIDEO_EXT | IMAGE_EXT)
            # Validate media now rather than fail much later during export.
            background_info = await run_in_threadpool(pipeline.probe, folder / files["background"])
            if not any(s.get("codec_type") == "video" for s in background_info.get("streams", [])):
                raise ValueError("Tệp nền phải chứa hình ảnh hoặc video.")
        duration = await run_in_threadpool(pipeline.extract_audio, folder / files["source"], folder / "audio.wav")
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Không đọc được thời lượng âm thanh.")
        files["audio"] = "audio.wav"
        if instrumental and instrumental.filename:
            beat = await store_upload(instrumental, folder, "beat-source", AUDIO_EXT | VIDEO_EXT)
            beat_duration = await run_in_threadpool(pipeline.extract_audio, folder / beat, folder / "instrumental.wav")
            if abs(beat_duration - duration) > 2:
                raise ValueError("Beat lệch thời lượng bài gốc quá 2 giây. Hãy dùng beat cùng phiên bản.")
            files["instrumental"] = "instrumental.wav"
        p = {"id": project_id, "title": title.strip()[:200] or "Bài hát mới", "status": "ready",
             "progress": 100, "message": "Đã nhập bài hát", "error": None, "duration": duration,
             "segments": [], "files": files, "created_at": time.time(), "version": 1}
        save(folder, p)
        return p
    except Exception as exc:
        shutil.rmtree(folder, ignore_errors=True)
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(400, str(exc)[:2000]) from exc


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    return load(project_id)


@app.put("/api/projects/{project_id}/lyrics")
def save_lyrics(project_id: str, body: Lyrics):
    with LOCK:
        p = idle(project_id)
        if body.segments and body.segments[-1].end > p["duration"] + 0.1:
            raise HTTPException(400, "Lời vượt quá thời lượng bài hát.")
        discard_exports(project_dir(project_id), p)
        p.update(segments=[s.model_dump() for s in body.segments], error=None, status="ready", message="Đã lưu lời")
        if p.get("alignment"):
            p["alignment"]["manually_edited"] = True
        save(project_dir(project_id), p)
        return p


def ensure_instrumental(project_id: str, device: str, require_vocals: bool = False):
    p = load(project_id)
    folder = project_dir(project_id)
    if "instrumental" not in p["files"] or (require_vocals and "vocals" not in p["files"]):
        # Stage stems separately: an uploaded beat must not be replaced when only
        # vocals are needed for alignment, or when separation fails halfway.
        with tempfile.TemporaryDirectory(prefix="stems-", dir=folder) as scratch:
            staging = Path(scratch)
            pipeline.separate_audio(folder / p["files"]["audio"], staging, device,
                                    lambda msg: update(project_id, message=msg))
            if not (staging / "vocals.wav").is_file() or not (staging / "instrumental.wav").is_file():
                raise ValueError("Tách giọng chưa tạo đủ vocal và instrumental.")
            p = load(project_id)
            shutil.copy2(staging / "vocals.wav", folder / "vocals.wav")
            p["files"]["vocals"] = "vocals.wav"
            if "instrumental" not in p["files"]:
                shutil.copy2(staging / "instrumental.wav", folder / "instrumental.wav")
                p["files"]["instrumental"] = "instrumental.wav"
            save(folder, p)


@app.post("/api/projects/{project_id}/separate", status_code=202)
def separate(project_id: str, options: Device):
    require_tools()
    def operation():
        update(project_id, status="processing", progress=10, message="Đang tách giọng hát…")
        ensure_instrumental(project_id, options.device, require_vocals=True)
    return submit(project_id, operation)


@app.post("/api/projects/{project_id}/transcribe", status_code=202)
def transcribe(project_id: str, options: Transcribe):
    require_tools()
    def operation():
        update(project_id, status="processing", progress=5, message="Đang chuẩn bị nhận diện lời…")
        if options.separate:
            ensure_instrumental(project_id, options.device, require_vocals=True)
        p = load(project_id)
        folder = project_dir(project_id)
        input_audio = folder / p["files"].get("vocals", p["files"]["audio"])
        update(project_id, progress=40, message="Đang nhận diện lời và thời gian từng từ…")
        segments = pipeline.transcribe_audio(input_audio, options.model,
                        None if options.language == "auto" else options.language, options.device,
                        lambda msg: update(project_id, message=msg))
        # Treat model output like imported data, including bounds checks.
        validated = Lyrics(segments=segments)
        if not validated.segments:
            raise ValueError("Không nhận diện được lời. Thử bài có giọng rõ hơn hoặc model khác.")
        if validated.segments[-1].end > p["duration"] + 0.1:
            raise ValueError("Thời gian nhận diện vượt thời lượng bài hát.")
        p = load(project_id)
        discard_exports(folder, p)
        p["segments"] = [s.model_dump() for s in validated.segments]
        p["alignment"] = {"source": "asr", "engine": "whisper-timestamped", "warnings": [],
                          "reference_text": None, "stale": bool(p.get("reference_lyrics", {}).get("text"))}
        p["reference_pending"] = bool(p.get("reference_lyrics", {}).get("text"))
        save(folder, p)
    return submit(project_id, operation)


def parse_reference(text: str) -> dict:
    try:
        cleaned = alignment.clean_lyrics(text)
        if not cleaned.get("text") or not cleaned.get("lines"):
            raise ValueError("Lời chuẩn không có câu hát sau khi bỏ chỉ dẫn trong ngoặc vuông.")
        if len(cleaned["text"].split()) > 20000:
            raise ValueError("Lời quá dài (tối đa 20.000 từ).")
        if any(len(word) > 300 for word in cleaned["text"].split()):
            raise ValueError("Một từ dài quá 300 ký tự. Hãy kiểm tra lại nội dung TXT.")
        return {**cleaned, "raw_text": text}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def store_reference(project_id: str, p: dict, reference: dict):
    changed = reference["text"] != p.get("reference_lyrics", {}).get("text")
    p["reference_lyrics"] = reference
    aligned_text = p.get("alignment", {}).get("reference_text")
    p["reference_pending"] = reference["text"] != aligned_text
    if p.get("alignment"):
        p["alignment"]["stale"] = p["reference_pending"]
    if changed:
        discard_exports(project_dir(project_id), p)
    (project_dir(project_id) / "lyrics-reference.txt").write_text(reference["text"] + "\n", encoding="utf-8")
    p["files"]["reference"] = "lyrics-reference.txt"
    save(project_dir(project_id), p)


@app.put("/api/projects/{project_id}/reference")
def save_reference(project_id: str, body: ReferenceText):
    reference = parse_reference(body.text)
    with LOCK:
        p = idle(project_id)
        p.update(status="ready", error=None, message="Đã lưu lời chuẩn; nhấn Căn lời theo giọng hát để tạo mốc thời gian.")
        store_reference(project_id, p, reference)
        return p


@app.post("/api/projects/{project_id}/reference/apply-timing")
def apply_saved_reference_timing(project_id: str, body: ApplyReference):
    """Use TXT as display text with existing timestamps, even if AI is unavailable.

    The default requires identical line/word counts and preserves every word
    interval. Explicit estimate=True is approximate and clearly marked.
    Neither mode fabricates model results or alters original source audio.
    """
    with LOCK:
        p = idle(project_id)
        reference = p.get("reference_lyrics") or {}
        if not reference.get("text") or not reference.get("lines"):
            raise HTTPException(400, "Hãy chọn TXT và nhấn Lưu lời chuẩn trước.")
        if not p.get("segments"):
            raise HTTPException(400, "Chưa có mốc thời gian cũ để ghép TXT. Hãy căn lời trước.")
        try:
            segments, estimated = apply_reference_to_existing(
                p["segments"], reference["lines"], estimate=body.estimate
            )
            validated = Lyrics(segments=segments)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        if validated.segments and validated.segments[-1].end > p["duration"] + 0.1:
            raise HTTPException(409, "Mốc thời gian hiện tại vượt độ dài bài hát; không thay đổi lời cũ.")
        folder = project_dir(project_id)
        # Keep one recoverable snapshot of the prior lyrics, not just an undo in UI.
        original = folder / "lyrics-before-txt.json"
        if not original.exists():
            original.write_text(
                json.dumps({"segments": p["segments"]}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        p["files"]["lyrics_before_txt"] = original.name
        discard_exports(folder, p)
        p["segments"] = [segment.model_dump() for segment in validated.segments]
        p["alignment"] = {
            "source": "reference",
            "engine": "manual-estimate" if estimated else "manual-preserve",
            "reference_text": reference["text"],
            "stale": False,
            "manually_edited": True,
            "estimated": estimated,
            "warnings": (
                ["Mốc từng từ đã ƯỚC LƯỢNG từ thời gian cũ vì số câu/từ không trùng TXT. "
                 "Hãy nghe kiểm tra và chỉnh từng từ trước khi xuất MP4."]
                if estimated else
                ["Đã áp dụng đúng chữ TXT và giữ nguyên từng mốc thời gian cũ."]
            ),
        }
        p["reference_pending"] = False
        p.update(status="ready", progress=100, error=None,
                 message="Đã áp dụng lời TXT (mốc từng từ ước lượng)." if estimated
                 else "Đã áp dụng lời TXT, giữ nguyên từng mốc thời gian.")
        save(folder, p)
        return p


@app.post("/api/projects/{project_id}/smart-sync/preview")
def preview_smart_sync(project_id: str):
    """Read-only preview. Never change a subtitle or fabricate a timestamp."""
    with LOCK:
        p = idle(project_id)
        reference = p.get("reference_lyrics") or {}
        if not reference.get("text") or not reference.get("lines"):
            raise HTTPException(400, "Hãy chọn file TXT và Lưu lời chuẩn trước.")
        try:
            result = build_preview(p.get("segments", []), reference["lines"], reference["text"])
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"revision": result["revision"], "items": result["items"],
                "counts": result["counts"], "project_id": project_id}


@app.post("/api/projects/{project_id}/smart-sync/apply")
def apply_smart_sync(project_id: str, body: SmartSyncApply):
    """Apply only explicitly approved green/yellow text changes.

    Rebuild the proposal from current project state; a changed TXT or timeline
    invalidates the preview. Red/unmatched lines are never auto-deleted.
    """
    with LOCK:
        p = idle(project_id)
        reference = p.get("reference_lyrics") or {}
        if not reference.get("text") or not reference.get("lines"):
            raise HTTPException(400, "TXT chuẩn chưa được lưu.")
        try:
            preview = build_preview(p.get("segments", []), reference["lines"], reference["text"])
            if body.revision != preview["revision"]:
                raise HTTPException(409, "Lời hoặc mốc thời gian đã thay đổi. Hãy bấm Xem trước lại.")
            proposed = apply_selection(p["segments"], preview, body.selected)
            validated = Lyrics(segments=proposed)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        if validated.segments and validated.segments[-1].end > p["duration"] + 0.1:
            raise HTTPException(409, "Lời ghép vượt độ dài bài hát; chưa áp dụng.")
        full = all(row["status"] == "same" or row["id"] in body.selected
                   for row in preview["items"])
        estimated = any(row.get("estimated_words", 0) > 0
                        for row in preview["items"] if row["id"] in body.selected)
        backup = {
            "segments": p["segments"], "alignment": p.get("alignment"),
            "reference_pending": p.get("reference_pending", False),
        }
        folder = project_dir(project_id)
        snapshot = folder / "lyrics-before-smart-sync.json"
        snapshot.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
        discard_exports(folder, p)
        p["files"]["smart_sync_backup"] = snapshot.name
        p["segments"] = [segment.model_dump() for segment in validated.segments]
        p["alignment"] = {
            "source": "reference" if full else "smart-sync",
            "engine": "smart-sync",
            "reference_text": reference["text"] if full else None,
            "stale": not full,
            "manually_edited": True,
            "estimated": estimated,
            "warnings": [
                f"Smart Sync đã sửa {len(body.selected)} câu; "
                + ("còn những câu chưa ghép, xem lại chữ hoặc thêm mốc thủ công." if not full
                   else "đã ghép toàn bộ lời TXT.")
                + (" Có mốc ước lượng, hãy nghe kiểm tra." if estimated else "")
            ],
        }
        p["reference_pending"] = not full
        p["smart_sync"] = {
            "can_undo": True, "applied_sha": segments_revision(p["segments"]),
            "changed_lines": len(body.selected), "estimated": estimated,
            "unresolved_lines": preview["counts"]["blocked"],
        }
        p.update(status="ready", progress=100, error=None,
                 message=f"Smart Sync đã cập nhật {len(body.selected)} câu. "
                         "Nhấn Hoàn tác nếu chưa đúng.")
        save(folder, p)
        return p


@app.post("/api/projects/{project_id}/smart-sync/undo")
def undo_smart_sync(project_id: str):
    """Single-step undo. Never overwrite edits made after a Smart Sync apply."""
    with LOCK:
        p = idle(project_id)
        info = p.get("smart_sync") or {}
        snapshot = project_dir(project_id) / "lyrics-before-smart-sync.json"
        if not info.get("can_undo") or not snapshot.is_file():
            raise HTTPException(409, "Không có bản Smart Sync để hoàn tác.")
        if info.get("applied_sha") != segments_revision(p["segments"]):
            raise HTTPException(409, "Đã có chỉnh sửa mới sau Smart Sync. "
                                "Không hoàn tác tự động để tránh mất phần đã sửa tay.")
        old = json.loads(snapshot.read_text(encoding="utf-8"))
        validated = Lyrics(segments=old["segments"])
        discard_exports(project_dir(project_id), p)
        p["segments"] = [segment.model_dump() for segment in validated.segments]
        if old.get("alignment") is None:
            p.pop("alignment", None)
        else:
            p["alignment"] = old["alignment"]
        p["reference_pending"] = old.get("reference_pending", False)
        p.pop("smart_sync", None)
        p["files"].pop("smart_sync_backup", None)
        p.update(status="ready", progress=100, error=None,
                 message="Đã hoàn tác Smart Sync; lời và mốc cũ được phục hồi.")
        save(project_dir(project_id), p)
        return p


@app.post("/api/projects/{project_id}/align", status_code=202)
def align_reference(project_id: str, options: Align):
    require_tools()
    reference = parse_reference(options.text)
    with LOCK:
        p = idle(project_id)
        store_reference(project_id, p, reference)
        def operation():
            update(project_id, status="processing", progress=5, message="Đang chuẩn bị căn lời chuẩn theo giọng hát…")
            if options.separate:
                ensure_instrumental(project_id, options.device, require_vocals=True)
            p = load(project_id)
            folder = project_dir(project_id)
            audio = folder / p["files"].get("vocals", p["files"]["audio"])
            update(project_id, progress=40, message="Đang căn từng từ trong lời chuẩn vào giọng hát…")
            result = alignment.align_lyrics(audio, reference["text"], options.model,
                                           options.language, options.device,
                                           lambda msg: update(project_id, message=msg))
            validated = Lyrics(segments=result["segments"])
            if not validated.segments:
                raise ValueError("Không tìm được mốc thời gian cho lời chuẩn. Kiểm tra lại bài hát và nội dung TXT.")
            actual = [w.text for segment in validated.segments for w in segment.words]
            if " ".join(actual).split() != reference["text"].split():
                raise ValueError("Kết quả căn chưa giữ đủ lời chuẩn. Không thay lời cũ; hãy kiểm tra nội dung TXT và thử lại.")
            if validated.segments[-1].end > p["duration"] + 0.1:
                raise ValueError("Thời gian căn vượt độ dài bài hát; lời cũ được giữ nguyên.")
            p = load(project_id)
            discard_exports(folder, p)
            p["segments"] = [segment.model_dump() for segment in validated.segments]
            p["alignment"] = {"source": "reference", "engine": result.get("engine", "stable-ts"),
                              "warnings": result.get("warnings", []), "reference_text": reference["text"],
                              "stale": False, "manually_edited": False, "offset_seconds": 0,
                              "language": result.get("language", options.language)}
            p["reference_pending"] = False
            save(folder, p)
        return submit(project_id, operation)


@app.post("/api/projects/{project_id}/timing")
def shift_timing(project_id: str, options: Timing):
    with LOCK:
        p = idle(project_id)
        require_lyrics(p)
        offset = options.offset_seconds
        if offset == 0:
            return p
        for segment in p["segments"]:
            segment["start"] = round(segment["start"] + offset, 3)
            segment["end"] = round(segment["end"] + offset, 3)
            for word in segment["words"]:
                word["start"] = round(word["start"] + offset, 3)
                word["end"] = round(word["end"] + offset, 3)
        if p["segments"][0]["start"] < 0 or p["segments"][-1]["end"] > p["duration"]:
            raise HTTPException(400, "Dịch mốc làm lời vượt đầu/cuối bài hát. Hãy chọn số giây nhỏ hơn.")
        try:
            validated = Lyrics(segments=p["segments"])
        except ValueError as exc:
            raise HTTPException(400, "Mốc thời gian không hợp lệ sau khi dịch.") from exc
        p["segments"] = [segment.model_dump() for segment in validated.segments]
        discard_exports(project_dir(project_id), p)
        if p.get("alignment"):
            p["alignment"]["offset_seconds"] = round(p["alignment"].get("offset_seconds", 0) + offset, 3)
        p.update(status="ready", error=None, message=f"Đã dịch lời {offset:+g} giây. Xuất lại video để áp dụng.")
        save(project_dir(project_id), p)
        return p


def subtitle_style(options: SubtitleOptions) -> dict:
    return {key: getattr(options, key) for key in
            ("font_family", "text_color", "highlight_color", "position", "margin_percent")}


@app.get("/api/motion/presets")
def motion_presets():
    """Optional presets; the existing karaoke workflow never needs npm."""
    return {
        "presets": motion_core.PRESETS,
        "transitions": motion_core.TRANSITIONS,
        "engine": motion_core.installed(),
        "optional": True,
    }


@app.get("/api/motion/preview", response_class=HTMLResponse)
def motion_preview(kind: Literal["intro", "outro"] = "intro",
                   preset: Literal["neon", "cinematic", "minimal", "retro"] = "neon",
                   title: str = "KARAOKE STUDIO", subtitle: str = ""):
    """Standalone HTML preview. Without npm it uses CSS; with GSAP it also runs timelines."""
    if len(title) > 100 or len(subtitle) > 100:
        raise HTTPException(422, "Tên bài và ca sĩ không được vượt 100 ký tự.")
    html = motion_core.composition_html(
        kind, preset, title, subtitle, gsap_path="/api/motion/gsap.js")
    return HTMLResponse(html, headers={"Cache-Control": "no-store",
                                     "Content-Security-Policy":
                                     "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline' 'self'; "
                                     "img-src 'self' data:; connect-src 'none'; frame-ancestors 'self'"})


@app.get("/api/motion/gsap.js")
def motion_gsap():
    """Serve locally installed GSAP; never pull arbitrary scripts from the CDN."""
    source = motion_core.ROOT / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    if not source.is_file():
        raise HTTPException(404, "Chưa cài GSAP tùy chọn. Preview CSS vẫn hoạt động.")
    return FileResponse(source, media_type="text/javascript")


@app.post("/api/projects/{project_id}/subtitles")
def subtitles(project_id: str, options: SubtitleOptions):
    with LOCK:
        p = idle(project_id)
        require_lyrics(p)
        outputs = pipeline.write_subtitles(p["segments"], project_dir(project_id), options.font_size,
                                           RESOLUTIONS[options.resolution], style=subtitle_style(options),
                                           countdown=options.countdown)
        p["subtitle_style"] = {**subtitle_style(options), "font_size": options.font_size, "resolution": options.resolution}
        p["files"].update(outputs)
        save(project_dir(project_id), p)
        return p


@app.post("/api/projects/{project_id}/render", status_code=202)
def render(project_id: str, options: Render):
    require_tools()
    with LOCK:
        p = idle(project_id)
        require_lyrics(p)
        if options.audio_mode == "instrumental" and "instrumental" not in p["files"]:
            raise HTTPException(400, "Hãy tách vocal hoặc nhập beat trước khi xuất chế độ nhạc nền.")
        cancel_event = threading.Event()
        RENDER_CANCEL[project_id] = cancel_event
        def operation():
            folder = project_dir(project_id)
            p = load(project_id)
            update(project_id, status="rendering", progress=10, message="Đang xuất phụ đề và video…")
            outputs = pipeline.write_subtitles(p["segments"], folder, options.font_size, RESOLUTIONS[options.resolution],
                                               style=subtitle_style(options), countdown=options.countdown)
            audio_key = {"original": "audio", "instrumental": "instrumental", "silent": None}[options.audio_mode]
            audio = folder / p["files"][audio_key] if audio_key else None
            background = folder / p["files"]["background"] if "background" in p["files"] else None
            temp_output = folder / "rendering.mp4"
            try:
                pipeline.render_video(audio, background, folder / outputs["ass"], temp_output,
                                      p["duration"], RESOLUTIONS[options.resolution],
                                      lambda msg: update(project_id, message=msg),
                                      on_progress=lambda percent: update(
                                          project_id, progress=10 + int(percent * 0.88),
                                          message=f"Đang xuất video MP4: {percent}%"
                                      ), cancel_event=cancel_event)
                if cancel_event.is_set():
                    from .render_control import RenderCancelled
                    raise RenderCancelled("Đã hủy tác vụ xuất video.")
                if options.motion_intro != "none" or options.motion_outro != "none":
                    if cancel_event.is_set():
                        from .render_control import RenderCancelled
                        raise RenderCancelled("Đã hủy Motion Engine.")
                    update(project_id, progress=98, message="Motion Engine: dựng intro/outro với HyperFrames + GSAP…")
                    enhanced = folder / "motion-rendered.mp4"
                    try:
                        add_motion(
                            temp_output, enhanced,
                            project_title=p.get("title", "KARAOKE STUDIO"),
                            subtitle="NVS KARAOKE",
                            intro=options.motion_intro,
                            outro=options.motion_outro,
                            transition=options.motion_transition,
                            song_duration=p["duration"],
                            resolution=RESOLUTIONS[options.resolution],
                            has_audio=audio is not None,
                            on_progress=None,
                            cancel_event=cancel_event,
                        )
                        enhanced.replace(temp_output)
                    finally:
                        enhanced.unlink(missing_ok=True)
                temp_output.replace(folder / "karaoke.mp4")
            finally:
                temp_output.unlink(missing_ok=True)
            p = load(project_id)
            p["files"].update(outputs, video="karaoke.mp4")
            p["last_render"] = options.model_dump()
            p["subtitle_style"] = {**subtitle_style(options), "font_size": options.font_size, "resolution": options.resolution}
            save(folder, p)
        return submit(project_id, operation, cancel_event=cancel_event)


@app.post("/api/projects/{project_id}/render/cancel")
def cancel_render(project_id: str):
    with LOCK:
        project = load(project_id)
        event = RENDER_CANCEL.get(project_id)
        if event is None or project["status"] not in {"queued", "rendering"}:
            raise HTTPException(409, "Dự án không có tác vụ render đang chờ hoặc chạy.")
        event.set()
        return {"status": "cancelling", "message": "Đã yêu cầu hủy. Đang dừng FFmpeg an toàn."}


@app.get("/api/projects/{project_id}/quality")
def render_quality_report(project_id: str):
    """Inspect a completed MP4 without touching media or re-running AI."""
    from .render_quality import analyze_probe
    p = load(project_id)
    filename = p.get("files", {}).get("video")
    folder = project_dir(project_id).resolve()
    if (not isinstance(filename, str) or Path(filename).name != filename
            or not (folder / filename).resolve().is_file()
            or (folder / filename).resolve().parent != folder):
        raise HTTPException(404, "Dự án chưa có video MP4 để kiểm tra.")
    try:
        info = pipeline.probe(folder / filename)
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(422, "Không kiểm tra được file MP4. Hãy xuất lại video.") from exc
    recorded = p.get("last_render") or {}
    resolution = RESOLUTIONS.get(recorded.get("resolution"))
    if resolution is None:
        # Older projects did not store render options: don't invent a target.
        video = next((v for v in info.get("streams", []) if v.get("codec_type") == "video"), {})
        resolution = (video.get("width"), video.get("height"))
    mode = recorded.get("audio_mode")
    expect_audio = (mode != "silent") if mode in ("original", "instrumental", "silent") else None
    return analyze_probe(info, float(p["duration"]), resolution, expect_audio)


@app.get("/api/projects/{project_id}/download")
def download_project(project_id: str):
    p = load(project_id)
    return JSONResponse(p, headers={"Content-Disposition": 'attachment; filename="karaoke-project.json"'})


@app.get("/api/projects/{project_id}/files/{filename}")
def get_file(project_id: str, filename: str):
    p = load(project_id)
    folder = project_dir(project_id)
    if filename not in p["files"].values() or Path(filename).name != filename:
        raise HTTPException(404, "Không tìm thấy tệp.")
    path = (folder / filename).resolve()
    if path.parent != folder.resolve() or not path.is_file():
        raise HTTPException(404, "Không tìm thấy tệp.")
    media = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media, filename=filename)


# The background library shares the same loopback/origin guards and job queue.
from .media_api import create_router
app.include_router(create_router(sys.modules[__name__]))

# Portable project ZIP backup and restore; no frontend modifications.
from .project_backup import create_router as create_backup_router
app.include_router(create_backup_router(sys.modules[__name__]))

# Optional built React Studio: same-origin /nvs/ -> /api, no permissive CORS needed.
_nvs_dist = Path(__file__).resolve().parents[1] / "nvs_studio" / "dist"
if _nvs_dist.is_dir():
    app.mount("/nvs", StaticFiles(directory=_nvs_dist, html=True), name="nvs_studio")

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="assets")
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="ui")
