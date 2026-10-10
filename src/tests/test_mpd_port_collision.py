"""MPD must never lose its TCP port to a connection made by its own client.

R195 evidence on 198.51.100.24: the app process held an established loopback
pair ``127.0.0.1:56660 <-> 127.0.0.1:56660``, because the kernel had handed
MPD's own listening port to our outbound connect.  MPD could no longer bind
(``Failed to bind to '127.0.0.1:56660'; Address already in use``) and every
later start died with ``MPD exited before becoming ready`` until the whole app
process was restarted, which is how the user lost playback for the rest of the
session.  Two guards keep that from happening again: the client never takes
MPD's port as its source port, and the service re-picks a port outside the
kernel ephemeral range before it writes ``mpd.conf``.
"""

import inspect
import sys
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from playback import mpd_client
from playback.mpd_client import (
    MAX_MPD_LOCAL_PORT_ATTEMPTS,
    MpdConnection,
    _draw_local_port,
    _mpd_client_socket,
)
from services import mpd_service as mpd_module
from services.mpd_service import (
    DEFAULT_EPHEMERAL_RANGE,
    EPHEMERAL_RANGE_PATH,
    MAX_FALLBACK_PORT_CANDIDATES,
    MpdService,
)

MPD_PORT = 56660
HOST = "127.0.0.1"


def build_service():
    """Build a service without touching MPD discovery or a real data directory."""
    with mock.patch.object(MpdService, "_select_port", return_value=MPD_PORT), mock.patch.object(
        MpdService, "_find_binary", return_value="/usr/bin/mpd"
    ):
        return MpdService({"library_paths": ["/vol2/1000/music"], "mpd_port": MPD_PORT})


class FakeHandle:
    def __init__(self, payload):
        self._payload = payload

    def read(self, *_args, **_kwargs):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class EphemeralRangeTests(unittest.TestCase):
    def test_the_range_is_read_from_the_documented_proc_file(self):
        with mock.patch.object(mpd_module, "open", return_value=FakeHandle("32768\t60999\n")) as handle:
            self.assertEqual(mpd_module._ephemeral_port_range(), (32768, 60999))
        handle.assert_called_once_with(EPHEMERAL_RANGE_PATH, "r", encoding="utf-8")

    def test_an_unreadable_or_malformed_range_falls_back_to_the_default(self):
        cases = [
            ("missing proc file", OSError(2, "no such file")),
            ("non numeric", "not a range\n"),
            ("single number", "32768\n"),
            ("below the privileged floor", "400 500\n"),
            ("inverted bounds", "60999 32768\n"),
            ("above the wire limit", "70000 80000\n"),
        ]
        for label, payload in cases:
            with self.subTest(label):
                if isinstance(payload, OSError):
                    patcher = mock.patch.object(mpd_module, "open", side_effect=payload)
                else:
                    patcher = mock.patch.object(mpd_module, "open", return_value=FakeHandle(payload))
                with patcher:
                    self.assertEqual(mpd_module._ephemeral_port_range(), DEFAULT_EPHEMERAL_RANGE)

    def test_candidates_come_from_outside_the_range_and_are_capped(self):
        with mock.patch.object(mpd_module, "_ephemeral_port_range", return_value=(32768, 60999)):
            candidates = mpd_module._candidate_fallback_ports()
        self.assertGreaterEqual(len(candidates), 1)
        self.assertEqual(len(candidates), 2 * MAX_FALLBACK_PORT_CANDIDATES)
        self.assertEqual(candidates[0], 61000)
        for port in candidates:
            self.assertFalse(32768 <= port <= 60999, port)
            self.assertTrue(1024 <= port <= 65535, port)
        self.assertEqual(len(set(candidates)), len(candidates))

    def test_the_upper_block_is_capped_so_the_lower_block_is_reachable(self):
        # A range pushed to the top of the wire still leaves the block below it.
        with mock.patch.object(mpd_module, "_ephemeral_port_range", return_value=(32768, 65535)):
            candidates = mpd_module._candidate_fallback_ports()
        self.assertEqual(len(candidates), MAX_FALLBACK_PORT_CANDIDATES)
        self.assertEqual(candidates[0], 1024)
        self.assertEqual(candidates[-1], 1023 + MAX_FALLBACK_PORT_CANDIDATES)


