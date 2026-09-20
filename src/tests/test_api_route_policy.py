import sys
import unittest

sys.path.insert(0, "src/app/server")

from api_route_policy import normalize_path, required_scope, requires_resource_auth


class ApiRoutePolicyTests(unittest.TestCase):
    def test_normalize_path_removes_query_and_bounds_input(self):
        self.assertEqual(normalize_path("/api/library?offset=1"), "/api/library")
        self.assertEqual(len(normalize_path("x" * 5000)), 4096)

    def test_route_policy_does_not_stringify_untrusted_objects(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("route policy must not stringify arbitrary objects")
        self.assertEqual(normalize_path(Explosive()), "")
        self.assertEqual(required_scope(Explosive(), Explosive()), "library.read")

    def test_resource_auth_uses_path_prefix(self):
        self.assertTrue(requires_resource_auth("/cover/abc?size=small"))
        self.assertTrue(requires_resource_auth("/metadata/artwork/abc"))
        self.assertFalse(requires_resource_auth("/api/health"))

    def test_scope_policy_preserves_read_write_mapping(self):
        self.assertEqual(required_scope("GET", "/api/health"), "")
        self.assertEqual(required_scope("GET", "/api/library"), "library.read")
        self.assertEqual(required_scope("GET", "/api/metadata/track"), "library.read")
        self.assertEqual(required_scope("POST", "/api/metadata/track/apply"), "settings.write")
        self.assertEqual(required_scope("POST", "/api/playback/control"), "playback.control")
        self.assertEqual(required_scope("POST", "/api/config/library"), "settings.write")
        self.assertEqual(required_scope("GET", "/api/library/location"), "files.read")


if __name__ == "__main__":
    unittest.main()
