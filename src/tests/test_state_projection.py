import sys
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from state_projection import MAX_PLAYLIST_TRACK_IDS_TOTAL, MAX_STATE_PAYLOAD_BYTES, dump_json_bounded, dump_json_bounded_strict, load_json_bounded, mapping_or_empty, playlists, strings, ui_preferences


class StateProjectionTests(unittest.TestCase):
    def test_playback_queue_ids_are_bounded_and_do_not_coerce_objects(self):
        from state_projection import MAX_PLAYBACK_QUEUE_TRACKS, playback_queue_ids

        class Bad:
            def __str__(self):
                raise AssertionError("arbitrary objects must not be stringified")

        self.assertEqual(playback_queue_ids(["a", "a", Bad(), "b"]), ["a", "b"])
        self.assertEqual(len(playback_queue_ids(["x"] * (MAX_PLAYBACK_QUEUE_TRACKS + 10))), 1)

    def test_json_payload_is_bounded_before_decode(self):
        self.assertEqual(load_json_bounded("{\"ok\":true}"), {"ok": True})
        self.assertEqual(load_json_bounded("x" * (MAX_STATE_PAYLOAD_BYTES + 1)), {})
        self.assertEqual(dump_json_bounded({"ok": True}), '{"ok":true}')
        self.assertEqual(dump_json_bounded({"x": "a" * MAX_STATE_PAYLOAD_BYTES}), "{}")
        self.assertEqual(dump_json_bounded({"value": float("nan")}), "{}")
        self.assertEqual(dump_json_bounded({"value": float("inf")}), "{}")

    def test_deep_json_recursion_falls_back_safely(self):
        with mock.patch("state_projection.json.dumps", side_effect=RecursionError):
            self.assertEqual(dump_json_bounded({"nested": True}), "{}")
        with mock.patch("state_projection.json.loads", side_effect=RecursionError):
            self.assertEqual(load_json_bounded("{}"), {})

    def test_strict_dump_raises_for_oversized_or_non_finite_values(self):
        with self.assertRaises(ValueError):
            dump_json_bounded_strict({"x": "a" * MAX_STATE_PAYLOAD_BYTES})
        with self.assertRaises(ValueError):
            dump_json_bounded_strict({"value": float("nan")})

    def test_strings_bounds_and_deduplicates_without_coercion(self):
        self.assertEqual(strings(["a", "a", "b", 3], 10), ["a", "b"])

    def test_broken_string_subclass_is_ignored(self):
        class BrokenString(str):
            def strip(self):
                raise RuntimeError("broken text")

        self.assertEqual(strings([BrokenString("bad"), "ok"], 10), ["ok"])

    def test_mapping_projection_rejects_non_object_json_shapes(self):
        self.assertEqual(mapping_or_empty({"ok": True}), {"ok": True})
        self.assertEqual(mapping_or_empty([]), {})
        self.assertEqual(mapping_or_empty("text"), {})

    def test_playlists_and_ui_preferences_share_safe_projection(self):
        value = playlists([{"id": "p", "name": "P", "trackIds": ["a", "a", "b"]}])
        self.assertEqual(value[0]["trackIds"], ["a", "b"])
        ui = ui_preferences({"track_columns": {"all": ["title", "title"]}, "track_column_widths": {"all": {"title": 120}}})
        self.assertEqual(ui["track_columns"], {"all": ["title"]})
        self.assertEqual(ui["track_column_widths"], {"all": {"title": 120}})

    def test_playlists_cap_track_ids_across_the_entire_state_payload(self):
        per_playlist = 10000
        source = [
            {"id": "playlist-%d" % index, "name": "Playlist", "trackIds": ["%d-%d" % (index, track) for track in range(per_playlist)]}
            for index in range(6)
        ]

        projected = playlists(source)

        self.assertEqual(len(projected), 6)
        self.assertEqual(sum(len(entry["trackIds"]) for entry in projected), MAX_PLAYLIST_TRACK_IDS_TOTAL)
        self.assertEqual(projected[-1]["trackIds"], [])

    def test_projection_keeps_items_before_iterator_failure(self):
        class BrokenList(list):
            def __iter__(self):
                yield {"id": "first", "name": "First", "trackIds": ["a"]}
                raise RuntimeError("broken iterator")

        self.assertEqual(playlists(BrokenList())[0]["id"], "first")

    def test_width_projection_keeps_columns_before_iterator_failure(self):
        class Broken(dict):
            def items(self):
                yield ("title", 120)
                raise RuntimeError("broken iterator")

        result = ui_preferences({"track_column_widths": {"all": Broken()}})
        self.assertEqual(result["track_column_widths"], {"all": {"title": 120}})

    def test_width_projection_rejects_fractional_and_non_finite_values(self):
        result = ui_preferences({"track_column_widths": {"all": {
            "fraction": 120.5,
            "text_fraction": "120.5",
            "nan": float("nan"),
            "valid": "120",
        }}})
        self.assertEqual(result["track_column_widths"], {"all": {"valid": 120}})


if __name__ == "__main__":
    unittest.main()
