import sys
import unittest

sys.path.insert(0, "app/server")

from network_address import local_address


class _Socket:
    def __init__(self, address="198.51.100.8", fail=False):
        self.address = address
        self.fail = fail
        self.connected_to = None
        self.closed = False

    def connect(self, address):
        self.connected_to = address
        if self.fail:
            raise OSError("offline")

    def getsockname(self):
        return self.address, 12345

    def close(self):
        self.closed = True


class NetworkAddressTests(unittest.TestCase):
    def test_returns_outbound_address_and_closes_socket(self):
        probe = _Socket()
        self.assertEqual(local_address(lambda *_args: probe), "198.51.100.8")
        self.assertEqual(probe.connected_to, ("8.8.8.8", 80))
        self.assertTrue(probe.closed)

    def test_uses_loopback_when_probe_fails(self):
        probe = _Socket(fail=True)
        self.assertEqual(local_address(lambda *_args: probe), "127.0.0.1")
        self.assertTrue(probe.closed)


if __name__ == "__main__":
    unittest.main()
