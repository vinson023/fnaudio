import unittest

import sys
sys.path.insert(0, "app/server")

from library_memory_page import build_memory_library_page


class LibraryMemoryPageTests(unittest.TestCase):
    class Query:
        view = "all"
        group = ""
        album = ""
        search = ""
        folder = ""
        root = ""
        sort_key = "title"
        sort_dir = "asc"
        group_column = "album"
        limit = 2
        offset = 1

    def test_builds_bounded_window_without_mutating_source(self):
        rows = [{"id": "b", "title": "B"}, {"id": "a", "title": "A"}, {"id": "c", "title": "C"}]
        result = build_memory_library_page(rows, self.Query(), [], "未分类", lambda *_: False, lambda value: 0)
        self.assertEqual([row["id"] for row in result["items"]], ["b", "c"])
        self.assertEqual(result["count"], 3)
        self.assertEqual([row["id"] for row in rows], ["b", "a", "c"])

    def test_random_view_uses_fixed_sample_before_shuffle(self):
        query = type("Query", (self.Query,), {"view": "random100", "limit": 100, "offset": 0})()
        rows = [{"id": str(index), "title": str(index)} for index in range(140)]
        seen = []
        choices = []

        def shuffle(sample):
            seen.append(len(sample))

        def choose(upper):
            choices.append(upper)
            return upper - 1

        result = build_memory_library_page(rows, query, [], "未分类", lambda *_: False, lambda value: 0, shuffle=shuffle, randrange=choose)
        self.assertEqual(seen, [100])
        self.assertEqual(len(choices), 40)
        self.assertEqual(result["count"], 100)
        self.assertEqual(len(result["items"]), 100)


if __name__ == "__main__":
    unittest.main()
