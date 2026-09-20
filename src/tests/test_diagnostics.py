import sys
import unittest

sys.path.insert(0, "app/server")

from diagnostics import support_snapshot
from summary_values import bounded_text, nonnegative_int


class DiagnosticsTests(unittest.TestCase):
    def test_snapshot_isolates_broken_mapping_access(self):
        class BrokenDict(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken dependency state")

        snapshot = support_snapshot(
            server_name="fnAudio", mpd=BrokenDict(), scan_state=BrokenDict(),
            metadata=BrokenDict(), transcode=BrokenDict(), dlna_available=False,
            renderer_count=0, metrics=BrokenDict(), playback=BrokenDict(),
            library_query_cache=BrokenDict(), thumbnail_prewarm=BrokenDict(),
            dlna_discovery=BrokenDict(), dlna_eventing=BrokenDict(),
        )
        self.assertEqual(snapshot["playback"]["queue_length"], 0)
        self.assertEqual(snapshot["components"]["metadata"]["pending"], 0)
        self.assertEqual(snapshot["components"]["transcode"]["queued"], 0)

    def test_summary_integer_rejects_overlong_numeric_text(self):
        self.assertEqual(nonnegative_int("9" * 10000), 0)
        self.assertEqual(nonnegative_int("bad", default=object(), maximum=object()), 0)
        self.assertEqual(nonnegative_int(10, maximum=5), 5)
        self.assertEqual(nonnegative_int("bad", default=999, maximum=5), 5)
        self.assertEqual(bounded_text("abcdef", maximum=3), "abc")
        self.assertEqual(bounded_text("abcdef", maximum=object()), "abcdef")
        self.assertEqual(bounded_text(object(), default=object()), "")
        self.assertEqual(bounded_text(object(), default="abcdef", maximum=3), "abc")

    def test_snapshot_is_bounded_and_redacts_sensitive_values(self):
        snapshot = support_snapshot(
            server_name="fnAudio test",
            mpd={"running": True, "fault": {"state": "PLAYING"}, "playback_errors": {"last_category": ""}},
            scan_state={"running": False, "errors": ["one"]},
            metadata={"running": True, "pending": 2, "dropped": 1, "network_workers_active": 3, "network_worker_limit": 4, "status_cache": {"ttl_ms": 750, "age_ms": 12, "hits": 4, "misses": 2, "private": "/vol1/secret"}},
            transcode={
                "queued": 3, "tracked": 5, "queue_limit": 64,
                "ffmpeg": {"active": 1, "limit": 2, "waiting": 1, "peak": 2, "peak_waiting": 3, "acquired": 7, "waited": 4, "rejected": 1, "waiter_rejected": 2, "timed_out": 1, "waiter_limit": 32, "wait_seconds": 0.1234},
            },
            dlna_available=True,
            renderer_count=2,
            metrics={"token": "must-not-leak"},
            playback={"target_id": "dac:one", "transport": "PLAYING", "queue_length": 8, "current": {"path": "/private/song.flac"}},
            library_search_index={"mode": "fts5-trigram", "substring_minimum_chars": 3, "private_path": "/vol1/secret"},
            thumbnail_prewarm={"interactive": {"queued": 2, "limit": 96}, "library": {"queued": 24, "limit": 5000, "dropped": 7, "root_limit": 8, "root_rejected": 3}},
            cover_cache={"entries": 9, "limit": 512, "inflight": 1, "inflight_limit": 64, "private_path": "/vol1/secret"},
            cache_failures={"load": 2, "save": 3, "private": "/vol1/secret"},
            library_storage={"database_bytes": 100, "wal_bytes": 20, "shm_bytes": 3, "total_bytes": 123, "path": "/vol1/secret"},
            dlna_discovery={"refreshing": True, "workers": 1, "worker_limit": 1, "cached_renderers": 2, "refresh_skipped": 3},
            dlna_eventing={"subscriptions": 2, "subscription_limit": 64, "workers": 1, "worker_limit": 4, "pending": 3, "pending_limit": 64, "peak_pending": 4, "accepted": 5, "dropped": 1},
            playback_command_cache={"entries": 4, "limit": 1024, "saturated": False, "inflight": 2, "inflight_limit": 1024, "private": "/vol1/secret"},
        )
        self.assertEqual(snapshot["schema"], 1)
        self.assertEqual(snapshot["playback"]["queue_length"], 8)
        self.assertNotIn("path", str(snapshot))
        self.assertEqual(snapshot["metrics"]["token"], "[REDACTED]")
        self.assertEqual(snapshot["components"]["transcode"]["queued"], 3)
        self.assertEqual(snapshot["components"]["metadata"]["network_workers_active"], 3)
        self.assertEqual(snapshot["components"]["metadata"]["network_worker_limit"], 4)
        self.assertEqual(snapshot["components"]["metadata"]["status_cache"], {"ttl_ms": 750, "age_ms": 12, "hits": 4, "misses": 2})
        self.assertEqual(snapshot["components"]["dlna"]["discovery"]["worker_limit"], 1)
        self.assertEqual(snapshot["components"]["dlna"]["discovery"]["refresh_skipped"], 3)
        self.assertEqual(snapshot["components"]["dlna"]["eventing"]["pending_limit"], 64)
        self.assertEqual(snapshot["components"]["dlna"]["eventing"]["dropped"], 1)
        self.assertEqual(snapshot["components"]["transcode"]["ffmpeg"]["waiting"], 1)
        self.assertEqual(snapshot["components"]["transcode"]["ffmpeg"]["wait_seconds"], 0.123)
        self.assertEqual(snapshot["components"]["transcode"]["ffmpeg"]["waiter_rejected"], 2)
        self.assertEqual(snapshot["components"]["transcode"]["ffmpeg"]["timed_out"], 1)
        self.assertEqual(snapshot["components"]["playback"]["command_cache"], {"entries": 4, "limit": 1024, "saturated": False, "inflight": 2, "inflight_limit": 1024})
        self.assertEqual(snapshot["components"]["transcode"]["ffmpeg"]["waiter_limit"], 32)
        self.assertEqual(snapshot["components"]["library"]["thumbnail_prewarm"]["interactive"]["queued"], 2)
        self.assertEqual(snapshot["components"]["library"]["thumbnail_prewarm"]["library"]["limit"], 5000)
        self.assertEqual(snapshot["components"]["library"]["thumbnail_prewarm"]["library"]["dropped"], 7)
        self.assertEqual(snapshot["components"]["library"]["thumbnail_prewarm"]["library"]["root_limit"], 8)
        self.assertEqual(snapshot["components"]["library"]["thumbnail_prewarm"]["library"]["root_rejected"], 3)
        self.assertEqual(snapshot["components"]["library"]["cover_cache"], {"entries": 9, "limit": 512, "inflight": 1, "inflight_limit": 64})
        self.assertEqual(snapshot["components"]["library"]["cache_failures"], {"load": 2, "save": 3})
        self.assertEqual(snapshot["components"]["library"]["storage"], {"database_bytes": 100, "wal_bytes": 20, "shm_bytes": 3, "total_bytes": 123})
        self.assertEqual(snapshot["components"]["library"]["search_index"], {"mode": "fts5-trigram", "substring_minimum_chars": 3})

    def test_snapshot_does_not_degrade_health_for_recoverable_playback_warning(self):
        snapshot = support_snapshot(
            server_name="fnAudio test",
            mpd={
                "running": True,
                "fault": {"state": "IDLE"},
                "playback_errors": {
                    "last_category": "queue_stale",
                    "items": [{"category": "queue_stale", "severity": "warning"}],
                },
            },
            scan_state={}, metadata={}, transcode={}, dlna_available=False,
            renderer_count=0, metrics={}, playback={},
        )

        self.assertEqual(snapshot["components"]["mpd"]["error_category"], "")

    def test_snapshot_refuses_object_coercion_for_public_summary_fields(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("diagnostics must not coerce arbitrary objects")

            def __str__(self):
                raise AssertionError("diagnostics must not stringify arbitrary objects")

        snapshot = support_snapshot(
            server_name=Explosive(), mpd={"fault": {"state": Explosive()}}, scan_state={},
            metadata={"pending": Explosive(), "dropped": float("inf"), "status_cache": {"hits": Explosive()}}, transcode={"queued": Explosive()},
            dlna_available=False, renderer_count=Explosive(), metrics={},
            playback={"target_id": Explosive(), "transport": Explosive(), "queue_length": Explosive()},
        )
        self.assertEqual(snapshot["server"]["name"], "fnAudio")
        self.assertEqual(snapshot["playback"], {"target_id": "", "transport": "", "queue_length": 0, "has_current_track": False})
        self.assertEqual(snapshot["components"]["metadata"]["pending"], 0)
        self.assertEqual(snapshot["components"]["metadata"]["status_cache"]["hits"], 0)
        self.assertEqual(snapshot["components"]["dlna"]["renderers"], 0)

    def test_snapshot_is_safe_for_malformed_top_level_and_nested_payloads(self):
        malformed = object()
        snapshot = support_snapshot(
            server_name="x", mpd={"fault": malformed, "playback_errors": malformed},
            scan_state=malformed, metadata={"status_cache": malformed}, transcode=malformed,
            dlna_available=False, renderer_count=0, metrics=malformed, playback={"current": malformed},
        )
        self.assertEqual(snapshot["playback"]["has_current_track"], False)
        self.assertEqual(snapshot["components"]["metadata"]["status_cache"]["hits"], 0)


if __name__ == "__main__":
    unittest.main()
