import sys
import unittest

sys.path.insert(0, "app/server")

from response_header_policy import MAX_HEADERS, normalize_response_headers


class ResponseHeaderPolicyTests(unittest.TestCase):
    def test_keeps_valid_text_headers(self):
        self.assertEqual(normalize_response_headers({" X-Test ": " value ", "Link": "</next>"}), {"X-Test": "value", "Link": "</next>"})

    def test_rejects_non_text_injection_and_oversized_values(self):
        source = {"X-Number": 1, "X-Bad": "ok\r\nInjected: yes", "X-Large": "x" * 3000}
        self.assertEqual(normalize_response_headers(source), {})

    def test_limits_header_count_without_coercion(self):
        headers = {"X-%s" % index: "ok" for index in range(MAX_HEADERS + 5)}
        result = normalize_response_headers(headers)
        self.assertEqual(len(result), MAX_HEADERS)

    def test_broken_mapping_is_safe(self):
        class Broken(dict):
            def items(self):
                raise RuntimeError("broken")
        self.assertEqual(normalize_response_headers(Broken()), {})
