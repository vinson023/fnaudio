import sys
import unittest

sys.path.insert(0, "app/server")
from cue_item_presentation import build_cue_item


class CueItemPresentationTests(unittest.TestCase):
    def test_builds_segment_duration_and_preserves_inputs(self):
        metadata = {"title": "Track", "artist": "Artist"}
        info = {"sample_rate": 192000}
        item = build_cue_item("id", metadata, ".ape", "audio/ape", False,
                              99, info, "/music/a.ape", "/music/a.cue", True,
                              10.0, 35.5, 100.25, 12, 1234, 16)
        self.assertEqual(item["duration"], 25.5)
        self.assertEqual(item["format"], "APE")
        self.assertEqual(item["modified"], 12)
        self.assertTrue(item["cue_track"])
        self.assertEqual(metadata, {"title": "Track", "artist": "Artist"})
        self.assertEqual(info, {"sample_rate": 192000})

    def test_an_unknown_boundary_presents_as_a_zero_length_segment(self):
        # A cue_end of 0.0 is what the scanner stores when the sheet never stated
        # where the segment ends, so presentation must not turn it into a track that
        # fills the source file: the segment it cannot measure is shown as unmeasured.
        item = build_cue_item("id", {}, ".flac", "audio/flac", False, 1, {},
                              "/music/disc.flac", "/music/album.cue", True,
                              240.0, 0.0, 100.25, 12, 1234, 16)
        self.assertEqual(item["cue_start"], 240.0)
        self.assertEqual(item["cue_end"], 0.0)
        self.assertEqual(item["duration"], 0.0)

    def test_non_positive_segment_has_zero_duration_and_boolean_flag(self):

        item = build_cue_item("id", {}, ".dsf", "audio/x-dsf", 1, 1, {},
                              "/a.dsf", "/a.cue", 1, 5, 2, 1, 1, 2, 16)
        self.assertEqual(item["duration"], 0.0)
        self.assertIs(item["is_dsd"], True)
        self.assertIs(item["cue_track"], True)


if __name__ == "__main__":
    unittest.main()
