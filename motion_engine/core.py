"""Optional HTML motion compositions for @hyperframes/cli and GSAP.

This is a separate rendering adapter, *not* a replacement for FFmpeg, ASS,
Whisper, audio extraction, or lyric timing. All titles are escaped before HTML.
"""
from __future__ import annotations

from html import escape
import os
from pathlib import Path
import shutil
import subprocess

PRESETS = {
    "neon": {"label": "Neon Pulse", "detail": "Ánh tím xanh, chữ nổi & vệt sáng", "accent": "#A790FF", "accent2": "#45E4CE", "bg": "#100E27"},
    "cinematic": {"label": "Cinema Gold", "detail": "Tựa phim tối, ánh vàng trang trọng", "accent": "#F3D48A", "accent2": "#E7A45F", "bg": "#171416"},
    "minimal": {"label": "Minimal Clean", "detail": "Chữ lớn tối giản, chuyển động nhẹ", "accent": "#D6EDFA", "accent2": "#8BBDC7", "bg": "#14212B"},
    "retro": {"label": "Retro Wave", "detail": "Sắc hồng, xanh neon kiểu synthwave", "accent": "#F68BCC", "accent2": "#5AD4F9", "bg": "#251435"},
}
TRANSITIONS = {
    "fade": "Fade mượt",
    "wipeleft": "Quét ngang",
    "smoothleft": "Trượt mềm",
}
KINDS = {"intro", "outro"}
DURATION = 3.0
TRANSITION_DURATION = 0.55
ROOT = Path(__file__).resolve().parent


def installed() -> dict:
    """No network calls or implicit install; useful before showing render button."""
    bin_dir = ROOT / "node_modules" / ".bin"
    executable = bin_dir / ("hyperframes.cmd" if os.name == "nt" else "hyperframes")
    gsap = ROOT / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    node = shutil.which("node")
    version = None
    if node:
        try:
            output = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=4)
            if output.returncode == 0:
                version = output.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    node_ok = bool(version and version.startswith("v") and int(version[1:].split(".")[0]) >= 22)
    return {
        "installed": node_ok and executable.is_file() and gsap.is_file(),
        "node_version": version, "node_ok": node_ok,
        "hyperframes": executable.is_file(), "gsap": gsap.is_file(),
    }


def _color_palette(preset: str) -> dict:
    if preset not in PRESETS:
        raise ValueError("Mẫu Motion Engine không hợp lệ.")
    return PRESETS[preset]


def composition_html(kind: str, preset: str, title: str, subtitle: str = "", *, gsap_path: str = "./assets/gsap.min.js") -> str:
    """Self-contained HyperFrames composition with a paused registered GSAP timeline."""
    if kind not in KINDS:
        raise ValueError("Loại clip Motion Engine không hợp lệ.")
    if len(title) > 100 or len(subtitle) > 100:
        raise ValueError("Tên bài hoặc tên ca sĩ tối đa 100 ký tự.")
    palette = _color_palette(preset)
    title = escape(title or "KARAOKE STUDIO", quote=True)
    subtitle = escape(subtitle or ("SẴN SÀNG CẤT GIỌNG" if kind == "intro" else "CẢM ƠN ĐÃ LẮNG NGHE"), quote=True)
    # HTML is also served as an iframe preview. Its CSS keyframes act as a
    # no-dependency fallback until npm install is explicitly done by the user.
    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:{palette['bg']};font-family:Inter,Segoe UI,Arial,sans-serif;color:white}}
