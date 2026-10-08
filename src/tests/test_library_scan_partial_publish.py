"""Discriminating tests for the scan accumulator and partial index publish.

A scan that runs out of time used to discard everything it had already read,
so on a library large enough to exceed ``scan_timeout_seconds`` the interface
never showed a single track.  These tests pin the two halves of the fix: the
scanner must hand its partial work back through the caller's sink, and an
aborted refresh must publish that partial index with an empty signature.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "app/server")

import cover_cache
import library


def audio_item(root, name):
    return {
        "id": name,
        "path": os.path.join(root, name),
        "title": name,
        "artist": "artist",
        "album": "album",
        "format": "FLAC",
        "mime": "audio/flac",
        "duration": 1,
    }


def write_tracks(root, count):
    os.makedirs(root, exist_ok=True)
    for index in range(count):
        with open(os.path.join(root, "track-%02d.flac" % index), "wb") as handle:
            handle.write(b"fnaudio-test-track")
    return root


class ScanSinkTests(unittest.TestCase):
    def test_p1_a_timed_out_scan_leaves_the_read_tracks_in_the_sink(self):
        with tempfile.TemporaryDirectory() as root:
            music = write_tracks(os.path.join(root, "music"), 3)
            seen = []

            def probe(path, config):
                # ``read_metadata`` re-reads the same path through the probe, so
                # the deadline only fires when the scanner reaches a new track.
                if path not in seen:
                    seen.append(path)
                if len(seen) == 2:
                    raise library.ScanTimedOut("library scan made no progress")
                return {}, {}

            sink = []
            with patch.object(library, "read_probe_metadata", side_effect=probe):
                with self.assertRaises(library.ScanTimedOut):
                    library.scan_library(music, config={}, sink=sink)
            self.assertEqual(len(sink), 1)
            self.assertEqual(len(seen), 2)

    def test_p1_without_a_sink_the_same_scan_still_raises(self):
        with tempfile.TemporaryDirectory() as root:
            music = write_tracks(os.path.join(root, "music"), 3)
            seen = []

            def probe(path, config):
                if path not in seen:
                    seen.append(path)
                if len(seen) == 2:
                    raise library.ScanTimedOut("library scan made no progress")
                return {}, {}

            with patch.object(library, "read_probe_metadata", side_effect=probe):
                with self.assertRaises(library.ScanTimedOut):
                    library.scan_library(music, config={})
            self.assertEqual(len(seen), 2)

    def test_p1_a_completed_scan_is_sorted_and_untouched_by_the_sink(self):
        with tempfile.TemporaryDirectory() as root:
            music = write_tracks(os.path.join(root, "music"), 3)
            sink = []
            items, signature = library.scan_library(music, config={}, sink=sink)
            self.assertEqual(len(items), 3)
            self.assertEqual(len(sink), 3)
            self.assertTrue(signature)
            self.assertEqual([item["path"] for item in items],
                             sorted(item["path"] for item in items))
            plain_items, plain_signature = library.scan_library(music, config={})
            self.assertEqual(plain_signature, signature)
            self.assertEqual([item["path"] for item in plain_items],
                             [item["path"] for item in items])

    def test_p2_a_shared_sink_is_filled_once_per_track_across_roots(self):
        with tempfile.TemporaryDirectory() as root:
            first = write_tracks(os.path.join(root, "one"), 1)
            second = write_tracks(os.path.join(root, "two"), 1)
            calls = []

            def fake_scan(library_root, previous_items, config, deadline, offset, sink):
                calls.append((library_root, offset, sink))
                sink.append(audio_item(library_root, "track-%s.flac" % os.path.basename(library_root)))
                return list(sink), "sig-%s" % os.path.basename(library_root)

            shared = []
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [first, second]}
            with patch.object(library, "scan_library", side_effect=fake_scan):
                items, signature = library.scan_libraries(config, None, None, shared)
            self.assertEqual(len(shared), 2)
            self.assertEqual(len(items), 2)
            self.assertTrue(signature)
            self.assertEqual(calls[0][1], 0, "shared mode reports the running total")
            self.assertEqual(calls[1][1], 0)
            self.assertIs(calls[0][2], shared)
            self.assertIs(calls[1][2], shared)

    def test_p2_the_separate_mode_still_reports_the_previous_total(self):
        with tempfile.TemporaryDirectory() as root:
            first = write_tracks(os.path.join(root, "one"), 1)
            second = write_tracks(os.path.join(root, "two"), 1)
            calls = []

            def fake_scan(library_root, previous_items, config, deadline, offset, sink):
                calls.append((library_root, offset, sink))
                name = "track-%s.flac" % os.path.basename(library_root)
                return [audio_item(library_root, name)], "sig-%s" % os.path.basename(library_root)

            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [first, second]}
            with patch.object(library, "scan_library", side_effect=fake_scan):
                items, signature = library.scan_libraries(config)
            self.assertEqual(len(items), 2)
            self.assertEqual([call[1] for call in calls], [0, 1])
            self.assertEqual([call[2] for call in calls], [None, None])

            shared = []
            with patch.object(library, "scan_library", side_effect=fake_scan):
                library.scan_libraries(config, None, None, shared)
            self.assertEqual([call[1] for call in calls][-2:], [0, 0])


class PartialPublishTests(unittest.TestCase):
    def setUp(self):
        self.previous_items = library.MUSIC_CACHE["items"]
        self.previous_signature = library.FS_CACHE["signature"]

    def tearDown(self):
        library.MUSIC_CACHE["items"] = self.previous_items
        library.FS_CACHE["signature"] = self.previous_signature

    def test_p3_an_empty_partial_never_touches_the_disk(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": root, "library_paths": [os.path.join(root, "music")]}
            library.FS_CACHE["signature"] = "full-signature"
            with patch.object(library, "save_library_cache") as save:
                self.assertFalse(library.publish_partial_library_index(config, []))
                self.assertFalse(library.publish_partial_library_index(config, None))
            save.assert_not_called()
            self.assertEqual(library.FS_CACHE["signature"], "full-signature")

    def test_p3_the_partial_is_stored_with_an_empty_signature(self):
        with tempfile.TemporaryDirectory() as root:
            music = write_tracks(os.path.join(root, "music"), 2)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music]}
            library.FS_CACHE["signature"] = "full-signature"
            items = [audio_item(music, "track-00.flac"), audio_item(music, "track-01.flac")]
            with patch.object(cover_cache, "prewarm_library_thumbnails"):
                self.assertTrue(library.publish_partial_library_index(config, items))
            self.assertEqual(library.FS_CACHE["signature"], "full-signature")
            stored = library.load_items_from_sqlite(config)
            self.assertIsNotNone(stored)
            self.assertEqual(stored["signature"], "")
            self.assertEqual(len(stored["items"]), 2)
            saved_signature = None
            with library.library_db_connect(config) as conn:
                meta = {row["key"]: row["value"] for row in conn.execute("SELECT key,value FROM library_meta")}
                saved_signature = meta.get("signature")
            self.assertEqual(saved_signature, "")
            self.assertEqual(meta.get("library_path"), library.display_library_path(config))
            self.assertEqual(len(library.MUSIC_CACHE["items"]), 2)

    def test_p3_a_failed_persist_is_reported_as_no_publish(self):
        with tempfile.TemporaryDirectory() as root:
            music = write_tracks(os.path.join(root, "music"), 1)
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music]}
            library.MUSIC_CACHE["items"] = []
            with patch.object(library, "save_library_cache", return_value=False):
                self.assertFalse(library.publish_partial_library_index(config, [audio_item(music, "track-00.flac")]))
            self.assertEqual(library.MUSIC_CACHE["items"], [])
            with patch.object(library, "save_library_cache", side_effect=OSError("locked")):
                self.assertFalse(library.publish_partial_library_index(config, [audio_item(music, "a.flac")]))

    def refresh_config(self, root):
        music = write_tracks(os.path.join(root, "music"), 2)
        config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music]}
        library.MUSIC_CACHE["items"] = []
        library.FS_CACHE["signature"] = ""
        return config, music

    def test_p4_a_timed_out_refresh_publishes_what_it_read(self):
        with tempfile.TemporaryDirectory() as root:
            config, music = self.refresh_config(root)
            read = [audio_item(music, "track-00.flac")]

            def scan(scan_config, previous_items, deadline, sink):
                sink.extend(read)
                raise library.ScanTimedOut("library scan made no progress for 1 seconds")

            with patch.object(library, "scan_libraries", side_effect=scan), \
                    patch.object(library, "legacy_reuse_items_for_scan", return_value=[]), \
                    patch.object(library, "save_library_cache", return_value=True) as save:
                library.refresh_library_if_changed(config, force=True)
            save.assert_called_once()
            self.assertEqual(save.call_args[0][1], read)
            self.assertEqual(save.call_args[0][2], "")
            self.assertEqual(library.SCAN_STATE["result"], "timed_out")
            self.assertTrue(library.SCAN_STATE["timed_out"])
            self.assertEqual(library.MUSIC_CACHE["items"], read)
            self.assertEqual(library.FS_CACHE["signature"], "")

    def test_p4_a_cancelled_refresh_publishes_what_it_read(self):
        with tempfile.TemporaryDirectory() as root:
            config, music = self.refresh_config(root)
            read = [audio_item(music, "track-00.flac")]

            def scan(scan_config, previous_items, deadline, sink):
                sink.extend(read)
                raise library.ScanCancelled("library scan cancelled")

            with patch.object(library, "scan_libraries", side_effect=scan), \
                    patch.object(library, "legacy_reuse_items_for_scan", return_value=[]), \
                    patch.object(library, "save_library_cache", return_value=True) as save:
                library.refresh_library_if_changed(config, force=True)
            save.assert_called_once()
            self.assertEqual(save.call_args[0][2], "")
            self.assertEqual(library.SCAN_STATE["result"], "cancelled")
            self.assertEqual(library.MUSIC_CACHE["items"], read)

    def test_p4_a_refresh_that_read_nothing_publishes_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            config, music = self.refresh_config(root)

            def scan(scan_config, previous_items, deadline, sink):
                raise library.ScanTimedOut("library scan made no progress for 1 seconds")

            with patch.object(library, "scan_libraries", side_effect=scan), \
                    patch.object(library, "legacy_reuse_items_for_scan", return_value=[]), \
                    patch.object(library, "save_library_cache", return_value=True) as save:
                library.refresh_library_if_changed(config, force=True)
            save.assert_not_called()
            self.assertEqual(library.SCAN_STATE["result"], "timed_out")
            self.assertEqual(library.MUSIC_CACHE["items"], [])

    def test_p4_a_broken_scan_still_fails_without_publishing(self):
        with tempfile.TemporaryDirectory() as root:
            config, music = self.refresh_config(root)
            with patch.object(library, "scan_libraries", side_effect=OSError("boom")), \
                    patch.object(library, "legacy_reuse_items_for_scan", return_value=[]), \
                    patch.object(library, "save_library_cache", return_value=True) as save:
                library.refresh_library_if_changed(config, force=True)
            save.assert_not_called()
            self.assertEqual(library.SCAN_STATE["result"], "error")

    def test_p4_a_completed_scan_publishes_the_real_signature(self):
        with tempfile.TemporaryDirectory() as root:
            config, music = self.refresh_config(root)
            done = [audio_item(music, "track-00.flac")]
            with patch.object(library, "scan_libraries", return_value=(done, "real-signature")), \
                    patch.object(library, "legacy_reuse_items_for_scan", return_value=[]), \
                    patch.object(library, "save_library_cache", return_value=True) as save, \
                    patch.object(library, "publish_partial_library_index") as publish:
                library.refresh_library_if_changed(config, force=True)
            save.assert_called_once()
            self.assertEqual(save.call_args[0][2], "real-signature")
            publish.assert_not_called()
            self.assertEqual(library.FS_CACHE["signature"], "real-signature")
            self.assertEqual(library.SCAN_STATE["result"], "completed")


class LegacyHandoverWiringTests(unittest.TestCase):
    def setUp(self):
        self.previous_items = library.MUSIC_CACHE["items"]
        self.previous_signature = library.FS_CACHE["signature"]

    def tearDown(self):
        library.MUSIC_CACHE["items"] = self.previous_items
        library.FS_CACHE["signature"] = self.previous_signature

    def test_w1_the_legacy_index_is_only_consulted_for_an_empty_active_index(self):
        with tempfile.TemporaryDirectory() as root:
            config, music = self.refresh_config(root)
            done = [audio_item(music, "track-00.flac")]
            with patch.object(library, "load_items_from_sqlite", return_value={"items": done}), \
                    patch.object(library, "legacy_reuse_items_for_scan") as legacy, \
                    patch.object(library, "scan_libraries", return_value=(done, "sig")) as scan, \
                    patch.object(library, "save_library_cache", return_value=True):
                library.refresh_library_if_changed(config, force=True)
            legacy.assert_not_called()
            self.assertEqual(scan.call_args[0][1], done)

    def test_w2_an_empty_active_index_asks_for_the_legacy_handover(self):
        with tempfile.TemporaryDirectory() as root:
            config, music = self.refresh_config(root)
            legacy_items = [audio_item(music, "legacy.flac")]
            done = legacy_items + [audio_item(music, "new.flac")]
            with patch.object(library, "load_items_from_sqlite", return_value=None), \
                    patch.object(library, "legacy_reuse_items_for_scan", return_value=legacy_items) as legacy, \
                    patch.object(library, "scan_libraries", return_value=(done, "sig")) as scan, \
                    patch.object(library, "save_library_cache", return_value=True):
                library.refresh_library_if_changed(config, force=True)
            legacy.assert_called_once_with(config)
            self.assertEqual(scan.call_args[0][1], legacy_items)

    def test_w3_the_shell_reports_the_source_it_reused(self):
        config = {"cache_dir": "/usr/local/apps/@appconf/fnaudio/transcode",
                  "library_paths": ["/vol2/1000/music"]}
        with patch.object(library, "find_legacy_reuse_items",
                          return_value=([{"path": "/vol2/1000/music/a.flac"}],
                                         "/vol1/@appconf/fnaudio/transcode")) as finder, \
                patch.object(library, "display_library_path", return_value="/vol2/1000/music"):
            items = library.legacy_reuse_items_for_scan(config)
        self.assertEqual(len(items), 1)
        kwargs = finder.call_args[1]
        self.assertEqual(kwargs["library_path"], "/vol2/1000/music")
        self.assertEqual(kwargs["metadata_version"], library.METADATA_VERSION)
        self.assertEqual(kwargs["active_db_path"], library.library_db_path(config))
        self.assertEqual(finder.call_args[0][0], config["cache_dir"])

    def test_w3_a_failing_handover_is_invisible_to_the_scan(self):
        config = {"cache_dir": "/usr/local/apps/@appconf/fnaudio/transcode",
                  "library_paths": ["/vol2/1000/music"]}
        with patch.object(library, "find_legacy_reuse_items", side_effect=OSError("no root")):
            self.assertEqual(library.legacy_reuse_items_for_scan(config), [])
        with patch.object(library, "find_legacy_reuse_items", return_value=([], "")):
            self.assertEqual(library.legacy_reuse_items_for_scan(config), [])

    def refresh_config(self, root):
        music = write_tracks(os.path.join(root, "music"), 2)
        config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [music]}
        library.MUSIC_CACHE["items"] = []
        library.FS_CACHE["signature"] = ""
        return config, music


if __name__ == "__main__":
    unittest.main()