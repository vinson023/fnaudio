# -*- coding: utf-8 -*-
"""The offline gate must actually stay offline.

`tools/test_offline.ps1` promises a run with no external dependencies, and until
this guard existed the promise was only true by accident: two metadata tests let
their background workers call the real providers, so a normal gate run sent live
HTTPS requests to seven public music services, and a leaked DLNA subscription
thread dialed a fake customer's router address.  Both were invisible -- the
requests either failed or "worked" -- and both made the suite's duration and its
assertions depend on the network.

Discovery imports every test module before the first test runs, so installing the
policy from this module covers the whole run regardless of module order.  Names
that cannot resolve (`.test`, `.invalid`) are deliberately not blocked: a reserved
lookup answers instantly with no egress, while the harm this guard exists for is a
dial that reaches a live host.
"""
import socket
import unittest

_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex
_original_create_connection = socket.create_connection

INTERNET_FAMILIES = (socket.AF_INET, socket.AF_INET6)
LOOPBACK_PREFIXES = ("127.", "::1", "0:0:0:0:0:0:0:1")
LOOPBACK_EXACT = {"", "::", "0.0.0.0", "localhost"}

# Blocked attempts are counted as well as refused.  A test that asserts a request
# is rejected for a non-LAN host legitimately tries to dial, so the count is a
# diagnostic rather than an assertion; `tools` reads it when auditing the gate.
external_access_attempts = []
MAX_RECORDED_ATTEMPTS = 64


class ExternalNetworkAccess(RuntimeError):
    """Raised instead of dialing out of the loopback interface."""


def is_loopback_address(address):
    text = str(address).strip("[]")
    return text.startswith(LOOPBACK_PREFIXES) or text in LOOPBACK_EXACT


def _refuse(host, port, via):
    if is_loopback_address(host):
        return None
    target = "%s:%s" % (host, port)
    if len(external_access_attempts) < MAX_RECORDED_ATTEMPTS:
        external_access_attempts.append("%s %s" % (via, target))
    return ExternalNetworkAccess(
        "the offline gate tried to leave loopback: %s %s" % (via, target))


def _guarded_connect(self, address, *args, **kwargs):
    family = getattr(self, "family", None)
    if isinstance(address, tuple) and len(address) >= 2 and family in INTERNET_FAMILIES:
        error = _refuse(address[0], address[1], "socket.connect")
        if error is not None:
            raise error
    return _original_connect(self, address, *args, **kwargs)


def _guarded_connect_ex(self, address, *args, **kwargs):
    family = getattr(self, "family", None)
    if isinstance(address, tuple) and len(address) >= 2 and family in INTERNET_FAMILIES:
        error = _refuse(address[0], address[1], "socket.connect_ex")
        if error is not None:
            raise error
    return _original_connect_ex(self, address, *args, **kwargs)


def _guarded_create_connection(address, *args, **kwargs):
    if isinstance(address, tuple) and len(address) >= 2:
        error = _refuse(address[0], address[1], "create_connection")
        if error is not None:
            raise error
    return _original_create_connection(address, *args, **kwargs)


socket.socket.connect = _guarded_connect
socket.socket.connect_ex = _guarded_connect_ex
socket.create_connection = _guarded_create_connection


class SocketGuardTests(unittest.TestCase):
    def test_the_guard_refuses_a_dial_beyond_loopback(self):
        for host in ("musicbrainz.org", "198.51.100.20", "8.8.8.8"):
            with self.subTest(host=host):
                with self.assertRaises(ExternalNetworkAccess):
                    socket.create_connection((host, 443), 0.1)
                with self.assertRaises(ExternalNetworkAccess):
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                        sock.connect((host, 443))

    def test_loopback_traffic_still_works(self):
        """A guard that also blocks local sockets would be removed, not fixed."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            with socket.create_connection(("127.0.0.1", port), 2.0) as client:
                client.sendall(b"ping")
                server, _address = listener.accept()
                with server:
                    self.assertEqual(server.recv(4), b"ping")
                    server.sendall(b"pong")
                    self.assertEqual(client.recv(4), b"pong")

    def test_the_guard_is_installed_over_the_real_functions(self):
        """The wrappers replace the real entry points, and hold them for opt-out."""
        self.assertIs(socket.socket.connect, _guarded_connect)
        self.assertIs(socket.socket.connect_ex, _guarded_connect_ex)
        self.assertIs(socket.create_connection, _guarded_create_connection)
        self.assertTrue(callable(_original_connect))
        self.assertTrue(callable(_original_create_connection))

    def test_unrelated_socket_families_are_not_intercepted(self):
        first, second = socket.socketpair()
        try:
            first.sendall(b"x")
            self.assertEqual(second.recv(1), b"x")
        finally:
            first.close()
            second.close()

    def test_the_production_http_path_cannot_leave_loopback(self):
        """The guard has to bite on the stack the product actually uses.

        urllib reaches the wire through http.client, which keeps its own alias for
        `socket.create_connection`, so patching only the module attribute would be
        enough to miss it.  This goes through the real metadata request function,
        which is the path the two fixed tests were using to dial seven music
        services.
        """
        import urllib.request

        from metadata_service import _open_metadata_url

        with self.assertRaises(ExternalNetworkAccess):
            _open_metadata_url(urllib.request.Request("https://musicbrainz.org/ws/2/recording"), 2.0)
        self.assertTrue(any("musicbrainz.org:443" in item for item in external_access_attempts[-2:]),
                        "the dial was refused somewhere other than the socket layer")

    def test_a_refused_attempt_is_recorded_for_the_gate_audit(self):
        before = len(external_access_attempts)
        with self.assertRaises(ExternalNetworkAccess):
            socket.create_connection(("203.0.113.9", 80), 0.1)
        self.assertEqual(external_access_attempts[before:], ["create_connection 203.0.113.9:80"])
        loopback_before = len(external_access_attempts)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            with socket.create_connection(("127.0.0.1", listener.getsockname()[1]), 2.0):
                pass
        self.assertEqual(len(external_access_attempts), loopback_before, "loopback is not a violation")


if __name__ == "__main__":
    unittest.main()
