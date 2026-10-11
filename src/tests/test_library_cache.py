import json
import ctypes
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from unittest.mock import patch

sys.path.insert(0, "app/server")

import cover_cache
import library
from metadata_unavailable_policy import local_cached_projection, local_lyrics_projection


class LibraryCacheTests(unittest.TestCase):
    def test_empty_directory_request_lists_browsable_roots(self):
        with mock.patch.object(library, "browsable_roots", return_value=["/vol1"] ) as roots:
            self.assertEqual(library.list_music_directories(""), ["/vol1"])
            roots.assert_called_once_with()

    def test_directory_listing_is_bounded_and_alphabetical(self):
        with tempfile.TemporaryDirectory() as root:
            entries = [os.path.join(root, "dir-%04d" % index) for index in range(600)]
            for path in entries:
                os.makedirs(path)
            listed = library.list_music_directories(root)

            self.assertEqual(len(listed), 512)
            self.assertEqual(listed, sorted(listed, key=lambda value: value.lower()))
            self.assertEqual(listed[0], os.path.join(root, "dir-0000"))
            self.assertEqual(listed[-1], os.path.join(root, "dir-0511"))

    def test_database_cache_identity_changes_when_wal_changes(self):
        database_stat = mock.Mock(st_dev=1, st_ino=2, st_mtime_ns=3, st_size=4)
        first_wal_stat = mock.Mock(st_dev=5, st_ino=6, st_mtime_ns=7, st_size=8)
        second_wal_stat = mock.Mock(st_dev=5, st_ino=6, st_mtime_ns=9, st_size=10)

        with patch.object(library.os, "stat", side_effect=[database_stat, first_wal_stat]):
            first = library._library_database_cache_identity("library.sqlite3")
        with patch.object(library.os, "stat", side_effect=[database_stat, second_wal_stat]):
            second = library._library_database_cache_identity("library.sqlite3")

        self.assertEqual(first, (1, 2, 3, 4, 5, 6, 7, 8))
        self.assertNotEqual(first, second)

    def test_database_cache_identity_handles_missing_wal_file(self):
        database_stat = mock.Mock(st_dev=1, st_ino=2, st_mtime_ns=3, st_size=4)
        with patch.object(library.os, "stat", side_effect=[database_stat, OSError("no WAL")]):
            identity = library._library_database_cache_identity("library.sqlite3")

        self.assertEqual(identity, (1, 2, 3, 4, 0, 0, 0, 0))

    def test_stop_library_watcher_wakes_and_joins_long_sleep(self):
        thread = mock.Mock()
        thread.is_alive.return_value = False
        original = library.LIBRARY_WATCH_THREAD
        try:
            library.LIBRARY_WATCH_THREAD = thread
            library.LIBRARY_WATCH_STOP_EVENT.clear()
            library.stop_library_watcher(wait=True, timeout=1.5)
            self.assertTrue(library.LIBRARY_WATCH_STOP_EVENT.is_set())
            thread.join.assert_called_once_with(1.5)
        finally:
            library.LIBRARY_WATCH_THREAD = original
            library.LIBRARY_WATCH_STOP_EVENT.clear()

    def test_library_shutdown_waits_fall_back_for_nonfinite_timeouts(self):
        scan_thread = mock.Mock()
        watcher_thread = mock.Mock()
        original_scan = library.SCAN_WORKER_THREAD
        original_watcher = library.LIBRARY_WATCH_THREAD
        try:
            library.SCAN_WORKER_THREAD = scan_thread
            library.LIBRARY_WATCH_THREAD = watcher_thread
            library.shutdown_library_refresh(wait=True, timeout=float("nan"))
            library.stop_library_watcher(wait=True, timeout=float("inf"))
            scan_thread.join.assert_called_once_with(5.0)
            watcher_thread.join.assert_called_once_with(2.0)
        finally:
            library.SCAN_WORKER_THREAD = original_scan
            library.LIBRARY_WATCH_THREAD = original_watcher
            library.SCAN_CANCEL_EVENT.clear()
            library.LIBRARY_WATCH_STOP_EVENT.clear()

    def test_watcher_does_not_clear_stop_signal_after_shutdown_race(self):
        library.LIBRARY_WATCH_STOP_EVENT.set()
        try:
            with patch.object(library, "LibraryChangeMonitor") as monitor_class:
                library.watch_library({"library_paths": []})
                monitor_class.assert_not_called()
        finally:
            library.LIBRARY_WATCH_STOP_EVENT.clear()

    def test_start_library_watcher_rolls_back_when_thread_start_fails(self):
        original_thread = library.LIBRARY_WATCH_THREAD
        library.LIBRARY_WATCH_THREAD = None
        library.LIBRARY_WATCH_STOP_EVENT.clear()
        try:
            with patch.object(library.threading.Thread, "start", side_effect=RuntimeError("no threads")):
                with self.assertRaisesRegex(RuntimeError, "no threads"):
                    library.start_library_watcher({"library_paths": []})
            self.assertIsNone(library.LIBRARY_WATCH_THREAD)
            self.assertTrue(library.LIBRARY_WATCH_STOP_EVENT.is_set())
        finally:
            library.LIBRARY_WATCH_THREAD = original_thread
            library.LIBRARY_WATCH_STOP_EVENT.clear()

    def test_concurrent_watcher_start_reserves_a_single_thread(self):
        original_thread = library.LIBRARY_WATCH_THREAD
        library.LIBRARY_WATCH_THREAD = None
        library.LIBRARY_WATCH_STOP_EVENT.clear()
        entered = threading.Event()
        release = threading.Event()
        created = []
        real_thread = threading.Thread

        class DelayedThread:
            def __init__(self, **_kwargs):
                self.started = False
                created.append(self)

            def start(self):
                entered.set()
                release.wait(1)
                self.started = True

            def is_alive(self):
                return self.started

        try:
            with patch.object(library.threading, "Thread", DelayedThread):
                first = real_thread(target=library.start_library_watcher, args=({"library_paths": []},))
                first.start()
                self.assertTrue(entered.wait(1))
                second = real_thread(target=library.start_library_watcher, args=({"library_paths": []},))
                second.start()
                release.set()
                first.join(1)
                second.join(1)
            self.assertEqual(len(created), 1)
        finally:
            library.LIBRARY_WATCH_THREAD = original_thread
            library.LIBRARY_WATCH_STOP_EVENT.clear()

    def test_watcher_restart_uses_a_private_stop_event(self):
        original_thread = library.LIBRARY_WATCH_THREAD
        original_stop = library.LIBRARY_WATCH_CURRENT_STOP_EVENT
        library.LIBRARY_WATCH_THREAD = None
        library.LIBRARY_WATCH_CURRENT_STOP_EVENT = None
        library.LIBRARY_WATCH_STOP_EVENT.clear()
        created = []

        class FakeThread:
            def __init__(self, target, args, daemon):
                self.target = target
                self.args = args
                self.daemon = daemon
                created.append(self)

            def start(self):
                return None

            def is_alive(self):
                return False

        try:
            with patch.object(library.threading, "Thread", FakeThread):
                library.start_library_watcher({"library_paths": []})
                first_event = created[0].args[1]
                library.stop_library_watcher(wait=False)
                library.start_library_watcher({"library_paths": []})
                second_event = created[1].args[1]
            self.assertIsNot(first_event, second_event)
            self.assertTrue(first_event.is_set())
            self.assertFalse(second_event.is_set())
        finally:
            library.LIBRARY_WATCH_THREAD = original_thread
            library.LIBRARY_WATCH_CURRENT_STOP_EVENT = original_stop
            library.LIBRARY_WATCH_STOP_EVENT.clear()

    def test_shutdown_library_refresh_cancels_and_joins_worker(self):
        thread = mock.Mock()
        original = library.SCAN_WORKER_THREAD
        old_running = library.SCAN_STATE["running"]
        old_queued = library.SCAN_STATE["queued"]
        try:
            library.SCAN_WORKER_THREAD = thread
            library.SCAN_STATE["running"] = True
            library.SCAN_STATE["queued"] = False
            library.SCAN_CANCEL_EVENT.clear()
            library.shutdown_library_refresh(wait=True, timeout=1.5)
            self.assertTrue(library.SCAN_CANCEL_EVENT.is_set())
            thread.join.assert_called_once_with(1.5)
        finally:
            library.SCAN_WORKER_THREAD = original
            library.SCAN_STATE["running"] = old_running
            library.SCAN_STATE["queued"] = old_queued
            library.SCAN_CANCEL_EVENT.clear()

    def test_cache_failure_status_is_bounded_and_separates_load_and_save(self):
        original = dict(library.LIBRARY_CACHE_FAILURES)
        try:
            library.LIBRARY_CACHE_FAILURES.update({"load": 3, "save": 7})
            self.assertEqual(library.library_cache_failure_status(), {"load": 3, "save": 7})
            library.LIBRARY_CACHE_FAILURES["load"] = 2_147_483_647
            library._record_library_cache_failure("load")
            self.assertEqual(library.library_cache_failure_status()["load"], 2_147_483_647)
            library._record_library_cache_failure("unknown")
            self.assertEqual(library.library_cache_failure_status()["save"], 7)
        finally:
            library.LIBRARY_CACHE_FAILURES.clear()
            library.LIBRARY_CACHE_FAILURES.update(original)

    def test_library_status_handles_missing_library_path(self):
        import library
        original_items = library.MUSIC_CACHE["items"]
        with tempfile.TemporaryDirectory() as root:
            try:
                library.MUSIC_CACHE["items"] = []
                status = library.library_status({"cache_dir": root})
                self.assertIn("library_path", status)
                self.assertGreaterEqual(status["count"], 0)
                self.assertEqual(set(status["storage"]), {"database_bytes", "wal_bytes", "shm_bytes", "total_bytes"})
            finally:
                library.MUSIC_CACHE["items"] = original_items

    def test_library_summary_cache_reuses_short_lived_sqlite_summary(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0], exist_ok=True)
            library.save_items_to_sqlite(config, [], "summary-cache")
            with patch.object(library, "library_db_connect", wraps=library.library_db_connect) as connect:
                first = library.library_summary_from_sqlite(config)
                second = library.library_summary_from_sqlite(config)
            self.assertEqual(first, second)
            self.assertEqual(connect.call_count, 1)

    def test_library_summary_cache_is_invalidated_when_wal_identity_changes(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0], exist_ok=True)
            library.save_items_to_sqlite(config, [], "summary-wal")
            identities = [
                ((1, 2, 3, 4), (5, 6, 7, 8)),
                ((1, 2, 3, 4), (5, 6, 9, 10)),
            ]
            with patch.object(library, "_library_database_cache_identity", side_effect=identities), \
                    patch.object(library, "library_db_connect", wraps=library.library_db_connect) as connect:
                first = library.library_summary_from_sqlite(config)
                second = library.library_summary_from_sqlite(config)
            self.assertEqual(first, second)
            self.assertEqual(connect.call_count, 2)
            library.invalidate_library_query_cache(config)

    def test_library_summary_cache_coalesces_concurrent_sqlite_reads(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0], exist_ok=True)
            library.save_items_to_sqlite(config, [], "summary-single-flight")
            database = os.path.abspath(library.library_db_path(config))
            original_connect = library.library_db_connect
            connected = threading.Event()
            release = threading.Event()
            calls = []
            results = []

            def delayed_connect(*args, **kwargs):
                calls.append(1)
                connected.set()
                release.wait(2.0)
                return original_connect(*args, **kwargs)

            def read_summary():
                results.append(library.library_summary_from_sqlite(config))

            with patch.object(library, "library_db_connect", side_effect=delayed_connect):
                first = threading.Thread(target=read_summary)
                first.start()
                self.assertTrue(connected.wait(1.0))
                second = threading.Thread(target=read_summary)
                second.start()
                # The second caller must join the active read before the
                # leader is allowed to populate the short-lived cache.
                self.assertIn(database, library.LIBRARY_SUMMARY_INFLIGHT)
                release.set()
                first.join(2.0)
                second.join(2.0)

            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual(len(calls), 1)
            self.assertEqual(results, [{"count": 0, "dsd_count": 0, "signature": "summary-single-flight"}] * 2)
            self.assertNotIn(database, library.LIBRARY_SUMMARY_INFLIGHT)
            library.invalidate_library_query_cache(config)

    def test_library_summary_cache_is_invalidated_by_index_write(self):
        with tempfile.TemporaryDirectory() as root:
            music = os.path.join(root, "music")
            os.makedirs(music, exist_ok=True)
            config = {"cache_dir": root, "library_paths": [music]}
            library.save_items_to_sqlite(config, [], "summary-v1")
            self.assertEqual(library.library_summary_from_sqlite(config)["count"], 0)
            item = {
                "id": "one", "path": os.path.join(music, "one.flac"),
                "title": "One", "artist": "Artist", "album": "Album",
                "format": "FLAC", "mime": "audio/flac", "duration": 1,
            }
            library.save_items_to_sqlite(config, [item], "summary-v2")
            summary = library.library_summary_from_sqlite(config)
            self.assertEqual(summary["count"], 1)
            self.assertEqual(summary["signature"], "summary-v2")

    def test_library_summary_cache_rejects_replaced_database_file(self):
        with tempfile.TemporaryDirectory() as root:
            music = os.path.join(root, "music")
            os.makedirs(music, exist_ok=True)
            config = {"cache_dir": root, "library_paths": [music]}
            library.save_items_to_sqlite(config, [], "replace-v1")
            self.assertEqual(library.library_summary_from_sqlite(config)["signature"], "replace-v1")
            db_path = library.library_db_path(config)
            replacement_root = os.path.join(root, "replacement")
            os.makedirs(replacement_root, exist_ok=True)
            replacement_config = {"cache_dir": replacement_root, "library_paths": [music]}
            library.save_items_to_sqlite(replacement_config, [{"id": "one", "path": os.path.join(music, "one.flac"), "title": "One", "artist": "A", "album": "B", "format": "FLAC", "mime": "audio/flac", "duration": 1}], "replace-v2")
            replacement_db = library.library_db_path(replacement_config)
            # Bypass the normal write/invalidation path to model an external
            # index replacement while the process is still serving requests.
            shutil.copyfile(replacement_db, db_path)
            self.assertEqual(library.library_summary_from_sqlite(config)["signature"], "replace-v2")

    def test_library_summary_cache_has_a_bounded_database_entry_limit(self):
        original = dict(library.LIBRARY_SUMMARY_CACHE)
        try:
            library.LIBRARY_SUMMARY_CACHE.clear()
            for index in range(library.LIBRARY_SUMMARY_CACHE_LIMIT):
                library.LIBRARY_SUMMARY_CACHE[f"db-{index}"] = (time.monotonic(), {"count": index})
            # The production insertion path must evict the oldest entry once
            # the configured bound is reached; keep the assertion tied to the
            # public constant so future tuning remains explicit.
            self.assertEqual(len(library.LIBRARY_SUMMARY_CACHE), library.LIBRARY_SUMMARY_CACHE_LIMIT)
            with tempfile.TemporaryDirectory() as root:
                config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
                os.makedirs(config["library_paths"][0], exist_ok=True)
                library.save_items_to_sqlite(config, [], "bounded")
                library.library_summary_from_sqlite(config)
            self.assertLessEqual(len(library.LIBRARY_SUMMARY_CACHE), library.LIBRARY_SUMMARY_CACHE_LIMIT)
            # A legacy process may have left an oversized map; the next new
            # insertion must converge all the way back to the configured cap.
        finally:
            library.LIBRARY_SUMMARY_CACHE.clear()
            library.LIBRARY_SUMMARY_CACHE.update(original)

    def test_schema_and_search_mode_maps_evict_retired_database_roots(self):
        original_schema = dict(library.LIBRARY_SCHEMA_READY)
        original_modes = dict(library.LIBRARY_SEARCH_INDEX_MODE)
        try:
            library.LIBRARY_SCHEMA_READY.clear()
            library.LIBRARY_SEARCH_INDEX_MODE.clear()
            for index in range(library.LIBRARY_SCHEMA_READY_LIMIT + 1):
                library._bounded_database_state_put(
                    library.LIBRARY_SCHEMA_READY, "schema-%d" % index, (1, index),
                    library.LIBRARY_SCHEMA_READY_LIMIT,
                )
            for index in range(library.LIBRARY_SEARCH_INDEX_MODE_LIMIT + 1):
                library._bounded_database_state_put(
                    library.LIBRARY_SEARCH_INDEX_MODE, "mode-%d" % index, "like",
                    library.LIBRARY_SEARCH_INDEX_MODE_LIMIT,
                )
            self.assertEqual(len(library.LIBRARY_SCHEMA_READY), library.LIBRARY_SCHEMA_READY_LIMIT)
            self.assertEqual(len(library.LIBRARY_SEARCH_INDEX_MODE), library.LIBRARY_SEARCH_INDEX_MODE_LIMIT)
            self.assertNotIn("schema-0", library.LIBRARY_SCHEMA_READY)
            self.assertNotIn("mode-0", library.LIBRARY_SEARCH_INDEX_MODE)
        finally:
            library.LIBRARY_SCHEMA_READY.clear()
            library.LIBRARY_SCHEMA_READY.update(original_schema)
            library.LIBRARY_SEARCH_INDEX_MODE.clear()
            library.LIBRARY_SEARCH_INDEX_MODE.update(original_modes)

    def test_library_paths_use_safe_default_cache_directory(self):
        self.assertTrue(library.library_db_path({}).endswith("library.sqlite3"))
        self.assertTrue(library.library_cache_path({}).endswith("library.json"))

    def test_library_storage_status_counts_sqlite_sidecars_without_exposing_paths(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root}
            db_path = library.library_db_path(config)
            with open(db_path, "wb") as handle:
                handle.write(b"db")
            with open(db_path + "-wal", "wb") as handle:
                handle.write(b"wal!")
            status = library.library_storage_status(config)
            self.assertEqual(status, {"database_bytes": 2, "wal_bytes": 4, "shm_bytes": 0, "total_bytes": 6})
            self.assertNotIn(root, str(status))
            self.assertEqual(library.library_storage_status({"cache_dir": "x" * 5000})["total_bytes"], 0)

    def test_library_status_projects_invalid_server_port(self):
        status = library.library_status({"cache_dir": ".", "server_port": object()})
        self.assertEqual(status["server_port"], 53199)

    def test_library_status_handles_missing_scan_state_fields(self):
        original = library.SCAN_STATE
        try:
            library.SCAN_STATE = {"result": "x"}
            status = library.library_status({"cache_dir": "."})
            self.assertFalse(status["scanning"])
            self.assertEqual(status["last_error"], "")
            self.assertEqual(status["last_scan"], 0.0)
            self.assertEqual(status["scanned"], 0)
        finally:
            library.SCAN_STATE = original

    def test_library_status_bounds_corrupt_scan_state_text_and_time(self):
        original = library.SCAN_STATE
        try:
            library.SCAN_STATE = {
                "running": object(),
                "result": "r" * 200,
                "last_error": "e" * 1000,
                "last_scan": float("nan"),
                "current": "c" * 1000,
                "phase": object(),
            }
            status = library.library_status({"cache_dir": "."})
            self.assertFalse(status["scanning"])
            self.assertEqual(len(status["result"]), 32)
            self.assertEqual(len(status["last_error"]), 512)
            self.assertEqual(status["last_scan"], 0.0)
            self.assertEqual(len(status["current"]), 512)
            self.assertEqual(status["phase"], "")
        finally:
            library.SCAN_STATE = original

    def test_library_status_does_not_truthiness_coerce_scan_state_booleans(self):
        original = library.SCAN_STATE
        try:
            library.SCAN_STATE = {"running": "false", "queued": "true", "cancelled": 1}
            status = library.library_status({"cache_dir": "."})
            self.assertFalse(status["scanning"])
            self.assertFalse(status["queued"])
            self.assertFalse(status["cancelled"])
        finally:
            library.SCAN_STATE = original

    def test_malformed_json_shape_is_ignored_without_interrupting_cache_restore(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0], exist_ok=True)
            cache_path = library.library_cache_path(config)
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as handle:
                handle.write("[]")
            with mock.patch.object(library, "library_summary_from_sqlite", return_value=None):
                library.load_library_cache(config)
    def tearDown(self):
        library.SCAN_CANCEL_EVENT.clear()
        library.SCAN_STATE["running"] = False
        library.SCAN_STATE["queued"] = False
        library.SCAN_STATE["queued_force"] = False
        library.SCAN_STATE["worker_active"] = False

    def test_merge_library_paths_uses_scan_path_identity(self):
        with tempfile.TemporaryDirectory() as root:
            music = os.path.join(root, "music")
            os.makedirs(music)
            merged = library.merge_library_paths([music], [os.path.join(music, "."), "", music])
            self.assertEqual(merged, [library.canonical_library_path(music)])
            config = {}
            library.apply_library_paths(config, merged)
            self.assertEqual(config["library_paths"], merged)
            self.assertEqual(config["library_path"], merged[0])

    def test_unchanged_refresh_does_not_rewrite_existing_sqlite_index(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0])
            library.save_items_to_sqlite(config, [], "same-signature")
            old_signature = library.FS_CACHE["signature"]
            try:
                library.FS_CACHE["signature"] = "same-signature"
                with patch.object(library, "scan_libraries", return_value=([], "same-signature")), patch.object(library, "save_library_cache") as save_cache:
                    library.refresh_library_if_changed(config, force=True)
                    save_cache.assert_not_called()
            finally:
                library.FS_CACHE["signature"] = old_signature

    def test_unchanged_background_refresh_does_not_hydrate_full_library(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0])
            old_items = library.MUSIC_CACHE["items"]
            old_signature = library.FS_CACHE["signature"]
            try:
                library.MUSIC_CACHE["items"] = []
                library.FS_CACHE["signature"] = "same-signature"
                with patch.object(library, "library_signature_for_config", return_value="same-signature"), \
                     patch.object(library, "load_items_from_sqlite", side_effect=AssertionError("full library loaded")), \
                     patch.object(library, "scan_libraries", side_effect=AssertionError("full scan started")):
                    library.refresh_library_if_changed(config, force=False)
            finally:
                library.MUSIC_CACHE["items"] = old_items
                library.FS_CACHE["signature"] = old_signature

    def test_unchanged_refresh_rebuilds_missing_sqlite_index(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0])
            old_items = library.MUSIC_CACHE["items"]
            old_signature = library.FS_CACHE["signature"]
            try:
                library.MUSIC_CACHE["items"] = [{"id": "cached"}]
                library.FS_CACHE["signature"] = "same-signature"
                with patch.object(library, "library_signature_for_config", return_value="same-signature"), \
                     patch.object(library, "scan_libraries", return_value=([{"id": "rebuilt"}], "same-signature")) as scan, \
                     patch.object(library, "save_library_cache") as save_cache:
                    library.refresh_library_if_changed(config, force=False)
                scan.assert_called_once()
                save_cache.assert_called_once()
            finally:
                library.MUSIC_CACHE["items"] = old_items
                library.FS_CACHE["signature"] = old_signature

    def test_clean_change_monitor_skips_the_o_n_signature_walk(self):
        class CleanMonitor:
            available = True

            def generation(self):
                return 7

            def needs_scan(self):
                return False

        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0])
            old_signature = library.FS_CACHE["signature"]
            try:
                library.FS_CACHE["signature"] = "same-signature"
                with patch.object(library, "library_signature_for_config", side_effect=AssertionError("O(n) signature walk started")), \
                     patch.object(library, "scan_libraries", side_effect=AssertionError("full scan started")):
                    library.refresh_library_if_changed(config, change_monitor=CleanMonitor())
            finally:
                library.FS_CACHE["signature"] = old_signature

    def test_dirty_change_monitor_is_cleared_only_after_signature_confirmation(self):
        class DirtyMonitor:
            available = True

            def __init__(self):
                self.cleaned = []

            def generation(self):
                return 11

            def needs_scan(self):
                return True

            def mark_clean(self, generation):
                self.cleaned.append(generation)
                return True

        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0])
            library.save_items_to_sqlite(config, [], "same-signature")
            monitor = DirtyMonitor()
            old_signature = library.FS_CACHE["signature"]
            try:
                library.FS_CACHE["signature"] = "same-signature"
                with patch.object(library, "library_signature_for_config", return_value="same-signature"), \
                     patch.object(library, "scan_libraries", side_effect=AssertionError("full scan started")):
                    library.refresh_library_if_changed(config, change_monitor=monitor)
                self.assertEqual(monitor.cleaned, [11])
            finally:
                library.FS_CACHE["signature"] = old_signature

    def test_inotify_event_parser_marks_supported_files_and_new_directories_dirty(self):
        monitor = library.LibraryChangeMonitor(["/music"])
        monitor.available = True
        monitor._dirty = False
        monitor._watches[3] = "/music"
        added = []
        monitor._add_tree = added.append

        def event(mask, name):
            encoded = name.encode("utf-8") + b"\0"
            return monitor.EVENT_HEADER.pack(3, mask, 0, len(encoded)) + encoded

        monitor._handle_events(event(monitor.IN_CLOSE_WRITE, "track.flac"))
        self.assertTrue(monitor.needs_scan())
        monitor.mark_clean(monitor.generation())
        monitor._handle_events(event(monitor.IN_CREATE | monitor.IN_ISDIR, "new-album"))
        self.assertEqual(added, [os.path.join("/music", "new-album")])
        self.assertTrue(monitor.needs_scan())

    def test_inotify_watch_ceiling_avoids_exhausting_host_watch_quota(self):
        monitor = library.LibraryChangeMonitor(["/music"])
        monitor._fd = 7
        monitor._libc = mock.Mock()
        monitor._watch_budget = 64
        with monitor._lock:
            monitor._watches = {index: "/music/%d" % index for index in range(64)}
        with self.assertRaises(OSError):
            monitor._watch_path("/music/too-many")
        monitor._libc.inotify_add_watch.assert_not_called()

    def test_inotify_watch_ceiling_disables_partial_runtime_monitoring(self):
        monitor = library.LibraryChangeMonitor(["/music"])
        monitor.available = True
        monitor._watches[3] = "/music"
        monitor._add_tree = mock.Mock(side_effect=OSError("watch limit"))
        encoded = b"new-album\0"
        payload = monitor.EVENT_HEADER.pack(
            3, monitor.IN_CREATE | monitor.IN_ISDIR, 0, len(encoded)
        ) + encoded

        monitor._handle_events(payload)

        self.assertTrue(monitor.needs_scan())
        self.assertFalse(monitor.available)

    def test_inotify_monitor_stop_waits_for_old_thread_and_restart_clears_stop(self):
        monitor = library.LibraryChangeMonitor(["/music"])
        old_thread = mock.Mock()
        old_thread.is_alive.return_value = False
        monitor._thread = old_thread
        monitor._stop.set()
        monitor.stop()
        old_thread.join.assert_called_once()
        self.assertTrue(monitor._stop.is_set())

        with patch.object(os, "name", "posix"), \
             patch.object(os.path, "isdir", return_value=True), \
             patch.object(monitor, "_add_tree", side_effect=lambda _root: monitor._watches.__setitem__(1, "/music")), \
             patch.object(threading.Thread, "start"), \
             patch.object(monitor._stop, "clear", wraps=monitor._stop.clear) as clear:
            with patch.object(ctypes, "CDLL") as cdll:
                libc = cdll.return_value
                libc.inotify_init1.return_value = 7
                libc.inotify_add_watch.return_value = 1
                self.assertTrue(monitor.start())
        clear.assert_called_once_with()

    def test_inotify_monitor_thread_start_failure_rolls_back_fd_and_state(self):
        monitor = library.LibraryChangeMonitor(["/music"])
        with patch.object(os, "name", "posix"), \
             patch.object(os.path, "isdir", return_value=True), \
             patch.object(monitor, "_add_tree", side_effect=lambda _root: monitor._watches.__setitem__(1, "/music")), \
             patch.object(threading.Thread, "start", side_effect=RuntimeError("no threads")):
            with patch.object(ctypes, "CDLL") as cdll:
                libc = cdll.return_value
                libc.inotify_init1.return_value = 7
                libc.inotify_add_watch.return_value = 1
                self.assertFalse(monitor.start())
        self.assertFalse(monitor.available)
        self.assertEqual(monitor._fd, -1)
        self.assertIsNone(monitor._thread)

    def test_inotify_worker_does_not_read_replacement_fd_after_restart(self):
        monitor = library.LibraryChangeMonitor(["/music"])
        monitor._fd = 7
        monitor._stop = threading.Event()
        monitor._stop.set()
        with patch.object(os, "read") as read:
            monitor._run()
        read.assert_not_called()

        monitor._stop.clear()
        wait_calls = [False, True]
        def wait_and_replace(_timeout):
            result = wait_calls.pop(0)
            if not result:
                monitor._fd = 8
            return result
        with patch.object(monitor._stop, "wait", side_effect=wait_and_replace), \
             patch.object(os, "read", return_value=b"") as read:
            monitor._run()
        read.assert_not_called()

    def test_large_library_uses_sqlite_without_serializing_all_items_to_json(self):
        # This path hands cover work to the library prewarm pool, whose worker parks between
        # pages.  R88's audit caught that worker alive a second after the test ended, still
        # holding the cache directory it decodes into.
        self.addCleanup(cover_cache.shutdown_library_thumbnail_prewarm, True)
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            old_items = library.MUSIC_CACHE["items"]
            old_signature = library.FS_CACHE["signature"]
            try:
                library.MUSIC_CACHE["items"] = [{"id": str(index), "path": "/music/%s.flac" % index} for index in range(library.LIBRARY_JSON_CACHE_LIMIT + 1)]
                library.FS_CACHE["signature"] = "large-test"
                library.save_library_cache(config)

                with open(library.library_cache_path(config), "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                self.assertEqual(payload["items"], [])
                self.assertTrue(payload["sqlite"])
                self.assertEqual(library.library_summary_from_sqlite(config)["count"], library.LIBRARY_JSON_CACHE_LIMIT + 1)
            finally:
                library.MUSIC_CACHE["items"] = old_items
                library.FS_CACHE["signature"] = old_signature

    def test_legacy_json_cache_rows_survive_into_the_single_item_lookup(self):
        # The recovery projections in metadata_unavailable_policy read
        # ``lyrics``/``cover_url`` off the raw row returned by
        # ``find_library_item``.  The scanner never puts those keys there, but
        # a legacy ``library.json`` cache can, and the whole persistence chain
        # has to keep them verbatim: cache file -> in-memory index ->
        # ``tracks.item_json`` -> single-item lookup.  If any of those steps
        # starts whitelisting keys, the reads become the dead code an audit
        # round once believed them to be, so the chain is pinned here.
        with tempfile.TemporaryDirectory() as root:
            music = os.path.join(root, "music")
            os.makedirs(music, exist_ok=True)
            config = {"cache_dir": root, "library_paths": [music]}
            legacy_item = {
                "id": "legacy-1",
                "path": os.path.join(music, "song.flac"),
                "title": "Legacy",
                "lyrics": "[00:01.00]cached body",
                "cover_url": "cover/legacy-1?v=7",
                "cover_thumbnail_url": "cover-asset/legacy?size=160",
            }
            with open(library.library_cache_path(config), "w", encoding="utf-8") as handle:
                json.dump({
                    "library_path": library.display_library_path(config),
                    "signature": "legacy-signature",
                    "items": [legacy_item],
                }, handle, ensure_ascii=False)
            old_items = library.MUSIC_CACHE["items"]
            old_signature = library.FS_CACHE["signature"]
            try:
                library.MUSIC_CACHE["items"] = []
                with patch.object(library, "library_summary_from_sqlite", return_value=None):
                    library.load_library_cache(config)
                self.assertEqual(library.FS_CACHE["signature"], "legacy-signature")
                # Drop the in-memory copy so the lookup has to come back out of
                # the SQLite row this call just wrote.
                library.MUSIC_CACHE["items"] = []
                row = library.query_library_item_by_id(config, "legacy-1")
                self.assertIsNotNone(row)
                self.assertEqual(row["lyrics"], "[00:01.00]cached body")
                self.assertEqual(row["cover_url"], "cover/legacy-1?v=7")
                self.assertEqual(row["cover_thumbnail_url"], "cover-asset/legacy?size=160")
                cached = local_cached_projection("legacy-1", row)
                self.assertEqual(cached["lyrics"], "[00:01.00]cached body")
                self.assertEqual(cached["image_url"], "cover/legacy-1?v=7")
                startup = local_lyrics_projection(row)
                self.assertEqual(startup["lyrics"], "[00:01.00]cached body")
                self.assertEqual(startup["image_url"], "cover/legacy-1?v=7")
            finally:
                library.MUSIC_CACHE["items"] = old_items
                library.FS_CACHE["signature"] = old_signature
    def test_oversized_legacy_json_cache_is_rejected_before_decode(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            cache_path = library.library_cache_path(config)
            with open(cache_path, "wb") as handle:
                handle.write(b"{" + b"x" * library.LIBRARY_JSON_CACHE_MAX_BYTES + b"}")
            old_items = library.MUSIC_CACHE["items"]
            try:
                library.MUSIC_CACHE["items"] = [{"id": "keep"}]
                with patch.object(library, "library_summary_from_sqlite", return_value=None), \
                     patch.object(json, "loads", side_effect=AssertionError("oversized cache decoded")):
                    library.load_library_cache(config)
                self.assertEqual(library.MUSIC_CACHE["items"], [{"id": "keep"}])
            finally:
                library.MUSIC_CACHE["items"] = old_items

    def test_cancelled_scan_keeps_existing_in_memory_index(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0])
            old_items = library.MUSIC_CACHE["items"]
            old_signature = library.FS_CACHE["signature"]
            try:
                library.MUSIC_CACHE["items"] = [{"id": "existing"}]
                library.FS_CACHE["signature"] = "existing-signature"
                with patch.object(library, "scan_libraries", side_effect=library.ScanCancelled("library scan cancelled")):
                    library.refresh_library_if_changed(config, force=True)
                self.assertEqual(library.MUSIC_CACHE["items"], [{"id": "existing"}])
                self.assertEqual(library.FS_CACHE["signature"], "existing-signature")
                self.assertTrue(library.SCAN_STATE["cancelled"])
            finally:
                library.MUSIC_CACHE["items"] = old_items
                library.FS_CACHE["signature"] = old_signature

    def test_failed_scan_persistence_still_publishes_the_finished_scan(self):
        # R201: a write that lost the lock is a durability problem, not a scan
        # failure. Throwing the snapshot away kept the library empty and made the
        # next watcher tick walk the same 60,000-file tree again.
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0])
            old_items = library.MUSIC_CACHE["items"]
            old_signature = library.FS_CACHE["signature"]
            try:
                library.MUSIC_CACHE["items"] = [{"id": "existing"}]
                library.FS_CACHE["signature"] = "existing-signature"
                with patch.object(library, "scan_libraries", return_value=([{"id": "new"}], "new-signature")), \
                     patch.object(library, "save_library_cache", return_value=False) as save_cache:
                    library.refresh_library_if_changed(config, force=True)
                self.assertEqual(save_cache.call_count, 1)
                self.assertEqual(library.MUSIC_CACHE["items"], [{"id": "new"}])
                self.assertEqual(library.FS_CACHE["signature"], "new-signature")
                self.assertEqual(library.SCAN_STATE["result"], "completed")
            finally:
                library.MUSIC_CACHE["items"] = old_items
                library.FS_CACHE["signature"] = old_signature

    def test_setup_failure_before_the_scan_releases_the_scan_lock(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            os.makedirs(config["library_paths"][0])
            # The deadline is built after SCAN_LOCK is taken. A failure in that
            # setup used to escape the guarded block and keep the lock forever,
            # so every later refresh request would queue behind a dead scan.
            with patch.object(library, "ScanDeadline", side_effect=RuntimeError("setup failed")):
                library.refresh_library_if_changed(config, force=True)
            self.assertEqual(library.SCAN_STATE["result"], "error")
            self.assertFalse(library.SCAN_STATE["running"])
            self.assertTrue(library.SCAN_LOCK.acquire(timeout=2))
            library.SCAN_LOCK.release()

    def test_scan_deadline_distinguishes_timeout_from_manual_cancel(self):
        with self.assertRaises(library.ScanTimedOut):
            library.check_scan_deadline(time.monotonic() - 1)
        library.SCAN_CANCEL_EVENT.set()
        with self.assertRaises(library.ScanCancelled):
            library.check_scan_deadline(time.monotonic() + 60)

    def test_scan_deadline_renews_while_progress_continues(self):
        with patch.object(library.time, "monotonic", side_effect=[0, 50, 100, 171]):
            deadline = library.ScanDeadline(60)
            library.check_scan_deadline(deadline)
            library.check_scan_deadline(deadline)
            with self.assertRaises(library.ScanTimedOut):
                library.check_scan_deadline(deadline)

    def test_multi_root_scan_reports_monotonic_found_count(self):
        config = {"library_paths": ["/music/a", "/music/b"]}

        def fake_scan(root, previous_items=None, config=None, deadline=None, found_offset=0, sink=None):
            count = 2 if root.endswith("a") else 3
            items = [
                {"id": "%s-%s" % (root, index), "artist": "", "album": "", "title": str(index)}
                for index in range(count)
            ]
            library.SCAN_STATE["found"] = found_offset + len(items)
            observed.append(library.SCAN_STATE["found"])
            return items, root

        observed = []
        with patch.object(library, "scan_library", side_effect=fake_scan):
            items, _signature = library.scan_libraries(config)
        self.assertEqual(len(items), 5)
        self.assertEqual(observed, [2, 5])

    def test_request_and_cancel_report_whether_action_was_accepted(self):
        config = {"library_paths": []}
        with patch.object(library.threading, "Thread") as thread_class:
            library.SCAN_STATE["running"] = False
            library.SCAN_STATE["queued"] = False
            library.SCAN_STATE["worker_active"] = False
            self.assertTrue(library.request_library_refresh(config))
            thread_class.return_value.start.assert_called_once()
            self.assertTrue(library.SCAN_STATE["queued"])
            self.assertFalse(library.request_library_refresh(config))
            self.assertTrue(library.request_library_refresh(config, True))
            self.assertTrue(library.SCAN_STATE["queued_force"])
            self.assertFalse(library.request_library_refresh(config, True))
            library.SCAN_STATE["queued"] = False
            library.SCAN_STATE["queued_force"] = False
            library.SCAN_STATE["running"] = True
            self.assertTrue(library.request_library_refresh(config, True))
            self.assertTrue(library.SCAN_STATE["queued_force"])
            self.assertTrue(library.cancel_library_refresh())
            self.assertTrue(library.SCAN_CANCEL_EVENT.is_set())
            self.assertFalse(library.SCAN_STATE["queued"])
            library.SCAN_STATE["running"] = False
            library.SCAN_STATE["worker_active"] = False
            self.assertFalse(library.cancel_library_refresh())

    def test_cancelled_worker_generation_cannot_start_a_taken_refresh(self):
        config = {"library_paths": []}
        with library.SCAN_REQUEST_LOCK:
            generation = library.SCAN_REFRESH_GENERATION
            library.SCAN_STATE["running"] = False
            library.SCAN_STATE["queued"] = False
            library.SCAN_STATE["queued_force"] = False
            library.SCAN_STATE["worker_active"] = True
        self.assertTrue(library.cancel_library_refresh())
        with patch.object(library, "scan_libraries", side_effect=AssertionError("stale scan started")):
            library.refresh_library_if_changed(config, _refresh_generation=generation)
        self.assertTrue(library.SCAN_STATE["cancelled"])
        self.assertEqual(library.SCAN_STATE["result"], "cancelled")

    def test_stale_refresh_worker_cannot_clear_replacement_worker_state(self):
        old_worker = threading.current_thread()
        replacement = object()
        with library.SCAN_REQUEST_LOCK:
            library.SCAN_WORKER_THREAD = replacement
            library.SCAN_STATE["worker_active"] = True
        try:
            with patch.object(library, "take_refresh", return_value=(None, False, False)):
                library._run_library_refresh_queue({})
        finally:
            with library.SCAN_REQUEST_LOCK:
                library.SCAN_WORKER_THREAD = None
                library.SCAN_STATE["worker_active"] = False
        self.assertIs(library.SCAN_WORKER_THREAD, None)

    def test_cue_file_reference_cannot_escape_the_library_root(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            outside = os.path.join(root, "outside.mp3")
            with open(outside, "wb") as handle:
                handle.write(b"not-a-real-mp3")
            cue = os.path.join(music_root, "escape.cue")
            with open(cue, "w", encoding="utf-8") as handle:
                handle.write('FILE "../outside.mp3" MP3\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n')

            items, _signature = library.scan_library(music_root, config={})
            self.assertEqual(items, [])

    def test_symlinked_audio_cannot_escape_the_library_root(self):
        with tempfile.TemporaryDirectory() as root:
            music_root = os.path.join(root, "music")
            os.makedirs(music_root)
            outside = os.path.join(root, "outside.mp3")
            with open(outside, "wb") as handle:
                handle.write(b"not-a-real-mp3")
            link = os.path.join(music_root, "linked.mp3")
            try:
                os.symlink(outside, link)
            except OSError as exc:
                self.skipTest("symlinks are unavailable: %s" % exc)

            items, signature = library.scan_library(music_root, config={})
            self.assertEqual(items, [])
            self.assertEqual(signature, library.library_signature(music_root))


if __name__ == "__main__":
    unittest.main()
