"""The opt-in software volume switch, at the point where it becomes audible.

`mixer_policy()` is what writes `mixer_type` into mpd.conf, so it is the only
place where "允许调节没有硬件音量的输出" turns from a setting into behaviour.
R629: the switch had a config key and nothing else - no caller, no UI, and a
half-written policy that referenced a constant nobody had defined.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, "app/server")

from services.mpd_service import MpdService, SOFTWARE_VOLUME_FALLBACK_MESSAGE  # noqa: E402


def policy_for(config, device=None, probe=None):
    service = object.__new__(MpdService)
    service.config = dict(config)
    return service.mixer_policy(device if device is not None else {"alsa_id": "hw:1"},
                                probe if probe is not None else {"available": False, "controls": []})


class SoftwareVolumeFallbackTests(unittest.TestCase):
    def test_off_keeps_the_fixed_level_refusal(self):
        policy = policy_for({"mpd_mixer_type": "none", "volume_software_fallback_enabled": False})
        self.assertIs(policy["available"], False)
        self.assertEqual(policy["mode"], "none")
        self.assertIs(policy["bitperfect"], True)
        self.assertIn("固定输出电平", policy["message"])

    def test_on_scales_the_samples_and_says_so(self):
        policy = policy_for({"mpd_mixer_type": "none", "volume_software_fallback_enabled": True})
        self.assertIs(policy["available"], True)
        self.assertEqual(policy["mode"], "software", "mpd.conf must be told mixer_type software")
        self.assertIs(policy["bitperfect"], False)
        self.assertIs(policy["fallback"], True)
        self.assertEqual(policy["message"], SOFTWARE_VOLUME_FALLBACK_MESSAGE)
        self.assertIn("bit-perfect", policy["message"])

    def test_on_covers_a_dac_that_asked_for_hardware_and_has_no_control(self):
        # The DAC case the switch exists for: the user selected "hardware" and
        # the device exposes no Playback Volume. Returning `mode: none` here is
        # what left the slider dead even with the switch on.
        policy = policy_for({"mpd_mixer_type": "hardware", "volume_software_fallback_enabled": True},
                            probe={"available": False, "controls": [], "message": "no control"})
        self.assertEqual(policy["mode"], "software")
        self.assertIs(policy["available"], True)
        self.assertIs(policy["fallback"], True)

    def test_on_never_downgrades_a_working_hardware_control(self):
        # A DAC that does expose PCM must keep its bit-perfect hardware volume.
        policy = policy_for({"mpd_mixer_type": "hardware", "volume_software_fallback_enabled": True},
                            probe={"available": True, "controls": ["PCM"]})
        self.assertEqual(policy["mode"], "hardware")
        self.assertEqual(policy["control"], "PCM")
        self.assertIs(policy["bitperfect"], True)
        self.assertIs(policy["fallback"], False)

    def test_an_explicit_software_choice_is_not_labelled_a_fallback(self):
        policy = policy_for({"mpd_mixer_type": "software", "volume_software_fallback_enabled": True})
        self.assertEqual(policy["mode"], "software")
        self.assertIs(policy["fallback"], False,
                      "choosing software is not the same trade as being forced into it")

    def test_a_string_is_not_a_switch(self):
        # Same rule as every other switch in this file: only a real JSON boolean
        # may turn sample scaling on behind the user's back.
        policy = policy_for({"mpd_mixer_type": "none", "volume_software_fallback_enabled": "true"})
        self.assertIs(policy["available"], False)
        self.assertEqual(policy["mode"], "none")


class SoftwareVolumeSwitchSurfaceTests(unittest.TestCase):
    """The switch has to exist where the user was told it would be."""

    @staticmethod
    def _read(relative):
        root = pathlib.Path(__file__).resolve().parents[2]
        return (root / relative).read_text(encoding="utf-8")

    def test_the_switch_lives_in_the_playback_output_pane(self):
        html = self._read("src/app/ui/index.html")
        self.assertIn('id="volumeSoftwareFallbackInput"', html)
        self.assertIn('data-settings-block="playback-volume"', html)
        self.assertIn("播放输出", html)
        block = html.split('data-settings-block="playback-volume"', 1)[1]
        self.assertIn("bit-perfect", block.split("playback-sleep", 1)[0])

    def test_the_pane_reads_back_the_server_value_and_saves_it(self):
        script = self._read("src/app/ui/app.js")
        self.assertIn('VOLUME_SOFTWARE_FALLBACK_SETTING_KEY = "volume_software_fallback_enabled"', script)
        self.assertIn("volumeSoftwareFallbackInput()", script)
        # Load: adopt the echo, never the markup default.
        self.assertIn("data?.config?.[VOLUME_SOFTWARE_FALLBACK_SETTING_KEY]", script)

    def test_the_server_projects_the_key_both_ways(self):
        server = self._read("src/app/server/server.py")
        self.assertGreaterEqual(server.count('"volume_software_fallback_enabled": volume_software_fallback_enabled('), 1)
        self.assertIn('payload, "volume_software_fallback_enabled",', server)
        self.assertIn('"volume_software_fallback_enabled": volume_fallback,', server)

    def test_the_save_path_restarts_the_audio_backend_only_on_a_real_change(self):
        server = self._read("src/app/server/server.py")
        self.assertIn("if previous_volume_fallback != volume_fallback and MPD_SERVICE:", server)

    def test_the_policy_reaches_mpd_conf(self):
        # `mode` is the string MPD reads as mixer_type; without this line the
        # policy could report "software" while mpd.conf kept mixer_type "none".
        service = self._read("src/app/server/services/mpd_service.py")
        self.assertIn('mixer_type = mixer["mode"]', service)
        self.assertIn("""'    mixer_type "%s"' % mixer_type""", service)


if __name__ == "__main__":
    unittest.main()
