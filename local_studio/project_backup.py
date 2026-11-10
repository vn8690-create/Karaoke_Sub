"""Portable, local-only project backup with path and integrity validation.

A backup contains only the project manifest and files referenced by the project.
No settings, API keys, external directories, model weights or unrelated files.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

FORMAT = "nvs-karaoke-local-backup"
VERSION = 1
MAX_ARCHIVE = 12 * 1024**3
MAX_UNPACKED = 16 * 1024**3
MAX_FILE = 4 * 1024**3
MAX_FILES = 32
MAX_MANIFEST = 2 * 1024**2

KEY_EXTENSIONS = {
    "source": {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma",
               ".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"},
    "audio": {".wav"},
    "instrumental": {".wav"},
    "vocals": {".wav"},
    "background": {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v",
                   ".jpg", ".jpeg", ".png", ".webp"},
    "video": {".mp4"},
    "ass": {".ass"},
    "srt": {".srt"},
    "lrc": {".lrc"},
}

# A backup should not retain external filesystem locations or private settings.
PROJECT_FIELDS = {
    "title", "duration", "segments", "files", "version", "subtitle_style",
    "alignment", "reference_pending", "last_render", "background_info",
}


def _name(name: str) -> str:
    if (not isinstance(name, str) or not name or len(name) > 240
            or name in {".", ".."} or "/" in name or "\\" in name
            or ":" in name or "\x00" in name or name[-1] in {" ", "."}
            or any(ord(c) < 32 for c in name)):
        raise ValueError("Tên tệp trong bản sao lưu không hợp lệ.")
    if name.lower().split(".")[0] in {"con", "prn", "aux", "nul", "com1", "lpt1"}:
        raise ValueError("Tên tệp bị Windows dành riêng.")
    return name


def _files(project: dict) -> dict[str, str]:
    mapping = project.get("files")
    if not isinstance(mapping, dict) or not {"source", "audio"} <= set(mapping):
        raise ValueError("Bản sao lưu thiếu file nhạc gốc hoặc audio.")
    if len(mapping) > MAX_FILES or set(mapping) - set(KEY_EXTENSIONS):
        raise ValueError("Danh sách file dự án không hợp lệ.")
    used: dict[str, str] = {}
    for key, name in mapping.items():
        _name(name)
        if Path(name).suffix.lower() not in KEY_EXTENSIONS[key]:
            raise ValueError(f"Định dạng file không hợp lệ: {key}.")
        # Windows filesystem is case insensitive; a collision is unsafe.
        folded = name.casefold()
        if folded in used and used[folded] != name:
            raise ValueError("Hai file trong bản sao lưu trùng tên trên Windows.")
        used[folded] = name
    return mapping


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_backup(folder: Path, project: dict, destination: Path) -> None:
    mapping = _files(project)
    names = sorted(set(mapping.values()))
    if len(names) > MAX_FILES:
        raise ValueError("Dự án chứa quá nhiều file.")
    archive_files: list[dict] = []
    total = 0
    safe_folder = folder.resolve()
    for name in names:
        path = (safe_folder / name).resolve()
        if path.parent != safe_folder or not path.is_file() or path.is_symlink():
            raise ValueError(f"Thiếu file dự án hoặc đường dẫn không an toàn: {name}.")
        size = path.stat().st_size
        if size > MAX_FILE:
            raise ValueError(f"File vượt giới hạn 4 GB: {name}.")
        total += size
        if total > MAX_UNPACKED:
            raise ValueError("Dung lượng bản sao lưu quá lớn.")
        archive_files.append({"name": name, "size": size, "sha256": _sha256(path)})
    data = {key: project[key] for key in PROJECT_FIELDS if key in project}
    data["files"] = mapping
    manifest = {"format": FORMAT, "schema": VERSION, "project": data, "media": archive_files}
    encoded = json.dumps(manifest, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_MANIFEST:
        raise ValueError("Thông tin dự án vượt giới hạn.")
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED,
                         allowZip64=True) as archive:
        archive.writestr("manifest.json", encoded)
        for item in archive_files:
            archive.write(safe_folder / item["name"], arcname="media/" + item["name"])


def restore_backup(archive_path: Path, destination: Path, project_id: str, lyrics_model) -> dict:
    """Restore into a new staging folder; caller atomically publishes it."""
    try:
        source = zipfile.ZipFile(archive_path, "r")
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("ZIP sao lưu không hợp lệ.") from exc
    with source:
        members = source.infolist()
        if len(members) < 3 or len(members) > MAX_FILES + 1:
            raise ValueError("Số lượng file trong ZIP không hợp lệ.")
        lookup = {}
        for member in members:
            filename = member.filename
            if (member.is_dir() or member.flag_bits & 1
                    or (member.external_attr >> 16) & 0o170000 == 0o120000
                    or filename.casefold() in lookup):
                raise ValueError("ZIP có mục không an toàn hoặc trùng tên.")
            if filename != "manifest.json":
                if not filename.startswith("media/"):
                    raise ValueError("ZIP chứa file ngoài thư mục media.")
                _name(filename[6:])
            lookup[filename.casefold()] = member
        info = source.getinfo("manifest.json")
        if info.file_size > MAX_MANIFEST:
            raise ValueError("Manifest quá lớn.")
        try:
            manifest = json.loads(source.read(info))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Không đọc được manifest.") from exc
        if not isinstance(manifest, dict) or manifest.get("format") != FORMAT or manifest.get("schema") != VERSION:
            raise ValueError("Không hỗ trợ phiên bản sao lưu này.")
        project, entries = manifest.get("project"), manifest.get("media")
        if not isinstance(project, dict) or not isinstance(entries, list):
            raise ValueError("Manifest thiếu thông tin dự án.")
        mapping = _files(project)
        expected = set(mapping.values())
        if len(entries) != len(expected) or len(entries) > MAX_FILES:
            raise ValueError("Danh sách file không khớp manifest.")
        metadata: dict[str, dict] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Thông tin file không hợp lệ.")
            name = _name(entry.get("name"))
            if (name in metadata or name not in expected
                    or type(entry.get("size")) is not int
                    or not 0 <= entry["size"] <= MAX_FILE
                    or not isinstance(entry.get("sha256"), str)
                    or re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) is None):
                raise ValueError("Thông tin file hoặc checksum không hợp lệ.")
            metadata[name] = entry
        expected_members = {"manifest.json"} | {"media/" + name for name in expected}
        if set(member.filename for member in members) != expected_members:
            raise ValueError("ZIP chứa file thiếu hoặc không thuộc dự án.")
        if sum(entry["size"] for entry in entries) > MAX_UNPACKED:
            raise ValueError("Dung lượng giải nén quá lớn.")
        duration = project.get("duration")
        if (type(duration) not in (int, float) or not math.isfinite(duration)
                or not 0 < duration <= 24 * 3600):
            raise ValueError("Thời lượng dự án không hợp lệ.")
        validated = lyrics_model(segments=project.get("segments", []))
        if validated.segments and validated.segments[-1].end > duration + 0.1:
            raise ValueError("Lời bài hát vượt quá thời lượng dự án.")
        title = project.get("title")
        if not isinstance(title, str):
            raise ValueError("Tên dự án không hợp lệ.")
        destination.mkdir(parents=True, exist_ok=False)
        for name in sorted(expected):
            member = source.getinfo("media/" + name)
            entry = metadata[name]
            if member.file_size != entry["size"]:
                raise ValueError("Kích thước file không khớp.")
            target = destination / name
            digest = hashlib.sha256()
            copied = 0
            with source.open(member) as input_file, target.open("xb") as output_file:
                for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                    copied += len(chunk)
                    if copied > entry["size"]:
                        raise ValueError("File vượt dung lượng khai báo.")
                    digest.update(chunk)
                    output_file.write(chunk)
            if copied != entry["size"] or digest.hexdigest() != entry["sha256"]:
                raise ValueError("File trong bản sao lưu bị lỗi hoặc đã thay đổi.")
        clean = {key: project[key] for key in PROJECT_FIELDS if key in project}
        clean.update(id=project_id, title=title.strip()[:200] or "Bài hát khôi phục",
                     version=1, duration=float(duration),
                     segments=[s.model_dump() for s in validated.segments],
                     status="ready", progress=100, message="Đã khôi phục từ ZIP",
                     error=None, created_at=time.time(), updated_at=time.time())
        return clean


def create_router(studio) -> APIRouter:
    router = APIRouter()

    @router.get("/api/projects/{project_id}/backup")
    def download_backup(project_id: str):
        temporary = Path(tempfile.mkdtemp(prefix="nvs-backup-", dir=studio.ROOT))
        archive_path = temporary / "karaoke-project-backup.zip"
        try:
            with studio.LOCK:
                project = studio.idle(project_id)
                create_backup(studio.project_dir(project_id), project, archive_path)
            return FileResponse(
                archive_path, media_type="application/zip",
                filename="karaoke-project-backup.zip",
                background=BackgroundTask(shutil.rmtree, temporary, ignore_errors=True),
            )
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            shutil.rmtree(temporary, ignore_errors=True)
            raise HTTPException(400, str(exc)) from exc
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    @router.post("/api/projects/import-backup", status_code=201)
    async def import_backup(backup: UploadFile = File(...)):
        # Streaming prevents a large upload from being buffered in RAM.
        with tempfile.TemporaryDirectory(prefix="nvs-import-", dir=studio.ROOT) as scratch:
            temp_file = Path(scratch) / "uploaded.zip"
            total = 0
            try:
                with temp_file.open("wb") as output:
                    while data := await backup.read(1024 * 1024):
                        total += len(data)
                        if total > MAX_ARCHIVE:
                            raise HTTPException(413, "ZIP vượt giới hạn 12 GB.")
                        output.write(data)
            finally:
                await backup.close()
            project_id = uuid.uuid4().hex
            staging = studio.PROJECTS / (".import-" + project_id)
            final = studio.PROJECTS / project_id
            try:
                clean = await run_in_threadpool(
                    restore_backup, temp_file, staging, project_id, studio.Lyrics
                )
                with studio.LOCK:
                    studio.save(staging, clean)
                    staging.rename(final)
                return clean
            except (ValueError, OSError, zipfile.BadZipFile) as exc:
                shutil.rmtree(staging, ignore_errors=True)
                raise HTTPException(400, str(exc)) from exc
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                raise

    return router
