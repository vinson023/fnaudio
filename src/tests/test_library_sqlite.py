import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

from library import UNCLASSIFIED, query_library_folders, query_library_groups, query_library_item_location, query_library_page, query_library_root_folders, read_metadata, save_items_to_sqlite


class LibrarySqliteTests(unittest.TestCase):
    def test_missing_tags_do_not_turn_parent_folders_into_artist_or_album(self):
        with tempfile.TemporaryDirectory() as root:
            folder = os.path.join(root, "Folder Artist", "Folder Album")
            os.makedirs(folder)
            path = os.path.join(folder, "Track.flac")
            with open(path, "wb"):
                pass

            metadata = read_metadata(path, root, probe_tags={"title": "Track"})

            self.assertEqual(metadata["artist"], "未知艺术家")
            self.assertEqual(metadata["album"], UNCLASSIFIED)
            self.assertEqual(metadata["metadata_source"]["artist"], "unknown")
            self.assertEqual(metadata["metadata_source"]["album"], "unknown")

    def test_explicit_tags_are_kept_independent_of_folder_names(self):
        with tempfile.TemporaryDirectory() as root:
            folder = os.path.join(root, "Wrong Artist", "Wrong Album")
            os.makedirs(folder)
            path = os.path.join(folder, "Track.flac")
            with open(path, "wb"):
                pass

            metadata = read_metadata(path, root, probe_tags={"title": "Track", "artist": "Tagged Artist", "album": "Tagged Album"})

            self.assertEqual(metadata["artist"], "Tagged Artist")
            self.assertEqual(metadata["album"], "Tagged Album")
            self.assertEqual(metadata["metadata_source"]["artist"], "tag")
            self.assertEqual(metadata["metadata_source"]["album"], "tag")

    def test_multi_root_folders_do_not_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as root:
            first_root = os.path.join(root, "music-a")
            second_root = os.path.join(root, "music-b")
            os.makedirs(os.path.join(first_root, "Shared"))
            os.makedirs(os.path.join(second_root, "Shared"))
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [first_root, second_root]}
            items = [
                self._item("a-1", os.path.join(first_root, "Shared", "first.flac"), "First", 2),
                self._item("a-2", os.path.join(first_root, "Shared", "second.flac"), "Second", 1),
                self._item("b-1", os.path.join(second_root, "Shared", "third.flac"), "Third", 1),
            ]
            save_items_to_sqlite(config, items, "test")

            roots = query_library_root_folders(config)
            self.assertEqual([row["track_count"] for row in roots], [2, 1])
            self.assertEqual([row["name"] for row in query_library_folders(config, "", first_root)], ["Shared"])
            self.assertEqual([row["name"] for row in query_library_folders(config, "", second_root)], ["Shared"])
            folder_page = query_library_folders(config, "", first_root, "asc", 1, 0)
            self.assertEqual(folder_page["count"], 1)
            self.assertEqual(folder_page["folders"][0]["name"], "Shared")

            page = query_library_page(config, {"view": "folders", "root": first_root, "folder": "Shared", "sort": "track_no", "dir": "asc", "limit": "1", "offset": "0"})
            self.assertEqual(page["count"], 2)
            self.assertEqual([item["id"] for item in page["items"]], ["a-2"])
            second_page = query_library_page(config, {"view": "folders", "root": first_root, "folder": "Shared", "sort": "track_no", "dir": "asc", "limit": "1", "offset": "1"})
            self.assertEqual([item["id"] for item in second_page["items"]], ["a-1"])

    def test_album_index_falls_back_to_track_artist(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            item = self._item("one", os.path.join(music_root, "one.flac"), "One", 1)
            item.update({"album": "Example Album", "artist": "Example Artist", "album_artist": ""})

            save_items_to_sqlite(config, [item], "test")
            groups = query_library_groups(config, "albums")

            self.assertEqual(groups[0]["name"], "Example Album")
            self.assertEqual(groups[0]["artist"], "Example Artist")

    def test_index_save_removes_deleted_tracks_and_keeps_current_tracks(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("keep", os.path.join(music_root, "keep.flac"), "Keep", 1)
            removed = self._item("remove", os.path.join(music_root, "remove.flac"), "Remove", 2)
            save_items_to_sqlite(config, [first, removed], "first")
            save_items_to_sqlite(config, [first], "second")
            page = query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
            self.assertEqual(page["count"], 1)
            self.assertEqual(page["items"][0]["id"], "keep")

    def test_item_location_is_resolved_only_inside_configured_music_roots(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            outside_root = os.path.join(root, "outside")
            os.makedirs(music_root)
            os.makedirs(outside_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            inside = self._item("inside", os.path.join(music_root, "album", "inside.flac"), "Inside", 1)
            outside = self._item("outside", os.path.join(outside_root, "outside.flac"), "Outside", 2)
            os.makedirs(os.path.dirname(inside["path"]))
            with open(inside["path"], "wb"):
                pass
            with open(outside["path"], "wb"):
                pass
            save_items_to_sqlite(config, [inside, outside], "test")

            location = query_library_item_location(config, "inside")
            self.assertEqual(location["path"], os.path.realpath(inside["path"]))
            self.assertEqual(location["folder"], os.path.dirname(os.path.realpath(inside["path"])))
            self.assertIsNone(query_library_item_location(config, "outside"))
            self.assertIsNone(query_library_item_location(config, "missing"))

    def test_item_location_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            outside_root = os.path.join(root, "outside")
            os.makedirs(music_root)
            os.makedirs(outside_root)
            outside_file = os.path.join(outside_root, "secret.flac")
            with open(outside_file, "wb"):
                pass
            link = os.path.join(music_root, "linked.flac")
            try:
                os.symlink(outside_file, link)
            except OSError as exc:
                self.skipTest("symlinks are unavailable: %s" % exc)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            save_items_to_sqlite(config, [self._item("escape", link, "Escape", 1)], "test")
            self.assertIsNone(query_library_item_location(config, "escape"))

    def test_incremental_group_and_folder_refresh_handles_changes(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(os.path.join(music_root, "A", "Disc 1"))
            os.makedirs(os.path.join(music_root, "B"))
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("one", os.path.join(music_root, "A", "Disc 1", "one.flac"), "One", 1)
            first.update({"album": "Old Album", "artist": "Old Artist", "composer": "Old Composer", "genre": "Old Genre"})
            save_items_to_sqlite(config, [first], "first")

            changed = dict(first)
            changed.update({"path": os.path.join(music_root, "B", "one.flac"), "album": "New Album", "artist": "New Artist", "composer": "New Composer", "genre": "New Genre"})
            save_items_to_sqlite(config, [changed], "second")

            self.assertEqual([row["name"] for row in query_library_folders(config, "", music_root)], ["B"])
            self.assertEqual([row["name"] for row in query_library_groups(config, "albums")], ["New Album"])
            self.assertEqual([row["name"] for row in query_library_groups(config, "artists")], ["New Artist"])
            self.assertEqual([row["name"] for row in query_library_groups(config, "composers")], ["New Composer"])
            self.assertEqual([row["name"] for row in query_library_groups(config, "genres")], ["New Genre"])

    def test_artist_albums_then_tracks_are_scoped_to_the_selected_artist(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("a-1", os.path.join(music_root, "a-1.flac"), "First", 1)
            first.update({"artist": "Artist A", "album": "Album One"})
            second = self._item("a-2", os.path.join(music_root, "a-2.flac"), "Second", 1)
            second.update({"artist": "Artist A", "album": "Album Two"})
            third = self._item("b-1", os.path.join(music_root, "b-1.flac"), "Other", 1)
            third.update({"artist": "Artist B", "album": "Album One"})
            save_items_to_sqlite(config, [first, second, third], "test")

            albums = query_library_groups(config, "albums", artist="Artist A")
            self.assertEqual([row["name"] for row in albums], ["Album One", "Album Two"])
            page = query_library_page(config, {"view": "artists", "group": "Artist A", "album": "Album One", "sort": "track_no"})
            self.assertEqual(page["count"], 1)
            self.assertEqual([item["id"] for item in page["items"]], ["a-1"])

    def test_composer_albums_then_tracks_are_scoped_to_the_selected_composer(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("c-1", os.path.join(music_root, "c-1.flac"), "First", 1)
            first.update({"composer": "Composer A", "artist": "Performer A", "album": "Album One"})
            second = self._item("c-2", os.path.join(music_root, "c-2.flac"), "Second", 1)
            second.update({"composer": "Composer A", "artist": "Performer A", "album": "Album Two"})
            third = self._item("d-1", os.path.join(music_root, "d-1.flac"), "Other", 1)
            third.update({"composer": "Composer B", "artist": "Performer B", "album": "Album One"})
            save_items_to_sqlite(config, [first, second, third], "test")

            albums = query_library_groups(config, "albums", composer="Composer A")
            self.assertEqual([row["name"] for row in albums], ["Album One", "Album Two"])
            self.assertEqual([row["artist"] for row in albums], ["Performer A", "Performer A"])
            page = query_library_page(config, {"view": "composers", "group": "Composer A", "album": "Album One", "sort": "track_no"})
            self.assertEqual(page["count"], 1)
            self.assertEqual([item["id"] for item in page["items"]], ["c-1"])

    def test_group_search_matches_track_metadata_but_keeps_current_group_shape(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            needle = self._item("needle", os.path.join(music_root, "needle.flac"), "Hidden Needle", 1)
            needle.update({"artist": "Singer A", "album": "Album Alpha", "composer": "Composer A", "genre": "Rock"})
            sibling = self._item("sibling", os.path.join(music_root, "sibling.flac"), "Another Song", 2)
            sibling.update({"artist": "Singer A", "album": "Album Alpha", "composer": "Composer A", "genre": "Rock"})
            other = self._item("other", os.path.join(music_root, "other.flac"), "Different Song", 1)
            other.update({"artist": "Singer B", "album": "Album Beta", "composer": "Composer B", "genre": "Jazz"})
            save_items_to_sqlite(config, [needle, sibling, other], "test")

            albums = query_library_groups(config, "albums", search="hidden needle")
            self.assertEqual([row["name"] for row in albums], ["Album Alpha"])
            self.assertEqual(albums[0]["track_count"], 2)
            self.assertEqual([row["name"] for row in query_library_groups(config, "albums", search="Singer B")], ["Album Beta"])
            self.assertEqual([row["name"] for row in query_library_groups(config, "artists", search="Album Alpha")], ["Singer A"])
            self.assertEqual([row["name"] for row in query_library_groups(config, "composers", search="Hidden Needle")], ["Composer A"])
            self.assertEqual([row["name"] for row in query_library_groups(config, "genres", search="Singer B")], ["Jazz"])

            artist_albums = query_library_groups(config, "albums", search="Hidden Needle", artist="Singer A")
            self.assertEqual([row["name"] for row in artist_albums], ["Album Alpha"])
            self.assertEqual(artist_albums[0]["track_count"], 2)

    def test_folder_search_keeps_root_and_child_hierarchy(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            target_folder = os.path.join(music_root, "Parent", "Child")
            other_folder = os.path.join(music_root, "Other")
            os.makedirs(target_folder)
            os.makedirs(other_folder)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            target = self._item("target", os.path.join(target_folder, "target.flac"), "Search Target", 1)
            target.update({"artist": "Matching Artist", "album": "Matching Album"})
            other = self._item("other", os.path.join(other_folder, "other.flac"), "Unrelated", 1)
            other.update({"artist": "Other Artist", "album": "Other Album"})
            save_items_to_sqlite(config, [target, other], "test")

            roots = query_library_root_folders(config, "Matching Artist")
            self.assertEqual([row["path"] for row in roots], [music_root])
            top = query_library_folders(config, "", music_root, search="Search Target")
            self.assertEqual([row["name"] for row in top], ["Parent"])
            child = query_library_folders(config, "Parent", music_root, search="Matching Album")
            self.assertEqual([row["name"] for row in child], ["Child"])
            empty = query_library_folders(config, "", music_root, search="not present")
            self.assertEqual(empty, [])

    def test_builtin_playlists_honor_shared_library_sorting(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("z-last", os.path.join(music_root, "z.flac"), "Zebra", 2)
            first["added_ns"] = 100
            second = self._item("a-first", os.path.join(music_root, "a.flac"), "Alpha", 1)
            second["added_ns"] = 200
            save_items_to_sqlite(config, [first, second], "test")

            recent_by_title = query_library_page(config, {"view": "recent", "sort": "title", "dir": "asc", "limit": "100", "offset": "0"})
            self.assertEqual([item["id"] for item in recent_by_title["items"]], ["a-first", "z-last"])
            recent_by_added = query_library_page(config, {"view": "recent", "sort": "added", "dir": "desc", "limit": "100", "offset": "0"})
            self.assertEqual([item["id"] for item in recent_by_added["items"]], ["a-first", "z-last"])
            random_by_title = query_library_page(config, {"view": "random100", "sort": "title", "dir": "desc", "limit": "100", "offset": "0"})
            self.assertEqual([item["id"] for item in random_by_title["items"]], ["z-last", "a-first"])

    @staticmethod
    def _item(item_id, path, title, track_no):
        return {
            "id": item_id,
            "path": path,
            "title": title,
            "artist": "Artist",
            "album": "Album",
            "track_no": track_no,
            "format": "FLAC",
            "mime": "audio/flac",
            "duration": 180,
        }


if __name__ == "__main__":
    unittest.main()
