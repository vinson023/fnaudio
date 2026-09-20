import sys
import unittest

sys.path.insert(0, "app/server")

from json_response_policy import MAX_JSON_RESPONSE_BYTES, serialize_json_response


class JsonResponsePolicyTests(unittest.TestCase):
    def test_serializes_normal_payload(self):
        body, valid = serialize_json_response({"ok": True, "text": "音乐"})
        self.assertTrue(valid)
        self.assertIn("音乐".encode("utf-8"), body)
        self.assertNotIn(b": ", body)

    def test_rejects_oversized_payload_without_returning_partial_json(self):
        body, valid = serialize_json_response({"data": "x" * 100 }, maximum=32)
        self.assertFalse(valid)
        self.assertEqual(body, b'{"ok":false,"error":"response exceeds size limit"}')

    def test_rejects_serialization_failures(self):
        payload = {}
        payload["self"] = payload
        body, valid = serialize_json_response(payload)
        self.assertFalse(valid)
        self.assertIn(b"serialization failed", body)

    def test_invalid_limit_uses_default(self):
        body, valid = serialize_json_response({"ok": True}, maximum=True)
        self.assertTrue(valid)
        self.assertLess(len(body), MAX_JSON_RESPONSE_BYTES)

    def test_custom_limit_cannot_raise_global_response_budget(self):
        body, valid = serialize_json_response({"data": "x" * (MAX_JSON_RESPONSE_BYTES + 1)}, maximum=MAX_JSON_RESPONSE_BYTES * 2)
        self.assertFalse(valid)
        self.assertIn(b"response exceeds size limit", body)
