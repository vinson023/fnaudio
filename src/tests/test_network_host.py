import sys
import unittest

sys.path.insert(0, "app/server")

from network_host import is_private_host
from transcode import is_private_host as transcode_private_host


class NetworkHostTests(unittest.TestCase):
    def test_private_host_supports_ipv4_ipv6_and_host_ports(self):
        for value in ("198.51.100.8:5666", "10.0.0.2", "[fd00::1]:5666", "::1", "[fe80::1]"):
            self.assertTrue(is_private_host(value), value)

    def test_public_ipv6_is_not_truncated_to_a_false_private_host(self):
        self.assertFalse(is_private_host("[2409:8a60::1]:5666"))

    def test_transcode_uses_the_shared_network_host_classifier(self):
        self.assertIs(transcode_private_host, is_private_host)


if __name__ == "__main__":
    unittest.main()
