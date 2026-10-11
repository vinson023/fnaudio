# -*- coding: utf-8 -*-
"""R204 discriminating suite: the CGI gateway must forward browser revalidation."""
import importlib.util
import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "ui" / "cgi_proxy.py"
SPEC = importlib.util.spec_from_file_location("fnaudio_cgi_proxy_conditional", MODULE_PATH)
cgi_proxy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cgi_proxy)

CGI_ENV = (
    "REQUEST_METHOD", "PATH_INFO", "QUERY_STRING", "SERVER_PROTOCOL",
    "CONTENT_LENGTH", "CONTENT_TYPE", "HTTP_ACCEPT", "HTTP_RANGE",
    "HTTP_IF_NONE_MATCH", "HTTP_IF_MODIFIED_SINCE", "HTTP_HOST",
    "HTTP_X_FORWARDED_PROTO", "REMOTE_ADDR", "HTTP_AUTHORIZATION",
    "HTTP_COOKIE", "TRIM_API_TOKEN", "HTTP_TRIM_TOKEN", "HTTP_X_TRIM_TOKEN",
    "HTTP_X_FNAUDIO_TRIM_TOKEN", "HTTP_X_FNAUDIO_PATH", "REQUEST_URI",
)


class FakeUpstream:
    """Minimal stand-in for a urllib response object."""

    def __init__(self, status=304, reason="Not Modified", headers=None, body=b""):
        self.status = status
        self.reason = reason
        self.headers = headers if headers is not None else {
            "ETag": '"size-123-mtime-456"',
            "Cache-Control": "no-cache",
            "Content-Type": "text/javascript",
        }
        self._body = body
        self.closed = False

    def read(self, size=-1):
        chunk, self._body = self._body[:size], self._body[size:] if size and size > 0 else b""
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False


class CapturedRequest:
    def __init__(self):
        self.requests = []

    def urlopen(self, request, timeout=None):
        self.requests.append(request)
        return FakeUpstream()

    def headers_for(self, index=0):
        request = self.requests[index]
        # urllib.request.Request capitalizes header names ("If-none-match"), so
        # the assertion helper compares them case-insensitively.
        return {name.lower(): value for name, value in request.header_items()}


