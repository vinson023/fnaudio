import sys
import os
import tempfile
import unittest

sys.path.insert(0, "app/server")

import library


class LibrarySignatureBudgetTests(unittest.TestCase):
    def test_signature_budget_constants_are_bounded(self):
        self.assertEqual(library.MAX_LIBRARY_SIGNATURE_PARTS, 200000)
        self.assertEqual(library.MAX_LIBRARY_SIGNATURE_BYTES, 8 * 1024 * 1024)

    def test_metadata_version_is_reserved_when_signature_budget_is_tiny(self):
        with tempfile.TemporaryDirectory() as root:
            open(os.path.join(root, "song.flac"), "wb").close()
            old_parts = library.MAX_LIBRARY_SIGNATURE_PARTS
            old_bytes = library.MAX_LIBRARY_SIGNATURE_BYTES
            old_version = library.METADATA_VERSION
            try:
                library.MAX_LIBRARY_SIGNATURE_PARTS = 2
                library.MAX_LIBRARY_SIGNATURE_BYTES = 32
                first = library.library_signature(root)
                library.METADATA_VERSION = old_version + 1
                second = library.library_signature(root)
            finally:
                library.MAX_LIBRARY_SIGNATURE_PARTS = old_parts
                library.MAX_LIBRARY_SIGNATURE_BYTES = old_bytes
                library.METADATA_VERSION = old_version
            self.assertNotEqual(first, second)

    def test_signature_uses_shared_digest_policy(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "song.flac")
            open(path, "wb").close()
            stat = os.stat(path)
            self.assertEqual(
                library.library_signature(root),
                library.digest_signature_parts([
                    "%s:%s:%s" % (path, stat.st_mtime_ns, stat.st_size),
                    "metadata_version:%s" % library.METADATA_VERSION,
                ]),
            )


if __name__ == "__main__":
    unittest.main()
