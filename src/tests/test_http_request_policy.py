import sys
import unittest

sys.path.insert(0, "app/server")
from http_request_policy import (HTTP_LATENCY_ROUTES, MAX_REQUEST_BODY_BYTES, MAX_REQUEST_PATH,
                                  MAX_REQUEST_TARGET, http_latency_route, request_body_length,
                                  request_path, request_target_allowed,
                                  should_write_http_request)


class HttpRequestPolicyTests(unittest.TestCase):
    def test_fixed_routes_strip_query_without_retaining_request_values(self):
        self.assertEqual(http_latency_route("/api/library?search=private-song"), "library_page")
        self.assertEqual(http_latency_route("/cover/a-secret-track-id?token=hidden"), "cover")
        self.assertEqual(set(HTTP_LATENCY_ROUTES), {
            "library_page", "library_groups", "library_folders", "library_roots",
            "cover", "playback", "static", "other",
        })

    def test_non_text_inputs_do_not_trigger_string_conversion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("request policy must not stringify custom values")

        value = Explosive()
        self.assertEqual(request_path(value), "")
        self.assertEqual(http_latency_route(value), "static")
        self.assertTrue(should_write_http_request(value, value, value))
        self.assertEqual(len(request_path("/api/library" + "x" * (MAX_REQUEST_PATH + 100))), MAX_REQUEST_PATH)

    def test_successful_polling_remains_out_of_the_sync_log_path(self):
        self.assertFalse(should_write_http_request("GET", "/api/playback/status?target=local", 200))
        self.assertFalse(should_write_http_request("HEAD", "/api/playback/events", 200))
        self.assertTrue(should_write_http_request("POST", "/api/playback/status", 200))
        self.assertTrue(should_write_http_request("GET", "/cover/item", 404))

    def test_content_length_is_bounded_without_object_coercion(self):
        self.assertEqual(request_body_length(None), 0)
        self.assertEqual(request_body_length(" 12 "), 12)
        self.assertEqual(request_body_length(str(MAX_REQUEST_BODY_BYTES + 1)), MAX_REQUEST_BODY_BYTES + 1)
        self.assertIsNone(request_body_length("-1"))
        self.assertIsNone(request_body_length("1.5"))
        self.assertIsNone(request_body_length(object()))

    def test_request_target_is_bounded_without_object_coercion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("request target policy must not stringify custom values")

        self.assertTrue(request_target_allowed("/api/health"))
        self.assertFalse(request_target_allowed("x" * (MAX_REQUEST_TARGET + 1)))
        self.assertFalse(request_target_allowed(Explosive()))
        self.assertFalse(request_target_allowed("/api/health", maximum=MAX_REQUEST_TARGET + 1))


if __name__ == "__main__":
    unittest.main()
