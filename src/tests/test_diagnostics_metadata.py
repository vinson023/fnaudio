import sys
import unittest

sys.path.insert(0, "app/server")

from diagnostics_metadata import metadata_summary


class DiagnosticsMetadataTests(unittest.TestCase):
    def test_summary_keeps_bounded_metadata_pressure_fields(self):
        self.assertEqual(
            metadata_summary({"running": True, "pending": 2, "dropped": 1, "network_workers_active": 3, "network_worker_limit": 4, "provider_failures": {"qq": {"count": 2, "last_error": "timeout", "cooldown_seconds": 20, "private": "/secret"}}, "provider_activity": {"qq": {"successes": 3, "last_success_seconds_ago": 12, "empty_results": 4, "no_valid_candidates": 2, "private": "/secret"}}, "status_cache": {"ttl_ms": 750, "age_ms": 12, "hits": 4, "misses": 2, "private": "/secret"}, "provider_candidate_cache": {"entries": 1, "limit": 128, "hits": 5, "misses": 2, "private": "/secret"}, "local_lyrics_cache": {"entries": 2, "limit": 256, "bytes": 8388608, "bytes_limit": 8388608, "hits": 6, "misses": 3, "private": "/secret"}}),
            {"running": True, "pending": 2, "dropped": 1, "network_workers_active": 3, "network_worker_limit": 4, "provider_failures": {"qq": {"count": 2, "last_error": "timeout", "cooldown_seconds": 20}}, "provider_activity": {"qq": {"successes": 3, "last_success_seconds_ago": 12, "empty_results": 4, "no_valid_candidates": 2}}, "status_cache": {"ttl_ms": 750, "age_ms": 12, "hits": 4, "misses": 2}, "provider_candidate_cache": {"entries": 1, "limit": 128, "hits": 5, "misses": 2, "ttl_ms": 0}, "local_lyrics_cache": {"entries": 2, "limit": 256, "bytes": 8388608, "bytes_limit": 8388608, "hits": 6, "misses": 3}},
        )

    def test_summary_isolates_broken_mapping_access(self):
        class BrokenDict(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken state")

        self.assertEqual(metadata_summary(BrokenDict())["status_cache"]["hits"], 0)
        self.assertEqual(metadata_summary({"status_cache": BrokenDict()})["status_cache"]["hits"], 0)
        self.assertEqual(metadata_summary({"provider_failures": BrokenDict()})["provider_failures"], {})
        self.assertEqual(metadata_summary({"provider_activity": BrokenDict()})["provider_activity"], {})


if __name__ == "__main__":
    unittest.main()
