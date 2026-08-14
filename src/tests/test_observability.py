import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")
from observability import Observability, redact, request_id


class ObservabilityTests(unittest.TestCase):
    def test_request_id_accepts_safe_value_and_replaces_untrusted_value(self):
        self.assertEqual(request_id("client-12345678"), "client-12345678")
        self.assertRegex(request_id("bad value\nheader"), r"^[0-9a-f]{32}$")

    def test_redaction_removes_nested_credentials(self):
        payload = redact({"token": "one", "nested": {"password": "two", "status": "ok"}})
        self.assertEqual(payload["token"], "[REDACTED]")
        self.assertEqual(payload["nested"], {"password": "[REDACTED]", "status": "ok"})

    def test_structured_log_is_json_and_does_not_emit_secrets(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "events.jsonl")
            metrics = Observability()
            metrics.write(path, "request", request_id="abc", authorization="Bearer secret", status=200)
            with open(path, encoding="utf-8") as handle:
                row = json.loads(handle.read())
            self.assertEqual(row["authorization"], "[REDACTED]")
            self.assertEqual(row["status"], 200)

    def test_structured_log_rotates_at_the_size_bound(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "events.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("old-data")
            Observability().write(path, "request", max_bytes=4, status=200)
            self.assertTrue(os.path.isfile(path + ".1"))
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(json.loads(handle.read())["event"], "request")


if __name__ == "__main__":
    unittest.main()
