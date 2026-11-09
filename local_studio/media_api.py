"""Local and online background selection API for the standalone studio.

Search results remain server-side. Clients select opaque expiring IDs rather
than supplying download URLs. Provider credentials never enter project data.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import json
import mimetypes
import os
from pathlib import Path
import random
import shutil
import tempfile
import threading
import time
from typing import Literal
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import backgrounds

REGISTRY_LIMIT = 256
REGISTRY_TTL = 60 * 60
LOCAL_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".jpg", ".jpeg", ".png", ".webp", ".ogv"}
MAX_BYTES = backgrounds.MAX_DOWNLOAD_BYTES
MAX_LOCAL_BYTES = backgrounds.MAX_LOCAL_BYTES


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchRequest(StrictRequest):
    query: str = Field(min_length=1, max_length=160)
    provider: Literal["commons", "pexels"] = "commons"
    limit: int = Field(default=8, ge=1, le=8)


class LocalScanRequest(StrictRequest):
    folder: str = Field(min_length=1, max_length=4096)
    recursive: bool = False


class BackgroundRequest(StrictRequest):
    mode: Literal["selected", "local", "online"]
    asset_id: str | None = Field(default=None, max_length=100)
    folder: str | None = Field(default=None, max_length=4096)
    recursive: bool = False
    provider: Literal["commons", "pexels"] = "commons"
    query: str = Field(default="nature landscape", max_length=160)

    @model_validator(mode="after")
    def required_selection(self):
        if self.mode == "selected" and not self.asset_id:
            raise ValueError("Chọn một ảnh hoặc video nền trước.")
        if self.mode == "local" and not (self.folder or "").strip():
            raise ValueError("Nhập thư mục chứa ảnh/video nền.")
        if self.mode == "online" and not self.query.strip():
            raise ValueError("Nhập từ khóa tìm nền online.")
        return self


def create_router(studio) -> APIRouter:
    """Bind handlers to the running application's project persistence helpers."""
    router = APIRouter()
    registry: OrderedDict[str, tuple[float, dict]] = OrderedDict()
    registry_lock = threading.RLock()

    def settings_path() -> Path:
        return Path(studio.ROOT) / "settings.json"

    def read_settings() -> dict:
        with studio.LOCK:
            try:
                value = json.loads(settings_path().read_text(encoding="utf-8"))
                return value if isinstance(value, dict) else {}
            except (FileNotFoundError, ValueError, OSError):
                return {}

    def pexels_key() -> str | None:
        value = read_settings().get("pexels_api_key") or os.environ.get("PEXELS_API_KEY")
        return value if isinstance(value, str) and value.strip() else None

    def provider_metadata() -> dict:
        return {"providers": [
            {"id": "commons", "name": "Wikimedia Commons", "configured": True, "requires_key": False},
            {"id": "pexels", "name": "Pexels", "configured": bool(pexels_key()), "requires_key": True},
        ]}

    def provider_key(provider: str) -> str | None:
        key = pexels_key() if provider == "pexels" else None
        if provider == "pexels" and not key:
            raise HTTPException(400, "Pexels cần API key. Hãy lưu khóa trong mục Nền online hoặc chọn Wikimedia Commons.")
        return key

    def safe_exception(exc: Exception, key: str | None = None) -> RuntimeError:
        message = str(exc)[:3000]
        if key:
            message = message.replace(key, "[khóa đã ẩn]")
        return RuntimeError(message or "Không tải được nền. Hãy chọn nguồn khác hoặc thử lại.")

    def register(asset: dict, kind: str, local_root: Path | None = None) -> dict:
        asset = deepcopy(asset)
        asset["_kind"] = kind
        if local_root is not None:
            asset["_local_root"] = str(local_root)
        now = time.monotonic()
        asset_id = uuid.uuid4().hex
        with registry_lock:
            expired = [key for key, (created, _) in registry.items() if now - created >= REGISTRY_TTL]
            for key in expired:
                registry.pop(key, None)
            registry[asset_id] = (now, asset)
            while len(registry) > REGISTRY_LIMIT:
                registry.popitem(last=False)
        # Only presentation metadata is sent to the browser, never file/download
        # URLs or the user's filesystem path from a registered asset.
        public = {key: asset[key] for key in ("title", "provider", "type", "size", "license", "license_url", "author", "source_url", "preview_url", "thumbnail_url", "width", "height", "duration") if key in asset}
        public.update(id=asset_id, provider=asset.get("provider", "local" if kind == "local" else "commons"))
        if kind == "local":
            public["preview_url"] = f"/api/backgrounds/preview/{asset_id}"
        elif asset.get("preview_url") or asset.get("thumbnail_url"):
            public["preview_url"] = asset.get("preview_url") or asset["thumbnail_url"]
        return public

    def registered(asset_id: str) -> dict:
        with registry_lock:
            found = registry.get(asset_id)
            if found is None or time.monotonic() - found[0] >= REGISTRY_TTL:
                registry.pop(asset_id, None)
                raise HTTPException(404, "Nền đã hết hạn hoặc không tồn tại. Hãy tìm/quét lại rồi chọn.")
            return deepcopy(found[1])

    def scan(folder: str, recursive: bool) -> tuple[list[dict], Path]:
        try:
            assets = backgrounds.list_local(folder, recursive=recursive, limit=100)
            return assets, Path(folder).expanduser().resolve()
        except Exception as exc:
            raise HTTPException(400, str(safe_exception(exc))) from None

    def search(query: str, provider: str, limit: int) -> list[dict]:
        key = provider_key(provider)
        try:
            return backgrounds.search_online(query, provider=provider, api_key=key, limit=limit)
        except Exception as exc:
            raise HTTPException(400, str(safe_exception(exc, key))) from None

    @router.get("/api/backgrounds/providers")
    def providers():
        return provider_metadata()

    @router.get("/api/backgrounds/settings")
    def settings_metadata():
        return provider_metadata()

    @router.put("/api/backgrounds/settings")
    async def save_settings(request: Request):
        # Never let validation errors serialize a supplied API key as an input
        # value. Keep the whole settings body small and return generic failures.
        chunks = bytearray()
        async for chunk in request.stream():
            chunks.extend(chunk)
            if len(chunks) > 4096:
                raise HTTPException(413, "Nội dung cài đặt quá lớn.")
        try:
            body = json.loads(chunks)
        except (ValueError, UnicodeError):
            raise HTTPException(400, "Cài đặt phải là JSON có trường pexels_api_key.") from None
        if not isinstance(body, dict) or set(body) != {"pexels_api_key"} or not isinstance(body["pexels_api_key"], str):
            raise HTTPException(400, "Chỉ chấp nhận trường pexels_api_key dạng văn bản.")
        key = body["pexels_api_key"].strip()
        if len(key) > 300 or any(ord(char) < 32 or ord(char) > 126 for char in key):
            raise HTTPException(400, "API key không hợp lệ; hãy kiểm tra rồi nhập lại.")
        with studio.LOCK:
            settings = read_settings()
            if key:
                settings["pexels_api_key"] = key
            else:
                settings.pop("pexels_api_key", None)
            path = settings_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.parent / (".settings-" + uuid.uuid4().hex + ".tmp")
            try:
                descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(settings, stream, ensure_ascii=False, indent=2)
                temp.replace(path)
            finally:
                temp.unlink(missing_ok=True)
        return provider_metadata()

    @router.post("/api/backgrounds/search")
    def search_backgrounds(options: SearchRequest):
        assets = search(options.query.strip(), options.provider, options.limit)
        return {"assets": [register(asset, "online") for asset in assets]}

    @router.post("/api/backgrounds/local/scan")
    def scan_backgrounds(options: LocalScanRequest):
        assets, root = scan(options.folder, options.recursive)
        return {"assets": [register(asset, "local", root) for asset in assets]}

    def validated_local_path(asset: dict) -> Path:
        try:
            # The root was resolved at registration; do not resolve it anew,
            # which could accept a root directory replaced with a symlink.
            root = Path(asset["_local_root"])
            original = Path(asset["path"])
            if root.is_symlink() or original.is_symlink():
                raise ValueError("Không dùng liên kết tượng trưng làm nền.")
            path = original.resolve(strict=True)
            if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() not in LOCAL_EXTENSIONS:
                raise ValueError("Không tìm thấy nền local hợp lệ.")
            if not 0 < path.stat().st_size <= MAX_LOCAL_BYTES:
                raise ValueError("Nền local rỗng hoặc vượt quá giới hạn 4 GB.")
            return path
        except (KeyError, OSError, ValueError):
            raise ValueError("Nền local đã thay đổi hoặc không còn trong thư mục đã quét. Hãy quét lại.") from None

    @router.get("/api/backgrounds/preview/{asset_id}")
    def preview_background(asset_id: str):
        asset = registered(asset_id)
        if asset["_kind"] != "local":
            raise HTTPException(404, "Nguồn này không có tệp xem trước local.")
        try:
            path = validated_local_path(asset)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from None
        return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                            filename=path.name, content_disposition_type="inline")

    @router.post("/api/projects/{project_id}/background", status_code=202)
    def select_background(project_id: str, options: BackgroundRequest):
        studio.require_tools()
        with studio.LOCK:
            studio.idle(project_id)
            selected = registered(options.asset_id) if options.mode == "selected" else None
            # Fail a missing provider key immediately, before a background job is
            # enqueued; no credential is ever added to the public job manifest.
            key = provider_key(options.provider) if options.mode == "online" else None
            def operation():
                studio.update(project_id, status="processing", progress=10, message="Đang chọn và chuẩn bị nền…")
                asset = selected
                if options.mode == "local":
                    assets, root = scan(options.folder or "", options.recursive)
                    if not assets:
                        raise RuntimeError("Không tìm thấy ảnh/video phù hợp trong thư mục đã chọn.")
                    asset = deepcopy(random.choice(assets))
                    asset.update(_kind="local", _local_root=str(root))
                elif options.mode == "online":
                    assets = search(options.query.strip(), options.provider, 8)
                    if not assets:
                        raise RuntimeError("Không tìm thấy nền online phù hợp. Hãy đổi từ khóa.")
                    asset = deepcopy(random.choice(assets))
                    asset["_kind"] = "online"
                folder = studio.project_dir(project_id)
                studio.update(project_id, progress=30, message="Đang tải hoặc chép nền vào dự án…")
                try:
                    with tempfile.TemporaryDirectory(prefix="background-", dir=folder) as scratch:
                        staging = Path(scratch)
                        if asset.get("_kind") == "local":
                            validated_local_path(asset)
                        result = backgrounds.fetch_background(asset, staging)
                        name = result.get("filename")
                        if not isinstance(name, str) or Path(name).name != name:
                            raise ValueError("Nguồn nền trả về tên tệp không hợp lệ.")
                        source = (staging / name).resolve()
                        if source.parent != staging.resolve() or not source.is_file() or source.suffix.lower() not in LOCAL_EXTENSIONS:
                            raise ValueError("Không nhận được tệp nền hợp lệ.")
                        limit = MAX_LOCAL_BYTES if asset.get("_kind") == "local" else MAX_BYTES
                        if not 0 < source.stat().st_size <= limit:
                            raise ValueError("Nền rỗng hoặc vượt quá giới hạn dung lượng của nguồn đã chọn.")
                        info = studio.pipeline.probe(source)
                        if not any(stream.get("codec_type") == "video" for stream in info.get("streams", [])):
                            raise ValueError("Tệp nền phải chứa ảnh hoặc video.")
                        filename = "background-" + uuid.uuid4().hex[:12] + source.suffix.lower()
                        destination = folder / filename
                        shutil.copy2(source, destination)
                    project = studio.load(project_id)
                    old_background = project["files"].get("background")
                    old_video = project["files"].pop("video", None)
                    project["files"]["background"] = filename
                    attribution = result.get("attribution")
                    project["background_info"] = attribution if isinstance(attribution, dict) else {}
                    project["background_config"] = {"mode": options.mode}
                    if options.mode == "local":
                        project["background_config"].update(folder=options.folder, recursive=options.recursive)
                    if options.mode == "online":
                        project["background_config"].update(provider=options.provider, query=options.query.strip())
                    if options.mode == "selected":
                        project["background_config"]["provider"] = asset.get("provider", "local")
                    try:
                        studio.save(folder, project)
                    except Exception:
                        destination.unlink(missing_ok=True)
                        raise
                    # Windows players can still hold the old file open. Stop
                    # exposing it immediately; cleanup must not undo a good job.
                    for obsolete in (old_background, old_video):
                        if obsolete and obsolete != filename and Path(obsolete).name == obsolete:
                            try:
                                (folder / obsolete).unlink(missing_ok=True)
                            except OSError:
                                pass
                except Exception as exc:
                    raise safe_exception(exc, key or pexels_key()) from None
            return studio.submit(project_id, operation)

    return router
