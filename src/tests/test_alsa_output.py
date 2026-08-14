import sys
import os
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "app/server")

from playback.alsa_output import (
    ALSA_CAPS_CACHE,
    alsa_device_identity,
    choose_dac_strategy,
    enrich_dac_device,
    preserve_verified_busy_probe,
    start_dac_playback,
)


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

    def test_usb_stable_identity_survives_numeric_card_index_change(self):
        with tempfile.TemporaryDirectory() as root:
            proc_root = os.path.join(root, "proc")
            sys_root = os.path.join(root, "sys")
            usb_root = os.path.join(root, "usb-device")
            os.makedirs(usb_root)
            for name, value in {
                "idVendor": "1234",
                "idProduct": "5678",
                "serial": "DAC-SERIAL-1",
                "product": "Reference DAC",
            }.items():
                with open(os.path.join(usb_root, name), "w", encoding="utf-8") as handle:
                    handle.write(value)
            for card in ("0", "3"):
                os.makedirs(os.path.join(proc_root, "card" + card))
                with open(os.path.join(proc_root, "card" + card, "id"), "w", encoding="utf-8") as handle:
                    handle.write("RefDAC")
                os.makedirs(os.path.join(sys_root, "card" + card))
                os.symlink(usb_root, os.path.join(sys_root, "card" + card, "device"), target_is_directory=True)
            with patch.dict(
                os.environ,
                {"FNAUDIO_ASOUND_ROOT": proc_root, "FNAUDIO_SYS_SOUND_ROOT": sys_root},
            ):
                first = alsa_device_identity("0", "0")
                reconnected = alsa_device_identity("3", "0")

        self.assertEqual(first["stable_id"], reconnected["stable_id"])
        self.assertEqual(first["stable_alsa_id"], "hw:CARD=RefDAC,DEV=0")
        self.assertEqual(reconnected["card_index"], 3)

    def test_direct_alsa_dsd_never_falls_back_to_pcm(self):
        device = {
            "id": "dac:usb:test",
            "alsa_id": "hw:2,0",
            "stable_alsa_id": "hw:CARD=DAC,DEV=0",
            "caps": {"source": "driver", "dsd": True},
        }
        item = {"id": "dsd", "path": "/music/test.dsf", "is_dsd": True}
        with patch("playback.alsa_output.dac_device_by_id", return_value=device), patch(
            "playback.alsa_output.subprocess.Popen"
        ) as popen:
            ok, message = start_dac_playback(device["id"], item, {})

        self.assertFalse(ok)
        self.assertIn("MPD", message)
        popen.assert_not_called()

    def test_busy_probe_preserves_a_previous_verified_result(self):
        result = preserve_verified_busy_probe(
            {
                "source": "alsa-hw-params",
                "verified": True,
                "available": True,
                "native_dsd": True,
                "native_dsd_formats": ["DSD_U32_LE"],
                "pcm_rates": [44100, 192000],
            },
            {
                "busy": True,
                "available": False,
                "error": "ALSA open failed (-16)",
                "probed_at": 10,
            },
        )
        self.assertTrue(result["verified"])
        self.assertTrue(result["native_dsd"])
        self.assertTrue(result["busy"])
        self.assertIn("(-16)", result["error"])

    def test_busy_probe_does_not_promote_unverified_result(self):
        result = preserve_verified_busy_probe(
            {
            "verified": True,
            },
            {"busy": False, "verified": False},
        )
        self.assertFalse(result["verified"])


if __name__ == "__main__":
    unittest.main()
