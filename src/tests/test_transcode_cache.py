import os
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, "app/server")

import transcode
from transcode import prune_transcode_cache


class TranscodeCacheTests(unittest.TestCase):
    def test_direct_clients_cannot_forge_forwarded_playback_profile(self):
        handler = SimpleNamespace(
            client_address=("198.51.100.20", 1234),
            headers={
                "X-Forwarded-For": "8.8.8.8",
                "X-Forwarded-Host": "public.example",
                "X-Forwarded-Proto": "https",
                "Host": "198.51.100.20:53199",
            },
        )
        self.assertEqual(transcode.playback_profile(handler), "lan")
        access = transcode.public_access(handler)
        self.assertEqual(access["client_ip"], "198.51.100.20")
        self.assertEqual(access["host"], "198.51.100.20:53199")
        self.assertEqual(access["proto"], "http")

    def test_loopback_cgi_proxy_forwarded_identity_is_preserved(self):
        handler = SimpleNamespace(
            client_address=("127.0.0.1", 1234),
            headers={
                "X-Forwarded-For": "8.8.8.8",
                "X-Forwarded-Host": "public.example",
                "X-Forwarded-Proto": "https",
                "Host": "127.0.0.1:53199",
            },
        )
        self.assertEqual(transcode.playback_profile(handler), "wan")
        self.assertEqual(transcode.public_access(handler), {
            "profile": "wan",
            "client_ip": "8.8.8.8",
            "host": "public.example",
            "proto": "https",
        })

    def test_direct_clients_cannot_forge_forwarded_public_url_inputs(self):
        handler = SimpleNamespace(
            client_address=("198.51.100.20", 1234),
            headers={
                "X-Forwarded-Host": "public.example:443",
                "X-Forwarded-Proto": "https",
                "Host": "198.51.100.20:53199",
            },
        )
        forwarded = transcode.trusted_forwarded_headers(handler)
        self.assertEqual(forwarded, {})

    def test_cache_target_does_not_stringify_an_untrusted_item_id(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("cache identity must not stringify arbitrary objects")

        target, mime = transcode.transcode_cache_target({"id": Explosive()}, {"cache_dir": "/tmp/cache"})

        self.assertEqual(mime, "audio/mpeg")
        self.assertIn("item-", os.path.basename(target))

    def test_warm_queue_key_uses_safe_cache_identity(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("queue identity must not stringify arbitrary objects")

        fake_thread = mock.Mock()
        fake_thread.is_alive.return_value = True
        with mock.patch.object(transcode, "transcode_cache_ready", return_value=("", "audio/mpeg", False)), mock.patch.object(
            transcode.threading, "Thread", return_value=fake_thread
        ):
            self.assertTrue(transcode.warm_transcode_cache({"id": Explosive()}, {}, priority=100))

        self.assertEqual(len(transcode.TRANSCODE_JOBS), 1)
        self.assertTrue(next(iter(transcode.TRANSCODE_JOBS)).startswith("mp3:item-"))

    def test_warm_queue_does_not_coerce_an_untrusted_priority(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("queue priority must not coerce arbitrary objects")
            def __float__(self):
                raise AssertionError("queue priority must not coerce arbitrary objects")

        fake_thread = mock.Mock()
        fake_thread.is_alive.return_value = True
        with mock.patch.object(transcode, "transcode_cache_ready", return_value=("", "audio/mpeg", False)), mock.patch.object(
            transcode.threading, "Thread", return_value=fake_thread
        ):
            self.assertTrue(transcode.warm_transcode_cache({"id": "priority"}, {}, priority=Explosive()))
        self.assertEqual(transcode.TRANSCODE_QUEUE[0][0], 100)

    def test_safe_float_rejects_non_finite_and_boolean_values(self):
        self.assertEqual(transcode.safe_float(float("nan")), 0.0)
        self.assertEqual(transcode.safe_float(float("inf"), 3.0), 3.0)
        self.assertEqual(transcode.safe_float(True, 3.0), 3.0)

    def test_find_ffmpeg_does_not_modify_candidate_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            candidate = os.path.join(root, "ffmpeg")
            with open(candidate, "wb") as handle:
                handle.write(b"binary")
            with mock.patch.object(transcode, "shutil", SimpleNamespace(which=lambda _name: "")), \
                 mock.patch.object(transcode.os, "chmod") as chmod, \
                 mock.patch.object(transcode.os, "access", return_value=True):
                self.assertEqual(transcode.find_ffmpeg({"ffmpeg_path": candidate}), candidate)
            chmod.assert_not_called()

    def setUp(self):
        with transcode.TRANSCODE_LOCK:
            transcode.TRANSCODE_QUEUE[:] = []
            transcode.TRANSCODE_JOBS.clear()
            transcode.TRANSCODE_WORKER = None
            transcode.TRANSCODE_SEQUENCE = 0
            transcode.TRANSCODE_STOP_EVENT.clear()
            transcode._ACTIVE_TRANSCODE_PATHS.clear()

    def test_shutdown_clears_queued_jobs_and_stops_worker(self):
        fake_thread = mock.Mock()
        fake_thread.is_alive.return_value = True
        config = {"transcode_queue_max_jobs": 3}
        with mock.patch.object(transcode, "transcode_cache_ready", return_value=("", "audio/mpeg", False)), mock.patch.object(
            transcode.threading, "Thread", return_value=fake_thread
        ):
            self.assertTrue(transcode.warm_transcode_cache({"id": "one"}, config))
            self.assertTrue(transcode.warm_transcode_cache({"id": "two"}, config))

        transcode.shutdown_transcode_cache_worker(wait=False)

        self.assertTrue(transcode.TRANSCODE_STOP_EVENT.is_set())
        self.assertEqual(transcode.TRANSCODE_QUEUE, [])
        self.assertEqual(transcode.TRANSCODE_JOBS, set())

    def test_shutdown_worker_rejects_nonfinite_timeout(self):
        worker = mock.Mock()
        worker.is_alive.return_value = False
        with transcode.TRANSCODE_LOCK:
            transcode.TRANSCODE_WORKER = worker
        transcode.shutdown_transcode_cache_worker(wait=True, timeout=float("nan"))
        worker.join.assert_called_once_with(5.0)

    def test_warming_can_restart_after_shutdown_worker_has_exited(self):
        with transcode.TRANSCODE_LOCK:
            transcode.TRANSCODE_STOP_EVENT.set()
            transcode.TRANSCODE_WORKER = None
        fake_thread = mock.Mock()
        fake_thread.is_alive.return_value = True
        with mock.patch.object(transcode, "transcode_cache_ready", return_value=("", "audio/mpeg", False)), mock.patch.object(
            transcode.threading, "Thread", return_value=fake_thread
        ):
            self.assertTrue(transcode.warm_transcode_cache({"id": "restart"}, {}))
        self.assertFalse(transcode.TRANSCODE_STOP_EVENT.is_set())

    def test_worker_start_failure_does_not_strand_transcode_job(self):
        config = {"transcode_queue_max_jobs": 3}
        with mock.patch.object(transcode, "transcode_cache_ready", return_value=("", "audio/mpeg", False)), mock.patch.object(
            transcode.threading, "Thread", side_effect=RuntimeError("no threads")
        ):
            self.assertFalse(transcode.warm_transcode_cache({"id": "start-fails"}, config))
        self.assertEqual(transcode.TRANSCODE_QUEUE, [])
        self.assertNotIn("mp3:start-fails", transcode.TRANSCODE_JOBS)
        self.assertIsNone(transcode.TRANSCODE_WORKER)

    def test_prune_only_removes_audio_transcode_files(self):
        with tempfile.TemporaryDirectory() as root:
            removable = (
                "track.mp3",
                "track.dsd-96k-24bit.wav",
                "track.cue-segment.flac",
                "track.mp3.tmp.mp3",
            )
            persistent = (
                "library.sqlite3",
                "library.sqlite3-wal",
                "state.sqlite3",
                "library.json",
                "online-metadata-cache.json",
            )
            for name in removable + persistent:
                with open(os.path.join(root, name), "wb") as fh:
                    fh.write(b"data")
            metadata_dir = os.path.join(root, "metadata", "artwork")
            os.makedirs(metadata_dir)
            artwork = os.path.join(metadata_dir, "cover.jpg")
            with open(artwork, "wb") as fh:
                fh.write(b"image")

            removed = prune_transcode_cache({"cache_dir": root}, max_age_seconds=-1)

            self.assertEqual(removed, len(removable))
            for name in removable:
                self.assertFalse(os.path.exists(os.path.join(root, name)))
            for name in persistent:
                self.assertTrue(os.path.isfile(os.path.join(root, name)))
            self.assertTrue(os.path.isfile(artwork))

    def test_current_track_cache_runs_before_queued_opportunistic_work(self):
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()
        calls = []

        def fake_transcode(item, config, mode):
            calls.append(item["id"])
            if item["id"] == "blocking":
                started.set()
                release.wait(2)
            if len(calls) == 3:
                finished.set()
            return "", "audio/mpeg"

        with mock.patch.object(transcode, "transcode_cache_ready", return_value=("", "audio/mpeg", False)), mock.patch.object(transcode, "transcode_to_audio", side_effect=fake_transcode):
            self.assertTrue(transcode.warm_transcode_cache({"id": "blocking"}, {}, priority=100))
            self.assertTrue(started.wait(1))
            self.assertTrue(transcode.warm_transcode_cache({"id": "opportunistic"}, {}, priority=100))
            self.assertTrue(transcode.warm_transcode_cache({"id": "current"}, {}, priority=0))
            release.set()
            self.assertTrue(finished.wait(2))

        self.assertEqual(calls, ["blocking", "current", "opportunistic"])

    def test_queue_limit_rejects_normal_work_and_current_track_evicts_worst_job(self):
        fake_thread = mock.Mock()
        fake_thread.is_alive.return_value = True
        config = {"transcode_queue_max_jobs": 2}
        with mock.patch.object(transcode, "transcode_cache_ready", return_value=("", "audio/mpeg", False)), mock.patch.object(
            transcode.threading, "Thread", return_value=fake_thread
        ):
            self.assertTrue(transcode.warm_transcode_cache({"id": "one"}, config, priority=100))
            self.assertTrue(transcode.warm_transcode_cache({"id": "two"}, config, priority=200))
            self.assertFalse(transcode.warm_transcode_cache({"id": "three"}, config, priority=200))
            self.assertTrue(transcode.warm_transcode_cache({"id": "current"}, config, priority=0))

        queued_ids = {entry[3]["id"] for entry in transcode.TRANSCODE_QUEUE}
        self.assertEqual(queued_ids, {"one", "current"})
        self.assertNotIn("mp3:two", transcode.TRANSCODE_JOBS)
        self.assertEqual(len(transcode.TRANSCODE_QUEUE), 2)

    def test_prune_preserves_queued_target_and_removes_oldest_to_meet_byte_limit(self):
        with tempfile.TemporaryDirectory() as root:
            paths = []
            for index, name in enumerate(("active.mp3", "old.mp3", "new.mp3")):
                path = os.path.join(root, name)
                with open(path, "wb") as fh:
                    fh.write(b"x" * 10)
                os.utime(path, (100 + index, 100 + index))
                paths.append(path)
            with transcode.TRANSCODE_LOCK:
                transcode.TRANSCODE_JOBS.add("mp3:active")

            def fake_bound(config, key, default, minimum, maximum):
                return 10 if key == "transcode_cache_max_bytes" else 0

            with mock.patch.object(transcode, "bounded_int", side_effect=fake_bound), mock.patch.object(
                transcode, "disk_has_reserve", return_value=True
            ):
                removed = prune_transcode_cache({"cache_dir": root}, max_age_seconds=10**12)

            self.assertEqual(removed, 1)
            self.assertTrue(os.path.isfile(paths[0]))
            self.assertFalse(os.path.exists(paths[1]))
            self.assertTrue(os.path.isfile(paths[2]))

    def test_prune_preserves_active_cache_for_invalid_item_id(self):
        with tempfile.TemporaryDirectory() as root:
            item = {"id": "../active", "path": os.path.join(root, "source.flac")}
            target, _ = transcode.transcode_cache_target(item, {"cache_dir": root})
            with open(target, "wb") as fh:
                fh.write(b"active")
            os.utime(target, (100, 100))
            with transcode.TRANSCODE_LOCK:
                transcode.TRANSCODE_JOBS.add("mp3:../active")

            removed = prune_transcode_cache({"cache_dir": root}, max_age_seconds=-1)

            self.assertEqual(removed, 0)
            self.assertTrue(os.path.isfile(target))

    def test_prune_preserves_active_synchronous_transcode_paths(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "track.mp3.tmp.mp3")
            with open(path, "wb") as fh:
                fh.write(b"partial")
            os.utime(path, (100, 100))
            with transcode.TRANSCODE_LOCK:
                transcode._ACTIVE_TRANSCODE_PATHS.add(path)

            removed = prune_transcode_cache({"cache_dir": root}, max_age_seconds=-1)

            self.assertEqual(removed, 0)
            self.assertTrue(os.path.isfile(path))

    def test_resource_status_never_exceeds_configured_queue_limit(self):
        fake_thread = mock.Mock()
        fake_thread.is_alive.return_value = True
        config = {"transcode_queue_max_jobs": 1, "ffmpeg_max_concurrency": 1}
        with mock.patch.object(transcode, "transcode_cache_ready", return_value=("", "audio/mpeg", False)), mock.patch.object(
            transcode.threading, "Thread", return_value=fake_thread
        ):
            self.assertTrue(transcode.warm_transcode_cache({"id": "one"}, config))
            self.assertFalse(transcode.warm_transcode_cache({"id": "two"}, config))
        status = transcode.transcode_resource_status(config)
        self.assertEqual(status["queued"], 1)
        self.assertEqual(status["queue_limit"], 1)
        self.assertLessEqual(status["queued"], status["queue_limit"])

    def test_transcode_timeout_removes_partial_file(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "source.flac")
            with open(source, "wb") as fh:
                fh.write(b"source")
            item = {"id": "track", "path": source, "mime": "audio/flac"}

            def timeout(command, **_kwargs):
                with open(command[-1], "wb") as fh:
                    fh.write(b"partial")
                raise transcode.subprocess.TimeoutExpired("ffmpeg", 30)

            with mock.patch.object(transcode, "find_ffmpeg", return_value="ffmpeg"), mock.patch.object(
                transcode.subprocess, "run", side_effect=timeout
            ), mock.patch.object(transcode, "cleanup_transcode_cache_if_due"):
                with self.assertRaisesRegex(RuntimeError, "timed out"):
                    transcode.transcode_to_audio(item, {"cache_dir": root, "cache_min_free_bytes": 64 * 1024 * 1024})

            self.assertEqual([name for name in os.listdir(root) if ".tmp." in name], [])

    def test_ape_flac_mode_uses_lossless_cache_target_and_ffmpeg_flac_encoder(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "source.ape")
            with open(source, "wb") as fh:
                fh.write(b"MAC ")
            item = {"id": "ape-track", "path": source, "mime": "audio/ape"}

            def fake_run(command, **_kwargs):
                with open(command[-1], "wb") as fh:
                    fh.write(b"fLaC")
                return mock.Mock(returncode=0, stderr=b"")

            with mock.patch.object(transcode, "find_ffmpeg", return_value="ffmpeg"), mock.patch.object(
                transcode.subprocess, "run", side_effect=fake_run
            ) as run, mock.patch.object(transcode, "cleanup_transcode_cache_if_due"):
                target, mime = transcode.transcode_to_audio(item, {"cache_dir": root, "cache_min_free_bytes": 0}, "ape_flac")

            self.assertEqual(mime, "audio/flac")
            self.assertTrue(target.endswith("ape-track.ape-source.flac"))
            command = run.call_args.args[0]
            self.assertIn("flac", command)

    def test_transcode_captures_stderr_to_a_bounded_file_not_memory_pipe(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "source.flac")
            with open(source, "wb") as fh:
                fh.write(b"source")
            item = {"id": "track", "path": source, "mime": "audio/flac"}
            failed = mock.Mock(returncode=1, stderr=b"")
            with mock.patch.object(transcode, "find_ffmpeg", return_value="ffmpeg"), mock.patch.object(
                transcode.subprocess, "run", return_value=failed
            ) as run, mock.patch.object(transcode, "cleanup_transcode_cache_if_due"):
                with self.assertRaisesRegex(RuntimeError, "音频转码失败"):
                    transcode.transcode_to_audio(item, {"cache_dir": root, "cache_min_free_bytes": 0})
            self.assertNotEqual(run.call_args.kwargs.get("stderr"), transcode.subprocess.PIPE)

    def test_real_transcode_stops_when_diagnostic_output_exceeds_limit(self):
        process = mock.Mock()
        process.pid = 321
        process.poll.return_value = None
        process.wait.return_value = 0
        errors = mock.Mock()
        errors.tell.return_value = transcode.MAX_TRANSCODE_STDERR_BYTES + 1

        def real_run_marker(*_args, **_kwargs):
            raise AssertionError("real transcode must use Popen")
        real_run_marker.__module__ = "subprocess"
        with mock.patch.object(transcode.subprocess, "run", real_run_marker), \
             mock.patch.object(transcode.subprocess, "Popen", return_value=process), \
             mock.patch.object(transcode.os, "killpg", create=True) as killpg:
            with self.assertRaisesRegex(transcode.ResourceLimitError, "diagnostic output"):
                transcode._run_transcode_process(
                    ["ffmpeg"], stdout=transcode.subprocess.DEVNULL, stderr=errors,
                    timeout=1, env={},
                )
        if os.name != "nt":
            killpg.assert_called_once_with(321, transcode.signal.SIGKILL)
        else:
            process.kill.assert_called_once_with()

    def test_completed_transcode_still_enforces_diagnostic_output_limit(self):
        process = mock.Mock()
        process.pid = 654
        process.poll.return_value = 0
        process.wait.return_value = 0
        errors = mock.Mock()
        errors.tell.return_value = transcode.MAX_TRANSCODE_STDERR_BYTES + 1

        def real_run_marker(*_args, **_kwargs):
            raise AssertionError("real transcode must use Popen")
        real_run_marker.__module__ = "subprocess"
        with mock.patch.object(transcode.subprocess, "run", real_run_marker), \
             mock.patch.object(transcode.subprocess, "Popen", return_value=process):
            with self.assertRaisesRegex(transcode.ResourceLimitError, "diagnostic output"):
                transcode._run_transcode_process(
                    ["ffmpeg"], stdout=transcode.subprocess.DEVNULL, stderr=errors,
                    timeout=1, env={},
                )

    def test_diagnostic_output_limit_removes_partial_transcode_file(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "source.flac")
            with open(source, "wb") as fh:
                fh.write(b"source")
            item = {"id": "track", "path": source, "mime": "audio/flac"}

            def too_noisy(command, **_kwargs):
                with open(command[-1], "wb") as fh:
                    fh.write(b"partial")
                raise transcode.ResourceLimitError("transcode diagnostic output is too large")

            with mock.patch.object(transcode, "find_ffmpeg", return_value="ffmpeg"), \
                 mock.patch.object(transcode, "_run_transcode_process", side_effect=too_noisy), \
                 mock.patch.object(transcode, "cleanup_transcode_cache_if_due"):
                with self.assertRaisesRegex(RuntimeError, "diagnostic output"):
                    transcode.transcode_to_audio(item, {"cache_dir": root, "cache_min_free_bytes": 0})
            self.assertEqual([name for name in os.listdir(root) if ".tmp." in name], [])

    def test_unexpected_publish_failure_removes_partial_transcode_file(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "source.flac")
            with open(source, "wb") as fh:
                fh.write(b"source")
            item = {"id": "track", "path": source, "mime": "audio/flac"}

            def successful_run(command, **_kwargs):
                with open(command[-1], "wb") as fh:
                    fh.write(b"partial")
                return mock.Mock(returncode=0, stderr=b"")

            with mock.patch.object(transcode, "find_ffmpeg", return_value="ffmpeg"), \
                 mock.patch.object(transcode.subprocess, "run", side_effect=successful_run), \
                 mock.patch.object(transcode, "secure_file", side_effect=OSError("publish failed")), \
                 mock.patch.object(transcode, "cleanup_transcode_cache_if_due"):
                # Publish failures must surface as RuntimeError: every request
                # path handler for /media/* only guards RuntimeError, so a bare
                # OSError would drop the connection instead of answering 501.
                with self.assertRaisesRegex(RuntimeError, "publish transcode cache"):
                    transcode.transcode_to_audio(item, {"cache_dir": root, "cache_min_free_bytes": 0})

            self.assertEqual([name for name in os.listdir(root) if ".tmp." in name], [])

    def test_transcode_attempts_use_unique_temporary_paths(self):
        target = "/cache/track.mp3"
        with mock.patch.object(transcode.uuid, "uuid4", side_effect=[
            mock.Mock(hex="first"), mock.Mock(hex="second"),
        ]):
            first = transcode._transcode_temp_path(target)
            second = transcode._transcode_temp_path(target)

        self.assertTrue(first.endswith(".tmp.first.mp3"))
        self.assertTrue(second.endswith(".tmp.second.mp3"))
        self.assertNotEqual(first, second)

    def test_cue_ape_uses_the_cue_flac_segment_mode(self):
        item = {"id": "cue-ape", "path": "/music/album.ape", "cue_track": True}
        target, mime = transcode.transcode_cache_target(item, {}, "cue_flac")

        self.assertTrue(target.endswith("cue-ape.cue-segment.flac"))
        self.assertEqual(mime, "audio/flac")

    def test_cue_cache_is_stale_when_cue_file_is_newer_than_target(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "album.ape")
            cue = os.path.join(root, "album.cue")
            target = os.path.join(root, "cue-track.cue-segment.flac")
            for path in (source, cue, target):
                with open(path, "wb") as fh:
                    fh.write(b"data")
            os.utime(source, (100, 100))
            os.utime(target, (150, 150))
            os.utime(cue, (200, 200))

            item = {
                "id": "cue-track",
                "path": source,
                "cue_path": cue,
            }
            _, _, ready = transcode.transcode_cache_ready(item, {"cache_dir": root}, "cue_flac")

            self.assertFalse(ready)

    def test_transcode_cache_ignores_missing_cue_file(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "source.flac")
            target = os.path.join(root, "track.mp3")
            for path in (source, target):
                with open(path, "wb") as fh:
                    fh.write(b"data")
            os.utime(source, (100, 100))
            os.utime(target, (150, 150))

            item = {
                "id": "track",
                "path": source,
                "cue_path": os.path.join(root, "missing.cue"),
            }
            _, _, ready = transcode.transcode_cache_ready(item, {"cache_dir": root})

            self.assertTrue(ready)

    def test_transcode_cache_treats_target_disappearing_during_stat_as_miss(self):
        item = {"id": "vanishing", "path": "source.flac"}
        with mock.patch.object(transcode.os.path, "isfile", return_value=True), mock.patch.object(
            transcode.os.path, "getmtime", side_effect=FileNotFoundError
        ):
            target, mime, ready = transcode.transcode_cache_ready(item, {}, "mp3")

        self.assertTrue(target.endswith("vanishing.mp3"))
        self.assertEqual(mime, "audio/mpeg")
        self.assertFalse(ready)

    def test_cache_ready_degrades_when_source_file_is_gone(self):
        # /api/transcode/status and /api/transcode/warm look up stale index
        # rows without an isfile() guard, so a deleted or unmounted source has
        # to read as a cache miss instead of raising out of the request path.
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "gone.mp3")
            with open(target, "wb") as fh:
                fh.write(b"cached")
            item = {"id": "gone", "path": os.path.join(root, "gone.flac")}

            found, mime, ready = transcode.transcode_cache_ready(item, {"cache_dir": root})

            self.assertEqual(found, target)
            self.assertEqual(mime, "audio/mpeg")
            self.assertFalse(ready)

    def test_missing_source_raises_handled_transcode_error_not_oserror(self):
        with tempfile.TemporaryDirectory() as root:
            item = {"id": "gone", "path": os.path.join(root, "gone.flac"), "mime": "audio/flac"}
            with mock.patch.object(transcode, "find_ffmpeg", return_value="ffmpeg"), mock.patch.object(
                transcode, "cleanup_transcode_cache_if_due"
            ):
                with self.assertRaisesRegex(RuntimeError, "source is no longer readable"):
                    transcode.transcode_to_audio(item, {"cache_dir": root, "cache_min_free_bytes": 0})

    def test_unpublishable_cache_write_raises_handled_transcode_error(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "source.flac")
            with open(source, "wb") as fh:
                fh.write(b"source")
            item = {"id": "track", "path": source, "mime": "audio/flac"}

            def fake_run(command, **_kwargs):
                with open(command[-1], "wb") as fh:
                    fh.write(b"audio")
                return mock.Mock(returncode=0, stderr=b"")

            def fail_replace(*_args, **_kwargs):
                raise OSError("no space left on device")

            with mock.patch.object(transcode, "find_ffmpeg", return_value="ffmpeg"), mock.patch.object(
                transcode.subprocess, "run", side_effect=fake_run
            ), mock.patch.object(transcode, "cleanup_transcode_cache_if_due"), mock.patch.object(
                transcode.os, "replace", side_effect=fail_replace
            ):
                with self.assertRaisesRegex(RuntimeError, "publish transcode cache"):
                    transcode.transcode_to_audio(item, {"cache_dir": root, "cache_min_free_bytes": 0})

            self.assertEqual([name for name in os.listdir(root) if ".tmp." in name], [])

    def test_cache_cleanup_sweeps_once_per_interval(self):
        with mock.patch.object(transcode, "LAST_CACHE_CLEANUP", 0), mock.patch.object(
            transcode, "prune_transcode_cache", return_value=0
        ) as prune:
            transcode.cleanup_transcode_cache_if_due({"cache_dir": "unused"})
            transcode.cleanup_transcode_cache_if_due({"cache_dir": "unused"})

        self.assertEqual(prune.call_count, 1)

    def test_failed_cache_sweep_still_arms_the_cleanup_interval(self):
        # Without this the stamp stayed unarmed after every raise, so each
        # transcode retried a full sweep of a directory that keeps failing.
        with mock.patch.object(transcode, "LAST_CACHE_CLEANUP", 0), mock.patch.object(
            transcode, "prune_transcode_cache", side_effect=OSError("stale mount")
        ) as prune:
            transcode.cleanup_transcode_cache_if_due({"cache_dir": "unused"})
            transcode.cleanup_transcode_cache_if_due({"cache_dir": "unused"})

        self.assertEqual(prune.call_count, 1)

    def test_concurrent_cleanup_requests_share_one_sweep(self):
        # Two playback requests can miss the cache in the same instant. Without
        # the claim lock both walk the whole cache directory on the request path.
        started = threading.Event()
        release = threading.Event()
        sweeps = []

        def fake_prune(_config):
            sweeps.append(1)
            started.set()
            release.wait(2)
            return 0

        with mock.patch.object(transcode, "LAST_CACHE_CLEANUP", 0), mock.patch.object(
            transcode, "prune_transcode_cache", side_effect=fake_prune
        ):
            first = threading.Thread(target=transcode.cleanup_transcode_cache_if_due, args=({"cache_dir": "unused"},))
            first.start()
            self.assertTrue(started.wait(1))
            second = threading.Thread(target=transcode.cleanup_transcode_cache_if_due, args=({"cache_dir": "unused"},))
            second.start()
            second.join(2)
            release.set()
            first.join(2)

        self.assertEqual(len(sweeps), 1)

    def test_force_cleanup_bypasses_the_interval(self):
        with mock.patch.object(transcode, "LAST_CACHE_CLEANUP", transcode.time.time()), mock.patch.object(
            transcode, "prune_transcode_cache", return_value=0
        ) as prune:
            transcode.cleanup_transcode_cache_if_due({"cache_dir": "unused"})
            transcode.cleanup_transcode_cache_if_due({"cache_dir": "unused"}, force=True)

        self.assertEqual(prune.call_count, 1)

    def test_prune_returns_when_cache_dir_vanishes_mid_sweep(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(transcode.os.path, "isdir", return_value=True), mock.patch.object(
                transcode.os, "listdir", side_effect=OSError("stale file handle")
            ):
                self.assertEqual(prune_transcode_cache({"cache_dir": root}), 0)

    def test_cache_target_hashes_invalid_item_id_without_escaping_cache_dir(self):
        with tempfile.TemporaryDirectory() as root:
            target, _ = transcode.transcode_cache_target(
                {"id": "../outside", "path": os.path.join(root, "source.flac")},
                {"cache_dir": root},
            )
            self.assertEqual(os.path.commonpath((os.path.realpath(root), os.path.realpath(os.path.dirname(target)))), os.path.realpath(root))
            self.assertTrue(os.path.basename(target).startswith("item-"))

    def test_same_target_transcodes_are_serialized(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "source.flac")
            with open(source, "wb") as fh:
                fh.write(b"source")
            item = {"id": "shared", "path": source, "mime": "audio/flac"}
            entered = threading.Event()
            release = threading.Event()
            calls = []

            def fake_run(command, **_kwargs):
                calls.append(command[-1])
                entered.set()
                release.wait(2)
                with open(command[-1], "wb") as fh:
                    fh.write(b"audio")
                return mock.Mock(returncode=0, stderr=b"")

            with mock.patch.object(transcode, "find_ffmpeg", return_value="ffmpeg"), mock.patch.object(
                transcode.subprocess, "run", side_effect=fake_run
            ), mock.patch.object(transcode, "cleanup_transcode_cache_if_due"), mock.patch.object(
                transcode, "disk_has_reserve", return_value=True
            ):
                first = threading.Thread(target=transcode.transcode_to_audio, args=(item, {"cache_dir": root, "cache_min_free_bytes": 0}))
                second = threading.Thread(target=transcode.transcode_to_audio, args=(item, {"cache_dir": root, "cache_min_free_bytes": 0}))
                first.start()
                self.assertTrue(entered.wait(1))
                second.start()
                release.set()
                first.join(2)
                second.join(2)

            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
