import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, "app/server")

from playback.alsa_output import choose_dac_strategy, enrich_dac_device


class AlsaOutputTests(unittest.TestCase):
    def test_device_uses_driver_reported_pcm_capabilities(self):
        detected = {
            "source": "/proc/asound/card0/stream*",
            "pcm_rates": [44100, 192000, 352800, 384000],
            "pcm_max_rate": 384000,
            "pcm_max_bits": 32,
            "dsd": True,
            "dsd_rates": ["DSD_U32"],
        }
        with patch("playback.alsa_output.parse_dac_stream_caps", return_value=detected):
            device = enrich_dac_device({"name": "Any USB DAC", "alsa_id": "hw:0,0"})
        caps = device["caps"]
        self.assertEqual(caps["pcm_max_rate"], 384000)
        self.assertEqual(caps["pcm_max_bits"], 32)
        self.assertEqual(caps["pcm_rates"], [44100, 192000, 352800, 384000])
        self.assertTrue(caps["dsd"])

    def test_unknown_capabilities_use_the_same_conservative_fallback_for_all_names(self):
        item = {"sample_rate": 96000, "bit_depth": 24, "is_dsd": False}
        for name in ("TEAC UD-301", "Generic USB DAC"):
            strategy = choose_dac_strategy(item, {"name": name, "caps": {"source": "unknown"}})
            self.assertEqual(strategy["rate"], 44100)
            self.assertEqual(strategy["bits"], 16)
            self.assertTrue(strategy["needs_transcode"])


if __name__ == "__main__":
    unittest.main()
