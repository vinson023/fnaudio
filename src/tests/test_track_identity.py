"""Track identity is content, not location.

Reported symptom: after reinstalling fnOS on new hardware with a new disk, the
restored favorites kept counting while the same songs were favorited again. A
track id used to be ``sha1(absolute path)``, so the reinstall renamed every track
and the old rows became unreachable ghosts.

These tests pin the property the migration depends on: the same bytes get the
same id from any path, and different bytes never share one.
"""

import hashlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

import track_identity
from track_identity import content_track_id, cue_track_id, fallback_track_id


class TrackIdentityTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)

    def write(self, name, payload):
        path = os.path.join(self.root.name, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(payload)
        return path

    def test_the_same_bytes_get_the_same_id_from_anywhere(self):
        first = self.write("a/song.flac", b"FLAC" + b"\x00" * 4096)
        second = self.write("b/copy-flac.dat", b"FLAC" + b"\x00" * 4096)
        self.assertEqual(content_track_id(first), content_track_id(second))

    def test_moving_the_file_keeps_the_id(self):
        path = self.write("music/song.flac", b"FLAC" + os.urandom(8192))
        before = content_track_id(path)
        moved = os.path.join(self.root.name, "elsewhere", "renamed.flac")
        os.makedirs(os.path.dirname(moved), exist_ok=True)
        os.replace(path, moved)
        self.assertEqual(before, content_track_id(moved))

    def test_one_changed_byte_changes_the_id(self):
        first = self.write("a.flac", b"FLAC" + b"\x01" * 8192)
        second = self.write("b.flac", b"FLAC" + b"\x01" * 4095 + b"\x02" + b"\x01" * 4096)
        self.assertNotEqual(content_track_id(first), content_track_id(second))

    def test_a_different_size_changes_the_id(self):
        first = self.write("short.flac", b"FLAC" + b"\x00" * 1024)
        second = self.write("long.flac", b"FLAC" + b"\x00" * 1024 + b"\x00")
        self.assertNotEqual(content_track_id(first), content_track_id(second))

    def test_large_files_are_sampled_without_reading_everything(self):
        # 8 MiB is well past the small-file path; the id still has to be stable.
        path = self.write("big.flac", b"FLAC" + os.urandom(track_identity.SMALL_FILE_LIMIT + 1024 * 1024))
        self.assertEqual(content_track_id(path), content_track_id(path))

    def test_an_unreadable_file_reports_nothing(self):
        missing = os.path.join(self.root.name, "gone.flac")
        self.assertEqual(content_track_id(missing), "")
        # The caller keeps a path-based id so the track does not vanish over a
        # transient IO error, and that fallback is still deterministic.
        self.assertEqual(fallback_track_id(missing), fallback_track_id(missing))
        self.assertNotEqual(fallback_track_id(missing), "")

    def test_cue_tracks_are_identified_by_the_sheet_plus_the_number(self):
        sheet = self.write("album.cue", b"FILE \"album.flac\" WAVE\n  TRACK 01 AUDIO\n")
        first = cue_track_id(sheet, 1)
        self.assertEqual(first, cue_track_id(sheet, 1))
        self.assertNotEqual(first, cue_track_id(sheet, 2))
        # Rewriting the sheet content moves every track of it, which is correct:
        # a re-split is a different album.
        with open(sheet, "ab") as handle:
            handle.write(b"  TRACK 02 AUDIO\n")
        self.assertNotEqual(first, cue_track_id(sheet, 1))

    def test_the_id_keeps_the_historic_width(self):
        path = self.write("width.flac", b"FLAC" + b"\x00" * 64)
        value = content_track_id(path)
        self.assertEqual(len(value), 16)
        self.assertTrue(all(character in "0123456789abcdef" for character in value))

    def test_it_is_not_a_hash_of_the_path_in_disguise(self):
        # Guard against a regression that quietly returns to path identity.
        path = self.write("same.flac", b"FLAC" + b"\x00" * 128)
        self.assertNotEqual(content_track_id(path), hashlib.sha1(path.encode()).hexdigest()[:16])


if __name__ == "__main__":
    unittest.main()
