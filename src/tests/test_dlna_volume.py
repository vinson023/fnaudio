"""Pushing volume to a DLNA renderer, and the policy that decides who attenuates.

Volumio attenuates in ALSA and moOde inside MPD; neither has an answer for "the
thing making the sound is on another machine". For a push there are only two
honest options: ask the device (RenderingControl SetVolume, bytes untouched) or
re-encode the stream with a gain filter (bytes changed). This file pins the
first one and the refusals around the second.
"""

import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, "app/server")

from dlna import control_point  # noqa: E402


class SetVolumeTests(unittest.TestCase):
    def test_set_volume_clamps_and_uses_the_rendering_service(self):
        device = {"volume_url": "http://198.51.100.20:53199/dlna/renderer/rendering/control"}
        with mock.patch.object(control_point, "soap_request") as soap:
            self.assertEqual(control_point.upnp_set_volume(device, 240), (True, "ok"))
        args, kwargs = soap.call_args
        self.assertEqual(args[0], device["volume_url"])
        self.assertEqual(args[1], "urn:schemas-upnp-org:service:RenderingControl:1")
        self.assertEqual(args[2], "SetVolume")
        self.assertIn("<DesiredVolume>100</DesiredVolume>", args[3])
        self.assertIn("<Channel>Master</Channel>", args[3])

    def test_set_volume_never_sends_a_negative_or_fractional_level(self):
        device = {"volume_url": "http://198.51.100.20/rc"}
        for value, expected in ((-5, 0), ("42", 42), (33.7, 34), (None, 100)):
            with self.subTest(value=value):
                with mock.patch.object(control_point, "soap_request") as soap:
                    control_point.upnp_set_volume(device, value)
                self.assertIn("<DesiredVolume>%d</DesiredVolume>" % expected, soap.call_args[0][3])

    def test_a_renderer_without_the_service_is_refused_without_a_request(self):
        with mock.patch.object(control_point, "soap_request") as soap:
            ok, message = control_point.upnp_set_volume({}, 50)
        self.assertFalse(ok)
        self.assertIn("RenderingControl", message)
        soap.assert_not_called()

    def test_a_refused_soap_call_reports_the_status_not_urllib_wording(self):
        import urllib.error

        device = {"volume_url": "http://198.51.100.20/rc"}
        refusal = urllib.error.HTTPError(device["volume_url"], 500, "Internal Server Error", {}, None)
        with mock.patch.object(control_point, "soap_request", side_effect=refusal):
            ok, message = control_point.upnp_set_volume(device, 30)
        self.assertFalse(ok)
        self.assertIn("500", message)
        self.assertNotIn("Internal Server Error", message)


class VolumeCapabilityProbeTests(unittest.TestCase):
    """The slider is only offered when the device says it can take the write."""

    @staticmethod
    def _probe(actions):
        device = {
            "location": "http://198.51.100.20:53199/dlna/renderer/description.xml",
            "connection_url": "http://198.51.100.20:53199/dlna/renderer/connection/control",
            "avtransport_scpd_url": "http://198.51.100.20:53199/dlna/scpd/avtransport.xml",
            "volume_scpd_url": "http://198.51.100.20:53199/dlna/scpd/rendering.xml",
        }
        with mock.patch.object(control_point, "device_protocol_info", return_value={}), \
                mock.patch.object(control_point, "scpd_actions", side_effect=lambda url: actions.get(url, [])), \
                mock.patch.dict(control_point.UPNP_CAPABILITY_CACHE, {}, clear=True):
            return control_point.probe_device_capabilities(device)

    def test_a_renderer_that_answers_rendering_control_is_marked_volumetric(self):
        caps = self._probe({
            "http://198.51.100.20:53199/dlna/scpd/rendering.xml": ["GetVolume", "SetVolume", "SetMute"],
        })
        self.assertIs(caps["volume"], True)
        self.assertIs(caps["mute"], True)

    def test_a_renderer_without_set_volume_is_not(self):
        caps = self._probe({
            "http://198.51.100.20:53199/dlna/scpd/rendering.xml": ["GetVolume"],
            "http://198.51.100.20:53199/dlna/scpd/avtransport.xml": ["Play", "Stop"],
        })
        self.assertIs(caps["volume"], False)
        self.assertIs(caps["mute"], False)

    def test_no_rendering_scpd_url_means_no_volume(self):
        caps = self._probe({})
        self.assertIs(caps["volume"], False)


