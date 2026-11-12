"""Optional CLI end-to-end smoke: actual HyperFrames composition to MP4 (Node 22+).

Run after npm install in motion_engine/. Never touches user project files.
"""
import json
from pathlib import Path
import subprocess
import tempfile

from motion_engine.core import installed, render_clip


def main():
    state = installed()
    if not state["installed"]:
        raise RuntimeError("HyperFrames/GSAP is not installed or Node is older than 22: "
                           + json.dumps(state))
    with tempfile.TemporaryDirectory(prefix="hyperframes-test-") as temp:
        path = render_clip(Path(temp), "intro", "neon", "NVS KARAOKE", "READY TO SING")
        details = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            capture_output=True, text=True, check=True, timeout=20,
        )
        info = json.loads(details.stdout)
        streams = info["streams"]
        assert any(stream.get("codec_type") == "video" for stream in streams), streams
        duration = float(info["format"]["duration"])
        assert 2.7 < duration < 3.3, duration
        print("HYPERFRAMES_GSAP_RENDER_OK", {"duration": duration, "bytes": path.stat().st_size})


if __name__ == "__main__":
    main()
