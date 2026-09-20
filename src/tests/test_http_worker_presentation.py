import unittest

from http_worker_presentation import project_http_workers


class HttpWorkerPresentationTests(unittest.TestCase):
    def test_projects_known_fields_and_normalizes_values(self):
        self.assertEqual(
            project_http_workers({"active": 2, "limit": 8, "peak": -1, "extra": 9}),
            {"active": 2, "limit": 8, "peak": 0, "acquired": 0, "rejected": 0,
             "event_stream_active": 0, "event_stream_limit": 0, "event_stream_peak": 0,
             "event_stream_acquired": 0, "event_stream_rejected": 0},
        )

    def test_rejects_non_mapping_and_broken_access(self):
        expected = {key: 0 for key in ("active", "limit", "peak", "acquired", "rejected")}
        expected.update({"event_stream_" + key: 0 for key in ("active", "limit", "peak", "acquired", "rejected")})
        self.assertEqual(project_http_workers(None), expected)

        class Broken(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken")

        self.assertEqual(project_http_workers(Broken()), expected)


if __name__ == "__main__":
    unittest.main()
