import sys
import unittest

sys.path.insert(0, "app/server")

from metadata_provider_failure_policy import provider_activity_snapshot, provider_failure_snapshot


class MetadataProviderFailurePolicyTests(unittest.TestCase):
    def test_projects_bounded_failure_fields(self):
        snapshot = provider_failure_snapshot({
            "qq": {"count": "2", "last_error": "ValueError: bad\nresponse", "cooldown_seconds": 23},
        })
        self.assertEqual(snapshot, {
            "qq": {"count": 2, "last_error": "ValueError: bad response", "cooldown_seconds": 23},
        })

    def test_rejects_objects_and_clamps_corrupt_values(self):
        snapshot = provider_failure_snapshot({
            object(): {"count": 3},
            "bad": object(),
            "netease": {"count": True, "last_error": object(), "cooldown_seconds": -5},
            "migu": {"count": 999999999, "last_error": "x" * 500, "cooldown_seconds": 999},
        })
        self.assertEqual(list(snapshot), ["migu"])
        self.assertEqual(snapshot["migu"]["count"], 1000000)
        self.assertEqual(len(snapshot["migu"]["last_error"]), 240)
        self.assertEqual(snapshot["migu"]["cooldown_seconds"], 60)

    def test_limits_number_of_provider_rows(self):
        source = {"provider-%s" % index: {"count": 1} for index in range(30)}
        self.assertEqual(len(provider_failure_snapshot(source)), 16)

    def test_activity_projects_only_bounded_reachability_fields(self):
        self.assertEqual(
            provider_activity_snapshot({"qq": {"successes": "3", "last_success_seconds_ago": 12, "query": "private"}}),
            {"qq": {"successes": 3, "last_success_seconds_ago": 12}},
        )
        self.assertEqual(provider_activity_snapshot({"bad": {"successes": True}}), {})

    def test_activity_keeps_outcome_only_provider_rows(self):
        self.assertEqual(
            provider_activity_snapshot({
                "qq": {"successes": 0, "empty_results": 2},
                "netease": {"successes": 0, "no_valid_candidates": "3"},
                "bad": {"successes": 0, "empty_results": object()},
            }),
            {
                "qq": {"successes": 0, "last_success_seconds_ago": 0, "empty_results": 2},
                "netease": {"successes": 0, "last_success_seconds_ago": 0, "no_valid_candidates": 3},
            },
        )


if __name__ == "__main__":
    unittest.main()
