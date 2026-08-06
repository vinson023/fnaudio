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
                    "spotify_client_id": "client-id",
                    "spotify_client_secret": "private-secret",
                    "metadata_orphan_grace_days": 14,
                }
            )

            self.assertTrue(save_config(path, config))
            loaded = load_config(path)

            self.assertFalse(loaded["metadata_enabled"])
            self.assertEqual(loaded["spotify_client_id"], "client-id")
            self.assertEqual(loaded["spotify_client_secret"], "private-secret")
            self.assertEqual(loaded["metadata_orphan_grace_days"], 14)
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            self.assertEqual(payload["spotify_client_secret"], "private-secret")

    def test_metadata_cleanup_grace_is_bounded(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"metadata_orphan_grace_days": 999}, fh)
            self.assertEqual(load_config(path)["metadata_orphan_grace_days"], 90)


if __name__ == "__main__":
    unittest.main()
