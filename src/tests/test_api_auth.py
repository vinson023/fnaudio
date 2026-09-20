import sys
import unittest

sys.path.insert(0, "app/server")
from api_auth import ALL_API_SCOPES, authorize_api, required_scope, requires_resource_auth


class ApiAuthTests(unittest.TestCase):
    def test_public_health_does_not_require_credentials(self):
        self.assertTrue(authorize_api("198.51.100.2", "GET", "/api/health", "", [])[0])

    def test_private_lan_request_can_use_the_direct_web_ui(self):
        for address in ("198.51.100.2", "10.0.0.4", "fd00::24", "fe80::24"):
            with self.subTest(address=address):
                self.assertTrue(authorize_api(address, "POST", "/api/playback/control", "", [])[0])

    def test_private_lan_cannot_anonymously_change_settings_or_files(self):
        for path in ("/api/config/library", "/api/metadata/refresh", "/api/fs/delete"):
            with self.subTest(path=path):
                allowed, status, _scope, message = authorize_api(
                    "198.51.100.2", "POST", path, "", []
                )
                self.assertFalse(allowed)
                self.assertEqual(status, 403)
                self.assertIn("fnOS", message)

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
