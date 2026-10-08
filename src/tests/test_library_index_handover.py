"""Discriminating tests for the read-only legacy library index handover."""

import json
import posixpath
import sys
import unittest
from contextlib import contextmanager

sys.path.insert(0, "app/server")

import library_index_handover as handover

ACTIVE_SYSTEM = "/usr/local/apps/@appconf/fnaudio/transcode"
ACTIVE_SYSTEM_DB = ACTIVE_SYSTEM + "/library.sqlite3"
LEGACY_VOLUME = "/vol1/@appconf/fnaudio/transcode"
LEGACY_VOLUME_DB = LEGACY_VOLUME + "/library.sqlite3"
LIBRARY_PATH = "/vol2/1000/music"
METADATA_VERSION = 16
FOUND = [{"path": LIBRARY_PATH + "/found.flac"}]


def meta_rows(library_path=LIBRARY_PATH, metadata_version=METADATA_VERSION):
    return [
        {"key": "library_path", "value": library_path},
        {"key": "metadata_version", "value": str(metadata_version)},
    ]


def track_rows(count):
    return [{"item_json": json.dumps({"path": "%s/t%02d.flac" % (LIBRARY_PATH, index)})}
            for index in range(count)]


class FakeConnection(object):
    def __init__(self, meta=None, tracks=None, error=None):
        self.meta = meta_rows() if meta is None else meta
        self.tracks = track_rows(2) if tracks is None else tracks
        self.error = error
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if self.error is not None:
            raise self.error
        if sql == handover.META_SQL:
            return iter(self.meta)
        if sql == handover.TRACKS_SQL:
            return iter(self.tracks)
        raise AssertionError("unexpected statement: %s" % sql)


class FakeHandle(object):
    def __init__(self, connection, log):
        self.connection = connection
        self.log = log

    def __enter__(self):
        self.log.append("open")
        return self.connection

    def __exit__(self, exc_type, exc, tb):
        self.log.append("close")
        return False


def make_connect(connection, log):
    def connect(uri):
        log.append(uri)
        return FakeHandle(connection, log)
    return connect


def probes(exists=(), links=(), sizes=None):
    """Filesystem probes driven by path sets, so no test touches a real disk."""
    existing = set(exists)
    linking = set(links)
    sizing = dict(sizes or {})

    def is_file(path):
        return path in existing

    def is_link(path):
        return path in linking

    def file_size(path):
        if path in sizing:
            return sizing[path]
        raise OSError(path)

    return {"is_file": is_file, "is_link": is_link, "file_size": file_size}


class HandoverNameTests(unittest.TestCase):
    def test_h1_volume_root_names_are_positive_bounded_ascii_digits(self):
        for name in ("vol1", "vol9", "vol12", "vol123456"):
            self.assertTrue(handover.is_volume_root_name(name), name)
        for name in ("vol", "vol0", "vol01", "vol1234567", "VOL1", "volume1",
                     "vol1x", "vol1 ", "", None, 7, "\u00b2", "vol\u00b2", "vol\uff11"):
            self.assertFalse(handover.is_volume_root_name(name), repr(name))

    def test_h1_app_names_cannot_carry_separators_or_traversal(self):
        self.assertTrue(handover.is_valid_app_name("fnaudio"))
        self.assertTrue(handover.is_valid_app_name("fn.audio_v2-x"))
        for name in ("", ".", "..", "a..b", "fn audio", "fn/audio", "fn\\audio",
                     "fnaudio" * 20, "\u00e9pp", None):
            self.assertFalse(handover.is_valid_app_name(name), repr(name))


class HandoverCandidateTests(unittest.TestCase):
    def test_h2_system_root_offers_the_volume_roots_only(self):
        self.assertEqual(
            handover.candidate_cache_dirs(ACTIVE_SYSTEM, ["vol1", "vol2", "usr", "etc"]),
            [LEGACY_VOLUME, "/vol2/@appconf/fnaudio/transcode"])

    def test_h2_volume_root_offers_other_roots_and_appends_the_system_root(self):
        self.assertEqual(
            handover.candidate_cache_dirs(LEGACY_VOLUME, ["/vol1", "/vol2", "vol3", "/vol2"]),
            ["/vol2/@appconf/fnaudio/transcode",
             "/vol3/@appconf/fnaudio/transcode",
             ACTIVE_SYSTEM])

    def test_h2_candidate_list_is_bounded(self):
        entries = ["vol%d" % index for index in range(1, 40)]
        candidates = handover.candidate_cache_dirs(ACTIVE_SYSTEM, entries)
        self.assertEqual(len(candidates), handover.MAX_HANDOVER_CANDIDATES)
        self.assertTrue(all(path.startswith("/vol") for path in candidates))

    def test_h3_any_other_directory_shape_is_refused(self):
        refused = [
            "",
            None,
            "relative/@appconf/fnaudio/transcode",
            "/@appconf/fnaudio/transcode",
            "/vol1/@appconf/fnaudio",
            "/vol1/@appconf/transcode",
            "/vol1/@appcenter/fnaudio/transcode",
            "/vol1/@appconf/../fnaudio/transcode",
            "/vol1/@appconf/fn audio/transcode",
            "/vol1/@appconf/fnaudio/transcode/extra",
            "/vol1/@appconf/fnaudio/Transcode",
        ]
        for cache_dir in refused:
            self.assertIsNone(handover.split_cache_dir(cache_dir), repr(cache_dir))
            self.assertEqual(handover.candidate_cache_dirs(cache_dir, ["vol1"]), [], repr(cache_dir))

    def test_split_cache_dir_returns_root_and_app_name(self):
        self.assertEqual(handover.split_cache_dir(ACTIVE_SYSTEM), ("/usr/local/apps", "fnaudio"))
        self.assertEqual(handover.split_cache_dir(LEGACY_VOLUME + "/"), ("/vol1", "fnaudio"))
        self.assertEqual(handover.index_path_for_cache_dir(LEGACY_VOLUME), LEGACY_VOLUME_DB)


