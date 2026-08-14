import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, "app/server")

import cover_cache


class CoverCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = {"cache_dir": self.temp.name}
        self.item = {"id": "track", "path": "/music/track.flac", "modified_ns": 123}

    def tearDown(self):
        cover_cache.shutdown_library_thumbnail_prewarm(wait=True)
        self.temp.cleanup()

    def test_thumbnail_is_persisted_and_reused(self):
        reader = mock.Mock(return_value=("image/png", b"original"))
        with mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb") as resize:
            first = cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader)
            second = cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader)
        self.assertEqual(first, ("image/jpeg", b"\xff\xd8thumb"))
        self.assertEqual(second, first)
        reader.assert_called_once()
        resize.assert_called_once()

    def test_concurrent_requests_generate_once(self):
        calls = []

        def reader(_item, _config):
            calls.append(1)
            time.sleep(0.05)
            return "image/jpeg", b"original"

        results = []
        with mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb"):
            threads = [threading.Thread(target=lambda: results.append(
                cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader))) for _ in range(6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        self.assertEqual(len(calls), 1)
        self.assertEqual(results, [("image/jpeg", b"\xff\xd8thumb")] * 6)

    def test_missing_cover_uses_negative_cache(self):
        reader = mock.Mock(return_value=(None, None))
        self.assertEqual(cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader), (None, None))
        self.assertTrue(cover_cache.cover_is_known_missing(self.item, self.config, 160))
        self.assertEqual(cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader), (None, None))
        reader.assert_called_once()

    def test_modified_source_uses_a_new_cache_entry(self):
        reader = mock.Mock(return_value=(None, None))
        cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader)
        changed = dict(self.item, modified_ns=124)
        self.assertFalse(cover_cache.cover_is_known_missing(changed, self.config, 160))

    def test_cue_item_uses_audio_mtime_to_invalidate_missing_cover(self):
        audio = os.path.join(self.temp.name, "album.ape")
        with open(audio, "wb") as handle:
            handle.write(b"audio")
        cue_item = {"id": "cue-track", "path": audio, "modified_ns": 1}
        reader = mock.Mock(return_value=(None, None))
        cover_cache.cached_thumbnail_for_item(cue_item, self.config, 160, reader)
        with open(audio, "ab") as handle:
            handle.write(b"tag-update")
        os.utime(audio, None)
        self.assertFalse(cover_cache.cover_is_known_missing(cue_item, self.config, 160))

    def test_identical_artwork_shares_one_thumbnail_asset(self):
        first = dict(self.item, id="first")
        second = dict(self.item, id="second", path="/music/second.flac")
        reader = mock.Mock(return_value=("image/jpeg", b"shared-original"))
        with mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb"):
            cover_cache.cached_thumbnail_for_item(first, self.config, 160, reader)
            cover_cache.cached_thumbnail_for_item(second, self.config, 160, reader)
        assets = os.listdir(os.path.join(self.temp.name, "covers", "assets", "thumb-160"))
        self.assertEqual(len(assets), 1)
        self.assertTrue(assets[0].endswith(".jpg"))
        asset_id = cover_cache.thumbnail_asset_id_for_item(first, self.config, 160)
        self.assertEqual(len(asset_id), 64)
        self.assertEqual(cover_cache.thumbnail_asset_bytes(self.config, asset_id, 160), ("image/jpeg", b"\xff\xd8thumb"))

    def test_thumbnail_uses_shared_ffmpeg_resource_gate(self):
        with mock.patch.object(cover_cache, "find_ffmpeg", return_value="ffmpeg"), \
             mock.patch.object(cover_cache, "ffmpeg_slot", return_value=nullcontext()) as slot, \
             mock.patch.object(cover_cache.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b"\xff\xd8thumb")):
            result = cover_cache._thumbnail_bytes(b"cover", self.config, 160, ffmpeg_slot_timeout=0.25)
        self.assertEqual(result, b"\xff\xd8thumb")
        slot.assert_called_once_with(self.config, timeout=0.25)

    def test_cancelled_library_prewarm_does_not_write_after_reader_returns(self):
        started = threading.Event()
        release = threading.Event()

        def reader(_item, _config):
            started.set()
            release.wait(2)
            return "image/jpeg", b"original"

        item = dict(self.item, path=__file__)
        cover_cache.prewarm_library_thumbnails([item], self.config, reader)
        self.assertTrue(started.wait(2))
        cover_cache.shutdown_library_thumbnail_prewarm()
        release.set()
        cover_cache.shutdown_library_thumbnail_prewarm(wait=True)
        self.assertFalse(os.path.exists(os.path.join(self.temp.name, "covers")))


if __name__ == "__main__":
    unittest.main()
