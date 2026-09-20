import math
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "server")))

from metadata_track_match_policy import (
    MAX_PERSISTED_CANDIDATE_TEXT, MAX_PERSISTED_TRACK_CANDIDATES,
    MAX_TRACK_MATCH_JSON_BYTES, decode_track_match_fields,
    finite_candidate_confidence,
    normalize_track_candidates, track_match_fields_are_valid, valid_artwork_id,
)


class MetadataTrackMatchPolicyTests(unittest.TestCase):
    def test_artwork_id_compatibility_export_remains_strict(self):
        self.assertTrue(valid_artwork_id("a" * 64))
        self.assertFalse(valid_artwork_id("../cover.jpg"))

    def test_confidence_rejects_non_finite_and_boolean_values(self):
        self.assertEqual(finite_candidate_confidence(float("nan")), 0.0)
        self.assertEqual(finite_candidate_confidence(float("inf")), 0.0)
        self.assertEqual(finite_candidate_confidence(True), 0.0)
        self.assertEqual(finite_candidate_confidence("0.83"), 0.83)

    def test_normalization_is_bounded_detached_and_does_not_mutate_provider(self):
        original = {"title": "Song", "confidence": "bad"}
        values = [original, None, "invalid"] + [{"title": "Other", "confidence": 0.9}] * 100
        result = normalize_track_candidates(values)
        self.assertLessEqual(len(result), 64)
        self.assertEqual(result[0]["confidence"], 0.0)
        self.assertEqual(original["confidence"], "bad")
        self.assertTrue(all(math.isfinite(item["confidence"]) for item in result))

    def test_normalization_persists_only_bounded_display_fields(self):
        original = {
            "title": "T" * 1000,
            "artist": "Artist",
            "confidence": 0.9,
            "provider_blob": "x" * (1024 * 1024),
            "nested": {"untrusted": "payload"},
        }
        result = normalize_track_candidates([original] * (MAX_PERSISTED_TRACK_CANDIDATES + 3))

        self.assertEqual(len(result), MAX_PERSISTED_TRACK_CANDIDATES)
        self.assertEqual(set(result[0]), {
            "title", "artist", "album", "album_artist", "date", "genre",
            "track_no", "disc_no", "image_url", "provider_id", "source", "confidence",
        })
        self.assertEqual(len(result[0]["title"]), MAX_PERSISTED_CANDIDATE_TEXT)
        self.assertNotIn("provider_blob", result[0])
        self.assertEqual(original["title"], "T" * 1000)

    def test_decode_rejects_oversized_or_non_mapping_legacy_rows(self):
        self.assertEqual(decode_track_match_fields("x" * (MAX_TRACK_MATCH_JSON_BYTES + 1)), {})
        self.assertEqual(decode_track_match_fields("[]"), {})
        self.assertEqual(decode_track_match_fields('{"best":{"title":"Song"}}'), {"best": {"title": "Song"}})
        self.assertTrue(track_match_fields_are_valid("{}"))
        self.assertFalse(track_match_fields_are_valid("[]"))


if __name__ == "__main__":
    unittest.main()
