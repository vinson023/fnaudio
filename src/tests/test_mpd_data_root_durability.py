"""The MPD index must outlive a reinstall of the payload directory.

R192 evidence: ``appcenter-cli install-local`` rewrites every subdirectory of
``@appcenter/fnaudio``, so ``share/mpd/database`` was found truncated to 8,499
bytes minutes after an upgrade, and the user was told to wait ~30 minutes for a
cold scan before a DAC could play anything.
"""

import io
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from services import mpd_service as mpd_module
from services.mpd_service import (
    DURABLE_CONFIG_MARKER,
    LEGACY_DATA_ROOT_PARTS,
    RECLAIMED_INDEX_FILES,
    MpdService,
)

# The layout production launches with, mirrored inside a temporary directory so
# ``os.path.abspath`` cannot rewrite a hand-written POSIX path into a drive letter.
DURABLE_SEGMENT = DURABLE_CONFIG_MARKER + os.sep + "fnaudio"
REPORT_LINE = '"reclaimed_index_from": self.reclaimed_index_from,'


class Layout:
    def __init__(self, temp):
        self.root = temp
        self.app_root = os.path.join(temp, "@appcenter", "fnaudio")
        self.conf_dir = os.path.join(temp, DURABLE_SEGMENT)
        self.config_path = os.path.join(self.conf_dir, "config.json")
        self.payload_data = os.path.join(self.app_root, *LEGACY_DATA_ROOT_PARTS)
        self.durable_data = os.path.join(self.conf_dir, "mpd")
        os.makedirs(self.payload_data)
        os.makedirs(self.durable_data)
        with io.open(self.config_path, "w", encoding="utf-8") as fh:
            fh.write("{}")


def read_bytes(path):
    with io.open(path, "rb") as fh:
        return fh.read()


def build_service(layout=None, config_path=None, app_root=None, config=None):
    values = {"library_paths": ["/vol2/1000/music"], "mpd_port": 56660}
    if config is not None:
        values = dict(config)
    with mock.patch.object(MpdService, "_select_port", return_value=56660), mock.patch.object(
        MpdService, "_find_binary", return_value="/usr/bin/mpd"
    ):
        return MpdService(
            values,
            app_root=app_root if app_root is not None else (layout.app_root if layout else ""),
            app_config_path=config_path if config_path is not None else (layout.config_path if layout else ""),
        )


_REAL_OPEN = open


def fake_proc(cmdlines):
    """Answer ``/proc/<pid>/cmdline`` reads from a dict without touching the OS.

    Everything else - the legacy pid file included - goes to the real filesystem,
    because the module under test opens both through the same global ``open``.
    """

    class FakeHandle:
        def __init__(self, payload):
            self._payload = payload

        def read(self, *_args, **_kwargs):
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    def opener(path, *args, **kwargs):
        for pid, text in cmdlines.items():
            if path.endswith("/%d/cmdline" % pid):
                return FakeHandle(text.replace(" ", "\x00").encode("utf-8"))
        return _REAL_OPEN(path, *args, **kwargs)

    return mock.patch.object(mpd_module, "open", side_effect=opener)


class TempServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.layout = Layout(self.temp.name)
        self.service = build_service(self.layout)


class DurableDataRootTests(TempServiceTests):
    def test_the_index_moves_beside_the_durable_config_file(self):
        self.assertEqual(self.service.data_root, self.layout.durable_data)
        self.assertEqual(
            self.service.config_path, os.path.join(self.layout.durable_data, "mpd.conf")
        )

    def test_a_config_file_without_the_durable_marker_keeps_the_payload_directory(self):
        # ``@appconfx`` holds the marker as a substring but not as a path segment.
        plain_dir = os.path.join(self.temp.name, "@appconfx", "fnaudio")
        os.makedirs(plain_dir)
        stray = build_service(app_root=self.layout.app_root, config_path=os.path.join(plain_dir, "config.json"))
        self.assertEqual(stray.data_root, self.layout.payload_data)

    def test_a_relative_config_path_keeps_the_payload_directory(self):
        stayed = build_service(config_path=os.path.abspath("config.json"), app_root=self.layout.app_root)
        self.assertEqual(stayed.data_root, os.path.abspath(os.path.join(self.layout.app_root, *LEGACY_DATA_ROOT_PARTS)))

    def test_no_config_path_keeps_the_payload_directory(self):
        stayed = build_service(config_path="", app_root=self.layout.app_root)
        self.assertEqual(stayed.data_root, os.path.abspath(self.layout.payload_data))

    def test_an_explicit_mpd_data_dir_still_wins(self):
        custom = os.path.join(self.temp.name, "chosen", "mpd")
        moved = build_service(config={"mpd_data_dir": custom, "mpd_port": 56660})
        self.assertEqual(moved.data_root, os.path.abspath(custom))

    def test_the_legacy_root_is_reported_only_after_the_move(self):
        self.assertEqual(self.service._legacy_data_root(), os.path.abspath(self.layout.payload_data))
        stayed = build_service(config_path="", app_root=self.layout.app_root)
        self.assertEqual(stayed._legacy_data_root(), "")


