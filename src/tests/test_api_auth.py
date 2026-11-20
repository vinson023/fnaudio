import ipaddress
import sys
import unittest

sys.path.insert(0, "app/server")
from api_auth import (ALL_API_SCOPES, DIRECT_ACCESS_DENIED, TRUSTED_LAN_NETWORKS,
                      authorize_api, peer_may_reach, required_scope, requires_resource_auth)


class ApiAuthTests(unittest.TestCase):
    def test_trusted_networks_are_valid_and_cover_documentation_fixture(self):
        self.assertTrue(all(ipaddress.ip_network(str(network), strict=True) == network for network in TRUSTED_LAN_NETWORKS))
        self.assertTrue(any(ipaddress.ip_address("198.51.100.2") in network for network in TRUSTED_LAN_NETWORKS))

    def test_public_health_does_not_require_credentials(self):
        self.assertTrue(authorize_api("198.51.100.2", "GET", "/api/health", "", [])[0])

    def test_private_lan_cannot_reach_the_api_at_all(self):
        # R565: a direct LAN client never passed an authentication step, so it gets
        # nothing - not reads, not writes. R563 made it read-only, which still
        # served the whole library to every device on the network.
        for address in ("198.51.100.2", "10.0.0.4", "fd00::24", "fe80::24"):
            for method, path in (("GET", "/api/library"), ("GET", "/api/state/user"),
                                 ("GET", "/api/playback/status"), ("POST", "/api/state/user"),
                                 ("POST", "/api/playback/control"), ("POST", "/api/fs/delete")):
                with self.subTest(address=address, path=path):
                    allowed, status, _scope, message = authorize_api(address, method, path, "", [])
                    self.assertFalse(allowed, "a direct LAN client must be refused: " + path)
                    self.assertEqual(status, 403, "403, because no credential can fix this")
                    self.assertEqual(message, DIRECT_ACCESS_DENIED)

    def test_upnp_surface_stays_open_to_renderers(self):
        # A television fetches the stream and the device description straight from
        # this port and has no credentials to offer; UPnP has no authentication.
        for path in ("/upnp/media/abc123/x.flac", "/dlna/media/description.xml",
                     "/dlna/media/xml/SCPD.xml", "/upnp/cover/abc123/cover.jpg"):
            with self.subTest(path=path):
                self.assertTrue(peer_may_reach("192.168.5.30", "GET", path))
                self.assertTrue(authorize_api("192.168.5.30", "GET", path, "", [])[0])

    def test_upnp_control_posts_reach_the_renderer(self):
        # A UPnP action is SOAP: POST with a SOAPACTION header, never GET. While
        # the exception covered GET/HEAD only, another fnAudio on the same LAN
        # could discover and describe this renderer and then took a 403 on the
        # first action, which its UI reported as "HTTP Error 403: Forbidden".
        for path in ("/dlna/renderer/avtransport/control",
                     "/dlna/renderer/rendering/control",
                     "/dlna/renderer/connection/control",
                     "/dlna/server/content/control",
                     "/dlna/server/connection/control"):
            with self.subTest(path=path):
                self.assertTrue(peer_may_reach("192.168.5.30", "POST", path))
                self.assertTrue(authorize_api("192.168.5.30", "POST", path, "", [])[0])

    def test_the_dlna_control_exception_covers_no_other_write(self):
        # Only the control routes take a POST. The stream, the cover, the
        # description, the SCPD and the eventing URL still answer a write with
        # the notice page, and so does every API route.
        for path in ("/upnp/media/abc123/x.flac", "/upnp/cover/abc123/cover.jpg",
                     "/dlna/renderer/description.xml", "/dlna/scpd/avtransport.xml",
                     "/dlna/renderer/avtransport/event", "/dlna/renderer/avtransport/control/x",
                     "/dlna/media/avtransport/control", "/api/state/user", "/"):
            with self.subTest(path=path):
                self.assertFalse(peer_may_reach("192.168.5.30", "POST", path))

    def test_lan_peer_cannot_reach_the_page_static_or_writes_to_dlna(self):
        for method, path in (("GET", "/"), ("GET", "/app.js"), ("POST", "/upnp/media/abc/x.flac"),
                             ("GET", "/media/abc/x.flac"), ("GET", "/api/access")):
            with self.subTest(path=path):
                self.assertFalse(peer_may_reach("192.168.5.30", method, path))

    def test_loopback_page_and_static_stay_reachable(self):
        for path in ("/", "/app.js", "/upnp/media/abc/x.flac", "/api/library"):
            with self.subTest(path=path):
                self.assertTrue(peer_may_reach("127.0.0.1", "GET", path))
                self.assertTrue(peer_may_reach("::1", "GET", path))

    def test_private_lan_cannot_anonymously_change_settings_or_files(self):
        # Settings and file management are the routes that used to answer with a
        # dedicated "fnOS entry required" message; they now fall under the same
        # blanket refusal as every other API route.
        for path in ("/api/config/library", "/api/metadata/refresh", "/api/fs/delete"):
            with self.subTest(path=path):
                allowed, status, _scope, message = authorize_api(
                    "198.51.100.2", "POST", path, "", []
                )
                self.assertFalse(allowed)
                self.assertEqual(status, 403)
                self.assertEqual(message, DIRECT_ACCESS_DENIED)

    def test_public_direct_request_still_requires_the_authenticated_proxy(self):
        result = authorize_api("2001:4860:4860::8888", "POST", "/api/playback/control", "token", ALL_API_SCOPES)
        self.assertEqual(result[:2], (False, 403))

    def test_loopback_request_requires_token_and_scope(self):
        self.assertEqual(authorize_api("127.0.0.1", "GET", "/api/library", "", ALL_API_SCOPES)[1], 401)
        self.assertEqual(authorize_api("127.0.0.1", "GET", "/api/library", "token", [])[1], 403)
        self.assertTrue(authorize_api("127.0.0.1", "GET", "/api/library", "token", ALL_API_SCOPES)[0])

    def test_loopback_scope_projection_rejects_non_text_and_unbounded_values(self):
        values = [object(), "x" * 129, " library.read "] + ["state.read"] * 100
        self.assertTrue(authorize_api("127.0.0.1", "GET", "/api/library", "token", values)[0])
        self.assertEqual(authorize_api("127.0.0.1", "GET", "/api/library", "token", object())[1], 403)

    def test_auth_policy_does_not_coerce_untrusted_peer_or_token(self):
        class Explosive:
            def __bool__(self):
                raise AssertionError("auth policy must not evaluate object truthiness")

            def __str__(self):
                raise AssertionError("auth policy must not stringify arbitrary objects")

        self.assertEqual(authorize_api(Explosive(), "GET", "/api/library", "token", ALL_API_SCOPES)[1], 403)
        self.assertEqual(authorize_api("127.0.0.1", "GET", "/api/library", Explosive(), ALL_API_SCOPES)[1], 401)

    def test_sensitive_routes_have_distinct_scopes(self):
        self.assertEqual(required_scope("GET", "/api/library"), "library.read")
        self.assertEqual(required_scope("GET", "/api/metadata/track"), "library.read")
        self.assertEqual(required_scope("GET", "/api/metadata/status"), "library.read")
        self.assertEqual(required_scope("POST", "/api/playback/control"), "playback.control")
        self.assertEqual(required_scope("POST", "/api/config/library"), "settings.write")
        self.assertEqual(required_scope("POST", "/api/library/scan/cancel"), "settings.write")
        self.assertEqual(required_scope("GET", "/api/library/location"), "files.read")
        self.assertEqual(required_scope("POST", "/api/metadata/retry-tag-writes"), "settings.write")

    def test_private_media_resources_require_library_scope(self):
        for path in ("/media/track", "/cover/track", "/metadata/artwork/asset"):
            self.assertTrue(requires_resource_auth(path))
            self.assertEqual(required_scope("GET", path), "library.read")
        self.assertFalse(requires_resource_auth("/upnp/media/track/file.flac"))
        self.assertFalse(requires_resource_auth("/images/icon_64.png"))
