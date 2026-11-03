"""R461: HTTP surface for the fallback directory browser.

The settings pane on the Android client has no fnOS host, so it asks the server
for directory listings.  These tests pin the route itself: it answers on
loopback, refuses a missing directory with a readable message, and is not
reachable without the same permission the file-manager routes require.
"""

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, "app/server")

import server


class LibraryDirBrowseHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        os.makedirs(os.path.join(self.root, "Music"), exist_ok=True)
        os.makedirs(os.path.join(self.root, "Media"), exist_ok=True)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.httpd.config = {"server_name": "fnAudio test", "cache_dir": self.root}
        self.httpd.config_path = os.path.join(self.root, "config.json")
        self.httpd.web_root = os.path.abspath("app/ui")
        self.httpd.config["server_port"] = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = "http://127.0.0.1:%s" % self.httpd.server_port

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def get(self, path, headers=None):
        request = urllib.request.Request(self.base_url + path, method="GET", headers=headers or {})
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.loads(response.read() or b"{}")

    @staticmethod
    def internal_headers():
        return {"X-Fnaudio-Internal": "1"}

    def test_lists_child_directories_for_an_allowed_root(self):
        status, payload = self.get(
            "/api/library/dirs?" + urllib.parse.urlencode({"path": self.root}),
            self.internal_headers(),
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(sorted(entry["name"] for entry in payload["entries"]), ["Media", "Music"])
        self.assertFalse(payload["truncated"])

    def test_empty_path_returns_browse_roots(self):
        status, payload = self.get("/api/library/dirs", self.internal_headers())
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["path"], "")
        self.assertEqual(payload["entries"], [])
        self.assertIsInstance(payload["roots"], list)

    def test_missing_directory_is_refused_with_a_message(self):
        status, payload = self.get(
            "/api/library/dirs?" + urllib.parse.urlencode({"path": os.path.join(self.root, "missing")}),
            self.internal_headers(),
        )
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertIn("目录", payload["message"])

    def test_route_is_not_public(self):
        status, payload = self.get("/api/library/dirs")
        self.assertGreaterEqual(status, 400)
        self.assertFalse(payload.get("ok", False))


if __name__ == "__main__":
    unittest.main()