class FallbackPortSelectionTests(unittest.TestCase):
    def setUp(self):
        self.service = build_service()

    def test_the_first_free_candidate_above_the_range_wins(self):
        probed = []

        def available(_host, port):
            probed.append(port)
            return port == 61002

        with mock.patch.object(mpd_module, "_ephemeral_port_range", return_value=(32768, 60999)):
            with mock.patch.object(mpd_module, "_tcp_port_available", side_effect=available):
                self.assertEqual(self.service._select_fallback_port(), 61002)
        self.assertEqual(probed[:3], [61000, 61001, 61002])

    def test_every_candidate_taken_falls_back_to_a_random_port(self):
        with mock.patch.object(mpd_module, "_candidate_fallback_ports", return_value=[61000]):
            with mock.patch.object(mpd_module, "_tcp_port_available", return_value=False):
                with mock.patch.object(mpd_module.socket, "socket") as factory:
                    instance = factory.return_value.__enter__.return_value
                    instance.getsockname.return_value = (HOST, 34687)
                    self.assertEqual(self.service._select_fallback_port(), 34687)
        instance.bind.assert_called_once_with((HOST, 0))

    def test_select_port_hands_a_contested_port_to_the_fallback_selector(self):
        # This is the line that used to end in a random bind inside the ephemeral
        # range, i.e. a number our own client could steal again.
        with mock.patch.object(mpd_module, "_tcp_port_available", return_value=False):
            with mock.patch.object(MpdService, "_reap_legacy_instances", return_value=False):
                with mock.patch.object(MpdService, "_select_fallback_port", return_value=61000) as pick:
                    self.assertEqual(self.service._select_port(MPD_PORT), 61000)
        pick.assert_called_once_with()


class EnsureBindablePortTests(unittest.TestCase):
    def setUp(self):
        self.service = build_service()

    def test_a_bindable_port_leaves_the_service_and_its_config_alone(self):
        with mock.patch.object(mpd_module, "_tcp_port_available", return_value=True):
            with mock.patch.object(MpdService, "_reap_legacy_instances") as reap:
                with mock.patch.object(MpdService, "_select_fallback_port") as pick:
                    self.service._ensure_bindable_port()
        reap.assert_not_called()
        pick.assert_not_called()
        self.assertEqual(self.service.port, MPD_PORT)
        self.assertEqual(self.service.config["mpd_port"], MPD_PORT)

    def test_a_legacy_mpd_is_reaped_before_the_port_moves(self):
        # First probe: MPD's own port from the previous payload layout.  Second
        # probe, after reaping: free again, so nothing moves.
        with mock.patch.object(
            mpd_module, "_tcp_port_available", side_effect=[False, True]
        ) as available:
            with mock.patch.object(MpdService, "_reap_legacy_instances", return_value=True) as reap:
                with mock.patch.object(MpdService, "_select_fallback_port") as pick:
                    self.service._ensure_bindable_port()
        reap.assert_called_once_with()
        pick.assert_not_called()
        self.assertEqual(available.call_args_list[0][0], (HOST, MPD_PORT))
        self.assertEqual(self.service.port, MPD_PORT)

    def test_a_stranger_on_the_port_moves_mpd_outside_the_ephemeral_range(self):
        def available(_host, port):
            return port != MPD_PORT

        with mock.patch.object(mpd_module, "_ephemeral_port_range", return_value=(32768, 60999)):
            with mock.patch.object(mpd_module, "_tcp_port_available", side_effect=available):
                with mock.patch.object(MpdService, "_reap_legacy_instances", return_value=False):
                    self.service._ensure_bindable_port()
        low, high = DEFAULT_EPHEMERAL_RANGE
        self.assertNotEqual(self.service.port, MPD_PORT)
        self.assertFalse(low <= self.service.port <= high, self.service.port)
        self.assertEqual(self.service.config["mpd_port"], self.service.port)


