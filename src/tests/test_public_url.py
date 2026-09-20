import sys
import unittest

sys.path.insert(0, "app/server")

from public_url import build_public_base_url


class PublicUrlTests(unittest.TestCase):
    def test_ipv6_host_and_port_are_preserved_with_brackets(self):
        value = build_public_base_url(
            "[2409:8a60::1]:5888", "HTTPS",
            local_address=lambda: "127.0.0.1",
            is_private_host=lambda host: host == "2409:8a60::1",
        )
        self.assertEqual(value, "https://[2409:8a60::1]:5888/cgi/ThirdParty/fnaudio/index.cgi")

    def test_public_host_falls_back_to_local_address_and_safe_defaults(self):
        value = build_public_base_url(
            "public.example", "ftp",
            local_address=lambda: "198.51.100.8",
            is_private_host=lambda _host: False,
        )
        self.assertEqual(value, "http://198.51.100.8:5666/cgi/ThirdParty/fnaudio/index.cgi")

    def test_does_not_stringify_untrusted_headers_or_resolver_values(self):
        class ExplodingString:
            def __str__(self):
                raise AssertionError("must not stringify")

        value = build_public_base_url(
            ExplodingString(), ExplodingString(),
            local_address=lambda: ExplodingString(),
            is_private_host=lambda _host: False,
        )
        self.assertEqual(value, "http://127.0.0.1:5666/cgi/ThirdParty/fnaudio/index.cgi")


if __name__ == "__main__":
    unittest.main()
