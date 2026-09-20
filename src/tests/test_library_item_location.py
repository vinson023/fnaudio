import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

from library_item_location import resolve_item_location


class LibraryItemLocationTests(unittest.TestCase):
    def test_resolves_file_inside_configured_root(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "track.flac")
            open(path, "wb").close()
            result = resolve_item_location({"id": "x", "path": path}, "fallback", [root], lambda p, r: os.path.commonpath([p, r]) == r)
            self.assertEqual(result["id"], "x")
            self.assertEqual(result["path"], os.path.realpath(path))

    def test_rejects_missing_outside_and_oversized_paths(self):
        with tempfile.TemporaryDirectory() as root:
            outside = os.path.join(os.path.dirname(root), "outside.flac")
            self.assertIsNone(resolve_item_location({"path": outside}, "x", [root], lambda *_: True))
            self.assertIsNone(resolve_item_location({"path": "x" * 20}, "x", [root], lambda *_: True, max_text=10))

    def test_invalid_item_or_roots_are_safe(self):
        self.assertIsNone(resolve_item_location(None, "x", [], None))
        self.assertIsNone(resolve_item_location({"path": "/tmp/x"}, "x", [None], lambda *_: True))


if __name__ == "__main__":
    unittest.main()
