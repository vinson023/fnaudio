import sys
import unittest
import math

sys.path.insert(0, "app/server")

from playback_status_spec import command_id_from_payload, target_id_from_query


class PlaybackStatusSpecTests(unittest.TestCase):
    def test_target_id_prefers_target_then_device_and_handles_query_lists(self):
        self.assertEqual(target_id_from_query({"target_id": ["alsa:1"], "device_id": ["mpd"]}), "alsa:1")
        self.assertEqual(target_id_from_query({"device_id": ["mpd"]}), "mpd")
        self.assertEqual(target_id_from_query({"target_id": "browser"}), "browser")

    def test_target_id_uses_local_for_missing_empty_or_non_mapping_input(self):
        self.assertEqual(target_id_from_query({}), "local")
        self.assertEqual(target_id_from_query({"target_id": [""]}), "local")
        self.assertEqual(target_id_from_query(None), "local")

    def test_target_id_rejects_arbitrary_objects_and_bounds_text(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("target ids must not stringify arbitrary objects")
        self.assertEqual(target_id_from_query({"target_id": [Explosive()]}), "local")
        self.assertEqual(target_id_from_query({"target_id": [" x "]}), "x")
        self.assertEqual(len(target_id_from_query({"target_id": ["x" * 1000]})), 128)
        self.assertEqual(target_id_from_query({"target_id": [math.nan]}), "local")
        self.assertEqual(target_id_from_query({"target_id": [math.inf]}), "local")
        self.assertEqual(target_id_from_query({"target_id": [10 ** 10000]}), "local")

    def test_command_id_accepts_bounded_text_only(self):
        self.assertEqual(command_id_from_payload({"command_id": "  abc  "}), "abc")
        self.assertEqual(command_id_from_payload({"command_id": object()}), "")
        self.assertEqual(len(command_id_from_payload({"command_id": "x" * 500})), 128)

if __name__ == "__main__":
    unittest.main()
