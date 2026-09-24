import json
import io
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, "app/server")

import cover_cache
import server
from http_request_policy import MAX_REQUEST_TARGET
from metadata_local_lyrics_cache import (
    CONFIG_BYTES_KEY,
    DEFAULT_MAX_BYTES,
    MAX_MAX_BYTES,
    MIN_MAX_BYTES,
    LocalLyricsCache,
    bytes_limit_from_config,
)


class RuntimeLyricsService:
    """Stand in for the metadata service with two real lyric cache lanes.

    The runtime pane promises the budget the process enforces, so the stub has
    to enforce it too: an object that only remembered the number it was handed
    would let a handler that reads the config file back look correct.
    """

    def __init__(self, lanes=None):
        self.applied = []
        self.lanes = lanes if lanes is not None else [
            LocalLyricsCache(lambda path: "l" * 600),
            LocalLyricsCache(lambda path: "l" * 600),
        ]

    def apply_lyrics_cache_config(self, config):
        self.applied.append(dict(config))
        limit = bytes_limit_from_config(config)
        for lane in self.lanes:
            lane.apply_bytes_limit(limit)
        return limit

    def lyrics_cache_bytes_limit(self):
        return min(lane.snapshot()["bytes_limit"] for lane in self.lanes)


class HttpIntegrationTests(unittest.TestCase):
    def test_request_body_reader_requires_the_declared_length(self):
        class ShortStream:
            def __init__(self):
                self.parts = [b'{"action":"stop"}', b""]

            def read(self, _size):
                return self.parts.pop(0)

        self.assertIsNone(server.read_complete_request_body(ShortStream(), 20))

        class ChunkedStream:
            def __init__(self):
                self.parts = [b"abc", bytearray(b"def")]

            def read(self, _size):
                return self.parts.pop(0)

        self.assertEqual(server.read_complete_request_body(ChunkedStream(), 6, chunk_size=3), b"abcdef")

    def test_send_xml_ignores_client_disconnect_after_headers(self):
        class DisconnectingBuffer(io.BytesIO):
            def write(self, value):
                raise OSError("client transport closed")

        handler = object.__new__(server.Handler)
        handler.send_response = lambda status: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler.wfile = DisconnectingBuffer()

        handler.send_xml("<root/>")

    def test_json_and_xml_responses_ignore_closed_writer_value_error(self):
        class ClosedWriter(io.BytesIO):
            def write(self, value):
                raise ValueError("I/O operation on closed file")

        handler = object.__new__(server.Handler)
        handler.send_response = lambda status: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler.current_request_id = lambda: "test-request"
        handler.command = "GET"
        handler.path = "/api/health"
        handler.wfile = ClosedWriter()

        handler.send_json({"ok": True})
        handler.send_xml("<root/>")

    def test_dlna_subscription_rejects_oversized_target_and_unconsumed_body(self):
        handler = object.__new__(server.Handler)
        errors = []
        handler.send_error = lambda status, message: errors.append((status, message))
        handler.close_connection = False
        handler.headers = {}
        handler.path = "/" + ("x" * (MAX_REQUEST_TARGET + 1))

        handler.handle_dlna_subscription()

        self.assertEqual(errors, [(414, "Request target too long")])
        self.assertTrue(handler.close_connection)

        errors.clear()
        handler.close_connection = False
        handler.path = "/dlna/renderer/avtransport/event"
        handler.headers = {"Content-Length": "1"}

        handler.handle_dlna_subscription()

        self.assertEqual(errors, [(400, "DLNA subscriptions do not accept request bodies")])
        self.assertTrue(handler.close_connection)

    def test_send_json_emits_normalized_extra_headers(self):
        headers = []
        handler = object.__new__(server.Handler)
        handler.send_response = lambda status: None
        handler.send_header = lambda name, value: headers.append((name, value))
        handler.end_headers = lambda: None
        handler.current_request_id = lambda: "test-request"
        handler.command = "HEAD"
        handler.path = "/legacy/play"
        handler.wfile = io.BytesIO()

        handler.send_json({"ok": True}, extra_headers={" X-Test ": " enabled "})

        self.assertIn(("X-Test", "enabled"), headers)

    def test_cover_responses_ignore_client_disconnect_after_headers(self):
        class DisconnectingBuffer(io.BytesIO):
            def write(self, value):
                raise OSError("client transport closed")

        handler = object.__new__(server.Handler)
        handler.send_response = lambda status: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler.wfile = DisconnectingBuffer()

        with mock.patch.object(server, "find_library_item", return_value={"id": "1", "path": "x"}), \
             mock.patch.object(server, "cached_cover_for_item", return_value=("image/jpeg", b"cover")):
            handler.headers = {}
            handler.server = mock.Mock(config={})
            handler.serve_cover("1")

        with mock.patch.object(server, "thumbnail_asset_bytes", return_value=("image/jpeg", b"asset")):
            handler.serve_cover_asset("asset")

    def test_metadata_artwork_stream_keeps_connection_reusable_after_complete_body(self):
        with tempfile.TemporaryDirectory() as root:
            artwork_path = os.path.join(root, "metadata.jpg")
            with open(artwork_path, "wb") as handle:
                handle.write(b"metadata-cover")

            class ArtworkService:
                def artwork(self, _asset_id):
                    return {"path": artwork_path, "mime": "image/jpeg"}

            handler = object.__new__(server.Handler)
            handler.send_response = lambda status: None
            handler.send_header = lambda name, value: None
            handler.end_headers = lambda: None
            handler.headers = {}
            handler.wfile = io.BytesIO()
            handler.close_connection = False
            previous = server.METADATA_SERVICE
            server.METADATA_SERVICE = ArtworkService()
            try:
                handler.serve_metadata_artwork("a" * 64)
            finally:
                server.METADATA_SERVICE = previous

            self.assertEqual(handler.wfile.getvalue(), b"metadata-cover")
            self.assertFalse(handler.close_connection)

    def test_cached_cover_rejects_non_mapping_items_without_stringifying(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("cover cache must not stringify arbitrary items")

        self.assertEqual(server.cached_cover_for_item(Explosive(), {}), (None, None))

    def test_cached_cover_isolates_broken_mapping_fields_and_bounds_path(self):
        class BrokenMapping(dict):
            def get(self, key, default=None):
                raise RuntimeError("field unavailable")

        self.assertEqual(server.cached_cover_for_item(BrokenMapping(), {}), (None, None))
        with mock.patch.object(server, "read_cover_for_item", return_value=(None, None)) as reader:
            with server.COVER_CACHE_LOCK:
                server.COVER_CACHE.clear()
            item = {"path": "p" * (server.COVER_CACHE_MAX_PATH_CHARS + 200), "modified": 1}
            self.assertEqual(server.cached_cover_for_item(item, {}), (None, None))
            self.assertEqual(len(reader.call_args.args[0]["path"]), server.COVER_CACHE_MAX_PATH_CHARS + 200)
            key = next(iter(server.COVER_CACHE))
            self.assertEqual(len(key[0]), server.COVER_CACHE_MAX_PATH_CHARS)

    def test_cached_cover_uses_lru_order_for_hot_items(self):
        with mock.patch.object(server, "read_cover_for_item", side_effect=lambda item, config: ("image/jpeg", item["path"].encode())):
            with server.COVER_CACHE_LOCK:
                server.COVER_CACHE.clear()
            original_limit = server.COVER_CACHE_MAX_ENTRIES
            server.COVER_CACHE_MAX_ENTRIES = 2
            try:
                first = {"path": "first", "modified": 1}
                second = {"path": "second", "modified": 1}
                third = {"path": "third", "modified": 1}
                server.cached_cover_for_item(first, {})
                server.cached_cover_for_item(second, {})
                server.cached_cover_for_item(first, {})
                server.cached_cover_for_item(third, {})
                keys = [key[0] for key in server.COVER_CACHE]
                self.assertEqual(keys, ["first", "third"])
            finally:
                server.COVER_CACHE_MAX_ENTRIES = original_limit

    def test_cached_cover_coalesces_concurrent_misses_for_the_same_item(self):
        item = {"path": "same", "modified": 1}
        started = threading.Event()
        release = threading.Event()
        results = []

        def reader(_item, _config):
            started.set()
            self.assertTrue(release.wait(2))
            return ("image/jpeg", b"cover")

        with server.COVER_CACHE_LOCK:
            server.COVER_CACHE.clear()
            server.COVER_CACHE_INFLIGHT.clear()
        with mock.patch.object(server, "read_cover_for_item", side_effect=reader) as mocked:
            first = threading.Thread(target=lambda: results.append(server.cached_cover_for_item(item, {})))
            second = threading.Thread(target=lambda: results.append(server.cached_cover_for_item(item, {})))
            first.start()
            self.assertTrue(started.wait(1))
            second.start()
            time.sleep(0.05)
            release.set()
            first.join(2)
            second.join(2)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(results, [("image/jpeg", b"cover"), ("image/jpeg", b"cover")])
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
        health = json.loads(body)
        self.assertTrue(health["ok"])
        self.assertIn("query_cache", health["components"]["library"])
        self.assertIn("search_index", health["components"]["library"])
        self.assertTrue(headers.get("X-Request-ID"))

        status, headers, body = self.request("/api/health", method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)
        self.assertIn("no-store", headers.get("Cache-Control", ""))

    def test_static_asset_is_rejected_before_unbounded_read(self):
        target = os.path.join(self.temp.name, "oversized.bin")
        with open(target, "wb") as handle:
            handle.truncate(16 * 1024 * 1024 + 1)
        previous_root = self.httpd.web_root
        self.httpd.web_root = self.temp.name
        try:
            status, _headers, body = self.request("/oversized.bin")
        finally:
            self.httpd.web_root = previous_root
        self.assertEqual(status, 413)
        self.assertIn(b"Static asset exceeds size limit", body)

    def test_versioned_static_asset_honors_etag_without_blocking_deploys(self):
        status, headers, body = self.request("/app.css?v=test-build")
        self.assertEqual(status, 200)
        self.assertTrue(body)
        self.assertIn("immutable", headers["Cache-Control"])
        self.assertIn("ETag", headers)

        status, headers_304, body = self.request(
            "/app.css?v=test-build", headers={"If-None-Match": headers["ETag"]}
        )
        self.assertEqual(status, 304)
        self.assertEqual(body, b"")
        self.assertEqual(headers_304["ETag"], headers["ETag"])
        self.assertIn("immutable", headers_304["Cache-Control"])

        status, html_headers, _body = self.request("/index.html")
        self.assertEqual(status, 200)
        self.assertEqual(html_headers["Cache-Control"], "no-cache")

    def test_static_asset_rejects_windows_separator_traversal(self):
        outside = os.path.join(self.temp.name, "outside.txt")
        with open(outside, "wb") as handle:
            handle.write(b"must not be served")
        previous_root = self.httpd.web_root
        self.httpd.web_root = os.path.join(self.temp.name, "web")
        os.makedirs(self.httpd.web_root)
        try:
            status, _headers, _body = self.request("/%5c%5c..%5coutside.txt")
        finally:
            self.httpd.web_root = previous_root
        self.assertEqual(status, 400)

    def test_static_asset_rejects_symlink_outside_web_root(self):
        outside = os.path.join(self.temp.name, "outside-secret.txt")
        with open(outside, "wb") as handle:
            handle.write(b"must not be served")
        web_root = os.path.join(self.temp.name, "symlink-web")
        os.makedirs(web_root)
        link = os.path.join(web_root, "secret.txt")
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("symlinks are unavailable: %s" % exc)
        previous_root = self.httpd.web_root
        self.httpd.web_root = web_root
        try:
            status, _headers, _body = self.request("/secret.txt")
        finally:
            self.httpd.web_root = previous_root
        self.assertEqual(status, 400)

    def test_api_authentication_is_enforced_by_the_real_handler(self):
        self.assertEqual(self.request("/api/library")[0], 401)
        self.assertEqual(self.request("/api/library", headers=self.auth_headers("playback.read"))[0], 403)
        status, _headers, body = self.request("/api/library", headers=self.auth_headers())
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["items"][0]["id"], "fixture")

    def test_json_object_shape_is_required_for_api_posts(self):
        status, _headers, body = self.request(
            "/api/playback/target",
            method="POST",
            headers={**self.auth_headers("playback.control"), "Content-Type": "application/json"},
            data=b"[]",
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"], "invalid payload")

    def test_invalid_target_and_library_path_types_do_not_mutate_runtime_state(self):
        status, _headers, _body = self.request(
            "/api/playback/target",
            method="POST",
            headers={**self.auth_headers("playback.control"), "Content-Type": "application/json"},
            data=json.dumps({"target_id": ["mpd:unexpected"]}).encode(),
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(_body)["error"], "target_id must be text")
        status, _headers, body = self.request(
            "/api/config/library",
            method="POST",
            headers={**self.auth_headers("settings.write"), "Content-Type": "application/json"},
            data=b'{"library_path":[]}',
        )
        self.assertEqual(status, 400)
        self.assertIn("文本", json.loads(body)["message"])

    def test_library_path_config_bounds_candidates_before_filesystem_checks(self):
        paths = ["/missing-%d" % index for index in range(server.MAX_LIBRARY_PATHS)]
        paths.append(os.path.join(self.temp.name, "music-after-limit"))
        os.makedirs(paths[-1])
        with mock.patch.object(server.os.path, "isdir", wraps=server.os.path.isdir) as isdir:
            status, _headers, body = self.request(
                "/api/config/library",
                method="POST",
                headers={**self.auth_headers("settings.write"), "Content-Type": "application/json"},
                data=json.dumps({"library_path": "\n".join(paths)}).encode(),
            )
        self.assertEqual(status, 400)
        self.assertIn("不能作为音乐目录", json.loads(body)["message"])
        checked = [call.args[0] for call in isdir.call_args_list]
        self.assertNotIn(paths[-1], checked)

    def test_library_path_config_does_not_let_blank_entries_consume_valid_slots(self):
        music = os.path.join(self.temp.name, "music-with-blanks")
        os.makedirs(music)
        raw = ("\n;\r\n" * server.MAX_LIBRARY_PATHS) + music
        status, _headers, body = self.request(
            "/api/config/library",
            method="POST",
            headers={**self.auth_headers("settings.write"), "Content-Type": "application/json"},
            data=json.dumps({"library_path": raw}).encode(),
        )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])
        self.assertEqual(len(self.httpd.config["library_paths"]), 1)

    def test_offline_renderer_target_selection_does_not_mutate_core(self):
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"target_id": "mpd:active", "target_kind": "mpd"}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server, "find_upnp_device", return_value=None
        ):
            status, _headers, body = self.request(
                "/api/playback/target",
                method="POST",
                headers={**self.auth_headers("playback.control"), "Content-Type": "application/json"},
                data=b'{"target_id":"uuid:offline-renderer"}',
            )

        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"], "playback_target_not_found")
        fake_core.set_target.assert_not_called()

    def test_target_persistence_failure_restores_previous_core_target(self):
        fake_core = mock.Mock()
        fake_core.snapshot.return_value = {"target_id": "local", "target_kind": "browser"}
        with mock.patch.object(server, "PLAYBACK_CORE", fake_core), mock.patch.object(
            server, "playback_target_kind", return_value="mpd"
        ), mock.patch.object(server, "save_playback_target_session", return_value=None):
            status, _headers, body = self.request(
                "/api/playback/target",
                method="POST",
                headers={**self.auth_headers("playback.control"), "Content-Type": "application/json"},
                data=b'{"target_id":"mpd:test"}',
            )
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)["error"], "playback_state_persistence_failed")
        fake_core.set_target.assert_not_called()

    def test_metadata_apply_rejects_fractional_candidate_index(self):
        previous = server.METADATA_SERVICE

        class Metadata:
            def apply_track_match(self, _track_id, _candidate_index):
                raise AssertionError("invalid candidate index must be rejected at the HTTP boundary")

        server.METADATA_SERVICE = Metadata()
        try:
            status, _headers, body = self.request(
                "/api/metadata/track/apply",
                method="POST",
                headers={**self.auth_headers("settings.write"), "Content-Type": "application/json"},
                data=b'{"track_id":"fixture","candidate_index":1.5}',
            )
        finally:
            server.METADATA_SERVICE = previous
        self.assertEqual(status, 400)
        self.assertIn("non-negative integer", json.loads(body)["message"])

    def test_transfer_encoding_is_rejected_before_body_parsing(self):
        status, _headers, body = self.request(
            "/api/playback/target",
            method="POST",
            headers={**self.auth_headers("playback.control"), "Transfer-Encoding": "chunked", "Content-Length": "1"},
            data=b"0\r\n\r\n",
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"], "transfer encoding is unsupported")

    def test_invalid_utf8_request_body_returns_bad_request(self):
        status, _headers, body = self.request(
            "/api/playback/target",
            method="POST",
            headers={**self.auth_headers("playback.control"), "Content-Type": "application/json"},
            data=b"{\xff}",
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"], "invalid json")

    def test_library_item_hydration_rejects_unbounded_id_lists_before_sqlite(self):
        ids = ",".join("id-%s" % index for index in range(121))
        status, _headers, body = self.request("/api/library/items?ids=" + ids, headers=self.auth_headers())
        self.assertEqual(status, 400)
        self.assertIn("at most 120", json.loads(body)["error"])

    def test_library_item_hydration_reuses_metadata_projection(self):
        class Projection:
            def enrich_track_page(self, page):
                item = dict(page["items"][0])
                item["album"] = "Cached Album"
                return {"items": [item]}

        previous = server.METADATA_SERVICE
        server.METADATA_SERVICE = Projection()
        try:
            with mock.patch.object(server, "query_library_items_by_ids", return_value=[dict(self.item)]):
                status, _headers, body = self.request(
                    "/api/library/items?ids=fixture",
                    headers=self.auth_headers(),
                )
        finally:
            server.METADATA_SERVICE = previous
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["items"][0]["album"], "Cached Album")

    def test_uninitialized_metadata_service_returns_local_track_projection(self):
        previous = server.METADATA_SERVICE
        server.METADATA_SERVICE = None
        try:
            status, _headers, body = self.request(
                "/api/metadata/track?track_id=fixture",
                headers=self.auth_headers("library.read"),
            )
        finally:
            server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "local")
        self.assertFalse(payload["pending"])
        self.assertEqual(payload["source"], "本地标签")
        self.assertFalse(payload.get("metadata_unavailable", False))
        self.assertEqual(payload["track_id"], "fixture")

    def test_uninitialized_metadata_service_returns_a_lyrics_only_track_as_local(self):
        # An untagged row is only allowed to fall through to the retryable
        # pending result when the projection really has nothing to show.  A
        # legacy cache row can carry a lyric body and no tags at all; the
        # startup branch must still answer with it instead of pushing the
        # client into a provider loop that cannot produce the document.
        previous = server.METADATA_SERVICE
        server.METADATA_SERVICE = None
        try:
            with mock.patch.object(server, "find_library_item", return_value={
                "id": "fixture", "path": "/music/song.flac",
                "lyrics": "[00:01.00]legacy body",
            }):
                status, _headers, body = self.request(
                    "/api/metadata/track?track_id=fixture",
                    headers=self.auth_headers("library.read"),
                )
        finally:
            server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "local")
        self.assertEqual(payload["lyrics"], "[00:01.00]legacy body")
        self.assertFalse(payload["pending"])
    def test_uninitialized_metadata_service_keeps_untagged_track_retryable(self):
        previous = server.METADATA_SERVICE
        server.METADATA_SERVICE = None
        try:
            with mock.patch.object(server, "find_library_item", return_value={"id": "fixture"}), \
                 mock.patch.object(server, "metadata_service_available", return_value=False):
                status, _headers, body = self.request(
                    "/api/metadata/track?track_id=fixture",
                    headers=self.auth_headers("library.read"),
                )
        finally:
            server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "pending")
        self.assertTrue(payload["retryable"])
        self.assertTrue(payload["metadata_unavailable"])

    def test_missing_metadata_worker_keeps_lyrics_pending(self):
        previous = server.METADATA_SERVICE
        server.METADATA_SERVICE = None
        try:
            status, _headers, body = self.request(
                "/api/lyrics?track_id=fixture",
                headers=self.auth_headers("library.read"),
            )
        finally:
            server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["pending"])
        self.assertTrue(payload["retryable"])
        self.assertTrue(payload["metadata_unavailable"])

    def test_uninitialized_metadata_service_returns_embedded_lyrics(self):
        previous = server.METADATA_SERVICE
        server.METADATA_SERVICE = None
        try:
            with mock.patch.object(server, "find_library_item", return_value={
                "id": "fixture", "lyrics": "[00:01.00]embedded", "cover_url": "cover/fixture?v=1",
            }):
                status, _headers, body = self.request(
                    "/api/lyrics?track_id=fixture",
                    headers=self.auth_headers("library.read"),
                )
        finally:
            server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "local")
        self.assertEqual(payload["lyrics"], "[00:01.00]embedded")
        self.assertFalse(payload["pending"])

    def test_cached_metadata_projection_is_returned_before_worker_liveness_check(self):
        class CachedMetadata:
            def track_match(self, track_id, retry_failed=False):
                self.track_id = track_id
                self.retry_failed = retry_failed
                return {
                    "track_id": track_id,
                    "status": "auto",
                    "best": {"title": "Fixture", "image_url": "https://example.test/cover.jpg"},
                    "candidates": [],
                }

        previous = server.METADATA_SERVICE
        service = CachedMetadata()
        server.METADATA_SERVICE = service
        with mock.patch.object(server, "metadata_service_available", side_effect=AssertionError("cached metadata must bypass worker check")):
            try:
                status, _headers, body = self.request(
                    "/api/metadata/track?track_id=fixture",
                    headers=self.auth_headers("library.read"),
                )
            finally:
                server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "auto")
        self.assertEqual(payload["track_id"], "fixture")

    def test_metadata_track_explicit_retry_reaches_service(self):
        class RetryAwareMetadata:
            def __init__(self):
                self.calls = []

            def track_match(self, track_id, retry_failed=False):
                self.calls.append((track_id, retry_failed))
                return {
                    "track_id": track_id,
                    "status": "pending",
                    "pending": True,
                    "best": {},
                    "candidates": [],
                }

        previous = server.METADATA_SERVICE
        service = RetryAwareMetadata()
        server.METADATA_SERVICE = service
        try:
            status, _headers, body = self.request(
                "/api/metadata/track?track_id=fixture&retry=1",
                headers=self.auth_headers("library.read"),
            )
        finally:
            server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["pending"])
        self.assertEqual(service.calls, [("fixture", True)])

    def test_cached_lyrics_are_returned_before_worker_liveness_check(self):
        class CachedLyrics:
            def lyrics(self, track_id, retry_failed=False):
                return {
                    "lyrics": "[00:01.00]Fixture lyric",
                    "source": "本地歌词",
                    "pending": False,
                }

        previous = server.METADATA_SERVICE
        server.METADATA_SERVICE = CachedLyrics()
        with mock.patch.object(server, "metadata_service_available", side_effect=AssertionError("cached lyrics must bypass worker check")):
            try:
                status, _headers, body = self.request(
                    "/api/lyrics?track_id=fixture",
                    headers=self.auth_headers("library.read"),
                )
            finally:
                server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["source"], "本地歌词")
        self.assertIn("Fixture lyric", payload["lyrics"])

    def test_lyrics_explicit_retry_reaches_service(self):
        class RetryAwareLyrics:
            def __init__(self):
                self.calls = []

            def lyrics(self, track_id, retry_failed=False):
                self.calls.append((track_id, retry_failed))
                return {
                    "lyrics": "",
                    "source": "后台匹配中",
                    "pending": True,
                }

        previous = server.METADATA_SERVICE
        service = RetryAwareLyrics()
        server.METADATA_SERVICE = service
        try:
            status, _headers, body = self.request(
                "/api/lyrics?track_id=fixture&retry=1",
                headers=self.auth_headers("library.read"),
            )
        finally:
            server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["pending"])
        self.assertEqual(service.calls, [("fixture", True)])

    def test_pending_metadata_triggers_recovery_without_becoming_a_hard_error(self):
        class PendingMetadata:
            def track_match(self, track_id, retry_failed=False):
                return {"track_id": track_id, "status": "pending", "pending": True, "best": {}, "candidates": []}

        previous = server.METADATA_SERVICE
        service = PendingMetadata()
        server.METADATA_SERVICE = service
        with mock.patch.object(server, "metadata_service_available", return_value=False) as availability:
            try:
                status, _headers, body = self.request(
                    "/api/metadata/track?track_id=fixture",
                    headers=self.auth_headers("library.read"),
                )
            finally:
                server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["pending"])
        self.assertTrue(payload["retryable"])
        availability.assert_called_once_with(service, "fetch")

    def test_pending_metadata_preserves_local_presentation_fields(self):
        class PendingMetadata:
            def track_match(self, track_id, retry_failed=False):
                return {"track_id": track_id, "status": "pending", "pending": True, "best": {}, "candidates": []}

        previous = server.METADATA_SERVICE
        service = PendingMetadata()
        server.METADATA_SERVICE = service
        local = dict(self.item, title="本地标题", artist="本地歌手", album="本地专辑", cover_url="cover/fixture?v=4")
        with mock.patch.object(server, "find_library_item", return_value=local), \
             mock.patch.object(server, "metadata_service_available", return_value=False):
            try:
                status, _headers, body = self.request(
                    "/api/metadata/track?track_id=fixture",
                    headers=self.auth_headers("library.read"),
                )
            finally:
                server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["pending"])
        self.assertEqual(payload["best"]["title"], "本地标题")
        self.assertEqual(payload["best"]["album"], "本地专辑")
        self.assertEqual(payload["image_url"], "cover/fixture?v=4")

    def test_empty_metadata_result_keeps_recovery_loop_and_local_projection(self):
        class EmptyMetadata:
            def track_match(self, track_id, retry_failed=False):
                return {}

        previous = server.METADATA_SERVICE
        server.METADATA_SERVICE = EmptyMetadata()
        local = dict(self.item, title="本地标题", artist="本地歌手", album="本地专辑")
        with mock.patch.object(server, "find_library_item", return_value=local), \
             mock.patch.object(server, "metadata_service_available", return_value=True):
            try:
                status, _headers, body = self.request(
                    "/api/metadata/track?track_id=fixture",
                    headers=self.auth_headers("library.read"),
                )
            finally:
                server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "pending")
        self.assertTrue(payload["pending"])
        self.assertTrue(payload["retryable"])
        self.assertEqual(payload["best"]["title"], "本地标题")
        self.assertEqual(payload["best"]["album"], "本地专辑")

    def test_metadata_lookup_exception_keeps_local_projection(self):
        class BrokenMetadata:
            def track_match(self, track_id, retry_failed=False):
                raise RuntimeError("temporary database lock")

        previous = server.METADATA_SERVICE
        server.METADATA_SERVICE = BrokenMetadata()
        local = dict(self.item, title="本地标题", artist="本地歌手", album="本地专辑")
        with mock.patch.object(server, "find_library_item", return_value=local), \
             mock.patch.object(server, "metadata_service_available", return_value=True):
            try:
                status, _headers, body = self.request(
                    "/api/metadata/track?track_id=fixture",
                    headers=self.auth_headers("library.read"),
                )
            finally:
                server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "pending")
        self.assertTrue(payload["retryable"])
        self.assertEqual(payload["best"]["artist"], "本地歌手")

    def test_pending_lyrics_triggers_recovery_without_becoming_a_hard_error(self):
        class PendingLyrics:
            def lyrics(self, track_id, retry_failed=False):
                return {"lyrics": "", "source": "后台匹配中", "pending": True}

        previous = server.METADATA_SERVICE
        service = PendingLyrics()
        server.METADATA_SERVICE = service
        with mock.patch.object(server, "metadata_service_available", return_value=False) as availability:
            try:
                status, _headers, body = self.request(
                    "/api/lyrics?track_id=fixture",
                    headers=self.auth_headers("library.read"),
                )
            finally:
                server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["pending"])
        self.assertTrue(payload["retryable"])
        availability.assert_called_once_with(service, "lyrics")

    def test_pending_lyrics_with_cached_artwork_still_triggers_recovery(self):
        artwork_id = "a" * 64

        class PendingLyrics:
            def lyrics(self, track_id, retry_failed=False):
                return {
                    "lyrics": "", "source": "后台匹配中", "pending": True,
                    "image_url": "metadata/artwork/" + artwork_id,
                }

        previous = server.METADATA_SERVICE
        service = PendingLyrics()
        server.METADATA_SERVICE = service
        with mock.patch.object(server, "metadata_service_available", return_value=False) as availability:
            try:
                status, _headers, body = self.request(
                    "/api/lyrics?track_id=fixture",
                    headers=self.auth_headers("library.read"),
                )
            finally:
                server.METADATA_SERVICE = previous
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["pending"])
        self.assertTrue(payload["retryable"])
        self.assertEqual(payload["image_url"], "metadata/artwork/" + artwork_id)
        availability.assert_called_once_with(service, "lyrics")

    def test_metadata_lane_availability_keeps_lyrics_up_when_priority_worker_lives(self):
        class Dead:
            def is_alive(self):
                return False

        class Alive:
            def is_alive(self):
                return True

        service = type("Service", (), {"fetch_threads": [Dead()], "priority_thread": Alive()})()
        self.assertFalse(server.metadata_service_available(service, "fetch"))
        self.assertTrue(server.metadata_service_available(service, "lyrics"))

    def test_metadata_lane_availability_recovers_a_partially_dead_fetch_pool(self):
        class Dead:
            def is_alive(self):
                return False

        class Alive:
            def is_alive(self):
                return True

        class Service:
            def __init__(self):
                self.fetch_threads = [Alive(), Dead()]
                self.priority_thread = None
                self.calls = 0

            def ensure_workers(self, lane):
                self.calls += 1
                self.fetch_threads = [Alive(), Alive()]

        service = Service()
        self.assertTrue(server.metadata_service_available(service, "fetch"))
        self.assertEqual(service.calls, 1)

    def test_metadata_lane_availability_attempts_one_lazy_recovery(self):
        class Service:
            fetch_threads = [type("Dead", (), {"is_alive": lambda _self: False})()]
            priority_thread = None
            def __init__(self):
                self.recovered = 0
            def ensure_workers(self):
                self.recovered += 1
                self.fetch_threads = [type("Alive", (), {"is_alive": lambda _self: True})()]
                return True

        service = Service()
        self.assertTrue(server.metadata_service_available(service, "fetch"))
        self.assertEqual(service.recovered, 1)

    def test_metadata_lane_availability_allows_worker_startup_race(self):
        class Worker:
            def __init__(self):
                self.calls = 0
            def is_alive(self):
                self.calls += 1
                return self.calls >= 2

        class Service:
            fetch_threads = []
            priority_thread = None
            tag_thread = None
            def __init__(self):
                self.worker = Worker()
            def ensure_workers(self, lane):
                self.fetch_threads = [self.worker]

        service = Service()
        with mock.patch.object(server.time, "sleep") as pause:
            self.assertTrue(server.metadata_service_available(service, "fetch"))
        pause.assert_called_once_with(0.02)

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

    def test_library_path_update_invalidates_library_query_cache(self):
        with mock.patch.object(server, "invalidate_library_query_cache") as invalidate:
            status, _headers, body = self.request(
                "/api/config/library",
                method="POST",
                headers={**self.auth_headers("settings.write"), "Content-Type": "application/json"},
                data=json.dumps({"library_path": self.temp.name}).encode(),
            )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])
        invalidate.assert_called_once_with(self.httpd.config)

    def test_metadata_config_rejects_string_boolean_values(self):
        self.httpd.config.update({
            "metadata_enabled": False,
            "metadata_tag_write_enabled": False,
            "metadata_orphan_grace_days": 7,
        })
        with mock.patch.object(server, "METADATA_SERVICE", None):
            status, _headers, body = self.request(
                "/api/config/metadata",
                method="POST",
                headers={**self.auth_headers("settings.write"), "Content-Type": "application/json"},
                data=json.dumps({"enabled": "false", "tag_write_enabled": "0"}).encode("utf-8"),
            )
        self.assertEqual(status, 400)
        self.assertFalse(self.httpd.config["metadata_enabled"])
        self.assertFalse(self.httpd.config["metadata_tag_write_enabled"])

    def test_metadata_config_accepts_json_booleans_and_refreshes_with_exact_value(self):
        class Service:
            def __init__(self):
                self.forces = []
            def wake(self, force=False):
                self.forces.append(force)
            def status(self):
                return {"ok": True}

        service = Service()
        with mock.patch.object(server, "METADATA_SERVICE", service):
            status, _headers, body = self.request(
                "/api/config/metadata",
                method="POST",
                headers={**self.auth_headers("settings.write"), "Content-Type": "application/json"},
                data=json.dumps({"enabled": True, "tag_write_enabled": False, "refresh": True, "orphan_grace_days": 3}).encode("utf-8"),
            )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])
        self.assertTrue(self.httpd.config["metadata_enabled"])
        self.assertFalse(self.httpd.config["metadata_tag_write_enabled"])
        self.assertEqual(service.forces, [True])

    def test_metadata_config_rejects_fractional_grace_days_without_truncating(self):
        previous = dict(self.httpd.config)
        try:
            status, _headers, body = self.request(
                "/api/config/metadata",
                method="POST",
                headers={**self.auth_headers("settings.write"), "Content-Type": "application/json"},
                data=b'{"enabled":true,"tag_write_enabled":false,"orphan_grace_days":1.9}',
            )
        finally:
            self.httpd.config.clear()
            self.httpd.config.update(previous)
        self.assertEqual(status, 400)
        self.assertIn("宽限天数", json.loads(body)["message"])

    # --- R124 / D9: the library connection pool switch on the settings pane -------
    # These are the discriminative checks for exposing a switch that used to be
    # config-file-only.  Each one fails in exactly one direction: a route that lies
    # about the running value, a route that coerces text into a boolean, a route that
    # claims success without draining the handles, or a route that clobbers the key it
    # was not given.
    def runtime_post(self, payload, scope="settings.write"):
        return self.request(
            "/api/config/runtime",
            method="POST",
            headers={**self.auth_headers(scope), "Content-Type": "application/json"},
            data=json.dumps(payload).encode("utf-8"),
        )

    def test_runtime_config_reports_the_value_the_pool_actually_honours(self):
        # Absent key: the reader path treats that as disabled, so the pane must not
        # show the config-module default of "on" while nothing is being pooled.
        self.httpd.config.pop("library_connection_pool", None)
        status, _headers, body = self.request(
            "/api/config/runtime", headers=self.auth_headers("settings.read")
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["ok"])
        self.assertIs(payload["config"]["library_connection_pool"], False)
        for key, expected in ((True, True), (False, False)):
            self.httpd.config["library_connection_pool"] = key
            status, _headers, body = self.request(
                "/api/config/runtime", headers=self.auth_headers("settings.read")
            )
            self.assertEqual(status, 200)
            self.assertIs(json.loads(body)["config"]["library_connection_pool"], expected)

    def test_runtime_config_requires_the_settings_scopes(self):
        status, _headers, _body = self.request("/api/config/runtime")
        self.assertEqual(status, 401)
        status, _headers, _body = self.runtime_post({"library_connection_pool": False}, scope="settings.read")
        self.assertEqual(status, 403)

    def test_runtime_config_rejects_text_boolean_without_changing_the_switch(self):
        self.httpd.config["library_connection_pool"] = True
        for value in ("false", 0, "0", None, 1):
            status, _headers, body = self.runtime_post({"library_connection_pool": value})
            self.assertEqual(status, 400, value)
            self.assertIn("布尔值", json.loads(body)["message"])
            self.assertIs(self.httpd.config["library_connection_pool"], True)

    def test_runtime_config_omitting_the_key_keeps_the_current_switch(self):
        self.httpd.config["library_connection_pool"] = False
        status, _headers, body = self.runtime_post({})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])
        self.assertIs(self.httpd.config["library_connection_pool"], False)

    def test_runtime_config_turning_the_pool_off_drains_handles_after_the_commit(self):
        self.httpd.config["library_connection_pool"] = True
        seen = []

        def record_applied(config):
            # Read the live dictionary, not the candidate: this is what proves the
            # drain runs after the in-place commit rather than against stale state.
            seen.append(self.httpd.config.get("library_connection_pool"))

        with mock.patch.object(server, "apply_library_connection_pool_config", side_effect=record_applied) as applied:
            status, _headers, body = self.runtime_post({"library_connection_pool": False})
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["ok"])
        self.assertIs(payload["restart_required"], False)
        self.assertIs(payload["config"]["library_connection_pool"], False)
        applied.assert_called_once()
        self.assertEqual(seen, [False])
        self.assertIs(self.httpd.config["library_connection_pool"], False)

    def test_runtime_config_persistence_failure_leaves_the_running_switch_alone(self):
        self.httpd.config["library_connection_pool"] = True
        with mock.patch.object(server, "save_config", return_value=False):
            status, _headers, body = self.runtime_post({"library_connection_pool": False})
        self.assertEqual(status, 500)
        self.assertFalse(json.loads(body)["ok"])
        self.assertIs(self.httpd.config["library_connection_pool"], True)

    # --- R139 / ruling Q6=A: the lyric cache budget joins the same runtime pane ----
    def runtime_get(self):
        return self.request("/api/config/runtime", headers=self.auth_headers("settings.read"))

    def test_runtime_config_reports_the_budget_the_lanes_actually_enforce(self):
        # The pane promises the running value. A handler that echoed the config
        # file would show 1 MiB while both lanes still held four, which is the
        # exact lie the connection-pool check above exists to prevent.
        self.httpd.config[CONFIG_BYTES_KEY] = 1024 * 1024
        lanes = [
            LocalLyricsCache(lambda path: "l", max_bytes=4 * 1024 * 1024),
            LocalLyricsCache(lambda path: "l", max_bytes=MAX_MAX_BYTES),
        ]
        stub = RuntimeLyricsService(lanes=lanes)
        with mock.patch.object(server, "METADATA_SERVICE", stub):
            status, _headers, body = self.runtime_get()
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["config"][CONFIG_BYTES_KEY], 4 * 1024 * 1024)
        self.assertNotEqual(payload["config"][CONFIG_BYTES_KEY], 1024 * 1024)

    def test_runtime_config_without_a_metadata_service_shows_the_bounded_config(self):
        # Before the service exists (startup, or a unit harness that never built
        # one) the only honest answer is the config clamped the way the cache
        # would clamp it, never the raw stored junk.
        with mock.patch.object(server, "METADATA_SERVICE", None):
            self.httpd.config.pop(CONFIG_BYTES_KEY, None)
            status, _headers, body = self.runtime_get()
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["config"][CONFIG_BYTES_KEY], DEFAULT_MAX_BYTES)
            self.httpd.config[CONFIG_BYTES_KEY] = 10
            status, _headers, body = self.runtime_get()
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["config"][CONFIG_BYTES_KEY], MIN_MAX_BYTES)

    def test_runtime_config_ignores_an_unusable_report_from_the_service(self):
        # Other suites replace METADATA_SERVICE with a MagicMock whose answers
        # are not JSON-serialisable integers. Falling back to the bounded config
        # keeps a settings read honest instead of answering 500.
        stub = mock.MagicMock()
        stub.lyrics_cache_bytes_limit.return_value = "8 MiB"
        self.httpd.config[CONFIG_BYTES_KEY] = 2 * 1024 * 1024
        with mock.patch.object(server, "METADATA_SERVICE", stub):
            status, _headers, body = self.runtime_get()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["config"][CONFIG_BYTES_KEY], 2 * 1024 * 1024)

    def test_runtime_config_rejects_an_unusable_budget_without_moving_the_cache(self):
        self.httpd.config[CONFIG_BYTES_KEY] = 2 * 1024 * 1024
        lanes = [LocalLyricsCache(lambda path: "l", max_bytes=2 * 1024 * 1024)]
        stub = RuntimeLyricsService(lanes=lanes)
        for value in (True, False, 0, -1, MIN_MAX_BYTES - 1, MAX_MAX_BYTES + 1,
                      10 ** 12, "8388608", 8.5, None, []):
            with mock.patch.object(server, "METADATA_SERVICE", stub):
                status, _headers, body = self.runtime_post({CONFIG_BYTES_KEY: value})
            self.assertEqual(status, 400, value)
            self.assertIn("歌词缓存预算", json.loads(body)["message"])
            self.assertEqual(self.httpd.config[CONFIG_BYTES_KEY], 2 * 1024 * 1024)
            self.assertEqual(lanes[0].snapshot()["bytes_limit"], 2 * 1024 * 1024)
        self.assertEqual(stub.applied, [])

    def test_runtime_config_applies_a_budget_after_the_commit_and_drains_the_lanes(self):
        lanes = [
            LocalLyricsCache(lambda path: "l" * 60000, max_bytes=4 * 1024 * 1024),
            LocalLyricsCache(lambda path: "l" * 60000, max_bytes=4 * 1024 * 1024),
        ]
        for lane in lanes:
            lane.read("a.lrc", (1, 1))
            lane.read("b.lrc", (2, 2))
        self.assertTrue(all(lane.snapshot()["entries"] == 2 for lane in lanes))
        stub = RuntimeLyricsService(lanes=lanes)
        with mock.patch.object(server, "METADATA_SERVICE", stub):
            status, _headers, body = self.runtime_post({CONFIG_BYTES_KEY: 64 * 1024})
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["ok"])
        self.assertIs(payload["restart_required"], False)
        self.assertEqual(payload["config"][CONFIG_BYTES_KEY], 64 * 1024)
        self.assertEqual(self.httpd.config[CONFIG_BYTES_KEY], 64 * 1024)
        # One applier call, and it saw the committed dictionary: retraining
        # against the candidate would leave a phantom change after a failed save.
        self.assertEqual([call[CONFIG_BYTES_KEY] for call in stub.applied], [64 * 1024])
        # Two 60 kB documents do not fit a 64 KiB budget, so the oldest has to
        # be gone by the time this response claims success.
        for lane in lanes:
            snapshot = lane.snapshot()
            self.assertEqual(snapshot["bytes_limit"], 64 * 1024)
            self.assertEqual(snapshot["entries"], 1)
            self.assertLessEqual(snapshot["bytes"], snapshot["bytes_limit"])

    def test_runtime_config_budget_and_pool_do_not_clobber_each_other(self):
        stub = RuntimeLyricsService()
        self.httpd.config["library_connection_pool"] = True
        self.httpd.config[CONFIG_BYTES_KEY] = 2 * 1024 * 1024
        with mock.patch.object(server, "METADATA_SERVICE", stub):
            status, _headers, body = self.runtime_post({"library_connection_pool": False})
            self.assertEqual(status, 200, body)
            self.assertIs(self.httpd.config["library_connection_pool"], False)
            self.assertEqual(self.httpd.config[CONFIG_BYTES_KEY], 2 * 1024 * 1024)
            status, _headers, body = self.runtime_post({CONFIG_BYTES_KEY: 64 * 1024})
            self.assertEqual(status, 200, body)
            self.assertIs(self.httpd.config["library_connection_pool"], False)
            self.assertEqual(self.httpd.config[CONFIG_BYTES_KEY], 64 * 1024)

    def test_runtime_config_budget_untouched_when_the_save_fails(self):
        lanes = [LocalLyricsCache(lambda path: "l", max_bytes=2 * 1024 * 1024)]
        stub = RuntimeLyricsService(lanes=lanes)
        self.httpd.config[CONFIG_BYTES_KEY] = 2 * 1024 * 1024
        with mock.patch.object(server, "METADATA_SERVICE", stub), \
                mock.patch.object(server, "save_config", return_value=False):
            status, _headers, body = self.runtime_post({CONFIG_BYTES_KEY: 64 * 1024})
        self.assertEqual(status, 500)
        self.assertFalse(json.loads(body)["ok"])
        self.assertEqual(self.httpd.config[CONFIG_BYTES_KEY], 2 * 1024 * 1024)
        self.assertEqual(lanes[0].snapshot()["bytes_limit"], 2 * 1024 * 1024)
        self.assertEqual(stub.applied, [])

    def test_server_source_names_the_cache_budget_only_through_the_shared_constant(self):
        # The key lives in the cache module so the config default, the reader,
        # the HTTP route and the UI cannot drift apart; a second spelling here is
        # how a rename silently breaks one of them.
        with open(os.path.join("app", "server", "server.py"), encoding="utf-8") as handle:
            source = handle.read()
        # Boolean checks on purpose: assertIn/NotIn dump the whole 3.4k-line
        # module into the log when they fail, which buries the real failure.
        self.assertFalse((chr(34) + CONFIG_BYTES_KEY + chr(34)) in source)
        self.assertTrue("LYRICS_CACHE_BYTES_CONFIG_KEY" in source)
        self.assertTrue("apply_lyrics_cache_config" in source)

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

    def test_media_get_opens_one_stable_file_handle_for_size_and_body(self):
        # The endpoint must not stat a path and later reopen it for GET: a
        # replacement between those operations could bypass the earlier root
        # validation. The integration fixture still proves the public result.
        status, headers, body = self.request("/media/fixture", headers=self.auth_headers())
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Length"], "10")
        self.assertEqual(body, b"0123456789")

    def test_media_head_uses_the_same_stable_file_open_path(self):
        status, headers, body = self.request("/media/fixture", method="HEAD", headers=self.auth_headers())
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Length"], "10")
        self.assertEqual(body, b"")

    def test_upnp_media_remains_credential_free_for_renderers(self):
        status, headers, body = self.request("/upnp/media/fixture/fixture.mp3")
        self.assertEqual(status, 200)
        self.assertEqual(headers["transferMode.dlna.org"], "Streaming")
        self.assertEqual(body, b"0123456789")

    def test_percent_encoded_track_ids_round_trip_on_media_and_cover(self):
        # Advertised URIs always percent-encode the ID segment, and the UI
        # encodes it too, so a route that looks up the raw text can never
        # resolve an ID that needs escaping.  %74 decodes to the fixture ID.
        status, _headers, body = self.request("/upnp/media/fix%74ure/fixture.mp3")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"0123456789")

        status, _headers, body = self.request("/cover/fix%74ure", headers=self.auth_headers())
        self.assertEqual(status, 200)
        self.assertEqual(body, b"cover")

        status, _headers, body = self.request("/upnp/cover/fix%74ure?size=160")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"cover")

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

    def test_metadata_artwork_stream_uses_open_file_size(self):
        artwork_path = os.path.join(self.temp.name, "metadata.jpg")
        with open(artwork_path, "wb") as handle:
            handle.write(b"metadata-cover")

        class ArtworkService:
            def artwork(self, _asset_id):
                return {"path": artwork_path, "mime": "image/jpeg", "size": 1}

        previous = server.METADATA_SERVICE
        server.METADATA_SERVICE = ArtworkService()
        try:
            status, headers, body = self.request(
                "/metadata/artwork/" + ("a" * 64),
                headers=self.auth_headers(),
            )
        finally:
            server.METADATA_SERVICE = previous
        self.assertEqual(status, 200)
        self.assertEqual(body, b"metadata-cover")
        self.assertEqual(headers["Content-Length"], str(len(body)))

    def test_metadata_artwork_sized_request_uses_the_shared_thumbnail_store(self):
        artwork_path = os.path.join(self.temp.name, "sized-metadata.jpg")
        with open(artwork_path, "wb") as handle:
            handle.write(b"metadata-cover")

        class ArtworkService:
            def artwork(self, _asset_id):
                return {"path": artwork_path, "mime": "image/jpeg", "size": 1}

        asset_id = "d" * 64
        previous = server.METADATA_SERVICE
        server.METADATA_SERVICE = ArtworkService()
        try:
            with mock.patch.object(
                server, "generate_asset_thumbnail", return_value=("image/jpeg", b"tile")
            ) as render:
                status, headers, body = self.request(
                    "/metadata/artwork/%s?size=160" % asset_id, headers=self.auth_headers()
                )
                self.assertEqual(status, 200)
                self.assertEqual(body, b"tile")
                self.assertEqual(headers["Content-Length"], str(len(body)))
                self.assertEqual(render.call_args.args[1:3], (asset_id, 160))
                # The unsized request still describes the stored original, and a
                # conditional hit earned there must not answer for the tile.
                original_status, original_headers, original_body = self.request(
                    "/metadata/artwork/%s" % asset_id, headers=self.auth_headers()
                )
                self.assertEqual(original_body, b"metadata-cover")
                sized_status, _sized_headers, sized_body = self.request(
                    "/metadata/artwork/%s?size=160" % asset_id,
                    headers={**self.auth_headers(), "If-None-Match": original_headers["ETag"]},
                )
                # A conditional hit earned from the tile must keep answering
                # with the tile, not the original behind it.
                conditional = self.request(
                    "/metadata/artwork/%s?size=160" % asset_id,
                    headers={**self.auth_headers(), "If-None-Match": headers["ETag"]},
                )
            self.assertEqual(sized_status, 200)
            self.assertEqual(sized_body, b"tile")
            self.assertEqual(original_status, 200)
            self.assertNotEqual(original_headers["ETag"], headers["ETag"])
            self.assertEqual(conditional[0], 304)
            self.assertEqual(conditional[2], b"")
        finally:
            server.METADATA_SERVICE = previous

    def test_metadata_artwork_sized_request_falls_back_without_a_render(self):
        artwork_path = os.path.join(self.temp.name, "unsized-metadata.jpg")
        with open(artwork_path, "wb") as handle:
            handle.write(b"metadata-cover")

        class ArtworkService:
            def artwork(self, _asset_id):
                return {"path": artwork_path, "mime": "image/jpeg", "size": 1}

        previous = server.METADATA_SERVICE
        server.METADATA_SERVICE = ArtworkService()
        try:
            with mock.patch.object(server, "generate_asset_thumbnail", return_value=None):
                status, _headers, body = self.request(
                    "/metadata/artwork/" + ("e" * 64) + "?size=160", headers=self.auth_headers()
                )
        finally:
            server.METADATA_SERVICE = previous
        self.assertEqual(status, 200)
        self.assertEqual(body, b"metadata-cover")

    def test_metadata_artwork_stream_rechecks_resource_limit(self):
        artwork_path = os.path.join(self.temp.name, "oversized-metadata.jpg")
        with open(artwork_path, "wb") as handle:
            handle.truncate(server.MAX_ARTWORK_BYTES + 1)

        class ArtworkService:
            def artwork(self, _asset_id):
                return {"path": artwork_path, "mime": "image/jpeg", "size": server.MAX_ARTWORK_BYTES}

        previous = server.METADATA_SERVICE
        server.METADATA_SERVICE = ArtworkService()
        try:
            status, _headers, _body = self.request(
                "/metadata/artwork/" + ("b" * 64),
                headers=self.auth_headers(),
            )
        finally:
            server.METADATA_SERVICE = previous
        self.assertEqual(status, 404)

    def test_cover_thumbnail_uses_long_lived_cache_headers(self):
        with mock.patch.object(server, "cached_thumbnail_for_item", return_value=("image/jpeg", b"thumb")) as thumbnail, \
             mock.patch.object(server.OBSERVABILITY, "write") as write_log:
            status, headers, body = self.request("/cover/fixture?size=160", headers=self.auth_headers())
        self.assertEqual(status, 200)
        self.assertEqual(body, b"thumb")
        self.assertIn("immutable", headers["Cache-Control"])
        thumbnail.assert_called_once()
        write_log.assert_not_called()

    def test_post_body_limit_is_enforced_before_json_parsing(self):
        # The gate reads the declared length, never the body, so an oversized
        # declaration is refused with a two-byte payload on the wire. Pushing a
        # real 2 MiB instead races the server: every response here is HTTP/1.0,
        # so the socket is already closing while the client still has unsent
        # bytes, and on Windows the pending write can abort the connection and
        # discard the buffered 413 (WSAECONNABORTED). Withholding the body also
        # proves something the full write could not: the limit is enforced before
        # the body is read at all. Same idiom as
        # test_transfer_encoding_is_rejected_before_body_parsing above.
        oversized = str(2 * 1024 * 1024 + 1)
        status, _headers, body = self.request(
            "/api/playback/control",
            method="POST",
            headers={**self.auth_headers("playback.control"),
                     "Content-Type": "application/json",
                     "Content-Length": oversized},
            data=b"{}",
        )
        self.assertEqual(status, 413)
        self.assertIn(b"too large", body)

    def test_user_state_rejects_invalid_revision_instead_of_disabling_conflict_check(self):
        headers = {**self.auth_headers("state.write"), "Content-Type": "application/json"}
        status, _headers, body = self.request(
            "/api/state/user",
            method="POST",
            headers=headers,
            data=b'{"revision":"1.5","favorites_add":[]}',
        )
        self.assertEqual(status, 400)
        self.assertIn(b"revision must be a nonnegative integer", body)

        status, _headers, body = self.request(
            "/api/state/user",
            method="POST",
            headers=headers,
            data=b'{"revision":true,"favorites_add":[]}',
        )
        self.assertEqual(status, 400)
        self.assertIn(b"revision must be a nonnegative integer", body)

    def test_control_text_fields_reject_json_containers_without_coercion(self):
        headers = {**self.auth_headers("settings.write"), "Content-Type": "application/json"}
        status, _headers, body = self.request(
            "/api/transcode/warm",
            method="POST",
            headers=headers,
            data=b'{"track_id":"missing","mode":[]}',
        )
        self.assertEqual(status, 400)
        self.assertIn(b"unsupported cache mode", body)

    def test_transcode_status_rejects_modes_without_a_matching_cache_contract(self):
        status, _headers, body = self.request(
            "/api/transcode/status?track_id=fixture&mode=dsd_wav",
            headers=self.auth_headers(),
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"], "unsupported cache mode")

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
    def test_the_retired_fnos_get_routes_answer_like_any_unknown_path(self):
        # R118 removed seven `if False and` route blocks rather than a route table,
        # so retirement is only real if the deleted paths now behave like every other
        # unknown path: a GET reaches the static handler and misses, a POST reaches
        # the terminal not-found response. A resurrected block could not have answered
        # either request successfully -- the shared-folder helpers it called were
        # never imported -- so the failure mode this pins is 200/500 instead of 404.
        status, _headers, _body = self.request(
            "/api/fnos/shared-folders",
            headers=self.auth_headers(),
        )
        self.assertEqual(status, 404)

        for path in ("/api/fnos/auth-debug", "/api/fnos/shared-folders/nested"):
            status, _headers, _body = self.request(path, headers=self.auth_headers())
            self.assertEqual(status, 404, path)

    def test_the_retired_fnos_posts_still_reach_the_terminal_not_found(self):
        headers = {**self.auth_headers("settings.write"), "Content-Type": "application/json"}
        for path in ("/api/fnos/shared-folders/sync", "/api/fnos/shared-folders/delete"):
            with mock.patch.object(server, "commit_config_update") as commit:
                status, _headers, body = self.request(
                    path,
                    method="POST",
                    headers=headers,
                    data=b'{"paths":["/mnt/nas/music"]}',
                )
            self.assertEqual(status, 404, path)
            self.assertEqual(json.loads(body)["error"], "not found")
            commit.assert_not_called()


class ArtworkMediaTypeTests(unittest.TestCase):
    """Cover routes answer on the service origin, including without a session.

    The MIME string that reaches these routes can originate in an audio file tag
    or in a provider response header, so each one has to prove its own type from
    the bytes it is about to write.
    """

    PNG = b"\x89PNG\r\n\x1a\npayload"
    HTML = b"<script>alert(document.domain)</script>"

    def _handler(self, errors):
        handler = object.__new__(server.Handler)
        handler.server = mock.Mock()
        handler.server.config = {}
        handler.headers = {}
        handler.records = []
        handler.send_response = lambda status: handler.records.append(("status", status))
        handler.send_header = lambda name, value: handler.records.append((name, value))
        handler.end_headers = lambda: handler.records.append(("end", None))
        handler.wfile = io.BytesIO()
        handler.send_error = lambda status, message=None: errors.append(status)
        return handler

    def _headers(self, handler):
        return [value for name, value in handler.records if name == "Content-Type"]

    def test_cover_route_refuses_a_declaration_that_is_not_an_image(self):
        errors = []
        handler = self._handler(errors)
        with mock.patch.object(server, "find_library_item", return_value={"id": "t1", "path": "a.flac"}), \
                mock.patch.object(server, "cover_source_version", return_value="1"), \
                mock.patch.object(server, "cache_cover_for_item", return_value=("text/html", self.HTML)):
            handler.serve_cover("t1")
        self.assertEqual(errors, [404])
        self.assertEqual(handler.records, [])
        self.assertEqual(handler.wfile.getvalue(), b"")

    def test_cover_route_reports_the_pixels_not_the_tag(self):
        errors = []
        handler = self._handler(errors)
        declared = "image/png\r\nSet-Cookie: session=hijacked"
        with mock.patch.object(server, "find_library_item", return_value={"id": "t1", "path": "a.flac"}), \
                mock.patch.object(server, "cover_source_version", return_value="1"), \
                mock.patch.object(server, "cache_cover_for_item", return_value=(declared, self.PNG)):
            handler.serve_cover("t1")
        self.assertEqual(errors, [])
        self.assertEqual(self._headers(handler), ["image/png"])
        self.assertEqual(handler.wfile.getvalue(), self.PNG)
        # A declared type never survives as text on the wire, so it cannot become
        # a second header line either.
        self.assertFalse(any("png\r" in str(value) or "Set-Cookie" in str(value) for _, value in handler.records))

    def test_thumbnail_cover_route_resolves_the_source_version_once(self):
        """One request, one filesystem identity.

        The endpoint used to resolve the version for the ETag while
        ``cached_thumbnail_for_item`` resolved it again for the cache path, again
        for the memory key and again for the render lock.  Four probes could
        disagree with each other whenever the media file changed mid-request, so
        the whole chain now shares a single resolution, which this counts.
        """
        errors = []
        handler = self._handler(errors)
        probes = []

        def counting_version(item, allow_disk=True):
            probes.append(allow_disk)
            return "7:4096"

        with tempfile.TemporaryDirectory() as root:
            handler.server.config = {"cache_dir": root}
            with mock.patch.object(server, "find_library_item",
                                   return_value={"id": "t1", "path": "a.flac", "modified_ns": 7, "size": 4096}), \
                    mock.patch.object(server, "cover_source_version", counting_version), \
                    mock.patch("cover_cache.cover_source_version", counting_version), \
                    mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb"), \
                    mock.patch.object(server, "cache_cover_for_item",
                                      return_value=("image/jpeg", b"\xff\xd8thumbnail")):
                handler.serve_cover("t1", query={"size": ["160"]})
            self.assertEqual(errors, [])
            self.assertEqual(len(probes), 1, "the cover chain must resolve one version per request")
            etag = next(value for name, value in handler.records if name == "ETag")
            self.assertIn("7:4096", etag)
            stored = os.listdir(os.path.join(root, "covers", "thumb-160"))
            self.assertTrue(stored, "the request must have published one cached thumbnail")
            key = cover_cache._cache_key({"id": "t1", "path": "a.flac", "modified_ns": 7, "size": 4096}, 160, "7:4096")
            # The store writes the `<key>.asset` alias for the shared asset; the
            # stem is what has to agree with the version the ETag reports.
            self.assertEqual([os.path.splitext(name)[0] for name in stored], [key])

    def test_cover_route_refuses_before_the_conditional_branch(self):
        errors = []
        handler = self._handler(errors)
        handler.headers = {"If-None-Match": "anything"}
        with mock.patch.object(server, "find_library_item", return_value={"id": "t1", "path": "a.flac"}), \
                mock.patch.object(server, "cover_source_version", return_value="1"), \
                mock.patch.object(server, "cache_cover_for_item", return_value=("text/html", self.HTML)):
            handler.serve_cover("t1")
        self.assertEqual(errors, [404])
        self.assertNotIn(("status", 304), handler.records)

    def test_upnp_cover_route_shares_the_same_refusal_without_auth(self):
        errors = []
        handler = self._handler(errors)
        with mock.patch.object(server, "find_library_item", return_value={"id": "t1", "path": "a.flac"}), \
                mock.patch.object(server, "cover_source_version", return_value="1"), \
                mock.patch.object(server, "cache_cover_for_item", return_value=("text/html", self.HTML)):
            handler.serve_upnp_cover("t1")
        self.assertEqual(errors, [404])
        self.assertEqual(handler.records, [])

    def test_thumbnail_asset_route_refuses_bytes_it_cannot_describe(self):
        errors = []
        handler = self._handler(errors)
        with mock.patch.object(server, "thumbnail_asset_bytes", return_value=("image/png", self.HTML)):
            handler.serve_cover_asset("a" * 64)
        self.assertEqual(errors, [404])
        self.assertEqual(handler.records, [])

    def test_thumbnail_asset_route_uses_the_real_type_of_its_bytes(self):
        errors = []
        handler = self._handler(errors)
        with mock.patch.object(server, "thumbnail_asset_bytes", return_value=("image/unknown-tagged", self.PNG)):
            handler.serve_cover_asset("a" * 64)
        self.assertEqual(errors, [])
        self.assertEqual(self._headers(handler), ["image/png"])
        self.assertEqual(handler.wfile.getvalue(), self.PNG)

    def _serve_artwork(self, stored_mime, body):
        errors = []
        handler = self._handler(errors)
        service = mock.Mock()
        service.artwork.return_value = {"path": "artwork.png", "mime": stored_mime, "size": len(body)}
        handle = self._RecordingHandle(body)
        with mock.patch.object(server, "METADATA_SERVICE", service), \
                mock.patch.object(server, "open_bounded_artwork", return_value=(handle, len(body))):
            handler.serve_metadata_artwork("a" * 64)
        return errors, handler, handle

    class _RecordingHandle(io.BytesIO):
        """Records the read sizes so the proof cannot ask for the whole asset."""

        def __init__(self, body):
            super().__init__(body)
            self.read_sizes = []

        def read(self, size=-1):
            self.read_sizes.append(size)
            return super().read(size)


    def test_metadata_artwork_route_relabels_a_stored_declaration(self):
        body = self.PNG
        errors, handler, handle = self._serve_artwork("text/html", body)
        self.assertEqual(handle.read_sizes[0], server.SNIFF_PREFIX_BYTES)
        self.assertEqual(errors, [])
        self.assertEqual(self._headers(handler), ["image/png"])
        # The sniff prefix must still reach the client exactly once.
        self.assertEqual(handler.wfile.getvalue(), body)
        self.assertEqual(
            [value for name, value in handler.records if name == "Content-Length"],
            [str(len(body))],
        )

    def test_metadata_artwork_route_refuses_a_scriptable_asset(self):
        errors, handler, _handle = self._serve_artwork("image/jpeg", self.HTML)
        self.assertEqual(errors, [404])
        self.assertEqual(handler.records, [])
        self.assertEqual(handler.wfile.getvalue(), b"")


if __name__ == "__main__":
    unittest.main()
