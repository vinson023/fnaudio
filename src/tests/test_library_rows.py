import sys
import unittest

sys.path.insert(0, "app/server")

from library_rows import MAX_ITEM_JSON_BYTES, decode_item_row, decode_item_rows


class LibraryRowTests(unittest.TestCase):
    def test_decoder_skips_malformed_rows_and_preserves_order(self):
        rows = [{"item_json": "{\"id\":\"one\"}"}, {"item_json": "not-json"}, {"item_json": "{\"id\":\"two\"}"}, {"wrong": "column"}]
        self.assertEqual(decode_item_rows(rows), [{"id": "one"}, {"id": "two"}])

    def test_single_decoder_handles_missing_or_invalid_rows(self):
        self.assertEqual(decode_item_row({"item_json": "{\"id\":\"one\"}"}), {"id": "one"})
        self.assertIsNone(decode_item_row(None))
        self.assertIsNone(decode_item_row({"item_json": "bad"}))

    def test_decoder_skips_oversized_or_non_mapping_payloads(self):
        oversized = "x" * MAX_ITEM_JSON_BYTES
        rows = [{"item_json": oversized}, {"item_json": "[1,2]"}, {"item_json": "{\"id\":\"ok\"}"}]
        self.assertEqual(decode_item_rows(rows), [{"id": "ok"}])
        self.assertEqual(decode_item_rows(None), [])
        self.assertEqual(decode_item_rows("not rows"), [])

    def test_decoder_isolates_row_accessor_failures(self):
        class BrokenRow:
            def __getitem__(self, key):
                raise RuntimeError("broken row")

        rows = [BrokenRow(), {"item_json": "{\"id\":\"ok\"}"}]
        self.assertEqual(decode_item_rows(rows), [{"id": "ok"}])

    def test_decoder_accepts_multibyte_payload_at_byte_limit(self):
        value = "音" * 10000
        payload = "{\"title\":\"" + value + "\"}"
        self.assertEqual(decode_item_rows([{"item_json": payload}])[0]["title"], value)

    def test_decoder_rejects_multibyte_payload_at_character_boundary_over_byte_limit(self):
        prefix = "{\"title\":\""
        suffix = "\"}"
        value = "音" * (MAX_ITEM_JSON_BYTES // 2 - len(prefix) - len(suffix))
        payload = prefix + value + suffix
        self.assertEqual(len(payload), MAX_ITEM_JSON_BYTES // 2)
        self.assertGreater(len(payload.encode("utf-8")), MAX_ITEM_JSON_BYTES)
        self.assertEqual(decode_item_rows([{"item_json": payload}]), [])
