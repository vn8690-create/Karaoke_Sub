"""No-download Motion Engine regression tests.

Render-off path never loads third-party code. GSAP/HyperFrames are optional
and must be installed explicitly to enable optional motion composition.
"""
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch, SimpleNamespace

from fastapi.testclient import TestClient
from local_studio.app import app
from motion_engine import core
from motion_engine.compositor import compose_argv


class CompositionTests(unittest.TestCase):
    def test_all_preset_compositions_are_escaped_and_seek_driven(self):
        for kind in ("intro", "outro"):
            for preset in core.PRESETS:
                with self.subTest(kind=kind, preset=preset):
                    html = core.composition_html(
                        kind, preset, '<script>alert("x")</script>', 'Nghệ sĩ & bạn')
                    self.assertIn("&lt;script&gt;", html)
                    self.assertNotIn('<script>alert("x")', html)
                    self.assertIn('Nghệ sĩ &amp; bạn', html)
                    self.assertIn("data-composition-id=", html)
                    self.assertIn('class="clip"', html)
                    self.assertIn("gsap.timeline({paused:true", html.replace(" ", ""))
                    self.assertIn('window.__timelines["nvs-motion"]', html)
                    self.assertIn("data-width=\"1920\"", html)

    def test_transition_previews_have_registered_paused_gsap_timeline(self):
        for kind in core.TRANSITIONS:
            with self.subTest(kind=kind):
                preview = core.transition_preview_html(kind)
                self.assertIn("data-composition-id=\"nvs-transition\"", preview)
                self.assertIn("gsap.timeline({paused:true})", preview)
                self.assertIn("window.__timelines", preview)
        with self.assertRaises(ValueError):
            core.transition_preview_html("fade;rm -rf /")
        with self.assertRaises(ValueError):
            core.composition_html("intro", "invalid", "A")
        with self.assertRaises(ValueError):
            core.composition_html("bad", "neon", "A")
        with self.assertRaises(ValueError):
            core.composition_html("intro", "neon", "X" * 101)

    def test_generate_local_project_without_network_or_untrusted_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            gsap = root / "node_modules" / "gsap" / "dist" / "gsap.min.js"
            gsap.parent.mkdir(parents=True)
            gsap.write_text("window.gsap={};", encoding="utf-8")
            with patch.object(core, "ROOT", root), patch.object(core, "installed", return_value={"installed": True}):
                html = core.make_composition(root / "composition", "intro", "neon", "A&B", "<OK>")
            self.assertTrue(html.is_file())
            self.assertTrue((html.parent / "assets" / "gsap.min.js").is_file())
            self.assertIn("&lt;OK&gt;", html.read_text("utf-8"))
            self.assertIn("gsap.min.js", html.read_text("utf-8"))

    def test_render_clip_uses_only_local_executable_and_one_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            gsap = root / "node_modules" / "gsap" / "dist" / "gsap.min.js"
            gsap.parent.mkdir(parents=True)
            gsap.write_text("window.gsap={};", encoding="utf-8")
            def fake_run(args, **kwargs):
                self.assertEqual(args[1], "render")
                self.assertEqual(args[-2:], ["--workers", "1"])
                self.assertNotIn("npx", args[0])
                (Path(kwargs["cwd"]) / "intro.mp4").write_bytes(b"mock-video")
                return SimpleNamespace(returncode=0, stderr="", stdout="")
            with patch.object(core, "ROOT", root), patch.object(core, "installed", return_value={"installed": True}), patch.object(core.subprocess, "run", side_effect=fake_run):
                clip = core.render_clip(root / "project", "intro", "minimal", "Xin chào", "Karaoke")
            self.assertEqual(clip.read_bytes(), b"mock-video")

    def test_compositor_crossfade_offsets_audio_and_total_are_consistent(self):
        song = Path("song.mp4")
        intro = Path("intro.mp4")
        outro = Path("outro.mp4")
        out = Path("out.mp4")
        both, duration = compose_argv(song, intro, outro, out, 60.0, (1280, 720), True, "fade")
        joined = " ".join(both)
        self.assertAlmostEqual(duration, 64.9)
        self.assertIn("offset=2.450", joined)
        self.assertIn("offset=61.900", joined)
        self.assertIn("adelay=2450:all=1", joined)
        self.assertIn("xfade=transition=fade", joined)
        just_outro, duration = compose_argv(song, None, outro, out, 60, (1280, 720), True, "wipeleft")
        self.assertAlmostEqual(duration, 62.45)
        self.assertIn("offset=59.450", " ".join(just_outro))
        self.assertIn("adelay=0:all=1", " ".join(just_outro))
        with self.assertRaises(ValueError):
            compose_argv(song, None, None, out, 60, (1280, 720), True, "fade")
        with self.assertRaises(ValueError):
            compose_argv(song, intro, outro, out, 60, (1280, 720), True, "unsafe")


class MotionApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_catalog_and_html_preview_without_install(self):
        result = self.client.get("/api/motion/presets")
        self.assertEqual(result.status_code, 200, result.text)
        body = result.json()
        self.assertEqual(len(body["presets"]), 4)
        self.assertEqual(len(body["transitions"]), 3)
        self.assertIn("installed", body["engine"])
        preview = self.client.get("/api/motion/preview", params={
            "kind": "intro", "preset": "neon",
            "title": '<img src=x onerror=alert(1)>',
        })
        self.assertEqual(preview.status_code, 200)
        self.assertNotIn('<img src=x', preview.text)
        self.assertIn("&lt;img", preview.text)
        self.assertIn("frame-ancestors 'self'", preview.headers["content-security-policy"])
        transition = self.client.get("/api/motion/preview", params={
            "kind": "transition", "transition": "smoothleft",
        })
        self.assertEqual(transition.status_code, 200, transition.text)
        self.assertIn("nvs-transition", transition.text)
        self.assertEqual(self.client.get("/api/motion/preview", params={"kind": "evil"}).status_code, 422)
        self.assertEqual(self.client.get("/api/motion/preview", params={"title": "x" * 101}).status_code, 422)

    def test_render_schema_does_not_change_existing_default(self):
        from local_studio.app import Render
        defaults = Render(audio_mode="original")
        self.assertEqual((defaults.motion_intro, defaults.motion_outro), ("none", "none"))
        self.assertEqual(defaults.motion_transition, "fade")
        custom = Render(audio_mode="original", motion_intro="neon", motion_outro="retro",
                        motion_transition="wipeleft", motion_title="Xin chào")
        self.assertEqual(custom.motion_title, "Xin chào")
        with self.assertRaises(Exception):
            Render(audio_mode="original", motion_transition="command-injection")
        with self.assertRaises(Exception):
            Render(audio_mode="original", motion_title="X"*101)


if __name__ == "__main__":
    unittest.main()
