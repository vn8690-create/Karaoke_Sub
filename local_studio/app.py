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
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import APP_ID, alignment, pipeline

log = logging.getLogger("local_studio")
ROOT = Path(os.environ.get("KARAOKE_DATA_DIR", Path(__file__).resolve().parents[1] / ".local-data")).resolve()
PROJECTS = ROOT / "projects"
PROJECTS.mkdir(parents=True, exist_ok=True)
ACTIVE = {"queued", "processing", "rendering"}
LOCK = threading.RLock()
WORKER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="karaoke")
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
    language: Literal["vi", "en", "auto"] = "vi"
    separate: bool = True


class ReferenceText(StrictModel):
    text: str = Field(min_length=1, max_length=100000)


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


class Render(SubtitleOptions):
    audio_mode: Literal["original", "instrumental", "silent"] = "instrumental"


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


def submit(project_id: str, operation):
    with LOCK:
        idle(project_id)
        result = update(project_id, status="queued", progress=0, error=None, message="Đang chờ xử lý…")
        def execute():
            try:
                operation()
                update(project_id, status="ready", progress=100, error=None, message="Hoàn tất")
            except Exception as exc:
                log.exception("Local job failed: %s", project_id)
                update(project_id, status="error", message="Xử lý thất bại", error=str(exc)[:2000])
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


@app.post("/api/projects/{project_id}/subtitles")
def subtitles(project_id: str, options: SubtitleOptions):
    with LOCK:
        p = idle(project_id)
        require_lyrics(p)
        outputs = pipeline.write_subtitles(p["segments"], project_dir(project_id), options.font_size,
                                           RESOLUTIONS[options.resolution], style=subtitle_style(options))
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
        def operation():
            folder = project_dir(project_id)
            p = load(project_id)
            update(project_id, status="rendering", progress=10, message="Đang xuất phụ đề và video…")
            outputs = pipeline.write_subtitles(p["segments"], folder, options.font_size, RESOLUTIONS[options.resolution],
                                               style=subtitle_style(options))
            audio_key = {"original": "audio", "instrumental": "instrumental", "silent": None}[options.audio_mode]
            audio = folder / p["files"][audio_key] if audio_key else None
            background = folder / p["files"]["background"] if "background" in p["files"] else None
            temp_output = folder / "rendering.mp4"
            try:
                pipeline.render_video(audio, background, folder / outputs["ass"], temp_output,
                                      p["duration"], RESOLUTIONS[options.resolution],
                                      lambda msg: update(project_id, message=msg))
                temp_output.replace(folder / "karaoke.mp4")
            finally:
                temp_output.unlink(missing_ok=True)
            p = load(project_id)
            p["files"].update(outputs, video="karaoke.mp4")
            p["last_render"] = options.model_dump()
            p["subtitle_style"] = {**subtitle_style(options), "font_size": options.font_size, "resolution": options.resolution}
            save(folder, p)
        return submit(project_id, operation)


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

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="assets")
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="ui")
