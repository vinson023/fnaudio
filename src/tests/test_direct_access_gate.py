"""The packaged port belongs to fnOS, not to the network.

fnOS authenticates in front of this process and relays the request over loopback,
so anything that arrives from a LAN address never passed an identity check. R565
closed the port: only loopback, the public health probe, and the UPnP surface a
renderer must fetch (a television has no credentials to offer) get through.

These tests drive the real ``Handler`` gate rather than the policy module, because
the policy alone would still let the page, the JavaScript and the static assets be
served - the whole UI was reachable that way.
"""

import io
import json
import sys
import unittest

sys.path.insert(0, "app/server")
import server  # noqa: E402


class _FakeGate:
    """Just enough of a handler for the gate and its two response writers."""

    enforce_direct_access = server.Handler.enforce_direct_access
    send_direct_access_denied = server.Handler.send_direct_access_denied

    def __init__(self, peer, command="GET"):
        self.client_address = (peer, 50000)
        self.command = command
        self.status = None
        self.headers_sent = {}
        self.wfile = io.BytesIO()
        self.closed = False

    def send_json(self, payload, status=200):
        self.status = status
        self.ai = payload

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.headers_sent[name.lower()] = value

    def end_headers(self):
        pass

    def body(self):
        return self.wfile.getvalue().decode("utf-8")


class DirectAccessGateTests(unittest.TestCase):
    def test_lan_browser_gets_the_notice_page_not_the_app(self):
        gate = _FakeGate("192.168.5.30")
        self.assertFalse(gate.enforce_direct_access("/"))
        self.assertEqual(gate.status, 403)
        self.assertEqual(gate.headers_sent["content-type"], "text/html; charset=utf-8")
        self.assertEqual(gate.headers_sent["cache-control"], "no-store")
        page = gate.body()
        self.assertIn("飞牛", page, "the notice has to say where to go instead")
        self.assertIn("禁止直连访问", page)
        self.assertNotIn("app.js", page, "nothing of the application shell is served")

    def test_lan_api_call_gets_json_not_a_script(self):
        gate = _FakeGate("192.168.5.30")
        self.assertFalse(gate.enforce_direct_access("/api/library"))
        self.assertEqual(gate.status, 403)
        self.assertEqual(gate.ai, {"ok": False, "error": server.DIRECT_ACCESS_DENIED})
        self.assertEqual(gate.body(), "", "the API must not receive the HTML page")

    def test_lan_cannot_fetch_static_assets_either(self):
        for path in ("/app.js", "/app.css", "/index.html", "/favicon.ico"):
            with self.subTest(path=path):
                gate = _FakeGate("192.168.5.30")
                self.assertFalse(gate.enforce_direct_access(path))
                self.assertEqual(gate.status, 403)

    def test_health_probe_stays_public(self):
        # Monitoring and the fnOS supervisor poll it; it carries no library data.
        gate = _FakeGate("192.168.5.30")
        self.assertTrue(gate.enforce_direct_access("/api/health"))
        self.assertIsNone(gate.status)

    def test_upnp_surface_stays_reachable_for_cast_receivers(self):
        for path in ("/upnp/media/abc123/x.flac", "/dlna/media/description.xml",
                     "/upnp/cover/abc123/cover.jpg"):
            with self.subTest(path=path):
                gate = _FakeGate("192.168.5.30")
                self.assertTrue(gate.enforce_direct_access(path))
                self.assertIsNone(gate.status)

    def test_dlna_control_post_passes_the_gate(self):
        # A UPnP action is SOAP and arrives as POST. The gate used to key on the
        # verb alone, so a controller on another host got the notice page here
        # and reported "HTTP Error 403: Forbidden".
        for path in ("/dlna/renderer/avtransport/control",
                     "/dlna/renderer/connection/control",
                     "/dlna/server/content/control"):
            with self.subTest(path=path):
                gate = _FakeGate("192.168.5.30", command="POST")
                self.assertTrue(gate.enforce_direct_access(path))
                self.assertIsNone(gate.status)

    def test_a_post_outside_the_control_routes_still_gets_the_notice(self):
        for path in ("/upnp/media/abc123/x.flac", "/dlna/renderer/description.xml",
                     "/dlna/renderer/avtransport/event", "/api/state/user"):
            with self.subTest(path=path):
                gate = _FakeGate("192.168.5.30", command="POST")
                self.assertFalse(gate.enforce_direct_access(path))
                self.assertEqual(gate.status, 403)

    def test_loopback_is_untouched(self):
        for path in ("/", "/app.js", "/api/library", "/api/state/user"):
            with self.subTest(path=path):
                gate = _FakeGate("127.0.0.1")
                self.assertTrue(gate.enforce_direct_access(path))
        gate = _FakeGate("::1")
        self.assertTrue(gate.enforce_direct_access("/"))

    def test_dual_stack_ipv4_peer_is_judged_as_ipv4(self):
        gate = _FakeGate("::ffff:192.168.5.30")
        self.assertFalse(gate.enforce_direct_access("/"))
        self.assertEqual(gate.status, 403)


class NoticePageTests(unittest.TestCase):
    def test_notice_is_self_contained_and_names_both_audiences(self):
        page = server.DIRECT_ACCESS_PAGE
        self.assertIn("<!doctype html>", page.lower())
        self.assertNotIn("<script", page.lower(), "no script, no asset, no request")
        for hint in ("飞牛", "DLNA", "安卓"):
            self.assertIn(hint, page, "the page has to answer every way in: " + hint)

    def test_notice_carries_no_server_state(self):
        # It is a constant: nothing from the config, the library or the request may
        # be interpolated into it.
        self.assertNotIn("%s", server.DIRECT_ACCESS_PAGE)
        self.assertNotIn("{", server.DIRECT_ACCESS_PAGE.split("<style>")[0])


if __name__ == "__main__":
    unittest.main()
