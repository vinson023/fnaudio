import importlib.util
import os
from pathlib import Path
import unittest


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


if __name__ == "__main__":
    unittest.main()
