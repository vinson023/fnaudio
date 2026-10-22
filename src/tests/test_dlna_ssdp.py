import socket
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from dlna.ssdp import SsdpService


class SsdpServiceTests(unittest.TestCase):
    def test_announce_alive_rebroadcasts_all_discovery_targets(self):
        service = SsdpService(lambda: "http://127.0.0.1:18080")
        sock = mock.MagicMock()
        sock.__enter__.return_value = sock
        with mock.patch("dlna.ssdp.socket.socket", return_value=sock):
            service.announce_alive()
        packets = [call.args[0] for call in sock.sendto.call_args_list]
        self.assertEqual(len(packets), 9)
        self.assertTrue(all(b"NTS: ssdp:alive\r\n" in packet for packet in packets))

    def test_start_failure_clears_thread_reference(self):
        service = SsdpService(lambda: "http://127.0.0.1:18080")
        with mock.patch("dlna.ssdp.threading.Thread", side_effect=RuntimeError("no threads")):
            with self.assertRaises(RuntimeError):
                service.start()
        self.assertIsNone(service._thread)
        self.assertTrue(service._stop.is_set())

    def test_concurrent_start_creates_one_responder_thread(self):
        service = SsdpService(lambda: "http://127.0.0.1:18080")
        real_thread = threading.Thread
        entered = threading.Event()
        release = threading.Event()
        created = []

        class DelayedThread:
            def __init__(self, **_kwargs):
                self.started = False
                created.append(self)

            def start(self):
                entered.set()
                release.wait(1)
                self.started = True

            def is_alive(self):
                return self.started

        with mock.patch("dlna.ssdp.threading.Thread", DelayedThread):
            first = real_thread(target=service.start)
            first.start()
            self.assertTrue(entered.wait(1))
            second = real_thread(target=service.start)
            second.start()
            release.set()
            first.join(1)
            second.join(1)
        self.assertEqual(len(created), 1)

    def test_bind_failure_closes_created_socket(self):
        service = SsdpService(lambda: "http://127.0.0.1:18080")
        sock = mock.MagicMock()
        sock.bind.side_effect = OSError("port busy")
        with mock.patch.object(service, "_announce"), mock.patch(
            "dlna.ssdp.socket.socket", return_value=sock
        ):
            service._run()
        sock.close.assert_called_once_with()

    def test_stop_clears_finished_thread_reference(self):
        service = SsdpService(lambda: "http://127.0.0.1:18080")
        thread = mock.Mock()
        thread.is_alive.return_value = False
        service._thread = thread
        with mock.patch.object(service, "_announce"):
            service.stop()
        thread.join.assert_called_once_with(timeout=1.5)
        self.assertIsNone(service._thread)

    def test_stop_does_not_join_current_thread(self):
        service = SsdpService(lambda: "http://127.0.0.1:18080")
        current = mock.Mock()
        current.is_alive.return_value = True
        service._thread = current
        with mock.patch.object(service, "_announce"), mock.patch(
            "dlna.ssdp.threading.current_thread", return_value=current
        ):
            service.stop()
        current.join.assert_not_called()
        self.assertIs(current, service._thread)

    def test_failed_search_response_does_not_stop_listener(self):
        service = SsdpService(lambda: "http://127.0.0.1:18080", roles=("server",))
        sock = mock.MagicMock()
        sock.recvfrom.side_effect = [
            (b"M-SEARCH * HTTP/1.1\r\nST: ssdp:all\r\n\r\n", ("127.0.0.1", 1900)),
            socket.timeout(),
        ]
        sock.sendto.side_effect = [OSError("renderer disappeared"), None, None, None]
        with mock.patch("dlna.ssdp.socket.socket", return_value=sock), mock.patch.object(
            service, "_announce"
        ), mock.patch.object(service._stop, "is_set", side_effect=[False, False, True]):
            service._run()
        self.assertEqual(sock.sendto.call_count, 4)


    def test_transient_receive_error_keeps_the_listener_answering(self):
        """An ICMP-derived reset must not end discovery for the process lifetime."""
        service = SsdpService(lambda: "http://127.0.0.1:18080", roles=("server",))
        sock = mock.MagicMock()
        sock.recvfrom.side_effect = [
            ConnectionResetError("previous send hit a dead host"),
            (b"M-SEARCH * HTTP/1.1\r\nST: ssdp:all\r\n\r\n", ("127.0.0.1", 5000)),
            socket.timeout(),
        ]
        with mock.patch("dlna.ssdp.socket.socket", return_value=sock), mock.patch.object(
            service, "_announce"
        ), mock.patch.object(
            service._stop, "is_set", side_effect=[False, False, False, True]
        ), mock.patch.object(service._stop, "wait", return_value=False) as paused:
            service._run()
        paused.assert_called_once_with(0.25)
        self.assertEqual(sock.sendto.call_count, 4, "the listener must still answer discovery")
        sock.close.assert_called_once_with()

if __name__ == "__main__":
    unittest.main()