class LegacyProcessRecognitionTests(TempServiceTests):
    def test_an_old_durable_mount_is_recognised_as_legacy(self):
        old_root = os.path.join(self.temp.name, "old", "@appconf", "fnaudio", "mpd")
        os.makedirs(old_root)
        with mock.patch.object(mpd_module.glob, "glob", return_value=[old_root]):
            roots = self.service._legacy_data_roots()
        self.assertIn(os.path.abspath(old_root), roots)

    def test_a_legacy_command_line_is_still_recognised_as_ours(self):
        legacy_conf = os.path.join(self.service._legacy_data_root(), "mpd.conf")
        with fake_proc({4242: "/usr/bin/mpd " + legacy_conf}):
            self.assertTrue(self.service._pid_matches_mpd(4242))

    def test_the_durable_command_line_is_recognised(self):
        with fake_proc({4343: "/usr/bin/mpd " + self.service.config_path}):
            self.assertTrue(self.service._pid_matches_mpd(4343))

    def test_an_unrelated_mpd_is_not_mistaken_for_ours(self):
        stranger = os.path.join(self.temp.name, "other", "mpd.conf")
        with fake_proc({4444: "/usr/bin/mpd " + stranger}):
            self.assertFalse(self.service._pid_matches_mpd(4444))

    def test_the_reaper_terminates_a_legacy_holder(self):
        legacy_conf = os.path.join(self.service._legacy_data_root(), "mpd.conf")
        with fake_proc({4242: "/usr/bin/mpd " + legacy_conf}), mock.patch.object(
            MpdService, "_scan_matching_pids", return_value=[4242]
        ), mock.patch.object(MpdService, "_terminate_pid") as kill:
            self.assertTrue(self.service._reap_legacy_instances())
        self.assertEqual([call.args[0] for call in kill.call_args_list], [4242])

    def test_the_reaper_stops_the_pid_file_holder_even_when_proc_scans_miss_it(self):
        pid_file = os.path.join(self.service._legacy_data_root(), "mpd.pid")
        legacy_conf = os.path.join(self.service._legacy_data_root(), "mpd.conf")
        with io.open(pid_file, "w", encoding="utf-8") as fh:
            fh.write("4242\n")
        with fake_proc({4242: "/usr/bin/mpd " + legacy_conf}), mock.patch.object(
            MpdService, "_scan_matching_pids", return_value=[]
        ), mock.patch.object(MpdService, "_terminate_pid") as kill:
            self.assertTrue(self.service._reap_legacy_instances())
        kill.assert_called_once_with(4242)

    def test_the_reaper_stays_out_of_the_way_when_there_is_nothing_legacy(self):
        stayed = build_service(config_path="", app_root=self.layout.app_root)
        with mock.patch.object(MpdService, "_scan_matching_pids") as scan, mock.patch.object(
            MpdService, "_terminate_pid"
        ) as kill:
            self.assertFalse(stayed._reap_legacy_instances())
        scan.assert_not_called()
        kill.assert_not_called()

    def test_a_reaped_legacy_holder_frees_the_requested_port(self):
        with mock.patch.object(MpdService, "_reap_legacy_instances", return_value=True) as reap, mock.patch.object(
            MpdService, "_find_binary", return_value="/usr/bin/mpd"
        ), mock.patch.object(mpd_module, "_tcp_port_available", side_effect=[False, True]) as probe:
            service = MpdService(
                {"mpd_port": 56660, "library_paths": ["/vol2/1000/music"]},
                app_root=self.layout.app_root,
                app_config_path=self.layout.config_path,
            )
        self.assertEqual(service.port, 56660)
        reap.assert_called_once_with()
        self.assertEqual(probe.call_count, 2)

    def test_a_stranger_on_the_port_is_never_reaped(self):
        with mock.patch.object(MpdService, "_reap_legacy_instances", return_value=False) as reap, mock.patch.object(
            MpdService, "_find_binary", return_value="/usr/bin/mpd"
        ), mock.patch.object(mpd_module, "_tcp_port_available", return_value=False):
            service = MpdService(
                {"mpd_port": 56660, "library_paths": ["/vol2/1000/music"]},
                app_root=self.layout.app_root,
                app_config_path=self.layout.config_path,
            )
        reap.assert_called_once_with()
        self.assertNotEqual(service.port, 56660)


