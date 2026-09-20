import unittest

from metadata_candidate_search_policy import finalize_track_candidates, prefer_track_candidate, should_stop_track_candidate_search


class MetadataCandidateSearchPolicyTests(unittest.TestCase):
    def test_complete_high_confidence_candidate_stops_fanout(self):
        self.assertTrue(should_stop_track_candidate_search({
            "title": "Song", "artist": "Artist", "album": "Album",
            "image_url": "https://example.test/art.jpg", "confidence": 0.95,
        }))

    def test_sparse_or_ambiguous_candidate_keeps_fallback_chain(self):
        base = {"title": "Song", "artist": "Artist", "album": "Album", "confidence": 0.95}
        self.assertFalse(should_stop_track_candidate_search(base))
        base["image_url"] = "https://example.test/art.jpg"
        base["confidence"] = 0.90
        self.assertFalse(should_stop_track_candidate_search(base))

    def test_untrusted_values_fail_closed(self):
        self.assertFalse(should_stop_track_candidate_search({"confidence": object()}))

    def test_non_finite_confidence_never_stops_provider_fanout(self):
        candidate = {
            "title": "Song", "artist": "Artist", "album": "Album",
            "image_url": "https://example.test/art.jpg",
        }
        for confidence in (float("nan"), float("inf"), float("-inf"), True):
            candidate["confidence"] = confidence
            self.assertFalse(should_stop_track_candidate_search(candidate))

    def test_invalid_stop_threshold_falls_back_without_raising(self):
        candidate = {
            "title": "Song", "artist": "Artist", "album": "Album",
            "image_url": "https://example.test/art.jpg", "confidence": 0.95,
        }
        self.assertFalse(should_stop_track_candidate_search(candidate, minimum_confidence=object()))
        self.assertFalse(should_stop_track_candidate_search(candidate, minimum_confidence=float("nan")))

    def test_finalize_filters_deduplicates_and_bounds(self):
        values = [
            {"title": "Song", "artist": "A", "album": "X", "confidence": 0.8},
            {"title": "Song", "artist": "A", "album": "X", "image_url": "art", "confidence": 0.7},
            {"title": "", "artist": "A", "confidence": 1.0},
            {"title": "Bad", "confidence": object()},
        ]
        result = finalize_track_candidates(values)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["image_url"], "art")

    def test_finalize_rejects_untrusted_container_and_limit(self):
        self.assertEqual(finalize_track_candidates(object()), [])
        self.assertEqual(finalize_track_candidates([], limit=object()), [])
        self.assertEqual(finalize_track_candidates([], limit=True), [])
        self.assertEqual(finalize_track_candidates([], minimum_confidence=float("nan")), [])

    def test_finalize_rejects_fractional_candidate_limit(self):
        values = [
            {"title": "One", "confidence": 0.9},
            {"title": "Two", "confidence": 0.8},
        ]
        self.assertEqual(len(finalize_track_candidates(values, limit=1.5)), 2)

    def test_finalize_rejects_non_finite_candidate_confidence(self):
        self.assertEqual(finalize_track_candidates([
            {"title": "Bad", "confidence": float("inf")},
            {"title": "Also bad", "confidence": float("nan")},
            {"title": "Boolean bad", "confidence": True},
        ]), [])

    def test_complete_candidate_wins_over_higher_scoring_sparse_duplicate(self):
        self.assertTrue(prefer_track_candidate(
            {"title": "Song", "artist": "Artist", "album": "Album",
             "album_artist": "Artist", "image_url": "https://img.test/a.jpg", "confidence": 0.88},
            {"title": "Song", "artist": "Artist", "album": "Album",
             "album_artist": "Artist", "image_url": "", "confidence": 0.97},
        ))

    def test_preference_and_sorting_fail_closed_for_untrusted_fields(self):
        class Explosive:
            def __bool__(self):
                raise AssertionError("candidate fields must not use arbitrary truthiness")

        candidate = {"title": "Song", "artist": "Artist", "album": "Album", "confidence": 0.8}
        current = {"title": "Song", "artist": Explosive(), "album": "Album", "confidence": 0.7}
        self.assertTrue(prefer_track_candidate(candidate, current))
        self.assertEqual(finalize_track_candidates([
            {"title": "Song", "artist": "Artist", "album": "Album", "confidence": 0.8},
            {"title": "Other", "artist": "Artist", "album": "Album", "confidence": object()},
        ])[0]["title"], "Song")


if __name__ == "__main__":
    unittest.main()
