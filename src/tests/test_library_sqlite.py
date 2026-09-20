import os
import io
import json
import shutil
import sys
import contextlib
import tempfile
import unittest
from contextlib import contextmanager
from unittest import mock

sys.path.insert(0, "app/server")

import library
from library import UNCLASSIFIED, group_match_condition, library_db_connect, library_search_index_status, query_library_folders, query_library_groups, query_library_item_location, query_library_items_by_ids, query_library_page, query_library_root_folders, read_metadata, save_items_to_sqlite
from scan_control import ScanCancelled, ScanDeadline, ScanTimedOut, check_scan_deadline
from library_search_index_policy import FTS_MODE, LIKE_MODE, cache_token, search_index_status, uses_fts


class LibraryConnectionPoolingTests(unittest.TestCase):
    """The read path may reuse an idle handle; the write path may never borrow one."""

    POOLED = "library_connection_pool"

    def setUp(self):
        # Cleanup order matters here: an idle handle keeps the index file open on
        # Windows, so the pool has to be drained before the temporary directory
        # is removed. Registered second, it therefore runs first.
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.addCleanup(library.close_library_connections)
        self.music_root = os.path.join(self.root.name, "music")
        os.makedirs(self.music_root, exist_ok=True)

    def _config(self, pooled):
        config = {"cache_dir": os.path.join(self.root.name, "cache"), "library_paths": [self.music_root]}
        if pooled:
            config[self.POOLED] = True
        return config

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

    @staticmethod
    def _status():
        return library.library_connection_pool_status()

    def test_pooling_is_off_by_default_so_one_query_opens_one_handle(self):
        config = self._config(pooled=False)
        save_items_to_sqlite(config, [self._item("one", os.path.join(self.music_root, "one.flac"), "One", 1)], "test")
        before = self._status()
        original_connect = library.library_db_connect
        calls = []

        def counted_connect(current_config):
            calls.append(current_config)
            return original_connect(current_config)

        with mock.patch.object(library, "library_db_connect", side_effect=counted_connect):
            query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
            query_library_page(config, {"view": "all", "limit": "9", "offset": "0"})
        self.assertEqual(len(calls), 2)
        after = self._status()
        # Disabled must mean untouched, not merely unused: the pool counters stay
        # where they were so a regression cannot hide behind a full idle cache.
        self.assertEqual(after["creations"], before["creations"])
        self.assertEqual(after["reuses"], before["reuses"])
        self.assertEqual(after["idle"], 0)

    def test_enabled_pooling_hands_the_next_read_an_idle_handle(self):
        config = self._config(pooled=True)
        save_items_to_sqlite(config, [self._item("one", os.path.join(self.music_root, "one.flac"), "One", 1)], "test")
        before = self._status()
        page = query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        self.assertEqual([item["id"] for item in page["items"]], ["one"])
        first = self._status()
        self.assertEqual(first["creations"], before["creations"] + 1)
        self.assertEqual(first["reuses"], before["reuses"])
        self.assertEqual(first["idle"], 1)
        second_page = query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        self.assertEqual(second_page["items"], page["items"])
        second = self._status()
        self.assertEqual(second["reuses"], first["reuses"] + 1)
        self.assertEqual(second["creations"], first["creations"])
        self.assertEqual(second["idle"], 1)

    def test_a_committed_scan_is_visible_to_the_next_pooled_read(self):
        config = self._config(pooled=True)
        first = self._item("one", os.path.join(self.music_root, "one.flac"), "One", 1)
        save_items_to_sqlite(config, [first], "first")
        query_library_page(config, {"view": "all", "limit": "10", "offset": "1"})
        idle = self._status()
        self.assertEqual(idle["idle"], 1)
        save_items_to_sqlite(
            config,
            [first, self._item("two", os.path.join(self.music_root, "two.flac"), "Two", 2)],
            "second",
        )
        # Forgetting the schema had to discard the idle handle, otherwise this
        # read would answer from a descriptor predating the committed scan.
        after_save = self._status()
        self.assertEqual(after_save["idle"], 0)
        self.assertGreater(after_save["closures"], idle["closures"])
        page = query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        self.assertEqual(sorted(item["id"] for item in page["items"]), ["one", "two"])
        self.assertEqual(self._status()["creations"], after_save["creations"] + 1)

    def test_write_path_never_borrows_a_pooled_handle(self):
        config = self._config(pooled=True)
        first = self._item("one", os.path.join(self.music_root, "one.flac"), "One", 1)
        save_items_to_sqlite(config, [first], "first")
        query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        self.assertEqual(self._status()["idle"], 1)
        options = []
        original_connect = library.sqlite3.connect

        def traced_connect(*args, **kwargs):
            options.append(kwargs)
            return original_connect(*args, **kwargs)

        with mock.patch.object(library.sqlite3, "connect", side_effect=traced_connect):
            save_items_to_sqlite(
                config,
                [first, self._item("two", os.path.join(self.music_root, "two.flac"), "Two", 2)],
                "second",
            )
        # A scan recreates tables inside one long transaction. Cross-thread access
        # is only allowed for handles the pool may hand to another worker.
        self.assertEqual(len(options), 1)
        self.assertNotIn("check_same_thread", options[0])

    def test_a_failed_read_discards_its_handle(self):
        config = self._config(pooled=True)
        save_items_to_sqlite(config, [self._item("one", os.path.join(self.music_root, "one.flac"), "One", 1)], "test")
        query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        before = self._status()
        self.assertEqual(before["idle"], 1)
        with self.assertRaisesRegex(RuntimeError, "reader failed"):
            with library.library_db_connect(config) as conn:
                conn.execute("SELECT 1")
                raise RuntimeError("reader failed")
        self.assertEqual(self._status()["idle"], 0)
        # A different page on purpose: the identical query would be answered by
        # the short-lived page cache and never reach the database at all.
        page = query_library_page(config, {"view": "all", "limit": "9", "offset": "0"})
        self.assertEqual([item["id"] for item in page["items"]], ["one"])
        self.assertEqual(self._status()["creations"], before["creations"] + 1)

    def test_a_patched_connection_cannot_leak_into_the_pool(self):
        config = self._config(pooled=True)
        save_items_to_sqlite(config, [self._item("one", os.path.join(self.music_root, "one.flac"), "One", 1)], "test")
        query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        library.close_library_connections()
        before = self._status()
        connection = mock.Mock()
        with mock.patch.object(library.sqlite3, "connect", return_value=connection), \
             mock.patch.object(library, "secure_directory"), \
             mock.patch.object(library, "secure_sqlite_files"), \
             mock.patch.object(library, "_ensure_library_schema_once"):
            with library.library_db_connect(config):
                pass
        after = self._status()
        self.assertEqual(after["idle"], 0)
        self.assertEqual(after["creations"], before["creations"] + 1)
        connection.close.assert_called_once_with()

    def test_a_failed_read_prologue_still_rolls_back_and_closes(self):
        # The pragma/schema setup belongs to the guarded section: an index that
        # fails to migrate must never leave its handle open or back in the pool.
        for name in ("library_db_connect", "library_db_writer"):
            with self.subTest(connection=name):
                connection = mock.Mock()
                with contextlib.ExitStack() as stack:
                    for target, value in (
                        ("secure_directory", mock.Mock()),
                        ("secure_sqlite_files", mock.Mock()),
                        ("_ensure_library_schema_once", mock.Mock(side_effect=RuntimeError("migration failed"))),
                    ):
                        stack.enter_context(mock.patch.object(library, target, value))
                    stack.enter_context(mock.patch.object(library.sqlite3, "connect", return_value=connection))
                    with self.assertRaisesRegex(RuntimeError, "migration failed"):
                        with getattr(library, name)(self._config(pooled=True)):
                            self.fail("the prologue must run before the body")
                connection.rollback.assert_called_once_with()
                connection.commit.assert_not_called()
                connection.close.assert_called_once_with()
                self.assertEqual(library.library_connection_pool_status()["idle"], 0)

    def test_a_failed_open_does_not_count_a_connection(self):
        config = self._config(pooled=True)
        before = self._status()
        with mock.patch.object(library, "secure_directory"), \
             mock.patch.object(library, "secure_sqlite_files"), \
             mock.patch.object(library.sqlite3, "connect", side_effect=OSError("disk gone")):
            with self.assertRaisesRegex(OSError, "disk gone"):
                with library.library_db_connect(config):
                    self.fail("no handle was opened")
        after = self._status()
        self.assertEqual(after["creations"], before["creations"])
        self.assertEqual(after["idle"], before["idle"])

    def test_a_replaced_index_discards_the_idle_handle(self):
        config = self._config(pooled=True)
        save_items_to_sqlite(config, [self._item("one", os.path.join(self.music_root, "one.flac"), "One", 1)], "first")
        query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        before = self._status()
        self.assertEqual(before["idle"], 1)
        original_identity = library._library_database_identity
        identities = iter([("9", "9")])

        def replaced_identity(path):
            try:
                return next(identities)
            except StopIteration:
                return original_identity(path)

        # An installer swapped the index file underneath the service. The old
        # descriptor belongs to a file nobody is reading any more.
        with mock.patch.object(library, "_library_database_identity", side_effect=replaced_identity):
            save_items_to_sqlite(
                config,
                [self._item("nine", os.path.join(self.music_root, "nine.flac"), "Nine", 9)],
                "replaced",
            )
            library.invalidate_library_query_cache(config)
            page = query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        self.assertEqual([item["id"] for item in page["items"]], ["nine"])
        after = self._status()
        self.assertGreater(after["closures"], before["closures"])
        self.assertGreater(after["creations"], before["creations"])

    def test_stop_library_connections_survives_a_reader_that_finishes_afterwards(self):
        # The shutdown drain has to hold against a reader that was already inside a query
        # when it ran: the HTTP handler comes out of `library_db_connect` later and offers
        # its handle back. `close_library_connections()` would have pooled it again; the
        # shutdown variant refuses it, so the cache directory stays removable. Closing
        # acceptance is one-way for the pool it is called on, so the test runs against a
        # private instance rather than poisoning the process-wide pool for its neighbours.
        config = self._config(pooled=True)
        with mock.patch.object(library, "LIBRARY_CONNECTION_POOL",
                               library.LIBRARY_CONNECTION_POOL.__class__()):
            save_items_to_sqlite(config, [self._item("one", os.path.join(self.music_root, "one.flac"), "One", 1)], "test")
            query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
            self.assertEqual(self._status()["idle"], 1)
            self.assertEqual(library.stop_library_connections(config), 1)
            with library.library_db_connect(config) as connection:
                self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)
            self.assertEqual(self._status()["idle"], 0, "a late reader re-pooled a handle")
        shutil.rmtree(config["cache_dir"])

    def test_disabling_the_pool_drains_the_handles_it_left_behind(self):
        config = self._config(pooled=True)
        save_items_to_sqlite(config, [self._item("one", os.path.join(self.music_root, "one.flac"), "One", 1)], "test")
        query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        self.assertEqual(self._status()["idle"], 1)
        config[self.POOLED] = False
        self.assertEqual(library.apply_library_connection_pool_config(config), 1)
        self.assertEqual(self._status()["idle"], 0)
        # The cache directory has to become removable the moment the switch moves, which
        # is why the drain belongs to the setting instead of to shutdown only.
        shutil.rmtree(config["cache_dir"])

    def test_the_disable_drain_stays_reversible_for_a_later_enable(self):
        # Turning the switch off must not be the one-way `stop_library_connections()`:
        # after switching back on, the very next read borrows again.
        config = self._config(pooled=True)
        save_items_to_sqlite(config, [self._item("one", os.path.join(self.music_root, "one.flac"), "One", 1)], "test")
        query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        config[self.POOLED] = False
        self.assertEqual(library.apply_library_connection_pool_config(config), 1)
        config[self.POOLED] = True
        query_library_page(config, {"view": "all", "limit": "9", "offset": "0"})
        self.assertEqual(self._status()["idle"], 1, "the pool stayed closed after re-enabling")
        before = self._status()["reuses"]
        query_library_page(config, {"view": "all", "limit": "8", "offset": "0"})
        self.assertEqual(self._status()["reuses"], before + 1)

    def test_enabling_the_pool_leaves_idle_handles_alone(self):
        config = self._config(pooled=True)
        save_items_to_sqlite(config, [self._item("one", os.path.join(self.music_root, "one.flac"), "One", 1)], "test")
        query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        before = self._status()
        self.assertEqual(before["idle"], 1)
        self.assertEqual(library.apply_library_connection_pool_config(config), 0)
        after = self._status()
        self.assertEqual(after["idle"], before["idle"])
        self.assertEqual(after["closures"], before["closures"])

    def test_the_drain_scope_follows_the_config_it_was_given(self):
        config = self._config(pooled=True)
        save_items_to_sqlite(config, [self._item("one", os.path.join(self.music_root, "one.flac"), "One", 1)], "test")
        query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        self.assertEqual(self._status()["idle"], 1)
        # A readable config names its own index, so it drains that one database only;
        # an empty one points at a file this test never opened.
        self.assertEqual(library.apply_library_connection_pool_config({}), 0)
        self.assertEqual(self._status()["idle"], 1)
        # Anything that cannot name an index must not leave a handle behind either. The
        # two shapes differ on purpose: a non-dict reaches `library_db_path()` with no
        # cache directory to read, so only an explicit global drain can free the file.
        self.assertEqual(library.apply_library_connection_pool_config([]), 1)
        self.assertEqual(self._status()["idle"], 0)
        # Re-parking needs a page the query cache has never seen: an identical
        # `limit` is served from that cache and opens no connection at all.
        query_library_page(config, {"view": "all", "limit": "9", "offset": "0"})
        self.assertEqual(self._status()["idle"], 1)
        self.assertEqual(library.apply_library_connection_pool_config(None), 1)
        self.assertEqual(self._status()["idle"], 0)

    def test_close_library_connections_releases_the_cache_directory(self):
        config = self._config(pooled=True)
        save_items_to_sqlite(config, [self._item("one", os.path.join(self.music_root, "one.flac"), "One", 1)], "test")
        query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        self.assertEqual(self._status()["idle"], 1)
        self.assertEqual(library.close_library_connections(config), 1)
        self.assertEqual(self._status()["idle"], 0)
        shutil.rmtree(config["cache_dir"])
        page = query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
        self.assertEqual(page["items"], [])