class LegacyIndexReclaimTests(TempServiceTests):
    def seed_legacy(self, payload=b"mpd-database-bytes"):
        with io.open(os.path.join(self.layout.payload_data, "database"), "wb") as fh:
            fh.write(payload)
        with io.open(os.path.join(self.layout.payload_data, "sticker.sql"), "wb") as fh:
            fh.write(b"stickers")
        with io.open(os.path.join(self.layout.payload_data, "mpd.log"), "wb") as fh:
            fh.write(b"logs")
        return payload

    def test_the_payload_database_is_copied_into_the_durable_root(self):
        payload = self.seed_legacy()
        self.assertEqual(self.service._reclaim_legacy_index(), self.service._legacy_data_root())
        durable = os.path.join(self.service.data_root, "database")
        self.assertEqual(read_bytes(durable), payload)
        self.assertEqual(read_bytes(os.path.join(self.service.data_root, "sticker.sql")), b"stickers")

    def test_an_old_durable_mount_is_reclaimed_when_payload_data_is_absent(self):
        self.seed_legacy(b"")
        os.remove(os.path.join(self.layout.payload_data, "database"))
        old_root = os.path.join(self.temp.name, "old", "@appconf", "fnaudio", "mpd")
        os.makedirs(old_root)
        with io.open(os.path.join(old_root, "database"), "wb") as fh:
            fh.write(b"old-durable-index")
        with mock.patch.object(mpd_module.glob, "glob", return_value=[old_root]):
            self.assertEqual(self.service._reclaim_legacy_index(), old_root)
        self.assertEqual(read_bytes(os.path.join(self.service.data_root, "database")), b"old-durable-index")

    def test_the_legacy_copy_is_left_in_place(self):
        # The payload dies with the next reinstall anyway, but deleting it while the
        # durable copy is unverified would turn a slow start into a lost index.
        self.seed_legacy()
        self.service._reclaim_legacy_index()
        self.assertTrue(os.path.isfile(os.path.join(self.layout.payload_data, "database")))

    def test_files_that_are_not_index_state_are_not_copied(self):
        self.seed_legacy()
        self.service._reclaim_legacy_index()
        self.assertFalse(os.path.exists(os.path.join(self.service.data_root, "mpd.log")))

    def test_an_existing_durable_database_is_never_overwritten(self):
        self.seed_legacy(b"stale-payload-copy")
        with io.open(os.path.join(self.service.data_root, "database"), "wb") as fh:
            fh.write(b"durable-newer")
        self.assertEqual(self.service._reclaim_legacy_index(), "")
        self.assertEqual(read_bytes(os.path.join(self.service.data_root, "database")), b"durable-newer")

    def test_a_missing_payload_database_is_not_an_error(self):
        self.assertEqual(self.service._reclaim_legacy_index(), "")

    def test_a_missing_payload_directory_is_not_an_error(self):
        import shutil as _shutil

        _shutil.rmtree(self.layout.payload_data)
        self.assertEqual(self.service._reclaim_legacy_index(), "")

    def test_a_failed_copy_leaves_no_partial_index(self):
        self.seed_legacy()
        with mock.patch.object(mpd_module.shutil, "copyfile", side_effect=OSError("disk full")):
            self.assertEqual(self.service._reclaim_legacy_index(), "")
        self.assertFalse(os.path.exists(os.path.join(self.service.data_root, "database")))
        self.assertFalse([name for name in os.listdir(self.service.data_root) if "reclaim" in name])

    def test_reclaim_is_wired_into_the_configuration_step(self):
        with io.open(mpd_module.__file__, encoding="utf-8") as fh:
            source = fh.read()
        start = source.index("    def ensure_config(self)")
        end = source.index('db_file "', start)
        self.assertIn("self.reclaimed_index_from = self._reclaim_legacy_index()", source[start:end])