#root{{position:relative;width:1920px;height:1080px;overflow:hidden;background:radial-gradient(ellipse at 50% 42%,{palette['accent']}25,transparent 48%),{palette['bg']}}}
#glow{{position:absolute;left:360px;top:90px;width:1200px;height:800px;border-radius:50%;background:radial-gradient(ellipse,{palette['accent2']}2b,transparent 70%);filter:blur(40px)}}
#frame{{position:absolute;inset:95px;border:2px solid {palette['accent']}55;border-radius:30px}}
#bar{{position:absolute;width:430px;height:7px;background:linear-gradient(90deg,transparent,{palette['accent']},{palette['accent2']},transparent);left:745px;top:690px;border-radius:100px}}
#title{{font-size:102px;font-weight:850;letter-spacing:-3px;line-height:1.15;text-align:center;color:#fff;text-shadow:0 7px 50px #000d;max-width:1550px;position:absolute;left:185px;top:390px}}
#subtitle{{font-size:29px;font-weight:650;letter-spacing:7px;text-transform:uppercase;text-align:center;color:{palette['accent']};position:absolute;left:185px;top:585px;width:1550px}}
#tag{{position:absolute;left:165px;top:124px;font-size:26px;letter-spacing:9px;color:{palette['accent2']}}}
#brand{{position:absolute;right:155px;bottom:120px;font-size:25px;letter-spacing:7px;color:#ffffff99}}
/* Standalone preview when GSAP hasn't been installed yet. HyperFrames' GSAP
   timeline overrides these visual transforms during deterministic rendering. */
@keyframes entrance{{from{{opacity:0;transform:translateY(35px) scale(.96)}}to{{opacity:1;transform:translateY(0) scale(1)}}}}
#title,#subtitle,#bar{{animation:entrance 1.1s cubic-bezier(.18,.8,.3,1) both}}
#subtitle{{animation-delay:.25s}}#bar{{animation-delay:.5s}}
</style></head>
<body><div id="root" data-composition-id="nvs-motion" data-start="0" data-width="1920" data-height="1080" data-duration="3">
<div id="glow"></div><div id="frame"></div>
<div id="tag">{"INTRO" if kind=="intro" else "OUTRO"} · NVS STUDIO</div>
<h1 id="title" class="clip" data-start="0" data-duration="3" data-track-index="0">{title}</h1>
<p id="subtitle" class="clip" data-start="0" data-duration="3" data-track-index="1">{subtitle}</p>
<div id="bar"></div><div id="brand">NVS · KARAOKE</div>
</div>
<script src="{escape(gsap_path, quote=True)}"></script>
<script>
if (window.gsap) {{
  const tl = gsap.timeline({{paused:true, defaults:{{ease:"power2.out"}}}});
  tl.fromTo("#title",{{opacity:0,y:80,scale:.95}},{{opacity:1,y:0,scale:1,duration:1.05}},0)
    .fromTo("#subtitle",{{opacity:0,y:30}},{{opacity:1,y:0,duration:.85}},.36)
    .fromTo("#bar",{{opacity:0,scaleX:0}},{{opacity:1,scaleX:1,duration:.8}},.7)
    .to(["#title","#subtitle","#bar"],{{opacity:0,y:-20,duration:.5,ease:"power1.in"}},2.45);
  window.__timelines = window.__timelines || {{}};
  window.__timelines["nvs-motion"] = tl;
  if (window.location.search.includes("preview=1")) tl.play();
}}
function fitPreview() {{
  const scale = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
  document.getElementById("root").style.transformOrigin = "top left";
  document.getElementById("root").style.transform = "scale(" + scale + ")";
}}
window.addEventListener("resize", fitPreview);
fitPreview();
</script></body></html>"""



def transition_preview_html(transition: str, *, gsap_path: str = "/api/motion/gsap.js") -> str:
    """Three-second two-panel visualization of the selected FFmpeg xfade mode."""
    if transition not in TRANSITIONS:
        raise ValueError("Hiệu ứng chuyển cảnh không hợp lệ.")
    effect = {
        "fade": "opacity:0",
        "wipeleft": "clip-path:inset(0 0 0 100%)",
        "smoothleft": "transform:translateX(100%)",
    }[transition]
    css_out = {
        "fade": "opacity:1",
        "wipeleft": "clip-path:inset(0 0 0 0)",
        "smoothleft": "transform:translateX(0)",
    }[transition]
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><style>
html,body{{margin:0;width:100%;height:100%;background:#131021;overflow:hidden;font-family:Segoe UI,sans-serif}}
#root{{position:relative;width:1920px;height:1080px;overflow:hidden}}
.scene{{position:absolute;inset:0;display:grid;place-items:center;color:white;font-size:104px;font-weight:800}}
#scene-a{{background:linear-gradient(120deg,#26153f,#6c3cb0)}}
#scene-b{{background:linear-gradient(120deg,#113b3a,#2d88a7);{effect};animation:scene-in 1.6s ease-in-out .7s both}}
@keyframes scene-in{{from{{{effect}}}to{{{css_out}}}}}
</style></head><body><div id="root" data-composition-id="nvs-transition" data-start="0" data-width="1920" data-height="1080" data-duration="3">
<div class="scene clip" id="scene-a" data-start="0" data-duration="3" data-track-index="0">CẢNH A</div>
<div class="scene clip" id="scene-b" data-start="0" data-duration="3" data-track-index="1">CẢNH B</div>
</div><script src="{escape(gsap_path, quote=True)}"></script><script>
if (window.gsap) {{
 const tl = gsap.timeline({{paused:true}});
 const effect={transition!r};
 if(effect==="fade") tl.fromTo("#scene-b",{{opacity:0}},{{opacity:1,duration:1.6}},.7);
 if(effect==="wipeleft") tl.fromTo("#scene-b",{{clipPath:"inset(0 0 0 100%)"}},{{clipPath:"inset(0 0 0 0)",duration:1.6}},.7);
 if(effect==="smoothleft") tl.fromTo("#scene-b",{{x:1920}},{{x:0,duration:1.6}},.7);
 window.__timelines=window.__timelines||{{}};
 window.__timelines["nvs-transition"]=tl;
 if(window.location.search.includes("preview=1"))tl.play();
}}
function resizePreview() {{
 const root=document.getElementById("root");
 root.style.transformOrigin="top left";
 root.style.transform="scale("+Math.min(innerWidth/1920,innerHeight/1080)+")";
}}
window.addEventListener("resize",resizePreview);resizePreview();
</script></body></html>"""


