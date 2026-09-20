import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, "app/server")
from library_scan_presentation import build_audio_item


class LibraryScanPresentationTests(unittest.TestCase):
    def test_build_audio_item_keeps_metadata_and_normalizes_format(self):
        stat = SimpleNamespace(st_mtime=12.9, st_mtime_ns=12900000000)
        metadata = {"title": "Song", "artist": "Artist"}
        info = {"duration": 42.5, "sample_rate": 96000}
        item = build_audio_item("abc", metadata, ".flac", "audio/flac", False,
                                1234, info, "/music/song.flac", 10.75, stat)

        self.assertEqual(item["format"], "FLAC")
        self.assertEqual(item["mime"], "audio/flac")
        self.assertFalse(item["is_dsd"])
        self.assertEqual(item["duration"], 42.5)
        self.assertEqual(item["added"], 10)
        self.assertEqual(item["added_ns"], 10750000000)
        self.assertEqual(item["modified"], 12)
        self.assertEqual(item["metadata_version"], 16)
        self.assertEqual(metadata, {"title": "Song", "artist": "Artist"})

    def test_dsd_flag_is_boolean(self):
        stat = SimpleNamespace(st_mtime=1, st_mtime_ns=2)
        item = build_audio_item("d", {}, ".dsf", "audio/x-dsf", 1, 2, {},
                                "/music/a.dsf", 1, stat)
        self.assertIs(item["is_dsd"], True)


if __name__ == "__main__":
    unittest.main()
