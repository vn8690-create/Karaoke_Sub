"""Launch the local UI: python -m local_studio [--no-browser] [--port 8776]."""
import argparse
import errno
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
import uuid
import webbrowser

from . import APP_ID

HOST = "127.0.0.1"
DEFAULT_PORT = 8776


def reserve_socket(preferred_port: int, max_attempts: int = 20) -> socket.socket:
    """Keep ownership of the selected port until Uvicorn takes the same socket.

    A separate availability check would race with another process. On Windows,
    exclusive binding also prevents another application sharing this listener.
    """
    if not 1 <= preferred_port <= 65535 or max_attempts < 1:
        raise ValueError("Port must be 1–65535; max_attempts must be positive")
    ports = list(range(preferred_port, min(65536, preferred_port + max_attempts))) + [0]
    for port in ports:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind((HOST, port))
            return listener
        except OSError as exc:
            listener.close()
            unavailable = exc.errno in {errno.EADDRINUSE, errno.EACCES} or getattr(exc, "winerror", None) in {10048, 10013}
            if port == 0 or not unavailable:
                raise
    raise OSError("Không tìm được cổng local còn trống.")


def open_when_ready(url: str, instance_id: str, stop: threading.Event, timeout: float = 60) -> bool:
    """Open only this launch's Karaoke Studio, never another app's health page."""
    deadline = time.monotonic() + timeout
    # The loopback probe must stay local even on PCs with a system HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while not stop.is_set() and time.monotonic() < deadline:
        try:
            with opener.open(url + "/api/health", timeout=1) as response:
                health = json.loads(response.read(4096))
            if (isinstance(health, dict) and health.get("ok") is True
                    and health.get("app") == APP_ID and health.get("instance") == instance_id):
                if stop.is_set():
                    return False
                webbrowser.open(url)
                return True
        except (OSError, ValueError, urllib.error.URLError):
            pass
        stop.wait(min(0.25, max(0, deadline - time.monotonic())))
    return False


def main():
    parser = argparse.ArgumentParser(description="Karaoke Sub — local studio")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="Cổng ưu tiên (mặc định 8776); tự chọn cổng khác nếu đang bị chiếm")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    import uvicorn

    stop = threading.Event()
    with reserve_socket(args.port) as listener:
        port = listener.getsockname()[1]
        url = f"http://{HOST}:{port}"
        instance_id = uuid.uuid4().hex
        os.environ["KARAOKE_INSTANCE_ID"] = instance_id
        if port != args.port:
            print(f"Cổng {args.port} đang được sử dụng/không khả dụng. Karaoke Sub chuyển sang cổng {port}.", flush=True)
        print(f"Karaoke Sub: {url} — Ctrl+C để dừng", flush=True)
        server = uvicorn.Server(uvicorn.Config("local_studio.app:app", host=HOST, port=port))
        if not args.no_browser:
            threading.Thread(target=open_when_ready, args=(url, instance_id, stop), daemon=True).start()
        try:
            server.run(sockets=[listener])
        finally:
            stop.set()


if __name__ == "__main__":
    main()
