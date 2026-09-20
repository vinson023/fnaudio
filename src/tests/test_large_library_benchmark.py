import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tools")))

from benchmark_large_library import (
    group_cardinality,
    run_benchmark,
    wide_folder_sibling_count,
)


class LargeLibraryBenchmarkTests(unittest.TestCase):
    def test_benchmark_fixture_scales_with_the_library(self):
        # Two failure classes were invisible at the old shape: group paging, because albums
        # stopped at 2000 no matter how many tracks the fixture was handed, and folder paging or
        # folder search, because every directory had a few hundred siblings at most. The shapes
        # are functions of the library size now, so the relation is what gets pinned.
        self.assertEqual(group_cardinality(2500), 312)
        self.assertEqual(group_cardinality(100000), 12500)
        self.assertEqual(group_cardinality(1000000), 125000)
        self.assertEqual(wide_folder_sibling_count(2500), 625)
        self.assertEqual(wide_folder_sibling_count(100000), 25000)
        self.assertGreater(group_cardinality(100000), 10000, "cursor gains need five-digit group counts")
        self.assertGreater(wide_folder_sibling_count(100000), 10000, "folder pages need five-digit siblings")

    def test_benchmark_enforces_bounded_sqlite_pagination(self):
        with tempfile.TemporaryDirectory() as root:
            result = run_benchmark(root, track_count=2500, page_size=120)
        self.assertTrue(result["bounded_pagination"])
        self.assertEqual(result["tracks"], 2500)
        self.assertRegex(result["runtime"]["python"], r"^\d+\.\d+")
        self.assertRegex(result["runtime"]["sqlite"], r"^\d+\.\d+")
        self.assertEqual([page["returned"] for page in result["pages"]], [120, 120, 120])
        self.assertTrue(all(page["count"] == 2500 for page in result["pages"]))
        self.assertTrue(result["cursor_pagination"]["matching_page"])
        self.assertEqual(result["cursor_pagination"]["cursor_returned"], 120)
        self.assertEqual(result["cursor_pagination"]["offset_returned"], 120)
        self.assertEqual(result["cursor_pagination"]["count"], 2500)
        self.assertTrue(result["cursor_pagination"]["has_more"])
        # The depth sweep is what makes a keyset that stops seeking visible, so
        # both sorts have to report every measured depth with its own ratio.
        sweep = result["cursor_pagination"]
        self.assertEqual(sweep["depths"], [0, 1200, 1250, 2260])
        self.assertEqual(sweep["samples"], 3)
        self.assertEqual(set(sweep["sorts"]), {"title", "artist", "format"})
        for sort_key in ("title", "artist", "format"):
            measurements = sweep["sorts"][sort_key]
            self.assertEqual([page["offset"] for page in measurements], sweep["depths"])
            for page in measurements:
                self.assertEqual(page["count"], 2500)
                self.assertTrue(page["matching_page"], (sort_key, page))
                self.assertEqual(page["cursor_returned"], 120)
                self.assertEqual(page["offset_returned"], 120)
                # A continuation seeded at depth d shows rows d+120..d+239, so the
                # last measured depth (2260 here) is exactly the tail page.
                self.assertEqual(page["has_more"], page["offset"] + 240 < 2500)
                self.assertGreater(page["cursor_versus_offset"], 0.0)
        self.assertEqual(sweep["seed_offset"], 1250)
        self.assertIn(sweep["seed_offset"], sweep["depths"])
        self.assertGreater(sweep["seek_evidence_depth"], sweep["depths"][-1])
        expected_indexes = {
            "artist_asc": "idx_tracks_artist_nocase_title_id_asc",
            "artist_desc": "idx_tracks_artist_nocase_title_id_desc",
            "album_asc": "idx_tracks_album_nocase_title_id_asc",
            "album_desc": "idx_tracks_album_nocase_title_id_desc",
            "added_asc": "idx_tracks_added_title_id_asc",
            "added_desc": "idx_tracks_added_title_id_desc",
            "format_asc": "idx_tracks_format_nocase_title_id_asc",
            "format_desc": "idx_tracks_format_nocase_title_id_desc",
            "track_no_asc": "idx_tracks_track_no_title_id_asc",
            "track_no_desc": "idx_tracks_track_no_title_id_desc",
        }
        self.assertEqual(set(result["sorted_pages"]), set(expected_indexes))
        for name, index_name in expected_indexes.items():
            sorted_page = result["sorted_pages"][name]
            self.assertEqual([page["returned"] for page in sorted_page["pages"]], [120, 120, 120])
            self.assertTrue(all(page["count"] == 2500 for page in sorted_page["pages"]))
            self.assertTrue(any(index_name in detail for detail in sorted_page["plan"]), sorted_page["plan"])
            self.assertFalse(any("TEMP B-TREE" in detail for detail in sorted_page["plan"]), sorted_page["plan"])
        expected_folder_indexes = {
            "asc": "idx_folders_root_parent_name_nocase_asc",
            "desc": "idx_folders_root_parent_name_nocase_desc",
        }
        folder_pages = result["browse"]["folder_pages"]
        self.assertEqual(set(folder_pages), set(expected_folder_indexes))
        for sort_dir, index_name in expected_folder_indexes.items():
            entry = folder_pages[sort_dir]
            self.assertEqual(entry["count"], 81, sort_dir)
            self.assertEqual(entry["returned"], 81, sort_dir)
            self.assertTrue(any(index_name in detail for detail in entry["plan"]), (sort_dir, entry["plan"]))
            self.assertFalse(any("TEMP B-TREE" in detail for detail in entry["plan"]), (sort_dir, entry["plan"]))
        self.assertEqual(result["browse"]["albums"]["count"], 312)
        self.assertEqual(result["browse"]["albums"]["returned"], 120)
        self.assertEqual(result["browse"]["albums_tail"]["offset"], 192)
        self.assertEqual(result["browse"]["albums_tail"]["count"], 312)
        self.assertEqual(result["browse"]["albums_tail"]["returned"], 120)
        self.assertGreaterEqual(result["browse"]["albums_tail"]["hits"], 1)
        self.assertGreaterEqual(result["browse"]["albums_tail"]["misses"], 1)
        self.assertTrue(result["browse"]["albums_cursor"]["matching_page"])
        self.assertEqual(result["browse"]["albums_cursor"]["cursor_returned"], 120)
        self.assertEqual(result["browse"]["albums_cursor"]["offset_returned"], 120)
        self.assertEqual(result["browse"]["albums_cursor"]["count"], 312)
        self.assertTrue(result["browse"]["albums_cursor"]["has_more"])
        # A browse continuation must stay two single-comparison statements. The OR
        # they replaced is one query fewer and plans as a scan of every earlier
        # group, so the statement count is asserted, not just the page contents.
        cursor_pages = result["browse"]["group_cursor_pages"]
        self.assertEqual(set(cursor_pages), {"asc", "desc"})
        for sort_dir, entry in cursor_pages.items():
            self.assertEqual(entry["statements"], 2, (sort_dir, entry))
            # The measured continuation starts at an offset that is not always a full page from
            # the end: with 312 groups the ascending window at 240 can only hold 72 rows.
            self.assertEqual(entry["returned"], min(120, 312 - entry["offset"]), sort_dir)
            self.assertEqual(entry["count"], 312, sort_dir)
            self.assertGreater(entry["cursor_seconds"], 0.0)
            self.assertGreater(entry["cursor_versus_offset"], 0.0)
        self.assertEqual(cursor_pages["asc"]["offset"], 240)
        self.assertEqual(cursor_pages["desc"]["offset"], 192)
        self.assertEqual(result["browse"]["folders"]["count"], 81)
        self.assertEqual(result["browse"]["folders"]["returned"], 81)
        # The folder search page over the wide parent. The unit tests assert the same plan, but
        # they only build a few dozen siblings, which is the regime where a seek and a scan cost
        # the same; R58's fold that replaced the per-sibling pass over `tracks` is only visible
        # against thousands of them.
        search_page = result["browse"]["folder_search"]
        self.assertEqual(search_page["siblings"], wide_folder_sibling_count(2500))
        self.assertEqual(search_page["count"], 25)
        self.assertEqual(search_page["returned"], 25)
        self.assertLessEqual(search_page["returned"], 120)
        self.assertGreater(search_page["seconds"], 0.0)
        self.assertTrue(any("idx_folders_root_parent_name_nocase_asc" in detail for detail in search_page["plan"]),
                        search_page["plan"])
        self.assertFalse(any("TEMP B-TREE" in detail for detail in search_page["plan"]), search_page["plan"])
        self.assertEqual(result["browse"]["creator_albums"]["artist"], "Artist 0000")
        self.assertGreaterEqual(result["browse"]["creator_albums"]["count"], 1)
        # Every group view has to read its page straight out of an ordering
        # index. These eight entries fail the moment a browse page goes back to
        # sorting the whole group table for one window total.
        expected_group_indexes = {
            "albums_asc": "idx_albums_name_nocase_asc",
            "albums_desc": "idx_albums_name_nocase_desc",
            "artists_asc": "idx_artists_name_nocase_asc",
            "artists_desc": "idx_artists_name_nocase_desc",
            "composers_asc": "idx_composers_name_nocase_asc",
            "composers_desc": "idx_composers_name_nocase_desc",
            "genres_asc": "idx_genres_name_nocase_asc",
            "genres_desc": "idx_genres_name_nocase_desc",
        }
        group_pages = result["browse"]["group_pages"]
        self.assertEqual(set(group_pages), set(expected_group_indexes))
        for label, index_name in expected_group_indexes.items():
            entry = group_pages[label]
            self.assertTrue(any(index_name in detail for detail in entry["plan"]), (label, entry["plan"]))
            self.assertFalse(any("TEMP B-TREE" in detail for detail in entry["plan"]), (label, entry["plan"]))
            self.assertLessEqual(entry["returned"], 120)
            self.assertGreaterEqual(entry["count"], 1)
        self.assertEqual(group_pages["albums_asc"]["count"], 312)
        self.assertEqual(group_pages["albums_desc"]["count"], 312)
        for view in ("albums", "creator_albums", "folders", "roots"):
            cache = result["browse"][view]
            self.assertGreaterEqual(cache["hits"], 1)
            self.assertGreaterEqual(cache["misses"], 1)
            self.assertGreaterEqual(cache["speedup"], 0.0)
        self.assertEqual(result["browse"]["roots"]["count"], 1)
        self.assertEqual(result["browse"]["roots"]["track_count"], 2500)
        self.assertEqual(result["metadata_page_overlay"]["items"], 120)
        self.assertTrue(result["metadata_page_overlay"]["tag_precedence"])
        self.assertGreaterEqual(result["metadata_page_overlay"]["cold_seconds"], 0.0)
        self.assertGreaterEqual(result["metadata_page_overlay"]["repeat_seconds"], 0.0)
        self.assertGreaterEqual(result["metadata_page_overlay"]["speedup"], 0.0)
        self.assertGreaterEqual(result["metadata_page_overlay"]["cache_hits"], 1)
        self.assertGreaterEqual(result["metadata_page_overlay"]["cache_misses"], 1)
        self.assertGreaterEqual(result["metadata_page_overlay"]["cache_entries"], 1)
        self.assertGreaterEqual(result["metadata_page_overlay"]["cache_limit"], 1)
        # Reopening the index has to stay cheaper than reusing a handle, and the
        # pool must have actually reused one, or this section measures nothing. The
        # two counters are traffic inside this sample window only, because draining
        # idle handles does not rewind the process-wide counters and the tool also
        # runs after other modules may have used the pool.
        connection = result["first_screen_connection"]
        self.assertEqual(connection["samples"], 5)
        self.assertEqual(connection["reuses"], connection["samples"] - 1)
        self.assertEqual(connection["creations"], 1)
        self.assertEqual(connection["idle_after_drain"], 0)
        self.assertGreater(connection["speedup"], 1.0)
        self.assertGreater(connection["saving_seconds"], 0.0)
        # The tool rounds each duration on its own, so the reported saving can
        # differ from a re-subtraction of the rounded fields by its own precision.
        self.assertLess(
            abs(
                (connection["unpooled_seconds"] - connection["pooled_seconds"])
                - connection["saving_seconds"]
            ),
            1e-5,
        )
        # An empty artist/album/format is the key an untagged file is indexed with,
        # and it used to make every page that ended inside that cluster answer
        # has_more without a continuation cursor. Each walk has to cross a whole
        # cluster by cursor alone, and never lose the cursor while rows remain.
        empty_group = result["empty_key_group_pagination"]
        self.assertEqual(empty_group["rows"], 1200)
        self.assertEqual(empty_group["page_size"], 500)
        self.assertEqual(set(empty_group["walks"]), {"artist_asc", "artist_desc", "format_desc"})
        for label, steps in empty_group["walks"].items():
            self.assertTrue(steps, label)
            self.assertGreaterEqual(sum(page["returned"] for page in steps), empty_group["rows"], label)
            for page in steps:
                self.assertLessEqual(page["returned"], empty_group["page_size"], (label, page))
                if page["returned"] < empty_group["page_size"]:
                    self.assertFalse(page["has_more"], (label, page))
                if page["has_more"]:
                    self.assertTrue(page["continues"], (label, page))
                self.assertGreater(page["cursor_seconds"], 0.0, (label, page))
                self.assertGreater(page["offset_seconds"], 0.0, (label, page))
        self.assertLess(result["query_peak_python_bytes"], 64 * 1024 * 1024)
        self.assertEqual(result["search"]["active"]["count"], 1)
        self.assertEqual(result["search"]["active"]["first_id"], "track-001250")
        self.assertIn("speedup_vs_like", result["search"])
        if result["search"].get("like_baseline"):
            self.assertGreaterEqual(result["search"]["speedup_vs_like"], 0.0)


if __name__ == "__main__":
    unittest.main()
