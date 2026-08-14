import sys
import unittest
from unittest import mock

sys.path.insert(0, "app/server")
from dlna.network import fetch_lan, lan_http_url, optional_lan_http_url


class DlnaNetworkTests(unittest.TestCase):
    @mock.patch("dlna.network.socket.getaddrinfo", return_value=[(0, 0, 0, "", ("198.51.100.20", 80))])
    def test_accepts_lan_http_endpoint(self, _resolve):
        self.assertEqual(lan_http_url("http://speaker.local/description.xml"), "http://speaker.local/description.xml")

    @mock.patch("dlna.network.socket.getaddrinfo", return_value=[(0, 0, 0, "", ("8.8.8.8", 80))])
    def test_rejects_public_endpoint(self, _resolve):
        with self.assertRaisesRegex(ValueError, "LAN"):
            lan_http_url("https://example.test/media")

    def test_rejects_credentials_and_non_http_scheme(self):
        for value in ("file:///etc/passwd", "http://user:pass@198.51.100.2/x"):
            with self.assertRaises(ValueError):
                lan_http_url(value)

    def test_optional_endpoint_allows_clearing_next_uri(self):
        self.assertEqual(optional_lan_http_url(""), "")

    @mock.patch("dlna.network.lan_http_url", side_effect=lambda value: value)
    @mock.patch("dlna.network.urllib.request.build_opener")
    def test_fetch_rejects_oversized_response(self, build_opener, _validate):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "http://198.51.100.20/device.xml"
        response.headers = {"Content-Length": "9"}
        build_opener.return_value.open.return_value = response
        with self.assertRaisesRegex(ValueError, "size limit"):
            fetch_lan("http://198.51.100.20/device.xml", max_bytes=8)

    def test_redirect_handler_never_follows_location(self):
        from dlna.network import _NoRedirect

        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, "Found", {}, "http://8.8.8.8/x"))
