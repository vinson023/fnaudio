import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

import library


class LibraryScanSignatureTests(unittest.TestCase):
    def test_signature_includes_cue_and_supported_audio_files(self):
        with tempfile.TemporaryDirectory() as root:
            open(os.path.join(root, "album.cue"), "wb").close()
            open(os.path.join(root, "song.flac"), "wb").close()
            open(os.path.join(root, "cover.jpg"), "wb").close()
            signature = library.library_signature(root)
            self.assertTrue(signature)

            os.remove(os.path.join(root, "album.cue"))
            changed = library.library_signature(root)
            self.assertNotEqual(changed, signature)


if __name__ == "__main__":
    unittest.main()
