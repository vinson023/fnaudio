import unittest

from playback_cue_position import normalize_cue_position


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


if __name__ == "__main__":
    unittest.main()
