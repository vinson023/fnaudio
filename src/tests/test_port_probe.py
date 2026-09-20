import socket
import sys
import unittest

sys.path.insert(0, "app/server")

from port_probe import find_free_tcp_port, is_tcp_port_available


class _Socket:
    def __init__(self, port=43199, bind_error=False):
        self.port = port
        self.bind_error = bind_error
        self.closed = False
        self.bound = None

    def setsockopt(self, *_args):
        return None

    def bind(self, address):
        self.bound = address
        if self.bind_error:
            raise OSError("busy")

    def getsockname(self):
        return ("0.0.0.0", self.port)

    def close(self):
        self.closed = True


class PortProbeTests(unittest.TestCase):
    def test_availability_rejects_fractional_boolean_and_out_of_range_ports(self):
        factory = lambda *_args: self.fail("invalid ports must not open a socket")
        for value in (53199.5, True, 0, 65536, "53199"):
            self.assertFalse(is_tcp_port_available(value, 0, factory))

    def test_availability_handles_current_and_busy_ports_without_network(self):
        self.assertTrue(is_tcp_port_available(53199, 53199, lambda *_args: self.fail("should not probe")))
        busy = _Socket(bind_error=True)
        self.assertFalse(is_tcp_port_available(53199, 0, lambda *_args: busy))
        self.assertTrue(busy.closed)

    def test_free_port_uses_ephemeral_bind_and_closes_probe(self):
        probe = _Socket(port=45678)
        self.assertEqual(find_free_tcp_port(lambda *_args: probe), 45678)
        self.assertEqual(probe.bound, ("0.0.0.0", 0))
        self.assertTrue(probe.closed)


if __name__ == "__main__":
    unittest.main()
