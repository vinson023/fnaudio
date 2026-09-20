import sys
import unittest

sys.path.insert(0, "app/server")

from metadata_lane_policy import lane_workers_alive, service_was_started
from metadata_response_policy import has_cached_lyrics, has_cached_track_projection, is_pending_result


class MetadataLanePolicyTests(unittest.TestCase):
    def test_distinguishes_unstarted_and_dead_services(self):
        class Dead:
            def is_alive(self):
                return False

        self.assertFalse(service_was_started(object()))
        self.assertTrue(service_was_started(type("S", (), {"fetch_threads": [Dead()]})()))
        self.assertFalse(lane_workers_alive(type("S", (), {"fetch_threads": [Dead()]})()))

    def test_lyrics_lane_accepts_priority_worker(self):
        class Alive:
            def is_alive(self):
                return True

        service = type("S", (), {"fetch_threads": [], "priority_thread": Alive()})()
        self.assertTrue(lane_workers_alive(service, "lyrics"))
        self.assertFalse(lane_workers_alive(service, "fetch"))

    def test_empty_pool_is_not_available(self):
        service = type("S", (), {"fetch_threads": [], "priority_thread": None})()
        self.assertFalse(lane_workers_alive(service, "fetch"))
        self.assertFalse(lane_workers_alive(service, "lyrics"))

    def test_non_iterable_pool_reports_unavailable_instead_of_raising(self):
        for lane in ("fetch", "lyrics"):
            with self.subTest(lane=lane):
                service = type(
                    "S",
                    (),
                    {"fetch_threads": 3, "priority_thread": None},
                )()
                self.assertFalse(lane_workers_alive(service, lane))
                self.assertTrue(service_was_started(service))

    def test_failing_service_attributes_report_an_unavailable_lane(self):
        def raiser(_self):
            raise RuntimeError("broken double")

        service = type(
            "S",
            (),
            {
                "fetch_threads": property(raiser),
                "priority_thread": property(raiser),
                "tag_thread": property(raiser),
            },
        )()
        self.assertFalse(lane_workers_alive(service))
        self.assertFalse(lane_workers_alive(service, "lyrics"))
        self.assertFalse(service_was_started(service))

    def test_cached_response_policy_distinguishes_pending(self):
        cached = {"status": "auto", "best": {"title": "x"}}
        pending = {"status": "pending", "pending": True}
        self.assertTrue(has_cached_track_projection(cached))
        self.assertFalse(has_cached_track_projection(pending))
        self.assertFalse(has_cached_track_projection({"status": "failed", "best": {}, "candidates": []}))
        self.assertTrue(has_cached_track_projection({
            "status": "auto", "best": {}, "candidates": [],
            "image_url": "metadata/artwork/" + "a" * 64,
        }))
        self.assertFalse(has_cached_track_projection({
            "status": "auto", "best": {}, "candidates": [],
            "image_url": "metadata/artwork/not-a-content-address",
        }))
        self.assertFalse(has_cached_track_projection({
            "status": "auto", "best": {}, "candidates": [],
            "image_url": "metadata/artwork/" + "A" * 64,
        }))
        self.assertTrue(has_cached_track_projection({"status": "no_match", "best": {"title": "local"}, "retryable": True}))
        self.assertTrue(has_cached_lyrics({"lyrics": "[00:01]x", "pending": False}))
        self.assertFalse(has_cached_lyrics({
            "lyrics": "", "image_url": "metadata/artwork/" + "a" * 64, "pending": True,
        }))
        self.assertFalse(has_cached_lyrics(pending))
        self.assertTrue(is_pending_result(pending))


if __name__ == "__main__":
    unittest.main()
