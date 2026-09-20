import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "server")))

from metadata_artwork_file import open_bounded_artwork, read_bounded_artwork


class MetadataArtworkFileTests(unittest.TestCase):
    def test_reads_only_a_non_empty_file_within_bound(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "cover.jpg")
            with open(path, "wb") as handle:
                handle.write(b"cover")
            self.assertEqual(read_bounded_artwork(path, 5), b"cover")
            self.assertEqual(read_bounded_artwork(path, 4), b"")

    def test_opened_descriptor_keeps_a_bounded_size_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "cover.jpg")
            with open(path, "wb") as handle:
                handle.write(b"cover")
            opened = open_bounded_artwork(path, 8)
            self.assertIsNotNone(opened)
            handle, size = opened
            try:
                self.assertEqual(size, 5)
                with open(path, "ab") as replacement:
                    replacement.write(b"-expanded")
                self.assertEqual(handle.read(size), b"cover")
            finally:
                handle.close()

    def test_rejects_empty_invalid_and_non_text_paths(self):
        with tempfile.TemporaryDirectory() as root:
            empty = os.path.join(root, "empty.jpg")
            open(empty, "wb").close()
            self.assertIsNone(open_bounded_artwork(empty, 8))
            self.assertIsNone(open_bounded_artwork(object(), 8))
            self.assertIsNone(open_bounded_artwork(empty, True))

    def test_closes_handle_when_descriptor_stat_fails(self):
        handle = mock.Mock()
        handle.fileno.return_value = 7
        with mock.patch("metadata_artwork_file.open", return_value=handle), \
             mock.patch("metadata_artwork_file.os.fstat", side_effect=OSError("stat failed")):
            self.assertIsNone(open_bounded_artwork("cover.jpg", 8))
        handle.close.assert_called_once_with()

    def test_rejects_short_read_after_size_snapshot(self):
        handle = mock.Mock()
        handle.fileno.return_value = 7
        handle.read.return_value = b"short"
        with mock.patch("metadata_artwork_file.open", return_value=handle), \
             mock.patch("metadata_artwork_file.os.fstat", return_value=mock.Mock(st_size=8)):
            self.assertEqual(read_bounded_artwork("cover.jpg", 16), b"")
        handle.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