class ReclaimReportingTests(unittest.TestCase):
    """A silent reclaim is indistinguishable from a lost index, so it must be visible."""

    def _source(self):
        with io.open(mpd_module.__file__, encoding="utf-8") as fh:
            return fh.read()

    def test_the_configuration_result_carries_the_reclaim_source(self):
        source = self._source()
        start = source.index("    def ensure_config(self)")
        end = source.index('"music_directory": music_directory,', start)
        self.assertIn(REPORT_LINE, source[start:end])

    def test_the_status_payload_carries_the_reclaim_source(self):
        source = self._source()
        start = source.index("    def status(self")
        end = source.index('"supervisor": supervisor,', start)
        self.assertIn(REPORT_LINE, source[start:end])

    def test_the_reclaim_source_is_reported_exactly_twice(self):
        self.assertEqual(self._source().count(REPORT_LINE), 2)


class ReclaimFileListTests(unittest.TestCase):
    def test_only_index_bearing_files_are_reclaimed(self):
        self.assertIn("database", RECLAIMED_INDEX_FILES)
        self.assertNotIn("mpd.conf", RECLAIMED_INDEX_FILES)
        self.assertNotIn("mpd.log", RECLAIMED_INDEX_FILES)
        self.assertNotIn("database.reclaim", RECLAIMED_INDEX_FILES)

    def test_the_payload_fallback_is_the_directory_an_upgrade_erases(self):
        self.assertEqual(LEGACY_DATA_ROOT_PARTS, ("share", "mpd"))


if __name__ == "__main__":
    unittest.main()

class ReaperNeverTouchesOurOwnChildTests(unittest.TestCase):
    """Depth defence for the R197 evidence: never SIGTERM the MPD we supervise.

    ``_pid_matches_mpd`` recognises a command line by our config path, the durable
    data root and the legacy data root, so a healthy child launched from
    ``@appconf`` matches its own needle list.  Whatever caller reaches the reaper
    while that child is running, the pid the supervisor owns must be dropped from
    the targets before anything is terminated.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.layout = Layout(self.temp.name)
        self.service = build_service(self.layout)

    def managed(self, pid):
        return mock.patch.object(
            self.service.supervisor, "status", return_value={"running": True, "pid": pid}
        )

    def test_the_managed_pid_is_dropped_from_the_reap_targets(self):
        legacy_conf = os.path.join(self.service._legacy_data_root(), "mpd.conf")
        cmdlines = {4242: "/usr/bin/mpd " + legacy_conf, 4343: "/usr/bin/mpd " + legacy_conf}
        with fake_proc(cmdlines), mock.patch.object(
            MpdService, "_scan_matching_pids", return_value=[4242, 4343]
        ), self.managed(4242), mock.patch.object(MpdService, "_terminate_pid") as kill:
            self.assertTrue(self.service._reap_legacy_instances())
        self.assertEqual([call.args[0] for call in kill.call_args_list], [4343])

    def test_a_legacy_pid_file_naming_our_own_child_is_not_terminated(self):
        pid_file = os.path.join(self.service._legacy_data_root(), "mpd.pid")
        legacy_conf = os.path.join(self.service._legacy_data_root(), "mpd.conf")
        with io.open(pid_file, "w", encoding="utf-8") as fh:
            fh.write("4242" + chr(10))
        with fake_proc({4242: "/usr/bin/mpd " + legacy_conf}), mock.patch.object(
            MpdService, "_scan_matching_pids", return_value=[]
        ), self.managed(4242), mock.patch.object(MpdService, "_terminate_pid") as kill:
            self.assertFalse(self.service._reap_legacy_instances())
        kill.assert_not_called()

    def test_an_unmanaged_pid_is_still_terminated(self):
        # The guard may not soften what the reaper is actually for: with no child of
        # ours running, a legacy holder is still stopped.
        legacy_conf = os.path.join(self.service._legacy_data_root(), "mpd.conf")
        with fake_proc({4242: "/usr/bin/mpd " + legacy_conf}), mock.patch.object(
            MpdService, "_scan_matching_pids", return_value=[4242]
        ), mock.patch.object(MpdService, "_terminate_pid") as kill:
            self.assertTrue(self.service._reap_legacy_instances())
        kill.assert_called_once_with(4242)
