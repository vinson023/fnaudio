import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

import transcode
from transcode import prune_transcode_cache


class TranscodeCacheTests(unittest.TestCase):
    def setUp(self):
        with transcode.TRANSCODE_LOCK:
            transcode.TRANSCODE_QUEUE[:] = []
            transcode.TRANSCODE_JOBS.clear()
            transcode.TRANSCODE_WORKER = None
            transcode.TRANSCODE_SEQUENCE = 0

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
            temporary = os.path.join(root, "track.mp3.tmp.mp3")

            def timeout(*_args, **_kwargs):
                with open(temporary, "wb") as fh:
                    fh.write(b"partial")
                raise transcode.subprocess.TimeoutExpired("ffmpeg", 30)

            with mock.patch.object(transcode, "find_ffmpeg", return_value="ffmpeg"), mock.patch.object(
                transcode.subprocess, "run", side_effect=timeout
            ), mock.patch.object(transcode, "cleanup_transcode_cache_if_due"):
                with self.assertRaisesRegex(RuntimeError, "timed out"):
                    transcode.transcode_to_audio(item, {"cache_dir": root, "cache_min_free_bytes": 64 * 1024 * 1024})

            self.assertFalse(os.path.exists(temporary))

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

    def test_cue_ape_uses_the_cue_flac_segment_mode(self):
        item = {"id": "cue-ape", "path": "/music/album.ape", "cue_track": True}
        target, mime = transcode.transcode_cache_target(item, {}, "cue_flac")

        self.assertTrue(target.endswith("cue-ape.cue-segment.flac"))
        self.assertEqual(mime, "audio/flac")


if __name__ == "__main__":
    unittest.main()
