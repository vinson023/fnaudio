import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "app/server")

from cue_reader import MAX_CUE_FILE_BYTES, read_cue_lines


class CueReaderTests(unittest.TestCase):
    def test_decodes_supported_encodings_and_bom(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "album.cue"
            path.write_bytes("TITLE \"测试\"\n".encode("utf-8-sig"))
            self.assertEqual(read_cue_lines(str(path)), ['TITLE "测试"'])

    def test_oversized_source_is_rejected_before_decode(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "large.cue"
            with path.open("wb") as handle:
                handle.write(b"x" * (MAX_CUE_FILE_BYTES + 1))
            self.assertEqual(read_cue_lines(str(path)), [])

    def test_untrusted_or_missing_path_is_safe(self):
        self.assertEqual(read_cue_lines(None), [])
        self.assertEqual(read_cue_lines("missing-file.cue"), [])


if __name__ == "__main__":
    unittest.main()
