import sys
import unittest

sys.path.insert(0, "app/server")

from metadata_provider_payload import (
    MAX_PROVIDER_CANDIDATES, candidate_has_displayable_fields,
    candidate_mappings, candidate_payload_is_sequence, candidate_text_is_corrupt,
)


class MetadataProviderPayloadTests(unittest.TestCase):
    def test_candidate_displayability_requires_visible_text(self):
        self.assertTrue(candidate_has_displayable_fields({"title": "Song", "confidence": 0.9}))
        self.assertTrue(candidate_has_displayable_fields({"image_url": "https://example.test/a.jpg"}))
        self.assertFalse(candidate_has_displayable_fields({"confidence": 0.9, "provider_id": "x"}))
        self.assertFalse(candidate_has_displayable_fields({"title": "   "}))

    def test_candidates_keep_only_mappings_with_a_hard_limit(self):
        values = [{"id": index} for index in range(MAX_PROVIDER_CANDIDATES + 8)] + ["bad"]
        result = candidate_mappings(values, MAX_PROVIDER_CANDIDATES + 100)
        self.assertEqual(len(result), MAX_PROVIDER_CANDIDATES)
        self.assertEqual(result[0]["id"], 0)

    def test_candidates_reject_non_sequences_and_invalid_limits(self):
        self.assertEqual(candidate_mappings({"id": "one"}), ())
        self.assertEqual(candidate_mappings([{"id": "one"}], 0), ())
        self.assertEqual(candidate_mappings([{"id": "one"}], True), ({"id": "one"},))

    def test_candidate_payload_shape_is_explicit_for_provider_fallbacks(self):
        self.assertTrue(candidate_payload_is_sequence([]))
        self.assertTrue(candidate_payload_is_sequence(({"id": "one"},)))
        self.assertFalse(candidate_payload_is_sequence({"error": "rate limited"}))
        self.assertFalse(candidate_payload_is_sequence("not a candidate list"))

    def test_replacement_text_is_not_displayable_metadata(self):
        self.assertTrue(candidate_text_is_corrupt("周\ufffd杰伦"))
        self.assertFalse(candidate_text_is_corrupt("周杰伦"))
        self.assertFalse(candidate_has_displayable_fields({"title": "晴\ufffd天"}))

    def test_candidates_keep_prefix_when_custom_iterator_fails(self):
        class BrokenList(list):
            def __iter__(self):
                yield {"id": "one"}
                raise RuntimeError("broken payload")

        self.assertEqual(candidate_mappings(BrokenList()), ({"id": "one"},))


if __name__ == "__main__":
    unittest.main()
