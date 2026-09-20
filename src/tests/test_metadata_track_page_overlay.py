import sys
import unittest
import json

sys.path.insert(0, "app/server")

from metadata_track_page_overlay import (
    MAX_OVERLAY_TEXT, project_match_fields, visible_match_projection_signature,
)
from metadata_track_match_policy import MAX_TRACK_MATCH_JSON_BYTES


class MetadataTrackPageOverlayTests(unittest.TestCase):
    def test_projects_only_bounded_text_fields(self):
        result = project_match_fields('{"best":{"artist":"Artist","album":" Album ","id":123,"genre":["bad"]}}')
        self.assertEqual(result, {"artist": "Artist", "album": "Album"})

    def test_malformed_or_non_mapping_payload_is_empty(self):
        self.assertEqual(project_match_fields("{"), {})
        self.assertEqual(project_match_fields('{"best":[]}'), {})

    def test_text_is_nul_free_and_bounded(self):
        value = "\x00" + ("x" * (MAX_OVERLAY_TEXT + 20))
        result = project_match_fields(json.dumps({"best": {"title": value}}))
        self.assertEqual(len(result["title"]), MAX_OVERLAY_TEXT)
        self.assertNotIn("\x00", result["title"])

    def test_visible_signature_excludes_dialog_only_review_candidates(self):
        fields = json.dumps({"best": {"title": "Song", "album": "Album"}})
        self.assertEqual(visible_match_projection_signature(fields, "review"), ())
        self.assertEqual(visible_match_projection_signature(fields, "no_match"), ())
        self.assertEqual(
            visible_match_projection_signature(fields, "auto"),
            (("title", "Song"), ("album", "Album")),
        )

    def test_oversized_legacy_row_is_not_decoded_for_page_projection(self):
        self.assertEqual(project_match_fields("x" * (MAX_TRACK_MATCH_JSON_BYTES + 1)), {})


if __name__ == "__main__":
    unittest.main()
