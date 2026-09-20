import sys
import unittest

sys.path.insert(0, "app/server")

from health_snapshot import build_health_payload
from metadata_local_lyrics_cache import LocalLyricsCache
from playback.mpd_errors import classify_mpd_log_errors
from summary_values import MAX_SUMMARY_COUNT, nonnegative_int


class HealthSnapshotTests(unittest.TestCase):
    def test_component_status_booleans_do_not_coerce_text(self):
        payload = build_health_payload(
            server_name="fnAudio", request_id="r", mpd={"running": "false"},
            scan_state={}, metadata={"running": "false"}, transcode={},
            dlna_running="false", renderer_count=0, metrics={}, library_query_cache={},
        )
        self.assertFalse(payload["components"]["mpd"]["running"])
        self.assertFalse(payload["components"]["metadata"]["running"])
        self.assertFalse(payload["components"]["dlna"]["running"])
    def test_nonnegative_int_handles_extreme_maximum_without_raising(self):
        self.assertEqual(nonnegative_int(9, maximum=10 ** 10000), 9)
        self.assertEqual(nonnegative_int(9, maximum=float("inf")), 9)
        self.assertEqual(nonnegative_int(-1, maximum=MAX_SUMMARY_COUNT), 0)

    def test_health_payload_isolates_broken_mapping_access(self):
        class BrokenDict(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken dependency state")

        payload = build_health_payload(
            server_name="fnAudio",
            request_id="request-2",
            mpd=BrokenDict(),
            scan_state=BrokenDict(),
            metadata=BrokenDict(),
            transcode=BrokenDict(),
            dlna_running=False,
            renderer_count=0,
            metrics=BrokenDict(),
            library_query_cache=BrokenDict(),
            library_search_index=BrokenDict(),
            thumbnail_prewarm=BrokenDict(),
            dlna_discovery=BrokenDict(),
            dlna_eventing=BrokenDict(),
        )
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["components"]["mpd"]["running"])
        self.assertEqual(payload["components"]["metadata"]["pending"], 0)
        self.assertEqual(payload["components"]["transcode"]["queued"], 0)

    def test_health_payload_isolates_broken_library_error_sequence(self):
        class BrokenSequence:
            def __len__(self):
                raise RuntimeError("broken sequence")

        payload = build_health_payload(
            server_name="fnAudio", request_id="request-3",
            mpd={}, scan_state={"errors": BrokenSequence()}, metadata={},
            transcode={}, dlna_running=False, renderer_count=0, metrics={},
            library_query_cache={},
        )
        self.assertEqual(payload["components"]["library"]["errors"], 0)

    def test_health_payload_keeps_operational_counters_without_library_content(self):
        payload = build_health_payload(
            server_name="fnAudio test",
            request_id="request-1",
            mpd={"running": True, "fault": {"state": ""}, "playback_errors": {}},
            scan_state={"running": False, "cancelled": False, "timed_out": False, "errors": ["one"]},
            metadata={"running": True, "pending": 2, "pending_limit": 10, "dropped": 1, "network_workers_active": 3, "network_worker_limit": 4, "artwork_bytes": 100, "artwork_limit_bytes": 200, "status_cache": {"ttl_ms": 750, "age_ms": 12, "hits": 4, "misses": 2, "private": "/vol1/secret"}},
            transcode={
                "queued": 3,
                "tracked": 5,
                "queue_limit": 64,
                "private_path": "/vol1/secret",
                "ffmpeg": {"active": 1, "limit": 2, "waiting": 1, "waiter_rejected": 2, "waiter_limit": 32, "command": "ffmpeg /vol1/secret"},
            },
            dlna_running=True,
            renderer_count=2,
            metrics={"requests": 3},
            library_query_cache={"hits": 4, "misses": 2, "hit_rate": 0.6667},
            library_search_index={"mode": "fts5-trigram", "substring_minimum_chars": 3},
            thumbnail_prewarm={"interactive": {"queued": 2, "limit": 96}, "library": {"queued": 24, "limit": 5000, "dropped": 7, "root_limit": 8, "root_rejected": 3}},
            cover_cache={"entries": 12, "limit": 512, "inflight": 2, "inflight_limit": 64, "private_path": "/vol1/secret"},
            cache_failures={"load": 4, "save": "7", "private": "/vol1/secret"},
            library_storage={"database_bytes": 100, "wal_bytes": 20, "shm_bytes": 3, "total_bytes": 123, "path": "/vol1/secret"},
            dlna_discovery={"refreshing": True, "workers": 1, "worker_limit": 1, "cached_renderers": 2, "refresh_skipped": 3},
            dlna_eventing={"subscriptions": 2, "subscription_limit": 64, "workers": 1, "worker_limit": 4, "pending": 3, "pending_limit": 64, "peak_pending": 4, "accepted": 5, "dropped": 1},
            playback_command_cache={"entries": 4, "limit": 1024, "saturated": False, "inflight": 2, "inflight_limit": 1024, "private": "ignore"},
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["components"]["library"]["query_cache"], {"hits": 4, "misses": 2, "hit_rate": 0.6667})
        self.assertEqual(payload["components"]["library"]["search_index"]["mode"], "fts5-trigram")
        self.assertEqual(payload["components"]["library"]["cover_cache"], {"entries": 12, "limit": 512, "inflight": 2, "inflight_limit": 64})
        self.assertEqual(payload["components"]["library"]["cache_failures"], {"load": 4, "save": 7})
        self.assertEqual(payload["components"]["library"]["storage"], {"database_bytes": 100, "wal_bytes": 20, "shm_bytes": 3, "total_bytes": 123})
        self.assertNotIn("items", payload["components"]["library"])
        self.assertEqual(payload["components"]["metadata"]["pending"], 2)
        self.assertEqual(payload["components"]["metadata"]["network_workers_active"], 3)
        self.assertEqual(payload["components"]["metadata"]["network_worker_limit"], 4)
        self.assertEqual(payload["components"]["metadata"]["status_cache"], {"ttl_ms": 750, "age_ms": 12, "hits": 4, "misses": 2})
        self.assertEqual(payload["components"]["dlna"]["renderers"], 2)
        self.assertEqual(payload["components"]["dlna"]["discovery"]["worker_limit"], 1)
        self.assertEqual(payload["components"]["dlna"]["discovery"]["refresh_skipped"], 3)
        self.assertEqual(payload["components"]["dlna"]["eventing"]["pending_limit"], 64)
        self.assertEqual(payload["components"]["dlna"]["eventing"]["dropped"], 1)
        self.assertEqual(payload["components"]["transcode"]["ffmpeg"]["active"], 1)
        self.assertEqual(payload["components"]["transcode"]["ffmpeg"]["waiter_rejected"], 2)
        self.assertEqual(payload["components"]["transcode"]["ffmpeg"]["waiter_limit"], 32)
        self.assertEqual(payload["components"]["playback"]["command_cache"], {"entries": 4, "limit": 1024, "saturated": False, "inflight": 2, "inflight_limit": 1024})
        self.assertEqual(payload["components"]["library"]["thumbnail_prewarm"]["interactive"]["limit"], 96)
        self.assertEqual(payload["components"]["library"]["thumbnail_prewarm"]["library"]["limit"], 5000)
        self.assertEqual(payload["components"]["library"]["thumbnail_prewarm"]["library"]["dropped"], 7)
        self.assertEqual(payload["components"]["library"]["thumbnail_prewarm"]["library"]["root_limit"], 8)
        self.assertEqual(payload["components"]["library"]["thumbnail_prewarm"]["library"]["root_rejected"], 3)
        self.assertNotIn("private_path", str(payload["components"]["transcode"]))
        self.assertNotIn("command", str(payload["components"]["transcode"]))

    def test_health_summary_refuses_object_coercion_and_non_finite_counters(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("health must not coerce arbitrary objects")

            def __str__(self):
                raise AssertionError("health must not stringify arbitrary objects")

        payload = build_health_payload(
            server_name=Explosive(), request_id=Explosive(), mpd={}, scan_state={},
            metadata={"pending": Explosive(), "dropped": float("inf"), "artwork_bytes": -5, "status_cache": {"hits": Explosive()}},
            transcode={"queued": Explosive(), "ffmpeg": {"wait_seconds": float("nan")}},
            dlna_running=False, renderer_count=Explosive(), metrics={}, library_query_cache={},
        )
        self.assertEqual(payload["name"], "fnAudio")
        self.assertEqual(payload["request_id"], "")
        self.assertEqual(payload["components"]["metadata"]["pending"], 0)
        self.assertEqual(payload["components"]["metadata"]["dropped"], 0)
        self.assertEqual(payload["components"]["metadata"]["artwork_bytes"], 0)
        self.assertEqual(payload["components"]["metadata"]["status_cache"]["hits"], 0)
        self.assertEqual(payload["components"]["dlna"]["renderers"], 0)
        self.assertEqual(payload["components"]["transcode"]["queued"], 0)
        self.assertEqual(payload["components"]["transcode"]["ffmpeg"]["wait_seconds"], 0.0)

    def test_health_metrics_are_top_level_bounded_and_copied(self):
        metrics = {"": 1, "x" * 257: 2, "ok": {"count": 3}}
        payload = build_health_payload(
            server_name="fnAudio", request_id="", mpd={}, scan_state={}, metadata={},
            transcode={}, dlna_running=False, renderer_count=0, metrics=metrics,
            library_query_cache={},
        )
        self.assertNotIn("", payload["metrics"])
        self.assertNotIn("x" * 257, payload["metrics"])
        self.assertEqual(payload["metrics"]["ok"], {"count": 3})
        self.assertIsNot(payload["metrics"], metrics)

    def test_health_metrics_bound_nested_values_and_reject_objects(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("metrics must not stringify arbitrary objects")

        payload = build_health_payload(
            server_name="fnAudio", request_id="", mpd={}, scan_state={}, metadata={},
            transcode={}, dlna_running=False, renderer_count=0,
            metrics={"nested": {"text": "x" * 5000, "bad": Explosive()}},
            library_query_cache={},
        )
        self.assertEqual(len(payload["metrics"]["nested"]["text"]), 4096)
        self.assertEqual(payload["metrics"]["nested"]["bad"], "[UNAVAILABLE]")


    def _mpd_payload(self, playback_errors):
        return build_health_payload(
            server_name="fnAudio",
            request_id="request-playback-errors",
            mpd={"running": True, "fault": {"state": ""}, "playback_errors": playback_errors},
            scan_state={},
            metadata={},
            transcode={},
            dlna_running=False,
            renderer_count=0,
            metrics={},
            library_query_cache={},
        )["components"]["mpd"]["error_category"]

    def test_health_reports_the_latest_severe_playback_error(self):
        summary = classify_mpd_log_errors(
            "output: buffer underrun\n"
            "flac: invalid frame header, skipping frame\n"
        )

        self.assertEqual(summary["last_category"], "source_corrupt")
        self.assertEqual(self._mpd_payload(summary), "source_corrupt")

    def test_health_keeps_warning_only_playback_errors_out_of_the_category(self):
        summary = classify_mpd_log_errors("output: buffer underrun\n")

        self.assertEqual(summary["count"], 1)
        self.assertEqual(self._mpd_payload(summary), "")

    def test_playback_error_summary_survives_a_non_numeric_limit(self):
        # The classifier feeds the health payload.  `int(limit)` used to raise on a
        # drifted bound, so one bad value took the whole report down instead of
        # shrinking it.  Coercion must not change the answer, only avoid the raise.
        log = "output: buffer underrun\nflac: invalid frame header, skipping frame\n"
        base = classify_mpd_log_errors(log)
        self.assertGreater(base["count"], 0, "the fixture stopped classifying anything")
        for drifted in ("40", None, [], 3.9, True, {}, float("nan")):
            with self.subTest(limit=repr(drifted)):
                self.assertEqual(classify_mpd_log_errors(log, drifted), base)
        # Zero kept its old meaning of "unset" (`limit or 20`), and an absurd bound
        # is still clamped to the documented ceiling rather than slicing the log.
        self.assertEqual(classify_mpd_log_errors(log, 0), base)
        self.assertEqual(classify_mpd_log_errors(log, 10 ** 9), base)
        # A negative bound is not "unset": it clamps to the floor, exactly as
        # `max(1, min(100, -5))` did before the coercion existed.
        self.assertEqual(classify_mpd_log_errors(log, -5), classify_mpd_log_errors(log, 1))
        self.assertEqual(classify_mpd_log_errors(log, -5)["count"], 1)

    def test_health_projects_a_broken_playback_error_summary_as_no_error(self):
        class BrokenDict(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken playback error state")

        for unusable in (
            BrokenDict(),
            None,
            "source_corrupt",
            {"items": "not a list"},
            {"items": 5},
            {"items": ["x"]},
            {"items": [[["severity", "error"], ["category", "source_corrupt"]]]},
        ):
            with self.subTest(summary=str(unusable)[:24]):
                self.assertEqual(self._mpd_payload(unusable), "")



    def test_health_forwards_local_lyrics_cache_byte_pressure(self):
        # Every field the cache reports has to be whitelisted AND emitted. An
        # omitted whitelist entry reads as a permanent zero, which is how the MPD
        # error category stayed empty; a missing emit entry drops the value. Both
        # are caught here against the real producer. The document is deliberately
        # over one megabyte so a byte total that shares the count ceiling of
        # one million cannot pass.
        body = "x" * 2000000
        cache = LocalLyricsCache(lambda path: body)
        cache.read("/vol1/private/song.lrc", (1, 1))
        projected = build_health_payload(
            server_name="fnAudio", request_id="r", mpd={}, scan_state={},
            metadata={"local_lyrics_cache": cache.snapshot()}, transcode={},
            dlna_running=False, renderer_count=0, metrics={}, library_query_cache={},
        )["components"]["metadata"]["local_lyrics_cache"]

        self.assertEqual(set(projected), set(cache.snapshot()))
        self.assertEqual(projected["bytes"], sys.getsizeof(body))
        self.assertGreater(projected["bytes"], 1000000)
        self.assertEqual(projected["bytes_limit"], cache.snapshot()["bytes_limit"])
        self.assertNotIn("song", str(projected))

if __name__ == "__main__":
    unittest.main()
