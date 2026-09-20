import sys
import unittest

sys.path.insert(0, "app/server")

from playback_status_presentation import present_position, present_transport


class PlaybackStatusPresentationTests(unittest.TestCase):
    def test_transport_is_bounded_and_normalized(self):
        result = present_transport({"state": "playing", "nested": {"bad": 1}, "volume": 3})
        self.assertEqual(result["state"], "PLAYING")
        self.assertNotIn("nested", result)
        self.assertEqual(result["volume"], 3)

    def test_invalid_transport_falls_back_to_stopped(self):
        self.assertEqual(present_transport(None), {"state": "STOPPED"})

    def test_position_rejects_invalid_numbers(self):
        result = present_position({"rel_seconds": "bad", "duration_seconds": -2, "track_uri": "x"})
        self.assertEqual(result["rel_seconds"], 0.0)
        self.assertEqual(result["duration_seconds"], 0.0)
        self.assertEqual(result["track_uri"], "x")

    def test_broken_mapping_items_falls_back_safely(self):
        class Broken(dict):
            def items(self):
                raise RuntimeError("broken mapping")

        self.assertEqual(present_transport(Broken()), {"state": "STOPPED"})
        self.assertEqual(present_position(Broken()), {"rel_seconds": 0.0, "duration_seconds": 0.0})


if __name__ == "__main__":
    unittest.main()
