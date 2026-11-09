"""Background source/search/download regressions; network calls are deterministic."""
from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

from local_studio import backgrounds as media


class Response(BytesIO):
    def __init__(self, body=b"video bytes", headers=None):
        super().__init__(body)
        self.headers = headers or {}


class SearchTests(unittest.TestCase):
    def test_commons_prefers_small_derivative_and_retains_plain_attribution(self):
        payload = {"query": {"pages": {"42": {"pageid": 42, "title": "File:Rain.webm", "index": 1, "videoinfo": [{
            "mime": "video/webm", "url": "https://upload.wikimedia.org/rain.webm", "width": 3840, "height": 2160, "size": 640_000_000,
            "duration": 20, "descriptionurl": "https://commons.wikimedia.org/wiki/File:Rain.webm",
            "thumburl": "https://thumb.wikimedia.org/rain.jpg",
            "derivatives": [
                {"src": "https://upload.wikimedia.org/rain.480p.webm", "width": 854, "height": 480},
                {"src": "https://upload.wikimedia.org/rain.720p.webm", "width": 1280, "height": 720},
            ], "extmetadata": {
                "Artist": {"value": '<a href="/wiki/User:Writer">Writer &amp; Artist</a><script>hidden()</script>'},
                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                "LicenseUrl": {"value": "http://creativecommons.org/licenses/by-sa/4.0/"},
            },
        }]}}}}
        with patch.object(media, "_json_request", return_value=payload) as request:
            results = media.search_online("rain", limit=1)
        self.assertEqual(len(results), 1)
        asset = results[0]
        self.assertEqual(asset["id"], "commons:42")
        self.assertEqual(asset["download_url"], "https://upload.wikimedia.org/rain.720p.webm")
        self.assertEqual(asset["author"], "Writer & Artist")
        self.assertEqual(asset["license"], "CC BY-SA 4.0")
        self.assertTrue(asset["license_url"].startswith("https://"))
        self.assertIn("videoinfo", request.call_args.args[0])

    def test_pexels_requires_key_and_uses_official_api(self):
        with self.assertRaisesRegex(ValueError, "API key"):
            media.search_online("rain", provider="pexels")
        payload = {"videos": [{"id": 12, "url": "https://www.pexels.com/video/12/", "duration": 5,
                   "image": "https://images.pexels.com/12.jpg", "user": {"name": "Camera Person"}, "video_files": [
                       {"link": "https://videos.pexels.com/12-4k.mp4", "width": 3840, "height": 2160},
                       {"link": "https://videos.pexels.com/12-hd.mp4", "width": 1280, "height": 720},
                   ]}]}
        with patch.object(media, "_json_request", return_value=payload) as request:
            results = media.search_online("rain", provider="pexels", api_key="private-key", limit=1)
        self.assertTrue(request.call_args.args[0].startswith("https://api.pexels.com/videos/search?"))
        self.assertEqual(request.call_args.kwargs["api_key"], "private-key")
        self.assertEqual(results[0]["download_url"], "https://videos.pexels.com/12-hd.mp4")
        self.assertEqual(results[0]["license"], "Pexels License")
        self.assertNotIn("private-key", str(results))

    def test_api_key_is_never_sent_to_another_host(self):
        with patch.object(media, "_opener") as opener:
            with self.assertRaises(ValueError):
                media._json_request("https://attacker.example/api", api_key="secret")
            opener.assert_not_called()

    def test_invalid_and_unlicensed_results_are_filtered(self):
        payload = {"query": {"pages": {"1": {"pageid": 1, "videoinfo": [{"mime": "video/mp4", "url": "https://attacker.example/file.mp4"}]}}}}
        with patch.object(media, "_json_request", return_value=payload):
            self.assertEqual(media.search_online("rain"), [])
        for query in ["", " " * 3, "x" * 161]:
            with self.assertRaises(ValueError):
                media.search_online(query)
        with self.assertRaises(ValueError):
            media.search_online("rain", provider="arbitrary")


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="karaoke-background-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.previous = self.root / "background.mp4"
        self.previous.write_bytes(b"previous background")
        self.asset = {"provider": "pexels", "title": "Rain", "download_url": "https://videos.pexels.com/rain.mp4",
                      "source_url": "https://www.pexels.com/video/123/", "author": "Camera Person",
                      "license": "Pexels License", "license_url": "https://www.pexels.com/license/"}

    def assert_no_partial(self):
        self.assertFalse(list(self.root.glob(".background-*")))

    def test_valid_download_is_inspected_then_atomically_replaced(self):
        opener = Mock()
        opener.open.return_value = Response(b"valid video")
        with patch.object(media, "_opener", return_value=opener), patch.object(media, "probe", return_value={"streams": [{"codec_type": "video"}]}) as probe:
            result = media.fetch_background(self.asset, self.root)
        self.assertEqual(self.previous.read_bytes(), b"valid video")
        self.assertEqual(result["filename"], "background.mp4")
        self.assertEqual(result["attribution"]["author"], "Camera Person")
        self.assertEqual(result["attribution"]["source_url"], self.asset["source_url"])
        probe.assert_called_once()
        self.assert_no_partial()

    def test_nonvideo_download_preserves_existing_background(self):
        opener = Mock()
        opener.open.return_value = Response(b"audio only")
        with patch.object(media, "_opener", return_value=opener), patch.object(media, "probe", return_value={"streams": [{"codec_type": "audio"}]}):
            with self.assertRaisesRegex(ValueError, "video"):
                media.fetch_background(self.asset, self.root)
        self.assertEqual(self.previous.read_bytes(), b"previous background")
        self.assert_no_partial()

    def test_size_limit_rejects_header_and_stream_overflow_without_replacing(self):
        for response in [Response(b"x", {"Content-Length": "99"}), Response(b"too much data")]:
            with self.subTest(response=response), patch.object(media, "MAX_DOWNLOAD_BYTES", 4), patch.object(media, "_opener") as factory:
                factory.return_value.open.return_value = response
                with self.assertRaisesRegex(ValueError, "200 MB"):
                    media.fetch_background(self.asset, self.root)
                self.assertEqual(self.previous.read_bytes(), b"previous background")
                self.assert_no_partial()

    def test_untrusted_initial_url_and_redirect_are_rejected(self):
        for url in ["http://videos.pexels.com/rain.mp4", "https://127.0.0.1/rain.mp4", "https://videos.pexels.com.attacker.example/rain.mp4", "https://videos.pexels.com:8443/rain.mp4", "https://user:pass@videos.pexels.com/rain.mp4"]:
            with self.subTest(url=url), patch.object(media, "_opener") as factory:
                with self.assertRaises(ValueError):
                    media.fetch_background({**self.asset, "download_url": url}, self.root)
                factory.assert_not_called()
        redirect = urllib.error.HTTPError(self.asset["download_url"], 302, "redirect", {"Location": "https://127.0.0.1/private.mp4"}, None)
        with patch.object(media, "_opener") as factory:
            factory.return_value.open.side_effect = redirect
            with self.assertRaises(ValueError):
                media.fetch_background(self.asset, self.root)
            self.assertEqual(factory.return_value.open.call_count, 1)
        self.assertEqual(self.previous.read_bytes(), b"previous background")
        self.assert_no_partial()

    def test_safe_provider_redirect_is_followed_and_revalidated(self):
        redirect = urllib.error.HTTPError(self.asset["download_url"], 302, "redirect", {"Location": "/new-rain.mp4"}, None)
        with patch.object(media, "_opener") as factory, patch.object(media, "probe", return_value={"streams": [{"codec_type": "video"}]}):
            factory.return_value.open.side_effect = [redirect, Response(b"new video")]
            media.fetch_background(self.asset, self.root)
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, "https://videos.pexels.com/new-rain.mp4")
            self.assertIsNone(request.get_header("Authorization"))


class LocalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="karaoke-local-videos-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_folder_scan_is_sorted_bounded_and_does_not_escape_symlinks(self):
        folder = self.root / "videos"
        folder.mkdir()
        (folder / "b.mp4").write_bytes(b"b")
        (folder / "a.MP4").write_bytes(b"a")
        (folder / "not-a-video.txt").write_bytes(b"x")
        child = folder / "child"
        child.mkdir()
        (child / "c.webm").write_bytes(b"c")
        outside = self.root / "outside.mp4"
        outside.write_bytes(b"private")
        try:
            (folder / "escape.mp4").symlink_to(outside)
        except OSError:
            pass  # Windows runners may not grant symlink privileges.
        files = media.list_local(str(folder))
        self.assertEqual([entry["title"] for entry in files], ["a.MP4", "b.mp4"])
        self.assertEqual(len(media.list_local(str(folder), recursive=True)), 3)
        self.assertEqual(len(media.list_local(str(folder), limit=1)), 1)
        self.assertTrue(all(Path(entry["path"]).is_absolute() for entry in files))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_real_local_video_copy_and_media_validation(self):
        folder = self.root / "nguồn có dấu"
        folder.mkdir()
        video = folder / "mưa.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x120:d=0.2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True)
        asset = media.list_local(str(folder))[0]
        output = self.root / "project"
        result = media.fetch_background(asset, output)
        self.assertEqual((output / result["filename"]).read_bytes(), video.read_bytes())
        self.assertEqual(result["attribution"]["provider"], "local")
        self.assertFalse(list(output.glob(".background-*")))


if __name__ == "__main__":
    unittest.main()
