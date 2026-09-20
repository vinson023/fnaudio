import sys
import unittest

sys.path.insert(0, "app/server")

from library_query_spec import MAX_LIBRARY_ITEM_ID_CHARS, MAX_LIBRARY_OFFSET, MAX_LIBRARY_PATH_CHARS, MAX_LIBRARY_QUERY_TEXT_CHARS, normalize_library_item_id, normalize_library_item_sequence, parse_library_folder_query, parse_library_group_query, parse_library_item_ids, parse_library_page_query, parse_optional_page


class LibraryQuerySpecTests(unittest.TestCase):
    def test_normalizes_list_query_values_and_bounds_page(self):
        query = parse_library_page_query({
            "view": ["albums"], "group": ["Example"], "search": ["  TRACK  "],
            "sort": ["track_no"], "dir": ["DESC"], "limit": ["9999"], "offset": ["-4"],
        })
        self.assertEqual(query.limit, 500)
        self.assertEqual(query.offset, 0)
        self.assertEqual(query.search, "track")
        self.assertEqual(query.group_column, "album")
        self.assertEqual(query.sql_sort_dir, "DESC")
        self.assertIn("track_no", query.sql_order)

    def test_invalid_values_use_safe_default_order_and_page(self):
        query = parse_library_page_query({"limit": "nope", "offset": "bad", "sort": "not-a-column", "dir": "sideways"})
        self.assertEqual(query.limit, 100)
        self.assertEqual(query.offset, 0)
        self.assertEqual(query.sort_dir, "asc")
        self.assertEqual(query.sql_sort_dir, "ASC")
        self.assertEqual(query.sql_order, "title COLLATE NOCASE")
        self.assertEqual(query.sql_order_by, "title COLLATE NOCASE ASC, id ASC")
        self.assertEqual(parse_library_page_query({"limit": "9" * 10000}).limit, 100)
        self.assertEqual(parse_library_page_query({"offset": str(MAX_LIBRARY_OFFSET + 1)}).offset, MAX_LIBRARY_OFFSET)
        self.assertEqual(parse_optional_page(100, MAX_LIBRARY_OFFSET + 1).offset, MAX_LIBRARY_OFFSET)
        self.assertEqual(parse_library_page_query({"limit": "1.5", "offset": "2.5"}).limit, 100)
        self.assertEqual(parse_library_page_query({"limit": 1.5, "offset": 2.5}).offset, 0)
        self.assertEqual(parse_library_page_query({"limit": 10 ** 10000}).limit, 100)

    def test_offset_ceiling_stays_small_enough_for_direct_sqlite_pagination(self):
        self.assertEqual(MAX_LIBRARY_OFFSET, 100000)

    def test_title_order_keeps_the_stable_id_tiebreaker_without_repeating_title(self):
        ascending = parse_library_page_query({"sort": "title", "dir": "asc"})
        descending = parse_library_page_query({"sort": "title", "dir": "desc"})
        artist = parse_library_page_query({"sort": "artist", "dir": "desc"})
        self.assertEqual(ascending.sql_order_by, "title COLLATE NOCASE ASC, id ASC")
        self.assertEqual(descending.sql_order_by, "title COLLATE NOCASE DESC, id ASC")
        self.assertEqual(artist.sql_order_by, "artist COLLATE NOCASE DESC, title COLLATE NOCASE ASC, id ASC")

    def test_optional_page_normalizes_equivalent_cache_inputs_and_keeps_unpaged_queries(self):
        self.assertEqual(parse_optional_page("100.0", "-4").limit, 100)
        self.assertEqual(parse_optional_page("100.0", "-4").offset, 0)
        self.assertEqual(parse_optional_page("9999", "8").limit, 500)
        self.assertEqual(parse_optional_page("bad", "bad").limit, 100)
        self.assertIsNone(parse_optional_page(None, 42))
        self.assertEqual(parse_optional_page("100.5", "2.5").limit, 100)
        self.assertEqual(parse_optional_page("100.5", "2.5").offset, 0)

    def test_item_ids_are_deduplicated_and_bounded_before_sqlite_lookup(self):
        self.assertEqual(parse_library_item_ids(" first,second,first, ,third "), ["first", "second", "third"])
        with self.assertRaises(ValueError):
            parse_library_item_ids(",".join("id-%s" % index for index in range(121)))

    def test_text_params_are_bounded_without_stringifying_arbitrary_objects(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("query parser must not stringify custom values")

        query = parse_library_page_query({
            "view": Explosive(), "group": "g" * (MAX_LIBRARY_QUERY_TEXT_CHARS + 10),
            "search": " X" * (MAX_LIBRARY_QUERY_TEXT_CHARS + 10),
        })
        self.assertEqual(query.view, "all")
        self.assertEqual(len(query.group), MAX_LIBRARY_QUERY_TEXT_CHARS)
        self.assertEqual(len(query.search), MAX_LIBRARY_QUERY_TEXT_CHARS)
        self.assertEqual(parse_library_item_ids(Explosive()), [])
        with self.assertRaises(ValueError):
            parse_library_item_ids("x" * (MAX_LIBRARY_ITEM_ID_CHARS + 1))

    def test_direct_page_and_text_bounds_reject_hostile_configuration_values(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("query bounds must not coerce objects")
            def __float__(self):
                raise AssertionError("query bounds must not coerce objects")

        self.assertEqual(parse_optional_page("bad", 0, Explosive(), Explosive()).limit, 100)
        self.assertEqual(parse_library_item_ids("a,b", Explosive()), ["a", "b"])
        query = parse_library_page_query({"search": "x" * (MAX_LIBRARY_QUERY_TEXT_CHARS + 20)})
        self.assertEqual(len(query.search), MAX_LIBRARY_QUERY_TEXT_CHARS)

    def test_parameter_reader_isolates_broken_mapping_access(self):
        class BrokenMapping:
            def get(self, key):
                raise RuntimeError("broken mapping")

        self.assertEqual(parse_library_page_query(BrokenMapping()).view, "all")

    def test_internal_item_sequence_keeps_order_without_object_coercion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("internal ids must not stringify arbitrary objects")

        self.assertEqual(normalize_library_item_sequence([" second ", "first", "second", Explosive(), ""]), ["second", "first"])
        self.assertEqual(normalize_library_item_sequence("first,second"), [])
        self.assertEqual(normalize_library_item_id(" one "), "one")
        self.assertEqual(normalize_library_item_id(Explosive()), "")
        self.assertEqual(normalize_library_item_id("x" * (MAX_LIBRARY_ITEM_ID_CHARS + 1)), "")

    def test_group_and_folder_queries_share_bounded_safe_normalization(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("browse parser must not stringify custom values")

        group = parse_library_group_query("ALBUMS", "  NEEDLE  ", "9999", "-2", "DESC", "A" * 999, Explosive(), "cursor")
        self.assertEqual(group.view, "albums")
        self.assertEqual(group.search, "needle")
        self.assertEqual((group.page.limit, group.page.offset), (500, 0))
        self.assertEqual(group.sql_sort_dir, "DESC")
        self.assertEqual(len(group.artist), MAX_LIBRARY_QUERY_TEXT_CHARS)
        self.assertEqual(group.composer, "")
        self.assertEqual(group.cursor, "cursor")

        folder = parse_library_folder_query("p" * 9999, Explosive(), Explosive(), Explosive(), Explosive(), "  SEARCH  ", "cursor")
        self.assertEqual(len(folder.parent), MAX_LIBRARY_PATH_CHARS)
        self.assertEqual(folder.root, "")
        self.assertEqual(folder.search, "search")
        self.assertEqual((folder.page.limit, folder.page.offset), (100, 0))
        self.assertEqual(folder.sql_sort_dir, "ASC")
        self.assertEqual(folder.cursor, "cursor")


if __name__ == "__main__":
    unittest.main()