class ClientSourcePortTests(unittest.TestCase):
    def connect(self, **kwargs):
        return mock.Mock(**kwargs)

    def test_mpd_own_port_is_never_used_as_our_source_port(self):
        # The kernel keeps offering the very port MPD listens on; the guard has to
        # draw again instead of connecting to itself.
        drawn = [MPD_PORT, MPD_PORT, 61234]
        sock = self.connect()
        with mock.patch.object(mpd_client, "_draw_local_port", side_effect=drawn):
            with mock.patch.object(mpd_client.socket, "create_connection", return_value=sock) as made:
                self.assertIs(_mpd_client_socket(HOST, MPD_PORT, 2.0), sock)
        self.assertEqual(made.call_count, 1)
        self.assertEqual(made.call_args[0][0], (HOST, MPD_PORT))
        self.assertEqual(made.call_args[1]["source_address"], (HOST, 61234))

    def test_a_source_port_bind_conflict_retries_with_another_number(self):
        first = self.connect()
        second = self.connect()
        taken = OSError(98, "Address already in use")
        with mock.patch.object(
            mpd_client, "_draw_local_port", side_effect=[61001, 61002]
        ):
            with mock.patch.object(
                mpd_client.socket, "create_connection", side_effect=[taken, second]
            ) as made:
                self.assertIs(_mpd_client_socket(HOST, MPD_PORT, 2.0), second)
        self.assertEqual(made.call_count, 2)
        self.assertEqual(made.call_args_list[1][1]["source_address"], (HOST, 61002))
        first.close.assert_not_called()

    def test_no_drawable_port_falls_back_to_the_plain_connect(self):
        sock = self.connect()
        with mock.patch.object(mpd_client, "_draw_local_port", return_value=None):
            with mock.patch.object(mpd_client.socket, "create_connection", return_value=sock) as made:
                self.assertIs(_mpd_client_socket(HOST, MPD_PORT, 2.0), sock)
        self.assertEqual(made.call_count, 1)
        self.assertNotIn("source_address", made.call_args[1])

    def test_the_avoidance_loop_is_bounded_and_then_connects_anyway(self):
        # A kernel that only ever offers MPD's own port must not turn a status
        # read into an infinite loop: the guard draws a bounded number of times
        # and then connects the way it always did.
        sock = self.connect()
        with mock.patch.object(mpd_client, "MAX_MPD_LOCAL_PORT_ATTEMPTS", 3):
            with mock.patch.object(mpd_client, "_draw_local_port", return_value=MPD_PORT) as draw:
                with mock.patch.object(
                    mpd_client.socket, "create_connection", return_value=sock
                ) as made:
                    self.assertIs(_mpd_client_socket(HOST, MPD_PORT, 2.0), sock)
        self.assertEqual(draw.call_count, 3)
        self.assertEqual(made.call_count, 1)
        self.assertNotIn("source_address", made.call_args[1])

    def test_a_real_bind_only_probe_never_answers_on_the_mpd_port(self):
        drawn = _draw_local_port(HOST)
        self.assertIsInstance(drawn, int)
        self.assertTrue(1 <= drawn <= 65535)
        self.assertNotEqual(drawn, MPD_PORT)

    def test_an_unbindable_host_reports_no_port_instead_of_raising(self):
        self.assertIsNone(_draw_local_port("256.256.256.256"))

    def test_enter_connects_through_the_port_guard(self):
        connection = MpdConnection(HOST, MPD_PORT, 1.0)
        sock = self.connect()
        file = mock.Mock()
        sock.makefile.return_value = file
        file.readline.return_value = b"OK MPD 0.23.0\n"
        with mock.patch.object(mpd_client, "_mpd_client_socket", return_value=sock) as guarded:
            with connection:
                self.assertIs(connection.sock, sock)
        guarded.assert_called_once_with(HOST, MPD_PORT, 1.0)


class WiringTests(unittest.TestCase):
    """Source-level assertions for the two call sites that make the guards live."""

    def test_start_locks_the_port_before_the_config_is_written(self):
        body = inspect.getsource(MpdService._start_locked)
        guard = body.find("self._ensure_bindable_port()")
        write = body.find("self.ensure_config()")
        self.assertGreaterEqual(guard, 0, "MpdService._start_locked must call _ensure_bindable_port")
        self.assertGreaterEqual(write, 0)
        self.assertLess(guard, write, "the port has to be settled before mpd.conf is written")

    def test_the_client_never_connects_without_a_source_port_choice(self):
        enter = inspect.getsource(MpdConnection.__enter__)
        self.assertIn("_mpd_client_socket(self.host, self.port, self.timeout)", enter)
        self.assertNotIn("socket.create_connection((self.host", enter)

    def test_create_connection_stays_the_only_connect_primitive(self):
        # test_mpd_status patches socket.create_connection, so the guard may add
        # source_address but must not switch to a hand-rolled socket + connect.
        source = inspect.getsource(_mpd_client_socket)
        self.assertGreaterEqual(source.count("socket.create_connection"), 2)
        self.assertNotIn(".connect((", source)


if __name__ == "__main__":
    unittest.main()
