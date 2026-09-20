import importlib.util
import io
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "ui" / "cgi_proxy.py"
SPEC = importlib.util.spec_from_file_location("fnaudio_cgi_proxy", MODULE_PATH)
cgi_proxy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cgi_proxy)


class CgiProxyAuthTests(unittest.TestCase):
    TOKEN_ENV = (
        "TRIM_API_TOKEN",
        "HTTP_TRIM_TOKEN",
        "HTTP_X_TRIM_TOKEN",
        "HTTP_AUTHORIZATION",
        "HTTP_X_FNAUDIO_TRIM_TOKEN",
        "HTTP_COOKIE",
    )

    def setUp(self):
        self.saved = {name: os.environ.get(name) for name in self.TOKEN_ENV}
        for name in self.TOKEN_ENV:
            os.environ.pop(name, None)

    def tearDown(self):
        for name in self.TOKEN_ENV:
            os.environ.pop(name, None)
            if self.saved[name] is not None:
                os.environ[name] = self.saved[name]

    def test_authorization_header_has_priority(self):
        os.environ["HTTP_AUTHORIZATION"] = "Bearer header-token"
        os.environ["HTTP_COOKIE"] = "fnaudio_trim_token=cookie-token"
        self.assertEqual(cgi_proxy.trim_token(), "header-token")

    def test_android_cookie_is_url_decoded(self):
        os.environ["HTTP_COOKIE"] = "theme=dark; fnaudio_trim_token=abc%2Bdef%3D%3D; other=value"
        self.assertEqual(cgi_proxy.trim_token(), "abc+def==")

    def test_unrelated_cookie_is_not_accepted(self):
        os.environ["HTTP_COOKIE"] = "session=not-a-trim-token; theme=dark"
        self.assertEqual(cgi_proxy.trim_token(), "")

    def test_trim_token_rejects_header_injection_and_falls_back_to_next_source(self):
        os.environ["TRIM_API_TOKEN"] = "bad\r\nX-Injected: yes"
        os.environ["HTTP_TRIM_TOKEN"] = "Bearer usable-token"
        self.assertEqual(cgi_proxy.trim_token(), "usable-token")

    def test_trim_token_is_bounded_before_request_construction(self):
        os.environ["TRIM_API_TOKEN"] = "x" * (cgi_proxy.MAX_TRIM_TOKEN_CHARS + 1)
        self.assertEqual(cgi_proxy.trim_token(), "")

    def test_proxy_request_header_value_rejects_control_and_oversized_values(self):
        self.assertEqual(cgi_proxy.proxy_request_header_value("  10.0.0.1  "), "10.0.0.1")
        self.assertEqual(cgi_proxy.proxy_request_header_value("10.0.0.1\r\nX-Injected: yes"), "")
        self.assertEqual(cgi_proxy.proxy_request_header_value("x" * (cgi_proxy.MAX_PROXY_REQUEST_HEADER_VALUE_CHARS + 1)), "")

    def test_proxy_request_body_rejects_invalid_or_oversized_lengths(self):
        with self.assertRaises(ValueError):
            cgi_proxy.read_proxy_request_body(io.BytesIO(b"x"), "not-a-number")
        with self.assertRaises(OverflowError):
            cgi_proxy.read_proxy_request_body(io.BytesIO(b"x"), cgi_proxy.MAX_PROXY_REQUEST_BODY_BYTES + 1)
        self.assertEqual(cgi_proxy.read_proxy_request_body(io.BytesIO(b"abc"), "2"), b"ab")
        with self.assertRaises(ValueError):
            cgi_proxy.read_proxy_request_body(io.BytesIO(b"x"), "2")
        with self.assertRaises(ValueError):
            cgi_proxy.read_proxy_request_body(io.BytesIO(b"x"), "１２")

    def test_proxy_request_body_reads_short_chunks_until_declared_length(self):
        class ShortReader:
            def __init__(self):
                self.parts = [b"a", b"b", b"c"]

            def read(self, _size):
                return self.parts.pop(0) if self.parts else b""

        self.assertEqual(cgi_proxy.read_proxy_request_body(ShortReader(), "3"), b"abc")

    def test_service_start_propagates_nonzero_exit_code(self):
        with patch.object(cgi_proxy, "appdest", return_value="/app"), \
             patch.object(cgi_proxy.os.path, "isfile", return_value=True), \
             patch.object(cgi_proxy.subprocess, "run", return_value=SimpleNamespace(returncode=7)):
            ok, message = cgi_proxy.try_start_service()
        self.assertFalse(ok)
        self.assertIn("exit code 7", message)

    def test_cgi_base_is_injected_before_relative_assets(self):
        body = b"<!doctype html><html><head><title>fnAudio</title></head></html>"
        rewritten = cgi_proxy.inject_cgi_base(body)
        self.assertIn(b'<base href="/cgi/ThirdParty/fnaudio/index.cgi/">', rewritten)
        self.assertLess(rewritten.index(b"<base "), rewritten.index(b"<title>"))

    def test_existing_base_is_not_duplicated(self):
        body = b'<html><head><base href="/custom/"></head></html>'
        self.assertEqual(cgi_proxy.inject_cgi_base(body), body)

    def test_request_uri_suffix_wins_over_script_only_path_info(self):
        self.assertEqual(
            cgi_proxy.normalize_path_info(
                "/cgi/ThirdParty/fnaudio/index.cgi",
                "/cgi/ThirdParty/fnaudio/index.cgi/api/playback/queue",
            ),
            "/api/playback/queue",
        )

    def test_explicit_route_header_wins_when_cgi_paths_are_script_only(self):
        self.assertEqual(
            cgi_proxy.normalize_path_info(
                "/cgi/ThirdParty/fnaudio/index.cgi",
                "/cgi/ThirdParty/fnaudio/index.cgi/",
                "/api/playback/queue",
            ),
            "/api/playback/queue",
        )

    def test_explicit_root_route_wins_over_an_unrelated_request_uri(self):
        self.assertEqual(
            cgi_proxy.normalize_path_info(
                "/cgi/ThirdParty/fnaudio/index.cgi",
                "/unexpected/fnos/dispatch/path",
                "/",
            ),
            "/",
        )

    def test_proxy_route_rejects_traversal_controls_and_untrusted_values(self):
        class Exploding:
            def __str__(self):
                raise AssertionError("proxy routes must not be stringified")

        self.assertEqual(cgi_proxy.normalize_path_info(routed_path="/api/../settings"), "/")
        self.assertEqual(cgi_proxy.normalize_path_info(routed_path="/api/%2e%2e/settings"), "/")
        self.assertEqual(cgi_proxy.normalize_path_info(routed_path="/api\\settings"), "/")
        self.assertEqual(cgi_proxy.normalize_path_info(routed_path="/api\r\nX-Injected: yes"), "/")
        self.assertEqual(cgi_proxy.normalize_path_info(routed_path=Exploding()), "/")
        self.assertEqual(cgi_proxy.normalize_path_info(routed_path="/" + "x" * cgi_proxy.MAX_PROXY_ROUTE_CHARS), "/")

    def test_android_query_route_is_removed_before_backend_forwarding(self):
        route, query = cgi_proxy.extract_routed_query(
            "limit=50&__fnaudio_path=%2Fapi%2Flibrary&offset=100"
        )
        self.assertEqual(route, "/api/library")
        self.assertEqual(query, "limit=50&offset=100")

    def test_query_route_preserves_blank_and_repeated_values(self):
        route, query = cgi_proxy.extract_routed_query(
            "id=1&id=2&empty=&__fnaudio_path=%2Fapi%2Flibrary%2Fitems"
        )
        self.assertEqual(route, "/api/library/items")
        self.assertEqual(query, "id=1&id=2&empty=")

    def test_query_route_parser_is_bounded_before_materializing_fields(self):
        class Exploding:
            def __str__(self):
                raise AssertionError("query strings must not be stringified")

        self.assertEqual(cgi_proxy.extract_routed_query(Exploding()), ("", ""))
        self.assertEqual(
            cgi_proxy.extract_routed_query("x" * (cgi_proxy.MAX_PROXY_QUERY_STRING_CHARS + 1)),
            ("", ""),
        )
        too_many_fields = "&".join("id=%d" % index for index in range(cgi_proxy.MAX_PROXY_QUERY_FIELDS + 1))
        self.assertEqual(cgi_proxy.extract_routed_query(too_many_fields), ("", ""))

    def test_proxy_preserves_structured_backend_error_body(self):
        class ErrorResponse:
            status = 409
            reason = "Conflict"
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "X-Request-ID": "request-7",
                "Content-Length": "53",
            }

            def __init__(self):
                self.body = io.BytesIO(b'{"ok":false,"message":"state conflict"}')

            def read(self, size=-1):
                return self.body.read(size)

        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding="utf-8", newline="")
        previous = __import__("sys").stdout
        try:
            __import__("sys").stdout = output
            cgi_proxy.write_proxy_response(ErrorResponse(), "/api/state/user")
            output.flush()
        finally:
            __import__("sys").stdout = previous

        rendered = raw.getvalue().decode("utf-8")
        self.assertIn("Status: 409 Conflict", rendered)
        self.assertIn("Content-Type: application/json", rendered)
        self.assertIn('"message":"state conflict"', rendered)

    def test_oversized_rewritten_index_is_rejected_before_injection(self):
        class LargeResponse:
            status = 200
            reason = "OK"
            headers = {"Content-Type": "text/html"}

            def read(self, size=-1):
                if size != cgi_proxy.MAX_REWRITTEN_INDEX_BYTES + 1:
                    raise AssertionError("rewritten index read was not bounded")
                return b"x" * (cgi_proxy.MAX_REWRITTEN_INDEX_BYTES + 1)

        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding="utf-8", newline="")
        previous = __import__("sys").stdout
        try:
            __import__("sys").stdout = output
            cgi_proxy.write_proxy_response(LargeResponse(), "/index.html")
            output.flush()
        finally:
            __import__("sys").stdout = previous

        rendered = raw.getvalue().decode("utf-8")
        self.assertIn("Status: 413 Response Too Large", rendered)
        self.assertNotIn("<base ", rendered)

    def test_rewritten_index_drops_backend_content_encoding(self):
        class Response:
            status = 200
            reason = "OK"
            headers = {
                "Content-Type": "text/html; charset=utf-8",
                "Content-Encoding": "gzip",
                "Content-Length": "10",
            }

            def read(self, _size=-1):
                return b"<html><head></head></html>"

        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding="utf-8", newline="")
        previous = __import__("sys").stdout
        try:
            __import__("sys").stdout = output
            cgi_proxy.write_proxy_response(Response(), "/index.html")
            output.flush()
        finally:
            __import__("sys").stdout = previous

        rendered = raw.getvalue().decode("utf-8")
        self.assertNotIn("Content-Encoding:", rendered)
        self.assertIn("<base href=\"/cgi/ThirdParty/fnaudio/index.cgi/\">", rendered)

    def test_proxy_response_drops_injected_headers_and_invalid_status_parts(self):
        class Response:
            status = True
            reason = "bad\r\nX-Injected: yes"
            headers = {
                "Content-Type": "application/json",
                "X-Good": " value ",
                "X-Bad\r\nInjected": "yes",
                "X-Another": "ok\r\nInjected: yes",
            }

            def __init__(self):
                self.body = io.BytesIO(b'{"ok":false}')

            def read(self, _size=-1):
                return self.body.read(_size)

        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding="utf-8", newline="")
        previous = __import__("sys").stdout
        try:
            __import__("sys").stdout = output
            cgi_proxy.write_proxy_response(Response(), "/api/test")
            output.flush()
        finally:
            __import__("sys").stdout = previous

        rendered = raw.getvalue().decode("utf-8")
        self.assertIn("Status: 502 Bad Gateway", rendered)
        self.assertIn("X-Good: value", rendered)
        self.assertNotIn("X-Bad", rendered)
        self.assertNotIn("Injected: yes", rendered)

    def test_head_proxy_response_never_writes_backend_body(self):
        class Response:
            status = 200
            reason = "OK"
            headers = {"Content-Type": "application/json", "Content-Length": "12"}

            def __init__(self):
                self.read_calls = 0

            def read(self, _size=-1):
                self.read_calls += 1
                return b'{"ok":true}'

        response = Response()
        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding="utf-8", newline="")
        previous = __import__("sys").stdout
        try:
            __import__("sys").stdout = output
            cgi_proxy.write_proxy_response(response, "/api/health", head_only=True)
            output.flush()
        finally:
            __import__("sys").stdout = previous

        rendered = raw.getvalue().decode("utf-8")
        self.assertIn("Status: 200 OK", rendered)
        self.assertIn("Content-Length: 12", rendered)
        self.assertNotIn('{"ok":true}', rendered)
        self.assertEqual(response.read_calls, 0)

    def test_oversized_local_config_is_ignored_for_port_recovery(self):
        with __import__("tempfile").TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "wb") as handle:
                handle.write(b"{" + b"x" * cgi_proxy.MAX_LOCAL_CONFIG_BYTES + b"}")
            with patch.object(cgi_proxy, "header", side_effect=lambda name, default="": root if name == "TRIM_PKGETC" else default), \
                 patch.object(cgi_proxy.os.path, "isfile", side_effect=lambda candidate: candidate == path):
                self.assertEqual(cgi_proxy.service_port(), 53199)

    def test_missing_trim_pkg_etc_never_reads_relative_config_json(self):
        seen = []
        def missing(path):
            seen.append(path)
            raise OSError("missing")
        with patch.object(cgi_proxy, "header", return_value=""), \
             patch.object(cgi_proxy.os.path, "getsize", side_effect=missing):
            self.assertEqual(cgi_proxy.service_port(), 53199)
        self.assertTrue(seen)
        self.assertNotIn("config.json", seen)
        self.assertTrue(all(path.startswith(("/", "\\")) or ":\\" in path for path in seen))

    def test_non_object_local_config_is_ignored_for_port_recovery(self):
        with __import__("tempfile").TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("[]")
            with patch.object(cgi_proxy, "header", side_effect=lambda name, default="": root if name == "TRIM_PKGETC" else default), \
                 patch.object(cgi_proxy.os.path, "isfile", side_effect=lambda candidate: candidate == path):
                self.assertEqual(cgi_proxy.service_port(), 53199)

    def test_fractional_local_config_port_is_not_truncated(self):
        with __import__("tempfile").TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"server_port": 53199.5}')
            with patch.object(cgi_proxy, "header", side_effect=lambda name, default="": root if name == "TRIM_PKGETC" else default), \
                 patch.object(cgi_proxy.os.path, "isfile", side_effect=lambda candidate: candidate == path):
                self.assertEqual(cgi_proxy.service_port(), 53199)

    def test_proxy_rejects_unsupported_request_methods_before_backend_call(self):
        raw = io.BytesIO()
        output = __import__("io").TextIOWrapper(raw, encoding="utf-8", newline="")
        previous = __import__("sys").stdout
        previous_environ = dict(os.environ)
        try:
            os.environ["REQUEST_METHOD"] = "TRACE"
            os.environ["PATH_INFO"] = "/api/health"
            os.environ["CONTENT_LENGTH"] = "0"
            __import__("sys").stdout = output
            with patch.object(cgi_proxy.urllib.request, "urlopen", side_effect=AssertionError("backend must not be called")):
                cgi_proxy.main()
            output.flush()
        finally:
            os.environ.clear()
            os.environ.update(previous_environ)
            __import__("sys").stdout = previous
        self.assertIn("Status: 405 Method Not Allowed", raw.getvalue().decode("utf-8"))

    def test_proxy_uses_server_remote_addr_instead_of_client_forwarded_headers(self):
        raw = io.BytesIO()
        output = __import__("io").TextIOWrapper(raw, encoding="utf-8", newline="")
        previous = __import__("sys").stdout
        previous_environ = dict(os.environ)
        observed = {}

        class Response:
            status = 200
            headers = {"Content-Type": "application/json"}

            def __init__(self):
                self.read_once = False

            def read(self, _size=-1):
                if self.read_once:
                    return b""
                self.read_once = True
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        def fake_urlopen(request, timeout=0):
            observed["headers"] = dict(request.header_items())
            return Response()

        try:
            os.environ["REQUEST_METHOD"] = "GET"
            os.environ["PATH_INFO"] = "/api/access"
            os.environ["CONTENT_LENGTH"] = "0"
            os.environ["REMOTE_ADDR"] = "198.51.100.20"
            os.environ["HTTP_X_FORWARDED_FOR"] = "8.8.8.8"
            os.environ["HTTP_X_REAL_IP"] = "8.8.8.8"
            __import__("sys").stdout = output
            with patch.object(cgi_proxy.urllib.request, "urlopen", side_effect=fake_urlopen):
                cgi_proxy.main()
            output.flush()
        finally:
            os.environ.clear()
            os.environ.update(previous_environ)
            __import__("sys").stdout = previous
        self.assertEqual(observed["headers"].get("X-forwarded-for"), "198.51.100.20")
        self.assertNotIn("X-real-ip", {name.lower() for name in observed["headers"]})


