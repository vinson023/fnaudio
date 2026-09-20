import sys
import unittest

sys.path.insert(0, "app/server")

from http_observation import observe_http_request
from observability import Observability


class HttpObservationTests(unittest.TestCase):
    def test_observation_projects_paths_once_without_query_data(self):
        result = observe_http_request("GET", "/api/library?search=private-song", 200, 0.125)
        self.assertEqual(result["route"], "/api/library")
        self.assertEqual(result["latency_route"], "library_page")
        self.assertEqual(result["status_counter"], "http_status_2xx")
        self.assertTrue(result["write_log"])
        self.assertNotIn("private-song", repr(result))

    def test_observation_keeps_error_logging_and_normalizes_bad_values(self):
        class Explosive:
            def __float__(self):
                raise AssertionError("observation must not coerce arbitrary values")

        result = observe_http_request("GET", "/cover/private-id?x=hidden", True, Explosive())
        self.assertEqual(result["route"], "/cover/private-id")
        self.assertEqual(result["status_counter"], "http_status_5xx")
        self.assertEqual(result["elapsed_seconds"], 0.0)
        self.assertTrue(result["write_log"])

    def test_metrics_accept_an_already_projected_route(self):
        metrics = Observability()
        metrics.record_http_latency_route("library_page", 0.25)
        metrics.record_http_latency_route("private-route", 0.5)
        snapshot = metrics.snapshot()["http_latency"]
        self.assertEqual(snapshot["library_page"]["count"], 1)
        self.assertEqual(snapshot["static"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
