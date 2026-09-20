import sys
import unittest

sys.path.insert(0, "app/server")

from dlna_snapshot import dlna_component


class DlnaSnapshotTests(unittest.TestCase):
    def test_status_booleans_do_not_coerce_text(self):
        result = dlna_component("false", 0, {"refreshing": "false"})
        self.assertFalse(result["running"])
        self.assertFalse(result["discovery"]["refreshing"])
    def test_component_keeps_only_bounded_discovery_pressure_fields(self):
        payload = dlna_component(True, 2, {
            "refreshing": True, "workers": 1, "worker_limit": 1,
            "cached_renderers": 2, "cache_age_seconds": 9,
            "refresh_started": 3, "refresh_completed": 2,
            "refresh_failed": 1, "refresh_skipped": 4,
            "items": [{"name": "private"}], "error": "/secret",
        }, {"subscriptions": 1, "subscription_limit": 64, "workers": 1, "worker_limit": 4, "pending": 2, "pending_limit": 64, "peak_pending": 3, "accepted": 7, "dropped": 5, "callback": "http://private"})
        self.assertEqual(payload["renderers"], 2)
        self.assertEqual(payload["discovery"]["worker_limit"], 1)
        self.assertEqual(payload["eventing"]["pending_limit"], 64)
        self.assertEqual(payload["eventing"]["dropped"], 5)
        self.assertNotIn("private", str(payload))
        self.assertNotIn("secret", str(payload))

    def test_component_refuses_object_coercion(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("DLNA summary must not coerce objects")

        payload = dlna_component(False, Explosive(), {"workers": Explosive()}, {"pending": Explosive()})
        self.assertEqual(payload["renderers"], 0)
        self.assertEqual(payload["discovery"]["workers"], 0)
        self.assertEqual(payload["eventing"]["pending"], 0)


if __name__ == "__main__":
    unittest.main()