class ServiceReadinessWaitTests(unittest.TestCase):
    """The CGI readiness wait runs in-process and must ignore wall-clock steps."""

    def run_wait(self, ready_probe, seconds=6):
        class FakeClock:
            def __init__(self):
                self.now = 0.0

            def monotonic(self):
                return self.now

            def sleep(self, delay):
                self.now += delay

            def time(self):
                raise AssertionError("an in-process wait must not read the wall clock")

        clock = FakeClock()
        probes = []

        def fake_ready(port):
            probes.append(port)
            return ready_probe(len(probes))

        with patch.object(cgi_proxy, "time", clock), patch.object(
            cgi_proxy, "local_service_ready", new=fake_ready
        ):
            result = cgi_proxy.wait_for_service(53199, seconds=seconds)
        return result, probes, clock

    def test_wait_spans_the_full_budget_on_the_monotonic_clock(self):
        result, probes, clock = self.run_wait(lambda count: False)
        self.assertFalse(result)
        # Fifteen in-loop probes 0.4s apart, then one last check once past the deadline.
        self.assertEqual(len(probes), 16)
        self.assertAlmostEqual(clock.now, 6.0, places=6)
        self.assertEqual(set(probes), {53199})

    def test_wait_returns_as_soon_as_the_service_answers(self):
        result, probes, clock = self.run_wait(lambda count: count >= 3)
        self.assertTrue(result)
        self.assertEqual(len(probes), 3)
        self.assertAlmostEqual(clock.now, 0.8, places=6)

    def test_wait_honours_a_shorter_budget(self):
        result, probes, clock = self.run_wait(lambda count: False, seconds=1)
        self.assertFalse(result)
        self.assertEqual(len(probes), 4)
        self.assertAlmostEqual(clock.now, 1.2, places=6)



if __name__ == "__main__":
    unittest.main()
