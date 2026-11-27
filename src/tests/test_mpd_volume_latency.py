"""Software volume is delayed by the ALSA ring, and MPD's default is 500 ms.

Reported 2026-11-27 as "调节音量的时候响应会慢半拍，不是那种实时响应". Two
independent things produce that half beat: the UI only wrote on release (fixed in
`app.js`, covered by `test_ui_remote_volume_live.js`) and, once the write lands,
MPD still scales only the samples it has not yet handed to ALSA - 500 ms of them
by default. This file pins the second half: a software mixer asks for a shorter
ring, and a hardware mixer is left alone because its level does not travel
through the ring at all.
"""

import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from services.mpd_service import MpdService, SOFTWARE_VOLUME_BUFFER_MS  # noqa: E402


def config_for(**overrides):
    config = {
        "cache_dir": "",
        "library_paths": [],
        "volume": {"targets": {"dac": "software"}},
    }
    config.update(overrides)
    return config


def write_config(config):
    """Run ensure_config in a throwaway app root and return the generated text."""
    with tempfile.TemporaryDirectory() as root:
        config = dict(config)
        config.setdefault("cache_dir", os.path.join(root, "cache"))
        music = os.path.join(root, "music")
        os.makedirs(music, exist_ok=True)
        config["library_paths"] = [music]
        with mock.patch.object(MpdService, "_find_binary", return_value="/usr/bin/mpd"), \
                mock.patch.object(MpdService, "_selected_alsa_output", return_value={}):
            service = MpdService(config, app_root=root, app_config_path=os.path.join(root, "config.json"))
            result = service.ensure_config()
        if not result.get("ok"):
            raise AssertionError(result.get("message"))
        return pathlib.Path(service.config_path).read_text(encoding="utf-8")


class SoftwareVolumeBufferTests(unittest.TestCase):
    def test_a_software_mixer_gets_a_short_alsa_ring(self):
        text = write_config(config_for())
        self.assertIn('mixer_type "software"', text)
        self.assertIn('buffer_time "%d"' % (SOFTWARE_VOLUME_BUFFER_MS * 1000), text)
        self.assertIn('period_time "%d"' % (max(10, SOFTWARE_VOLUME_BUFFER_MS // 4) * 1000), text)

    def test_the_ring_is_shorter_than_mpds_default(self):
        # 500000 us is MPD's compiled-in default; anything at or above it would
        # leave the reported lag exactly where it was.
        self.assertLess(SOFTWARE_VOLUME_BUFFER_MS * 1000, 500000)

    def test_a_fixed_level_gets_no_ring_of_ours(self):
        # Nothing is attenuated, so there is no reason to trade buffer headroom
        # for a latency the user cannot perceive.
        text = write_config(config_for(volume={"targets": {"dac": "fixed"}}))
        self.assertIn('mixer_type "none"', text)
        self.assertNotIn("buffer_time", text)

    def test_a_dac_profile_can_ask_for_a_bigger_ring(self):
        # Dropout-prone DACs already own a `dac_profiles` entry; they must be
        # able to buy headroom back without a new setting elsewhere.
        text = write_config(config_for(dac_profiles=[{"name": "crackle", "settings": {"buffer_time_ms": 400}}]))
        self.assertIn('buffer_time "400000"', text)
        self.assertIn('period_time "100000"', text)

    def test_an_unreadable_profile_value_falls_back_to_the_default(self):
        text = write_config(config_for(dac_profiles=[{"name": "odd", "settings": {"buffer_time_ms": "soon"}}]))
        self.assertIn('buffer_time "%d"' % (SOFTWARE_VOLUME_BUFFER_MS * 1000), text)


if __name__ == "__main__":
    unittest.main()
