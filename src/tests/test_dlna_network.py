import sys
import http.server
import socket
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, "app/server")
from dlna.network import MAX_DLNA_XML_BYTES, fetch_lan, lan_http_url, optional_lan_http_url
from dlna import control_point, network



def ssdp_socket(responses):
    """A UDP socket fake that yields `responses` and then keeps timing out, like a real window.

    A finite `side_effect` list would end the queue and raise StopIteration on the next read,
    because the discovery loop catches `socket.timeout` and continues.
    """
    sock = mock.Mock()
    queue = list(responses)

    def recvfrom(_size):
        if queue:
            return queue.pop(0)
        raise control_point.socket.timeout()

    sock.recvfrom.side_effect = recvfrom
    return sock


def discovery_clock(past_call=24):
    """A monotonic clock that stays inside the window for `past_call` reads, then expires.

    `recvfrom` is a finite side_effect list, so the receive loop has to be ended by the deadline;
    returning a constant would walk the list off its end and surface as StopIteration.
    """
    state = {"calls": 0}

    def current():
        state["calls"] += 1
        return 0.0 if state["calls"] <= past_call else 99.0

    return current


def response_hosts(host):
    """The location `discover_upnp` reports for an SSDP `LOCATION` header from `host`."""
    return "http://%s/device.xml" % host
