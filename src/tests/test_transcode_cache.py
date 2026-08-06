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


if __name__ == "__main__":
    unittest.main()
