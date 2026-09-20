import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "server"))

import metadata_candidate_cache_key
from metadata_candidate_cache_key import MAX_CACHE_TEXT, build_candidate_cache_key


class MetadataCandidateCacheKeyTests(unittest.TestCase):
    def test_key_includes_normalized_query_and_filename_identity(self):
        first = build_candidate_cache_key({
            "title": "One", "artist": "", "album": "", "duration": 180,
            "path": "/music/Artist A - One.flac",
        })
        second = build_candidate_cache_key({
            "title": "One", "artist": "", "album": "", "duration": 180,
            "path": "/music/Artist B - One.flac",
        })
        self.assertNotEqual(first, second)
        self.assertEqual(first[1:3], ("artist a", "one"))

    def test_key_is_bounded_and_rejects_missing_query(self):
        key = build_candidate_cache_key({
            "title": "T" * (MAX_CACHE_TEXT + 20), "artist": "A", "duration": 1,
        })
        self.assertIsNotNone(key)
        self.assertLessEqual(len(key[0]), MAX_CACHE_TEXT)
        self.assertIsNone(build_candidate_cache_key({"title": "", "artist": "", "album": ""}))

    def test_key_does_not_coerce_untrusted_fields(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("cache key must not stringify arbitrary values")

        self.assertIsNotNone(build_candidate_cache_key({
            "title": "One", "artist": "Artist", "album": Explosive(), "duration": Explosive(),
        }))

    def test_precomputed_query_and_filename_hint_skip_duplicate_parsing(self):
        with mock.patch.object(metadata_candidate_cache_key, "track_search_query", side_effect=AssertionError("query recomputed")), \
                mock.patch.object(metadata_candidate_cache_key, "filename_track_hint", side_effect=AssertionError("filename hint recomputed")):
            key = build_candidate_cache_key(
                {"title": "One", "artist": "Artist", "album": "Album", "duration": 180},
                query="Artist One",
                hinted_artist="Artist",
                hinted_title="One",
            )
        self.assertEqual(key[:3], ("artist one", "artist", "one"))


if __name__ == "__main__":
    unittest.main()