class DlnaNetworkTests(unittest.TestCase):
    def test_device_supports_dsd_does_not_coerce_string_values(self):
        with mock.patch.object(control_point, "device_protocol_info", return_value={"supports_dsd": "false"}):
            self.assertFalse(control_point.device_supports_dsd("http://renderer.test/connection"))
    @mock.patch("dlna.network.socket.getaddrinfo", return_value=[(0, 0, 0, "", ("198.51.100.20", 80))])
    def test_accepts_lan_http_endpoint(self, _resolve):
        self.assertEqual(lan_http_url("http://speaker.local/description.xml"), "http://speaker.local/description.xml")

    @mock.patch("dlna.network.socket.getaddrinfo", return_value=[(0, 0, 0, "", ("8.8.8.8", 80))])
    def test_rejects_public_endpoint(self, _resolve):
        with self.assertRaisesRegex(ValueError, "LAN"):
            lan_http_url("https://example.test/media")

    @mock.patch("dlna.network.socket.getaddrinfo", return_value=[(0, 0, 0, "", ("127.0.0.1", 80))])
    def test_rejects_loopback_endpoint(self, _resolve):
        with self.assertRaisesRegex(ValueError, "LAN"):
            lan_http_url("http://localhost/private")

    @mock.patch("dlna.network.socket.getaddrinfo", return_value=[
        (0, 0, 0, "", ("198.51.100.20", 80)),
        (0, 0, 0, "", ("127.0.0.1", 80)),
    ])
    def test_rejects_hostname_with_any_loopback_answer(self, _resolve):
        with self.assertRaisesRegex(ValueError, "LAN"):
            lan_http_url("http://mixed.local/callback")

    def test_rejects_credentials_and_non_http_scheme(self):
        for value in ("file:///etc/passwd", "http://user:pass@198.51.100.2/x"):
            with self.assertRaises(ValueError):
                lan_http_url(value)

    def test_optional_endpoint_allows_clearing_next_uri(self):
        self.assertEqual(optional_lan_http_url(""), "")

    def test_endpoint_does_not_coerce_arbitrary_objects_to_text(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify untrusted URL values")

        with self.assertRaisesRegex(ValueError, "text URL"):
            lan_http_url(Explosive())
        with self.assertRaisesRegex(ValueError, "text URL"):
            optional_lan_http_url(Explosive())

    @mock.patch("dlna.network._lan_addresses", return_value=("198.51.100.20",))
    @mock.patch("dlna.network.lan_http_url", side_effect=lambda value: value)
    @mock.patch("dlna.network.urllib.request.build_opener")
    def test_fetch_rejects_oversized_response(self, build_opener, _validate, _addresses):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "http://198.51.100.20/device.xml"
        response.headers = {"Content-Length": "9"}
        build_opener.return_value.open.return_value = response
        with self.assertRaisesRegex(ValueError, "size limit"):
            fetch_lan("http://198.51.100.20/device.xml", max_bytes=8)

    @mock.patch("dlna.network._lan_addresses", return_value=("198.51.100.20",))
    @mock.patch("dlna.network.lan_http_url", side_effect=lambda value: value)
    @mock.patch("dlna.network.urllib.request.build_opener")
    def test_fetch_rejects_malformed_content_length(self, build_opener, _validate, _addresses):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "http://198.51.100.20/device.xml"
        response.headers = {"Content-Length": "not-a-number"}
        build_opener.return_value.open.return_value = response
        with self.assertRaisesRegex(ValueError, "invalid size"):
            fetch_lan("http://198.51.100.20/device.xml")

    @mock.patch("dlna.network._lan_addresses", return_value=("198.51.100.20",))
    @mock.patch("dlna.network.lan_http_url", side_effect=lambda value: value)
    @mock.patch("dlna.network.urllib.request.build_opener")
    def test_fetch_accumulates_short_response_chunks(self, build_opener, _validate, _addresses):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "http://198.51.100.20/device.xml"
        response.headers = {}
        response.read.side_effect = [b"<r", b"oot", b"/>", b""]
        build_opener.return_value.open.return_value = response
        self.assertEqual(fetch_lan("http://198.51.100.20/device.xml", max_bytes=32), b"<root/>")

    @mock.patch("dlna.network._lan_addresses", return_value=("198.51.100.20",))
    @mock.patch("dlna.network.lan_http_url", side_effect=lambda value: value)
    @mock.patch("dlna.network.urllib.request.build_opener")
    def test_fetch_rejects_truncated_declared_response(self, build_opener, _validate, _addresses):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "http://198.51.100.20/device.xml"
        response.headers = {"Content-Length": "8"}
        response.read.side_effect = [b"<root/>", b""]
        build_opener.return_value.open.return_value = response
        with self.assertRaisesRegex(ValueError, "truncated"):
            fetch_lan("http://198.51.100.20/device.xml", max_bytes=32)

    @mock.patch("dlna.network._lan_addresses", return_value=("198.51.100.20",))
    @mock.patch("dlna.network.lan_http_url", side_effect=lambda value: value)
    @mock.patch("dlna.network.urllib.request.build_opener")
    def test_fetch_rejects_non_ascii_content_length(self, build_opener, _validate, _addresses):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "http://198.51.100.20/device.xml"
        response.headers = {"Content-Length": "１２"}
        build_opener.return_value.open.return_value = response
        with self.assertRaisesRegex(ValueError, "invalid size"):
            fetch_lan("http://198.51.100.20/device.xml")

    @mock.patch("dlna.network._lan_addresses", return_value=("198.51.100.20",))
    @mock.patch("dlna.network.lan_http_url", side_effect=lambda value: value)
    @mock.patch("dlna.network.urllib.request.build_opener")
    def test_fetch_rejects_invalid_timeout_and_size_before_opening_connection(self, build_opener, _validate, _addresses):
        for timeout, size in ((float("nan"), 8), (11, 8), (3, True), (3, 0), (3, MAX_DLNA_XML_BYTES + 1)):
            with self.assertRaises(ValueError):
                fetch_lan("http://198.51.100.20/device.xml", timeout=timeout, max_bytes=size)
        build_opener.assert_not_called()

    @mock.patch("dlna.network.socket.create_connection")
    def test_pinned_http_connection_uses_validated_address(self, create_connection):
        from dlna.network import _PinnedHTTPConnection

        connection = _PinnedHTTPConnection("speaker.local", port=8080, pinned_address="198.51.100.20")
        connection.connect()

        create_connection.assert_called_once_with(("198.51.100.20", 8080), connection.timeout, connection.source_address)

    def test_pinned_https_handler_uses_standard_connection_arguments(self):
        from dlna.network import _PinnedHTTPSHandler

        handler = _PinnedHTTPSHandler("198.51.100.20")
        request = mock.Mock()
        with mock.patch.object(handler, "do_open") as do_open:
            handler.https_open(request)

        self.assertIs(do_open.call_args.args[0].__name__, "_PinnedHTTPSConnection")
        self.assertEqual(do_open.call_args.args[1], request)
        self.assertIs(do_open.call_args.kwargs["context"], handler._context)
        self.assertEqual(do_open.call_args.kwargs["pinned_address"], "198.51.100.20")
        self.assertNotIn("check_hostname", do_open.call_args.kwargs)

    def test_fetch_connects_to_pinned_address_while_preserving_host_header(self):
        observed = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                observed["host"] = self.headers.get("Host")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            port = server.server_address[1]
            url = "http://speaker.local:%d/description.xml" % port
            with mock.patch("dlna.network.lan_http_url", side_effect=lambda value: value), \
                 mock.patch("dlna.network._lan_addresses", return_value=("127.0.0.1",)):
                self.assertEqual(fetch_lan(url), b"ok")
            self.assertEqual(observed["host"], "speaker.local:%d" % port)
        finally:
            server.shutdown()
            server.server_close()

    def test_redirect_handler_never_follows_location(self):
        from dlna.network import _NoRedirect

        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, "Found", {}, "http://8.8.8.8/x"))

    def test_background_discovery_marks_refreshing_before_thread_start(self):
        previous = dict(control_point.UPNP_CACHE)

        class ThreadProbe:
            def __init__(self, target, daemon):
                self.target = target
                self.daemon = daemon

            def start(self):
                self.assert_refreshing()

            @staticmethod
            def assert_refreshing():
                if control_point.UPNP_CACHE.get("refreshing") is not True:
                    raise AssertionError("refreshing must be published before thread start")

        try:
            control_point.UPNP_CACHE.update({"stamp": 0, "items": [], "refreshing": False})
            with mock.patch.object(control_point.threading, "Thread", ThreadProbe):
                control_point.refresh_upnp_cache_background()
            self.assertTrue(control_point.UPNP_CACHE["refreshing"])
        finally:
            control_point.UPNP_CACHE.clear()
            control_point.UPNP_CACHE.update(previous)

    def test_background_discovery_admits_only_one_worker_and_counts_skips(self):
        previous = dict(control_point.UPNP_CACHE)

        class ThreadProbe:
            def __init__(self, target, daemon):
                self.target = target
                self.daemon = daemon

            def start(self):
                pass

        try:
            control_point.UPNP_CACHE.clear()
            control_point.UPNP_CACHE.update({"stamp": 0, "items": [], "refreshing": False})
            with mock.patch.object(control_point.threading, "Thread", side_effect=ThreadProbe) as thread:
                self.assertTrue(control_point.refresh_upnp_cache_background())
                self.assertFalse(control_point.refresh_upnp_cache_background())
            self.assertEqual(thread.call_count, 1)
            status = control_point.upnp_cache_status()
            self.assertTrue(status["refreshing"])
            self.assertEqual(status["workers"], 1)
            self.assertEqual(status["worker_limit"], 1)
            self.assertEqual(status["refresh_skipped"], 1)
        finally:
            control_point.UPNP_CACHE.clear()
            control_point.UPNP_CACHE.update(previous)

    def test_stale_discovery_worker_cannot_publish_after_shutdown_and_restart(self):
        previous_cache = dict(control_point.UPNP_CACHE)
        previous_generation = control_point._UPNP_REFRESH_GENERATION
        previous_thread = control_point._UPNP_REFRESH_THREAD
        threads = []

        class ThreadProbe:
            def __init__(self, target, daemon):
                self.target = target
                self.daemon = daemon
                threads.append(self)

            def start(self):
                pass

            def join(self, timeout=None):
                self.join_timeout = timeout

        try:
            control_point.UPNP_CACHE.clear()
            control_point.UPNP_CACHE.update({
                "stamp": 0, "items": [{"id": "old"}], "refreshing": False,
                "refresh_started": 0, "refresh_completed": 0,
                "refresh_failed": 0, "refresh_skipped": 0,
            })
            with mock.patch.object(control_point.threading, "Thread", ThreadProbe), \
                 mock.patch.object(control_point, "discover_upnp", side_effect=[[{"id": "stale"}], [{"id": "fresh"}]]):
                self.assertTrue(control_point.refresh_upnp_cache_background())
                stale_worker = threads[-1]
                control_point.shutdown_upnp_cache_background(wait=True, timeout=1)
                self.assertFalse(control_point.UPNP_CACHE["refreshing"])
                self.assertTrue(control_point.refresh_upnp_cache_background())
                fresh_worker = threads[-1]
                stale_worker.target()
                self.assertEqual(control_point.UPNP_CACHE["items"], [{"id": "old"}])
                self.assertEqual(control_point.UPNP_CACHE["refresh_completed"], 0)
                fresh_worker.target()

            self.assertEqual(control_point.UPNP_CACHE["items"], [{"id": "fresh"}])
            self.assertEqual(control_point.UPNP_CACHE["refresh_completed"], 1)
            self.assertFalse(control_point.UPNP_CACHE["refreshing"])
            self.assertEqual(stale_worker.join_timeout, 1.0)
        finally:
            control_point.UPNP_CACHE.clear()
            control_point.UPNP_CACHE.update(previous_cache)
            control_point._UPNP_REFRESH_GENERATION = previous_generation
            control_point._UPNP_REFRESH_THREAD = previous_thread

    def test_discovery_rotates_its_probe_budget_across_rounds(self):
        # Three responders, a budget of two. Taking them in arrival order meant the third was
        # never described, in any round, so it could never become a playback target.
        def response(host):
            return ("HTTP/1.1 200 OK\r\nLOCATION: http://%s/device.xml\r\n\r\n" % host).encode("ascii")

        hosts = ["198.51.100.20", "198.51.100.21", "198.51.100.22"]
        original_limit = control_point.UPNP_DISCOVERY_DEVICE_PROBE_LIMIT
        original_memory = control_point._UPNP_LAST_PROBED
        rounds = []
        second_round_devices = []
        try:
            control_point.UPNP_DISCOVERY_DEVICE_PROBE_LIMIT = 2
            for _ in range(2):
                sock = ssdp_socket([(response(host), (host, 1900)) for host in hosts])
                with mock.patch.object(control_point.socket, "socket", return_value=sock), \
                        mock.patch.object(control_point, "lan_http_url", side_effect=lambda value: value), \
                        mock.patch.object(control_point.time, "monotonic", side_effect=discovery_clock()), \
                        mock.patch.object(control_point, "fetch_lan") as fetch:
                    devices = control_point.discover_upnp()
                probed_locations = {call.args[0] for call in fetch.call_args_list}
                if rounds:
                    second_round_devices = devices
                rounds.append(probed_locations)
                self.assertEqual(len(devices), 2, "the budget itself must stay bounded")
            # Round one is arrival order; round two must reach the responder round one never
            # asked, and must not spend both slots on devices it already probed.
            self.assertEqual({response_hosts(h) for h in ["198.51.100.20", "198.51.100.21"]}, rounds[0])
            self.assertIn(response_hosts("198.51.100.22"), rounds[1])
            # Rotation moves who gets asked, not the published order: the target list the UI
            # renders keeps the order it is handed, so a refresh must not reshuffle it. Round two
            # picks the never-asked .22 plus the first arrival again, and must report them in
            # arrival order rather than in selection order.
            self.assertEqual([device["location"] for device in second_round_devices],
                             [response_hosts(hosts[0]), response_hosts(hosts[2])])
            self.assertEqual(len(rounds[0] | rounds[1]), 3, "two rounds covered only %d devices" % len(rounds[0] | rounds[1]))
        finally:
            control_point.UPNP_DISCOVERY_DEVICE_PROBE_LIMIT = original_limit
            control_point._UPNP_LAST_PROBED = original_memory

    def test_discovery_probe_order_is_untouched_when_everything_fits(self):
        # Rotation exists for the over-subscribed case. With three responders and a budget of
        # three, the list must still come back in arrival order and every one must be described:
        # reordering for its own sake would move devices around in the UI for no reason.
        def response(host):
            return ("HTTP/1.1 200 OK\r\nLOCATION: http://%s/device.xml\r\n\r\n" % host).encode("ascii")

        hosts = ["198.51.100.20", "198.51.100.21", "198.51.100.22"]
        original_memory = control_point._UPNP_LAST_PROBED
        try:
            control_point._UPNP_LAST_PROBED = frozenset({response_hosts(h) for h in hosts[:2]})
            sock = ssdp_socket([(response(host), (host, 1900)) for host in hosts])
            with mock.patch.object(control_point.socket, "socket", return_value=sock), \
                    mock.patch.object(control_point, "lan_http_url", side_effect=lambda value: value), \
                    mock.patch.object(control_point.time, "monotonic", side_effect=discovery_clock()), \
                    mock.patch.object(control_point, "fetch_lan") as fetch:
                devices = control_point.discover_upnp()
            self.assertEqual([device["location"] for device in devices],
                             [response_hosts(host) for host in hosts])
            self.assertTrue(all(device["probed"] for device in devices))
        finally:
            control_point._UPNP_LAST_PROBED = original_memory

    def test_refresh_keeps_renderers_the_rotation_did_not_probe(self):
        # The published list used to be replaced wholesale, so a renderer that was known last
        # round and skipped this round disappeared - and with it the ability to show the target
        # the user had selected (playback_targets_presentation marks `selected` only for devices
        # present in this list).
        probed = {"id": "a" * 16, "location": response_hosts("198.51.100.20"), "online": True}
        known = {"id": "b" * 16, "location": response_hosts("198.51.100.21"), "online": True}
        merged = control_point.retain_unprobed_devices([known, probed], [probed])
        self.assertEqual([device["location"] for device in merged],
                         [probed["location"], known["location"]])
        self.assertIs(merged[1]["probed"], False, "a carried-forward device must say it was not probed")
        self.assertNotIn("probed", merged[0], "the fresh entry keeps what discovery reported")
        # A device the round did probe is never duplicated from the previous list.
        again = control_point.retain_unprobed_devices(merged, [probed])
        self.assertEqual(len(again), 2)
        self.assertEqual(control_point.retain_unprobed_devices(None, [probed]), [probed])
        self.assertEqual(control_point.retain_unprobed_devices([known], []), [dict(known, probed=False)])
        # The merged list stays bounded by the same ceiling discovery already respects, or a long
        # run of rotating rounds would grow the published cache without limit.
        crowd = [{"id": "%02d" % index, "location": "http://10.0.0.%d/d.xml" % index} for index in range(300)]
        bounded = control_point.retain_unprobed_devices(crowd, [probed])
        self.assertEqual(len(bounded), control_point.UPNP_MAX_DISCOVERED_DEVICES)

    def test_a_refresh_publishes_rotation_results_over_the_known_renderers(self):
        # The merge only matters if the worker performs it. Asserting on the helper alone let a
        # mutant that goes back to `UPNP_CACHE["items"] = items` pass the whole suite, which is
        # the same class of gap as patching a function that the caller had already bound.
        probed = {"id": "a" * 16, "location": response_hosts("198.51.100.20"), "online": True, "probed": True}
        known = {"id": "b" * 16, "location": response_hosts("198.51.100.21"), "online": True, "probed": True}
        previous_cache = dict(control_point.UPNP_CACHE)
        previous_generation = control_point._UPNP_REFRESH_GENERATION
        previous_thread = control_point._UPNP_REFRESH_THREAD
        threads = []

        class ThreadProbe:
            def __init__(self, target=None, *args, **kwargs):
                self.target = target

            def start(self):
                threads.append(self)

            def join(self, timeout=None):
                pass

            def is_alive(self):
                return False

        try:
            control_point.UPNP_CACHE.clear()
            control_point.UPNP_CACHE.update({
                "stamp": 0, "items": [known], "refreshing": False,
                "refresh_started": 0, "refresh_completed": 0, "refresh_failed": 0, "refresh_skipped": 0,
            })
            with mock.patch.object(control_point.threading, "Thread", ThreadProbe), \
                    mock.patch.object(control_point, "discover_upnp", return_value=[probed]), \
                    mock.patch.object(control_point.time, "time", return_value=1000.0):
                self.assertTrue(control_point.refresh_upnp_cache_background())
                threads[-1].target()
            published = control_point.UPNP_CACHE["items"]
            self.assertEqual([device["location"] for device in published],
                             [probed["location"], known["location"]])
            self.assertIs(published[1]["probed"], False, "the carried-forward renderer must not claim freshness")
            self.assertEqual(control_point.UPNP_CACHE["stamp"], 1000.0)
        finally:
            control_point.UPNP_CACHE.clear()
            control_point.UPNP_CACHE.update(previous_cache)
            control_point._UPNP_REFRESH_GENERATION = previous_generation
            control_point._UPNP_REFRESH_THREAD = previous_thread

    def test_discovery_stops_before_network_probes_when_its_budget_is_exhausted(self):
        response = b"HTTP/1.1 200 OK\r\nLOCATION: http://198.51.100.20/device.xml\r\n\r\n"
        sock = mock.Mock()
        sock.recvfrom.side_effect = [(response, ("198.51.100.20", 1900)), control_point.socket.timeout()]
        with mock.patch.object(control_point.socket, "socket", return_value=sock), \
             mock.patch.object(control_point, "lan_http_url", side_effect=lambda value: value), \
             mock.patch.object(control_point.time, "time", side_effect=[0.0, 0.0, 3.0]), \
             mock.patch.object(control_point.time, "monotonic", side_effect=[0.0, 99.0, 99.0]), \
             mock.patch.object(control_point, "fetch_lan") as fetch:
            self.assertEqual(control_point.discover_upnp(), [])
        fetch.assert_not_called()

    def test_discovery_caps_sequential_device_probes(self):
        first = b"HTTP/1.1 200 OK\r\nLOCATION: http://198.51.100.20/first.xml\r\n\r\n"
        second = b"HTTP/1.1 200 OK\r\nLOCATION: http://198.51.100.21/second.xml\r\n\r\n"
        sock = mock.Mock()
        sock.recvfrom.side_effect = [
            (first, ("198.51.100.20", 1900)),
            (second, ("198.51.100.21", 1900)),
            control_point.socket.timeout(),
        ]
        original_limit = control_point.UPNP_DISCOVERY_DEVICE_PROBE_LIMIT
        try:
            control_point.UPNP_DISCOVERY_DEVICE_PROBE_LIMIT = 1
            with mock.patch.object(control_point.socket, "socket", return_value=sock), \
                 mock.patch.object(control_point, "lan_http_url", side_effect=lambda value: value), \
                 mock.patch.object(control_point.time, "time", side_effect=[0.0, 0.0, 0.0, 3.0]), \
                 mock.patch.object(control_point.time, "monotonic", side_effect=[0.0, 0.0, 0.0, 3.0, 3.0, 3.0]), \
                 mock.patch.object(control_point, "fetch_lan", return_value=b"<root><friendlyName>Renderer</friendlyName></root>") as fetch, \
                 mock.patch.object(control_point, "probe_device_capabilities", return_value={"protocol_info": {}}):
                devices = control_point.discover_upnp()
            self.assertEqual(len(devices), 1)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(fetch.call_args.args[0], "http://198.51.100.20/first.xml")
        finally:
            control_point.UPNP_DISCOVERY_DEVICE_PROBE_LIMIT = original_limit


    def test_discovery_keeps_reading_after_transient_socket_errors(self):
        first = b"HTTP/1.1 200 OK\r\nLOCATION: http://198.51.100.20/first.xml\r\n\r\n"
        second = b"HTTP/1.1 200 OK\r\nLOCATION: http://198.51.100.21/second.xml\r\n\r\n"
        sock = mock.Mock()
        sock.recvfrom.side_effect = [
            (first, ("198.51.100.20", 1900)),
            ConnectionResetError(10054, 'connection was reset'),
            (second, ("198.51.100.21", 1900)),
            control_point.socket.timeout(),
        ]
        original_limit = control_point.UPNP_DISCOVERY_DEVICE_PROBE_LIMIT
        try:
            control_point.UPNP_DISCOVERY_DEVICE_PROBE_LIMIT = 2
            with mock.patch.object(control_point.socket, "socket", return_value=sock), \
                 mock.patch.object(control_point, "lan_http_url", side_effect=lambda value: value), \
                 mock.patch.object(control_point.time, "time", return_value=0.0), \
                 mock.patch.object(
                     control_point.time, "monotonic",
                     side_effect=[0.0, 0.1, 0.2, 0.3, 0.4, 3.0, 3.0, 3.1, 3.2, 3.3],
                 ), \
                 mock.patch.object(control_point, "fetch_lan", return_value=b"<root><friendlyName>Renderer</friendlyName></root>"), \
                 mock.patch.object(control_point, "probe_device_capabilities", return_value={"protocol_info": {}}):
                devices = control_point.discover_upnp()
            self.assertEqual([device["name"] for device in devices], ["Renderer", "Renderer"])
            self.assertEqual(
                sorted(device["location"] for device in devices),
                ["http://198.51.100.20/first.xml", "http://198.51.100.21/second.xml"],
            )
        finally:
            control_point.UPNP_DISCOVERY_DEVICE_PROBE_LIMIT = original_limit
        sock.setsockopt.assert_any_call(
            socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2
        )

    def test_discovery_gives_up_after_repeated_transient_socket_errors(self):
        sock = mock.Mock()
        sock.recvfrom.side_effect = ConnectionResetError(10054, 'connection was reset')
        with mock.patch.object(control_point.socket, "socket", return_value=sock), \
             mock.patch.object(control_point.time, "time", return_value=0.0), \
             mock.patch.object(
                 control_point.time, "monotonic", side_effect=[0.0] + [0.1] * 10
             ), \
             mock.patch.object(control_point, "fetch_lan") as fetch:
            self.assertEqual(control_point.discover_upnp(), [])
        self.assertEqual(
            sock.recvfrom.call_count,
            control_point.UPNP_DISCOVERY_MAX_TRANSIENT_ERRORS,
        )
        fetch.assert_not_called()
        sock.close.assert_called_once()
    def test_cache_status_never_exposes_device_identity(self):
        previous = dict(control_point.UPNP_CACHE)
        try:
            control_point.UPNP_CACHE.clear()
            control_point.UPNP_CACHE.update({"stamp": 0, "items": [{"name": "Private renderer", "location": "http://198.51.100.9"}], "refreshing": False})
            status = control_point.upnp_cache_status()
            self.assertEqual(status["cached_renderers"], 1)
            self.assertNotIn("Private renderer", str(status))
            self.assertNotIn("198.51.100.9", str(status))
        finally:
            control_point.UPNP_CACHE.clear()
            control_point.UPNP_CACHE.update(previous)

    def test_capability_cache_is_bounded(self):
        previous = dict(control_point.UPNP_CAPABILITY_CACHE)
        try:
            control_point.UPNP_CAPABILITY_CACHE.clear()
            with mock.patch.object(control_point, "device_protocol_info", return_value={"supports_dsd": False}), \
                 mock.patch.object(control_point, "scpd_actions", return_value=[]):
                for index in range(control_point.UPNP_CAPABILITY_CACHE_LIMIT + 4):
                    control_point.probe_device_capabilities({
                        "id": "renderer-%d" % index,
                        "connection_url": "",
                        "avtransport_scpd_url": "",
                    })
            self.assertLessEqual(
                len(control_point.UPNP_CAPABILITY_CACHE),
                control_point.UPNP_CAPABILITY_CACHE_LIMIT,
            )
        finally:
            control_point.UPNP_CAPABILITY_CACHE.clear()
            control_point.UPNP_CAPABILITY_CACHE.update(previous)

    def test_capability_probe_treats_corrupt_cache_entries_as_misses(self):
        previous = dict(control_point.UPNP_CAPABILITY_CACHE)
        device = {
            "id": "corrupt-cache", "connection_url": "",
            "avtransport_scpd_url": "",
        }
        try:
            control_point.UPNP_CAPABILITY_CACHE.clear()
            control_point.UPNP_CAPABILITY_CACHE["corrupt-cache"] = object()
            # The eviction pass must tolerate unrelated broken entries too.
            control_point.UPNP_CAPABILITY_CACHE["older"] = object()
            original_limit = control_point.UPNP_CAPABILITY_CACHE_LIMIT
            control_point.UPNP_CAPABILITY_CACHE_LIMIT = 1
            with mock.patch.object(control_point, "device_protocol_info", return_value={"supports_dsd": False}), \
                 mock.patch.object(control_point, "scpd_actions", return_value=[]):
                result = control_point.probe_device_capabilities(device)
            self.assertFalse(result["set_next_uri"])
            self.assertLessEqual(len(control_point.UPNP_CAPABILITY_CACHE), 1)
        finally:
            control_point.UPNP_CAPABILITY_CACHE_LIMIT = original_limit
            control_point.UPNP_CAPABILITY_CACHE.clear()
            control_point.UPNP_CAPABILITY_CACHE.update(previous)

    def test_capability_cache_ttl_uses_monotonic_clock(self):
        previous = dict(control_point.UPNP_CAPABILITY_CACHE)
        device = {
            "id": "clock-stable", "connection_url": "",
            "avtransport_scpd_url": "",
        }
        try:
            control_point.UPNP_CAPABILITY_CACHE.clear()
            with mock.patch.object(control_point, "device_protocol_info", return_value={"supports_dsd": False}) as protocol, \
                 mock.patch.object(control_point, "scpd_actions", return_value=[]), \
                 mock.patch.object(control_point.time, "time", side_effect=[1000.0, 1.0]), \
                 mock.patch.object(control_point.time, "monotonic", side_effect=[50.0, 50.5]):
                control_point.probe_device_capabilities(device)
                control_point.probe_device_capabilities(device)
            protocol.assert_called_once_with("")
        finally:
            control_point.UPNP_CAPABILITY_CACHE.clear()
            control_point.UPNP_CAPABILITY_CACHE.update(previous)

    def test_upnp_time_helpers_reject_nonfinite_and_untrusted_values(self):
        self.assertEqual(control_point.seconds_to_upnp_time(float("nan")), "00:00:00")
        self.assertEqual(control_point.seconds_to_upnp_time(float("inf")), "00:00:00")
        self.assertEqual(control_point.upnp_time_to_seconds(float("inf")), 0)
        self.assertEqual(control_point.upnp_time_to_seconds("9:08:07"), 32887)
        self.assertEqual(control_point.upnp_time_to_seconds("00:99:99"), 0)
        self.assertEqual(control_point.upnp_time_to_seconds("25:00:00"), 0)

    def test_cache_status_recovers_from_corrupt_numeric_state(self):
        previous = dict(control_point.UPNP_CACHE)
        try:
            control_point.UPNP_CACHE.clear()
            control_point.UPNP_CACHE.update({
                "stamp": float("nan"), "items": [], "refreshing": False,
                "refresh_started": object(), "refresh_completed": float("inf"),
                "refresh_failed": -4, "refresh_skipped": True,
            })
            status = control_point.upnp_cache_status()
            self.assertEqual(status["cache_age_seconds"], 0)
            self.assertEqual(status["refresh_started"], 0)
            self.assertEqual(status["refresh_completed"], 0)
            self.assertEqual(status["refresh_failed"], 0)
            self.assertEqual(status["refresh_skipped"], 0)
        finally:
            control_point.UPNP_CACHE.clear()
            control_point.UPNP_CACHE.update(previous)

    def test_refresh_counter_writes_recover_from_corrupt_state(self):
        previous = dict(control_point.UPNP_CACHE)
        try:
            control_point.UPNP_CACHE.clear()
            control_point.UPNP_CACHE.update({"refreshing": True, "refresh_skipped": object()})
            self.assertFalse(control_point.refresh_upnp_cache_background())
            self.assertEqual(control_point.UPNP_CACHE["refresh_skipped"], 1)
        finally:
            control_point.UPNP_CACHE.clear()
            control_point.UPNP_CACHE.update(previous)



