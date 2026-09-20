import sys
import unittest
sys.path.insert(0, "app/server")
from dlna.request_context import request_context

class DlnaRequestContextTests(unittest.TestCase):
    def test_forwarded_ip_has_priority_and_is_first_entry(self):
        result = request_context({"X-Forwarded-For": " 10.0.0.1, 10.0.0.2 ", "User-Agent": "u"}, ("127.0.0.1", 1))
        self.assertEqual(result["client_ip"], "10.0.0.1")
        self.assertEqual(result["user_agent"], "u")

    def test_direct_dlna_peer_cannot_forge_forwarded_ip(self):
        result = request_context(
            {"X-Forwarded-For": "8.8.8.8", "X-Real-IP": "8.8.4.4"},
            ("198.51.100.20", 1),
        )
        self.assertEqual(result["client_ip"], "198.51.100.20")

    def test_non_text_and_broken_headers_are_safe(self):
        class Broken:
            def get(self, key, default=""):
                raise RuntimeError("broken")
        self.assertEqual(request_context(Broken(), object())["client_ip"], "")

        class BrokenAddress(list):
            def __getitem__(self, index):
                raise ValueError("broken address")

        self.assertEqual(request_context({}, BrokenAddress(["x"]))["client_ip"], "")

    def test_context_fields_are_bounded(self):
        result = request_context({"User-Agent": "x" * 1000, "Range": "r" * 1000}, ("1.2.3.4", 1))
        self.assertEqual(len(result["user_agent"]), 300)
        self.assertEqual(len(result["range"]), 128)
