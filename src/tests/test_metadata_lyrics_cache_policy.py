import sys
import unittest

sys.path.insert(0, "app/server")

from metadata_lyrics_cache_policy import cached_lyrics_is_fresh


class MetadataLyricsCachePolicyTests(unittest.TestCase):
    def test_requires_non_empty_lyrics_and_future_expiry(self):
        self.assertTrue(cached_lyrics_is_fresh({"lyrics": "line", "expires_at": 11}, 10))
        self.assertFalse(cached_lyrics_is_fresh({"lyrics": "line", "expires_at": 10}, 10))
        self.assertFalse(cached_lyrics_is_fresh({"lyrics": "", "expires_at": 11}, 10))

    def test_artwork_only_and_malformed_rows_fail_closed(self):
        self.assertFalse(cached_lyrics_is_fresh({"lyrics": "", "artwork_id": "a" * 64, "expires_at": 99}, 1))
        self.assertFalse(cached_lyrics_is_fresh({"lyrics": object(), "expires_at": 99}, 1))
        self.assertFalse(cached_lyrics_is_fresh(None, 1))

    def test_rejects_non_finite_or_boolean_times(self):
        self.assertFalse(cached_lyrics_is_fresh({"lyrics": "line", "expires_at": float("nan")}, 1))
        self.assertFalse(cached_lyrics_is_fresh({"lyrics": "line", "expires_at": True}, 1))


if __name__ == "__main__":
    unittest.main()
