import sys
import unittest

sys.path.insert(0, "app/server")

from services.dac_profiles import dac_quirk_profile


class DacProfileTests(unittest.TestCase):
    def test_custom_usb_profile_overrides_buffer_and_dsd_mode(self):
        profile = dac_quirk_profile(
            {"usb_vendor_id": "1234", "usb_product_id": "abcd", "stable_id": "usb:x"},
            [
                {
                    "name": "slow-locking-dac",
                    "match": {"vendor_id": "1234", "product_id": "ABCD"},
                    "settings": {
                        "audio_buffer_size": "16M",
                        "startup_delay_ms": 750,
                        "force_dop": True,
                    },
                }
            ],
        )

        self.assertEqual(profile["name"], "slow-locking-dac")
        self.assertEqual(profile["audio_buffer_size"], "16M")
        self.assertEqual(profile["startup_delay_ms"], 750)
        self.assertTrue(profile["force_dop"])
