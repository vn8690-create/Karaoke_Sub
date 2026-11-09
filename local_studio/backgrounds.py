"""Local-folder and licensed online video backgrounds, without cloud accounts.

Wikimedia Commons works without a key. Pexels uses its official API and the key
is sent only to api.pexels.com. Downloads are bounded and validated before an
existing project background can be replaced. Only server-registered assets
should be passed to fetch_background by the API layer.
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .pipeline import probe

USER_AGENT = "KaraokeSubLocal/1.0 (https://github.com/vn8690-create/Karaoke_Sub; video background search)"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".ogv"}
MAX_DOWNLOAD_BYTES = 200 * 1024**2
MAX_LOCAL_BYTES = 4 * 1024**3
MAX_JSON_BYTES = 8 * 1024**2
DOWNLOAD_HOSTS = {
    "commons": {"upload.wikimedia.org"},
    "pexels": {"videos.pexels.com", "images.pexels.com"},
}


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        elif tag in {"br", "p", "div"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif tag in {"p", "div"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _plain(value) -> str:
    parser = _PlainText()
    parser.feed(str(value or ""))
    return " ".join("".join(parser.parts).split())[:1500]


def _link(value, hosts: set[str] | None = None) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return None
        if parsed.port not in {None, 80, 443}:
            return None
        if hosts and parsed.hostname.lower() not in hosts:
            return None
        if parsed.scheme == "http":
            value = urllib.parse.urlunsplit(parsed._replace(scheme="https"))
        return value
    except ValueError:
        return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def _opener():
    # Keep inherited proxy and TLS verification; only disable implicit redirects.
    return urllib.request.build_opener(_NoRedirect())


def _json_request(url: str, *, api_key: str | None = None) -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if api_key:
        if urllib.parse.urlsplit(url).hostname != "api.pexels.com":
            raise ValueError("API key chỉ được gửi tới API chính thức của Pexels.")
        headers["Authorization"] = api_key
    try:
        with _opener().open(urllib.request.Request(url, headers=headers), timeout=25) as response:
            body = response.read(MAX_JSON_BYTES + 1)
        if len(body) > MAX_JSON_BYTES:
            raise ValueError("Kết quả tìm kiếm quá lớn. Hãy thu hẹp từ khóa.")
        data = json.loads(body)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403} and api_key:
            raise ValueError("Pexels chưa chấp nhận API key. Kiểm tra key trong phần nguồn nền.") from None
        if exc.code == 429:
            raise ValueError("Nguồn video đang giới hạn lượt tìm kiếm. Hãy thử lại sau.") from None
        raise ValueError(f"Không truy cập được kho video (HTTP {exc.code}). Hãy thử lại hoặc chọn nguồn khác.") from None
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        raise ValueError("Không đọc được kết quả từ kho video. Kiểm tra mạng rồi thử lại.") from None
    if not isinstance(data, dict):
        raise ValueError("Kho video trả kết quả không hợp lệ.")
    return data


def _number(value, default=0):
    try:
        return max(0, float(value))
    except (TypeError, ValueError):
        return default


def _choose_video(files: list[dict], *, provider: str, duration: float = 0) -> dict | None:
    candidates = []
    for entry in files:
        url = entry.get("src", entry.get("link"))
        valid = _link(url, DOWNLOAD_HOSTS[provider])
        if not valid or urllib.parse.urlsplit(valid).scheme != "https":
            continue
        suffix = Path(urllib.parse.unquote(urllib.parse.urlsplit(valid).path)).suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            continue
        height, width = _number(entry.get("height")), _number(entry.get("width"))
        if height > 1080 or width > 1920:
            continue
        bandwidth = _number(entry.get("bandwidth"))
        if duration and bandwidth and duration * bandwidth / 8 > MAX_DOWNLOAD_BYTES:
            continue
        if _number(entry.get("size")) > MAX_DOWNLOAD_BYTES:
            continue
        # Prefer 720p, then the best smaller derivative, then 1080p.
        score = (0 if height == 720 else 1 if 0 < height < 720 else 2, -height if height < 720 else height)
        candidates.append((score, {**entry, "url": valid, "width": int(width), "height": int(height)}))
    return min(candidates, key=lambda candidate: candidate[0])[1] if candidates else None


def search_online(query: str, provider: str = "commons", api_key: str | None = None, limit: int = 8) -> list[dict]:
    """Search official APIs and retain the attribution needed for downloaded clips."""
    query = " ".join(str(query).split())
    if not query or len(query) > 160:
        raise ValueError("Nhập từ khóa video từ 1 đến 160 ký tự.")
    if not 1 <= limit <= 16:
        raise ValueError("Mỗi lần tìm từ 1 đến 16 video.")
    if provider not in {"commons", "pexels"}:
        raise ValueError("Nguồn online phải là Wikimedia Commons hoặc Pexels.")
    if provider == "pexels":
        if not api_key or not api_key.strip():
            raise ValueError("Pexels cần API key. Bạn có thể dùng Wikimedia Commons không cần key.")
        params = urllib.parse.urlencode({"query": query, "per_page": min(40, limit * 3), "orientation": "landscape"})
        data = _json_request("https://api.pexels.com/videos/search?" + params, api_key=api_key.strip())
        results = []
        for video in data.get("videos", []):
            choice = _choose_video(video.get("video_files", []), provider="pexels", duration=_number(video.get("duration")))
            source = _link(video.get("url"), {"www.pexels.com", "pexels.com"})
            if not choice or not source:
                continue
            results.append({"id": f"pexels:{video.get('id')}", "provider": "pexels", "title": _plain(video.get("title") or f"Pexels video {video.get('id')}"),
                            "preview_url": _link(video.get("image"), {"images.pexels.com"}), "source_url": source,
                            "download_url": choice["url"], "author": _plain(video.get("user", {}).get("name")),
                            "license": "Pexels License", "license_url": "https://www.pexels.com/license/",
                            "duration": _number(video.get("duration")), "width": choice["width"], "height": choice["height"]})
            if len(results) >= limit:
                break
        return results

    params = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                                    "gsrsearch": f"filetype:video {query}", "gsrlimit": min(40, limit * 3),
                                    "prop": "videoinfo", "viprop": "url|size|mime|extmetadata|derivatives", "viurlwidth": 640})
    data = _json_request("https://commons.wikimedia.org/w/api.php?" + params)
    if data.get("error"):
        raise ValueError("Wikimedia không thực hiện được tìm kiếm. Thử từ khóa ngắn hơn.")
    results = []
    pages = data.get("query", {}).get("pages", {})
    for page in sorted(pages.values(), key=lambda entry: entry.get("index", 999999)):
        infos = page.get("videoinfo", page.get("imageinfo", []))
        if not infos:
            continue
        info = infos[0]
        if not str(info.get("mime", "")).startswith("video/"):
            continue
        options = list(info.get("derivatives", []))
        options.append({"src": info.get("url"), "width": info.get("width"), "height": info.get("height"), "size": info.get("size")})
        choice = _choose_video(options, provider="commons", duration=_number(info.get("duration")))
        metadata = info.get("extmetadata", {})
        license_name = _plain(metadata.get("LicenseShortName", {}).get("value") or metadata.get("UsageTerms", {}).get("value"))
        source = _link(info.get("descriptionurl"), {"commons.wikimedia.org"})
        if not choice or not source or not license_name:
            continue
        results.append({"id": f"commons:{page.get('pageid')}", "provider": "commons",
                        "title": _plain(page.get("title", "").removeprefix("File:")),
                        "preview_url": _link(info.get("thumburl"), {"upload.wikimedia.org", "thumb.wikimedia.org"}),
                        "source_url": source, "download_url": choice["url"],
                        "author": _plain(metadata.get("Artist", {}).get("value")), "license": license_name,
                        "license_url": _link(metadata.get("LicenseUrl", {}).get("value")),
                        "duration": _number(info.get("duration")), "width": choice["width"], "height": choice["height"]})
        if len(results) >= limit:
            break
    return results


def list_local(folder: str, recursive: bool = False, limit: int = 100) -> list[dict]:
    """List only video files in the explicitly selected local folder."""
    if not 1 <= limit <= 500:
        raise ValueError("Mỗi lần quét từ 1 đến 500 video.")
    try:
        path = Path(folder).expanduser().resolve(strict=True)
    except (ValueError, OSError):
        raise ValueError("Không tìm thấy thư mục video. Nhập đường dẫn đầy đủ trên máy đang chạy Karaoke Sub.") from None
    if not path.is_dir():
        raise ValueError("Đường dẫn cần là một thư mục video.")
    results = []
    visited = 0
    try:
        for directory, children, filenames in os.walk(path, followlinks=False):
            children[:] = sorted(name for name in children if not (Path(directory) / name).is_symlink()) if recursive else []
            for name in sorted(filenames):
                visited += 1
                if visited > 20000:
                    return results
                file = Path(directory) / name
                if file.suffix.lower() not in VIDEO_EXTENSIONS or file.is_symlink() or not file.is_file():
                    continue
                resolved = file.resolve(strict=True)
                if not resolved.is_relative_to(path):
                    continue
                size = resolved.stat().st_size
                if not 0 < size <= MAX_LOCAL_BYTES:
                    continue
                results.append({"id": "local:" + hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:24],
                                "provider": "local", "title": str(resolved.relative_to(path)), "path": str(resolved), "size": size})
                if len(results) >= limit:
                    return results
    except (OSError, ValueError):
        raise ValueError("Không đọc được thư mục video. Kiểm tra quyền truy cập hoặc chọn thư mục khác.") from None
    return results


def _download(url: str, provider: str, destination: Path):
    opener = _opener()
    for attempt in range(4):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not _link(url, DOWNLOAD_HOSTS[provider]):
            raise ValueError("Địa chỉ tải video không thuộc kho đã chọn hoặc không dùng HTTPS.")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "video/*,application/octet-stream"})
        try:
            response = opener.open(request, timeout=30)
        except urllib.error.HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                location = exc.headers.get("Location")
                if not location or attempt == 3:
                    raise ValueError("Kho video chuyển hướng quá nhiều lần hoặc thiếu địa chỉ tải.") from None
                url = urllib.parse.urljoin(url, location)
                continue
            raise ValueError(f"Không tải được video (HTTP {exc.code}). Chọn clip khác hoặc thử lại.") from None
        except (urllib.error.URLError, OSError):
            raise ValueError("Không tải được video. Kiểm tra mạng rồi thử lại.") from None
        try:
            with response:
                length = response.headers.get("Content-Length", "")
                if str(length).isdigit() and int(length) > MAX_DOWNLOAD_BYTES:
                    raise ValueError("Video vượt giới hạn 200 MB. Chọn clip ngắn hoặc nhẹ hơn.")
                total = 0
                deadline = time.monotonic() + 180
                with destination.open("wb") as output:
                    while True:
                        if time.monotonic() > deadline:
                            raise ValueError("Tải video quá lâu. Chọn clip nhẹ hơn hoặc thử lại.")
                        chunk = response.read(1024 * 128)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_DOWNLOAD_BYTES:
                            raise ValueError("Video vượt giới hạn 200 MB. Chọn clip nhẹ hơn.")
                        output.write(chunk)
                if total == 0:
                    raise ValueError("Kho video trả tệp rỗng. Chọn clip khác.")
            return
        except (urllib.error.URLError, OSError):
            raise ValueError("Kết nối tải video bị gián đoạn. Hãy thử lại.") from None
    raise ValueError("Không tải được video sau chuyển hướng.")


def fetch_background(asset: dict, output_dir: Path) -> dict:
    """Stage, inspect, then atomically publish one local or online video clip."""
    provider = asset.get("provider")
    if provider not in {"local", "commons", "pexels"}:
        raise ValueError("Nguồn video không được hỗ trợ.")
    if provider == "local":
        source = Path(str(asset.get("path", "")))
        if source.is_symlink() or not source.is_file() or source.suffix.lower() not in VIDEO_EXTENSIONS:
            raise ValueError("Video local không còn tồn tại hoặc không hợp lệ. Quét lại thư mục.")
        size = source.stat().st_size
        if not 0 < size <= MAX_LOCAL_BYTES:
            raise ValueError("Video local rỗng hoặc lớn hơn 4 GB.")
        suffix = source.suffix.lower()
    else:
        url = str(asset.get("download_url", ""))
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not _link(url, DOWNLOAD_HOSTS[provider]):
            raise ValueError("Địa chỉ video không thuộc nguồn đã chọn hoặc không dùng HTTPS.")
        suffix = Path(urllib.parse.unquote(parsed.path)).suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            raise ValueError("Định dạng video tải về chưa được hỗ trợ.")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary = output_dir / f".background-{uuid.uuid4().hex}{suffix}"
    try:
        if provider == "local":
            with source.open("rb") as input_file, temporary.open("wb") as output_file:
                copied = 0
                while chunk := input_file.read(1024 * 1024):
                    copied += len(chunk)
                    if copied > MAX_LOCAL_BYTES:
                        raise ValueError("Video local tăng quá giới hạn 4 GB trong khi sao chép.")
                    output_file.write(chunk)
        else:
            _download(url, provider, temporary)
        info = probe(temporary)
        if not any(stream.get("codec_type") == "video" for stream in info.get("streams", [])):
            raise ValueError("Tệp đã chọn không có hình ảnh video hợp lệ.")
        filename = "background" + suffix
        temporary.replace(output_dir / filename)
        return {"filename": filename, "attribution": {
            "provider": provider, "title": _plain(asset.get("title")),
            "source_url": _link(asset.get("source_url")) if provider != "local" else None,
            "author": _plain(asset.get("author")) if provider != "local" else "Tệp trên máy của bạn",
            "license": _plain(asset.get("license")) if provider != "local" else "Theo quyền sử dụng tệp của bạn",
            "license_url": _link(asset.get("license_url")) if provider != "local" else None,
        }}
    finally:
        temporary.unlink(missing_ok=True)
