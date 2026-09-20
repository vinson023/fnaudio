import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "server")))

from metadata_remote_url_policy import public_metadata_http_url


class MetadataRemoteUrlPolicyTests(unittest.TestCase):
    def test_allows_public_http_urls_and_domain_names(self):
        self.assertEqual(
            public_metadata_http_url("https://img.example.test/cover.jpg"),
            "https://img.example.test/cover.jpg",
        )
        self.assertEqual(public_metadata_http_url("https://8.8.8.8/cover.jpg"), "https://8.8.8.8/cover.jpg")

    def test_the_gate_asks_the_resolver_again_for_every_url(self):
        """Repeated resolution is the security property, not waste to cache away.

        Measured on this host: one lookup per call for a hostname (13.8 ms for the first),
        no lookup at all for a literal address, and five paths on one host cost five
        lookups.  R74's shape - a display path where a stale answer is harmless - does not
        transfer here.  This gate's contract is to reject a hostname when any
        *currently*-resolved address is non-global, so a domain that flips from a public
        record to a private one between two requests has to be caught by the second one.
        A cache of any size, however short-lived, is precisely what lets that through.
        """
        rows = [(2, 1, 6, "", ("93.184.216.34", 443))]
        with mock.patch("metadata_remote_url_policy.socket.getaddrinfo",
                        side_effect=[rows, rows, rows]) as resolve:
            for index in range(3):
                url = "https://provider.example/x%d" % index
                self.assertEqual(public_metadata_http_url(url), url)
        self.assertEqual([call.args[0] for call in resolve.call_args_list],
                         ["provider.example"] * 3, "the gate reused a previous resolution")

        with mock.patch("metadata_remote_url_policy.socket.getaddrinfo") as resolve:
            self.assertEqual(public_metadata_http_url("https://8.8.8.8/cover.jpg"),
                             "https://8.8.8.8/cover.jpg")
        resolve.assert_not_called()

        with mock.patch("metadata_remote_url_policy.socket.getaddrinfo",
                        side_effect=[[(2, 1, 6, "", ("93.184.216.34", 443))],
                                     [(2, 1, 6, "", ("10.0.0.5", 443))]]) as resolve:
            self.assertNotEqual(public_metadata_http_url("https://rebind.example/a"), "",
                                "the first answer is public, so that URL is allowed")
            self.assertEqual(public_metadata_http_url("https://rebind.example/b"), "",
                             "the record moved into private space and the next URL must see it")
        self.assertEqual(resolve.call_count, 2)

    def test_rejects_hostname_resolving_to_private_address(self):
        with mock.patch(
            "metadata_remote_url_policy.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("198.51.100.20", 443))],
        ):
            self.assertEqual(public_metadata_http_url("https://image.example.test/cover.jpg"), "")

    def test_allows_hostname_when_dns_is_unavailable(self):
        with mock.patch(
            "metadata_remote_url_policy.socket.getaddrinfo",
            side_effect=OSError("temporary DNS failure"),
        ):
            self.assertEqual(
                public_metadata_http_url("https://image.example.test/cover.jpg"),
                "https://image.example.test/cover.jpg",
            )

    def test_rejects_local_or_credentialed_urls(self):
        for value in (
            "http://127.0.0.1:8080/private",
            "http://[::1]/private",
            "http://198.51.100.9/private",
            "http://169.254.169.254/latest/meta-data",
            "https://localhost/private",
            "https://catalog.localhost/private",
            "https://user:password@img.example.test/cover.jpg",
            "file:///etc/passwd",
        ):
            self.assertEqual(public_metadata_http_url(value), "", value)

if __name__ == "__main__":
    unittest.main()