class DlnaResponseBudgetTests(unittest.TestCase):
    """The bounded reader has to accept exactly-budget bodies, refuse more."""

    class _Drip:
        """Hand out a canned body in short pieces, like a real socket read."""

        def __init__(self, body, step=None):
            self.body = body
            self.step = step
            self.read_sizes = []
            self.delivered = 0

        def read(self, size):
            self.read_sizes.append(size)
            limit = size if self.step is None else min(size, self.step)
            chunk = self.body[self.delivered:self.delivered + limit]
            self.delivered += len(chunk)
            return chunk

    def test_accepts_a_body_of_exactly_the_limit(self):
        body = b"<root>" + b"x" * 34
        response = self._Drip(body)
        self.assertEqual(network._read_response_limited(response, 40), body)
        # A zero-length read would end the loop early and silently truncate a
        # body that is still arriving, so every request must stay positive.
        self.assertTrue(response.read_sizes)
        self.assertTrue(all(size >= 1 for size in response.read_sizes))

    def test_byte_buffer_chunks_are_accumulated(self):
        response = self._Drip(bytearray(b"<root/>"), step=4)
        self.assertEqual(network._read_response_limited(response, 32), b"<root/>")

    def test_empty_body_is_not_an_error(self):
        self.assertEqual(network._read_response_limited(self._Drip(b""), 40), b"")

    def test_refuses_a_body_one_byte_over_the_limit_delivered_in_drips(self):
        # A peer with no Content-Length can keep streaming forever. The reader
        # must stop the moment the budget is really exceeded instead of
        # returning a truncated body that looks like a valid document.
        response = self._Drip(b"y" * 41, step=1)
        with self.assertRaisesRegex(ValueError, "size limit"):
            network._read_response_limited(response, 40)
        self.assertLessEqual(response.delivered, 41)
        self.assertTrue(all(size >= 1 for size in response.read_sizes))

    def test_text_chunk_is_refused_instead_of_extending_the_buffer(self):
        class _TextBody:
            def __init__(self):
                self.calls = 0

            def read(self, _size):
                self.calls += 1
                return "<root/>"

        response = _TextBody()
        with self.assertRaisesRegex(ValueError, "size limit"):
            network._read_response_limited(response, 40)
        self.assertEqual(response.calls, 1)

    @mock.patch("dlna.network._lan_addresses", return_value=("198.51.100.20",))
    @mock.patch("dlna.network.lan_http_url", side_effect=lambda value: value)
    @mock.patch("dlna.network.urllib.request.build_opener")
    def test_fetch_refuses_undeclared_overflow(self, build_opener, _validate, _addresses):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "http://198.51.100.20/device.xml"
        response.headers = {}
        response.read.side_effect = [b"z" * 8] * 6 + [b""]
        build_opener.return_value.open.return_value = response
        with self.assertRaisesRegex(ValueError, "size limit"):
            fetch_lan("http://198.51.100.20/device.xml", max_bytes=40)

