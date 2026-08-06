import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "app/server")

import library


class LibraryCacheTests(unittest.TestCase):
    def test_unchanged_refresh_does_not_rewrite_existing_sqlite_index(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0])
            library.save_items_to_sqlite(config, [], "same-signature")
            old_signature = library.FS_CACHE["signature"]
            try:
                library.FS_CACHE["signature"] = "same-signature"
                with patch.object(library, "scan_libraries", return_value=([], "same-signature")), patch.object(library, "save_library_cache") as save_cache:
                    library.refresh_library_if_changed(config, force=True)
                    save_cache.assert_not_called()
            finally:
                library.FS_CACHE["signature"] = old_signature

    def test_unchanged_background_refresh_does_not_hydrate_full_library(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0])
            old_items = library.MUSIC_CACHE["items"]
            old_signature = library.FS_CACHE["signature"]
            try:
                library.MUSIC_CACHE["items"] = []
                library.FS_CACHE["signature"] = "same-signature"
                with patch.object(library, "library_signature_for_config", return_value="same-signature"), \
                     patch.object(library, "load_items_from_sqlite", side_effect=AssertionError("full library loaded")), \
                     patch.object(library, "scan_libraries", side_effect=AssertionError("full scan started")):
                    library.refresh_library_if_changed(config, force=False)
            finally:
                library.MUSIC_CACHE["items"] = old_items
                library.FS_CACHE["signature"] = old_signature

    def test_large_library_uses_sqlite_without_serializing_all_items_to_json(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            old_items = library.MUSIC_CACHE["items"]
            old_signature = library.FS_CACHE["signature"]
            try:
                library.MUSIC_CACHE["items"] = [{"id": str(index), "path": "/music/%s.flac" % index} for index in range(library.LIBRARY_JSON_CACHE_LIMIT + 1)]
                library.FS_CACHE["signature"] = "large-test"
                library.save_library_cache(config)

                with open(library.library_cache_path(config), "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                self.assertEqual(payload["items"], [])
                self.assertTrue(payload["sqlite"])
                self.assertEqual(library.library_summary_from_sqlite(config)["count"], library.LIBRARY_JSON_CACHE_LIMIT + 1)
            finally:
                library.MUSIC_CACHE["items"] = old_items
                library.FS_CACHE["signature"] = old_signature


if __name__ == "__main__":
    unittest.main()
