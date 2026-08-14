import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, "app/server")

import library


class LibraryCacheTests(unittest.TestCase):
    def tearDown(self):
        library.SCAN_CANCEL_EVENT.clear()
        library.SCAN_STATE["running"] = False

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

    def test_large_library_uses_sqlite_without_serializing_all_items_to_json(self):
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

    def test_scan_deadline_distinguishes_timeout_from_manual_cancel(self):
        with self.assertRaises(library.ScanTimedOut):
            library.check_scan_deadline(time.monotonic() - 1)
        library.SCAN_CANCEL_EVENT.set()
        with self.assertRaises(library.ScanCancelled):
            library.check_scan_deadline(time.monotonic() + 60)

    def test_request_and_cancel_report_whether_action_was_accepted(self):
        config = {"library_paths": []}
        with patch.object(library.threading, "Thread") as thread_class:
            library.SCAN_STATE["running"] = False
            self.assertTrue(library.request_library_refresh(config))
            thread_class.return_value.start.assert_called_once()
            library.SCAN_STATE["running"] = True
            self.assertFalse(library.request_library_refresh(config))
            self.assertTrue(library.cancel_library_refresh())
            self.assertTrue(library.SCAN_CANCEL_EVENT.is_set())
            library.SCAN_STATE["running"] = False
            self.assertFalse(library.cancel_library_refresh())

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