class DlnaPinnedConnectionTests(unittest.TestCase):
    """Pinning may change the socket target but never the TLS identity."""

    @mock.patch("dlna.network.socket.create_connection")
    def test_tls_pinning_keeps_the_hostname_for_sni(self, create_connection):
        from dlna.network import _PinnedHTTPSConnection

        context = mock.Mock(name="ssl-context")
        connection = _PinnedHTTPSConnection(
            "speaker.local", port=8443, timeout=3,
            pinned_address="198.51.100.20", context=context,
        )
        raw_socket = mock.Mock(name="tcp-socket")
        create_connection.return_value = raw_socket

        connection.connect()

        create_connection.assert_called_once_with(
            ("198.51.100.20", 8443), connection.timeout, connection.source_address,
        )
        # The certificate is verified against the name from the validated
        # endpoint, so a peer that only holds a cert for its IP cannot be
        # accepted just because we resolved that IP ourselves.
        context.wrap_socket.assert_called_once_with(raw_socket, server_hostname="speaker.local")
        self.assertIs(connection.sock, context.wrap_socket.return_value)

    @mock.patch("dlna.network.socket.create_connection")
    def test_tls_without_a_pinned_address_dials_the_hostname(self, create_connection):
        from dlna.network import _PinnedHTTPSConnection

        context = mock.Mock(name="ssl-context")
        connection = _PinnedHTTPSConnection("speaker.local", port=8443, timeout=3, context=context)

        connection.connect()

        create_connection.assert_called_once_with(
            ("speaker.local", 8443), connection.timeout, connection.source_address,
        )
        context.wrap_socket.assert_called_once_with(create_connection.return_value, server_hostname="speaker.local")

    @mock.patch("dlna.network.socket.create_connection")
    def test_pinned_connections_refuse_a_proxy_tunnel(self, create_connection):
        from dlna.network import _PinnedHTTPConnection, _PinnedHTTPSConnection

        for factory in (_PinnedHTTPConnection, _PinnedHTTPSConnection):
            connection = factory("speaker.local", port=8443, pinned_address="198.51.100.20")
            connection.set_tunnel("proxy.invalid", port=3128)
            with self.assertRaisesRegex(ValueError, "cannot be proxied"):
                connection.connect()
        create_connection.assert_not_called()


