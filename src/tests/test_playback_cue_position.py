import unittest

from playback_cue_position import (
    cue_is_transcoded,
    cue_segment_declaration,
    normalize_cue_position,
    project_cue_seek,
    public_cue_position,
)

# A native CUE segment is played from the whole source file, so MPD reports
# source seconds; the projection must fold them down and a seek must fold them
# back.  100.0s in, 30.0s long.
NATIVE_CUE_ITEM = {
    "cue_track": True,
    "path": "/music/disc.flac",
    "cue_start": 100.0,
    "cue_end": 130.0,
    "duration": 30.0,
}


class PlaybackCuePositionTests(unittest.TestCase):
    def test_ape_cue_position_is_relative_and_clamped(self):
        status, finished = normalize_cue_position(
            {"position": {"rel_seconds": 12}},
            {"cue_track": True, "path": "disc.ape", "cue_start": 100, "cue_end": 110, "duration": 8},
        )
        self.assertEqual(status["position"]["rel_seconds"], 8)
        self.assertTrue(status["position"]["cue_transcoded"])
        self.assertTrue(finished)

    def test_native_cue_position_subtracts_source_start(self):
        status, finished = normalize_cue_position(
            {"position": {"rel_seconds": 105}},
            {"cue_track": True, "path": "disc.flac", "cue_start": 100, "cue_end": 110, "duration": 10},
        )
        self.assertEqual(status["position"]["rel_seconds"], 5)
        self.assertFalse(finished)

    def test_an_unknown_boundary_never_finishes_and_never_clamps(self):
        # cue_end 0.0 means the scan knows no end for this segment.  Playing it must
        # keep running instead of being clamped to a length nobody measured, and must
        # never be reported as finished.
        status, finished = normalize_cue_position(
            {"position": {"rel_seconds": 900}},
            {"cue_track": True, "path": "disc.flac", "cue_start": 240, "cue_end": 0.0, "duration": 0.0},
        )
        self.assertEqual(status["position"]["rel_seconds"], 660)
        self.assertEqual(status["position"]["duration_seconds"], 0.0)
        self.assertFalse(finished)
        # The same position with a stated boundary does both, so the assertions above
        # describe the unknown state and not an accident of the chosen numbers.
        known, known_finished = normalize_cue_position(
            {"position": {"rel_seconds": 900}},
            {"cue_track": True, "path": "disc.flac", "cue_start": 240, "cue_end": 300.0, "duration": 60.0},
        )
        self.assertEqual(known["position"]["rel_seconds"], 60.0)
        self.assertTrue(known_finished)

    def test_non_cue_state_is_copied_without_mutation(self):

        original = {"transport": "PLAYING"}
        status, finished = normalize_cue_position(original, {"cue_track": False})
        self.assertEqual(status, original)
        self.assertIsNot(status, original)
        self.assertFalse(finished)

    def test_non_finite_positions_are_reset_before_projection(self):
        status, finished = normalize_cue_position(
            {"position": {"rel_seconds": float("nan")}},
            {"cue_track": True, "path": "disc.flac", "cue_start": float("inf"), "cue_end": 10, "duration": float("nan")},
        )
        self.assertEqual(status["position"]["rel_seconds"], 0.0)
        self.assertEqual(status["position"]["cue_start"], 0.0)
        self.assertEqual(status["position"]["cue_end"], 10.0)
        self.assertFalse(finished)

    def test_transcoding_predicate_matches_only_ape_segments(self):
        self.assertTrue(cue_is_transcoded({"cue_track": True, "path": "/music/disc.ape"}))
        self.assertTrue(cue_is_transcoded({"cue_track": True, "path": "/music/DISC.APE"}))
        self.assertFalse(cue_is_transcoded({"cue_track": True, "path": "/music/disc.flac"}))
        # The whole .ape file is not a segment: folding it would shift every position.
        self.assertFalse(cue_is_transcoded({"cue_track": False, "path": "/music/disc.ape"}))
        self.assertFalse(cue_is_transcoded({"cue_track": True, "path": None}))
        for value in (None, "/music/disc.ape", 123, []):
            self.assertFalse(cue_is_transcoded(value), repr(value))

    def test_both_cue_shapes_declare_segment_units(self):
        self.assertTrue(cue_segment_declaration(NATIVE_CUE_ITEM))
        self.assertTrue(cue_segment_declaration({"cue_track": True, "path": "/music/disc.ape"}))
        self.assertFalse(cue_segment_declaration({"cue_track": False, "path": "/music/one.flac"}))
        for value in (None, "x", 1):
            self.assertFalse(cue_segment_declaration(value), repr(value))

    def test_seek_is_the_exact_inverse_of_the_status_fold(self):
        for whole_seconds in (100.0, 112.5, 129.0):
            reported = public_cue_position(whole_seconds, 210.0, NATIVE_CUE_ITEM)
            self.assertEqual(
                project_cue_seek(reported["rel_seconds"], NATIVE_CUE_ITEM),
                whole_seconds,
            )

    def test_transcoded_and_plain_tracks_round_trip_unchanged(self):
        transcoded = public_cue_position(30.0, 300.0, {
            "cue_track": True,
            "path": "/music/disc.ape",
            "cue_start": 100.0,
            "cue_end": 130.0,
            "duration": 30.0,
        })
        self.assertEqual(transcoded["rel_seconds"], 30.0)
        self.assertEqual(
            project_cue_seek(transcoded["rel_seconds"], {
                "cue_track": True,
                "path": "/music/disc.ape",
                "cue_start": 100.0,
            }),
            30.0,
        )
        # A non-CUE item must never receive an offset, whatever it claims.
        plain = public_cue_position(30.0, 300.0, {"cue_track": False, "cue_start": 100.0})
        self.assertEqual(plain, {"rel_seconds": 30.0, "duration_seconds": 300.0})
        self.assertEqual(project_cue_seek(30.0, {"cue_track": False, "cue_start": 100.0}), 30.0)

    def test_an_absurd_seek_stays_inside_the_segment(self):
        self.assertEqual(project_cue_seek(-5.0, NATIVE_CUE_ITEM), 100.0)
        self.assertEqual(project_cue_seek(float("nan"), NATIVE_CUE_ITEM), 100.0)
        self.assertEqual(project_cue_seek(None, NATIVE_CUE_ITEM), 100.0)
        self.assertEqual(project_cue_seek(5.0, None), 5.0)
        self.assertEqual(project_cue_seek(float("inf"), NATIVE_CUE_ITEM), 100.0)

    def test_public_projection_exposes_only_the_two_client_keys(self):
        reported = public_cue_position(112.5, 210.0, NATIVE_CUE_ITEM)
        self.assertEqual(set(reported), {"rel_seconds", "duration_seconds"})
        # The rail is 30 s long, not 210 s: the segment length replaces the
        # source-file duration instead of being clamped against it.
        self.assertEqual(reported, {"rel_seconds": 12.5, "duration_seconds": 30.0})


if __name__ == "__main__":
    unittest.main()
