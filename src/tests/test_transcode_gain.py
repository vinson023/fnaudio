"""Transcode gain, the only way to attenuate a receiver that has no volume.

Volumio scales in ALSA and moOde inside MPD; neither covers "the sound comes out
of another machine". For a DLNA push to a renderer without RenderingControl the
bytes themselves have to be scaled, which is what this mode produces - and it is
also why 100% must return the untouched original file.
"""

import sys
import unittest

sys.path.insert(0, "app/server")

import transcode  # noqa: E402
from playback_targets_presentation import build_targets  # noqa: E402


class GainModeParsingTests(unittest.TestCase):
    def test_a_level_survives_the_round_trip(self):
        for percent in (1, 35, 99):
            with self.subTest(percent=percent):
                self.assertEqual(transcode.parse_gain_mode("gain_flac:%d" % percent), percent)

    def test_out_of_range_levels_are_clamped_not_trusted(self):
        self.assertEqual(transcode.parse_gain_mode("gain_flac:0"), 1)
        self.assertEqual(transcode.parse_gain_mode("gain_flac:-40"), 1)
        self.assertEqual(transcode.parse_gain_mode("gain_flac:400"), 100)

    def test_anything_else_is_not_a_gain_mode(self):
        for value in ("mp3", "original", "gain_flac:", "gain_flac:abc", "", None, 30, True):
            with self.subTest(value=value):
                self.assertEqual(transcode.parse_gain_mode(value), 0,
                                 "an unreadable level must not become a full-volume re-encode")

    def test_percent_maps_to_decibels(self):
        self.assertAlmostEqual(transcode.gain_mode_percent_to_db(100), 0.0, places=3)
        self.assertAlmostEqual(transcode.gain_mode_percent_to_db(50), -6.02, places=2)
        self.assertAlmostEqual(transcode.gain_mode_percent_to_db(10), -20.0, places=2)


class MediaModeGainTests(unittest.TestCase):
    ITEM = {"id": "t1", "path": "/music/a.flac", "mime": "audio/flac"}

    def mode(self, item=None, **query):
        return transcode.media_mode(item or dict(self.ITEM),
                                    {k: [v] for k, v in query.items()}, None)

    def test_a_gain_request_becomes_a_gain_mode(self):
        self.assertEqual(self.mode(transcode="gain", gain="35"), "gain_flac:35")

    def test_full_scale_is_the_original_file(self):
        # 100% must not re-encode: that is what keeps the bit-perfect case free
        # of both the CPU cost and the format change.
        self.assertEqual(self.mode(transcode="gain", gain="100"), "original")

    def test_a_missing_or_broken_level_means_full_scale(self):
        self.assertEqual(self.mode(transcode="gain"), "original")
        self.assertEqual(self.mode(transcode="gain", gain="loud"), "original")

    def test_dsd_is_never_scaled(self):
        item = dict(self.ITEM, is_dsd=True)
        self.assertEqual(self.mode(item, transcode="gain", gain="30"), "original",
                         "the DSD push is the original DSF/DFF by contract")

    def test_the_gain_query_does_not_change_other_modes(self):
        self.assertEqual(self.mode(transcode="mp3"), "mp3")
        self.assertEqual(self.mode(transcode="original"), "original")


class MediaUrlGainTests(unittest.TestCase):
    @staticmethod
    def url(item, gain=None):
        from dlna.media_server import upnp_media_url
        return upnp_media_url(object(), item, lambda value: value, lambda _h: "http://nas:53199", gain)

    def test_a_gain_push_carries_the_level_in_the_url(self):
        url = self.url({"id": "t1", "title": "Song", "path": "/music/a.flac"}, 60)
        self.assertIn("?transcode=gain&gain=60", url)

    def test_full_scale_and_no_gain_keep_the_plain_url(self):
        for gain in (None, 100, 0, "60", True):
            with self.subTest(gain=gain):
                self.assertNotIn("?", self.url({"id": "t1", "title": "S", "path": "/music/a.flac"}, gain))

    def test_dsd_ignores_gain(self):
        url = self.url({"id": "t1", "title": "S", "path": "/music/a.dsf", "is_dsd": True}, 40)
        self.assertNotIn("?", url)


class TargetVolumeCapabilityTests(unittest.TestCase):
    """The slider appears when fnAudio can act, not only when the device can."""

    DEVICE = {"id": "d1", "name": "TV", "location": "http://198.51.100.20/x.xml",
              "online": True, "capabilities": {"volume": False}}

    def build(self, transcode_volume):
        targets, _current, _name = build_targets(
            {"available": True}, {"target_id": "local"}, [dict(self.DEVICE)],
            {}, {}, {}, transcode_volume=transcode_volume)
        return next(t for t in targets if t["id"] == "d1")

    def test_without_the_policy_the_slider_stays_off(self):
        self.assertIs(self.build(False)["capabilities"]["volume"], False)

    def test_with_the_policy_the_slider_is_offered(self):
        self.assertIs(self.build(True)["capabilities"]["volume"], True)

    def test_a_device_that_can_do_it_keeps_its_own_answer(self):
        device = dict(self.DEVICE, capabilities={"volume": True})
        targets, _current, _name = build_targets(
            {"available": True}, {"target_id": "local"}, [device], {}, {}, {},
            transcode_volume=False)
        row = next(t for t in targets if t["id"] == "d1")
        self.assertIs(row["capabilities"]["volume"], True)


if __name__ == "__main__":
    unittest.main()