class HandoverReadTests(unittest.TestCase):
    def read(self, connection, log, **kwargs):
        options = {"library_path": LIBRARY_PATH, "metadata_version": METADATA_VERSION}
        options.update(kwargs)
        options.setdefault("connect", make_connect(connection, log))
        options.setdefault("is_file", lambda path: True)
        options.setdefault("is_link", lambda path: False)
        options.setdefault("file_size", lambda path: 0)
        return handover.read_index_items(ACTIVE_SYSTEM_DB, **options)

    def test_h4_valid_index_is_read_through_a_read_only_handle(self):
        log = []
        connection = FakeConnection()
        items = self.read(connection, log)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["path"], "%s/t00.flac" % LIBRARY_PATH)
        self.assertEqual(log[0], "file:%s?mode=ro" % ACTIVE_SYSTEM_DB)
        self.assertEqual(log[1:], ["open", "close"])
        self.assertEqual(connection.executed[1], (handover.TRACKS_SQL,
                                                  (handover.MAX_HANDOVER_ITEMS + 1,)))

    def test_h4_index_for_another_library_root_is_refused(self):
        log = []
        connection = FakeConnection(meta=meta_rows(library_path="/vol1/1000/music"))
        self.assertEqual(self.read(connection, log), [])
        self.assertEqual(log[0], "file:%s?mode=ro" % ACTIVE_SYSTEM_DB)

    def test_h4_index_with_a_stale_metadata_version_is_refused(self):
        log = []
        connection = FakeConnection(meta=meta_rows(metadata_version=15))
        self.assertEqual(self.read(connection, log), [])

    def test_h4_index_with_a_pending_write_ahead_journal_is_refused(self):
        log = []
        items = self.read(FakeConnection(), log,
                          is_file=lambda path: path in (ACTIVE_SYSTEM_DB, ACTIVE_SYSTEM_DB + "-wal"),
                          file_size=lambda path: 4096)
        self.assertEqual(items, [])
        self.assertEqual(log, [])

    def test_h4_empty_write_ahead_journal_still_allows_the_read(self):
        log = []
        items = self.read(FakeConnection(), log,
                          is_file=lambda path: path in (ACTIVE_SYSTEM_DB, ACTIVE_SYSTEM_DB + "-wal"),
                          file_size=lambda path: 0)
        self.assertEqual(len(items), 2)

    def test_h4_missing_index_is_refused_without_opening_a_handle(self):
        log = []
        items = self.read(FakeConnection(), log, is_file=lambda path: False)
        self.assertEqual(items, [])
        self.assertEqual(log, [])

    def test_h4_symlinked_index_is_refused(self):
        log = []
        items = self.read(FakeConnection(), log, is_link=lambda path: True)
        self.assertEqual(items, [])
        self.assertEqual(log, [])

    def test_h4_unreadable_write_ahead_journal_is_refused(self):
        log = []
        items = self.read(FakeConnection(), log,
                          is_file=lambda path: path == ACTIVE_SYSTEM_DB or path.endswith("-wal"),
                          file_size=lambda path: (_ for _ in ()).throw(OSError(path)))
        self.assertEqual(items, [])
        self.assertEqual(log, [])

    def test_h4_database_failure_is_refused(self):
        log = []
        self.assertEqual(self.read(FakeConnection(error=OSError("locked")), log), [])

    def test_h4_relative_index_path_is_refused(self):
        for path in ("", None, "vol1/library.sqlite3"):
            self.assertEqual(handover.read_index_items(
                path, library_path=LIBRARY_PATH, metadata_version=METADATA_VERSION,
                connect=make_connect(FakeConnection(), [])), [], repr(path))

    def test_h4_oversized_index_is_refused(self):
        log = []
        oversized = [{"item_json": "{}"}] * (handover.MAX_HANDOVER_ITEMS + 1)
        self.assertEqual(self.read(FakeConnection(tracks=oversized), log), [])

    def test_h4_empty_index_is_refused(self):
        log = []
        self.assertEqual(self.read(FakeConnection(tracks=[]), log), [])

    def test_validate_index_payload_rejects_unshaped_meta(self):
        self.assertFalse(handover.validate_index_payload(None, LIBRARY_PATH, METADATA_VERSION))
        self.assertFalse(handover.validate_index_payload([], LIBRARY_PATH, METADATA_VERSION))
        self.assertFalse(handover.validate_index_payload({"library_path": LIBRARY_PATH}, "", METADATA_VERSION))
        self.assertFalse(handover.validate_index_payload({"library_path": LIBRARY_PATH}, None, METADATA_VERSION))
        self.assertTrue(handover.validate_index_payload(
            {"library_path": LIBRARY_PATH, "metadata_version": METADATA_VERSION},
            LIBRARY_PATH, METADATA_VERSION))


