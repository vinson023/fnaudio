import ast
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

import server


class _Closable:
    def __init__(self, calls, name):
        self.calls = calls
        self.name = name

    def stop(self):
        self.calls.append(self.name)

    def shutdown(self):
        self.calls.append(self.name)


class ServerLifecycleTests(unittest.TestCase):
    def test_metadata_workers_follow_background_switch(self):
        class Service:
            def __init__(self):
                self.calls = []

            def start(self):
                self.calls.append("start")

            def shutdown(self):
                self.calls.append("shutdown")

        service = Service()
        server.sync_metadata_workers(service, {"metadata_enabled": False, "metadata_tag_write_enabled": False})
        self.assertEqual(service.calls, [])
        server.sync_metadata_workers(service, {"metadata_enabled": True, "metadata_tag_write_enabled": False})
        self.assertEqual(service.calls, ["start"])

    def test_airplay_http_success_requires_explicit_boolean_ok(self):
        with open("app/server/server.py", encoding="utf-8") as source_file:
            source = source_file.read()
        self.assertIn(
            '200 if isinstance(result, dict) and result.get("ok") is True else 409',
            source,
        )

    def test_shutdown_runtime_continues_after_one_cleanup_failure(self):
        calls = []
        http_server = mock.Mock()

        def failing_monitor_stop():
            calls.append("monitor")
            raise RuntimeError("monitor already stopped")

        def record(name):
            return lambda **kwargs: calls.append(name)

        with mock.patch.object(server, "cancel_playback_restore_retry", side_effect=record("restore")), \
             mock.patch.object(server, "stop_remote_output_monitor", side_effect=failing_monitor_stop), \
             mock.patch.object(server, "shutdown_library_refresh", side_effect=record("refresh")), \
             mock.patch.object(server, "stop_library_watcher", side_effect=record("watcher")), \
             mock.patch.object(server, "shutdown_transcode_cache_worker", side_effect=record("transcode")), \
             mock.patch.object(server, "shutdown_library_thumbnail_prewarm", side_effect=record("thumbnail")), \
             mock.patch.object(server, "DLNA_SSDP", _Closable(calls, "ssdp")), \
             mock.patch.object(server, "DLNA_PROTOCOL", _Closable(calls, "protocol")), \
             mock.patch.object(server, "MPD_SERVICE", _Closable(calls, "mpd")), \
             mock.patch.object(server, "AIRPLAY_SERVICE", _Closable(calls, "airplay")), \
             mock.patch.object(server, "METADATA_SERVICE", _Closable(calls, "metadata")), \
             mock.patch.object(server, "stop_library_connections"):
            server.shutdown_runtime(http_server)

        self.assertEqual(
            calls,
            ["restore", "monitor", "refresh", "watcher", "transcode", "thumbnail", "ssdp", "protocol", "mpd", "airplay", "metadata"],
        )
        http_server.server_close.assert_called_once_with()

    def test_shutdown_runtime_drains_library_handles_after_the_library_stops(self):
        calls = []

        def record(name):
            return lambda **kwargs: calls.append(name)

        with mock.patch.object(server, "shutdown_library_refresh", side_effect=record("refresh")), \
             mock.patch.object(server, "stop_library_watcher", side_effect=record("watcher")), \
             mock.patch.object(server, "METADATA_SERVICE", _Closable(calls, "metadata")), \
             mock.patch.object(server, "stop_library_connections", side_effect=record("handles")):
            server.shutdown_runtime()
        # An idle library handle keeps the index file open, so the drain has to
        # run once the scanner and watcher can no longer start a new read.  The
        # metadata workers read the same index, and a provider chain still in
        # flight can hand a handle back to the pool after the drain, so the drain
        # has to come after every component that can touch the library.
        self.assertEqual(calls, ["refresh", "watcher", "metadata", "handles"])

    def test_the_whole_cleanup_order_is_pinned_by_name_with_the_drain_last(self):
        # The assertion above covers four of the thirteen steps. R62 left the rest of the
        # tuple unproven, so pin every step by name: the drain closing the sequence is the
        # invariant, and a step landing after it would reopen exactly the failure the drain
        # exists to prevent (an idle index handle keeping `library.sqlite3` open).
        calls = []

        def record(name):
            return lambda *args, **kwargs: calls.append(name)

        with mock.patch.object(server, "cancel_playback_restore_retry", side_effect=record("restore-retry")), \
             mock.patch.object(server, "stop_remote_output_monitor", side_effect=record("output-monitor")), \
             mock.patch.object(server, "shutdown_library_refresh", side_effect=record("library-refresh")), \
             mock.patch.object(server, "stop_library_watcher", side_effect=record("library-watcher")), \
             mock.patch.object(server, "shutdown_transcode_cache_worker", side_effect=record("transcode-worker")), \
             mock.patch.object(server, "shutdown_library_thumbnail_prewarm", side_effect=record("cover-prewarm")), \
             mock.patch.object(server, "shutdown_upnp_cache_background", side_effect=record("upnp-cache")), \
             mock.patch.object(server, "DLNA_SSDP", _Closable(calls, "dlna-ssdp")), \
             mock.patch.object(server, "DLNA_PROTOCOL", _Closable(calls, "dlna-protocol")), \
             mock.patch.object(server, "MPD_SERVICE", _Closable(calls, "mpd")), \
             mock.patch.object(server, "AIRPLAY_SERVICE", _Closable(calls, "airplay")), \
             mock.patch.object(server, "METADATA_SERVICE", _Closable(calls, "metadata")), \
             mock.patch.object(server, "stop_library_connections", side_effect=record("library-drain")):
            server.shutdown_runtime()
        self.assertEqual(calls, [
            "restore-retry", "output-monitor", "library-refresh", "library-watcher",
            "transcode-worker", "cover-prewarm", "upnp-cache", "dlna-ssdp",
            "dlna-protocol", "mpd", "airplay", "metadata", "library-drain",
        ])
        self.assertEqual(calls[-1], "library-drain")

    def test_the_library_handle_has_one_choke_point_outside_the_library_itself(self):
        # R62 could assert where the drain sits but not who it protects against, because
        # "can this component still open a handle" depends on one structural fact: the
        # server opens `library.sqlite3` through a single context manager. Measure that
        # fact rather than trust it - by syntax tree, so prose that merely names the helper
        # cannot trip it and a real call cannot hide. The scan also asserts its own size and
        # library.py's share, so it cannot pass by having looked at nothing.
        holders, scanned, own = [], 0, 0
        for root, directories, files in os.walk("app/server"):
            directories[:] = [name for name in directories if name != "__pycache__"]
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                path = os.path.join(root, filename)
                scanned += 1
                with open(path, encoding="utf-8") as source_file:
                    tree = ast.parse(source_file.read(), filename=path)
                hits = sum(1 for node in ast.walk(tree)
                           if isinstance(node, ast.Name) and node.id == "library_db_connect"
                           or isinstance(node, ast.Attribute) and node.attr == "library_db_connect")
                if path.replace("\\", "/") == "app/server/library.py":
                    own = hits
                elif hits:
                    holders.append("%s (%d)" % (path, hits))
        self.assertGreaterEqual(scanned, 60, "the scan found too few modules to be evidence")
        self.assertGreaterEqual(own, 8, "library.py is not the expected sole holder")
        self.assertEqual(holders, [])

    def test_a_config_commit_hands_the_committed_config_to_the_pool_applier(self):
        runtime = mock.Mock()
        runtime.config = {"library_connection_pool": True}
        seen = []

        def record(current):
            seen.append(dict(current))
            return 0

        with mock.patch.object(server, "save_config", return_value=True), \
             mock.patch.object(server, "apply_library_connection_pool_config", side_effect=record):
            self.assertTrue(server.commit_config_update(
                runtime,
                lambda candidate: candidate.update({"library_connection_pool": False, "metadata_enabled": True}),
            ))
        # The applier has to see the value after the in-place commit: both the switch it
        # reads and the index it drains come from the dictionary that was just replaced.
        self.assertEqual(len(seen), 1)
        self.assertIs(seen[0]["library_connection_pool"], False)
        self.assertIs(seen[0]["metadata_enabled"], True)
        self.assertIs(runtime.config["library_connection_pool"], False)

    def test_a_failed_config_commit_does_not_touch_the_pool(self):
        runtime = mock.Mock()
        runtime.config = {"library_connection_pool": False}
        with mock.patch.object(server, "save_config", return_value=False), \
             mock.patch.object(server, "apply_library_connection_pool_config") as applied:
            self.assertFalse(server.commit_config_update(
                runtime,
                lambda candidate: candidate.update({"library_connection_pool": True}),
            ))
        applied.assert_not_called()
        self.assertIs(runtime.config["library_connection_pool"], False)

    def test_the_pool_default_is_no_longer_invented_at_startup(self):
        # The switch used to exist only because `server.main()` injected the key into its
        # own dictionary, so `save_config` dropped it from disk and no other configuration
        # reader could see it. `config.py` owns the default now, so the server module must
        # not name the key at all - its only remaining job there is the drain.
        with open("app/server/server.py", encoding="utf-8") as source_file:
            source = source_file.read()
        self.assertNotIn("LIBRARY_CONNECTION_POOL_CONFIG_KEY", source)
        self.assertNotIn(chr(34) + "library_connection_pool" + chr(34), source)

    def test_the_stops_that_run_before_the_drain_have_no_library_coupling_at_all(self):
        # Of the steps between the pinned four and the drain, these are the ones R62 could
        # not vouch for. Measured (R89): none of them even imports the library module, so
        # no thread they stop can borrow a handle after their stop returns - their position
        # before the drain is defence in depth rather than the load-bearing part. The
        # metadata service is deliberately absent: it does import library helpers (none of
        # which reach the index), which is why its shutdown has to stay ordered before the
        # drain anyway.
        for relative_path in ("app/server/transcode.py", "app/server/cover_cache.py",
                              "app/server/dlna/control_point.py", "app/server/playback/core.py"):
            with open(relative_path, encoding="utf-8") as source_file:
                tree = ast.parse(source_file.read(), filename=relative_path)
            plain = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                     for alias in node.names]
            sourced = [node.module or "" for node in ast.walk(tree)
                       if isinstance(node, ast.ImportFrom)]
            self.assertEqual(plain.count("library"), 0, relative_path)
            self.assertEqual([name for name in sourced if name.split(".")[0] == "library"],
                             [], relative_path)
            self.assertEqual(sum(1 for node in ast.walk(tree)
                                 if isinstance(node, ast.Name)
                                 and node.id == "library_db_connect"), 0, relative_path)

    def test_shutdown_runtime_cancels_pending_playback_restore_retry(self):
        timer = mock.Mock()
        # The drain is now one-way for the process, so a test that only cares about the
        # retry timer must not actually run it against the shared pool.
        old_timer = server.PLAYBACK_RESTORE_RETRY_TIMER
        try:
            server.PLAYBACK_RESTORE_RETRY_TIMER = timer
            server.enable_playback_restore_retry()
            with mock.patch.object(server, "stop_library_connections"):
                server.shutdown_runtime()
            self.assertTrue(server.PLAYBACK_RESTORE_RETRY_STOP.is_set())
            self.assertIsNone(server.PLAYBACK_RESTORE_RETRY_TIMER)
            timer.cancel.assert_called_once_with()
        finally:
            server.enable_playback_restore_retry()
            server.PLAYBACK_RESTORE_RETRY_TIMER = old_timer


if __name__ == "__main__":
    unittest.main()
