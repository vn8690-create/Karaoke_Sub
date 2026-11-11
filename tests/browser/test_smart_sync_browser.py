"""Real Chrome UI smoke for Smart Lyrics Sync, without Torch/FFmpeg/AI weights.

Run in GitHub Windows runner after:
  python -m pip install fastapi pydantic python-multipart uvicorn httpx playwright
  python tests/browser/test_smart_sync_browser.py
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
from uuid import uuid4
import wave

from playwright.sync_api import sync_playwright, expect


REPO = Path(__file__).resolve().parents[2]
URL = "http://127.0.0.1:8878"


def line(text, start, step=0.3):
    words = [{"text": t, "start": round(start + i * step, 3),
              "end": round(start + (i + 1) * step, 3)}
             for i, t in enumerate(text.split())]
    return {"start": words[0]["start"], "end": words[-1]["end"], "words": words}


def fixture(directory):
    ident = uuid4().hex
    folder = directory / "projects" / ident
    folder.mkdir(parents=True)
    # Three seconds of silent WAV is enough for browser media fetch; our
    # manifest's 30-second duration is used by the editor for lyric timing.
    with wave.open(str(folder / "audio.wav"), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 48000)
    segments = [
        line("Vì vậy hãy đoán cho chúng ta một lần nữa", 0.1),
        line("Vì vậy hãy đoán cho chúng ta một lần nữa", 4.0),
        line("Hẹn gặp ngày mai", 9.0),
        line("Em là người tôi yêu", 13.0),
    ]
    manifest = {"id": ident, "title": "Smart Sync UI Smoke", "status": "ready",
                "progress": 100, "message": "Ready", "error": None, "duration": 30.0,
                "segments": segments, "files": {"audio": "audio.wav", "source": "audio.wav"},
                "created_at": time.time(), "version": 1}
    (folder / "project.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return ident


def check():
    with tempfile.TemporaryDirectory(prefix="karaoke-browser-smoke-") as tmp:
        folder = Path(tmp)
        project_id = fixture(folder)
        env = os.environ.copy()
        env.update(KARAOKE_DATA_DIR=str(folder), PYTHONUTF8="1")
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "local_studio.app:app", "--host", "127.0.0.1", "--port", "8878"],
            cwd=str(REPO), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(70):
                if server.poll() is not None:
                    raise RuntimeError("FastAPI terminated before browser smoke started")
                try:
                    with urllib.request.urlopen(URL + "/api/health", timeout=2) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(0.4)
            else:
                raise RuntimeError("FastAPI did not become available on 8878")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 920})
                    page.on("dialog", lambda dialog: dialog.accept())
                    page.goto(URL + "/", wait_until="domcontentloaded")
                    expect(page.locator("#smart-preview")).to_be_attached()
                    expect(page.locator("#project-select option[value='" + project_id + "']")).to_be_attached(timeout=20000)
                    page.locator("#project-select").select_option(project_id)
                    expect(page.locator("#project-name")).to_have_text("Smart Sync UI Smoke")
                    page.locator("#reference-lyrics").fill("[Intro]\nHẹn gặp ngày mai!\nEm là người anh yêu")
                    page.locator("#save-reference").click()
                    expect(page.locator("#reference-status")).to_contain_text("Đã lưu")
                    page.locator("#smart-preview").click()
                    expect(page.locator("#smart-panel")).to_be_visible()
                    expect(page.locator(".smart-row.smart-blocked")).to_have_count(2)
                    expect(page.locator(".smart-row.smart-safe")).to_have_count(1)
                    expect(page.locator(".smart-row.smart-review")).to_have_count(1)
                    expect(page.locator(".smart-row.smart-safe input:checked")).to_have_count(1)
                    expect(page.locator(".smart-row.smart-review input:checked")).to_have_count(0)
                    page.locator(".smart-row.smart-review input").check()
                    page.locator("#smart-apply").click()
                    expect(page.locator("#smart-undo")).to_be_enabled()
                    expect(page.locator("#lyrics-list")).to_contain_text("mai!")
                    expect(page.locator("#lyrics-list")).to_contain_text("anh")
                    # Unmatched hallucinations are preserved, never deleted.
                    expect(page.locator("#lyrics-list")).to_contain_text("Vì vậy")
                    page.locator("#smart-undo").click()
                    expect(page.locator("#smart-panel")).to_be_hidden()
                    expect(page.locator("#lyrics-list")).to_contain_text("tôi")
                    expect(page.locator("#lyrics-list")).to_contain_text("mai")
                    print("SMART_SYNC_BROWSER_OK")
                finally:
                    browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__ == "__main__":
    check()