class CgiProxyConditionalHeaderTests(unittest.TestCase):
    def setUp(self):
        self.saved = {name: os.environ.get(name) for name in CGI_ENV}
        for name in CGI_ENV:
            os.environ.pop(name, None)

    def tearDown(self):
        for name in CGI_ENV:
            os.environ.pop(name, None)
            if self.saved[name] is not None:
                os.environ[name] = self.saved[name]

    def execute_main(self):
        """Run cgi_proxy.main() and return (stdout_text, stdout_bytes_written)."""
        text = io.StringIO()
        raw = io.BytesIO()
        stream = DualStream(text, raw)
        real_stdout = cgi_proxy.sys.stdout
        real_stdin = cgi_proxy.sys.stdin
        try:
            with patch.object(cgi_proxy.sys, "stdout", stream), patch.object(cgi_proxy.sys, "stdin", FakeStdin()):
                cgi_proxy.main()
        finally:
            cgi_proxy.sys.stdout = real_stdout
            cgi_proxy.sys.stdin = real_stdin
        return text.getvalue(), raw.getvalue()

    # --- whitelist membership -------------------------------------------------
    def test_conditional_headers_are_whitelisted_with_exact_upstream_names(self):
        self.assertIn(("HTTP_IF_NONE_MATCH", "If-None-Match"), list(cgi_proxy.PROXY_REQUEST_HEADERS))
        self.assertIn(("HTTP_IF_MODIFIED_SINCE", "If-Modified-Since"), list(cgi_proxy.PROXY_REQUEST_HEADERS))
        self.assertEqual(
            set(cgi_proxy.CONDITIONAL_REQUEST_HEADERS),
            {"If-None-Match", "If-Modified-Since"},
        )

    def test_main_iterates_the_shared_whitelist_instead_of_an_inline_tuple(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertEqual(source.count('("HTTP_IF_NONE_MATCH", "If-None-Match")'), 1)
        self.assertEqual(source.count('("HTTP_IF_MODIFIED_SINCE", "If-Modified-Since")'), 1)
        self.assertIn("for env_name, http_name in PROXY_REQUEST_HEADERS:", source)
        self.assertNotIn('for env_name, http_name in (\n        ("CONTENT_TYPE"', source)

    # --- real forwarding behaviour -------------------------------------------
    def test_if_none_match_reaches_the_upstream_request(self):
        os.environ.update({
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/app.js",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "CONTENT_LENGTH": "0",
            "HTTP_IF_NONE_MATCH": 'W/"size-123-mtime-456"',
        })
        upstream = CapturedRequest()
        with patch.object(cgi_proxy.urllib.request, "urlopen", upstream.urlopen):
            text, raw = self.execute_main()
        self.assertEqual(upstream.headers_for().get("if-none-match"), 'W/"size-123-mtime-456"')
        self.assertIn("Status: 304 Not Modified", text)
        self.assertIn("ETag:", text)
        self.assertEqual(raw, b"")

    def test_if_modified_since_reaches_the_upstream_request(self):
        os.environ.update({
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/app.css",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "CONTENT_LENGTH": "0",
            "HTTP_IF_MODIFIED_SINCE": "Sun, 11 Oct 2026 12:00:00 GMT",
        })
        upstream = CapturedRequest()
        with patch.object(cgi_proxy.urllib.request, "urlopen", upstream.urlopen):
            self.execute_main()
        self.assertEqual(upstream.headers_for().get("if-modified-since"), "Sun, 11 Oct 2026 12:00:00 GMT")

    def test_absent_conditional_headers_are_not_invented(self):
        os.environ.update({
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/api/library/status",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "CONTENT_LENGTH": "0",
        })
        upstream = CapturedRequest()
        with patch.object(cgi_proxy.urllib.request, "urlopen", upstream.urlopen):
            self.execute_main()
        headers = upstream.headers_for()
        self.assertNotIn("if-none-match", headers)
        self.assertNotIn("if-modified-since", headers)

    # --- the whitelist stays a whitelist -------------------------------------
    def test_conditional_header_crlf_injection_is_dropped(self):
        os.environ.update({
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/app.js",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "CONTENT_LENGTH": "0",
            "HTTP_IF_NONE_MATCH": 'etag\r\nX-Injected: yes',
            "HTTP_IF_MODIFIED_SINCE": "date\nContent-Length: 0",
        })
        upstream = CapturedRequest()
        with patch.object(cgi_proxy.urllib.request, "urlopen", upstream.urlopen):
            self.execute_main()
        headers = upstream.headers_for()
        self.assertNotIn("if-none-match", headers)
        self.assertNotIn("if-modified-since", headers)
        self.assertNotIn("x-injected", headers)

    def test_oversized_conditional_header_is_dropped(self):
        os.environ.update({
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/app.js",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "CONTENT_LENGTH": "0",
            "HTTP_IF_NONE_MATCH": '"' + "x" * (cgi_proxy.MAX_PROXY_REQUEST_HEADER_VALUE_CHARS + 1) + '"',
        })
        upstream = CapturedRequest()
        with patch.object(cgi_proxy.urllib.request, "urlopen", upstream.urlopen):
            self.execute_main()
        self.assertNotIn("if-none-match", upstream.headers_for())

    def test_cookie_and_authorization_are_not_forwarded_upstream(self):
        os.environ.update({
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/app.js",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "CONTENT_LENGTH": "0",
            "HTTP_COOKIE": "session=secret; theme=dark",
            "HTTP_AUTHORIZATION": "Bearer secret-token",
            "HTTP_IF_NONE_MATCH": '"etag-value"',
        })
        upstream = CapturedRequest()
        with patch.object(cgi_proxy.urllib.request, "urlopen", upstream.urlopen):
            self.execute_main()
        headers = upstream.headers_for()
        self.assertNotIn("cookie", headers)
        self.assertEqual(headers.get("if-none-match"), '"etag-value"')
        self.assertEqual(headers.get("x-fnaudio-trim-token"), "secret-token")

    def test_unsupported_response_header_filter_still_drops_connection(self):
        upstream = FakeUpstream(headers={"ETag": '"x"', "Connection": "close", "X-Raw": "ok"})
        text = io.StringIO()
        real_stdout = cgi_proxy.sys.stdout
        try:
            with patch.object(cgi_proxy.sys, "stdout", DualStream(text, io.BytesIO())):
                cgi_proxy.write_proxy_response(upstream, "/app.js", False)
        finally:
            cgi_proxy.sys.stdout = real_stdout
        self.assertIn("ETag:", text.getvalue())
        self.assertNotIn("Connection:", text.getvalue())


class FakeStdin:
    """CGI stdin: main() reads through .buffer only when CONTENT_LENGTH is set."""

    buffer = io.BytesIO(b"")


class DualStream:
    """sys.stdout replacement: writes str to a text sink, bytes to a raw sink."""

    def __init__(self, text, raw):
        self._text = text
        self._raw = raw
        self.buffer = raw

    def write(self, value):
        if isinstance(value, (bytes, bytearray)):
            self._raw.write(value)
        else:
            self._text.write(value)
        return len(value)

    def flush(self):
        self._text.flush()
        self._raw.flush()


if __name__ == "__main__":
    unittest.main()