class DlnaLanAddressCacheTests(unittest.TestCase):
    """A LAN peer is resolved once per TTL, and the resolver never runs under the cache lock."""

    def setUp(self):
        network.clear_lan_address_cache()
        self.addCleanup(network.clear_lan_address_cache)

    class _Resolver:
        gaierror = OSError
        SOCK_STREAM = 1

        def __init__(self, addresses):
            self.addresses = list(addresses)
            self.seen = []

        def getaddrinfo(self, host, port, type=None):
            self.seen.append((host, port))
            return [(2, 1, 6, "", (address, port)) for address in self.addresses]

    class _Response:
        def __init__(self, url, payload=b"ok"):
            self._url = url
            self._payload = payload
            self.headers = {"Content-Length": str(len(payload))}

        def geturl(self):
            return self._url

        def read(self, amount=-1):
            chunk, self._payload = self._payload[:amount], self._payload[amount:]
            return chunk

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    @staticmethod
    def _opener(*injections):
        """Opener stand-in that answers with whatever endpoint the code asked for."""
        pending = list(injections)
        opener = mock.Mock()
        def respond(request, timeout=None):
            url = getattr(request, "full_url", request)
            if pending:
                outcome = pending.pop(0)
                if isinstance(outcome, BaseException):
                    raise outcome
                return DlnaLanAddressCacheTests._Response(url, outcome)
            return DlnaLanAddressCacheTests._Response(url)
        opener.open.side_effect = respond
        return opener

    def _fetch_twice(self, url, resolver, opener=None):
        opener = opener or self._opener()
        outcomes = []
        with mock.patch("dlna.network.urllib.request.build_opener", return_value=opener), \
                mock.patch.object(network, "socket", resolver):
            for _ in range(2):
                try:
                    outcomes.append(fetch_lan(url))
                except Exception as exc:                      # noqa: BLE001 - recorded for the assertion
                    outcomes.append(exc)
        return outcomes, opener


    def test_repeated_fetches_to_one_endpoint_resolve_once(self):
        resolver = self._Resolver(["198.51.100.20"])
        outcomes, _opener = self._fetch_twice("http://speaker.local:49152/desc.xml", resolver)
        self.assertEqual([type(item).__name__ for item in outcomes], ["bytes", "bytes"])
        self.assertEqual(resolver.seen, [("speaker.local", 49152)])

    def test_expired_entry_is_resolved_again(self):
        resolver = self._Resolver(["198.51.100.20"])
        original = network.LAN_ADDRESS_CACHE_TTL_SECONDS
        network.LAN_ADDRESS_CACHE_TTL_SECONDS = 0.0
        try:
            _outcomes, _opener = self._fetch_twice("http://speaker.local:49152/desc.xml", resolver)
        finally:
            network.LAN_ADDRESS_CACHE_TTL_SECONDS = original
        self.assertEqual(resolver.seen, [("speaker.local", 49152), ("speaker.local", 49152)])

    def test_different_ports_are_separate_policy_decisions(self):
        resolver = self._Resolver(["198.51.100.20"])
        url = "http://speaker.local:49152/desc.xml"
        opener = self._opener()
        with mock.patch("dlna.network.urllib.request.build_opener", return_value=opener), \
                mock.patch.object(network, "socket", resolver):
            fetch_lan(url)
            fetch_lan("http://speaker.local:49153/desc.xml")
        self.assertEqual(resolver.seen, [("speaker.local", 49152), ("speaker.local", 49153)])

    def test_the_status_surface_counts_traffic_without_naming_a_peer(self):
        # R74 left this cache with no observable at all and allowed exactly one shape of
        # replacement: counts.  A status carrying the key or an address would name a device
        # on the diagnostics page, so both halves are asserted - the numbers have to follow
        # the traffic, and nothing about the peer may be rendered.
        resolver = self._Resolver(["198.51.100.20"])
        with mock.patch("dlna.network.socket.getaddrinfo", new=resolver.getaddrinfo):
            before = network.lan_address_cache_status()
            before_page = control_point.upnp_cache_status()
            network._cached_lan_addresses("speaker.local", 80)
            network._cached_lan_addresses("speaker.local", 80)
            after = network.lan_address_cache_status()
        self.assertEqual(sorted(after), ["entries", "evictions", "expired", "hits", "limit",
                                         "misses", "ttl_seconds"],
                         "the surface grew beyond counts, which is where identity would leak")
        self.assertEqual(after["misses"] - before["misses"], 1, "one resolution for two lookups")
        self.assertEqual(after["hits"] - before["hits"], 1)
        self.assertEqual(after["expired"] - before["expired"], 0, "nothing aged out in this test")
        self.assertEqual(after["entries"], 1)
        self.assertEqual(after["limit"], network.LAN_ADDRESS_CACHE_LIMIT)
        rendered = repr(after)
        for secret in ("speaker", "198.51.100.20"):
            self.assertNotIn(secret, rendered)
        page = control_point.upnp_cache_status()
        self.assertEqual(page["lan_cache_misses"] - before_page["lan_cache_misses"], 1,
                         "the counters never reached the diagnostics page")
        self.assertEqual(page["lan_cache_hits"] - before_page["lan_cache_hits"], 1)
        self.assertNotIn("speaker", repr(page))

    def test_an_aged_out_entry_is_counted_separately_from_a_first_sight(self):
        # The question the counters exist to answer is "why was the first action after a peer
        # moved slow", and that is an expiry, not a miss: a brand new peer and a peer whose
        # lease ran out both miss, so only the split tells them apart.
        resolver = self._Resolver(["198.51.100.21"])
        clock = [1000.0]
        with mock.patch("dlna.network.socket.getaddrinfo", new=resolver.getaddrinfo), \
             mock.patch("dlna.network.time.monotonic", lambda: clock[0]):
            start = network.lan_address_cache_status()
            network._cached_lan_addresses("tv.local", 80)
            fresh = network.lan_address_cache_status()
            clock[0] += network.LAN_ADDRESS_CACHE_TTL_SECONDS + 1
            network._cached_lan_addresses("tv.local", 80)
            aged = network.lan_address_cache_status()
        # The counters are cumulative for the process, like the discovery counters beside
        # them, so every reading here is a delta.
        self.assertEqual(fresh["misses"] - start["misses"], 1)
        self.assertEqual(fresh["expired"] - start["expired"], 0)
        self.assertEqual(aged["misses"] - fresh["misses"], 1)
        self.assertEqual(aged["expired"] - fresh["expired"], 1,
                         "an expired lease must be distinguishable from a first sight")
        self.assertEqual(aged["hits"] - fresh["hits"], 0)

    def test_the_cache_key_folds_host_case_and_port_type(self):
        """`Speaker.Local` and `speaker.local` are one endpoint, `80` and `"80"` too.

        Reached at the helper rather than through `fetch_lan` because
        `urlparse().hostname` already lowercases, so the fold would be invisible
        end to end; it still has to hold for every other caller of the helper.
        """
        seen = []

        def fake_lan_addresses(hostname, port):
            seen.append((hostname, port))
            return ("198.51.100.20",)

        with mock.patch.object(network, "_lan_addresses", fake_lan_addresses):
            self.assertEqual(network._cached_lan_addresses("Speaker.Local", 80), ("198.51.100.20",))
            self.assertEqual(network._cached_lan_addresses("speaker.local", "80"), ("198.51.100.20",))
        self.assertEqual(seen, [("Speaker.Local", 80)])

    def test_dial_failure_forgets_the_remembered_address(self):
        resolver = self._Resolver(["198.51.100.20"])
        url = "http://speaker.local:49152/desc.xml"
        opener = self._opener(ConnectionRefusedError(10061, "refused"))
        with mock.patch("dlna.network.urllib.request.build_opener", return_value=opener), \
                mock.patch.object(network, "socket", resolver):
            with self.assertRaises(ConnectionRefusedError):
                fetch_lan(url)
            # The entry must have been dropped by the failure, so this second call
            # re-resolves instead of pinning the address that just refused us.
            self.assertEqual(fetch_lan(url), b"ok")
        self.assertEqual(len(resolver.seen), 2)

    def test_a_rejected_answer_is_not_remembered(self):
        """A public answer must not poison the entry for the next resolution."""
        url = "http://speaker.local:49152/desc.xml"
        bad = self._Resolver(["8.8.8.8"])
        with mock.patch("dlna.network.urllib.request.build_opener", return_value=mock.Mock()), \
                mock.patch.object(network, "socket", bad):
            with self.assertRaises(ValueError):
                fetch_lan(url)
        self.assertEqual(network.lan_address_cache_size(), 0)
        good = self._Resolver(["198.51.100.20"])
        outcomes, _opener = self._fetch_twice(url, good)
        self.assertEqual([type(item).__name__ for item in outcomes], ["bytes", "bytes"])
        self.assertEqual(good.seen, [("speaker.local", 49152)])

    def test_address_cache_is_bounded(self):
        resolver = self._Resolver(["198.51.100.20"])
        opener = self._opener()
        with mock.patch("dlna.network.urllib.request.build_opener", return_value=opener), \
                mock.patch.object(network, "socket", resolver):
            for index in range(network.LAN_ADDRESS_CACHE_LIMIT + 5):
                fetch_lan("http://host%d:80/x" % index)
        self.assertEqual(network.lan_address_cache_size(), network.LAN_ADDRESS_CACHE_LIMIT)
        self.assertEqual(len(resolver.seen), network.LAN_ADDRESS_CACHE_LIMIT + 5)
        # The very first host must have been evicted, so it resolves again.
        seen_before = len(resolver.seen)
        with mock.patch("dlna.network.urllib.request.build_opener", return_value=opener), \
                mock.patch.object(network, "socket", resolver):
            fetch_lan("http://host0:80/x")
        self.assertEqual(len(resolver.seen), seen_before + 1)

    def test_resolver_runs_outside_the_address_cache_lock(self):
        """One broken host must not stall every other DLNA request.

        Behaviour test: a thread waiting inside the resolver must not prevent
        another thread from taking the cache lock, so the elapsed time is the
        release signal, not an inspection of the source.
        """
        entered = threading.Event()
        release = threading.Event()

        def blocking_getaddrinfo(host, port, type=None):
            entered.set()
            self.assertTrue(release.wait(5.0), "the test harness released late")
            # A canned LAN answer: this test is about the lock, and a real lookup
            # of a made-up host would die with gaierror inside the worker thread.
            return [(2, 1, 6, "", ("198.51.100.20", port))]

        resolver = mock.Mock()
        resolver.getaddrinfo = blocking_getaddrinfo
        resolver.gaierror = OSError
        resolver.SOCK_STREAM = 1
        worker = threading.Thread(
            target=lambda: network._cached_lan_addresses("slowhost", 8000), daemon=True)
        try:
            with mock.patch.object(network, "socket", resolver):
                worker.start()
                self.assertTrue(entered.wait(5.0), "the resolver was never reached")
                began = time.perf_counter()
                with network._LAN_ADDRESS_CACHE_LOCK:
                    waited = time.perf_counter() - began
                release.set()
                worker.join(5.0)
            self.assertLess(waited, 0.2, "the cache lock was held across getaddrinfo")
        finally:
            release.set()

    def test_soap_action_resolves_the_control_host_once(self):
        """The control path used to validate the same endpoint twice per action."""
        resolver = self._Resolver(["198.51.100.20"])
        url = "http://198.51.100.20:49152/control"
        opener = self._opener(b"<s:Envelope/>")
        with mock.patch("dlna.network.urllib.request.build_opener", return_value=opener), \
                mock.patch.object(network, "socket", resolver):
            control_point.soap_request(url, "urn:schemas-upnp-org:service:AVTransport:1", "Play")
            control_point.soap_request(url, "urn:schemas-upnp-org:service:AVTransport:1", "Pause")
        self.assertEqual(len(resolver.seen), 1, "a burst of actions must not re-resolve per action")
        self.assertEqual(opener.open.call_count, 2, "both actions still went out")

    def test_soap_action_still_rejects_an_endpoint_that_is_not_lan(self):
        resolver = self._Resolver(["8.8.8.8"])
        opener = mock.Mock()
        with mock.patch("dlna.network.urllib.request.build_opener", return_value=opener), \
                mock.patch.object(network, "socket", resolver):
            with self.assertRaisesRegex(ValueError, "LAN addresses"):
                control_point.soap_request("http://evil.example:49152/control",
                                           "urn:schemas-upnp-org:service:AVTransport:1", "Play")
        opener.open.assert_not_called()

    def test_soap_action_rejects_a_non_text_endpoint_as_a_value_error(self):
        with self.assertRaisesRegex(ValueError, "text URL"):
            control_point.soap_request(None, "urn:schemas-upnp-org:service:AVTransport:1", "Play")

