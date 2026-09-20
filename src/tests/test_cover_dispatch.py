import sys
import unittest

sys.path.insert(0, "app/server")

from cover_dispatch import cover_kind


class CoverDispatchTests(unittest.TestCase):
    def test_supported_extensions_map_to_stable_reader_kinds(self):
        self.assertEqual(cover_kind("/music/a.MP3"), "id3")
        self.assertEqual(cover_kind("/music/a.dsf"), "id3")
        self.assertEqual(cover_kind("/music/a.ape"), "ape")
        self.assertEqual(cover_kind("/music/a.wav"), "wav")
        self.assertEqual(cover_kind("/music/a.flac"), "flac")
        self.assertEqual(cover_kind("/music/a.m4a"), "mp4")
        self.assertEqual(cover_kind("/music/a.mp4"), "mp4")

    def test_unknown_or_untrusted_paths_are_safe(self):
        self.assertEqual(cover_kind("/music/a.txt"), "")
        self.assertEqual(cover_kind(None), "")
        self.assertEqual(cover_kind({}), "")
        self.assertEqual(cover_kind("x" * 5000 + ".flac"), "")


if __name__ == "__main__":
    unittest.main()
