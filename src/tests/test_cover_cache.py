import hashlib
import inspect
import os
import re
import sys
import tempfile
import threading
import time
import gc
import weakref
import unittest
from collections import OrderedDict
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, "app/server")

import cover_cache


class CoverCacheTests(unittest.TestCase):
    def test_atomic_bytes_closes_descriptor_when_fdopen_fails(self):
        with tempfile.TemporaryDirectory() as root:
            descriptor = 987653
            temporary = os.path.join(root, ".failed-cover.tmp")
            with mock.patch.object(cover_cache.tempfile, "mkstemp", return_value=(descriptor, temporary)), \
                 mock.patch.object(cover_cache.os, "fdopen", side_effect=OSError("fdopen failed")), \
                 mock.patch.object(cover_cache.os, "close") as close:
                with self.assertRaises(OSError):
                    cover_cache._atomic_bytes(os.path.join(root, "cover.jpg"), b"image")
            close.assert_called_once_with(descriptor)

    def test_cover_source_version_reuses_indexed_identity_without_stat(self):
        item = {"path": "/missing/slow.nas.flac", "modified_ns": 123, "size": 456}
        with mock.patch("cover_cache.os.stat", side_effect=AssertionError("stat should not run")):
            self.assertEqual(cover_cache.cover_source_version(item), "123:456")

    def test_thumbnail_thread_start_failure_terminates_and_reaps_child(self):
        process = mock.Mock()
        process.pid = 321
        with (
            mock.patch.object(cover_cache.subprocess, "Popen", return_value=process),
            mock.patch.object(
                cover_cache.threading.Thread,
                "start",
                side_effect=RuntimeError("no threads"),
            ),
            mock.patch.object(cover_cache, "_terminate_thumbnail_process") as terminate,
        ):
            with self.assertRaises(RuntimeError):
                cover_cache._run_thumbnail_process(["thumbnail"], b"image", mock.Mock(), {}, 1)
        terminate.assert_called_once_with(process)

    def test_fast_cover_source_version_does_not_stat_unindexed_path(self):
        item = {"path": "/missing/slow.nas.flac"}
        with mock.patch("cover_cache.os.stat", side_effect=AssertionError("fast page version must not stat")):
            self.assertEqual(cover_cache.cover_source_version(item, allow_disk=False), "0")

    def test_cover_size_rejects_boolean_and_object_coercion(self):
        self.assertEqual(cover_cache.normalized_cover_size(True), 0)
        self.assertEqual(cover_cache.normalized_cover_size(object()), 0)
        self.assertEqual(cover_cache.normalized_cover_size(10**1000), 512)

    def test_missing_file_version_rejects_object_fallback(self):
        self.assertEqual(cover_cache.cover_source_version({"path": "missing", "modified_ns": object()}), "0")

    def test_cover_cache_key_never_stringifies_untrusted_item_identity(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("cover cache must not stringify item fields")

        item = {"id": Explosive(), "path": Explosive(), "modified_ns": 1, "size": 1}
        self.assertEqual(cover_cache.cover_source_version(item), "1:1")
        self.assertIsInstance(cover_cache._cache_key(item, 160), str)

    def test_thumbnail_asset_lookup_rejects_untrusted_or_oversized_ids(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("asset lookup must not stringify arbitrary ids")

        self.assertIsNone(cover_cache.thumbnail_asset_bytes(self.config, Explosive(), 160))
        self.assertIsNone(cover_cache.thumbnail_asset_bytes(self.config, "a" * 129, 160))

    def test_thumbnail_prewarm_shutdown_rejects_nonfinite_timeout(self):
        thread = mock.Mock()
        thread.is_alive.return_value = True
        state = {"cancel": threading.Event(), "pending": [], "items": [], "thread": thread}
        with mock.patch.object(cover_cache, "_INTERACTIVE_PREWARM", {"test": state}), \
             mock.patch.object(cover_cache, "_LIBRARY_PREWARM", {}):
            cover_cache.shutdown_library_thumbnail_prewarm(wait=True, timeout=float("nan"))
        thread.join.assert_called_once()
        self.assertGreaterEqual(thread.join.call_args.args[0], 0.0)


    def test_per_cover_locks_are_reclaimed_after_generation_finishes(self):
        key = "ephemeral-cover-lock"
        with cover_cache._LOCKS_GUARD:
            cover_cache._LOCKS.pop(key, None)
        lock = cover_cache._key_lock(key)
        reference = weakref.ref(lock)
        self.assertIs(cover_cache._key_lock(key), lock)
        del lock
        gc.collect()
        self.assertIsNone(reference())
        with cover_cache._LOCKS_GUARD:
            self.assertNotIn(key, cover_cache._LOCKS)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = {"cache_dir": self.temp.name}
        self.item = {"id": "track", "path": "/music/track.flac", "modified_ns": 123}

    def test_non_text_cache_directory_uses_a_stable_safe_default(self):
        class UnsafeText:
            def __str__(self):
                raise AssertionError("cache directory must not stringify arbitrary objects")

        self.assertEqual(cover_cache._cache_directory({"cache_dir": UnsafeText()}), ".")
        root, _target, _missing = cover_cache._cache_paths(self.item, {"cache_dir": UnsafeText()}, 160)
        self.assertEqual(root, os.path.join(".", "covers", "thumb-160"))

    def tearDown(self):
        cover_cache.shutdown_library_thumbnail_prewarm(wait=True)
        self.temp.cleanup()

    def _retire_window_injector(self, ready, inject, fire_on):
        """Instrumented ``_PREWARM_LOCK``: run ``inject`` on the ``fire_on``-th
        release that satisfies ``ready``.

        Counting lock releases is what stands a page or scan request up for the one
        window that matters - after a prewarm worker decided the queue is empty and
        before it gives up ``running``. ``ready`` reads a state object captured on the
        first pass because a correct worker unpublishes that state while still holding
        the lock, and ``fire_on`` skips the earlier releases that also show an empty
        queue (the bookkeeping turn, and the caller that started the worker).
        """
        class RetireWindowLock:
            def __init__(self, inner):
                self._inner = inner
                self._seen = 0

            def __enter__(self):
                self._inner.__enter__()
                return self

            def __exit__(self, *exc):
                result = self._inner.__exit__(*exc)
                if ready():
                    self._seen += 1
                    if self._seen == fire_on:
                        inject()
                return result

        return RetireWindowLock(cover_cache._PREWARM_LOCK)

    def test_interactive_prewarm_page_queued_while_retiring_still_gets_a_worker(self):
        cache_key = os.path.abspath(cover_cache._cache_directory(self.config))
        warmed = []
        captured = {}

        def ready():
            state = captured.get("state") or cover_cache._INTERACTIVE_PREWARM.get(cache_key)
            if state is None:
                return False
            captured["state"] = state
            return bool(warmed) and not state["pending"] and not state["inflight"]

        def later_page():
            cover_cache.prewarm_thumbnails(
                [dict(self.item, id="later", path="/music/later.flac")], self.config, mock.Mock(), size=160
            )

        with mock.patch.object(cover_cache, "_prewarm_result_exists", return_value=False), \
             mock.patch.object(
                 cover_cache,
                 "cached_thumbnail_for_item",
                 side_effect=lambda item, *_args, **_kwargs: warmed.append(item["id"]),
             ), \
             mock.patch.object(
                 cover_cache,
                 "_PREWARM_LOCK",
                 self._retire_window_injector(ready, later_page, fire_on=2),
             ):
            cover_cache.prewarm_thumbnails([dict(self.item, id="first")], self.config, mock.Mock(), size=160)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and "later" not in warmed:
                time.sleep(0.01)

        self.assertIn(
            "later", warmed, "a page queued while the worker retired must not be left behind a dead worker"
        )

    def test_library_prewarm_scan_queued_while_retiring_still_gets_a_worker(self):
        cache_key = os.path.abspath(cover_cache._cache_directory(self.config))
        warmed = []
        captured = {}

        def ready():
            state = captured.get("state") or cover_cache._LIBRARY_PREWARM.get(cache_key)
            if state is None:
                return False
            captured["state"] = state
            return not state["items"]

        def later_scan():
            cover_cache.prewarm_library_thumbnails(
                [dict(self.item, id="later", path=__file__)], self.config, mock.Mock(), size=160
            )

        with mock.patch.object(
            cover_cache,
            "cached_thumbnail_for_item",
            side_effect=lambda item, *_args, **_kwargs: warmed.append(item["id"]),
        ), mock.patch.object(
            cover_cache, "_PREWARM_LOCK", self._retire_window_injector(ready, later_scan, fire_on=3)
        ):
            # An empty scan still starts a worker, which immediately finds nothing
            # left to do and retires; that retire is the window under test.
            cover_cache.prewarm_library_thumbnails([], self.config, mock.Mock(), size=160)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and "later" not in warmed:
                time.sleep(0.01)

        self.assertIn(
            "later", warmed, "a scan queued while the worker retired must not be left behind a dead worker"
        )


    def test_thumbnail_is_persisted_and_reused(self):
        reader = mock.Mock(return_value=("image/png", b"original"))
        with mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb") as resize:
            first = cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader)
            second = cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader)
        self.assertEqual(first, ("image/jpeg", b"\xff\xd8thumb"))
        self.assertEqual(second, first)
        reader.assert_called_once()
        resize.assert_called_once()

    def test_interactive_prewarm_skips_results_the_writer_actually_produces(self):
        # Three on-disk markers, every one a state production can leave behind:
        # `<key>.asset` is the alias cached_thumbnail_for_item writes on success,
        # `<key>.none` is the negative marker, and `<key>.jpg` is the positive file
        # older releases wrote (and which is still read back).  Handing prewarm a
        # file it can never see is what let this skip go untested.
        root, target, missing = cover_cache._cache_paths(self.item, self.config, 160)
        alias = target[:-4] + ".asset"
        asset_root, asset_file = cover_cache._asset_path(self.config, 160, "a" * 64)
        os.makedirs(root, exist_ok=True)
        for marker in (alias, missing, target):
            with self.subTest(marker=os.path.basename(marker).split(".")[-1]):
                with open(marker, "wb") as handle:
                    handle.write(("a" * 64 if marker == alias else "cached").encode("ascii"))
                if marker == alias:
                    # The writer produces asset-then-alias, so a real success state has
                    # both; the alias alone is the reclaimed case tested further down.
                    os.makedirs(asset_root, exist_ok=True)
                    with open(asset_file, "wb") as handle:
                        handle.write(b"\xff\xd8jpeg")
                try:
                    self.assertTrue(
                        cover_cache._prewarm_result_exists(self.item, self.config, 160),
                        "prewarm must not re-render when %s exists" % marker,
                    )
                    with mock.patch.object(cover_cache, "cached_thumbnail_for_item") as warm:
                        cover_cache.prewarm_thumbnails([self.item], self.config, mock.Mock())
                        time.sleep(0.05)
                        warm.assert_not_called()
                finally:
                    os.unlink(marker)
                    if marker == alias:
                        os.unlink(asset_file)
                    cover_cache.clear_memory_cache()
        cover_cache.shutdown_library_thumbnail_prewarm(wait=True)

    def test_interactive_prewarm_still_warms_an_item_with_nothing_on_disk(self):
        self.assertFalse(cover_cache._prewarm_result_exists(self.item, self.config, 160))
        deadline = time.time() + 5.0
        with mock.patch.object(cover_cache, "cached_thumbnail_for_item") as warm:
            cover_cache.prewarm_thumbnails([self.item], self.config, mock.Mock())
            while warm.call_count == 0 and time.time() < deadline:
                time.sleep(0.01)
            self.assertEqual(warm.call_count, 1, "an uncached item must still be warmed")
        cover_cache.shutdown_library_thumbnail_prewarm(wait=True)

    def test_failed_asset_persist_still_serves_the_rendered_thumbnail(self):
        # A full or read-only volume must not turn a cold cover into a failed
        # response: the bytes rendered for this request are already in memory.
        reader = mock.Mock(return_value=("image/png", b"original"))
        cover_cache.clear_memory_cache()
        with mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb"), \
             mock.patch.object(cover_cache, "_atomic_bytes", side_effect=OSError("disk full")):
            value = cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader)
        self.assertEqual(value, ("image/jpeg", b"\xff\xd8thumb"))

    def test_failed_asset_persist_does_not_advertise_an_unstored_asset(self):
        # The in-memory alias cache answers latency-sensitive page serialization
        # without touching disk, so it may only name an asset that was persisted.
        reader = mock.Mock(return_value=("image/png", b"original"))
        cover_cache.clear_memory_cache()
        with mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb"), \
             mock.patch.object(cover_cache, "_atomic_bytes", side_effect=OSError("read-only volume")):
            cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader)
        self.assertEqual(
            cover_cache.thumbnail_asset_id_for_item(self.item, self.config, 160, allow_disk=False), "")
        self.assertEqual(cover_cache.thumbnail_asset_id_for_item(self.item, self.config, 160), "")

    def test_successful_persist_advertises_the_stored_asset(self):
        reader = mock.Mock(return_value=("image/png", b"original"))
        cover_cache.clear_memory_cache()
        with mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb"):
            cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader)
        expected = hashlib.sha256(b"original").hexdigest()
        self.assertEqual(
            cover_cache.thumbnail_asset_id_for_item(self.item, self.config, 160, allow_disk=False), expected)
        self.assertTrue(os.path.isfile(cover_cache._cache_paths(self.item, self.config, 160)[1][:-4] + ".asset"))

    def test_failed_negative_marker_write_still_answers_the_miss(self):
        reader = mock.Mock(return_value=(None, None))
        cover_cache.clear_memory_cache()
        with mock.patch.object(cover_cache, "_atomic_bytes", side_effect=OSError("disk full")):
            self.assertEqual(
                cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader), (None, None))
        # The in-memory marker is what keeps a later page from re-reading artwork.
        self.assertTrue(cover_cache.cover_is_known_missing(self.item, self.config, 160, allow_disk=False))
        reader.assert_called_once()

    def test_oversized_cached_thumbnail_is_not_loaded_into_memory(self):
        root, target, _missing = cover_cache._cache_paths(self.item, self.config, 160)
        os.makedirs(root, exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(b"x" * (cover_cache.MAX_CACHED_COVER_BYTES + 1))
        reader = mock.Mock(return_value=(None, None))
        self.assertEqual(cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader), (None, None))
        reader.assert_called_once()

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

    def test_known_missing_marker_reuses_bounded_positive_cache(self):
        root, _target, missing = cover_cache._cache_paths(self.item, self.config, 160)
        os.makedirs(root, exist_ok=True)
        with open(missing, "wb") as handle:
            handle.write(b"none")
        with cover_cache._MEMORY_CACHE_LOCK:
            cover_cache._MISSING_MARKER_CACHE.clear()
        with mock.patch("cover_cache.os.path.isfile", wraps=os.path.isfile) as is_file:
            self.assertTrue(cover_cache.cover_is_known_missing(self.item, self.config, 160))
            self.assertTrue(cover_cache.cover_is_known_missing(self.item, self.config, 160))
            self.assertEqual(is_file.call_count, 1)
        with cover_cache._MEMORY_CACHE_LOCK:
            self.assertIn(missing, cover_cache._MISSING_MARKER_CACHE)

    def test_expired_missing_marker_retries_a_new_sidecar_cover(self):
        reader = mock.Mock(return_value=(None, None))
        self.assertEqual(cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader), (None, None))
        _root, _target, missing = cover_cache._cache_paths(self.item, self.config, 160)
        expired = time.time() - cover_cache.MISSING_MARKER_TTL_SECONDS - 1
        os.utime(missing, (expired, expired))
        with cover_cache._MEMORY_CACHE_LOCK:
            cover_cache._MISSING_MARKER_CACHE.clear()
        reader.return_value = ("image/jpeg", b"new-sidecar")
        self.assertEqual(cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader), ("image/jpeg", b"new-sidecar"))
        self.assertFalse(os.path.exists(missing))
        self.assertEqual(reader.call_count, 2)

    def test_fast_page_cover_lookups_do_not_probe_disk_for_unknown_entries(self):
        with cover_cache._MEMORY_CACHE_LOCK:
            cover_cache._ASSET_ALIAS_CACHE.clear()
            cover_cache._MISSING_MARKER_CACHE.clear()
        with mock.patch("cover_cache.os.path.isfile", side_effect=AssertionError("page projection must not probe disk")):
            self.assertEqual(
                cover_cache.thumbnail_asset_id_for_item(self.item, self.config, 160, allow_disk=False),
                "",
            )
            self.assertFalse(cover_cache.cover_is_known_missing(self.item, self.config, 160, allow_disk=False))

    def test_fast_page_cover_lookups_reuse_in_process_positive_entries(self):
        reader = mock.Mock(return_value=("image/jpeg", b"original"))
        with mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb"):
            cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader)
        _root, target, missing = cover_cache._cache_paths(self.item, self.config, 160)
        alias = target[:-4] + ".asset"
        with mock.patch("cover_cache.os.path.isfile", side_effect=AssertionError("cached fast lookup must not stat")):
            self.assertTrue(cover_cache.thumbnail_asset_id_for_item(self.item, self.config, 160, allow_disk=False))
        missing_item = dict(self.item, id="missing", modified_ns=456)
        cover_cache.cached_thumbnail_for_item(missing_item, self.config, 160, mock.Mock(return_value=(None, None)))
        with mock.patch("cover_cache.os.path.isfile", side_effect=AssertionError("cached missing lookup must not stat")):
            self.assertTrue(cover_cache.cover_is_known_missing(missing_item, self.config, 160, allow_disk=False))

    def _seed_alias_cache(self):
        """Warm one cover through the normal path; return (alias, asset_id, asset_path)."""
        reader = mock.Mock(return_value=("image/jpeg", b"original"))
        with mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb"):
            cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader)
        _root, target, _missing = cover_cache._cache_paths(self.item, self.config, 160)
        alias = target[:-4] + ".asset"
        with cover_cache._MEMORY_CACHE_LOCK:
            asset_id = cover_cache._ASSET_ALIAS_CACHE.get(alias)
        self.assertTrue(asset_id, "the normal path must warm the alias cache")
        _asset_root, asset_path = cover_cache._asset_path(self.config, 160, asset_id)
        return alias, asset_id, asset_path

    def test_a_broken_alias_does_not_keep_an_item_out_of_the_prewarm_queue(self):
        # A bare `isfile` on the alias used to be enough to call a row "already
        # answered", so a truncated body or a reclaimed shared asset kept the item out
        # of the queue forever and only a real cover request would re-render it.
        for label, body in (("garbage body", b"not-a-content-address\n"),
                            ("truncated body", b"1234"),
                            ("oversized body", b"a" * 4096),
                            ("non-ascii body", b"\xff" * 64)):
            with self.subTest(alias=label):
                alias, _asset_id, _asset_path = self._seed_alias_cache()
                with open(alias, "wb") as handle:
                    handle.write(body)
                cover_cache.clear_memory_cache()  # a restart is when this bites
                self.assertTrue(os.path.isfile(alias), "the marker is still on disk")
                self.assertFalse(cover_cache._prewarm_result_exists(self.item, self.config, 160),
                                 "an unreadable alias is not a result")
                self.assertEqual(cover_cache.thumbnail_asset_id_for_item(self.item, self.config, 160), "",
                                 "prewarm may not be stricter than the read path")
        alias, _asset_id, asset_path = self._seed_alias_cache()
        os.remove(asset_path)
        cover_cache.clear_memory_cache()
        self.assertTrue(os.path.isfile(alias), "the alias itself is fine here")
        self.assertFalse(cover_cache._prewarm_result_exists(self.item, self.config, 160),
                         "an alias pointing at a reclaimed asset is not a result either")
        # The other direction: this must not turn into "re-render every warm cover".
        alias, _asset_id, _asset_path = self._seed_alias_cache()
        cover_cache.clear_memory_cache()
        self.assertTrue(cover_cache._prewarm_result_exists(self.item, self.config, 160),
                        "a valid alias is a result")
        self.assertEqual(cover_cache.thumbnail_asset_id_for_item(self.item, self.config, 160), _asset_id)

    def test_one_prewarm_row_resolves_the_source_version_once_and_shares_it(self):
        # The decision and the render used to resolve the version independently, so one
        # row paid two stats and a file that changed mid-row could be judged against one
        # key and rendered into another.
        resolutions = []
        decision = {}

        def counting_version(item, allow_disk=True):
            resolutions.append((item["id"], allow_disk))
            # The enqueue-side call is the dedup key: it never touches the disk
            # (``allow_disk=False``), so only the worker side is worth counting.
            return "enqueue-key" if allow_disk is False else "9:9"

        def record(_item, _config, _size, version=None):
            decision["version"] = version
            return False  # force the row through to the render

        with mock.patch.object(cover_cache, "cover_source_version", side_effect=counting_version), \
             mock.patch.object(cover_cache, "_prewarm_result_exists", side_effect=record), \
             mock.patch.object(cover_cache, "cached_thumbnail_for_item") as render:
            cover_cache.prewarm_thumbnails([dict(self.item, id="row")], self.config, mock.Mock(), size=160)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not render.called:
                time.sleep(0.01)
        self.assertTrue(render.called, "the prewarm worker never rendered the row")
        self.assertEqual(resolutions, [("row", False), ("row", True)],
                         "one row may resolve its disk version once, not once per call")
        self.assertEqual(decision.get("version"), "9:9", "the decision must receive that version")
        self.assertEqual(render.call_args[1].get("version"), "9:9",
                         "the render must reuse the version the decision was made on")

    def test_alias_hit_does_not_hold_the_cover_lock_while_statting(self):
        alias, asset_id, asset_path = self._seed_alias_cache()
        real_isfile = os.path.isfile
        entered = threading.Event()
        release = threading.Event()

        def slow_isfile(path):
            if path == asset_path:
                entered.set()
                release.wait(5)
            return real_isfile(path)

        results = []

        def lookup():
            with mock.patch("cover_cache.os.path.isfile", side_effect=slow_isfile):
                results.append(cover_cache.thumbnail_asset_id_for_item(self.item, self.config, 160))

        worker = threading.Thread(target=lookup)
        worker.start()
        try:
            self.assertTrue(entered.wait(2), "the alias lookup never reached the asset stat")
            began = time.perf_counter()
            with cover_cache._MEMORY_CACHE_LOCK:
                pass
            waited = time.perf_counter() - began
        finally:
            release.set()
            worker.join(5)
        self.assertLess(waited, 0.2, "one slow stat must not stop every other cover request")
        self.assertEqual(results, [asset_id])
        with cover_cache._MEMORY_CACHE_LOCK:
            self.assertEqual(cover_cache._ASSET_ALIAS_CACHE.get(alias), asset_id)

    def test_alias_miss_drops_only_the_entry_it_validated(self):
        alias, _asset_id, asset_path = self._seed_alias_cache()
        replaced = "f" * 64
        real_isfile = os.path.isfile
        # Remove the alias *file* so the lookup cannot re-validate from disk and
        # re-publish: the point under test is what the cache may drop, not what
        # the disk path returns.
        os.remove(alias)
        swapped = []

        def swap_once_then_report_missing(path):
            if path == asset_path and not swapped:
                swapped.append(True)
                with cover_cache._MEMORY_CACHE_LOCK:
                    cover_cache._ASSET_ALIAS_CACHE[alias] = replaced
                return False
            return real_isfile(path)

        with mock.patch("cover_cache.os.path.isfile", side_effect=swap_once_then_report_missing):
            self.assertEqual(
                cover_cache.thumbnail_asset_id_for_item(self.item, self.config, 160), "")
        self.assertTrue(swapped, "the lookup must have consulted the cached asset")
        with cover_cache._MEMORY_CACHE_LOCK:
            self.assertEqual(
                cover_cache._ASSET_ALIAS_CACHE.get(alias), replaced,
                "an older lookup must not delete an id another thread just validated")

    def test_cover_lock_scope_is_pinned_by_shape_where_threads_cannot_probe_it(self):
        """Two containment rules on the source of one function.

        Whether the current thread holds an ``RLock`` is not introspectable in
        Python, so a test cannot ask "did you read the alias cache under the
        lock": the only honest check is that the read sits inside a locked block.
        The opposite rule (no ``stat`` inside a locked block) *is* observable
        from another thread, and `test_alias_hit_does_not_hold_the_cover_lock_while_statting`
        pins it behaviorally; it is repeated here because a shape break is what
        lets a future refactor reintroduce the stall in a place the timing test
        might stop covering.
        """
        source = inspect.getsource(cover_cache._alias_asset_key)
        lines = source.split("\n")
        lock_lines = [index for index, line in enumerate(lines)
                      if line.strip().startswith("with _MEMORY_CACHE_LOCK:")]
        self.assertTrue(lock_lines, "the alias cache must be read under the lock")
        read_index = next(index for index, line in enumerate(lines)
                          if line.strip().startswith("cached = _ASSET_ALIAS_CACHE.get(alias)"))
        self.assertIn(read_index - 1, lock_lines,
                      "the alias cache read must be the body of a locked block")
        for index in lock_lines:
            indent = len(lines[index]) - len(lines[index].lstrip())
            for follower in lines[index + 1:]:
                if not follower.strip():
                    continue
                if len(follower) - len(follower.lstrip()) <= indent:
                    break
                self.assertNotIn("os.path.isfile(", follower,
                                 "filesystem calls must stay outside the cover lock (line %d)" % index)
                self.assertNotIn("open(", follower,
                                 "file reads must stay outside the cover lock (line %d)" % index)
        self.assertIn("_ASSET_ALIAS_CACHE.get(alias) ==", source,
                      "the drop/reorder guards must keep comparing the value they validated")
        # R79 made the prewarm decision a second caller, so the rule now has a second
        # half: exactly one function may own the alias rules.  A copy re-inlined into
        # either caller is how the two paths start disagreeing again.
        caller = inspect.getsource(cover_cache.thumbnail_asset_id_for_item)
        self.assertIn("_alias_asset_key(", caller,
                      "the page serializer must delegate instead of copying the rules")
        self.assertNotIn("_ASSET_ALIAS_CACHE", caller,
                         "no alias-cache access may live outside the single helper")
        prewarm = inspect.getsource(cover_cache._prewarm_result_exists)
        self.assertIn("_alias_asset_key(", prewarm,
                      "the prewarm decision must go through the same alias rules")

    def test_alias_hit_survives_the_cache_being_cleared_during_the_stat(self):
        _alias, asset_id, asset_path = self._seed_alias_cache()
        real_isfile = os.path.isfile

        def clear_then_present(path):
            if path == asset_path:
                cover_cache.clear_memory_cache()
                return True
            return real_isfile(path)

        with mock.patch("cover_cache.os.path.isfile", side_effect=clear_then_present):
            self.assertEqual(
                cover_cache.thumbnail_asset_id_for_item(self.item, self.config, 160), asset_id)

    def test_an_asset_that_cannot_answer_stops_being_advertised_by_the_fast_page(self):
        # The page path never revalidates, and that is the point of it; so when the
        # sweep reclaimed a shared asset, a warm alias cache kept handing out
        # `cover-asset/<id>` and every browser image behind it 404ed until the alias
        # LRU moved on.  The 404 side is where that has to be mended, so the page path
        # still performs no stat.
        first_id = "%064x" % 11
        second_id = "%064x" % 12
        first = dict(self.item, id="row-1")
        second = dict(self.item, id="row-2")
        for row, key in ((first, first_id), (second, second_id)):
            _root, target, _missing = cover_cache._cache_paths(row, self.config, 160)
            alias = target[:-4] + ".asset"
            os.makedirs(os.path.dirname(alias), exist_ok=True)
            with open(alias, "wb") as handle:
                handle.write((key + "\n").encode("ascii"))
            _asset_root, asset_file = cover_cache._asset_path(self.config, 160, key)
            os.makedirs(_asset_root, exist_ok=True)
            with open(asset_file, "wb") as handle:
                handle.write(b"\xff\xd8jpeg")
            with cover_cache._MEMORY_CACHE_LOCK:
                cover_cache._ASSET_ALIAS_CACHE[alias] = key
        self.assertEqual(
            cover_cache.thumbnail_asset_id_for_item(first, self.config, 160, allow_disk=False), first_id,
            "the fast page is allowed to answer from the warm alias cache")
        _asset_root, gone = cover_cache._asset_path(self.config, 160, first_id)
        os.remove(gone)
        self.assertIsNone(cover_cache.thumbnail_asset_bytes(self.config, first_id, 160))
        self.assertEqual(
            cover_cache.thumbnail_asset_id_for_item(first, self.config, 160, allow_disk=False), "",
            "the page may not keep advertising an asset that cannot answer")
        self.assertEqual(
            cover_cache.thumbnail_asset_id_for_item(second, self.config, 160, allow_disk=False), second_id,
            "unrelated rows must keep their covers: the drop is by asset id, not a flush")
        self.assertIsNotNone(cover_cache.thumbnail_asset_bytes(self.config, second_id, 160))

    def test_memory_entries_are_keyed_by_identity_so_a_sweep_cannot_reverse_them(self):
        # R75 wrote this down as a design constraint with a caveat this test replaces:
        # the identity is the library id when the row has one and the media path when
        # it does not, so "there is no path in the key" is true for library rows only.
        # Both halves are pinned, together with the deliberate semantic that memory may
        # keep answering for bytes the disk no longer holds.
        cover_cache.clear_memory_cache()
        self.addCleanup(cover_cache.clear_memory_cache)
        media = os.path.join(os.path.dirname(self.config["cache_dir"]), "needle.flac")
        with open(media, "wb") as handle:
            handle.write(b"fLaC" + b"\x00" * 64)
        id_item = dict(self.item, id="track-9", path=media)
        reader = mock.Mock(return_value=("image/jpeg", b"original"))
        with mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb"):
            cover_cache.cached_thumbnail_for_item(id_item, self.config, 160, reader)

        def memory_keys():
            with cover_cache._MEMORY_CACHE_LOCK:
                return list(cover_cache._MEMORY_CACHE)

        def flattened(key):
            # Not `repr`: on Windows it escapes every backslash, and a path substring
            # test against it would pass without ever looking at the key.
            return "|".join(str(part) for part in key)

        keys = memory_keys()
        self.assertIn("track-9", [key[1] for key in keys], "an id row is keyed by its id")
        self.assertFalse(any(media in flattened(key) for key in keys),
                         "a library row's media path must not appear in any memory key")
        _root, target, _missing = cover_cache._cache_paths(id_item, self.config, 160)
        _asset_root, asset_file = cover_cache._asset_path(
            self.config, 160, cover_cache.thumbnail_asset_id_for_item(id_item, self.config, 160))
        os.remove(asset_file)
        os.remove(media)
        self.assertFalse(os.path.isfile(target), "nothing of this row is on disk any more")
        self.assertFalse(os.path.isfile(asset_file))
        self.assertTrue(any(cover_cache._memory_get(key) is not None for key in keys),
                        "memory is allowed to keep answering; that is why the sweep cannot reverse it")

        path_item = dict(id_item, id="")
        with mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8other"):
            cover_cache.cached_thumbnail_for_item(path_item, self.config, 160, reader)
        self.assertTrue(any(media in flattened(key) for key in memory_keys()),
                        "without a library id the key is the path: the note only holds for id rows")

    def test_only_the_image_bytes_ask_the_disk_to_hold_them(self):
        # R67 asked which cover artifacts need durability and left it unmeasured.  An
        # image tile is the only artifact whose half-written state a reader cannot tell
        # apart from a valid file (the shared-asset address names the source artwork,
        # not the rendered bytes), so only that write waits for the disk.  A truncated
        # alias or negative marker fails the read path's own validation and is
        # re-derived, so it must not stall the publish.
        policy = []
        real_atomic = cover_cache._atomic_bytes

        def record(path, body, config=None, durable=True):
            policy.append((os.path.splitext(path)[1], len(body), durable))
            return real_atomic(path, body, config, durable=durable)

        reader = mock.Mock(return_value=("image/jpeg", b"original"))
        with mock.patch.object(cover_cache, "_atomic_bytes", side_effect=record), \
             mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb"):
            cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader)
        durable_by_suffix = {suffix: durable for suffix, _size, durable in policy}
        self.assertEqual(sorted(durable_by_suffix), [".asset", ".jpg"],
                         "a successful cover publishes the image and its alias, nothing else")
        self.assertTrue(durable_by_suffix[".jpg"], "the image bytes keep their fsync")
        self.assertFalse(durable_by_suffix[".asset"], "a 64-hex alias is re-derivable, so it does not wait")

        policy.clear()
        with mock.patch.object(cover_cache, "_atomic_bytes", side_effect=record), \
             mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b""):
            cover_cache.cached_thumbnail_for_item(dict(self.item, id="no-art"), self.config, 160,
                                                  mock.Mock(return_value=(None, None)))
        self.assertIn((".none", 0, False), policy, "the negative marker is an optimization, not a promise")

    def test_the_durability_flag_is_what_controls_the_fsync(self):
        with tempfile.TemporaryDirectory() as root:
            for durable, expected in ((True, 1), (False, 0)):
                calls = []
                path = os.path.join(root, "artifact-%s" % durable)
                with mock.patch("cover_cache.os.fsync", side_effect=calls.append):
                    cover_cache._atomic_bytes(path, b"body", durable=durable)
                self.assertEqual(len(calls), expected, "durable=%s" % durable)
                with open(path, "rb") as handle:
                    self.assertEqual(handle.read(), b"body", "the write itself must not change")

    def test_no_locked_block_in_the_module_touches_the_disk(self):
        # R72 moved the filesystem calls out of the alias lookup, and R80 added one read
        # plus one stat to that chain - outside the lock.  R72's note said the worry was
        # that a single-function assertion cannot cover a block nobody has written yet,
        # so this scans every locked block in the module.  These locks are process-wide:
        # one slow SMB call under them stops every cover request and every prewarm
        # worker for as long as the file server takes to answer.
        locked_calls = ("os.path.isfile(", "os.path.exists(", "os.stat(", "_read_bounded_file(",
                        "open(", "os.unlink(", "os.replace(", "os.fsync(", "_atomic_bytes(",
                        "os.listdir(", "os.makedirs(", "os.remove(", "cover_source_version(")
        source = inspect.getsource(cover_cache).split("\n")
        blocks = []
        for index, line in enumerate(source):
            match = re.match(r"^(\s+)with (_MEMORY_CACHE_LOCK|_PREWARM_LOCK|_LOCKS_GUARD):", line)
            if not match:
                continue
            indent = len(match.group(1))
            body = []
            for follower in source[index + 1:]:
                if not follower.strip():
                    continue
                if len(follower) - len(follower.lstrip()) <= indent:
                    break
                body.append(follower.strip())
            blocks.append((index + 1, match.group(2), body))
        self.assertGreaterEqual(len(blocks), 30,
                                "the scan found almost no locked blocks, so it proves nothing")
        self.assertEqual({lock for _at, lock, _body in blocks},
                         {"_MEMORY_CACHE_LOCK", "_PREWARM_LOCK", "_LOCKS_GUARD"},
                         "every process-wide lock in this module must be covered")
        offenders = [
            (at, lock, call, text[:70])
            for at, lock, body in blocks
            for text in body
            for call in locked_calls
            # `cover_source_version(allow_disk=False)` is the documented no-stat form:
            # it reads the indexed identity, which is why the enqueue path may hold the
            # prewarm lock while calling it.
            if call in text and not (call == "cover_source_version(" and "allow_disk=False" in text)
        ]
        self.assertEqual(offenders, [], "filesystem work inside a process-wide lock: %s" % offenders[:4])

    def test_deleted_asset_is_not_advertised_from_a_warm_alias_cache(self):
        alias, _asset_id, asset_path = self._seed_alias_cache()
        os.remove(asset_path)
        self.assertEqual(
            cover_cache.thumbnail_asset_id_for_item(self.item, self.config, 160), "")
        with cover_cache._MEMORY_CACHE_LOCK:
            self.assertNotIn(alias, cover_cache._ASSET_ALIAS_CACHE)

    def test_one_cover_request_resolves_the_source_version_once(self):
        probes = []
        real = cover_cache.cover_source_version

        def spy(item, allow_disk=True):
            probes.append(allow_disk)
            return real(item, allow_disk=allow_disk)

        reader = mock.Mock(return_value=("image/jpeg", b"original"))
        for label, prepared in (("render path", False), ("cached path", True)):
            with self.subTest(path=label):
                probes.clear()
                cover_cache.clear_memory_cache()
                with mock.patch.object(cover_cache, "cover_source_version", side_effect=spy), \
                        mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb"):
                    if prepared:
                        cover_cache.cached_thumbnail_for_item(self.item, self.config, 512, reader)
                        cover_cache.clear_memory_cache()
                        probes.clear()
                    cover_cache.cached_thumbnail_for_item(self.item, self.config, 512, reader)
                self.assertEqual(len(probes), 1, "%s recomputed the source version" % label)

    def test_mid_request_identity_change_cannot_split_the_cache_keys(self):
        """The disk path, the memory key and the lock must come from one number.

        Simulated by making the version change after the first resolution, which
        is what a tag write or a scanner update does to a real file mid-request.
        Before the fix the rendered bytes landed under version A while the memory
        entry was keyed on version B, so the next request that saw B could never
        find the stored thumbnail and re-rendered it, leaving the A file as
        permanent unreachable garbage.
        """
        results = iter(["1:1", "2:2"])
        reader = mock.Mock(return_value=("image/jpeg", b"original"))
        with mock.patch.object(cover_cache, "cover_source_version", side_effect=lambda *a, **k: next(results)), \
                mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb"):
            self.assertEqual(
                cover_cache.cached_thumbnail_for_item(self.item, self.config, 160, reader),
                ("image/jpeg", b"\xff\xd8thumb"))
        expected_key = cover_cache._cache_key(self.item, 160, "1:1")
        _root, target, _missing = cover_cache._cache_paths(self.item, self.config, 160, "1:1")
        # The current store publishes `<key>.asset` (an alias onto the shared
        # asset); `<key>.jpg` is only ever left by an older release.
        self.assertTrue(os.path.isfile(target[:-4] + ".asset"),
                        "the thumbnail must live under the request's version")
        with cover_cache._MEMORY_CACHE_LOCK:
            memory_keys = list(cover_cache._MEMORY_CACHE)
        self.assertEqual([entry[2] for entry in memory_keys], ["1:1"],
                         "the memory entry must be keyed on the version that wrote the file")
        self.assertTrue(os.path.isfile(os.path.join(
            os.path.dirname(target), expected_key + ".asset")))

    def test_interactive_prewarm_queue_key_does_not_stat_unindexed_items(self):
        item = {"id": "slow-track", "path": "/slow/track.flac"}
        with mock.patch("cover_cache.os.stat", side_effect=AssertionError("prewarm enqueue must not stat")), \
             mock.patch.object(cover_cache, "cached_thumbnail_for_item", return_value=(None, None)):
            cover_cache.prewarm_thumbnails([item], self.config, mock.Mock())
            time.sleep(0.03)
        cover_cache.shutdown_library_thumbnail_prewarm(wait=True)

    def test_interactive_prewarm_yields_a_short_response_quiet_window(self):
        with cover_cache._PREWARM_LOCK:
            cover_cache._INTERACTIVE_PREWARM.clear()
        started = time.monotonic()
        with mock.patch.object(cover_cache, "cached_thumbnail_for_item", return_value=(None, None)) as warm:
            cover_cache.prewarm_thumbnails([self.item], self.config, mock.Mock())
            cache_key = os.path.abspath(self.config["cache_dir"])
            with cover_cache._PREWARM_LOCK:
                state = cover_cache._INTERACTIVE_PREWARM[cache_key]
                self.assertGreaterEqual(
                    state["not_before"],
                    started + cover_cache.INTERACTIVE_PREWARM_INITIAL_DELAY_SECONDS - 0.02,
                )
                self.assertEqual(len(state["pending"]), 1)
                self.assertEqual(len(state["inflight"]), 0)
            # The worker may be scheduled immediately, but must not do disk/
            # FFmpeg work alongside page-one response serialization.
            time.sleep(0.03)
            warm.assert_not_called()
        cover_cache.shutdown_library_thumbnail_prewarm(wait=True)

    def test_interactive_prewarm_recovers_corrupt_not_before_state(self):
        with cover_cache._PREWARM_LOCK:
            cover_cache._INTERACTIVE_PREWARM.clear()
            cache_key = os.path.abspath(self.config["cache_dir"])
            cover_cache._INTERACTIVE_PREWARM[cache_key] = {
                "pending": OrderedDict(), "inflight": set(), "running": False,
                "thread": None, "cancel": threading.Event(), "accepted": 0,
                "completed": 0, "failed": 0, "dropped": 0, "not_before": float("nan"),
            }
        with mock.patch.object(cover_cache, "cached_thumbnail_for_item", return_value=(None, None)):
            cover_cache.prewarm_thumbnails([self.item], self.config, mock.Mock())
            time.sleep(0.03)
        cover_cache.shutdown_library_thumbnail_prewarm(wait=True)

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

    def test_thumbnail_does_not_pipe_unbounded_ffmpeg_output_into_memory(self):
        with mock.patch.object(cover_cache, "find_ffmpeg", return_value="ffmpeg"), \
             mock.patch.object(cover_cache, "ffmpeg_slot", return_value=nullcontext()), \
             mock.patch.object(cover_cache.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b"ignored")) as run:
            result = cover_cache._thumbnail_bytes(b"cover", self.config, 160)
        self.assertIsNone(result)
        self.assertNotEqual(run.call_args.kwargs.get("stdout"), cover_cache.subprocess.PIPE)

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

    def test_library_prewarm_ignores_malformed_paths_without_stranding_worker(self):
        class Exploding:
            def __str__(self):
                raise AssertionError("prewarm must not stringify malformed paths")

        malformed = {"id": "bad", "path": Exploding()}
        with mock.patch.object(cover_cache, "cached_thumbnail_for_item") as warm:
            cover_cache.prewarm_library_thumbnails([malformed, dict(self.item, path=__file__)], self.config, mock.Mock())
            cache_key = os.path.abspath(self.config["cache_dir"])
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                with cover_cache._PREWARM_LOCK:
                    state = cover_cache._LIBRARY_PREWARM.get(cache_key)
                    if state is None:
                        break
                time.sleep(0.01)
            warm.assert_called_once()
        cover_cache.shutdown_library_thumbnail_prewarm(wait=True)

    def test_interactive_prewarm_is_single_worker_bounded_and_observable(self):
        started = threading.Event()
        release = threading.Event()

        def warm(_item, _config, _size, _reader, **_kwargs):
            started.set()
            release.wait(2)
            return None, None

        with mock.patch.object(cover_cache, "cached_thumbnail_for_item", side_effect=warm):
            cover_cache.prewarm_thumbnails([dict(self.item, id="first")], self.config, mock.Mock())
            self.assertTrue(started.wait(2))
            for index in range(110):
                cover_cache.prewarm_thumbnails([dict(self.item, id="pending-%d" % index)], self.config, mock.Mock())
            status = cover_cache.thumbnail_prewarm_status()["interactive"]
            self.assertEqual(status["workers"], 1)
            self.assertEqual(status["inflight"], 1)
            self.assertLessEqual(status["queued"], status["limit"])
            self.assertGreater(status["dropped"], 0)
        release.set()
        cover_cache.shutdown_library_thumbnail_prewarm(wait=True)
        self.assertEqual(cover_cache.thumbnail_prewarm_status()["interactive"]["workers"], 0)

    def test_library_prewarm_pending_items_are_bounded(self):
        items = [dict(self.item, id="pending-%d" % index, path="/music/pending-%d.flac" % index) for index in range(cover_cache.LIBRARY_PREWARM_MAX_PENDING + 25)]
        with mock.patch.object(cover_cache, "cached_thumbnail_for_item", return_value=(None, None)):
            cover_cache.prewarm_library_thumbnails(items, self.config, mock.Mock())
            status = cover_cache.thumbnail_prewarm_status()["library"]
            self.assertLessEqual(status["queued"], cover_cache.LIBRARY_PREWARM_MAX_PENDING)
            self.assertEqual(status["limit"], cover_cache.LIBRARY_PREWARM_MAX_PENDING)
            self.assertEqual(status["dropped"], 25)
            self.assertEqual(status["accepted"], cover_cache.LIBRARY_PREWARM_MAX_PENDING)
            self.assertGreaterEqual(status["completed"], 0)

    def test_library_prewarm_restarts_processing_after_queue_replacement(self):
        first_started = threading.Event()
        release_first = threading.Event()
        warmed = []

        def warm(item, *_args, **_kwargs):
            warmed.append(item["id"])
            if item["id"] == "first":
                first_started.set()
                release_first.wait(2)
            return None, None

        first = dict(self.item, id="first", path=__file__)
        second = dict(self.item, id="second", path=__file__)
        with mock.patch.object(cover_cache, "cached_thumbnail_for_item", side_effect=warm):
            cover_cache.prewarm_library_thumbnails([first], self.config, mock.Mock())
            self.assertTrue(first_started.wait(2))
            cover_cache.prewarm_library_thumbnails([second], self.config, mock.Mock())
            release_first.set()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and "second" not in warmed:
                time.sleep(0.01)
        cover_cache.shutdown_library_thumbnail_prewarm(wait=True)
        self.assertIn("second", warmed)

    def test_prewarm_status_ignores_corrupted_pressure_counters(self):
        with cover_cache._PREWARM_LOCK:
            cover_cache._INTERACTIVE_PREWARM.clear()
            cover_cache._INTERACTIVE_PREWARM["bad"] = {
                "accepted": object(), "completed": -4, "failed": True, "dropped": 7,
                "running": False, "pending": [], "inflight": [], "cancel": threading.Event(),
            }
        try:
            status = cover_cache.thumbnail_prewarm_status()["interactive"]
            self.assertEqual(status["accepted"], 0)
            self.assertEqual(status["completed"], 0)
            self.assertEqual(status["failed"], 0)
            self.assertEqual(status["dropped"], 7)
        finally:
            with cover_cache._PREWARM_LOCK:
                cover_cache._INTERACTIVE_PREWARM.clear()

    def test_prewarm_status_ignores_broken_state_mappings_and_sequences(self):
        class BrokenDict(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken state")

        with cover_cache._PREWARM_LOCK:
            cover_cache._INTERACTIVE_PREWARM.clear()
            cover_cache._INTERACTIVE_PREWARM["broken"] = BrokenDict()
        try:
            status = cover_cache.thumbnail_prewarm_status()["interactive"]
            self.assertEqual(status["workers"], 0)
            self.assertEqual(status["queued"], 0)
            self.assertEqual(status["accepted"], 0)
        finally:
            with cover_cache._PREWARM_LOCK:
                cover_cache._INTERACTIVE_PREWARM.clear()

    def test_prewarm_status_ignores_sequence_len_runtime_errors(self):
        class BrokenSequence:
            def __len__(self):
                raise RuntimeError("broken length")

        with cover_cache._PREWARM_LOCK:
            cover_cache._INTERACTIVE_PREWARM.clear()
            cover_cache._INTERACTIVE_PREWARM["broken-len"] = {"pending": BrokenSequence(), "inflight": BrokenSequence()}
        try:
            status = cover_cache.thumbnail_prewarm_status()["interactive"]
            self.assertEqual(status["queued"], 0)
            self.assertEqual(status["inflight"], 0)
        finally:
            with cover_cache._PREWARM_LOCK:
                cover_cache._INTERACTIVE_PREWARM.clear()

    def test_prewarm_status_exposes_bounded_memory_cache_pressure(self):
        status = cover_cache.thumbnail_prewarm_status()
        memory = status["memory_cache"]
        self.assertGreaterEqual(memory["entries"], 0)
        self.assertGreaterEqual(memory["bytes"], 0)
        self.assertLessEqual(memory["bytes"], memory["limit_bytes"])
        self.assertLessEqual(memory["entries"], memory["entry_limit"])
        self.assertGreaterEqual(memory["alias_entries"], 0)
        self.assertLessEqual(memory["alias_entries"], memory["alias_limit"])

    def test_memory_cover_cache_has_an_independent_entry_limit(self):
        old_limit = cover_cache._MEMORY_CACHE_ENTRY_LIMIT
        try:
            cover_cache.clear_memory_cache()
            cover_cache._MEMORY_CACHE_ENTRY_LIMIT = 2
            cover_cache._memory_put(("one",), ("image/jpeg", b"x"))
            cover_cache._memory_put(("two",), ("image/jpeg", b"x"))
            cover_cache._memory_put(("three",), ("image/jpeg", b"x"))
            with cover_cache._MEMORY_CACHE_LOCK:
                self.assertEqual(list(cover_cache._MEMORY_CACHE), [("two",), ("three",)])
        finally:
            cover_cache._MEMORY_CACHE_ENTRY_LIMIT = old_limit
            cover_cache.clear_memory_cache()

    def test_library_prewarm_normalizes_relative_cache_roots(self):
        entered = threading.Event()
        release = threading.Event()

        def blocked(*_args, **_kwargs):
            entered.set()
            release.wait(1)
            return None, None

        media_path = os.path.join(self.temp.name, "prewarm.flac")
        with open(media_path, "wb") as handle:
            handle.write(b"fixture")
        item = dict(self.item, path=media_path)
        relative = "artifacts"
        expected_root = os.path.abspath(relative)
        with mock.patch.object(cover_cache, "cached_thumbnail_for_item", side_effect=blocked):
            cover_cache.prewarm_library_thumbnails([item], {"cache_dir": relative}, mock.Mock())
            self.assertTrue(entered.wait(1))
            cover_cache.prewarm_library_thumbnails([item], {"cache_dir": expected_root}, mock.Mock())
            with cover_cache._PREWARM_LOCK:
                keys = list(cover_cache._LIBRARY_PREWARM)
            self.assertEqual(keys, [expected_root])
        release.set()

    def test_library_prewarm_rejects_new_roots_when_all_slots_are_active(self):
        original_limit = cover_cache.LIBRARY_PREWARM_MAX_ROOTS
        try:
            cover_cache.LIBRARY_PREWARM_MAX_ROOTS = 1
            with cover_cache._PREWARM_LOCK:
                cover_cache._LIBRARY_PREWARM.clear()
            cover_cache.prewarm_library_thumbnails([self.item], self.config, mock.Mock())
            with cover_cache._PREWARM_LOCK:
                state = cover_cache._LIBRARY_PREWARM[os.path.abspath(self.config["cache_dir"])]
                state["running"] = True
            before = cover_cache.thumbnail_prewarm_status()["library"]["root_rejected"]
            cover_cache.prewarm_library_thumbnails([self.item], {"cache_dir": "artifacts"}, mock.Mock())
            after = cover_cache.thumbnail_prewarm_status()["library"]["root_rejected"]
            self.assertEqual(after, before + 1)
        finally:
            cover_cache.LIBRARY_PREWARM_MAX_ROOTS = original_limit

    def test_interactive_prewarm_keeps_serving_a_registered_root_when_the_registry_is_full(self):
        # The cap guards against *new* roots only.  A root that already owns a
        # slot is the one the interface is looking at, so a full registry must
        # never refuse its next page: that would strand the visible rows on
        # placeholder artwork with no later request to recover them.
        original_limit = cover_cache.INTERACTIVE_PREWARM_MAX_ROOTS
        try:
            cover_cache.INTERACTIVE_PREWARM_MAX_ROOTS = 1
            key = os.path.abspath(self.config["cache_dir"])
            with cover_cache._PREWARM_LOCK:
                cover_cache._INTERACTIVE_PREWARM.clear()
            with mock.patch.object(cover_cache, "cached_thumbnail_for_item", return_value=(None, None)):
                cover_cache.prewarm_thumbnails([self.item], self.config, mock.Mock())
                with cover_cache._PREWARM_LOCK:
                    cover_cache._INTERACTIVE_PREWARM[key]["running"] = True
                    cover_cache._INTERACTIVE_PREWARM[key]["cancel"].set()
                before = cover_cache.thumbnail_prewarm_status()["interactive"]["root_rejected"]
                cover_cache.prewarm_thumbnails(
                    [dict(self.item, id="later", path="/music/later.flac")], self.config, mock.Mock()
                )
                after = cover_cache.thumbnail_prewarm_status()["interactive"]["root_rejected"]
            self.assertEqual(after, before)
            with cover_cache._PREWARM_LOCK:
                state = cover_cache._INTERACTIVE_PREWARM[key]
            # A cancelled queue is replaced rather than reused, and the fresh
            # state has to be the one the registry publishes.
            self.assertEqual(state["accepted"], 1)
            self.assertFalse(state["cancel"].is_set())
            self.assertEqual([item["id"] for item in state["pending"].values()], ["later"])
        finally:
            cover_cache.INTERACTIVE_PREWARM_MAX_ROOTS = original_limit

    def test_library_prewarm_waits_between_pages_without_holding_the_lock(self):
        observed = []

        class Watchdog:
            def __init__(self):
                self._event = threading.Event()

            def is_set(self):
                return self._event.is_set()

            def clear(self):
                self._event.clear()

            def set(self):
                self._event.set()

            def wait(self, _timeout):
                # Every page request and every interactive enqueue takes this
                # same lock, so sleeping inside it parks the first screen for
                # the whole page gap.
                if cover_cache._PREWARM_LOCK.acquire(blocking=False):
                    cover_cache._PREWARM_LOCK.release()
                    observed.append("free")
                else:
                    observed.append("held")
                self._event.wait(0.02)
                return self._event.is_set()

        key = os.path.abspath(self.config["cache_dir"])
        state = {
            "generation": 0, "running": False, "items": [], "accepted": 0,
            "completed": 0, "failed": 0, "dropped": 0, "cancel": Watchdog(), "thread": None,
        }
        with cover_cache._PREWARM_LOCK:
            cover_cache._LIBRARY_PREWARM.clear()
            cover_cache._LIBRARY_PREWARM[key] = state
        items = [
            dict(self.item, id="page-%d" % index, path="/music/page-%d.flac" % index)
            for index in range(cover_cache.LIBRARY_PREWARM_PAGE_SIZE + 2)
        ]
        with mock.patch.object(cover_cache, "cached_thumbnail_for_item", return_value=(None, None)):
            cover_cache.prewarm_library_thumbnails(items, self.config, mock.Mock())
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and not observed:
                time.sleep(0.01)
            cover_cache.shutdown_library_thumbnail_prewarm(wait=True)
        self.assertTrue(observed)
        self.assertNotIn("held", observed)

    def test_library_prewarm_keeps_serving_a_registered_root_when_the_registry_is_full(self):
        original_limit = cover_cache.LIBRARY_PREWARM_MAX_ROOTS
        try:
            cover_cache.LIBRARY_PREWARM_MAX_ROOTS = 1
            key = os.path.abspath(self.config["cache_dir"])
            with cover_cache._PREWARM_LOCK:
                cover_cache._LIBRARY_PREWARM.clear()
            with mock.patch.object(cover_cache, "cached_thumbnail_for_item", return_value=(None, None)):
                cover_cache.prewarm_library_thumbnails([self.item], self.config, mock.Mock())
                with cover_cache._PREWARM_LOCK:
                    cover_cache._LIBRARY_PREWARM[key]["running"] = True
                    cover_cache._LIBRARY_PREWARM[key]["cancel"].set()
                before = cover_cache.thumbnail_prewarm_status()["library"]["root_rejected"]
                cover_cache.prewarm_library_thumbnails(
                    [dict(self.item, id="later", path="/music/later.flac")], self.config, mock.Mock()
                )
                after = cover_cache.thumbnail_prewarm_status()["library"]["root_rejected"]
            self.assertEqual(after, before)
            with cover_cache._PREWARM_LOCK:
                self.assertEqual(cover_cache._LIBRARY_PREWARM[key]["accepted"], 2)
        finally:
            cover_cache.LIBRARY_PREWARM_MAX_ROOTS = original_limit

    def test_interactive_prewarm_reclaims_idle_roots_and_rejects_when_all_slots_are_active(self):
        original_limit = cover_cache.INTERACTIVE_PREWARM_MAX_ROOTS
        try:
            cover_cache.INTERACTIVE_PREWARM_MAX_ROOTS = 1
            with cover_cache._PREWARM_LOCK:
                cover_cache._INTERACTIVE_PREWARM.clear()
            # A completed root may be evicted so a settings change can still
            # warm the newly selected cache directory.
            cover_cache.prewarm_thumbnails([self.item], self.config, mock.Mock())
            with cover_cache._PREWARM_LOCK:
                first = cover_cache._INTERACTIVE_PREWARM[os.path.abspath(self.config["cache_dir"])]
                first["running"] = False
            alternate = {"cache_dir": os.path.join(self.temp.name, "alternate")}
            cover_cache.prewarm_thumbnails([self.item], alternate, mock.Mock())
            with cover_cache._PREWARM_LOCK:
                self.assertEqual(list(cover_cache._INTERACTIVE_PREWARM), [os.path.abspath(alternate["cache_dir"])])
                cover_cache._INTERACTIVE_PREWARM[os.path.abspath(alternate["cache_dir"])]["running"] = True
            before = cover_cache.thumbnail_prewarm_status()["interactive"]["root_rejected"]
            cover_cache.prewarm_thumbnails([self.item], {"cache_dir": os.path.join(self.temp.name, "third")}, mock.Mock())
            after = cover_cache.thumbnail_prewarm_status()["interactive"]["root_rejected"]
            self.assertEqual(after, before + 1)
        finally:
            cover_cache.INTERACTIVE_PREWARM_MAX_ROOTS = original_limit

    def test_interactive_prewarm_start_failure_does_not_strand_running_state(self):
        with cover_cache._PREWARM_LOCK:
            cover_cache._INTERACTIVE_PREWARM.clear()
        with mock.patch.object(threading.Thread, "start", side_effect=RuntimeError("no threads")):
            cover_cache.prewarm_thumbnails([self.item], self.config, mock.Mock())
        with cover_cache._PREWARM_LOCK:
            state = cover_cache._INTERACTIVE_PREWARM[os.path.abspath(self.config["cache_dir"])]
            self.assertFalse(state["running"])
            self.assertIsNone(state["thread"])

    def test_cancelled_interactive_worker_clears_running_state(self):
        started = threading.Event()
        release = threading.Event()

        def warm(*_args, **_kwargs):
            started.set()
            release.wait(2)
            return None, None

        with mock.patch.object(cover_cache, "cached_thumbnail_for_item", side_effect=warm):
            cover_cache.prewarm_thumbnails([self.item], self.config, mock.Mock())
            cache_key = os.path.abspath(self.config["cache_dir"])
            with cover_cache._PREWARM_LOCK:
                state = cover_cache._INTERACTIVE_PREWARM[cache_key]
            state["not_before"] = 0
            self.assertTrue(started.wait(2))
            cover_cache.shutdown_library_thumbnail_prewarm()
            release.set()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and state["running"]:
                time.sleep(0.01)
            self.assertFalse(state["running"])

    def test_cancelled_library_worker_clears_running_state(self):
        started = threading.Event()
        release = threading.Event()

        def warm(*_args, **_kwargs):
            started.set()
            release.wait(2)
            return None, None

        item = dict(self.item, path=__file__)
        with mock.patch.object(cover_cache, "cached_thumbnail_for_item", side_effect=warm):
            cover_cache.prewarm_library_thumbnails([item], self.config, mock.Mock())
            cache_key = os.path.abspath(self.config["cache_dir"])
            with cover_cache._PREWARM_LOCK:
                state = cover_cache._LIBRARY_PREWARM[cache_key]
            self.assertTrue(started.wait(2))
            cover_cache.shutdown_library_thumbnail_prewarm()
            release.set()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and state["running"]:
                time.sleep(0.01)
            self.assertFalse(state["running"])

    def test_library_prewarm_start_failure_does_not_strand_running_state(self):
        with cover_cache._PREWARM_LOCK:
            cover_cache._LIBRARY_PREWARM.clear()
        with mock.patch.object(threading.Thread, "start", side_effect=RuntimeError("no threads")):
            cover_cache.prewarm_library_thumbnails([self.item], self.config, mock.Mock())
        with cover_cache._PREWARM_LOCK:
            state = cover_cache._LIBRARY_PREWARM[os.path.abspath(self.config["cache_dir"])]
            self.assertFalse(state["running"])
            self.assertIsNone(state["thread"])

    def test_shutdown_releases_library_prewarm_items_before_workers_exit(self):
        state = {
            "items": [dict(self.item), dict(self.item, id="second")],
            "cancel": threading.Event(),
            "thread": None,
        }
        with cover_cache._PREWARM_LOCK:
            cover_cache._LIBRARY_PREWARM.clear()
            cover_cache._LIBRARY_PREWARM["cache"] = state
        cover_cache.shutdown_library_thumbnail_prewarm()
        self.assertTrue(state["cancel"].is_set())
        self.assertEqual(state["items"], [])

    def test_asset_thumbnail_renders_once_and_shares_the_result(self):
        body = b"provider-original-artwork"
        asset_id = hashlib.sha256(body).hexdigest()
        source = os.path.join(self.temp.name, "artwork.bin")
        with open(source, "wb") as handle:
            handle.write(body)
        with mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb") as render:
            first = cover_cache.generate_asset_thumbnail(self.config, asset_id, 160, source)
            second = cover_cache.generate_asset_thumbnail(self.config, asset_id, 160, source)
        self.assertEqual(first, ("image/jpeg", b"\xff\xd8thumb"))
        self.assertEqual(second, first)
        render.assert_called_once()
        _root, asset_target = cover_cache._asset_path(self.config, 160, asset_id)
        self.assertTrue(os.path.isfile(asset_target))

    def test_asset_thumbnail_never_publishes_bytes_that_miss_their_address(self):
        source = os.path.join(self.temp.name, "artwork.bin")
        with open(source, "wb") as handle:
            handle.write(b"some-other-artwork")
        with mock.patch.object(cover_cache, "_thumbnail_bytes", side_effect=AssertionError("must not render")):
            value = cover_cache.generate_asset_thumbnail(self.config, "a" * 64, 160, source)
        self.assertIsNone(value)
        _root, asset_target = cover_cache._asset_path(self.config, 160, "a" * 64)
        self.assertFalse(os.path.exists(asset_target))

    def test_asset_thumbnail_keeps_every_size_in_its_own_entry(self):
        # 160 and 512 share one content address, so the size has to be part of
        # both the in-process key and the on-disk name.  A render that answers
        # for the other size is invisible until a player cover turns up as a
        # thumbnail.
        body = b"size-separating-artwork"
        asset_id = hashlib.sha256(body).hexdigest()
        source = os.path.join(self.temp.name, "artwork.bin")
        with open(source, "wb") as handle:
            handle.write(body)

        def render(_body, _config, size, _timeout=5.0):
            return b"\xff\xd8" + str(size).encode("ascii")

        with mock.patch.object(cover_cache, "_thumbnail_bytes", side_effect=render):
            small = cover_cache.generate_asset_thumbnail(self.config, asset_id, 160, source)
            large = cover_cache.generate_asset_thumbnail(self.config, asset_id, 512, source)
            again = cover_cache.generate_asset_thumbnail(self.config, asset_id, 160, source)
        self.assertEqual(small, ("image/jpeg", b"\xff\xd8160"))
        self.assertEqual(large, ("image/jpeg", b"\xff\xd8512"))
        self.assertEqual(again, small)
        _root, small_target = cover_cache._asset_path(self.config, 160, asset_id)
        _root, large_target = cover_cache._asset_path(self.config, 512, asset_id)
        for path, expected in ((small_target, b"\xff\xd8160"), (large_target, b"\xff\xd8512")):
            with open(path, "rb") as handle:
                self.assertEqual(handle.read(), expected)

    def test_asset_thumbnail_reuses_a_render_another_request_published(self):
        body = b"shared-by-another-worker"
        asset_id = hashlib.sha256(body).hexdigest()
        source = os.path.join(self.temp.name, "artwork.bin")
        with open(source, "wb") as handle:
            handle.write(body)
        _root, asset_target = cover_cache._asset_path(self.config, 160, asset_id)
        cover_cache._atomic_bytes(asset_target, b"\xff\xd8already")
        with mock.patch.object(cover_cache, "_thumbnail_bytes", side_effect=AssertionError("must not render")):
            value = cover_cache.generate_asset_thumbnail(self.config, asset_id, 160, source)
        self.assertEqual(value, ("image/jpeg", b"\xff\xd8already"))

    def test_asset_thumbnail_serves_a_failing_cache_write_from_memory(self):
        body = b"write-should-not-block-the-response"
        asset_id = hashlib.sha256(body).hexdigest()
        source = os.path.join(self.temp.name, "artwork.bin")
        with open(source, "wb") as handle:
            handle.write(body)
        cover_cache.clear_memory_cache()
        with mock.patch.object(cover_cache, "_thumbnail_bytes", return_value=b"\xff\xd8thumb"), \
             mock.patch.object(cover_cache, "_atomic_bytes", side_effect=OSError("disk full")):
            value = cover_cache.generate_asset_thumbnail(self.config, asset_id, 160, source)
        self.assertEqual(value, ("image/jpeg", b"\xff\xd8thumb"))

    def test_asset_thumbnail_rejects_untrusted_addresses_sizes_and_paths(self):
        class UnsafeText:
            def __str__(self):
                raise AssertionError("asset input must not stringify arbitrary objects")

        source = os.path.join(self.temp.name, "artwork.bin")
        with open(source, "wb") as handle:
            handle.write(b"x" * 32)
        with mock.patch.object(cover_cache, "_thumbnail_bytes", side_effect=AssertionError("must not render")):
            self.assertIsNone(cover_cache.generate_asset_thumbnail(self.config, UnsafeText(), 160, source))
            self.assertIsNone(cover_cache.generate_asset_thumbnail(self.config, "a" * 63, 160, source))
            self.assertIsNone(cover_cache.generate_asset_thumbnail(self.config, "../" + "a" * 63, 160, source))
            self.assertIsNone(cover_cache.generate_asset_thumbnail(self.config, "a" * 64, 0, source))
            self.assertIsNone(cover_cache.generate_asset_thumbnail(self.config, "a" * 64, 160, source + "-missing"))
            self.assertIsNone(cover_cache.generate_asset_thumbnail(self.config, "a" * 64, 160, UnsafeText()))



class CoverCacheSweepTests(unittest.TestCase):
    """`covers/` is a cache, so it has to bound itself: stale, unreachable, then over budget."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.config = {"cache_dir": self._directory.name}
        self.now = time.time()
        cover_cache.clear_memory_cache()
        self.addCleanup(cover_cache.clear_memory_cache)
        # Housekeeping is a module-wide clock; keep every test's first sweep armed.
        original = cover_cache._last_cover_sweep
        cover_cache._last_cover_sweep = self.now - cover_cache.COVER_CACHE_SWEEP_INTERVAL_SECONDS - 1
        self.addCleanup(setattr, cover_cache, "_last_cover_sweep", original)

    def _thumb_dir(self, size=160):
        path = os.path.join(cover_cache._cache_directory(self.config), "covers", "thumb-%d" % size)
        os.makedirs(path, exist_ok=True)
        return path

    def _publish(self, key, asset_key, size=160, asset_mtime=None, alias_mtime=None,
                 asset_bytes=b"\xff\xd8shared-jpeg-bytes"):
        asset_root, asset_target = cover_cache._asset_path(self.config, size, asset_key)
        os.makedirs(asset_root, exist_ok=True)
        with open(asset_target, "wb") as handle:
            handle.write(asset_bytes)
        alias = os.path.join(self._thumb_dir(size), key + ".asset")
        with open(alias, "wb") as handle:
            handle.write(asset_key.encode("ascii"))
        for path, stamp in ((asset_target, asset_mtime), (alias, alias_mtime)):
            if stamp is not None:
                os.utime(path, (stamp, stamp))
        return asset_target, alias

    def _marker(self, name="a" * 64, size=160, mtime=None):
        path = os.path.join(self._thumb_dir(size), name + ".none")
        with open(path, "wb") as handle:
            handle.write(b"")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def _files(self):
        found = []
        for root, _directories, names in os.walk(os.path.join(cover_cache._cache_directory(self.config), "covers")):
            found.extend(os.path.join(root, name) for name in names)
        return sorted(found)

    def test_expired_negative_markers_are_removed_and_forgotten(self):
        stale = self._marker("b" * 64, mtime=self.now - cover_cache.MISSING_MARKER_TTL_SECONDS - 1)
        fresh = self._marker("c" * 64, mtime=self.now)
        with cover_cache._MEMORY_CACHE_LOCK:
            cover_cache._MISSING_MARKER_CACHE[stale] = self.now
            cover_cache._MISSING_MARKER_CACHE[fresh] = self.now
        self.assertEqual(cover_cache.prune_cover_cache(self.config), 1)
        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.isfile(fresh))
        with cover_cache._MEMORY_CACHE_LOCK:
            self.assertNotIn(stale, cover_cache._MISSING_MARKER_CACHE)
            self.assertIn(fresh, cover_cache._MISSING_MARKER_CACHE)

    def test_crash_left_behind_temporary_is_reclaimed_after_the_ttl(self):
        path = os.path.join(self._thumb_dir(), ".fnaudio-cover-abc123")
        with open(path, "wb") as handle:
            handle.write(b"half written")
        old = self.now - cover_cache.MISSING_MARKER_TTL_SECONDS - 1
        os.utime(path, (old, old))
        self.assertEqual(cover_cache.prune_cover_cache(self.config), 1)
        self.assertFalse(os.path.exists(path))

    def test_a_dangling_alias_never_survives_a_sweep(self):
        """An alias whose bytes are gone is the one shape that yields a broken image URL."""
        _asset, alias = self._publish("d" * 64, hashlib.sha256(b"one").hexdigest())
        os.unlink(_asset)
        with cover_cache._MEMORY_CACHE_LOCK:
            cover_cache._ASSET_ALIAS_CACHE[alias] = hashlib.sha256(b"one").hexdigest()
        self.assertEqual(cover_cache.prune_cover_cache(self.config), 1)
        self.assertFalse(os.path.exists(alias))
        with cover_cache._MEMORY_CACHE_LOCK:
            self.assertNotIn(alias, cover_cache._ASSET_ALIAS_CACHE)

    def test_an_asset_awaiting_its_alias_is_not_orphaned(self):
        _asset, alias = self._publish("e" * 64, hashlib.sha256(b"two").hexdigest())
        os.unlink(alias)                        # the writer has not published the alias yet
        os.utime(_asset, (self.now - 30, self.now - 30))
        self.assertEqual(cover_cache.prune_cover_cache(self.config), 0)
        self.assertTrue(os.path.isfile(_asset))

    def test_asset_bytes_no_alias_names_are_reclaimed_after_the_grace(self):
        asset, alias = self._publish("f" * 64, hashlib.sha256(b"three").hexdigest())
        aged = self.now - cover_cache.COVER_ASSET_ORPHAN_GRACE_SECONDS - 1
        os.unlink(alias)
        os.utime(asset, (aged, aged))
        self.assertEqual(cover_cache.prune_cover_cache(self.config), 1)
        self.assertFalse(os.path.exists(asset))

    def test_a_pass_deletes_at_most_the_bounded_number_of_files(self):
        """A reclaim may span intervals; one request must not pay for all of it."""
        original = cover_cache.COVER_CACHE_SWEEP_DELETE_LIMIT
        cover_cache.COVER_CACHE_SWEEP_DELETE_LIMIT = 2
        try:
            stale = self.now - cover_cache.MISSING_MARKER_TTL_SECONDS - 1
            for index in range(6):
                self._marker("%064x" % (index + 10), mtime=stale)
            self.assertEqual(cover_cache.prune_cover_cache(self.config), 2)
            self.assertEqual(len(self._files()), 4)
        finally:
            cover_cache.COVER_CACHE_SWEEP_DELETE_LIMIT = original

    def test_the_byte_budget_prunes_the_oldest_unit_and_keeps_the_newest(self):
        """Real payloads, because the configured budget has a 1 MiB floor.

        Asking for `cover_cache_max_bytes=1` clamps up to that floor, so the two
        units have to be genuinely bigger than 1 MiB for this to exercise the
        budget rule instead of the clamp.
        """
        cover_cache.clear_memory_cache()
        payload = b"\xff\xd8" + b"j" * (700 * 1024)
        old_asset, old_alias = self._publish("1" * 64, hashlib.sha256(b"old").hexdigest(),
                                             asset_mtime=self.now - 4000, alias_mtime=self.now - 4000,
                                             asset_bytes=payload)
        new_asset, new_alias = self._publish("2" * 64, hashlib.sha256(b"new").hexdigest(),
                                             asset_mtime=self.now - 10, alias_mtime=self.now - 10,
                                             asset_bytes=payload)
        with cover_cache._MEMORY_CACHE_LOCK:
            cover_cache._ASSET_ALIAS_CACHE[old_alias] = hashlib.sha256(b"old").hexdigest()
            cover_cache._ASSET_ALIAS_CACHE[new_alias] = hashlib.sha256(b"new").hexdigest()
        config = dict(self.config, cover_cache_max_bytes=1)     # clamped to the 1 MiB floor
        with mock.patch.object(cover_cache, "disk_has_reserve", return_value=True):
            self.assertEqual(cover_cache.prune_cover_cache(config), 2)
        self.assertFalse(os.path.exists(old_asset))
        self.assertFalse(os.path.exists(old_alias))
        self.assertTrue(os.path.isfile(new_asset))
        self.assertTrue(os.path.isfile(new_alias))
        with cover_cache._MEMORY_CACHE_LOCK:
            self.assertNotIn(old_alias, cover_cache._ASSET_ALIAS_CACHE)
            self.assertIn(new_alias, cover_cache._ASSET_ALIAS_CACHE)

    def test_disk_pressure_below_the_byte_budget_still_prunes(self):
        asset, alias = self._publish("3" * 64, hashlib.sha256(b"one").hexdigest())
        config = dict(self.config, cover_cache_max_bytes=8 * 1024 * 1024 * 1024)
        with mock.patch.object(cover_cache, "disk_has_reserve", return_value=False):
            self.assertEqual(cover_cache.prune_cover_cache(config), 2)
        self.assertFalse(os.path.exists(asset))
        self.assertFalse(os.path.exists(alias))

    def test_the_sweep_walk_is_bounded_per_pass(self):
        original = cover_cache.COVER_CACHE_SWEEP_ENTRY_LIMIT
        cover_cache.COVER_CACHE_SWEEP_ENTRY_LIMIT = 1
        try:
            for index in range(4):
                self._marker("%064x" % index, mtime=self.now - cover_cache.MISSING_MARKER_TTL_SECONDS - 1)
            self.assertEqual(cover_cache.prune_cover_cache(self.config), 1)
        finally:
            cover_cache.COVER_CACHE_SWEEP_ENTRY_LIMIT = original

    def test_sweep_runs_at_most_once_per_interval_even_when_it_fails(self):
        self._marker("4" * 64, mtime=self.now - cover_cache.MISSING_MARKER_TTL_SECONDS - 1)
        with mock.patch.object(cover_cache, "prune_cover_cache", side_effect=OSError("volume gone")) as prune:
            self.assertEqual(cover_cache.cleanup_cover_cache_if_due(self.config), 0)
            self.assertEqual(cover_cache.cleanup_cover_cache_if_due(self.config), 0)
            self.assertEqual(prune.call_count, 1, "a failing sweep must not re-arm every call")
            self.assertEqual(cover_cache.cleanup_cover_cache_if_due(self.config, force=True), 0)
            self.assertEqual(prune.call_count, 2)

    def test_publishing_triggers_housekeeping_once_and_a_failed_sweep_cannot_break_it(self):
        path = os.path.join(self._thumb_dir(), "5" * 64 + ".asset")
        # The failure belongs one level below the guard: housekeeping's own promise
        # is that its errors are absorbed there, so that is the function to break.
        with mock.patch.object(cover_cache, "prune_cover_cache", side_effect=OSError("volume gone")) as prune:
            cover_cache._atomic_bytes(path, b"\xff\xd8bytes", self.config)
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(prune.call_count, 1)
            cover_cache._atomic_bytes(path, b"\xff\xd8bytes", self.config)
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(prune.call_count, 1, "the interval was not consumed by the failure")
        with mock.patch.object(cover_cache, "cleanup_cover_cache_if_due") as sweep:
            cover_cache._atomic_bytes(path, b"\xff\xd8bytes")     # no config, no policy, no walk
            sweep.assert_not_called()


    def _assert_no_alias_names_missing_artwork(self):
        """The contract the sweep exists to keep: an alias always names real bytes.

        Checked twice on purpose.  On disk, because the cover endpoint re-reads
        the alias file, and in the in-process alias cache, because the
        latency-sensitive page path never revalidates and keeps handing the
        browser a cover-asset/<id> for as long as the entry sits there.
        """
        for path in self._files():
            if not path.endswith(".asset"):
                continue
            asset_target = cover_cache._alias_asset_path(self.config, path)
            self.assertTrue(asset_target and os.path.isfile(asset_target),
                            "%s names artwork that is no longer on disk" % os.path.basename(path))
        with cover_cache._MEMORY_CACHE_LOCK:
            advertised = dict(cover_cache._ASSET_ALIAS_CACHE)
        for alias, asset_key in advertised.items():
            _asset_root, asset_target = cover_cache._asset_path(self.config, 160, asset_key)
            self.assertTrue(os.path.isfile(asset_target),
                            "%s is still advertised to the page but its artwork is gone" % alias)

    def test_the_delete_budget_cannot_be_spent_across_a_unit(self):
        """A pass that cannot afford a whole unit must not start it.

        One shared asset named by two per-track aliases is the normal shape:
        every version of the same artwork points at the same JPEG.  With two
        credits and three files, spending the first on the asset used to leave
        the second alias behind naming bytes that no longer exist.
        """
        key = hashlib.sha256(b"shared-artwork").hexdigest()
        asset, first = self._publish("6" * 64, key)
        _again, second = self._publish("7" * 64, key)
        for alias in (first, second):
            with cover_cache._MEMORY_CACHE_LOCK:
                cover_cache._ASSET_ALIAS_CACHE[alias] = key
        original = cover_cache.COVER_CACHE_SWEEP_DELETE_LIMIT
        cover_cache.COVER_CACHE_SWEEP_DELETE_LIMIT = 2
        try:
            with mock.patch.object(cover_cache, "disk_has_reserve", return_value=False):
                self.assertEqual(cover_cache.prune_cover_cache(self.config), 0)
        finally:
            cover_cache.COVER_CACHE_SWEEP_DELETE_LIMIT = original
        self.assertTrue(os.path.isfile(asset))
        self.assertTrue(os.path.isfile(first))
        self.assertTrue(os.path.isfile(second))
        self._assert_no_alias_names_missing_artwork()

    def test_a_unit_that_fits_the_budget_is_reclaimed_whole(self):
        """The guard reserves credit, it does not refuse to evict anything."""
        key = hashlib.sha256(b"shared-artwork").hexdigest()
        asset, first = self._publish("8" * 64, key)
        _again, second = self._publish("9" * 64, key)
        original = cover_cache.COVER_CACHE_SWEEP_DELETE_LIMIT
        cover_cache.COVER_CACHE_SWEEP_DELETE_LIMIT = 3
        try:
            with mock.patch.object(cover_cache, "disk_has_reserve", return_value=False):
                self.assertEqual(cover_cache.prune_cover_cache(self.config), 3)
        finally:
            cover_cache.COVER_CACHE_SWEEP_DELETE_LIMIT = original
        self.assertFalse(os.path.exists(asset))
        self.assertFalse(os.path.exists(first))
        self.assertFalse(os.path.exists(second))
        self._assert_no_alias_names_missing_artwork()

    def test_an_alias_the_volume_keeps_backs_the_whole_unit_off(self):
        """A stuck alias means these bytes are not ours to take this pass.

        The delete budget is reserved before the first unlink, so the only way
        an alias can survive this loop is a volume that will not hand it over.
        Removing the asset anyway would recreate the dangling pointer, and
        carrying on to the next unit would evict newer artwork behind an older
        one that is still there.
        """
        stuck_key = hashlib.sha256(b"stuck-artwork").hexdigest()
        old = self.now - 5000
        stuck_asset, clear_alias = self._publish("a" * 64, stuck_key,
                                                 asset_mtime=old, alias_mtime=old)
        _again, stuck_alias = self._publish("b" * 64, stuck_key,
                                            asset_mtime=old, alias_mtime=old)
        newer_key = hashlib.sha256(b"newer-artwork").hexdigest()
        newer_asset, newer_alias = self._publish("c" * 64, newer_key,
                                                 asset_mtime=self.now - 10,
                                                 alias_mtime=self.now - 10)
        real_delete = cover_cache._delete_cover_file

        def refuse_one(path):
            return False if path == stuck_alias else real_delete(path)

        with mock.patch.object(cover_cache, "disk_has_reserve", return_value=False), \
             mock.patch.object(cover_cache, "_delete_cover_file", side_effect=refuse_one):
            self.assertEqual(cover_cache.prune_cover_cache(self.config), 1)
        self.assertFalse(os.path.exists(clear_alias))
        self.assertTrue(os.path.isfile(stuck_alias))
        self.assertTrue(os.path.isfile(stuck_asset))
        self.assertTrue(os.path.isfile(newer_asset))
        self.assertTrue(os.path.isfile(newer_alias))
        self._assert_no_alias_names_missing_artwork()


if __name__ == "__main__":
    unittest.main()
