import json
import unittest

from app.server.metadata_track_enrichment_policy import has_local_artwork, needs_track_enrichment


class MetadataTrackEnrichmentPolicyTests(unittest.TestCase):
    def test_complete_tags_skip_lookup(self):
        self.assertFalse(needs_track_enrichment({"item_json": '{"metadata_source":{"title":"tag","artist":"tag","album":"tag"}}'}))

    def test_filename_or_missing_sources_need_lookup(self):
        self.assertTrue(needs_track_enrichment({"item_json": '{"metadata_source":{"title":"filename","artist":"tag","album":"unknown"}}'}))
        self.assertTrue(needs_track_enrichment({"item_json": ""}))

    def test_malformed_rows_fail_open_for_enrichment(self):
        self.assertTrue(needs_track_enrichment({"item_json": "{"}))
        self.assertTrue(needs_track_enrichment(None))

    def test_artwork_reference_policy_is_bounded_and_safe(self):
        self.assertTrue(has_local_artwork({"item_json": '{"cover_url":"metadata/artwork/a"}'}))
        self.assertFalse(has_local_artwork({"item_json": '{"cover_url":""}'}))
        self.assertFalse(has_local_artwork({"item_json": "{"}))
        self.assertFalse(has_local_artwork(None))

    def test_untrusted_metadata_values_are_not_stringified(self):
        self.assertTrue(needs_track_enrichment({"item_json": json.dumps({"metadata_source": {"title": 123}})}))
        self.assertFalse(has_local_artwork({"item_json": json.dumps({"cover_url": 123})}))

    def test_oversized_multibyte_item_json_is_not_parsed(self):
        prefix = '{"metadata_source":{"title":"'
        suffix = '"}}'
        payload = prefix + ("音" * (1024 * 1024 // 2 - len(prefix) - len(suffix))) + suffix
        self.assertTrue(needs_track_enrichment({"item_json": payload}))
        self.assertFalse(has_local_artwork({"item_json": payload}))
    def test_item_json_artwork_copy_would_suppress_the_lookup_forever(self):
        # R107 forensics on the 2026-09-17 artwork-plumbing note.
        # `has_local_artwork` only ever reads the row payload, so persisting
        # a copy of the provider artwork id into `item_json` would silence the
        # enrichment lane permanently even when the authoritative
        # `metadata_tracks` row is later orphaned or deleted.  This pin
        # records why that proposed change is unsafe without a self-heal path;
        # it is deliberately not a claim that storing the copy is desirable.
        self.assertTrue(has_local_artwork({"item_json": json.dumps({"metadata_artwork_id": "a" * 64})}))
        self.assertTrue(has_local_artwork({"item_json": json.dumps({"artwork_id": "b" * 64})}))
        self.assertFalse(has_local_artwork({"item_json": json.dumps({"metadata_source": {"title": "tag"}})}))


if __name__ == "__main__":
    unittest.main()
