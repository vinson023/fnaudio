import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

from config import load_config, save_config


class ConfigTests(unittest.TestCase):
    def test_metadata_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            config.update(
                {
                    "library_path": "/vol1/music",
                    "library_paths": ["/vol1/music"],
                    "metadata_enabled": False,
                    "metadata_orphan_grace_days": 14,
                }
            )

            self.assertTrue(save_config(path, config))
            loaded = load_config(path)

            self.assertFalse(loaded["metadata_enabled"])
            self.assertEqual(loaded["metadata_orphan_grace_days"], 14)
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            self.assertNotIn("spotify_client_id", payload)
            self.assertNotIn("spotify_client_secret", payload)

    def test_metadata_cleanup_grace_is_bounded(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"metadata_orphan_grace_days": 999}, fh)
            self.assertEqual(load_config(path)["metadata_orphan_grace_days"], 90)

    def test_audio_scheduling_settings_are_bounded_and_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            config.update({"mpd_nice": -99, "ffmpeg_nice": 99, "dac_keepalive_mode": "invalid"})
            self.assertTrue(save_config(path, config))
            loaded = load_config(path)
            self.assertEqual(loaded["mpd_nice"], -5)
            self.assertEqual(loaded["ffmpeg_nice"], 10)
            self.assertEqual(loaded["dac_keepalive_mode"], "off")

    def test_usb_presence_samples_are_bounded_and_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            config["mpd_device_presence_samples"] = 99
            self.assertTrue(save_config(path, config))
            loaded = load_config(path)
            self.assertEqual(loaded["mpd_device_presence_samples"], 5)

    def test_resource_limits_are_bounded_and_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            config.update(
                {
                    "metadata_max_pending_jobs": 1,
                    "metadata_cache_max_bytes": 10**15,
                    "transcode_queue_max_jobs": 9999,
                    "transcode_cache_max_bytes": 1,
                    "cache_min_free_bytes": 1,
                    "ffmpeg_max_concurrency": 99,
                    "ffmpeg_job_timeout_seconds": 1,
                    "scan_timeout_seconds": 999999,
                }
            )
            self.assertTrue(save_config(path, config))
            loaded = load_config(path)
            self.assertEqual(loaded["metadata_max_pending_jobs"], 100)
            self.assertEqual(loaded["metadata_cache_max_bytes"], 8 * 1024 * 1024 * 1024)
            self.assertEqual(loaded["transcode_queue_max_jobs"], 1000)
            self.assertEqual(loaded["transcode_cache_max_bytes"], 64 * 1024 * 1024)
            self.assertEqual(loaded["cache_min_free_bytes"], 64 * 1024 * 1024)
            self.assertEqual(loaded["ffmpeg_max_concurrency"], 8)
            self.assertEqual(loaded["ffmpeg_job_timeout_seconds"], 30)
            self.assertEqual(loaded["scan_timeout_seconds"], 86400)


if __name__ == "__main__":
    unittest.main()
