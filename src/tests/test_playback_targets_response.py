import unittest

from playback_targets_response import compose_playback_targets_response


class PlaybackTargetsResponseTests(unittest.TestCase):
    def test_composes_target_availability_without_mutating_inputs(self):
        targets = [{"id": "local"}, {"id": "usb"}]
        payload = compose_playback_targets_response(
            targets=targets,
            current_target="usb",
            current_target_name="USB DAC",
            plugins={"mpd": {}},
            mpd={"running": True},
            upmpdcli={"available": False},
            airplay={},
            refreshing=False,
        )
        self.assertTrue(payload["current_target_available"])
        self.assertEqual(payload["targets"], targets)

    def test_invalid_inputs_use_safe_response_shapes(self):
        payload = compose_playback_targets_response(
            targets=None, current_target=None, current_target_name=None,
            plugins=None, mpd=None, upmpdcli=None, airplay=None, refreshing=0,
        )
        self.assertEqual(payload["targets"], [])
        self.assertFalse(payload["current_target_available"])
        self.assertEqual(payload["current_target"], "")
        self.assertEqual(payload["optional_backends"], {"mpd": {}, "upmpdcli": {}, "airplay": {}})


if __name__ == "__main__":
    unittest.main()
