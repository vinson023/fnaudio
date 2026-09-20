import os
import tempfile
import unittest

from vorbis_reader import MAX_VORBIS_READ_BYTES, read_vorbis_comments


class VorbisReaderTests(unittest.TestCase):
    def test_missing_or_non_text_paths_are_safe(self):
        self.assertEqual(read_vorbis_comments(None), {})
        self.assertEqual(read_vorbis_comments(123), {})
        self.assertEqual(read_vorbis_comments("missing-vorbis-file"), {})

    def test_reader_keeps_file_input_bounded(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "comments.bin")
            with open(path, "wb") as handle:
                handle.write(b"x" * (MAX_VORBIS_READ_BYTES + 1024))
            self.assertEqual(read_vorbis_comments(path), {})


if __name__ == "__main__":
    unittest.main()
