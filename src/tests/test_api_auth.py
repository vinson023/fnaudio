import sys
import unittest

sys.path.insert(0, "app/server")
from api_auth import ALL_API_SCOPES, authorize_api, required_scope, requires_resource_auth


class ApiAuthTests(unittest.TestCase):
    def test_public_health_does_not_require_credentials(self):
        self.assertTrue(authorize_api("198.51.100.2", "GET", "/api/health", "", [])[0])

    def test_direct_lan_request_is_rejected_even_with_claimed_scope(self):
        result = authorize_api("198.51.100.2", "POST", "/api/playback/control", "token", ALL_API_SCOPES)
        self.assertEqual(result[:2], (False, 403))

    def test_loopback_request_requires_token_and_scope(self):
        self.assertEqual(authorize_api("127.0.0.1", "GET", "/api/library", "", ALL_API_SCOPES)[1], 401)
        self.assertEqual(authorize_api("127.0.0.1", "GET", "/api/library", "token", [])[1], 403)
        self.assertTrue(authorize_api("127.0.0.1", "GET", "/api/library", "token", ALL_API_SCOPES)[0])

    def test_sensitive_routes_have_distinct_scopes(self):
        self.assertEqual(required_scope("GET", "/api/library"), "library.read")
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
