import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, "app/server")

import server


class HttpIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.media_path = os.path.join(self.temp.name, "fixture.mp3")
        with open(self.media_path, "wb") as handle:
            handle.write(b"0123456789")
        self.item = {
            "id": "fixture",
            "path": self.media_path,
            "title": "Fixture",
            "mime": "audio/mpeg",
            "format": "mp3",
            "is_dsd": False,
            "modified": 1,
        }
        self.patches = [
            mock.patch.object(server, "find_library_item", side_effect=lambda _config, item_id: self.item if item_id == "fixture" else None),
            mock.patch.object(server, "query_library_page", return_value={"items": [self.item], "count": 1, "limit": 10, "offset": 0}),
            mock.patch.object(server, "read_cover_for_item", return_value=("image/jpeg", b"cover")),
        ]
        for patcher in self.patches:
            patcher.start()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.httpd.config = {
            "server_name": "fnAudio test",
            "cache_dir": self.temp.name,
            "ffmpeg_max_concurrency": 1,
        }
        self.httpd.config_path = os.path.join(self.temp.name, "config.json")
        self.httpd.web_root = os.path.abspath("app/ui")
        self.httpd.config["server_port"] = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = "http://127.0.0.1:%s" % self.httpd.server_port

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temp.cleanup()

    def request(self, path, method="GET", headers=None, data=None):
        request = urllib.request.Request(
            self.base_url + path,
            method=method,
            headers=headers or {},
            data=data,
        )
        try:
            response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, dict(response.headers.items()), response.read()

    @staticmethod
    def auth_headers(scope="library.read"):
        return {
            "X-Fnaudio-Trim-Token": "test-token",
            "X-Fnaudio-Scopes": scope,
        }

    def test_health_get_and_head_follow_http_semantics(self):
        status, headers, body = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])
        self.assertTrue(headers.get("X-Request-ID"))

        status, headers, body = self.request("/api/health", method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)

    def test_api_authentication_is_enforced_by_the_real_handler(self):
        self.assertEqual(self.request("/api/library")[0], 401)
        self.assertEqual(self.request("/api/library", headers=self.auth_headers("playback.read"))[0], 403)
        status, _headers, body = self.request("/api/library", headers=self.auth_headers())
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["items"][0]["id"], "fixture")

    def test_internal_cgi_can_save_manual_library_paths_without_fnos_token(self):
        music = os.path.join(self.temp.name, "music")
        os.makedirs(music)
        body = json.dumps({"library_path": music, "server_port": self.httpd.server_port}).encode("utf-8")
        status, _headers, response = self.request(
            "/api/config/library",
            method="POST",
            headers={"Content-Type": "application/json", "X-Fnaudio-Internal": "1"},
            data=body,
        )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(response)["ok"])
        self.assertEqual(
            [os.path.normcase(os.path.normpath(path)) for path in self.httpd.config["library_paths"]],
            [os.path.normcase(os.path.normpath(music))],
        )
        self.assertEqual(self.httpd.config["server_port"], self.httpd.server_port)

    def test_private_media_requires_auth_and_supports_byte_ranges(self):
        self.assertEqual(self.request("/media/fixture")[0], 401)
        headers = {**self.auth_headers(), "Range": "bytes=2-5"}
        status, response_headers, body = self.request("/media/fixture", headers=headers)
        self.assertEqual(status, 206)
        self.assertEqual(response_headers["Content-Range"], "bytes 2-5/10")
        self.assertEqual(body, b"2345")

        status, response_headers, body = self.request("/media/fixture", method="HEAD", headers=self.auth_headers())
        self.assertEqual(status, 200)
        self.assertEqual(response_headers["Content-Length"], "10")
        self.assertEqual(body, b"")

    def test_invalid_range_returns_standard_unsatisfied_range(self):
        headers = {**self.auth_headers(), "Range": "bytes=20-30"}
        status, response_headers, body = self.request("/media/fixture", headers=headers)
        self.assertEqual(status, 416)
        self.assertEqual(response_headers["Content-Range"], "bytes */10")
        self.assertEqual(body, b"")

    def test_upnp_media_remains_credential_free_for_renderers(self):
        status, headers, body = self.request("/upnp/media/fixture/fixture.mp3")
        self.assertEqual(status, 200)
        self.assertEqual(headers["transferMode.dlna.org"], "Streaming")
        self.assertEqual(body, b"0123456789")

    def test_cover_is_private_and_honors_etag(self):
        self.assertEqual(self.request("/cover/fixture")[0], 401)
        status, headers, body = self.request("/cover/fixture", headers=self.auth_headers())
        self.assertEqual(status, 200)
        self.assertEqual(body, b"cover")
        status, _headers, body = self.request(
            "/cover/fixture",
            headers={**self.auth_headers(), "If-None-Match": headers["ETag"]},
        )
        self.assertEqual(status, 304)
        self.assertEqual(body, b"")

    def test_cover_thumbnail_uses_long_lived_cache_headers(self):
        with mock.patch.object(server, "cached_thumbnail_for_item", return_value=("image/jpeg", b"thumb")) as thumbnail:
            status, headers, body = self.request("/cover/fixture?size=160", headers=self.auth_headers())
        self.assertEqual(status, 200)
        self.assertEqual(body, b"thumb")
        self.assertIn("immutable", headers["Cache-Control"])
        thumbnail.assert_called_once()

    def test_post_body_limit_is_enforced_before_json_parsing(self):
        headers = {**self.auth_headers("playback.control"), "Content-Type": "application/json"}
        status, _headers, body = self.request(
            "/api/playback/control",
            method="POST",
            headers=headers,
            data=b"x" * (2 * 1024 * 1024 + 1),
        )
        self.assertEqual(status, 413)
        self.assertIn(b"too large", body)

    def test_post_failure_uses_the_private_structured_log(self):
        headers = {**self.auth_headers("playback.control"), "Content-Type": "application/json"}
        with mock.patch.object(server, "playback_control_idempotent", side_effect=RuntimeError("test failure")), \
             mock.patch.object(server.OBSERVABILITY, "write") as write_log:
            status, _headers, body = self.request(
                "/api/playback/control",
                method="POST",
                headers=headers,
                data=b'{"action":"play"}',
            )
        self.assertEqual(status, 500)
        self.assertIn(b"test failure", body)
        self.assertTrue(any(call.args[1] == "http_post_error" for call in write_log.call_args_list))


if __name__ == "__main__":
    unittest.main()
