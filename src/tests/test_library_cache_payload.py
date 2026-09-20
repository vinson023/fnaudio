import sys
import unittest

sys.path.insert(0, "app/server")

from library_cache_payload import MAX_LEGACY_CACHE_ITEMS, project_legacy_cache


class LibraryCachePayloadTests(unittest.TestCase):
    def test_projects_matching_object_with_list_items(self):
        self.assertEqual(project_legacy_cache({"library_path": "/music", "items": [{"id": "1"}], "signature": "abc"}, "/music"),
                         {"items": [{"id": "1"}], "signature": "abc"})

    def test_rejects_wrong_shape_or_path(self):
        self.assertIsNone(project_legacy_cache([], "/music"))
        self.assertIsNone(project_legacy_cache({"library_path": "/other", "items": []}, "/music"))
        self.assertIsNone(project_legacy_cache({"library_path": "/music", "items": {}}, "/music"))
        self.assertIsNone(project_legacy_cache({"library_path": "/music", "items": [None] * (MAX_LEGACY_CACHE_ITEMS + 1)}, "/music"))

    def test_rejects_list_with_broken_length(self):
        class BrokenList(list):
            def __len__(self):
                raise RuntimeError("broken length")

        self.assertIsNone(project_legacy_cache({"library_path": "/music", "items": BrokenList()}, "/music"))


if __name__ == "__main__":
    unittest.main()
