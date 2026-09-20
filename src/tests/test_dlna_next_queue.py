import sys
import unittest

sys.path.insert(0, "app/server")

from dlna.next_queue import (
    MAX_NEXT_METADATA_CHARS,
    MAX_NEXT_QUEUE_ENTRIES,
    MAX_NEXT_URI_CHARS,
    bounded_next_queue,
)


class DlnaNextQueueTests(unittest.TestCase):
    def test_fifo_queue_is_bounded_and_keeps_earliest_entries(self):
        existing = [{"uri": "http://example/%s" % index, "metadata": ""} for index in range(MAX_NEXT_QUEUE_ENTRIES)]
        queue, accepted = bounded_next_queue(existing, "http://example/overflow", "")
        self.assertFalse(accepted)
        self.assertEqual(len(queue), MAX_NEXT_QUEUE_ENTRIES)
        self.assertEqual(queue[0]["uri"], "http://example/0")

    def test_clear_and_payload_limits_keep_standard_next_uri_semantics(self):
        queue, accepted = bounded_next_queue([{"uri": "http://example/one", "metadata": ""}], "", "")
        self.assertTrue(accepted)
        self.assertEqual(queue, [])
        queue, accepted = bounded_next_queue([], "x" * (MAX_NEXT_URI_CHARS + 1), "")
        self.assertFalse(accepted)
        self.assertEqual(queue, [])
        queue, accepted = bounded_next_queue([], "http://example/one", "x" * (MAX_NEXT_METADATA_CHARS + 1))
        self.assertFalse(accepted)
        self.assertEqual(queue, [])

    def test_damaged_existing_queue_is_materialized_only_to_its_limit(self):
        class BrokenEntries:
            def __iter__(self):
                yield {"uri": "http://example/one", "metadata": ""}
                raise RuntimeError("broken state")

        queue, accepted = bounded_next_queue(BrokenEntries(), "http://example/two", "")
        self.assertTrue(accepted)
        self.assertEqual([entry["uri"] for entry in queue], ["http://example/one", "http://example/two"])
