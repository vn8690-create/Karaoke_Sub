"""Port collision and browser readiness regressions, without model downloads."""
from __future__ import annotations

import contextlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
from urllib.request import ProxyHandler, build_opener

from local_studio import __main__ as launcher


@contextlib.contextmanager
def health_server(payload):
    """An actual unrelated local app, bound before the launcher is tested."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class LauncherTests(unittest.TestCase):
    def test_default_port_does_not_overlap_cover_studio(self):
        self.assertEqual(launcher.DEFAULT_PORT, 8776)

    def test_occupied_port_falls_back_and_keeps_original_service(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as original:
            original.bind(("127.0.0.1", 0))
            original.listen(1)
            occupied = original.getsockname()[1]
            with launcher.reserve_socket(occupied) as reserved:
                chosen = reserved.getsockname()
                self.assertEqual(chosen[0], "127.0.0.1")
                self.assertNotEqual(chosen[1], occupied)
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as competitor:
                    with self.assertRaises(OSError):
                        competitor.bind(chosen)
                # The launcher neither kills nor takes over the original app.
                with socket.create_connection(("127.0.0.1", occupied), timeout=2):
                    connection, _ = original.accept()
                    connection.close()

    def test_exhausted_preferred_range_uses_os_assigned_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as original:
            original.bind(("127.0.0.1", 0))
            original.listen(1)
            with launcher.reserve_socket(original.getsockname()[1], max_attempts=1) as reserved:
                self.assertGreater(reserved.getsockname()[1], 0)
                self.assertNotEqual(reserved.getsockname()[1], original.getsockname()[1])

    def test_browser_never_opens_for_foreign_or_stale_health(self):
        for payload in (
            {"ok": True},
            {"ok": True, "app": "cover-studio", "instance": "this-launch"},
            {"ok": True, "app": "karaoke-sub-local", "instance": "previous-launch"},
            {"ok": False, "app": "karaoke-sub-local", "instance": "this-launch"},
            b"Not JSON: Cover Studio",
            ["ok", "karaoke-sub-local"],
        ):
            with self.subTest(payload=payload), health_server(payload) as server, \
                    patch.object(launcher.webbrowser, "open") as browser:
                url = f"http://127.0.0.1:{server.server_port}"
                self.assertFalse(launcher.open_when_ready(url, "this-launch", threading.Event(), timeout=0.08))
                browser.assert_not_called()

    def test_browser_opens_once_only_after_matching_instance_is_ready(self):
        payload = {"ok": True, "app": "karaoke-sub-local", "instance": "this-launch"}
        with health_server(payload) as server, patch.object(launcher.webbrowser, "open") as browser:
            url = f"http://127.0.0.1:{server.server_port}"
            self.assertTrue(launcher.open_when_ready(url, "this-launch", threading.Event(), timeout=1))
            browser.assert_called_once_with(url)

    def test_stopped_launch_does_not_open_browser(self):
        stop = threading.Event()
        stop.set()
        with patch.object(launcher.webbrowser, "open") as browser:
            self.assertFalse(launcher.open_when_ready("http://127.0.0.1:1", "this-launch", stop, timeout=1))
            browser.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec("uvicorn"), "uvicorn required for launcher integration")
    def test_real_launcher_runs_beside_an_existing_app(self):
        opener = build_opener(ProxyHandler({}))
        with health_server({"ok": True, "app": "cover-studio"}) as cover, \
                tempfile.TemporaryDirectory(prefix="karaoke-launcher-") as temp:
            folder = Path(temp)
            environment = os.environ.copy()
            environment.update(KARAOKE_DATA_DIR=str(folder / "data"), PYTHONUNBUFFERED="1", PYTHONUTF8="1")
            with (folder / "server.log").open("w", encoding="utf-8") as log:
                process = subprocess.Popen(
                    [sys.executable, "-m", "local_studio", "--no-browser", "--port", str(cover.server_port)],
                    cwd=Path(__file__).resolve().parents[2], env=environment,
                    stdout=log, stderr=subprocess.STDOUT,
                )
                try:
                    deadline = time.monotonic() + 20
                    ready = None
                    output = ""
                    while time.monotonic() < deadline:
                        output = (folder / "server.log").read_text(encoding="utf-8", errors="replace")
                        match = re.search(r"Karaoke Sub: (http://127\.0\.0\.1:\d+)", output)
                        if match:
                            url = match.group(1)
                            try:
                                with opener.open(url + "/api/health", timeout=1) as response:
                                    ready = json.load(response)
                                break
                            except OSError:
                                pass
                        if process.poll() is not None:
                            self.fail("Launcher exited before startup:\n" + output)
                        time.sleep(0.05)
                    self.assertIsNotNone(ready, "Launcher did not become ready:\n" + output)
                    self.assertTrue(ready["ok"])
                    self.assertEqual(ready["app"], "karaoke-sub-local")
                    self.assertTrue(ready["instance"])
                    self.assertNotEqual(int(url.rsplit(":", 1)[1]), cover.server_port)
                    with opener.open(f"http://127.0.0.1:{cover.server_port}/api/health", timeout=1) as response:
                        self.assertEqual(json.load(response)["app"], "cover-studio")
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