def make_composition(folder: Path, kind: str, preset: str, title: str, subtitle: str) -> Path:
    """Build a HyperFrames project in a temporary, sandboxed local directory."""
    state = installed()
    if not state["installed"]:
        raise RuntimeError("Chưa cài Motion Engine. Cần Node.js 22+ rồi chạy 'npm install' trong thư mục motion_engine.")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    assets = folder / "assets"
    assets.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "node_modules" / "gsap" / "dist" / "gsap.min.js", assets / "gsap.min.js")
    source = folder / "index.html"
    source.write_text(composition_html(kind, preset, title, subtitle), encoding="utf-8")
    (folder / "meta.json").write_text(
        '{"name":"NVS Motion","id":"nvs-motion","version":1}', encoding="utf-8"
    )
    return source


def render_clip(folder: Path, kind: str, preset: str, title: str, subtitle: str) -> Path:
    """Render once through official HyperFrames CLI, with no npx auto-download."""
    make_composition(folder, kind, preset, title, subtitle)
    cli = ROOT / "node_modules" / ".bin" / ("hyperframes.cmd" if os.name == "nt" else "hyperframes")
    output = (Path(folder) / f"{kind}.mp4").resolve()
    # One worker limits memory footprint on GTX 1050 Ti / low-RAM laptops.
    args = [str(cli), "render", "--output", str(output), "--fps", "30",
            "--quality", "draft", "--workers", "1"]
    process = subprocess.run(args, cwd=str(folder), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    if process.returncode or not output.is_file():
        raise RuntimeError("HyperFrames không xuất được clip. Kiểm tra Node.js 22+ và môi trường trình duyệt/FFmpeg: "
                           + (process.stderr or process.stdout or "không có log")[-1800:])
    return output