class LibrarySqliteTests(unittest.TestCase):
    def test_library_connection_rolls_back_and_preserves_body_failure(self):
        connection = mock.Mock()
        config = {"cache_dir": "cache"}
        with mock.patch.object(library.sqlite3, "connect", return_value=connection), \
             mock.patch.object(library, "secure_directory"), \
             mock.patch.object(library, "secure_sqlite_files"), \
             mock.patch.object(library, "library_db_path", return_value="library.sqlite3"), \
             mock.patch.object(library, "_ensure_library_schema_once"):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                with library_db_connect(config):
                    raise RuntimeError("write failed")
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        connection.close.assert_called_once_with()

    def test_library_connection_does_not_mask_body_failure_when_rollback_fails(self):
        connection = mock.Mock()
        connection.rollback.side_effect = OSError("rollback failed")
        config = {"cache_dir": "cache"}
        with mock.patch.object(library.sqlite3, "connect", return_value=connection), \
             mock.patch.object(library, "secure_directory"), \
             mock.patch.object(library, "secure_sqlite_files"), \
             mock.patch.object(library, "library_db_path", return_value="library.sqlite3"), \
             mock.patch.object(library, "_ensure_library_schema_once"):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                with library_db_connect(config):
                    raise RuntimeError("write failed")
        connection.rollback.assert_called_once_with()
        connection.close.assert_called_once_with()

    def test_library_connection_does_not_mask_body_failure_when_final_cleanup_fails(self):
        connection = mock.Mock()
        connection.close.side_effect = OSError("close failed")
        config = {"cache_dir": "cache"}
        with mock.patch.object(library.sqlite3, "connect", return_value=connection), \
             mock.patch.object(library, "secure_directory"), \
             mock.patch.object(library, "secure_sqlite_files", side_effect=[None, None, OSError("chmod failed")]), \
             mock.patch.object(library, "library_db_path", return_value="library.sqlite3"), \
             mock.patch.object(library, "_ensure_library_schema_once"):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                with library_db_connect(config):
                    raise RuntimeError("write failed")
        connection.rollback.assert_called_once_with()
        connection.close.assert_called_once_with()

    def test_library_connection_does_not_turn_committed_work_into_cleanup_failure(self):
        connection = mock.Mock()
        config = {"cache_dir": "cache"}
        with mock.patch.object(library.sqlite3, "connect", return_value=connection), \
             mock.patch.object(library, "secure_directory"), \
             mock.patch.object(library, "secure_sqlite_files", side_effect=[None, None, OSError("chmod failed")]), \
             mock.patch.object(library, "library_db_path", return_value="library.sqlite3"), \
             mock.patch.object(library, "_ensure_library_schema_once"):
            with library_db_connect(config):
                pass
        connection.commit.assert_called_once_with()
        connection.close.assert_called_once_with()

    def test_search_index_policy_projects_safe_status_and_threshold(self):
        self.assertEqual(search_index_status(FTS_MODE), {"mode": FTS_MODE, "substring_minimum_chars": 3})
        self.assertEqual(search_index_status(LIKE_MODE), {"mode": LIKE_MODE, "substring_minimum_chars": 0})
        self.assertEqual(search_index_status(object()), {"mode": LIKE_MODE, "substring_minimum_chars": 0})
        self.assertTrue(uses_fts(FTS_MODE, "abc"))
        self.assertFalse(uses_fts(FTS_MODE, "ab"))
        self.assertFalse(uses_fts(LIKE_MODE, "abcdef"))
        self.assertEqual(cache_token(FTS_MODE, "abc"), FTS_MODE)
        self.assertEqual(cache_token(FTS_MODE, "ab"), LIKE_MODE)
        self.assertEqual(cache_token(LIKE_MODE, "abcdef"), LIKE_MODE)

    def test_saved_library_meta_count_is_bounded_and_isolates_broken_rows(self):
        class BrokenRow:
            def __getitem__(self, key):
                raise RuntimeError("broken row")

        class Cursor:
            def __init__(self, row):
                self.row = row

            def fetchone(self):
                return self.row

        class Connection:
            def __init__(self, row):
                self.row = row

            def execute(self, *_args):
                return Cursor(self.row)

        self.assertIsNone(library._saved_library_meta_count(Connection(BrokenRow()), "track_count"))
        self.assertIsNone(library._saved_library_meta_count(Connection({"value": True}), "track_count"))
        self.assertIsNone(library._saved_library_meta_count(Connection({"value": 2_147_483_648}), "track_count"))
        self.assertEqual(library._saved_library_meta_count(Connection({"value": "42"}), "track_count"), 42)

    def test_search_helpers_reject_custom_objects_without_stringification(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify")
        self.assertEqual(library._track_search_condition(Explosive()), ("", []))
        self.assertFalse(library._search_uses_fts({}, Explosive()))
        with self.assertRaises(ValueError):
            library.group_match_condition(Explosive(), "album")

    def test_memory_item_lookup_and_location_reject_untrusted_fields(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify")
        previous = library.MUSIC_CACHE["items"]
        try:
            library.MUSIC_CACHE["items"] = [{"id": Explosive(), "path": Explosive()}]
            self.assertIsNone(library.query_library_item_by_id({"cache_dir": "unused"}, "missing"))
            self.assertIsNone(library.query_library_item_location({"cache_dir": "unused", "library_paths": []}, "missing"))
        finally:
            library.MUSIC_CACHE["items"] = previous

    def test_probe_output_over_limit_uses_native_fallback_without_json_decode(self):
        oversized = b"{" + (b"x" * (library.MAX_PROBE_OUTPUT_BYTES + 1))
        native = {"sample_rate": 44100, "bit_depth": 16, "duration": 1.25}
        completed = mock.Mock(stdout=oversized)
        with mock.patch.object(library, "find_ffprobe", return_value="ffprobe"), \
                mock.patch.object(library.subprocess, "run", return_value=completed) as run, \
                mock.patch.object(library, "read_native_audio_info", return_value=native) as native_reader, \
                mock.patch.object(library.json, "loads", side_effect=AssertionError("oversized probe must not be decoded")) as loads:
            tags, info = library.read_probe_metadata("/tmp/example.flac", {})

        run.assert_called_once()
        native_reader.assert_called_once_with("/tmp/example.flac")
        loads.assert_not_called()
        self.assertEqual(tags, {})
        self.assertEqual(info, native)

    def test_probe_failure_preserves_native_audio_info(self):
        native = {"sample_rate": 48000, "bit_depth": 24, "duration": 2.0}
        with mock.patch.object(library, "find_ffprobe", return_value="ffprobe"), \
                mock.patch.object(library.subprocess, "run", side_effect=RuntimeError("probe failed")), \
                mock.patch.object(library, "read_native_audio_info", return_value=native) as native_reader:
            tags, info = library.read_probe_metadata("/tmp/example.wav", {})

        native_reader.assert_called_once_with("/tmp/example.wav")
        self.assertEqual(tags, {})
        self.assertEqual(info, native)

    def test_scan_control_deadline_and_cancellation_are_independently_testable(self):
        state = {}
        deadline = ScanDeadline(1, state)
        deadline.check_and_touch()
        self.assertIn("deadline", state)
        deadline.expires_at = 0
        with self.assertRaises(ScanTimedOut):
            deadline.check_and_touch()

        class Cancelled:
            @staticmethod
            def is_set():
                return True

        with self.assertRaises(ScanCancelled):
            check_scan_deadline(cancel_event=Cancelled())

    def test_scan_control_rejects_nonfinite_or_overflowing_deadlines(self):
        self.assertEqual(ScanDeadline(10 ** 10000).timeout, 1.0)
        self.assertEqual(ScanDeadline(float("inf")).timeout, 1.0)
        self.assertEqual(ScanDeadline("10").timeout, 10.0)
        check_scan_deadline(10 ** 10000)
        check_scan_deadline(float("nan"))

    def test_sqlite_page_query_uses_one_connection_after_the_cache_miss(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            save_items_to_sqlite(config, [self._item("one", os.path.join(music_root, "one.flac"), "One", 1)], "test")
            original_connect = library.library_db_connect
            calls = []

            def counted_connect(current_config):
                calls.append(current_config)
                return original_connect(current_config)

            with mock.patch.object(library, "library_db_connect", side_effect=counted_connect):
                page = query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
            self.assertEqual([item["id"] for item in page["items"]], ["one"])
            self.assertEqual(len(calls), 1)

    def test_sqlite_library_queries_fingerprint_the_database_once(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            save_items_to_sqlite(config, [self._item("one", os.path.join(music_root, "one.flac"), "One", 1)], "test")
            queries = {
                "tracks": lambda: query_library_page(config, {"view": "all", "limit": "10", "offset": "0"}),
                "groups": lambda: query_library_groups(config, "albums", limit=10, offset=0),
                "folders": lambda: query_library_folders(config, "", music_root, limit=10, offset=0),
                "roots": lambda: query_library_root_folders(config),
                "items_by_id": lambda: query_library_items_by_ids(config, ["one"]),
            }
            original_identity = library._library_database_cache_identity
            fingerprints = []

            def counted_identity(path):
                fingerprints.append(path)
                return original_identity(path)

            for namespace, run in queries.items():
                with self.subTest(namespace=namespace):
                    # A second fingerprint would let the write half of the query
                    # move to a newer key than the rows it actually read.
                    library.invalidate_library_query_cache(config)
                    with mock.patch.object(library, "_library_database_cache_identity", side_effect=counted_identity):
                        before = len(fingerprints)
                        first = run()
                        self.assertEqual(len(fingerprints) - before, 1)
                        before = len(fingerprints)
                        second = run()
                    self.assertEqual(second, first)
                    self.assertEqual(len(fingerprints) - before, 1)

    def test_track_cursor_page_matches_the_following_offset_page(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = [
                self._item("one", os.path.join(music_root, "one.flac"), "Same", 1),
                self._item("two", os.path.join(music_root, "two.flac"), "Same", 2),
                self._item("three", os.path.join(music_root, "three.flac"), "Tail", 3),
            ]
            save_items_to_sqlite(config, items, "cursor-test")
            first = query_library_page(config, {"view": "all", "sort": "title", "dir": "asc", "limit": "2", "offset": "0"})
            self.assertTrue(first.get("next_cursor"))
            cursor_page = query_library_page(config, {
                "view": "all", "sort": "title", "dir": "asc", "limit": "2", "offset": "0",
                "cursor": first["next_cursor"],
            })
            offset_page = query_library_page(config, {"view": "all", "sort": "title", "dir": "asc", "limit": "2", "offset": "2"})
            self.assertEqual([item["id"] for item in cursor_page["items"]], [item["id"] for item in offset_page["items"]])
            self.assertEqual(cursor_page["count"], offset_page["count"])
            self.assertTrue(cursor_page.get("has_more") is False)

    def test_track_cursor_full_final_page_does_not_claim_more_rows(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = [
                self._item("one", os.path.join(music_root, "one.flac"), "One", 1),
                self._item("two", os.path.join(music_root, "two.flac"), "Two", 2),
                self._item("three", os.path.join(music_root, "three.flac"), "Three", 3),
                self._item("four", os.path.join(music_root, "four.flac"), "Four", 4),
            ]
            save_items_to_sqlite(config, items, "cursor-final-page")
            first = query_library_page(config, {"view": "all", "limit": "2", "offset": "0"})
            final = query_library_page(config, {"view": "all", "limit": "2", "offset": "0", "cursor": first["next_cursor"]})
            self.assertEqual([item["id"] for item in final["items"]], ["three", "two"])
            self.assertFalse(final["has_more"])
            self.assertNotIn("next_cursor", final)

    def test_track_cursor_ignores_nonzero_offset_in_client_request(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = [
                self._item("one", os.path.join(music_root, "one.flac"), "A", 1),
                self._item("two", os.path.join(music_root, "two.flac"), "B", 2),
                self._item("three", os.path.join(music_root, "three.flac"), "C", 3),
            ]
            save_items_to_sqlite(config, items, "cursor-offset")
            first = query_library_page(config, {"view": "all", "limit": "1", "offset": "0"})
            cursor_page = query_library_page(config, {
                "view": "all", "limit": "1", "offset": "99", "cursor": first["next_cursor"],
            })
            expected = query_library_page(config, {"view": "all", "limit": "1", "offset": "1"})
            self.assertEqual([item["id"] for item in cursor_page["items"]], [item["id"] for item in expected["items"]])
            self.assertEqual(cursor_page["offset"], 0)

    def test_track_cursor_nonzero_offset_reuses_normalized_query_cache_key(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = [
                self._item("one", os.path.join(music_root, "one.flac"), "A", 1),
                self._item("two", os.path.join(music_root, "two.flac"), "B", 2),
            ]
            save_items_to_sqlite(config, items, "cursor-cache-offset")
            library.invalidate_library_query_cache(config)
            first = query_library_page(config, {"view": "all", "limit": "1", "offset": "0"})
            normalized = query_library_page(config, {
                "view": "all", "limit": "1", "offset": "0", "cursor": first["next_cursor"],
            })
            status_before = library.library_query_cache_status()
            equivalent = query_library_page(config, {
                "view": "all", "limit": "1", "offset": "99", "cursor": first["next_cursor"],
            })
            status_after = library.library_query_cache_status()
            self.assertEqual(equivalent, normalized)
            self.assertGreater(status_after["hits"], status_before["hits"])

    def test_track_cursor_keeps_non_title_sort_tie_break_stable(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = [
                self._item("b", os.path.join(music_root, "b.flac"), "B", 1),
                self._item("a", os.path.join(music_root, "a.flac"), "A", 1),
                self._item("c", os.path.join(music_root, "c.flac"), "C", 2),
            ]
            save_items_to_sqlite(config, items, "cursor-track-no")
            first = query_library_page(config, {"view": "all", "sort": "track_no", "dir": "asc", "limit": "1", "offset": "0"})
            cursor_page = query_library_page(config, {
                "view": "all", "sort": "track_no", "dir": "asc", "limit": "1", "offset": "0",
                "cursor": first["next_cursor"],
            })
            offset_page = query_library_page(config, {"view": "all", "sort": "track_no", "dir": "asc", "limit": "1", "offset": "1"})
            self.assertEqual([item["id"] for item in cursor_page["items"]], [item["id"] for item in offset_page["items"]])

    def _walk_by_cursor(self, config, page_size, sort_key, sort_dir):
        ids = []
        token = ""
        for _ in range(24):
            params = {
                "view": "all", "sort": sort_key, "dir": sort_dir,
                "limit": str(page_size), "offset": "0",
            }
            if token:
                params["cursor"] = token
            page = query_library_page(config, params)
            batch = [item["id"] for item in page["items"]]
            ids.extend(batch)
            token = page.get("next_cursor") or ""
            if not batch or not token or not page.get("has_more"):
                return ids
        return ids

    def _walk_by_offset(self, config, page_size, sort_key, sort_dir):
        ids = []
        offset = 0
        for _ in range(24):
            page = query_library_page(config, {
                "view": "all", "sort": sort_key, "dir": sort_dir,
                "limit": str(page_size), "offset": str(offset),
            })
            batch = [item["id"] for item in page["items"]]
            if not batch:
                return ids
            ids.extend(batch)
            offset += len(batch)
        return ids

    def test_cursor_walk_matches_offset_walk_inside_one_huge_key_group(self):
        # Every item shares the same artist, album, and format, so each of those
        # sorts has a single key group holding the whole library: continuation
        # then depends entirely on skipping rows inside the group the cursor
        # landed in, which is where a keyset range stops being able to express
        # the position on its own.
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            titles = ["Same", "Same", "Same", "Same", "A", "a", "Z", "z", "M", "M", "0", "Å"]
            items = [
                self._item("tie-%02d" % index, os.path.join(music_root, "tie-%02d.flac" % index), title, index)
                for index, title in enumerate(titles)
            ]
            save_items_to_sqlite(config, items, "tie-group-cursor")
            library.invalidate_library_query_cache(config)
            for sort_key in ("artist", "album", "format", "title", "track_no"):
                for sort_dir in ("asc", "desc"):
                    for page_size in ("1", "3", "4"):
                        with self.subTest(sort=sort_key, dir=sort_dir, limit=page_size):
                            cursor_ids = self._walk_by_cursor(config, page_size, sort_key, sort_dir)
                            offset_ids = self._walk_by_offset(config, page_size, sort_key, sort_dir)
                            self.assertEqual(len(offset_ids), len(titles))
                            self.assertEqual(cursor_ids, offset_ids)
                            self.assertEqual(len(set(cursor_ids)), len(cursor_ids))
                        library.invalidate_library_query_cache(config)

    def test_cursor_walk_continues_through_an_untagged_key_group(self):
        # A file with no tags is indexed with "" for artist, album, and format, so
        # the empty key is one of the largest groups a real library has. While an
        # empty primary could not be encoded, every page ending inside that group
        # answered has_more with no next_cursor and this walk stopped early instead
        # of matching the offset walk.
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index, title in enumerate(("Zeta", "alpha", "Middle")):
                items.append(self._item("tagged-%02d" % index, os.path.join(music_root, "tagged-%02d.flac" % index), title, index + 1))
            for index, title in enumerate(("noot", "Three")):
                item = self._item("plain-%02d" % index, os.path.join(music_root, "plain-%02d.mp3" % index), title, index + 4)
                for key in ("artist", "album", "format"):
                    item[key] = ""
                items.append(item)
            save_items_to_sqlite(config, items, "untagged-cursor")
            with library.library_db_connect(config) as conn:
                empty_artists = conn.execute("SELECT COUNT(*) FROM tracks WHERE artist=''" ).fetchone()[0]
            self.assertEqual(empty_artists, 2)
            for sort_key in ("artist", "album", "format", "title", "track_no"):
                for sort_dir in ("asc", "desc"):
                    for page_size in ("1", "2", "3"):
                        with self.subTest(sort=sort_key, dir=sort_dir, limit=page_size):
                            cursor_ids = self._walk_by_cursor(config, page_size, sort_key, sort_dir)
                            offset_ids = self._walk_by_offset(config, page_size, sort_key, sort_dir)
                            self.assertEqual(len(offset_ids), len(items))
                            self.assertEqual(cursor_ids, offset_ids)
                            self.assertEqual(len(set(cursor_ids)), len(cursor_ids))
                        library.invalidate_library_query_cache(config)

    def _null_key_library(self, root, tag, artists, titles=None):
        """Index whose label columns hold SQL NULL, the shape a library written
        before the TODO.md:153 write-path collapse still has on disk.

        ``save_items_to_sqlite`` now refuses to store NULL in a label column and
        converges the legacy rows, so the NULL is injected underneath it with raw
        SQL: these tests are about what the read path does with such a row, never
        about how it got there.  The injection reaches only the columns, so the
        stored ``item_json`` keeps spelling the value "" - the column/payload split
        is exactly what a legacy row looks like between the one-time column repair
        and the payload self-heal, and no assertion here depends on the JSON.
        """
        music_root = os.path.join(root, "music")
        os.makedirs(music_root)
        config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
        items = []
        for index, artist in enumerate(artists):
            title = titles[index] if titles else "Track %d" % index
            item = self._item("%s-%02d" % (tag, index), os.path.join(music_root, "%s-%02d.flac" % (tag, index)), title, index + 1)
            item["artist"] = artist
            items.append(item)
        save_items_to_sqlite(config, items, tag)
        with library.library_db_writer(config) as conn:
            for index, item in enumerate(items):
                for column, supplied in (("artist", artists), ("title", titles or ())):
                    if index < len(supplied) and supplied[index] is None:
                        conn.execute("UPDATE tracks SET %s = NULL WHERE id = ?" % column, (item["id"],))
        library.invalidate_library_query_cache(config)
        return config, items

    def test_cursor_walk_continues_through_a_null_key_group(self):
        # artist, album, and format are nullable columns and the legacy migration
        # adds them to old rows without a default, so a real database can hold SQL
        # NULL. NULL satisfies no comparison predicate: the page that ended on such
        # a row used to answer has_more with no cursor at all, and the walk below
        # stopped on it instead of matching the offset walk.
        with tempfile.TemporaryDirectory() as root:
            config, items = self._null_key_library(root, "nullk", (None, "", "Zeta", "Adele"))
            with library.library_db_connect(config) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM tracks WHERE artist IS NULL").fetchone()[0], 1)
            for page_size in ("1", "2", "3"):
                with self.subTest(limit=page_size):
                    cursor_ids = self._walk_by_cursor(config, page_size, "artist", "asc")
                    offset_ids = self._walk_by_offset(config, page_size, "artist", "asc")
                    self.assertEqual(len(offset_ids), len(items))
                    self.assertEqual(cursor_ids, offset_ids)
                    self.assertEqual(len(set(cursor_ids)), len(cursor_ids))
                library.invalidate_library_query_cache(config)

    def test_cursor_walk_continues_through_a_null_title_inside_a_group(self):
        # A NULL title inside a tagged artist group is the shape that reaches the
        # substitution through a keyset page rather than only the first one: the
        # cursor page opens on the NULL row, and the row after it can name the
        # position, so the page anchors there inclusively.
        with tempfile.TemporaryDirectory() as root:
            config, items = self._null_key_library(
                root, "nullt", ("Aardvark", "Adele", "Adele", "Adele"),
                titles=("First", None, "Bravo", "Cobalt"),
            )
            for page_size in ("1", "2", "3"):
                with self.subTest(limit=page_size):
                    cursor_ids = self._walk_by_cursor(config, page_size, "artist", "asc")
                    offset_ids = self._walk_by_offset(config, page_size, "artist", "asc")
                    self.assertEqual(len(offset_ids), len(items))
                    self.assertEqual(cursor_ids, offset_ids)
                    self.assertEqual(len(set(cursor_ids)), len(cursor_ids))
                library.invalidate_library_query_cache(config)

    def test_cursor_walk_never_skips_the_rest_of_a_null_key_group(self):
        # The look-ahead substitution is only safe where the NULL block ends. With
        # two NULL rows and a page that stops on the first of them, the row after it
        # is NULL too, so the page keeps the old answer - has_more without a cursor
        # and a client that finishes the walk on OFFSET - rather than jumping over
        # the second NULL row. That residual is recorded in the closed TODO entry.
        with tempfile.TemporaryDirectory() as root:
            config, items = self._null_key_library(root, "nullrun", (None, None, "Adele", "Zeta"))
            first = query_library_page(config, {"view": "all", "sort": "artist", "dir": "asc", "limit": "1", "offset": "0"})
            self.assertEqual([item["id"] for item in first["items"]], ["nullrun-00"])
            self.assertTrue(first["has_more"])
            self.assertNotIn("next_cursor", first)
            cursor_ids = self._walk_by_cursor(config, "1", "artist", "asc")
            offset_ids = self._walk_by_offset(config, "1", "artist", "asc")
            self.assertEqual(offset_ids, [item["id"] for item in items])
            self.assertEqual(offset_ids[:len(cursor_ids)], cursor_ids)

    def test_a_descending_cursor_walk_stops_short_of_a_trailing_null_group(self):
        # Pinned so the remaining gap cannot be mistaken for a fixed one: NULL sorts
        # last in a descending page order, so the group before it hands out an
        # ordinary cursor that no predicate can extend onto the NULL rows, and the
        # walk ends with an empty page that reports has_more False. The rows are not
        # lost to a client that also reads the total, but they are not reachable by
        # cursor, which is the opposite direction from the ascending case above.
        with tempfile.TemporaryDirectory() as root:
            config, items = self._null_key_library(root, "nulldesc", (None, "", "Zeta", "Adele"))
            cursor_ids = self._walk_by_cursor(config, "1", "artist", "desc")
            offset_ids = self._walk_by_offset(config, "1", "artist", "desc")
            self.assertEqual(offset_ids[-1], "nulldesc-00")
            self.assertEqual(cursor_ids, offset_ids[:-1])
            library.invalidate_library_query_cache(config)
            last = query_library_page(config, {
                "view": "all", "sort": "artist", "dir": "desc", "limit": "1", "offset": "0",
                "cursor": self._tail_cursor(config, "nulldesc-01"),
            })
            self.assertEqual(last["items"], [])
            self.assertNotIn("next_cursor", last)
            self.assertNotIn("has_more", last)

    def test_a_legacy_index_loses_its_null_labels_on_the_next_save(self):
        # The write-path collapse in prepare_track_persistence only covers rows the
        # scanner rewrites.  This is the row it cannot reach: the stored item_json
        # already spells the tag "", so the upsert's ``WHERE tracks.item_json <>
        # excluded.item_json`` guard skips it and its legacy NULL column would outlive
        # every later scan.  Only the migration clears it.
        with tempfile.TemporaryDirectory() as root:
            config, items = self._null_key_library(root, "legacy", ("", "", "Zeta"))
            with library.library_db_writer(config) as conn:
                # Back the index up to the state a pre-collapse build leaves behind:
                # one NULL column and no migration marker.
                conn.execute("UPDATE tracks SET artist = NULL WHERE id = ?", (items[0]["id"],))
                conn.execute(
                    "DELETE FROM library_meta WHERE key = ?", (library.NULL_LABEL_COLLAPSE_KEY,)
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM tracks WHERE artist IS NULL").fetchone()[0], 1
                )
            library.invalidate_library_query_cache(config)
            save_items_to_sqlite(config, items, "legacy")
            with library.library_db_connect(config) as conn:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM tracks WHERE artist IS NULL").fetchone()[0], 0
                )
                self.assertIsNotNone(conn.execute(
                    "SELECT value FROM library_meta WHERE key = ?", (library.NULL_LABEL_COLLAPSE_KEY,)
                ).fetchone())
            # The browsable answer is unchanged by the repair: "" and NULL were both
            # already the UNCLASSIFIED group, so nothing moved between pages.
            page = query_library_page(config, {"view": "all", "sort": "artist", "dir": "asc", "limit": "3"})
            self.assertEqual([item["id"] for item in page["items"]], [items[0]["id"], items[1]["id"], items[2]["id"]])

    def test_the_null_label_collapse_is_a_one_time_migration_not_a_sweep(self):
        # Pinning the other half of the ruling: with the marker stored the UPDATE is
        # never issued again.  A sweep would quietly undo any future writer that
        # reintroduced NULL, and this test is what would fail if someone made the
        # migration run per save to "fix" a report about a legacy index.
        with tempfile.TemporaryDirectory() as root:
            config, items = self._null_key_library(root, "onetime", ("", "Zeta", "Adele"))
            with library.library_db_writer(config) as conn:
                self.assertIsNotNone(conn.execute(
                    "SELECT value FROM library_meta WHERE key = ?", (library.NULL_LABEL_COLLAPSE_KEY,)
                ).fetchone())
                conn.execute("UPDATE tracks SET artist = NULL WHERE id = ?", (items[0]["id"],))
            library.invalidate_library_query_cache(config)
            save_items_to_sqlite(config, items, "onetime")
            with library.library_db_connect(config) as conn:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM tracks WHERE artist IS NULL").fetchone()[0], 1
                )

    def _tail_cursor(self, config, item_id):
        page = query_library_page(config, {"view": "all", "sort": "artist", "dir": "desc", "limit": "3", "offset": "0"})
        library.invalidate_library_query_cache(config)
        self.assertEqual([item["id"] for item in page["items"]][-1], item_id)
        return page["next_cursor"]

    def test_cursor_page_reads_two_ranges_without_counting_the_group(self):
        # A continuation is the group tail plus the groups that follow it. Counting
        # the visited rows and then letting OFFSET walk them again was the previous
        # shape, and it paid the group prefix twice, so this asserts the statement
        # mix rather than a duration: two bounded reads, no OFFSET, no COUNT over
        # the tracks table.
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index in range(6):
                item = self._item("seek-%d" % index, os.path.join(music_root, "seek-%d.flac" % index), "T%d" % index, index + 1)
                item["artist"] = "Alpha" if index < 3 else "Beta"
                items.append(item)
            save_items_to_sqlite(config, items, "seek-shape")
            first = query_library_page(config, {"view": "all", "sort": "artist", "dir": "asc", "limit": "2", "offset": "0"})
            self.assertEqual([item["id"] for item in first["items"]], ["seek-0", "seek-1"])
            statements = []
            original_connect = library.library_db_connect

            class TracingConnection:
                def __init__(self, inner):
                    self.inner = inner
                    self.connection = None

                def __enter__(self):
                    self.connection = self.inner.__enter__()
                    return self

                def __exit__(self, *exc):
                    return self.inner.__exit__(*exc)

                def execute(self, sql, parameters=()):
                    statements.append((" ".join(sql.split()), list(parameters or ())))
                    return self.connection.execute(sql, parameters)

            def tracing_connect(current_config):
                return TracingConnection(original_connect(current_config))

            library.library_db_connect = tracing_connect
            try:
                page = query_library_page(config, {
                    "view": "all", "sort": "artist", "dir": "asc", "limit": "2", "offset": "0",
                    "cursor": first["next_cursor"],
                })
            finally:
                library.library_db_connect = original_connect
            # seek-2 is the tail of the cursor group and seek-3 the first row of the
            # group after it, so a single statement could not have produced this.
            self.assertEqual([item["id"] for item in page["items"]], ["seek-2", "seek-3"])
            reads = [entry for entry in statements if entry[0].startswith("SELECT item_json")]
            self.assertEqual([statement for statement, _ in reads], [
                "SELECT item_json, (artist COLLATE NOCASE) AS _cursor_primary,"
                " title AS _cursor_title, id AS _cursor_id FROM tracks"
                " WHERE artist COLLATE NOCASE = ? AND (title COLLATE NOCASE, id) > (?, ?)"
                " ORDER BY artist COLLATE NOCASE ASC, title COLLATE NOCASE ASC, id ASC LIMIT ?",
                "SELECT item_json, (artist COLLATE NOCASE) AS _cursor_primary,"
                " title AS _cursor_title, id AS _cursor_id FROM tracks"
                " WHERE artist COLLATE NOCASE > ?"
                " ORDER BY artist COLLATE NOCASE ASC, title COLLATE NOCASE ASC, id ASC LIMIT ?",
            ])
            for statement, _ in reads:
                self.assertNotIn("OFFSET", statement, statement)
            # The second read only asks for what the first one could not fill, so a
            # continuation never materialises more than one page plus the look-ahead.
            self.assertEqual([parameters[-1] for _, parameters in reads], [3, 2])
            self.assertEqual([parameters[:-1] for _, parameters in reads], [["Alpha", "T1", "seek-1"], ["Alpha"]])
            self.assertFalse([statement for statement, _ in statements if statement.startswith("SELECT COUNT(*) FROM tracks")], statements)

    def test_group_cursor_matches_following_offset_page_and_preserves_total(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = [
                self._item("a", os.path.join(music_root, "a.flac"), "A", 1),
                self._item("b", os.path.join(music_root, "b.flac"), "B", 2),
                self._item("c", os.path.join(music_root, "c.flac"), "C", 3),
                self._item("d", os.path.join(music_root, "d.flac"), "D", 4),
                self._item("e", os.path.join(music_root, "e.flac"), "E", 5),
                self._item("f", os.path.join(music_root, "f.flac"), "F", 6),
            ]
            for item, album in zip(items, ("Album A", "Album B", "Album C", "Album D", "Album E", "Album F")):
                item["album"] = album
            save_items_to_sqlite(config, items, "group-cursor")
            first = query_library_groups(config, "albums", limit=2, offset=0)
            cursor_page = query_library_groups(config, "albums", limit=2, offset=0, cursor=first["next_cursor"])
            offset_page = query_library_groups(config, "albums", limit=2, offset=2)
            self.assertEqual([row["name"] for row in cursor_page["groups"]], [row["name"] for row in offset_page["groups"]])
            self.assertEqual(cursor_page["count"], offset_page["count"])
            self.assertTrue(cursor_page.get("has_more"))
            final_page = query_library_groups(config, "albums", limit=2, offset=0, cursor=cursor_page["next_cursor"])
            self.assertEqual([row["name"] for row in final_page["groups"]], ["Album E", "Album F"])
            self.assertFalse(final_page.get("has_more"))

    def test_group_cursor_ignores_nonzero_offset_in_client_request(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index, album in enumerate(("Album A", "Album B", "Album C"), 1):
                item = self._item(str(index), os.path.join(music_root, "%s.flac" % index), album, index)
                items.append(item)
            save_items_to_sqlite(config, items, "group-cursor-offset")
            first = query_library_groups(config, "albums", limit=1, offset=0)
            cursor_page = query_library_groups(config, "albums", limit=1, offset=99, cursor=first["next_cursor"])
            expected = query_library_groups(config, "albums", limit=1, offset=1)
            self.assertEqual([row["name"] for row in cursor_page["groups"]], [row["name"] for row in expected["groups"]])
            self.assertEqual(cursor_page["offset"], 0)

    def test_group_cursor_is_stable_for_names_differing_only_by_case(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = [
                self._item("upper", os.path.join(music_root, "upper.flac"), "Upper", 1),
                self._item("lower", os.path.join(music_root, "lower.flac"), "Lower", 2),
            ]
            items[0]["album"] = "Album"
            items[1]["album"] = "album"
            save_items_to_sqlite(config, items, "group-case-cursor")

            first = query_library_groups(config, "albums", limit=1, offset=0)
            cursor_page = query_library_groups(
                config, "albums", limit=1, offset=0, cursor=first["next_cursor"]
            )
            offset_page = query_library_groups(config, "albums", limit=1, offset=1)

            self.assertEqual([row["name"] for row in cursor_page["groups"]],
                             [row["name"] for row in offset_page["groups"]])
            self.assertFalse(cursor_page.get("has_more"))

    class _StubResult:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

    class _StubConnection:
        """Answer each statement with a fixed row count and record what was asked."""

        def __init__(self, sizes):
            self.sizes = list(sizes)
            self.limits = []
            self.predicates = []

        def execute(self, statement, args):
            self.limits.append(args[-1])
            where = statement.rindex(" WHERE ") + len(" WHERE ")
            self.predicates.append(statement[where:statement.index(" ORDER BY ")])
            rows = [("row",) for _ in range(self.sizes.pop(0))]
            return LibrarySqliteTests._StubResult(rows)

    def test_browse_cursor_pair_shares_one_page_budget(self):
        # The two statements read one page together, so the second may only ask for
        # what the first left over. Running both with a full limit would return more
        # than a page, which the caller then truncates, hiding the wasted traversal.
        cursor = {"kind": "group", "sort_dir": "asc", "name": "Album", "tie": "Album"}
        arguments = (
            "SELECT * FROM albums", " WHERE ", "name COLLATE NOCASE ASC, name ASC", [],
            cursor, "group", "asc", "name COLLATE NOCASE", "name",
        )
        connection = self._StubConnection([3])
        rows = library._browse_cursor_rows(connection, *arguments, 2)
        self.assertEqual(len(rows), 3)
        self.assertEqual(connection.limits, [3])
        self.assertEqual(connection.predicates, ["name COLLATE NOCASE = ? AND name > ?"])

        connection = self._StubConnection([1, 2])
        rows = library._browse_cursor_rows(connection, *arguments, 2)
        self.assertEqual(len(rows), 3)
        self.assertEqual(connection.limits, [3, 2])
        self.assertEqual(
            connection.predicates,
            ["name COLLATE NOCASE = ? AND name > ?", "name COLLATE NOCASE > ?"],
        )

        # A tail that comes back empty has to leave the whole budget to the range
        # statement, and the range flips its operator with the sort direction while
        # the tail keeps its ascending tie-break in both directions.
        descending = dict(cursor, sort_dir="desc")
        connection = self._StubConnection([0, 3])
        library._browse_cursor_rows(
            connection, "SELECT * FROM albums", " WHERE ",
            "name COLLATE NOCASE DESC, name ASC", [], descending, "group", "desc",
            "name COLLATE NOCASE", "name", 2,
        )
        self.assertEqual(connection.limits, [3, 3])
        self.assertEqual(
            connection.predicates,
            ["name COLLATE NOCASE = ? AND name > ?", "name COLLATE NOCASE < ?"],
        )

    def test_group_cursor_continuation_reads_two_single_comparison_selects(self):
        # A continuation used to be one OR of two comparisons. SQLite cannot seek
        # on that shape, so it re-read every group that sat before the cursor. The
        # pair below stays single-comparison, and each statement is bounded by
        # limit + 1 so no page materialises the whole table.
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index, album in enumerate(("Album A", "album a", "Album B", "Album C", "Album D"), 1):
                item = self._item(str(index), os.path.join(music_root, "%s.flac" % index), album, index)
                item["album"] = album
                items.append(item)
            save_items_to_sqlite(config, items, "group-cursor-shape")
            first = query_library_groups(config, "albums", limit=2, offset=0)
            self.assertEqual([row["name"] for row in first["groups"]], ["Album A", "album a"])
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                cursor_page = query_library_groups(
                    config, "albums", limit=2, offset=0, cursor=first["next_cursor"]
                )
            pages = [line for line in statements if line.startswith("SELECT * FROM (SELECT * FROM albums)")]
            self.assertEqual(len(pages), 2, "; ".join(pages))
            self.assertTrue(all(" OR " not in line for line in pages), "; ".join(pages))
            self.assertTrue(all(line.endswith(" LIMIT 3") for line in pages), "; ".join(pages))
            tail, following = pages
            self.assertIn("name COLLATE NOCASE = 'album a' AND name > 'album a'", tail)
            self.assertIn("WHERE name COLLATE NOCASE > 'album a' ORDER BY", following)
            self.assertEqual([row["name"] for row in cursor_page["groups"]], ["Album B", "Album C"])
            self.assertEqual(cursor_page["count"], 5)

    def test_folder_cursor_continuation_reads_two_single_comparison_selects(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index, name in enumerate(("Alpha", "alpha", "Beta", "Gamma"), 1):
                folder = os.path.join(music_root, name)
                os.makedirs(folder, exist_ok=True)
                items.append(self._item(str(index), os.path.join(folder, "s.flac"), "S", index))
            save_items_to_sqlite(config, items, "folder-cursor-shape")
            first = query_library_folders(config, "", music_root, limit=2, offset=0)
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                cursor_page = query_library_folders(
                    config, "", music_root, "asc", 2, 0, "", first["next_cursor"]
                )
            pages = [line for line in statements if line.startswith("SELECT f.* FROM folders f WHERE")]
            self.assertEqual(len(pages), 2, "; ".join(pages))
            self.assertTrue(all(" OR " not in line for line in pages), "; ".join(pages))
            self.assertTrue(all(line.endswith(" LIMIT 3") for line in pages), "; ".join(pages))
            offset_page = query_library_folders(config, "", music_root, "asc", 2, 2)
            self.assertEqual(
                [row["path"] for row in cursor_page["folders"]],
                [row["path"] for row in offset_page["folders"]],
            )

    def test_group_cursor_walk_returns_every_group_once_across_a_case_cluster(self):
        # The page boundary lands inside the GRP/Grp/grp cluster, so only the
        # group-tail statement can reach the rest of it. A tail that loses its
        # tie-break, or that repeats the cursor row, shows up here as a missing or
        # duplicated group name.
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            albums = ("Album", "beta", "BETA", "GRP", "Grp", "grp", "sigma", "Zeta")
            items = []
            for index, album in enumerate(albums, 1):
                item = self._item(str(index), os.path.join(music_root, "%s.flac" % index), album, index)
                item["album"] = album
                items.append(item)
            save_items_to_sqlite(config, items, "group-cursor-walk")
            expected = [row["name"] for row in query_library_groups(config, "albums")]
            self.assertEqual(len(expected), len(albums))
            walked = []
            token = ""
            for _ in range(len(albums) + 2):
                page = query_library_groups(config, "albums", limit=2, offset=0, cursor=token)
                walked.extend(row["name"] for row in page["groups"])
                token = page.get("next_cursor") or ""
                if not page.get("has_more"):
                    break
            self.assertEqual(walked, ["Album", "BETA", "beta", "GRP", "Grp", "grp", "sigma", "Zeta"])

    def test_browse_cursor_continuations_keep_their_index_seek_plan(self):
        # 谓词形状、页预算和结果都由上面的游标用例钉住了，这里钉的是 SQLite 真正选了什么。
        # R116 取证结论：条目里"组表没有任何 name 排序索引、folders 只有二进制排序的
        # (root,parent,name)"这个前提已经过期，六条表达式索引都在 ensure_library_schema()
        # 里；100000 组 / 50000 同级目录实测续页两条语句 0.012~0.127ms 且零 temp b-tree，
        # 摘掉这六条索引后同一批语句退化为 2.6~150.2ms 并回到 USE TEMP B-TREE FOR ORDER BY。
        # 所以判别点必须落在计划上：摘索引、把表达式索引写成裸列（二进制排序，正是条目
        # 原来描述的那个形状）、或者把两条单比较谓词退回 OR，都在这里当场变红。
        index_prefixes = {
            "albums": "idx_albums_name_nocase",
            "artists": "idx_artists_name_nocase",
            "composers": "idx_composers_name_nocase",
            "genres": "idx_genres_name_nocase",
        }
        rows = (
            ("Album A", "Artist A", "Composer A", "Genre A"),
            ("album a", "artist a", "composer a", "genre a"),
            ("Album B", "Artist B", "Composer B", "Genre B"),
            ("Album C", "Artist C", "Composer C", "Genre C"),
            ("Album D", "Artist D", "Composer D", "Genre D"),
        )
        original_connect = library.library_db_connect

        def traced(statements):
            @contextmanager
            def connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection
            return connect

        def seek_statements(sql_list, index_prefix):
            with library_db_connect(config) as connection:
                for sql in sql_list:
                    with self.subTest(index=index_prefix, sql=sql[:64]):
                        plan = [row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + sql)]
                        self.assertFalse(
                            any("TEMP B-TREE" in detail for detail in plan),
                            "%s -> %s" % (sql[:120], " / ".join(plan)),
                        )
                        self.assertTrue(
                            any(index_prefix in detail for detail in plan),
                            "%s -> %s" % (sql[:120], " / ".join(plan)),
                        )

        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index, (album, artist, composer, genre) in enumerate(rows, 1):
                folder = os.path.join(music_root, album)
                os.makedirs(folder, exist_ok=True)
                item = self._item(str(index), os.path.join(folder, "s.flac"), album, index)
                item["album"], item["artist"] = album, artist
                item["composer"], item["genre"] = composer, genre
                items.append(item)
                # 同一个目录下再挂几个子目录：parent-only 浏览要的就是这一层。
                for offset, sub in enumerate(("Sub 1", "sub 1", "Sub 2", "Sub 3"), 1):
                    child = os.path.join(folder, sub)
                    os.makedirs(child, exist_ok=True)
                    sub_item = self._item(
                        "%d-%d" % (index, offset), os.path.join(child, "t.flac"),
                        "Track %d-%d" % (index, offset), offset + 1,
                    )
                    sub_item["album"], sub_item["artist"] = album, artist
                    sub_item["composer"], sub_item["genre"] = composer, genre
                    items.append(sub_item)
            save_items_to_sqlite(config, items, "browse-cursor-plan")
            for view, index_prefix in index_prefixes.items():
                for sort_dir in ("asc", "desc"):
                    with self.subTest(view=view, sort_dir=sort_dir):
                        first = query_library_groups(config, view, limit=2, offset=0, sort_dir=sort_dir)
                        self.assertTrue(first.get("next_cursor"), first)
                        statements = []
                        with mock.patch.object(library, "library_db_connect", side_effect=traced(statements)):
                            page = query_library_groups(
                                config, view, limit=2, offset=0, sort_dir=sort_dir,
                                cursor=first["next_cursor"],
                            )
                        continuations = [
                            line for line in statements
                            if line.startswith("SELECT * FROM (SELECT * FROM %s) grouped WHERE" % view)
                        ]
                        self.assertEqual(len(continuations), 2, "; ".join(statements))
                        seek_statements(continuations, index_prefix)
                        self.assertTrue(page["groups"], page)
            for sort_dir in ("asc", "desc"):
                with self.subTest(browse="folders-rooted", sort_dir=sort_dir):
                    first = query_library_folders(config, "", music_root, sort_dir, 2, 0)
                    self.assertTrue(first.get("next_cursor"), first)
                    statements = []
                    with mock.patch.object(library, "library_db_connect", side_effect=traced(statements)):
                        page = query_library_folders(
                            config, "", music_root, sort_dir, 2, 0, "", first["next_cursor"]
                        )
                    continuations = [
                        line for line in statements
                        if line.startswith("SELECT f.* FROM folders f WHERE f.root =")
                    ]
                    self.assertEqual(len(continuations), 2, "; ".join(statements))
                    seek_statements(continuations, "idx_folders_root_parent_name_nocase")
                    self.assertTrue(page["folders"], page)
                # 目录浏览也能带着空 root 到达：UI 只在真的选中根目录时才带这个参数，
                # 那条路径靠的是另一对 (parent, name COLLATE NOCASE, path) 索引。
                with self.subTest(browse="folders-parent-only", sort_dir=sort_dir):
                    # folders 里的 parent/path 存的是相对根的路径，所以这里传的是
                    # "Album A"——去掉 root 之后只剩 f.parent = ? 一个条件。
                    first = query_library_folders(config, "Album A", "", sort_dir, 2, 0)
                    self.assertTrue(first.get("next_cursor"), first)
                    statements = []
                    with mock.patch.object(library, "library_db_connect", side_effect=traced(statements)):
                        page = query_library_folders(
                            config, "Album A", "", sort_dir, 2, 0, "", first["next_cursor"]
                        )
                    continuations = [
                        line for line in statements
                        if line.startswith("SELECT f.* FROM folders f WHERE f.parent =")
                    ]
                    self.assertEqual(len(continuations), 2, "; ".join(statements))
                    seek_statements(continuations, "idx_folders_parent_name_nocase")
                    self.assertTrue(page["folders"], page)

    def test_every_group_ordering_index_is_named_by_a_real_browse_path(self):
        # R117 关闭 TODO L130：SQLite 从不报告「哪条索引没被用过」，所以八条组表排序
        # 索引是否还活着，只能逐方向把它们归属回真实代码路径的 EXPLAIN QUERY PLAN。
        # 本轮取证的归属矩阵（四张组表同形，albums 为例）：
        #   首屏/翻页（未过滤页与它的三种计数变体共用同一条 page_sql）
        #       ORDER BY name COLLATE NOCASE ASC  -> idx_albums_name_nocase_asc
        #       ORDER BY name COLLATE NOCASE DESC -> idx_albums_name_nocase_desc
        #   游标续页第一条（组内尾，谓词 name = ? AND tie > ?，故意与 sort_dir 无关）
        #       asc 与 desc 两个方向都落在 _desc：次键 name ASC 与浏览方向无关
        #   游标续页第二条（后续组范围，name COLLATE NOCASE > / < ?）
        #       asc -> _asc，desc -> _desc
        # 另两条路径不在这八条的归属表里，这里也一并钉住：searched 页用主键
        # autoindex 点查组表，owner-filtered albums 干脆不碰组表，两者的 ORDER BY 都在
        # 匹配集上做 TEMP B-TREE，规模由命中数而不是曲库规模决定。少了这两条断言，
        # 下一轮很容易误以为「带搜索的页也靠这八条」而把 _asc 当成冗余删掉。
        # 摘掉任意一条索引，下面至少一个具名 subTest 当场变红。
        views = ("albums", "artists", "composers", "genres")
        ordering = dict(
            (index, ("idx_%s_name_nocase_%s" % (view, direction)))
            for view in views
            for direction in ("asc", "desc")
            for index in ("%s:%s" % (view, direction),)
        )
        original_connect = library.library_db_connect

        def traced(sink):
            @contextmanager
            def connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(sink.append)
                    yield connection
            return connect

        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            # Alpha/alpha 同属一个大小写键组且页边界正好切在它后面，续页的两条语句
            # 才会都执行（尾读空、预算留给后续组）。
            names = ("Alpha", "alpha", "Beta", "Gamma", "Delta")
            items = []
            for index, name in enumerate(names, 1):
                folder = os.path.join(music_root, "Dir %d" % index)
                os.makedirs(folder, exist_ok=True)
                for slot in range(2):
                    item = self._item(
                        "%d-%d" % (index, slot),
                        os.path.join(folder, "s%d.flac" % slot),
                        "Track %d-%d" % (index, slot), slot + 1,
                    )
                    item["album"], item["artist"] = name, "Artist %d" % index
                    item["composer"], item["genre"] = "Composer %d" % index, "Genre %d" % index
                    items.append(item)
            save_items_to_sqlite(config, items, "group-index-attribution")

            def plan(connection, sql):
                return [row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + sql)]

            def named(connection, sql, view):
                detail = plan(connection, sql)
                hits = {name for line in detail for key, name in ordering.items()
                        if key.startswith(view + ":") and name in line}
                return hits, [line for line in detail if "TEMP B-TREE" in line]

            def expect(connection, sql, view, direction, expected, tag):
                with self.subTest(view=view, sort_dir=direction, path=tag):
                    hits, temps = named(connection, sql, view)
                    self.assertEqual(hits, {ordering["%s:%s" % (view, expected)]},
                                     "%s -> %s" % (sql[:110], " / ".join(plan(connection, sql))))
                    self.assertEqual(temps, [], "%s -> %s" % (sql[:110], " / ".join(plan(connection, sql))))

            covered = set()
            with library_db_connect(config) as connection:
                defined = {row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index'")}
                self.assertTrue(
                    set(ordering.values()) <= defined,
                    "missing ordering indexes: %s" % sorted(set(ordering.values()) - defined),
                )
            for view in views:
                page_prefix = "SELECT * FROM (SELECT * FROM %s) grouped" % view
                for direction in ("asc", "desc"):
                    with self.subTest(view=view, sort_dir=direction, path="first page"):
                        library.invalidate_library_query_cache(config)
                        sink = []
                        with mock.patch.object(library, "library_db_connect", side_effect=traced(sink)):
                            first = query_library_groups(config, view, limit=2, offset=0, sort_dir=direction)
                        pages = [line for line in sink if line.startswith(page_prefix + " ORDER BY")]
                        self.assertEqual(len(pages), 1, "; ".join(sink))
                        with library_db_connect(config) as connection:
                            expect(connection, pages[0], view, direction, direction, "first page")
                            covered.add(ordering["%s:%s" % (view, direction)])
                    token = first.get("next_cursor")
                    self.assertTrue(token, (view, direction, first))
                    library.invalidate_library_query_cache(config)
                    sink = []
                    with mock.patch.object(library, "library_db_connect", side_effect=traced(sink)):
                        page = query_library_groups(
                            config, view, limit=2, offset=0, sort_dir=direction, cursor=token)
                    with self.subTest(view=view, sort_dir=direction, path="continuation"):
                        reads = [line for line in sink if line.startswith(page_prefix + " WHERE")]
                        self.assertEqual(len(reads), 2, "; ".join(sink))
                        self.assertTrue(page["groups"], page)
                        # 尾读是唯一带第二个比较的那条（trace 回调把参数内联成字面量，
                        # 所以这里按形状而不是占位符计数）。
                        tails = [line for line in reads if " AND " in line]
                        self.assertEqual(len(tails), 1, "; ".join(reads))
                        tail, following = reads[0], reads[1]
                        self.assertEqual(tails[0], tail, "; ".join(reads))
                        self.assertNotIn(" AND ", following, following)
                        with library_db_connect(config) as connection:
                            # 组内尾两个方向都走 _desc：次键恒为 name ASC。
                            expect(connection, tail, view, direction, "desc", "cursor tail")
                            # 后续组范围才跟浏览方向一致。
                            expect(connection, following, view, direction, direction, "cursor next group")
                            covered.add(ordering["%s:desc" % view])
                            covered.add(ordering["%s:%s" % (view, direction)])
                with self.subTest(view=view, path="searched page"):
                    library.invalidate_library_query_cache(config)
                    sink = []
                    with mock.patch.object(library, "library_db_connect", side_effect=traced(sink)):
                        found = query_library_groups(config, view, search="Track", limit=2, offset=0)
                    reads = [line for line in sink if "JOIN matched" in line]
                    self.assertEqual(len(reads), 1, "; ".join(sink))
                    self.assertTrue(found["groups"], found)
                    with library_db_connect(config) as connection:
                        hits, _temps = named(connection, reads[0], view)
                        self.assertEqual(hits, set(), "%s -> %s" % (reads[0][:110], " / ".join(plan(connection, reads[0]))))
                with self.subTest(view=view, path="owner-filtered albums"):
                    library.invalidate_library_query_cache(config)
                    sink = []
                    with mock.patch.object(library, "library_db_connect", side_effect=traced(sink)):
                        owned = library.query_library_groups(
                            config, "albums", limit=2, offset=0, artist="Artist 1")
                    reads = [line for line in sink if line.startswith("WITH scoped AS")]
                    self.assertEqual(len(reads), 1, "; ".join(sink))
                    with library_db_connect(config) as connection:
                        hits = {name for line in plan(connection, reads[0]) for key, name in ordering.items() if name in line}
                        self.assertEqual(hits, set(), "%s" % reads[0][:110])
            self.assertEqual(covered, set(ordering.values()), sorted(set(ordering.values()) - covered))

    def test_no_browse_continuation_falls_back_to_the_offset_scan_shape(self):
        # R117 关闭 TODO L143：这条写的 browse_cursor_where 「前缀范围 + 页面 OFFSET」
        # 老形状已经被两读改造整体替换——取证见关闭注记（两个服务端模块源码 0 命中、三个续页调用点
        # 全部经 _browse_cursor_rows）。这里钉的是剩下的那两个可判别事实：
        # 旧符号不许回来，续页语句里不许再出现 OFFSET 或把两条单比较拼回 OR。
        server_root = os.path.dirname(library.__file__)
        for module in ("library.py", "library_browse_cursor_policy.py"):
            with self.subTest(module=module):
                with io.open(os.path.join(server_root, module), encoding="utf-8") as handle:
                    source = handle.read()
                self.assertNotIn("browse_cursor_where", source)
        original_connect = library.library_db_connect

        def traced(sink):
            @contextmanager
            def connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(sink.append)
                    yield connection
            return connect

        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            names = ("Alpha", "alpha", "Beta", "Gamma", "Delta")
            items = []
            for index, name in enumerate(names, 1):
                folder = os.path.join(music_root, "Dir %d" % index)
                os.makedirs(folder, exist_ok=True)
                for slot in range(2):
                    item = self._item(
                        "%d-%d" % (index, slot),
                        os.path.join(folder, "s%d.flac" % slot),
                        "Track %d-%d" % (index, slot), slot + 1,
                    )
                    item["album"], item["artist"] = name, "Artist %d" % index
                    item["composer"], item["genre"] = "Composer %d" % index, "Genre %d" % index
                    sub = os.path.join(folder, "Sub %d-%d" % (index, slot))
                    os.makedirs(sub, exist_ok=True)
                    items.append(item)
            save_items_to_sqlite(config, items, "browse-continuation-shape")
            for view in ("albums", "artists", "composers", "genres"):
                for direction in ("asc", "desc"):
                    with self.subTest(view=view, sort_dir=direction):
                        first = query_library_groups(config, view, limit=2, offset=0, sort_dir=direction)
                        token = first["next_cursor"]
                        self.assertTrue(token, first)
                        library.invalidate_library_query_cache(config)
                        sink = []
                        with mock.patch.object(library, "library_db_connect", side_effect=traced(sink)):
                            # 客户端即使带着非零 offset 进来，游标页也不许退回 OFFSET 分页。
                            page = query_library_groups(
                                config, view, limit=2, offset=4, sort_dir=direction, cursor=token)
                        reads = [line for line in sink if line.startswith("SELECT * FROM (SELECT * FROM %s) grouped WHERE" % view)]
                        self.assertEqual(len(reads), 2, "; ".join(sink))
                        self.assertTrue(all("OFFSET" not in line for line in reads), "; ".join(reads))
                        self.assertTrue(all(" OR " not in line for line in reads), "; ".join(reads))
                        self.assertTrue(page["groups"], page)
            for direction in ("asc", "desc"):
                with self.subTest(browse="folders", sort_dir=direction):
                    first = query_library_folders(config, "", music_root, direction, 2, 0)
                    token = first["next_cursor"]
                    self.assertTrue(token, first)
                    sink = []
                    with mock.patch.object(library, "library_db_connect", side_effect=traced(sink)):
                        page = query_library_folders(config, "", music_root, direction, 2, 4, "", token)
                    reads = [line for line in sink if line.startswith("SELECT f.* FROM folders f WHERE f.root =")]
                    self.assertEqual(len(reads), 2, "; ".join(sink))
                    self.assertTrue(all("OFFSET" not in line for line in reads), "; ".join(reads))
                    self.assertTrue(all(" OR " not in line for line in reads), "; ".join(reads))
                    self.assertTrue(page["folders"], page)

    def test_folder_cursor_matches_following_offset_page(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = [
                self._item("a", os.path.join(music_root, "A", "a.flac"), "A", 1),
                self._item("b", os.path.join(music_root, "B", "b.flac"), "B", 2),
                self._item("c", os.path.join(music_root, "C", "c.flac"), "C", 3),
                self._item("d", os.path.join(music_root, "D", "d.flac"), "D", 4),
            ]
            save_items_to_sqlite(config, items, "folder-cursor")
            first = query_library_folders(config, "", music_root, limit=2, offset=0)
            cursor_page = query_library_folders(config, "", music_root, "asc", 2, 0, "", first["next_cursor"])
            offset_page = query_library_folders(config, "", music_root, "asc", 2, 2)
            self.assertEqual([row["path"] for row in cursor_page["folders"]], [row["path"] for row in offset_page["folders"]])
            self.assertEqual(cursor_page["count"], offset_page["count"])
            self.assertFalse(cursor_page.get("has_more"))

    def test_folder_cursor_ignores_nonzero_offset_in_client_request(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            items = [
                self._item("a", os.path.join(music_root, "A", "a.flac"), "A", 1),
                self._item("b", os.path.join(music_root, "B", "b.flac"), "B", 2),
                self._item("c", os.path.join(music_root, "C", "c.flac"), "C", 3),
            ]
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            save_items_to_sqlite(config, items, "folder-cursor-offset")
            first = query_library_folders(config, "", music_root, limit=1, offset=0)
            cursor_page = query_library_folders(config, "", music_root, "asc", 1, 99, "", first["next_cursor"])
            expected = query_library_folders(config, "", music_root, "asc", 1, 1)
            self.assertEqual([row["path"] for row in cursor_page["folders"]], [row["path"] for row in expected["folders"]])
            self.assertEqual(cursor_page["offset"], 0)

    def test_track_cursor_uses_sql_added_anchor_when_json_omits_added_ns(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("one", os.path.join(music_root, "one.flac"), "One", 1)
            second = self._item("two", os.path.join(music_root, "two.flac"), "Two", 2)
            first["added_ns"] = 100
            second["added_ns"] = 200
            save_items_to_sqlite(config, [first, second], "cursor-added")
            with library_db_connect(config) as conn:
                row = conn.execute("SELECT item_json FROM tracks WHERE id = ?", ("one",)).fetchone()
                payload = json.loads(row["item_json"])
                payload.pop("added_ns", None)
                conn.execute("UPDATE tracks SET item_json = ? WHERE id = ?", (json.dumps(payload), "one"))
            first_page = query_library_page(config, {"view": "all", "sort": "added", "dir": "asc", "limit": "1", "offset": "0"})
            cursor_page = query_library_page(config, {
                "view": "all", "sort": "added", "dir": "asc", "limit": "1", "offset": "0",
                "cursor": first_page["next_cursor"],
            })
            offset_page = query_library_page(config, {"view": "all", "sort": "added", "dir": "asc", "limit": "1", "offset": "1"})
            self.assertEqual([item["id"] for item in cursor_page["items"]], [item["id"] for item in offset_page["items"]])

    def test_unfiltered_page_uses_saved_track_count_without_count_scan(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            save_items_to_sqlite(
                config,
                [self._item("one", os.path.join(music_root, "one.flac"), "One", 1),
                 self._item("two", os.path.join(music_root, "two.flac"), "Two", 2)],
                "test",
            )
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                page = query_library_page(config, {"view": "all", "limit": "1", "offset": "1"})
            self.assertEqual(page["count"], 2)
            self.assertEqual([item["id"] for item in page["items"]], ["two"])
            self.assertFalse(any("COUNT(*) FROM tracks" in statement for statement in statements))

    def test_recent_random_and_dsd_views_reuse_saved_counts(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("one", os.path.join(music_root, "one.dsf"), "One", 1)
            first["is_dsd"] = True
            second = self._item("two", os.path.join(music_root, "two.flac"), "Two", 2)
            save_items_to_sqlite(config, [first, second], "test")
            original_connect = library.library_db_connect
            traces = []

            def traced_connect(current_config):
                @contextmanager
                def manager():
                    with original_connect(current_config) as connection:
                        connection.set_trace_callback(traces.append)
                        yield connection
                return manager()

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                recent = query_library_page(config, {"view": "recent", "limit": "1"})
                random = query_library_page(config, {"view": "random100", "limit": "1"})
                dsd = query_library_page(config, {"view": "dsd", "limit": "1"})
            self.assertEqual(recent["count"], 2)
            self.assertEqual(random["count"], 1)
            self.assertEqual(dsd["count"], 1)
            self.assertFalse(any("COUNT(*) FROM tracks" in statement for statement in traces))

    def test_unfiltered_random_page_avoids_full_random_sort_when_rowids_are_available(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            save_items_to_sqlite(
                config,
                [self._item("one", os.path.join(music_root, "one.flac"), "One", 1),
                 self._item("two", os.path.join(music_root, "two.flac"), "Two", 2)],
                "test",
            )
            traces = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(traces.append)
                    yield connection

            random_values = iter([1, 2])
            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect), \
                 mock.patch.object(library.random, "randrange", side_effect=lambda _start, _stop: next(random_values)):
                page = query_library_page(config, {"view": "random100", "limit": "2"})

            self.assertEqual([item["id"] for item in page["items"]], ["one", "two"])
            self.assertFalse(any("ORDER BY RANDOM()" in statement for statement in traces))

    def test_unfiltered_random_page_does_not_bias_the_rowid_probe_set_to_older_tracks(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            save_items_to_sqlite(
                config,
                [self._item("one", os.path.join(music_root, "one.flac"), "One", 1),
                 self._item("two", os.path.join(music_root, "two.flac"), "Two", 2),
                 self._item("three", os.path.join(music_root, "three.flac"), "Three", 3),
                 self._item("four", os.path.join(music_root, "four.flac"), "Four", 4)],
                "test",
            )
            with mock.patch.object(library, "random_rowid_candidates", return_value=[1, 2, 3, 4]), \
                 mock.patch.object(library.random, "sample", return_value=[4, 2]) as sample:
                page = query_library_page(config, {"view": "random100", "limit": "2"})

            sample.assert_called_once()
            self.assertEqual([item["id"] for item in page["items"]], ["four", "two"])

    def test_unfiltered_random_page_falls_back_when_rowid_sampling_is_incomplete(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            save_items_to_sqlite(
                config,
                [self._item("one", os.path.join(music_root, "one.flac"), "One", 1),
                 self._item("two", os.path.join(music_root, "two.flac"), "Two", 2)],
                "test",
            )
            traces = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(traces.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect), \
                 mock.patch.object(library.random, "randrange", return_value=1):
                page = query_library_page(config, {"view": "random100", "limit": "2"})

            self.assertEqual(page["count"], 2)
            self.assertEqual(len(page["items"]), 2)
            self.assertTrue(any("ORDER BY RANDOM()" in statement for statement in traces))

    def test_explicit_random_refresh_bypasses_the_short_term_page_cache(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            save_items_to_sqlite(
                config,
                [self._item("one", os.path.join(music_root, "one.flac"), "One", 1),
                 self._item("two", os.path.join(music_root, "two.flac"), "Two", 2)],
                "test",
            )
            with mock.patch.object(library, "random_rowid_candidates", side_effect=([1], [2])):
                initial = query_library_page(config, {"view": "random100", "limit": "1"})
                refreshed = query_library_page(config, {"view": "random100", "limit": "1", "refresh": "1"})

            self.assertEqual([item["id"] for item in initial["items"]], ["one"])
            self.assertEqual([item["id"] for item in refreshed["items"]], ["two"])

    def test_library_summary_uses_saved_counts_without_table_scan(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("one", os.path.join(music_root, "one.dsf"), "One", 1)
            first["is_dsd"] = True
            second = self._item("two", os.path.join(music_root, "two.flac"), "Two", 2)
            save_items_to_sqlite(config, [first, second], "test")
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                summary = library.library_summary_from_sqlite(config)
            self.assertEqual(summary["count"], 2)
            self.assertEqual(summary["dsd_count"], 1)
            self.assertFalse(any("COUNT(*) FROM tracks" in statement for statement in statements))

    def test_normal_group_filters_use_plain_indexable_columns_and_keep_unclassified_semantics(self):
        self.assertEqual(group_match_condition("artist", "Artist A"), ("artist = ?", ["Artist A"]))
        self.assertEqual(
            group_match_condition("t.album", UNCLASSIFIED),
            ("(t.album = ? OR t.album = '' OR t.album IS NULL)", [UNCLASSIFIED]),
        )
        with self.assertRaises(ValueError):
            group_match_condition("path", "not allowed")

    def test_indexed_group_filter_preserves_literal_and_blank_unclassified_tracks(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            tagged = self._item("tagged", os.path.join(music_root, "tagged.flac"), "Tagged", 1)
            tagged["artist"] = UNCLASSIFIED
            blank = self._item("blank", os.path.join(music_root, "blank.flac"), "Blank", 2)
            blank["artist"] = ""
            named = self._item("named", os.path.join(music_root, "named.flac"), "Named", 3)
            named["artist"] = "Artist A"
            save_items_to_sqlite(config, [tagged, blank, named], "test")
            unknown = query_library_page(config, {"view": "artists", "group": UNCLASSIFIED, "limit": "10"})
            known = query_library_page(config, {"view": "artists", "group": "Artist A", "limit": "10"})
            self.assertEqual({item["id"] for item in unknown["items"]}, {"tagged", "blank"})
            self.assertEqual([item["id"] for item in known["items"]], ["named"])

    def test_normal_group_page_filter_uses_the_existing_group_index(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index in range(16):
                item = self._item("track-%s" % index, os.path.join(music_root, "%s.flac" % index), "Track %02d" % index, index)
                item["artist"] = "Artist A" if index % 2 else "Artist B"
                items.append(item)
            save_items_to_sqlite(config, items, "test")
            with library_db_connect(config) as conn:
                plan = [
                    row[3]
                    for row in conn.execute(
                        "EXPLAIN QUERY PLAN SELECT item_json FROM tracks WHERE artist = ? ORDER BY title COLLATE NOCASE ASC, id ASC LIMIT 10",
                        ("Artist A",),
                    )
                ]
            self.assertTrue(any("idx_tracks_artist" in detail for detail in plan), plan)

    def test_folder_pages_without_a_root_seek_by_parent_in_both_orders(self):
        # `/api/library/folders` can arrive with no `root`: the UI only sets the parameter once a
        # root has actually been chosen (app.js:5745), and the player adapter passes whatever it
        # holds straight through (server.py:3154). A `parent`-only predicate cannot use the
        # root-leading index, so the listing scanned every folder row and sorted the whole set in a
        # temporary B-tree. Measured through this function at 100000 folders: 5.84 ms per page
        # without the pair, 1.27 ms with it.
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            other_root = os.path.join(root, "other")
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root, other_root]}
            shared_parent = os.path.join(music_root, "Shared")
            rows = []
            for folder_root in (music_root, other_root):
                for name in ("alpha", "Bravo", "charlie"):
                    rows.append((os.path.join(shared_parent, name), folder_root, shared_parent, name, 1, ""))
            with library_db_connect(config) as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO folders(path,root,parent,name,track_count,cover_track_id)"
                    " VALUES (?,?,?,?,?,?)",
                    rows,
                )
                conn.commit()
                for direction, index_name in (("ASC", "idx_folders_parent_name_nocase_asc"),
                                              ("DESC", "idx_folders_parent_name_nocase_desc")):
                    with self.subTest(direction=direction):
                        plan = [row[3] for row in conn.execute(
                            "EXPLAIN QUERY PLAN SELECT * FROM folders f WHERE f.parent = ?"
                            " ORDER BY f.name COLLATE NOCASE %s, f.path ASC LIMIT ?" % direction,
                            (shared_parent, 10),
                        )]
                        self.assertTrue(any(index_name in detail for detail in plan), plan)
                        self.assertFalse(any("TEMP B-TREE" in detail for detail in plan), plan)
                        # The narrower index must not capture the root-scoped query: that one has a
                        # strictly better composite index and has to keep using it.
                        rooted_plan = [row[3] for row in conn.execute(
                            "EXPLAIN QUERY PLAN SELECT * FROM folders f WHERE f.root = ? AND f.parent = ?"
                            " ORDER BY f.name COLLATE NOCASE %s, f.path ASC LIMIT ?" % direction,
                            (music_root, shared_parent, 10),
                        )]
                        self.assertTrue(any("idx_folders_root_parent_name_nocase" in detail for detail in rooted_plan),
                                        rooted_plan)
            # And the answer must not quietly narrow: a parent string that exists under two roots is
            # listed across both, in case-insensitive name order.
            listing = query_library_folders(config, parent=shared_parent, root="", limit=10, offset=0)
            self.assertEqual([folder["name"] for folder in listing["folders"]],
                             ["alpha", "alpha", "Bravo", "Bravo", "charlie", "charlie"])
            self.assertEqual({folder["root"] for folder in listing["folders"]}, {music_root, other_root})

    def test_title_pages_use_stable_composite_indexes_without_a_temp_sort(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index in range(16):
                items.append(self._item("track-%02d" % index, os.path.join(music_root, "%s.flac" % index), "Same Title", index))
            save_items_to_sqlite(config, items, "test")
            with library_db_connect(config) as conn:
                for direction, index_name in (("ASC", "idx_tracks_title_nocase_id_asc"), ("DESC", "idx_tracks_title_nocase_id_desc")):
                    plan = [
                        row[3]
                        for row in conn.execute(
                            "EXPLAIN QUERY PLAN SELECT item_json FROM tracks ORDER BY title COLLATE NOCASE %s, id ASC LIMIT 10 OFFSET 4" % direction,
                        )
                    ]
                    self.assertTrue(any(index_name in detail for detail in plan), plan)
                    self.assertFalse(any("TEMP B-TREE" in detail for detail in plan), plan)
            ascending = query_library_page(config, {"view": "all", "sort": "title", "dir": "asc", "limit": "4", "offset": "4"})
            descending = query_library_page(config, {"view": "all", "sort": "title", "dir": "desc", "limit": "4", "offset": "4"})
            self.assertEqual([item["id"] for item in ascending["items"]], ["track-04", "track-05", "track-06", "track-07"])
            self.assertEqual([item["id"] for item in descending["items"]], ["track-04", "track-05", "track-06", "track-07"])

    def test_artist_and_album_pages_use_stable_composite_indexes_without_a_temp_sort(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index in range(16):
                item = self._item("track-%02d" % index, os.path.join(music_root, "%s.flac" % index), "Title %02d" % (15 - index), index)
                item["artist"] = "Artist %02d" % (index % 4)
                item["album"] = "Album %02d" % (index % 4)
                items.append(item)
            save_items_to_sqlite(config, items, "test")
            index_names = {
                ("artist", "ASC"): "idx_tracks_artist_nocase_title_id_asc",
                ("artist", "DESC"): "idx_tracks_artist_nocase_title_id_desc",
                ("album", "ASC"): "idx_tracks_album_nocase_title_id_asc",
                ("album", "DESC"): "idx_tracks_album_nocase_title_id_desc",
            }
            with library_db_connect(config) as conn:
                for (column, direction), index_name in index_names.items():
                    plan = [
                        row[3]
                        for row in conn.execute(
                            "EXPLAIN QUERY PLAN SELECT item_json FROM tracks ORDER BY %s COLLATE NOCASE %s, title COLLATE NOCASE ASC, id ASC LIMIT 10 OFFSET 4" % (column, direction),
                        )
                    ]
                    self.assertTrue(any(index_name in detail for detail in plan), plan)
                    self.assertFalse(any("TEMP B-TREE" in detail for detail in plan), plan)
            artist_page = query_library_page(config, {"view": "all", "sort": "artist", "dir": "desc", "limit": "4", "offset": "4"})
            album_page = query_library_page(config, {"view": "all", "sort": "album", "dir": "asc", "limit": "4", "offset": "4"})
            self.assertEqual(artist_page["count"], len(items))
            self.assertEqual(album_page["count"], len(items))
            self.assertEqual(len(artist_page["items"]), 4)
            self.assertEqual(len(album_page["items"]), 4)

    def test_added_pages_use_stable_composite_indexes_and_replace_legacy_index(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index in range(16):
                item = self._item("track-%02d" % index, os.path.join(music_root, "%s.flac" % index), "Title %02d" % (15 - index), index)
                item["added_ns"] = index * 1000
                items.append(item)
            save_items_to_sqlite(config, items, "test")
            index_names = {
                "ASC": "idx_tracks_added_title_id_asc",
                "DESC": "idx_tracks_added_title_id_desc",
            }
            with library_db_connect(config) as conn:
                available = {row[1] for row in conn.execute("PRAGMA index_list(tracks)")}
                self.assertNotIn("idx_tracks_added", available)
                for direction, index_name in index_names.items():
                    plan = [
                        row[3]
                        for row in conn.execute(
                            "EXPLAIN QUERY PLAN SELECT item_json FROM tracks ORDER BY added_ns %s, title COLLATE NOCASE ASC, id ASC LIMIT 10 OFFSET 4" % direction,
                        )
                    ]
                    self.assertTrue(any(index_name in detail for detail in plan), plan)
                    self.assertFalse(any("TEMP B-TREE" in detail for detail in plan), plan)
            ascending = query_library_page(config, {"view": "all", "sort": "added", "dir": "asc", "limit": "4", "offset": "4"})
            descending = query_library_page(config, {"view": "all", "sort": "added", "dir": "desc", "limit": "4", "offset": "4"})
            self.assertEqual([item["id"] for item in ascending["items"]], ["track-04", "track-05", "track-06", "track-07"])
            self.assertEqual([item["id"] for item in descending["items"]], ["track-11", "track-10", "track-09", "track-08"])

    def test_format_and_track_number_pages_use_stable_composite_indexes(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index in range(16):
                item = self._item("track-%02d" % index, os.path.join(music_root, "%s.flac" % index), "Title %02d" % (15 - index), index % 5)
                item["format"] = ("FLAC", "MP3", "WAV", "APE")[index % 4]
                items.append(item)
            save_items_to_sqlite(config, items, "test")
            queries = {
                ("format COLLATE NOCASE", "ASC"): "idx_tracks_format_nocase_title_id_asc",
                ("format COLLATE NOCASE", "DESC"): "idx_tracks_format_nocase_title_id_desc",
                ("CASE WHEN track_no <= 0 THEN 2147483647 ELSE track_no END", "ASC"): "idx_tracks_track_no_title_id_asc",
                ("CASE WHEN track_no <= 0 THEN 2147483647 ELSE track_no END", "DESC"): "idx_tracks_track_no_title_id_desc",
            }
            with library_db_connect(config) as conn:
                available = {row[1] for row in conn.execute("PRAGMA index_list(tracks)")}
                self.assertNotIn("idx_tracks_format_nocase", available)
                self.assertNotIn("idx_tracks_track_no", available)
                for (expression, direction), index_name in queries.items():
                    plan = [
                        row[3]
                        for row in conn.execute(
                            "EXPLAIN QUERY PLAN SELECT item_json FROM tracks ORDER BY %s %s, title COLLATE NOCASE ASC, id ASC LIMIT 10 OFFSET 4" % (expression, direction),
                        )
                    ]
                    self.assertTrue(any(index_name in detail for detail in plan), plan)
                    self.assertFalse(any("TEMP B-TREE" in detail for detail in plan), plan)
            format_page = query_library_page(config, {"view": "all", "sort": "format", "dir": "desc", "limit": "4", "offset": "4"})
            track_no_page = query_library_page(config, {"view": "all", "sort": "track_no", "dir": "asc", "limit": "4", "offset": "4"})
            self.assertEqual(format_page["count"], len(items))
            self.assertEqual(track_no_page["count"], len(items))
            self.assertEqual(len(format_page["items"]), 4)
            self.assertEqual(len(track_no_page["items"]), 4)

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

    def test_complete_probe_tags_skip_the_second_native_tag_scan(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "complete.flac")
            with open(path, "wb"):
                pass
            probe = {
                "title": "Title", "artist": "Artist", "album": "Album",
                "composer": "Composer", "genre": "Genre", "track_no": 1,
            }
            with mock.patch.object(library, "read_vorbis_comments", side_effect=AssertionError("native scan should be skipped")):
                metadata = read_metadata(path, root, probe_tags=probe)
            self.assertEqual(metadata["title"], "Title")

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

    def test_root_folder_query_uses_short_term_cache_and_index_save_invalidates_it(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("one", os.path.join(music_root, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [first], "first")
            original_connect = library.library_db_connect
            calls = []

            def counted_connect(current_config):
                calls.append(current_config)
                return original_connect(current_config)

            with mock.patch.object(library, "library_db_connect", side_effect=counted_connect):
                first_read = query_library_root_folders(config)
                second_read = query_library_root_folders(config)
            self.assertEqual([row["track_count"] for row in first_read], [1])
            self.assertEqual(second_read, first_read)
            self.assertEqual(len(calls), 1)

            second = self._item("two", os.path.join(music_root, "two.flac"), "Two", 2)
            save_items_to_sqlite(config, [first, second], "second")
            with mock.patch.object(library, "library_db_connect", side_effect=counted_connect):
                refreshed = query_library_root_folders(config)
            self.assertEqual([row["track_count"] for row in refreshed], [2])
            self.assertEqual(len(calls), 2)

    def test_root_folder_query_cache_includes_configured_root_identity(self):
        with tempfile.TemporaryDirectory() as root:
            first_root = os.path.join(root, "music-a")
            second_root = os.path.join(root, "music-b")
            os.makedirs(first_root)
            os.makedirs(second_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [first_root]}
            save_items_to_sqlite(config, [self._item("a", os.path.join(first_root, "one.flac"), "One", 1)], "test")

            first = query_library_root_folders(config)
            config["library_paths"] = [second_root]
            second = query_library_root_folders(config)

            self.assertEqual([row["root"] for row in first], [first_root])
            self.assertEqual([row["root"] for row in second], [second_root])

    def test_root_folder_query_uses_persisted_summary_and_old_indexes_fall_back(self):
        with tempfile.TemporaryDirectory() as root:
            first_root = os.path.join(root, "music-a")
            second_root = os.path.join(root, "music-b")
            os.makedirs(first_root)
            os.makedirs(second_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [first_root, second_root]}
            first = self._item("a", os.path.join(first_root, "one.flac"), "One", 1)
            second = self._item("b", os.path.join(second_root, "two.flac"), "Two", 2)
            save_items_to_sqlite(config, [first, second], "test")
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                roots = query_library_root_folders(config)
            self.assertEqual([row["track_count"] for row in roots], [1, 1])
            self.assertFalse(any("GROUP BY root" in statement for statement in statements))

            with library_db_connect(config) as connection:
                connection.execute("DELETE FROM library_meta WHERE key = 'root_summary'")
            library.invalidate_library_query_cache(config)
            statements[:] = []
            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                fallback = query_library_root_folders(config)
            self.assertEqual([row["track_count"] for row in fallback], [1, 1])
            self.assertTrue(any("GROUP BY root" in statement for statement in statements))

    def test_root_folder_search_without_matches_skips_summary_and_fallback_aggregation(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            save_items_to_sqlite(config, [self._item("one", os.path.join(music_root, "one.flac"), "Present", 1)], "test")
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                self.assertEqual(query_library_root_folders(config, "missing"), [])
            self.assertTrue(any("SELECT DISTINCT root FROM tracks" in statement for statement in statements))
            self.assertFalse(any("root_summary" in statement for statement in statements))
            self.assertFalse(any("GROUP BY root" in statement for statement in statements))

    def test_root_folder_fallback_ignores_stale_unconfigured_roots(self):
        with tempfile.TemporaryDirectory() as root:
            configured_root = os.path.join(root, "music")
            stale_root = os.path.join(root, "old")
            os.makedirs(configured_root)
            os.makedirs(stale_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [configured_root]}
            configured = self._item("configured", os.path.join(configured_root, "one.flac"), "Configured", 1)
            stale = self._item("stale", os.path.join(stale_root, "old.flac"), "Stale", 1)
            save_items_to_sqlite(config, [configured, stale], "test")
            with library_db_connect(config) as connection:
                connection.execute("DELETE FROM library_meta WHERE key = 'root_summary'")
            library.invalidate_library_query_cache(config)
            roots = query_library_root_folders(config)
            self.assertEqual([row["path"] for row in roots], [configured_root])
            self.assertEqual(roots[0]["track_count"], 1)

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

    def test_paged_query_cache_is_invalidated_after_index_save(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("first", os.path.join(music_root, "first.flac"), "First", 1)
            replacement = self._item("replacement", os.path.join(music_root, "replacement.flac"), "Replacement", 1)
            save_items_to_sqlite(config, [first], "first")

            initial = query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
            cached = query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
            self.assertEqual([item["id"] for item in initial["items"]], ["first"])
            self.assertEqual(cached, initial)

            save_items_to_sqlite(config, [replacement], "second")
            refreshed = query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
            self.assertEqual([item["id"] for item in refreshed["items"]], ["replacement"])

    def test_recent_page_reuses_the_same_short_lived_sqlite_cache(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            item = self._item("recent", os.path.join(music_root, "recent.flac"), "Recent", 1)
            save_items_to_sqlite(config, [item], "recent-cache")
            library.invalidate_library_query_cache(config)

            initial = query_library_page(config, {"view": "recent", "limit": "10", "offset": "0"})
            before = library.library_query_cache_status()["hits"]
            cached = query_library_page(config, {"view": "recent", "limit": "10", "offset": "0"})

            self.assertEqual(cached, initial)
            self.assertGreaterEqual(library.library_query_cache_status()["hits"], before + 1)

    def test_paged_query_cache_rejects_an_externally_replaced_database(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("first", os.path.join(music_root, "first.flac"), "First", 1)
            replacement = self._item("replacement", os.path.join(music_root, "replacement.flac"), "Replacement", 1)
            save_items_to_sqlite(config, [first], "first")
            initial = query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
            self.assertEqual([item["id"] for item in initial["items"]], ["first"])

            replacement_root = os.path.join(root, "replacement")
            os.makedirs(replacement_root)
            replacement_config = {"cache_dir": replacement_root, "library_paths": [music_root]}
            save_items_to_sqlite(replacement_config, [replacement], "replacement")
            shutil.copyfile(library.library_db_path(replacement_config), library.library_db_path(config))

            refreshed = query_library_page(config, {"view": "all", "limit": "10", "offset": "0"})
            self.assertEqual([item["id"] for item in refreshed["items"]], ["replacement"])

    def test_search_index_preserves_substring_results_and_rebuilds_with_the_library(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("first", os.path.join(music_root, "first.flac"), "Hidden Needle", 1)
            first.update({"artist": "Singer A", "album": "Album A"})
            save_items_to_sqlite(config, [first], "first")
            first_result = query_library_page(config, {"view": "all", "search": "needle", "limit": "10"})
            self.assertEqual([item["id"] for item in first_result["items"]], ["first"])

            replacement = self._item("replacement", os.path.join(music_root, "replacement.flac"), "Different Title", 1)
            replacement.update({"artist": "Singer A", "album": "Needle Album"})
            save_items_to_sqlite(config, [replacement], "second")
            second_result = query_library_page(config, {"view": "all", "search": "needle", "limit": "10"})
            self.assertEqual([item["id"] for item in second_result["items"]], ["replacement"])
            self.assertIn(library_search_index_status(config)["mode"], ("fts5-trigram", "like"))

    def test_short_search_keeps_legacy_contains_behavior_when_fts_is_available(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            item = self._item("short", os.path.join(music_root, "short.flac"), "Abc Song", 1)
            save_items_to_sqlite(config, [item], "test")
            result = query_library_page(config, {"view": "all", "search": "bc", "limit": "10"})
            self.assertEqual([row["id"] for row in result["items"]], ["short"])

    def test_search_page_cache_isolated_when_search_index_mode_changes(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            item = self._item("needle", os.path.join(music_root, "needle.flac"), "Needle Song", 1)
            save_items_to_sqlite(config, [item], "mode-cache")
            database = os.path.abspath(library.library_db_path(config))
            library.invalidate_library_query_cache(config)
            with library.LIBRARY_SEARCH_INDEX_LOCK:
                original_mode = library.LIBRARY_SEARCH_INDEX_MODE.get(database)
                library.LIBRARY_SEARCH_INDEX_MODE[database] = LIKE_MODE
            try:
                first = query_library_page(config, {"view": "all", "search": "needle", "limit": "10"})
                status_after_like = library.library_query_cache_status()
                with library.LIBRARY_SEARCH_INDEX_LOCK:
                    library.LIBRARY_SEARCH_INDEX_MODE[database] = FTS_MODE
                second = query_library_page(config, {"view": "all", "search": "needle", "limit": "10"})
                status_after_fts = library.library_query_cache_status()
            finally:
                with library.LIBRARY_SEARCH_INDEX_LOCK:
                    if original_mode is None:
                        library.LIBRARY_SEARCH_INDEX_MODE.pop(database, None)
                    else:
                        library.LIBRARY_SEARCH_INDEX_MODE[database] = original_mode
                library.invalidate_library_query_cache(config)
            self.assertEqual([row["id"] for row in first["items"]], ["needle"])
            self.assertEqual([row["id"] for row in second["items"]], ["needle"])
            self.assertGreaterEqual(status_after_fts["misses"], status_after_like["misses"] + 1)

    def test_non_search_browse_cache_does_not_consult_search_mode(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            item = self._item("one", os.path.join(music_root, "Album", "one.flac"), "One", 1)
            item.update({"artist": "Artist", "album": "Album", "folder": "Album", "root": music_root})
            save_items_to_sqlite(config, [item], "browse-cache")
            with mock.patch.object(library, "_search_cache_token", side_effect=AssertionError("non-search browse must not inspect mode")):
                self.assertEqual(query_library_groups(config, "albums", limit=10)["count"], 1)
                self.assertEqual(query_library_folders(config, "", music_root, limit=10)["count"], 1)
                self.assertEqual(len(query_library_root_folders(config)), 1)

    def test_search_plan_reads_index_mode_once_for_sql_and_cache(self):
        with mock.patch.object(library, "_search_index_mode", return_value=FTS_MODE) as mode:
            plan = library._search_plan({}, "needle")
        self.assertEqual(plan, (True, FTS_MODE))
        mode.assert_called_once_with({})

    def test_root_search_reads_index_mode_once_for_sql_and_cache(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            item = self._item("needle", os.path.join(music_root, "needle.flac"), "Needle", 1)
            item["root"] = music_root
            save_items_to_sqlite(config, [item], "root-search-plan")
            library.invalidate_library_query_cache(config)
            with mock.patch.object(library, "_search_index_mode", return_value=LIKE_MODE) as mode:
                roots = query_library_root_folders(config, "needle")
            self.assertEqual(len(roots), 1)
            mode.assert_called_once_with(config)

    def test_schema_migrations_are_not_replayed_for_each_connection(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": []}
            with mock.patch.object(library, "ensure_library_schema", wraps=library.ensure_library_schema) as ensure:
                with library_db_connect(config) as conn:
                    conn.execute("SELECT 1")
                with library_db_connect(config) as conn:
                    conn.execute("SELECT 1")
            self.assertEqual(ensure.call_count, 1)

    def test_schema_is_rebuilt_when_an_external_cleanup_replaces_the_database(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": []}
            with library_db_connect(config) as conn:
                conn.execute("INSERT OR REPLACE INTO library_meta(key,value) VALUES ('first','1')")
            database = library.library_db_path(config)
            os.remove(database)
            with mock.patch.object(library, "ensure_library_schema", wraps=library.ensure_library_schema) as ensure:
                with library_db_connect(config) as conn:
                    conn.execute("INSERT OR REPLACE INTO library_meta(key,value) VALUES ('replacement','1')")
                self.assertEqual(ensure.call_count, 1)
            with library_db_connect(config) as conn:
                self.assertEqual(conn.execute("SELECT value FROM library_meta WHERE key = 'replacement'").fetchone()[0], "1")

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

    def test_item_location_rejects_non_text_or_oversized_paths(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            path = os.path.join(music_root, "song.flac")
            with open(path, "wb"):
                pass
            self.assertFalse(library.is_library_item_path(config, object()))
            self.assertFalse(library.is_library_item_path(config, path + ("x" * 4096)))

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

    def test_paged_artist_album_groups_use_one_scoped_cte_for_total_and_page(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index in range(3):
                item = self._item("track-%d" % index, os.path.join(music_root, "%d.flac" % index), "Track %d" % index, index)
                item.update({"artist": "Artist A", "album": "Album %d" % index, "album_artist": "Artist A"})
                items.append(item)
            save_items_to_sqlite(config, items, "test")
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                page = query_library_groups(config, "albums", artist="Artist A", limit=1, offset=1)
            scoped_ctes = [statement for statement in statements if statement.startswith("WITH scoped AS")]
            self.assertEqual(page["count"], 3)
            self.assertEqual([group["name"] for group in page["groups"]], ["Album 1"])
            self.assertEqual(len(scoped_ctes), 1)
            out_of_range = query_library_groups(config, "albums", artist="Artist A", limit=1, offset=99)
            self.assertEqual(out_of_range["count"], 3)
            self.assertEqual(out_of_range["groups"], [])

    def test_paged_artist_album_groups_fall_back_when_sqlite_lacks_window_functions(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index in range(2):
                item = self._item("track-%d" % index, os.path.join(music_root, "%d.flac" % index), "Track %d" % index, index)
                item.update({"artist": "Artist A", "album": "Album %d" % index, "album_artist": "Artist A"})
                items.append(item)
            save_items_to_sqlite(config, items, "test")
            original_connect = library.library_db_connect

            class WindowlessConnection:
                def __init__(self, connection):
                    self._connection = connection

                def execute(self, statement, values=()):
                    if "COUNT(*) OVER()" in statement:
                        raise library.sqlite3.OperationalError("window functions unavailable")
                    return self._connection.execute(statement, values)

            @contextmanager
            def windowless_connect(current_config):
                with original_connect(current_config) as connection:
                    yield WindowlessConnection(connection)

            with mock.patch.object(library, "library_db_connect", side_effect=windowless_connect):
                page = query_library_groups(config, "albums", artist="Artist A", limit=1, offset=0)
            self.assertEqual(page["count"], 2)
            self.assertEqual([group["name"] for group in page["groups"]], ["Album 0"])

    def test_unfiltered_group_page_reads_an_indexed_page_and_a_persisted_count(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(os.path.join(music_root, "A"))
            os.makedirs(os.path.join(music_root, "B"))
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("one", os.path.join(music_root, "A", "one.flac"), "One", 1)
            first["album"] = "Album A"
            second = self._item("two", os.path.join(music_root, "B", "two.flac"), "Two", 2)
            second["album"] = "Album B"
            # Three tracks in two albums: a total that reads the wrong table is
            # visible in the reported count as well as in the SQL text.
            third = self._item("three", os.path.join(music_root, "A", "three.flac"), "Three", 3)
            third["album"] = "Album A"
            save_items_to_sqlite(config, [first, second, third], "test")
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                ascending = query_library_groups(config, "albums", limit=1, offset=0)
                group_statements = list(statements)
                statements[:] = []
                descending = query_library_groups(config, "albums", limit=1, offset=0, sort_dir="desc")
            self.assertEqual(ascending["count"], 2)
            self.assertEqual([row["name"] for row in ascending["groups"]], ["Album A"])
            self.assertEqual(descending["count"], 2)
            self.assertEqual([row["name"] for row in descending["groups"]], ["Album B"])
            # A window total would sort every group for every page, so the
            # unfiltered browse lane keeps its plain-count shape; the plain count
            # itself now comes from the persisted group total, so neither the
            # window nor the scan may appear, and the page reads one row past
            # its limit to keep that total honest.
            self.assertFalse(any("COUNT(*) OVER()" in sql for sql in group_statements), group_statements)
            self.assertFalse(
                any("SELECT COUNT(*) FROM albums" in sql for sql in group_statements),
                group_statements,
            )
            self.assertEqual(len([sql for sql in group_statements if "LIMIT 2 OFFSET 0" in sql]), 1)

    def test_group_tables_carry_case_insensitive_ordering_indexes(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            save_items_to_sqlite(
                config,
                [self._item("one", os.path.join(music_root, "one.flac"), "One", 1)],
                "test",
            )
            with library_db_connect(config) as conn:
                indexed = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
                for table in ("albums", "artists", "composers", "genres"):
                    for direction, order in (("asc", "ASC"), ("desc", "DESC")):
                        index_name = "idx_%s_name_nocase_%s" % (table, direction)
                        self.assertIn(index_name, indexed)
                        plan = [
                            row[3]
                            for row in conn.execute(
                                "EXPLAIN QUERY PLAN SELECT * FROM %s"
                                " ORDER BY name COLLATE NOCASE %s, name ASC LIMIT 1 OFFSET 0" % (table, order),
                            )
                        ]
                        self.assertTrue(any(index_name in detail for detail in plan), (table, direction, plan))
                        self.assertFalse(any("TEMP B-TREE" in detail for detail in plan), (table, direction, plan))

    def test_filtered_group_page_keeps_its_single_scoped_window_query(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            needle = self._item("needle", os.path.join(music_root, "needle.flac"), "Hidden Needle", 1)
            needle["album"] = "Album Alpha"
            other = self._item("other", os.path.join(music_root, "other.flac"), "Different Song", 2)
            other["album"] = "Album Beta"
            save_items_to_sqlite(config, [needle, other], "test")
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                page = query_library_groups(config, "albums", search="needle", limit=1, offset=0)
            self.assertEqual(page["count"], 1)
            self.assertEqual([row["name"] for row in page["groups"]], ["Album Alpha"])
            # A filtered group page totals from the same search CTE it renders,
            # so splitting total and page would evaluate that CTE twice.
            self.assertEqual(len([sql for sql in statements if "COUNT(*) OVER()" in sql]), 1)
            self.assertFalse(any("SELECT COUNT(*) FROM matched" in sql for sql in statements), statements)

    def _traced_folder_library(self, root):
        music_root = os.path.join(root, "music")
        for name in ("A", "B", "c"):
            os.makedirs(os.path.join(music_root, name))
        config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
        items = [
            self._item("one", os.path.join(music_root, "A", "one.flac"), "Track One", 1),
            self._item("two", os.path.join(music_root, "B", "two.flac"), "Track Two", 2),
            self._item("three", os.path.join(music_root, "c", "three.flac"), "Track Three", 3),
        ]
        save_items_to_sqlite(config, items, "test")
        return config, music_root

    def test_unfiltered_folder_page_reads_an_indexed_page_plus_count(self):
        with tempfile.TemporaryDirectory() as root:
            config, music_root = self._traced_folder_library(root)
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                folders = query_library_folders(config, "", music_root, "asc", 2, 1)
                descending = query_library_folders(config, "", music_root, "desc", 2, 0)
                folder_statements = list(statements)
            self.assertEqual(folders["count"], 3)
            self.assertEqual([row["name"] for row in folders["folders"]], ["B", "c"])
            self.assertEqual([row["name"] for row in descending["folders"]], ["c", "B"])
            pages = [sql for sql in folder_statements if sql.startswith("SELECT f.* FROM folders f WHERE")]
            counts = [sql for sql in folder_statements if "SELECT COUNT(*) FROM folders f WHERE" in sql]
            self.assertEqual(len(pages), 2, "; ".join(pages))
            self.assertEqual(len(counts), 2, "; ".join(counts))
            # A window total has to visit every sibling of the directory before
            # it can emit its first row, which is exactly what the NOCASE
            # ordering index avoids. Measured at 20k top-level folders: a 0.09 ms
            # indexed page plus a 0.56 ms covering count against 17-18 ms for the
            # window shape, and the gap grows with the directory.
            self.assertFalse(any("COUNT(*) OVER()" in sql for sql in folder_statements), folder_statements)
            with library_db_connect(config) as conn:
                for sql in pages:
                    plan = [row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + sql)]
                    self.assertTrue(
                        any("idx_folders_root_parent_name_nocase" in detail for detail in plan),
                        (sql, plan),
                    )
                    self.assertFalse(any("TEMP B-TREE" in detail for detail in plan), (sql, plan))

    def test_searched_folder_page_keeps_its_single_scoped_window_query(self):
        with tempfile.TemporaryDirectory() as root:
            config, music_root = self._traced_folder_library(root)
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                folders = query_library_folders(config, "", music_root, "asc", 2, 0, "track")
                folder_statements = list(statements)
            self.assertEqual([row["name"] for row in folders["folders"]], ["A", "B"])
            self.assertEqual(folders["count"], 3)
            # A search page tests every sibling for a match anyway, so carrying
            # the total inside the one statement stays the cheaper shape.
            self.assertEqual(len([sql for sql in folder_statements if "COUNT(*) OVER()" in sql]), 1)
            self.assertFalse(any("SELECT COUNT(*) FROM folders" in sql for sql in folder_statements))

    def test_folder_table_carries_case_insensitive_ordering_indexes(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            save_items_to_sqlite(
                config,
                [self._item("one", os.path.join(music_root, "A", "one.flac"), "One", 1)],
                "test",
            )
            # The schema pass is what an installed database built before these
            # indexes runs on its next open: it picks up the new ordering
            # indexes and sheds the binary-collate one no folder query can use.
            with library_db_connect(config) as conn:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_folders_root_parent_name ON folders(root, parent, name)")
                library.ensure_library_schema(conn)
                names = {
                    row["name"]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'folders'")
                }
                self.assertIn("idx_folders_root_parent_name_nocase_asc", names)
                self.assertIn("idx_folders_root_parent_name_nocase_desc", names)
                self.assertNotIn("idx_folders_root_parent_name", names)
                # The plain (root, parent) index stays: it is the covering index
                # the page count reads. Measured without it, that count goes from
                # 0.56 ms to 3.03 ms on the same 20k-row directory.
                self.assertIn("idx_folders_root_parent", names)
                for direction, index_name in (
                    ("ASC", "idx_folders_root_parent_name_nocase_asc"),
                    ("DESC", "idx_folders_root_parent_name_nocase_desc"),
                ):
                    plan = [
                        row[3]
                        for row in conn.execute(
                            "EXPLAIN QUERY PLAN SELECT f.* FROM folders f"
                            " WHERE f.root = ? AND f.parent = ?"
                            " ORDER BY f.name COLLATE NOCASE %s, f.path ASC LIMIT ? OFFSET ?" % direction,
                            (music_root, "", 100, 0),
                        )
                    ]
                    self.assertTrue(any(index_name in detail for detail in plan), (direction, plan))
                    self.assertFalse(any("TEMP B-TREE" in detail for detail in plan), (direction, plan))

    def test_filtered_group_pages_fall_back_when_sqlite_lacks_window_functions(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("one", os.path.join(music_root, "one.flac"), "Hidden Needle", 1)
            first["album"] = "Album A"
            second = self._item("two", os.path.join(music_root, "two.flac"), "Another Song", 2)
            second["album"] = "Album B"
            save_items_to_sqlite(config, [first, second], "test")
            original_connect = library.library_db_connect

            class WindowlessConnection:
                def __init__(self, connection):
                    self._connection = connection

                def execute(self, statement, values=()):
                    if "COUNT(*) OVER()" in statement:
                        raise library.sqlite3.OperationalError("window functions unavailable")
                    return self._connection.execute(statement, values)

            @contextmanager
            def windowless_connect(current_config):
                with original_connect(current_config) as connection:
                    yield WindowlessConnection(connection)

            with mock.patch.object(library, "library_db_connect", side_effect=windowless_connect):
                page = query_library_groups(config, "albums", search="needle", limit=1, offset=0)
            self.assertEqual(page["count"], 1)
            self.assertEqual([row["name"] for row in page["groups"]], ["Album A"])

    def test_filtered_track_page_uses_one_window_query_and_old_sqlite_falls_back(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("one", os.path.join(music_root, "one.flac"), "One", 1)
            first["artist"] = "Artist A"
            second = self._item("two", os.path.join(music_root, "two.flac"), "Two", 2)
            second["artist"] = "Artist A"
            third = self._item("three", os.path.join(music_root, "three.flac"), "Three", 3)
            third["artist"] = "Artist B"
            save_items_to_sqlite(config, [first, second, third], "test")
            params = {"view": "artists", "group": "Artist A", "limit": "1", "offset": "1"}
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                page = query_library_page(config, params)
            self.assertEqual(page["count"], 2)
            self.assertEqual([row["id"] for row in page["items"]], ["two"])
            self.assertEqual(len([sql for sql in statements if "COUNT(*) OVER()" in sql]), 1)
            self.assertFalse(any("SELECT COUNT(*) FROM tracks" in sql for sql in statements))

            library.invalidate_library_query_cache(config)

            class WindowlessConnection:
                def __init__(self, connection):
                    self._connection = connection

                def execute(self, statement, values=()):
                    if "COUNT(*) OVER()" in statement:
                        raise library.sqlite3.OperationalError("window functions unavailable")
                    return self._connection.execute(statement, values)

            @contextmanager
            def windowless_connect(current_config):
                with original_connect(current_config) as connection:
                    yield WindowlessConnection(connection)

            with mock.patch.object(library, "library_db_connect", side_effect=windowless_connect):
                fallback = query_library_page(config, params)
            self.assertEqual(fallback["count"], 2)
            self.assertEqual([row["id"] for row in fallback["items"]], ["two"])

    def test_item_hydration_batches_long_internal_queues_and_preserves_requested_order(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = [self._item("track-%03d" % index, os.path.join(music_root, "%03d.flac" % index), "Track %03d" % index, index) for index in range(125)]
            save_items_to_sqlite(config, items, "test")
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            requested = ["track-%03d" % index for index in range(124, -1, -1)]
            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                hydrated = query_library_items_by_ids(config, requested + [requested[0]])
            self.assertEqual([item["id"] for item in hydrated], requested)
            self.assertEqual(len([statement for statement in statements if "WHERE id IN" in statement]), 2)

    def test_item_hydration_reuses_query_cache_and_returns_a_defensive_copy(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = [self._item("one", os.path.join(music_root, "one.flac"), "One", 1)]
            save_items_to_sqlite(config, items, "test")
            library.invalidate_library_query_cache(config)
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                first = query_library_items_by_ids(config, ["one"])
                first[0]["title"] = "Mutated"
                second = query_library_items_by_ids(config, ["one"])
            self.assertEqual(second[0]["title"], "One")
            self.assertEqual(len([statement for statement in statements if "WHERE id IN" in statement]), 1)

    def test_long_item_hydration_sequences_do_not_alias_the_truncated_page_cache_key(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = [
                self._item("track-%03d" % index, os.path.join(music_root, "%03d.flac" % index), "Track %03d" % index, index)
                for index in range(34)
            ]
            save_items_to_sqlite(config, items, "test")
            library.invalidate_library_query_cache(config)
            prefix = ["track-%03d" % index for index in range(32)]
            first_ids = prefix + ["track-032"]
            second_ids = prefix + ["track-033"]
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                first = query_library_items_by_ids(config, first_ids)
                second = query_library_items_by_ids(config, second_ids)
            self.assertEqual([item["id"] for item in first], first_ids)
            self.assertEqual([item["id"] for item in second], second_ids)
            self.assertEqual(len([statement for statement in statements if "WHERE id IN" in statement]), 2)

    def test_item_hydration_cache_is_invalidated_by_an_index_write(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            first = self._item("one", os.path.join(music_root, "one.flac"), "First", 1)
            save_items_to_sqlite(config, [first], "first")
            self.assertEqual(query_library_items_by_ids(config, ["one"])[0]["title"], "First")
            updated = self._item("one", os.path.join(music_root, "one.flac"), "Updated", 1)
            save_items_to_sqlite(config, [updated], "updated")
            self.assertEqual(query_library_items_by_ids(config, ["one"])[0]["title"], "Updated")

    def test_rescan_removes_stale_cue_index_when_a_stable_track_becomes_a_file(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            segment = self._item("stable", os.path.join(music_root, "album.ape"), "Segment", 1)
            segment.update({"cue_path": os.path.join(music_root, "album.cue"), "cue_track": 1, "cue_start": 0.0, "cue_end": 120.0})
            save_items_to_sqlite(config, [segment], "cue")
            with library_db_connect(config) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM cue_tracks").fetchone()[0], 1)

            replacement = self._item("stable", os.path.join(music_root, "track.flac"), "Track", 1)
            save_items_to_sqlite(config, [replacement], "file")
            with library_db_connect(config) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM cue_tracks").fetchone()[0], 0)

    def test_single_item_lookup_rejects_unbounded_or_non_text_ids_without_sqlite(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("single item lookup must not stringify arbitrary objects")

        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": []}
            with mock.patch.object(library, "library_db_connect") as connect:
                self.assertIsNone(library.query_library_item_by_id(config, Explosive()))
                self.assertIsNone(library.query_library_item_by_id(config, "x" * 513))
            connect.assert_not_called()

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

    def test_folder_search_walks_a_three_level_parent_chain(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            for folder in ("Deep/Middle/Leaf", "Deep/Middle/Sibling", "Deep/Other"):
                os.makedirs(os.path.join(music_root, *folder.split("/")))
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            hit = self._item("hit", os.path.join(music_root, "Deep", "Middle", "Leaf", "hit.flac"), "Hidden Needle", 1)
            miss = self._item("miss", os.path.join(music_root, "Deep", "Other", "miss.flac"), "Unrelated", 2)
            save_items_to_sqlite(config, [hit, miss], "test")

            # Every ancestor of the matched folder answers on its own level, and
            # no branch without a hit is pulled in by a relative's match.
            self.assertEqual(
                [row["name"] for row in query_library_folders(config, "", music_root, search="needle")],
                ["Deep"],
            )
            self.assertEqual(
                [row["name"] for row in query_library_folders(config, "Deep", music_root, search="needle")],
                ["Middle"],
            )
            page = query_library_folders(config, "Deep/Middle", music_root, "asc", 10, 0, "needle")
            self.assertEqual([row["name"] for row in page["folders"]], ["Leaf"])
            self.assertEqual(page["count"], 1)

    def test_folder_search_does_not_treat_folder_name_wildcards_as_patterns(self):
        # The per-folder test used to be `t.folder LIKE f.path || '/%'`, so a `_`
        # or `%` inside a directory name matched any sibling that happened to
        # differ at that position, and a folder was listed as holding a hit that
        # belonged to somebody else.  It only shows with a sub-directory, since
        # the pattern demands a path separator after the folder name.
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            for folder in ("Album_One/Disc 1", "AlbumXOne/Disc 1", "Album%Two/Disc 1", "AlbumQTwo/Disc 1"):
                os.makedirs(os.path.join(music_root, *folder.split("/")))
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = [
                self._item("hit-one", os.path.join(music_root, "AlbumXOne", "Disc 1", "one.flac"), "First Hit", 1),
                self._item("hit-two", os.path.join(music_root, "AlbumQTwo", "Disc 1", "two.flac"), "Second Hit", 2),
                self._item("quiet-one", os.path.join(music_root, "Album_One", "Disc 1", "three.flac"), "Unrelated", 3),
                self._item("quiet-two", os.path.join(music_root, "Album%Two", "Disc 1", "four.flac"), "Unrelated", 4),
            ]
            save_items_to_sqlite(config, items, "test")
            page = query_library_folders(config, "", music_root, "asc", 20, 0, "hit")
            self.assertEqual(sorted(row["name"] for row in page["folders"]), ["AlbumQTwo", "AlbumXOne"])
            self.assertEqual(page["count"], 2)

    def test_folder_search_does_not_let_one_root_answer_for_another(self):
        with tempfile.TemporaryDirectory() as root:
            first_root = os.path.join(root, "music-a")
            second_root = os.path.join(root, "music-b")
            for base in (first_root, second_root):
                os.makedirs(os.path.join(base, "Shared", "Inner"))
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [first_root, second_root]}
            items = [
                # Both roots own the same relative folder names, so the quiet one
                # still has to have rows for the match set to be able to leak.
                self._item("a-1", os.path.join(first_root, "Shared", "Inner", "quiet.flac"), "Unrelated", 1),
                self._item("b-1", os.path.join(second_root, "Shared", "Inner", "one.flac"), "Needle Track", 1),
            ]
            save_items_to_sqlite(config, items, "test")

            # Both roots hold the very same relative folder names, so the match
            # set has to stay joined on the root as well as the path.
            self.assertEqual(query_library_folders(config, "", first_root, search="needle"), [])
            self.assertEqual(query_library_folders(config, "Shared", first_root, search="needle"), [])
            self.assertEqual(
                [row["name"] for row in query_library_folders(config, "", second_root, search="needle")],
                ["Shared"],
            )

    def test_folder_search_in_like_mode_binds_the_match_term_once(self):
        # A term shorter than the trigram minimum falls back to the multi-column
        # LIKE condition, which carries one placeholder per searchable column.
        # All of them now bind inside the match CTE, ahead of the folder filters.
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            for folder in ("Ab/Cd", "Ab/Xy", "Zz/Cd"):
                os.makedirs(os.path.join(music_root, *folder.split("/")))
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = [
                self._item("hit", os.path.join(music_root, "Ab", "Cd", "hit.flac"), "hi there", 1),
                self._item("miss", os.path.join(music_root, "Ab", "Xy", "miss.flac"), "no match", 2),
                self._item("other", os.path.join(music_root, "Zz", "Cd", "other.flac"), "still no", 3),
            ]
            save_items_to_sqlite(config, items, "test")
            page = query_library_folders(config, "", music_root, "asc", 20, 0, "hi")
            self.assertEqual([row["name"] for row in page["folders"]], ["Ab"])
            self.assertEqual(page["count"], 1)
            deep = query_library_folders(config, "Ab", music_root, "asc", 20, 0, "hi")
            self.assertEqual([row["name"] for row in deep["folders"]], ["Cd"])

    def test_folder_search_cursor_continuation_carries_the_match_set(self):
        # The app sends a browse cursor and a search term together on the same
        # folder page, and that lane builds its statements from a different SQL
        # prefix than the offset lane.  Both have to carry the match set, or the
        # continuation fails on a table that only exists inside the CTE.
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            for name in ("Alpha", "Bravo", "Cinder", "Delta", "Echo"):
                os.makedirs(os.path.join(music_root, name, "Disc 1"))
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            items = []
            for index, name in enumerate(("Alpha", "Cinder", "Echo"), 1):
                items.append(
                    self._item(str(index), os.path.join(music_root, name, "Disc 1", "hit%d.flac" % index), "Needle %d" % index, index)
                )
            items.append(self._item("9", os.path.join(music_root, "Bravo", "Disc 1", "quiet.flac"), "Unrelated", 9))
            save_items_to_sqlite(config, items, "test")

            first = query_library_folders(config, "", music_root, "asc", 2, 0, "needle")
            self.assertEqual([row["name"] for row in first["folders"]], ["Alpha", "Cinder"])
            self.assertEqual(first["count"], 3)
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                library.invalidate_library_query_cache(config)
                second = query_library_folders(config, "", music_root, "asc", 2, 0, "needle", first["next_cursor"])
                cursor_statements = list(statements)
            self.assertEqual([row["name"] for row in second["folders"]], ["Echo"])
            self.assertEqual(second["count"], 3)
            folder_statements = [sql for sql in cursor_statements if "FROM folders f" in sql]
            self.assertTrue(folder_statements, cursor_statements)
            for sql in folder_statements:
                self.assertTrue(sql.startswith("WITH RECURSIVE matched_folder_paths"), sql[:90])

    def test_folder_search_resolves_matches_before_probing_the_directory(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(os.path.join(music_root, "Deep", "Middle"))
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            hit = self._item("hit", os.path.join(music_root, "Deep", "Middle", "hit.flac"), "Hidden Needle", 1)
            save_items_to_sqlite(config, [hit], "test")
            statements = []
            original_connect = library.library_db_connect

            @contextmanager
            def traced_connect(current_config):
                with original_connect(current_config) as connection:
                    connection.set_trace_callback(statements.append)
                    yield connection

            with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
                library.invalidate_library_query_cache(config)
                page = query_library_folders(config, "", music_root, "asc", 20, 0, "needle")
                folder_statements = list(statements)
            self.assertEqual([row["name"] for row in page["folders"]], ["Deep"])
            searched = [sql for sql in folder_statements if "FROM folders f" in sql]
            self.assertTrue(searched, folder_statements)
            plans = []
            with library_db_connect(config) as conn:
                for sql in searched:
                    # One pass turns the matching tracks into a folder set, then
                    # each folder row probes that set.  Asking `tracks` per folder
                    # row instead made SQLite walk the whole library root for
                    # every sibling: 2.2 s at 4000 top-level folders, 64.6 s at
                    # 16000, because only `root` was bound in the folder index.
                    self.assertTrue(sql.startswith("WITH RECURSIVE matched_folder_paths"), sql[:90])
                    plans.append(" | ".join(row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + sql)))
            for plan in plans:
                self.assertIn("matched_folder_paths", plan, plan)
                self.assertNotIn("idx_tracks_root_folder", plan, plan)

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

    def _folder_closure_state(self, config):
        """Read the folders table and the closure implied by the tracks table.

        Returns (rows, expected): both are keyed by (root, path); rows maps to
        (parent, track_count) as stored, expected maps to the parent and the
        number of tracks that lie in that folder or below it.
        """
        with library_db_connect(config) as conn:
            tracks = [
                (str(row["root"] or ""), str(row["folder"] or ""))
                for row in conn.execute("SELECT root, folder FROM tracks")
            ]
            rows = {
                (str(row["root"] or ""), str(row["path"])): (str(row["parent"] or ""), row["track_count"])
                for row in conn.execute("SELECT root, path, parent, track_count FROM folders")
            }
        expected = {}
        for root, folder in tracks:
            if not folder:
                continue
            parts = [part for part in folder.split("/") if part]
            for index in range(1, len(parts) + 1):
                entry = expected.setdefault((root, "/".join(parts[:index])), ["/".join(parts[: index - 1]), 0])
                entry[1] += 1
        return rows, {key: (value[0], value[1]) for key, value in expected.items()}

    def _folder_closure_violations(self, config):
        rows, expected = self._folder_closure_state(config)
        violations = []
        for key in sorted(expected):
            if key not in rows:
                violations.append("missing folder row: " + key[1])
                continue
            parent, count = rows[key]
            if parent != expected[key][0]:
                violations.append("wrong parent for: " + key[1])
            if parent and (key[0], parent) not in rows:
                violations.append("dangling parent of: " + key[1])
            if count != expected[key][1]:
                violations.append("track_count drift on: " + key[1])
        for key in sorted(set(rows) - set(expected)):
            violations.append("folder row without tracks: " + key[1])
        return violations

    def test_incremental_folder_refresh_keeps_the_track_folder_closure_complete(self):
        # The recursive folder-search closure walks the folders parent chain, so
        # a folder row missing for a folder that still holds tracks silently
        # drops every ancestor level above it. This pins the invariant that
        # incremental rebuilds cannot lag behind the tracks table.
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            for folder in ("A/Disc 1", "A/Deep/Mid/Leaf", "B"):
                os.makedirs(os.path.join(music_root, *folder.split("/")))
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            a1 = self._item("a1", os.path.join(music_root, "A", "Disc 1", "a1.flac"), "Alpha One", 1)
            a2 = self._item("a2", os.path.join(music_root, "A", "Deep", "Mid", "Leaf", "a2.flac"), "Alpha Two", 2)
            b1 = self._item("b1", os.path.join(music_root, "B", "b1.flac"), "Beat One", 3)
            save_items_to_sqlite(config, [a1, a2, b1], "test")
            self.assertEqual(self._folder_closure_violations(config), [])

            moves = []
            # Move into a brand new chain below an existing top-level folder.
            moved_deep = dict(a2)
            moved_deep["path"] = os.path.join(music_root, "A", "New", "Deeper", "a2.flac")
            moves.append([a1, moved_deep, b1])
            # Move into a top-level folder that does not exist yet.
            moved_top = dict(a1)
            moved_top["path"] = os.path.join(music_root, "Z", "Top", "a1.flac")
            moves.append([moved_top, moved_deep, b1])
            # Empty the brand new top-level folder again.
            moves.append([moved_deep, b1])
            # Add a three level chain whose top folder never existed.
            fresh = self._item("c1", os.path.join(music_root, "Q", "R", "S", "c1.flac"), "Cue One", 4)
            moves.append([moved_deep, b1, fresh])
            # Same folder name under a second library root.
            second_root = os.path.join(root, "music2")
            os.makedirs(os.path.join(second_root, "Shared", "Inner"))
            twin = self._item("d1", os.path.join(second_root, "Shared", "Inner", "d1.flac"), "Dee One", 5)
            two_roots = {"cache_dir": config["cache_dir"], "library_paths": [music_root, second_root]}
            for index, items in enumerate(moves):
                save_items_to_sqlite(config, items, "test")
                self.assertEqual(self._folder_closure_violations(config), [], "stage " + str(index))
            save_items_to_sqlite(two_roots, list(moves[-1]) + [twin], "test")
            self.assertEqual(self._folder_closure_violations(two_roots), [])

    def test_folder_search_after_an_incremental_move_lists_every_ancestor_level(self):
        # The user-visible shape of the same invariant: after a track moves into
        # a freshly created chain, each ancestor level has to answer on its own.
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(os.path.join(music_root, "A", "Deep", "Mid", "Leaf"))
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
            needle = self._item("hit", os.path.join(music_root, "A", "Deep", "Mid", "Leaf", "hit.flac"), "Hidden Needle", 1)
            save_items_to_sqlite(config, [needle], "test")
            moved = dict(needle)
            moved["path"] = os.path.join(music_root, "A", "New", "Deeper", "hit.flac")
            save_items_to_sqlite(config, [moved], "test")
            self.assertEqual(
                [row["name"] for row in query_library_folders(config, "", music_root, search="needle")],
                ["A"],
            )
            self.assertEqual(
                [row["name"] for row in query_library_folders(config, "A", music_root, search="needle")],
                ["New"],
            )
            page = query_library_folders(config, "A/New", music_root, "asc", 10, 0, "needle")
            self.assertEqual([row["name"] for row in page["folders"]], ["Deeper"])
            self.assertEqual(page["count"], 1)

    def test_relative_folder_text_never_breaks_the_subtree_prefix_scope(self):
        # _rebuild_folders_for_changes narrows a subtree with a single "top/%"
        # LIKE prefix, which only covers exactly the descendants while folder
        # text has no leading, trailing, or empty segment.
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            cases = [
                (os.path.join(music_root, "one.flac"), ""),
                (os.path.join(music_root, "A", "one.flac"), "A"),
                (os.path.join(music_root, "A", "B", "C", "one.flac"), "A/B/C"),
                (os.path.join(music_root, "A", "Disc 1", "one.flac"), "A/Disc 1"),
            ]
            for path, want in cases:
                folder = library.relative_folder_for_path(path, music_root)
                self.assertEqual(folder, want)
                self.assertNotIn("\\", folder)
                self.assertFalse(folder.startswith("/"))
                self.assertFalse(folder.endswith("/"))
                self.assertTrue(not folder or all(part for part in folder.split("/")))

    def _group_browse_config(self, root, albums=7, tracks_per_album=1):
        """Build a library whose group tables are big enough to page through."""
        music_root = os.path.join(root, "music")
        os.makedirs(music_root, exist_ok=True)
        config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music_root]}
        items = []
        for album in range(albums):
            for track in range(tracks_per_album):
                name = "t%d-%d" % (album, track)
                item = self._item(name, os.path.join(music_root, name + ".flac"), "Title " + name, track + 1)
                item["album"] = "Album %d" % album
                items.append(item)
        save_items_to_sqlite(config, items, "test")
        return config, items

    def _group_count(self, config, key):
        with library_db_connect(config) as conn:
            row = conn.execute("SELECT value FROM library_meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else row["value"]

    def _set_group_count(self, config, key, value):
        """Rewrite -- or delete -- one persisted count behind the scanner's back."""
        with library_db_connect(config) as conn:
            if value is None:
                conn.execute("DELETE FROM library_meta WHERE key = ?", (key,))
            else:
                conn.execute("INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)", (key, value))
        library.invalidate_library_query_cache(config)

    def _trace_group_browse(self, config, **kwargs):
        """Read one group page while recording every statement it issues."""
        statements = []
        original_connect = library.library_db_connect

        @contextmanager
        def traced_connect(current_config):
            with original_connect(current_config) as connection:
                connection.set_trace_callback(statements.append)
                yield connection

        with mock.patch.object(library, "library_db_connect", side_effect=traced_connect):
            page = query_library_groups(config, **kwargs)
        return page, [sql for sql in statements if not sql.lstrip().startswith("--")]

    def test_scan_persists_the_row_count_of_every_group_table(self):
        with tempfile.TemporaryDirectory() as root:
            config, _items = self._group_browse_config(root, albums=7)
            with library_db_connect(config) as conn:
                for table, key, expected in (
                    ("albums", "group_count_albums", 7),
                    ("artists", "group_count_artists", 1),
                    ("composers", "group_count_composers", 1),
                    ("genres", "group_count_genres", 1),
                ):
                    live = conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
                    self.assertEqual(int(self._group_count(config, key)), live)
                    self.assertEqual(live, expected)

    def test_unfiltered_group_pages_stop_paying_the_count_scan(self):
        with tempfile.TemporaryDirectory() as root:
            config, _items = self._group_browse_config(root, albums=7)
            for offset, want in ((0, 3), (3, 3), (6, 1)):
                page, statements = self._trace_group_browse(config, view="albums", limit=3, offset=offset)
                self.assertEqual(page["count"], 7)
                self.assertEqual(len(page["groups"]), want)
                self.assertEqual(page["offset"], offset)
                self.assertEqual(
                    [group["name"] for group in page["groups"]],
                    ["Album %d" % index for index in range(offset, offset + want)],
                )
                self.assertFalse(any("SELECT COUNT(*) FROM albums" in sql for sql in statements), statements)
                self.assertTrue(any("LIMIT 4 OFFSET %d" % offset in sql for sql in statements), statements)
                self.assertEqual(page.get("has_more"), offset != 6)
                self.assertEqual(self._group_count(config, "group_count_albums"), "7")

    def test_a_small_persisted_group_count_cannot_truncate_the_list(self):
        # The risk named in the item: a total that drifted small makes the
        # client believe the last page arrived.  The look-ahead row has to
        # refute it, the page has to report the real total, and the repair has
        # to be written back so the next page stops refuting it.
        with tempfile.TemporaryDirectory() as root:
            config, _items = self._group_browse_config(root, albums=7)
            self._set_group_count(config, "group_count_albums", "1")
            page, statements = self._trace_group_browse(config, view="albums", limit=3, offset=0)
            self.assertEqual(page["count"], 7)
            self.assertTrue(page.get("has_more"))
            self.assertTrue(any("SELECT COUNT(*) FROM albums" in sql for sql in statements), statements)
            self.assertEqual(self._group_count(config, "group_count_albums"), "7")
            page, statements = self._trace_group_browse(config, view="albums", limit=3, offset=3)
            self.assertEqual(page["count"], 7)
            self.assertFalse(any("SELECT COUNT(*) FROM albums" in sql for sql in statements), statements)

    def test_a_full_group_page_repairs_a_persisted_count_that_drifted_high(self):
        # A page that is exactly as large as its limit, with the look-ahead row
        # missing, proves the table ended there -- so the stored total has to
        # come down to the rows actually read rather than keep claiming more.
        with tempfile.TemporaryDirectory() as root:
            config, _items = self._group_browse_config(root, albums=7)
            self._set_group_count(config, "group_count_albums", "99")
            page, statements = self._trace_group_browse(config, view="albums", limit=7, offset=0)
            self.assertEqual(page["count"], 7)
            self.assertFalse(page.get("has_more"))
            self.assertEqual(len(page["groups"]), 7)
            self.assertFalse(any("SELECT COUNT(*) FROM albums" in sql for sql in statements), statements)
            self.assertEqual(self._group_count(config, "group_count_albums"), "7")

    def test_a_group_page_without_a_persisted_count_heals_the_key(self):
        # An index written by an older build has no key at all, so the first
        # page keeps the old two-statement shape and stores what it learned.
        with tempfile.TemporaryDirectory() as root:
            config, _items = self._group_browse_config(root, albums=7)
            self._set_group_count(config, "group_count_albums", None)
            self.assertIsNone(self._group_count(config, "group_count_albums"))
            page, statements = self._trace_group_browse(config, view="albums", limit=3, offset=0)
            self.assertEqual(page["count"], 7)
            self.assertEqual(len([sql for sql in statements if "SELECT COUNT(*) FROM albums" in sql]), 1)
            self.assertEqual(self._group_count(config, "group_count_albums"), "7")
            page, statements = self._trace_group_browse(config, view="albums", limit=3, offset=3)
            self.assertEqual(page["count"], 7)
            self.assertFalse(any("SELECT COUNT(*) FROM albums" in sql for sql in statements), statements)

    def test_a_searched_group_page_never_reads_the_persisted_group_count(self):
        # A search counts a JOIN, not the whole table, so the stored total is
        # both wrong as an answer and wrong as a write-back.
        with tempfile.TemporaryDirectory() as root:
            config, _items = self._group_browse_config(root, albums=7)
            self._set_group_count(config, "group_count_albums", "99")
            page, statements = self._trace_group_browse(
                config, view="albums", limit=3, offset=0, search="album 1"
            )
            self.assertEqual(page["count"], 1)
            self.assertEqual([group["name"] for group in page["groups"]], ["Album 1"])
            self.assertFalse(
                any("FROM library_meta WHERE key = 'group_count_albums'" in sql for sql in statements),
                statements,
            )
            self.assertEqual(self._group_count(config, "group_count_albums"), "99")

    def test_each_group_view_only_touches_its_own_persisted_count(self):
        # Four views, four keys: a view that read or repaired somebody else's
        # key would silently shrink another view's list while still looking
        # correct on its own page.
        with tempfile.TemporaryDirectory() as root:
            config, _items = self._group_browse_config(root, albums=7)
            for view, key, want in (
                ("albums", "group_count_albums", "7"),
                ("artists", "group_count_artists", "1"),
                ("composers", "group_count_composers", "1"),
                ("genres", "group_count_genres", "1"),
            ):
                page, statements = self._trace_group_browse(config, view=view, limit=3, offset=0)
                self.assertEqual(page["count"], int(want), view)
                self.assertEqual(self._group_count(config, key), want, view)
                self.assertFalse(
                    any("SELECT COUNT(*) FROM " in sql for sql in statements),
                    (view, statements),
                )
            with library_db_connect(config) as conn:
                stored = {
                    row["key"]: row["value"]
                    for row in conn.execute("SELECT key, value FROM library_meta").fetchall()
                }
            self.assertEqual(stored.get("group_count_albums"), "7")
            self.assertEqual(stored.get("group_count_artists"), "1")
            self.assertEqual(stored.get("group_count_composers"), "1")
            self.assertEqual(stored.get("group_count_genres"), "1")

    def test_the_persisted_count_writer_only_accepts_its_own_contract(self):
        # A browse read borrows a pooled handle it did not open, so a repair
        # write must never raise and must never store a number it cannot prove.
        with tempfile.TemporaryDirectory() as root:
            config, _items = self._group_browse_config(root, albums=2)
            key = "group_count_albums"

            class Broken:
                def execute(self, *args, **kwargs):
                    raise RuntimeError("handle gone")

            with library_db_connect(config) as conn:
                for value in ("", None, -1, True, 1.0, "3"):
                    self.assertFalse(library._save_library_meta_count(conn, key, value), repr(value))
                for bad_key in ("", None, 7):
                    self.assertFalse(library._save_library_meta_count(conn, bad_key, 3), repr(bad_key))
                self.assertFalse(library._save_library_meta_count(Broken(), key, 3))
                row = conn.execute("SELECT value FROM library_meta WHERE key = ?", (key,)).fetchone()
                self.assertEqual(row["value"], "2")
                self.assertTrue(library._save_library_meta_count(conn, key, 5))
                row = conn.execute("SELECT value FROM library_meta WHERE key = ?", (key,)).fetchone()
                self.assertEqual(row["value"], "5")
                self.assertTrue(library._save_library_meta_count(conn, key, 0))
                row = conn.execute("SELECT value FROM library_meta WHERE key = ?", (key,)).fetchone()
                self.assertEqual(row["value"], "0")
            library.invalidate_library_query_cache(config)

    def test_an_incremental_rescan_refreshes_the_persisted_group_count(self):
        with tempfile.TemporaryDirectory() as root:
            config, _items = self._group_browse_config(root, albums=7)
            self.assertEqual(self._group_count(config, "group_count_albums"), "7")
            extra = self._item("t7-0", os.path.join(root, "music", "t7-0.flac"), "Title t7-0", 1)
            extra["album"] = "Album 7"
            # A scan replaces the index, so an incremental rescan has to resend
            # the tracks it still holds alongside the new one.
            save_items_to_sqlite(config, _items + [extra], "test")
            self.assertEqual(self._group_count(config, "group_count_albums"), "8")
            page, statements = self._trace_group_browse(config, view="albums", limit=3, offset=0)
            self.assertEqual(page["count"], 8)
            self.assertFalse(any("SELECT COUNT(*) FROM albums" in sql for sql in statements), statements)

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
