import sys
import unittest

sys.path.insert(0, "app/server")

from metadata_probe_policy import merge_missing_tags, probe_tags_complete


class MetadataProbePolicyTests(unittest.TestCase):
    def test_complete_probe_tags_skip_local_fallback(self):
        tags = {"title": "T", "artist": "A", "album": "B", "composer": "C", "genre": "G", "track_no": 1}
        self.assertTrue(probe_tags_complete(tags))

    def test_partial_probe_tags_require_fallback(self):
        self.assertFalse(probe_tags_complete({"title": "T", "track_no": 1}))
        self.assertFalse(probe_tags_complete({"title": "T", "artist": "A", "album": "B", "composer": "C", "genre": "G", "track_no": 0}))

    def test_fallback_never_overwrites_probe_values(self):
        merged = merge_missing_tags({"title": "probe"}, {"title": "local", "artist": "local-artist"})
        self.assertEqual(merged, {"title": "probe", "artist": "local-artist"})

    def test_broken_probe_mapping_isolated(self):
        class BrokenDict(dict):
            def __iter__(self):
                raise RuntimeError("broken mapping")
        self.assertEqual(merge_missing_tags(BrokenDict(), {"title": "fallback"}), {"title": "fallback"})


if __name__ == "__main__":
    unittest.main()
