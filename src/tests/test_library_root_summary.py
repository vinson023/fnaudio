import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "server"))

from library_root_summary import MAX_ROOT_SUMMARY_CHARS, decode_root_summary


class LibraryRootSummaryTests(unittest.TestCase):
    def test_decodes_only_complete_configured_roots(self):
        raw = json.dumps({
            "/music-a": {"track_count": 2, "cover_track_id": "a"},
            "/music-b": {"track_count": -1, "cover_track_id": ""},
        })
        self.assertEqual(
            decode_root_summary(raw, ["/music-a", "/music-b"]),
            {
                "/music-a": {"root": "/music-a", "track_count": 2, "cover_track_id": "a"},
                "/music-b": {"root": "/music-b", "track_count": 0, "cover_track_id": ""},
            },
        )

    def test_rejects_corrupt_oversized_and_mismatched_summary(self):
        self.assertIsNone(decode_root_summary("not json", ["/music"]))
        self.assertIsNone(decode_root_summary("x" * (MAX_ROOT_SUMMARY_CHARS + 1), ["/music"]))
        self.assertIsNone(decode_root_summary(json.dumps({"/other": {}}), ["/music"]))
        self.assertIsNone(decode_root_summary(json.dumps({"/music": {"track_count": 1, "cover_track_id": 2}}), ["/music"]))

    def test_normalizes_untrusted_track_count_without_object_conversion(self):
        decoded = decode_root_summary(
            json.dumps({"/music": {"track_count": "not-a-count", "cover_track_id": "a"}}),
            ["/music"],
        )
        self.assertEqual(decoded["/music"]["track_count"], 0)


if __name__ == "__main__":
    unittest.main()