class DlnaResolverBudgetTests(unittest.TestCase):
    """A delivery action waits a bounded time for the resolver, not the whole resolver timeout.

    ``socket.getaddrinfo`` has no timeout of its own, and it runs before the request
    timeout in ``fetch_lan`` can apply, so an unbounded lookup on a peer whose name
    hangs means the action worker is gone for the full resolver wait.  Measured on
    the NAS (docs/external-acceptance.md, entry L1860) that wait is fifteen to twenty
    seconds against a three second budget.  These tests hold the two things that bound
    it: the caller stops waiting, and the lookups that keep running are counted.
    """

    URL = "http://speaker.local:49152/desc.xml"

    class _Resolver:
        gaierror = OSError
        SOCK_STREAM = 1

        def __init__(self, addresses):
            self.addresses = list(addresses)
            self.seen = []

        def getaddrinfo(self, host, port, type=None):
            self.seen.append((host, port))
            return [(2, 1, 6, "", (address, port)) for address in self.addresses]

    def setUp(self):
        network.clear_lan_address_cache()
        self.addCleanup(network.clear_lan_address_cache)

    def _gate_is_quiet(self, within=10.0):
        """Wait for every lookup the tests started to hand its slot back."""
        deadline = time.monotonic() + within
        while time.monotonic() < deadline:
            if network._RESOLVER_GATE.snapshot()["active"] == 0:
                return True
            time.sleep(0.01)
        return False

    def test_the_bounds_stay_inside_the_request_budget_and_the_worker_pool(self):
        # Pinning the two numbers is the point: a bound quietly raised to the resolver
        # wait would keep this file green while restoring the behaviour it guards.
        self.assertLessEqual(
            network.RESOLVER_WAIT_SECONDS, 2.0,
            "a delivery action must not wait longer on a name than it is allowed to wait on the request")
        self.assertGreaterEqual(network.RESOLVER_WAIT_SECONDS, 0.1)
        self.assertLess(
            network.RESOLVER_IN_FLIGHT_LIMIT, 32 // 2,
            "the bound must leave most of the worker pool free")
        self.assertGreaterEqual(network.RESOLVER_IN_FLIGHT_LIMIT, 1)

    def test_a_prompt_lookup_and_a_refusal_both_travel_the_wrapper_unchanged(self):
        good = self._Resolver(["198.51.100.20"])
        with mock.patch.object(network, "socket", good):
            self.assertEqual(
                network._lan_addresses_within_budget("speaker.local", 49152), ("198.51.100.20",))
        self.assertEqual(good.seen, [("speaker.local", 49152)])
        bad = self._Resolver(["8.8.8.8"])
        with mock.patch.object(network, "socket", bad):
            with self.assertRaisesRegex(ValueError, "LAN addresses"):
                network._lan_addresses_within_budget("evil.example", 49152)
        self.assertEqual(network.lan_address_cache_size(), 0)

    def test_a_stalled_resolver_is_given_up_on_and_its_late_answer_is_dropped(self):
        entered = threading.Event()
        release = threading.Event()

        class StalledResolver(self._Resolver):
            def getaddrinfo(self, host, port, type=None):
                self.seen.append((host, port))
                entered.set()
                release.wait(30)
                return [(2, 1, 6, "", ("198.51.100.20", port))]

        resolver = StalledResolver(["198.51.100.20"])
        opener = mock.Mock()
        with mock.patch("dlna.network.urllib.request.build_opener", return_value=opener), \
                mock.patch.object(network, "socket", resolver):
            began = time.monotonic()
            with self.assertRaisesRegex(ValueError, "resolved in time"):
                fetch_lan(self.URL, timeout=3)
            waited = time.monotonic() - began
            self.assertTrue(entered.wait(5.0), "the resolver was never reached")
            self.assertLess(
                waited, network.RESOLVER_WAIT_SECONDS + 0.6,
                "the caller stayed with a resolver that never answered")
            self.assertEqual(opener.open.call_count, 0, "no request may go out behind a stalled lookup")
            self.assertEqual(network.lan_address_cache_size(), 0, "a timed out lookup is not remembered")
            self.assertEqual(
                network._RESOLVER_GATE.snapshot()["active"], 1,
                "the slot must stay with the lookup that is still stalled, not return to the caller that gave up")
            release.set()
            self.assertTrue(self._gate_is_quiet(), "a finished lookup never handed its slot back")
        # The answer arrived after everyone had stopped asking for it.  Keeping it would
        # put an address in front of the next action that no caller had waited for.
        self.assertEqual(network.lan_address_cache_size(), 0, "a late answer is dropped, not cached")
        self.assertEqual(resolver.seen, [("speaker.local", 49152)])

    def test_a_saturated_resolver_is_refused_without_resolving_or_queueing(self):
        limit = network.RESOLVER_IN_FLIGHT_LIMIT
        held = 0

        def give_back():
            for _ in range(held):
                network._RESOLVER_GATE.release()

        self.addCleanup(give_back)
        for _ in range(limit):
            self.assertTrue(network._RESOLVER_GATE.try_acquire(limit))
            held += 1
        resolver = self._Resolver(["198.51.100.20"])
        opener = mock.Mock()
        with mock.patch("dlna.network.urllib.request.build_opener", return_value=opener), \
                mock.patch.object(network, "socket", resolver):
            began = time.monotonic()
            with self.assertRaisesRegex(ValueError, "resolution is busy"):
                fetch_lan(self.URL, timeout=3)
            waited = time.monotonic() - began
        self.assertLess(waited, 0.2, "an overflow must be refused at once, not queued behind a dead name")
        self.assertEqual(resolver.seen, [], "no lookup runs while every slot is taken")
        opener.open.assert_not_called()

    def test_a_caller_that_gave_up_hands_its_slot_back_only_when_the_lookup_ends(self):
        # What the gate bounds is lookups still running, not callers still waiting. A caller
        # that handed its slot back when it gave up would let every later action against a
        # dead name start another resolver thread, which is the exhaustion the gate exists to
        # refuse, so the slot travels with the worker until the resolver finally answers.
        entered = threading.Event()
        release = threading.Event()

        class StalledResolver(self._Resolver):
            def getaddrinfo(self, host, port, type=None):
                self.seen.append((host, port))
                entered.set()
                release.wait(30)
                return [(2, 1, 6, "", ("198.51.100.20", port))]

        resolver = StalledResolver(["198.51.100.20"])
        self.assertTrue(self._gate_is_quiet(), "a previous test left a slot held")
        with mock.patch.object(network, "socket", resolver):
            with self.assertRaisesRegex(ValueError, "resolved in time"):
                network._lan_addresses_within_budget("speaker.local", 49152)
            self.assertTrue(entered.wait(5.0), "the resolver was never reached")
            snapshot = network._RESOLVER_GATE.snapshot()
            self.assertEqual(
                snapshot["active"], 1,
                "the slot belongs to the lookup still running, not to the caller that left")
            self.assertEqual(snapshot["waiting"], 0, "a given-up lookup must not build a queue")
            release.set()
            self.assertTrue(self._gate_is_quiet(), "the slot came back only when the lookup ended")
