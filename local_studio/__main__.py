"""Launch the local UI: python -m local_studio [--no-browser] [--port 8765]."""
import argparse
import threading
import webbrowser


def main():
    parser = argparse.ArgumentParser(description="Karaoke Sub — local studio")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    import uvicorn
    if not args.no_browser:
        def open_when_ready():
            import time
            import urllib.request
            url = f"http://127.0.0.1:{args.port}"
            for _ in range(60):
                try:
                    with urllib.request.urlopen(url + "/api/health", timeout=1):
                        webbrowser.open(url)
                        return
                except OSError:
                    time.sleep(1)
        threading.Thread(target=open_when_ready, daemon=True).start()
    print(f"Karaoke Sub: http://127.0.0.1:{args.port} — Ctrl+C để dừng")
    uvicorn.run("local_studio.app:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
