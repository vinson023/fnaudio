import sys
import unittest

sys.path.insert(0, "app/server")

from playback_targets_presentation import MAX_TARGETS, build_targets


class PlaybackTargetsPresentationTests(unittest.TestCase):
    def test_targets_are_bounded_and_compact(self):
        devices = [{"alsa_id": "hw:%s" % index, "stable_id": "usb-%s" % index, "is_usb": True, "name": "DAC %s" % index} for index in range(400)]
        targets, current, name = build_targets(
            {"available": True, "output_capabilities": {"devices": devices}},
            {"target_id": "mpd:usb-0"},
            [{"id": "dlna:%s" % index, "name": "Renderer %s" % index, "online": True} for index in range(400)],
            {}, {"sample_rates": [44100]}, {"formats": ["audio/flac"]},
        )
        self.assertEqual(len(targets), MAX_TARGETS)
        self.assertEqual(current, "mpd:usb-0")
        self.assertEqual(name, "USB DAC · DAC 0")
        self.assertTrue(all("mpd" not in row.get("backend", {}) for row in targets))

    def test_invalid_values_do_not_trigger_text_coercion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("presentation must not stringify untrusted values")

        targets, current, name = build_targets(
            {"available": True, "output_capabilities": {"devices": [{"alsa_id": Explosive(), "is_usb": True}]}},
            {"target_id": Explosive()},
            [{"id": Explosive(), "name": Explosive()}],
            {}, {}, {},
        )
        self.assertEqual([target["id"] for target in targets], ["local"])
        self.assertEqual(current, "local")
        self.assertEqual(name, "当前设备")

    def test_generic_mpd_target_resolves_selected_usb_output(self):
        targets, current, name = build_targets(
            {"available": True, "output_capabilities": {"selected_output": {"stable_id": "USB A"}, "devices": [{"alsa_id": "hw:1", "stable_id": "USB A", "is_usb": True, "name": "DAC"}]}},
            {"target_id": "mpd"}, [], {}, {}, {},
        )
        self.assertEqual(current, "mpd:USB%20A")
        self.assertEqual(name, "USB DAC · DAC")
        self.assertTrue(targets[1]["selected"])

    def test_boolean_capabilities_are_not_truthiness_coerced(self):
        targets, _, _ = build_targets(
            {
                "available": "false",
                "output_capabilities": {
                    "devices": [{
                        "alsa_id": "hw:1",
                        "stable_id": "USB A",
                        "is_usb": "true",
                    }, {
                        "alsa_id": "hw:2",
                        "stable_id": "USB B",
                        "is_usb": True,
                    }],
                },
            },
            {"target_id": "local"},
            [{"id": "renderer", "online": "true", "supports_dsd": "true"}],
            {},
            {"bad_number": float("nan"), "ok": 1},
            {},
        )
        self.assertEqual([target["id"] for target in targets], ["local", "mpd:USB%20B", "renderer"])
        self.assertFalse(targets[1]["online"])
        self.assertFalse(targets[2]["online"])
        self.assertFalse(targets[2]["capabilities"]["native_dsd"])
        self.assertNotIn("bad_number", targets[1]["capabilities"])

    def test_capability_projection_does_not_materialize_unbounded_mappings(self):
        class HugeMapping(dict):
            def items(self):
                for index in range(1000000):
                    yield "key-%s" % index, index

        targets, _, _ = build_targets(
            {"available": True, "output_capabilities": {"devices": []}},
            {"target_id": "local"},
            [],
            HugeMapping(),
            {},
            {},
        )
        self.assertEqual(len(targets[0]["capabilities"]), 32)


if __name__ == "__main__":
    unittest.main()