class HandoverFindTests(unittest.TestCase):
    def reader_for(self, hits):
        seen = []

        def reader(db_path, **kwargs):
            seen.append((db_path, kwargs.get("library_path"), kwargs.get("metadata_version")))
            return list(hits.get(db_path, []))

        return reader, seen

    def test_h5_first_non_empty_legacy_index_wins(self):
        reader, seen = self.reader_for({"/vol2/@appconf/fnaudio/transcode/library.sqlite3": FOUND})
        items, source = handover.find_reuse_items(
            ACTIVE_SYSTEM, library_path=LIBRARY_PATH, metadata_version=METADATA_VERSION,
            list_root=lambda path: ["vol1", "vol2", "usr"],
            active_db_path=ACTIVE_SYSTEM_DB, read_items=reader)
        self.assertEqual(items, FOUND)
        self.assertEqual(source, "/vol2/@appconf/fnaudio/transcode")
        self.assertEqual([entry[0] for entry in seen], [
            LEGACY_VOLUME_DB,
            "/vol2/@appconf/fnaudio/transcode/library.sqlite3",
        ])
        self.assertEqual(seen[0][1], LIBRARY_PATH)
        self.assertEqual(seen[0][2], METADATA_VERSION)

    def test_h5_a_legacy_install_without_any_index_returns_nothing(self):
        reader, seen = self.reader_for({})
        items, source = handover.find_reuse_items(
            ACTIVE_SYSTEM, library_path=LIBRARY_PATH, metadata_version=METADATA_VERSION,
            list_root=lambda path: ["vol1", "vol2"],
            active_db_path=ACTIVE_SYSTEM_DB, read_items=reader)
        self.assertEqual(items, [])
        self.assertEqual(source, "")
        self.assertEqual(len(seen), 2)

    def test_h5_the_active_database_is_never_read_as_a_legacy_one(self):
        reader, seen = self.reader_for({ACTIVE_SYSTEM_DB: FOUND})
        items, source = handover.find_reuse_items(
            LEGACY_VOLUME, library_path=LIBRARY_PATH, metadata_version=METADATA_VERSION,
            list_root=lambda path: ["vol1", "vol2"],
            active_db_path=posixpath.normpath(ACTIVE_SYSTEM_DB), read_items=reader)
        self.assertEqual(items, [])
        self.assertEqual(source, "")
        self.assertNotIn(ACTIVE_SYSTEM_DB, [entry[0] for entry in seen])

    def test_h5_a_raising_reader_does_not_abort_the_sweep(self):
        def reader(db_path, **kwargs):
            if db_path == LEGACY_VOLUME_DB:
                raise RuntimeError("boom")
            return list(FOUND)

        items, source = handover.find_reuse_items(
            ACTIVE_SYSTEM, library_path=LIBRARY_PATH, metadata_version=METADATA_VERSION,
            list_root=lambda path: ["vol1", "vol2"],
            active_db_path=ACTIVE_SYSTEM_DB, read_items=reader)
        self.assertEqual(items, FOUND)
        self.assertEqual(source, "/vol2/@appconf/fnaudio/transcode")

    def test_h5_a_failing_root_listing_still_probes_the_system_root(self):
        calls = []
        reader, seen = self.reader_for({ACTIVE_SYSTEM_DB: FOUND})

        def listing(path):
            calls.append(path)
            raise OSError("no root")

        items, source = handover.find_reuse_items(
            LEGACY_VOLUME, library_path=LIBRARY_PATH, metadata_version=METADATA_VERSION,
            list_root=listing, active_db_path=LEGACY_VOLUME_DB, read_items=reader)
        self.assertEqual(calls, ["/"])
        self.assertEqual(source, ACTIVE_SYSTEM)
        self.assertEqual(items, FOUND)
        self.assertEqual([entry[0] for entry in seen], [ACTIVE_SYSTEM_DB])

    def test_h5_a_non_handover_cache_dir_probes_nothing(self):
        reader, seen = self.reader_for({})
        items, source = handover.find_reuse_items(
            "", library_path=LIBRARY_PATH, metadata_version=METADATA_VERSION,
            list_root=lambda path: ["vol1"], active_db_path=ACTIVE_SYSTEM_DB, read_items=reader)
        self.assertEqual((items, source), ([], ""))
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()