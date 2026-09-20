import sys
import unittest

sys.path.insert(0, "app/server")

from library_metadata_presentation import library_metadata


class LibraryMetadataPresentationTests(unittest.TestCase):
    def test_tagged_values_keep_source_and_presentation(self):
        result = library_metadata(
            "/music/01_Artist - Filename.flac",
            {"title": " Tagged Title ", "artist": " Tagged Artist ", "album": " Album ", "composer": " C ", "genre": " G ", "track_no": "03/10"},
            "Album", "Music",
        )
        self.assertEqual(result["title"], "Tagged Title")
        self.assertEqual(result["artist"], "Tagged Artist")
        self.assertEqual(result["track_no"], 3)
        self.assertEqual(result["metadata_source"], {"title": "tag", "artist": "tag", "album": "tag"})

    def test_filename_and_unknown_fallbacks_do_not_mutate_tags(self):
        tags = {"title": "", "track_no": "side A"}
        result = library_metadata("/music/02_Artist - Song.flac", tags, object(), object())
        self.assertEqual(tags, {"title": "", "track_no": "side A"})
        self.assertEqual(result["title"], "Song")
        self.assertEqual(result["artist"], "Artist")
        self.assertEqual(result["album"], "未分类")
        self.assertEqual(result["folder"], "")
        self.assertEqual(result["metadata_source"], {"title": "filename", "artist": "filename", "album": "unknown"})


if __name__ == "__main__":
    unittest.main()
