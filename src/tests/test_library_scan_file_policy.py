import sys
import unittest

sys.path.insert(0, "app/server")

from library_scan_file_policy import classify_filename


class LibraryScanFilePolicyTests(unittest.TestCase):
    def test_classifies_cue_audio_and_ignored_files(self):
        supported = {".flac": "audio/flac", ".mp3": "audio/mpeg", ".cue": "application/x-cue"}
        self.assertEqual(classify_filename("album.CUE", supported), "cue")
        self.assertEqual(classify_filename("song.FLAC", supported), "audio")
        self.assertEqual(classify_filename("cover.jpg", supported), "ignore")

    def test_self_write_staging_files_are_never_tracks(self):
        supported = {".flac": "audio/flac", ".mp3": "audio/mpeg", ".cue": "application/x-cue"}
        self.assertEqual(
            classify_filename("song.flac.fnaudio-tagging.flac", supported), "ignore"
        )
        self.assertEqual(
            classify_filename("Song.Flac.FNAUDIO-TAGGING.Flac", supported), "ignore"
        )
        self.assertEqual(classify_filename("song.flac", supported), "audio")
        self.assertEqual(classify_filename("album.cue", supported), "cue")

    def test_rejects_untrusted_inputs_without_coercion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify filename")

        self.assertEqual(classify_filename(Explosive(), {".mp3": "audio/mpeg"}), "ignore")
        self.assertEqual(classify_filename("song.mp3", None), "ignore")


if __name__ == "__main__":
    unittest.main()