class PushVolumeCommandTests(unittest.TestCase):
    """What the volume command does to a renderer with and without a mixer."""

    @classmethod
    def setUpClass(cls):
        import server
        from playback.models import PlaybackCommand, PlaybackState
        cls.server = server
        cls.command = PlaybackCommand
        cls.state = PlaybackState(target_id="dlna:one", target_kind="dlna_push")

    def _run(self, device, config, percent=42):
        with mock.patch.object(self.server, "find_upnp_device", return_value=device), \
                mock.patch.object(self.server, "upnp_set_volume", return_value=(True, "ok")) as setter:
            result = self.server.dlna_output_command(
                self.command("volume", percent), self.state, {"config": config})
        return result, setter

    def test_a_renderer_with_rendering_control_gets_the_set_volume_call(self):
        device = {"capabilities": {"volume": True}}
        result, setter = self._run(device, {})
        self.assertIs(result["ok"], True)
        setter.assert_called_once_with(device, 42)

    def test_a_renderer_without_it_is_refused_and_says_why(self):
        result, setter = self._run({"capabilities": {"volume": False}}, {"volume": {"software_fallback": False}})
        self.assertIs(result["ok"], False)
        self.assertIn("没有音量控制", result["message"])
        self.assertIn("未开启软件音量", result["message"])
        setter.assert_not_called()

    def test_the_switch_routes_to_the_transcode_repush(self):
        device = {"capabilities": {"volume": False}}
        with mock.patch.object(self.server, "find_upnp_device", return_value=device), \
                mock.patch.object(self.server, "repush_dlna_with_gain",
                                  return_value={"ok": True, "message": "ok"}) as repush:
            result = self.server.dlna_output_command(
                self.command("volume", 37), self.state,
                {"config": {"volume": {"software_fallback": True}}})
        self.assertIs(result["ok"], True)
        repush.assert_called_once_with(device, self.state,
                                       {"volume": {"software_fallback": True}}, 37)
        self.assertEqual(self.server.DLNA_PUSH_GAIN,
                         {"target_id": "dlna:one", "percent": 37},
                         "the level has to outlive this request: the next track needs it too")

    def test_a_fixed_target_refuses_even_when_the_device_could(self):
        result, setter = self._run({"capabilities": {"volume": True}},
                                   {"volume": {"targets": {"dlna": "fixed"}}})
        self.assertIs(result["ok"], False)
        self.assertIn("固定", result["message"])
        setter.assert_not_called()

    def test_an_explicit_device_mode_never_falls_back_to_software(self):
        result, setter = self._run({"capabilities": {"volume": False}},
                                   {"volume": {"targets": {"dlna": "device"}, "software_fallback": True}})
        self.assertIs(result["ok"], False)
        self.assertIn("未开启软件音量", result["message"])


class GainRepushTests(unittest.TestCase):
    """Changing the level means a new URL, so the track is pushed again."""

    @classmethod
    def setUpClass(cls):
        import server
        from playback.models import PlaybackState
        cls.server = server
        cls.state = PlaybackState(target_id="dlna:two", target_kind="dlna_push")

    def test_the_position_is_read_before_the_push_and_restored_after(self):
        device = {"control_url": "http://198.51.100.20/av"}
        with mock.patch.object(self.server, "find_library_item", return_value={"id": "t1"}), \
                mock.patch.object(self.server.PLAYBACK_CORE, "state",
                                  SimpleNamespace(current_track_id="t1")), \
                mock.patch.object(self.server, "upnp_position_info", return_value={"rel_seconds": 42.5}), \
                mock.patch.object(self.server, "soap_push", return_value=(True, "ok")) as push, \
                mock.patch.object(self.server, "upnp_control", return_value=(True, "ok")) as control:
            self.server.DLNA_MONITOR_GUARD.clear()
            result = self.server.repush_dlna_with_gain(device, self.state, {}, 40)
        self.assertIs(result["ok"], True)
        self.assertEqual(push.call_args.kwargs.get("gain"), 40)
        control.assert_called_once_with(device, "seek", 42.5)
        self.assertGreater(self.server.DLNA_MONITOR_GUARD.get("suppress_stop_until", 0), 0,
                           "the transient STOPPED must not be read as 'the track ended'")

    def test_a_failed_seek_keeps_the_gain_and_says_so(self):
        device = {"control_url": "http://198.51.100.20/av"}
        with mock.patch.object(self.server, "find_library_item", return_value={"id": "t1"}), \
                mock.patch.object(self.server.PLAYBACK_CORE, "state",
                                  SimpleNamespace(current_track_id="t1")), \
                mock.patch.object(self.server, "upnp_position_info", return_value={"rel_seconds": 10.0}), \
                mock.patch.object(self.server, "soap_push", return_value=(True, "ok")), \
                mock.patch.object(self.server, "upnp_control", return_value=(False, "seek refused")):
            result = self.server.repush_dlna_with_gain(device, self.state, {}, 25)
        self.assertIs(result["ok"], False)
        self.assertIn("无法跳回原位置", result["message"])

    def test_no_current_track_is_a_refusal_not_a_crash(self):
        with mock.patch.object(self.server, "find_library_item", return_value=None):
            result = self.server.repush_dlna_with_gain({}, self.state, {}, 30)
        self.assertIs(result["ok"], False)
        self.assertIn("没有可重新推送", result["message"])

    def test_the_next_push_carries_the_level_that_was_set(self):
        from playback.models import PlaybackState
        track = mock.Mock(track_id="t1")
        track.item = {"id": "t1"}
        with mock.patch.object(self.server, "find_upnp_device", return_value={"control_url": "http://x/av"}), \
                mock.patch.object(self.server, "soap_push", return_value=(True, "ok")) as push:
            self.server.DLNA_PUSH_GAIN.update({"target_id": "dlna:three", "percent": 55})
            self.server.dlna_output_open(
                track, PlaybackState(target_id="dlna:three", target_kind="dlna_push"),
                {"handler": mock.Mock(), "item": track.item, "position": 0})
        self.assertEqual(push.call_args.kwargs.get("gain"), 55)

    def test_a_different_target_starts_at_full_scale(self):
        self.assertEqual(self.server.push_gain_for("dlna:other"), 100,
                         "the level belongs to the renderer that was set, not to the next one")


if __name__ == "__main__":
    unittest.main()
