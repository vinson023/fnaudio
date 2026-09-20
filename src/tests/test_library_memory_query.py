import unittest

import sys
sys.path.insert(0, "app/server")

from library_memory_query import MAX_MEMORY_ITEMS, MAX_MEMORY_SEARCH_TEXT, bounded_memory_items, bounded_random_memory_sample, filter_memory_page, filter_sort_memory_items, memory_item_root, memory_matches_search, memory_sort_key, memory_text


class LibraryMemoryQueryTests(unittest.TestCase):
    def test_bounded_memory_items_does_not_materialize_unbounded_iterables(self):
        self.assertEqual(len(bounded_memory_items(range(MAX_MEMORY_ITEMS + 100))), MAX_MEMORY_ITEMS)

    def test_random_sample_keeps_fixed_memory_for_large_inputs(self):
        calls = []

        def choose(upper):
            calls.append(upper)
            return upper - 1

        sample = bounded_random_memory_sample(range(MAX_MEMORY_ITEMS + 100), 100, choose)

        self.assertEqual(sample, list(range(100)))
        self.assertEqual(len(calls), MAX_MEMORY_ITEMS - 100)
        self.assertLessEqual(max(calls), MAX_MEMORY_ITEMS)

    def test_text_rejects_objects_and_bounds_strings(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify")
        self.assertEqual(memory_text(Explosive()), "")
        self.assertEqual(len(memory_text("x" * 5000)), 4096)
        self.assertTrue(memory_matches_search({}, object()))
        self.assertTrue(memory_matches_search({"title": "x" * 4096}, "x" * 4096 + "y"))

    def test_search_and_sort_are_deterministic_for_malformed_items(self):
        item = {"title": "Song", "artist": "Artist"}
        self.assertTrue(memory_matches_search(item, "song"))
        self.assertFalse(memory_matches_search(item, "missing"))
        self.assertEqual(memory_sort_key(item, "title", lambda value: 0), "song")
        self.assertEqual(memory_sort_key(None, "title", lambda value: 0), "")

    def test_numeric_sort_keys_isolate_broken_numeric_policy(self):
        def broken(_value):
            raise RuntimeError("numeric policy failed")

        self.assertEqual(memory_sort_key({"added": "bad"}, "added", broken), 0)
        self.assertEqual(memory_sort_key({"track_no": "bad"}, "track_no", broken), 2147483647)

    def test_search_haystack_has_a_total_text_bound(self):
        item = {"title": "a" * MAX_MEMORY_SEARCH_TEXT, "artist": "needle"}
        self.assertFalse(memory_matches_search(item, "needle"))

    def test_filter_sort_applies_folder_constraint(self):
        class Query:
            view = "folders"; group = ""; album = ""; search = ""; folder = "A"; root = "/music"
            sort_key = "title"; sort_dir = "asc"; group_column = "album"
        rows = [{"title": "B", "folder": "A", "path": "/music/B.mp3"}, {"title": "A", "folder": "B", "path": "/music/A.mp3"}]
        result = filter_sort_memory_items(rows, Query(), ["/music"], "未分类", lambda path, root: path.startswith(root + "/"), lambda value: 0)
        self.assertEqual([row["title"] for row in result], ["B"])

    def test_filter_sort_applies_dsd_constraint_without_a_prefilter_copy(self):
        class Query:
            view = "dsd"; group = ""; album = ""; search = ""; folder = ""; root = ""
            sort_key = "title"; sort_dir = "asc"; group_column = "album"

        rows = [{"title": "PCM", "is_dsd": False}, {"title": "DSD", "is_dsd": True}]
        result = filter_sort_memory_items(rows, Query(), [], "未分类", lambda *_: False, lambda value: 0)
        self.assertEqual([row["title"] for row in result], ["DSD"])

        rows = [{"title": "String false", "is_dsd": "false"}, {"title": "True", "is_dsd": True}]
        result = filter_sort_memory_items(rows, Query(), [], "未分类", lambda *_: False, lambda value: 0)
        self.assertEqual([row["title"] for row in result], ["True"])

    def test_filter_sort_bounds_and_isolates_broken_iterables(self):
        class Broken:
            def __iter__(self):
                return self

            def __next__(self):
                raise RuntimeError("iterator failed")

        class Endless:
            def __iter__(self):
                return iter([{"title": str(index)} for index in range(MAX_MEMORY_ITEMS + 1)])

        class Query:
            view = "all"; group = ""; album = ""; search = ""; folder = ""; root = ""
            sort_key = "title"; sort_dir = "asc"; group_column = "album"

        self.assertEqual(filter_sort_memory_items(Broken(), Query(), [], "未分类", lambda *_: False, lambda value: 0), [])
        bounded = filter_sort_memory_items(Endless(), Query(), [], "未分类", lambda *_: False, lambda value: 0)
        self.assertEqual(len(bounded), MAX_MEMORY_ITEMS)

    def test_filter_sort_isolates_broken_mapping_fields(self):
        class BrokenMapping(dict):
            def get(self, key, default=None):
                raise RuntimeError("field failed")

        class Query:
            view = "all"; group = ""; album = ""; search = ""; folder = ""; root = ""
            sort_key = "title"; sort_dir = "asc"; group_column = "album"

        result = filter_sort_memory_items([BrokenMapping()], Query(), [], "未分类", lambda *_: False, lambda value: 0)
        self.assertEqual(len(result), 1)

    def test_page_selection_keeps_count_and_ordered_window(self):
        class Query:
            view = "all"; group = ""; album = ""; search = ""; folder = ""; root = ""
            sort_key = "title"; sort_dir = "asc"; group_column = "album"
            limit = 2; offset = 1

        rows = [{"id": str(index), "title": "%04d" % index} for index in range(1000, 0, -1)]
        page, count = filter_memory_page(rows, Query(), [], "未分类", lambda *_: False, lambda value: 0)
        self.assertEqual(count, 1000)
        self.assertEqual([item["title"] for item in page], ["0002", "0003"])

    def test_page_selection_preserves_ties_and_one_shot_fallback(self):
        class Query:
            view = "all"; group = ""; album = ""; search = ""; folder = ""; root = ""
            sort_key = "title"; sort_dir = "desc"; group_column = "album"
            limit = 2; offset = 0

        rows = [{"id": "first", "title": "Same"}, {"id": "second", "title": "Same"}, {"id": "third", "title": "Other"}]
        page, count = filter_memory_page(rows, Query(), [], "未分类", lambda *_: False, lambda value: 0)
        self.assertEqual((count, [item["id"] for item in page]), (3, ["first", "second"]))
        page, count = filter_memory_page(iter(rows), Query(), [], "未分类", lambda *_: False, lambda value: 0)
        self.assertEqual((count, [item["id"] for item in page]), (3, ["first", "second"]))

    def test_page_selection_uses_sql_tie_breakers_for_descending_primary_sort(self):
        class Query:
            view = "all"; group = ""; album = ""; search = ""; folder = ""; root = ""
            sort_key = "artist"; sort_dir = "desc"; group_column = "album"
            limit = 2; offset = 0

        rows = [
            {"id": "z", "artist": "Artist", "title": "Zulu"},
            {"id": "a", "artist": "Artist", "title": "Alpha"},
            {"id": "m", "artist": "Artist", "title": "Alpha"},
        ]
        page, count = filter_memory_page(rows, Query(), [], "未分类", lambda *_: False, lambda value: 0)
        self.assertEqual((count, [item["id"] for item in page]), (3, ["a", "m"]))
        page, count = filter_memory_page(iter(rows), Query(), [], "未分类", lambda *_: False, lambda value: 0)
        self.assertEqual((count, [item["id"] for item in page]), (3, ["a", "m"]))

    def test_page_selection_rejects_boolean_and_object_coercion(self):
        class Query:
            view = "all"; group = ""; album = ""; search = ""; folder = ""; root = ""
            sort_key = "title"; sort_dir = "asc"; group_column = "album"
            limit = True; offset = object()

        page, count = filter_memory_page(iter([{"title": "Song"}]), Query(), [], "未分类", lambda *_: False, lambda value: 0)
        self.assertEqual((page, count), ([], 1))

    def test_page_selection_filters_a_replayable_cache_in_one_pass(self):
        class Query:
            view = "all"; group = ""; album = ""; search = ""; folder = ""; root = ""
            sort_key = "title"; sort_dir = "asc"; group_column = "album"
            limit = 2; offset = 0

        calls = []
        rows = [{"title": "B"}, {"title": "A"}, {"title": "C"}]
        def path_under(*args):
            calls.append(args)
            return False

        page, count = filter_memory_page(rows, Query(), [], "未分类", path_under, lambda value: 0)
        self.assertEqual((count, [item["title"] for item in page]), (3, ["A", "B"]))
        self.assertEqual(calls, [])

    def test_memory_root_matching_bounds_and_isolates_broken_roots(self):
        class BrokenRoots:
            def __iter__(self):
                raise RuntimeError("roots failed")

        self.assertEqual(memory_item_root({"path": "/music/a.mp3"}, BrokenRoots(), lambda *_: True), "")
        self.assertEqual(memory_item_root({"path": "/music/a.mp3"}, [object(), "/music"], lambda path, root: path.startswith(root + "/")), "/music")

    def test_memory_page_reuses_one_shot_roots_for_every_item(self):
        class Query:
            view = "folders"; group = ""; album = ""; search = ""; folder = ""; root = "/music"
            sort_key = "title"; sort_dir = "asc"; group_column = "album"
            limit = 10; offset = 0

        rows = [
            {"id": "a", "title": "A", "path": "/music/a.mp3"},
            {"id": "b", "title": "B", "path": "/music/b.mp3"},
        ]
        page, count = filter_memory_page(
            rows, Query(), (root for root in ["/music"]), "未分类",
            lambda path, root: path.startswith(root + "/"), lambda value: 0,
        )
        self.assertEqual((count, [item["id"] for item in page]), (2, ["a", "b"]))


if __name__ == "__main__":
    unittest.main()
