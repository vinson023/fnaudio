import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "server")))

from metadata_artwork_policy import artwork_url, is_artwork_url, normalize_artwork_id, valid_artwork_id


class MetadataArtworkPolicyTests(unittest.TestCase):
    def test_normalizes_only_bounded_sha256_ids(self):
        value = " A" + ("B" * 63)
        self.assertEqual(normalize_artwork_id(value), "a" + ("b" * 63))
        self.assertTrue(valid_artwork_id("C" * 64))
        self.assertFalse(valid_artwork_id("a" * 63))
        self.assertFalse(valid_artwork_id("../cover.jpg"))
        self.assertFalse(valid_artwork_id(None))

    def test_projects_safe_relative_url(self):
        artwork_id = "d" * 64
        self.assertEqual(artwork_url(" " + artwork_id.upper() + " "), "metadata/artwork/" + artwork_id)
        self.assertEqual(artwork_url("invalid"), "")

    def test_accepts_only_canonical_relative_artwork_urls(self):
        artwork_id = "e" * 64
        self.assertTrue(is_artwork_url("metadata/artwork/" + artwork_id))
        self.assertFalse(is_artwork_url("metadata/artwork/" + artwork_id.upper()))
        self.assertFalse(is_artwork_url("metadata/artwork/../" + artwork_id))
        self.assertFalse(is_artwork_url("/metadata/artwork/" + artwork_id))
        self.assertFalse(is_artwork_url(None))


if __name__ == "__main__":
    unittest.main()
