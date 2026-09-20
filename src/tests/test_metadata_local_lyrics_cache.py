import sys
import os
import unittest
from unittest.mock import Mock

sys.path.insert(0, "app/server")

from metadata_local_lyrics_cache import (
    DEFAULT_MAX_BYTES,
    MAX_BYTES_COUNTER,
    MAX_MAX_BYTES,
    MIN_MAX_BYTES,
    LocalLyricsCache,
    combined_snapshot,
)


class LocalLyricsCacheTests(unittest.TestCase):
    def test_version_hint_avoids_stat_and_hits_cache(self):
        reader = Mock(return_value="[00:01.00]one")
        stat = Mock(side_effect=AssertionError("indexed version should avoid stat"))
        cache = LocalLyricsCache(reader, stat_func=stat)
        self.assertEqual(cache.read("song.flac", (7, 42)), "[00:01.00]one")
        self.assertEqual(cache.read("song.flac", (7, 42)), "[00:01.00]one")
        reader.assert_called_once_with("song.flac")
        stat.assert_not_called()
        self.assertEqual(
            cache.snapshot(),
            {
                "entries": 1, "limit": 256,
                "bytes": sys.getsizeof("[00:01.00]one"), "bytes_limit": DEFAULT_MAX_BYTES,
                "hits": 1, "misses": 1,
            },
        )

    def test_replacement_evicts_old_path_version(self):
        reader = Mock(side_effect=["old", "new", "other", "old-again"])
        cache = LocalLyricsCache(reader)
        self.assertEqual(cache.read("song.flac", (1, 1)), "old")
        self.assertEqual(cache.read("song.flac", (2, 1)), "new")
        self.assertEqual(cache.read("other.flac", (1, 1)), "other")
        self.assertEqual(cache.read("song.flac", (1, 1)), "old-again")
        self.assertEqual(reader.call_count, 4)

    def test_stale_version_release_returns_its_retained_bytes(self):
        # The purge that drops a superseded version of the same file has to give
        # its bytes back, or one repeatedly re-written lyric file grows forever.
        bodies = iter(["x" * 60000, "y" * 1000, "q" * 500])
        cache = LocalLyricsCache(lambda path: next(bodies), max_bytes=1024 * 1024)
        cache.read("song.lrc", (1, 1))
        self.assertEqual(cache.snapshot()["bytes"], sys.getsizeof("x" * 60000))
        cache.read("song.lrc", (2, 2))
        self.assertEqual(cache.snapshot()["bytes"], sys.getsizeof("y" * 1000))
        cache.read("song.lrc", (1, 1))
        snapshot = cache.snapshot()
        self.assertEqual(snapshot["entries"], 1)
        self.assertEqual(snapshot["bytes"], sys.getsizeof("q" * 500))

    def test_stat_failure_keeps_virtual_reader_compatible_and_bounds_entries(self):
        reader = Mock(side_effect=lambda path: "lyrics:" + path)
        stat = Mock(side_effect=OSError("virtual"))
        cache = LocalLyricsCache(reader, limit=1, stat_func=stat)
        self.assertEqual(cache.read("virtual-a"), "lyrics:virtual-a")
        self.assertEqual(cache.read("virtual-a"), "lyrics:virtual-a")
        self.assertEqual(cache.read("virtual-b"), "lyrics:virtual-b")
        self.assertEqual(cache.read("virtual-a"), "lyrics:virtual-a")
        self.assertEqual(reader.call_count, 3)

    def test_empty_stat_failure_is_rechecked_when_sidecar_appears(self):
        reader = Mock(side_effect=["", "[00:01.00]now-visible"])
        stat = Mock(side_effect=[OSError("not-created-yet"), os.stat_result((0,) * 10)])
        cache = LocalLyricsCache(reader, stat_func=stat)
        self.assertEqual(cache.read("song.lrc"), "")
        self.assertEqual(cache.read("song.lrc"), "[00:01.00]now-visible")
        self.assertEqual(reader.call_count, 2)

    def test_empty_result_is_rechecked_even_with_media_version_hint(self):
        reader = Mock(side_effect=["", "[00:01.00]sidecar"])
        cache = LocalLyricsCache(reader)
        self.assertEqual(cache.read("song.flac", (7, 42)), "")
        self.assertEqual(cache.read("song.flac", (7, 42)), "[00:01.00]sidecar")
        self.assertEqual(reader.call_count, 2)

    def test_invalid_path_and_reader_failure_are_safe(self):
        cache = LocalLyricsCache(Mock(side_effect=ValueError("bad")))
        self.assertEqual(cache.read(None), "")
        self.assertEqual(cache.read("song.flac", (True, 1)), "")

    def test_byte_budget_evicts_before_the_entry_limit_is_reached(self):
        # Two ordinary lyric documents do not fit the smallest expressible byte
        # budget, even though the entry limit of 256 would happily allow both.
        body = "x" * 60000
        self.assertLessEqual(sys.getsizeof(body), MIN_MAX_BYTES)
        self.assertGreater(sys.getsizeof(body) * 2, MIN_MAX_BYTES)
        reader = Mock(side_effect=lambda path: body + path)
        cache = LocalLyricsCache(reader, max_bytes=MIN_MAX_BYTES)
        cache.read("a.lrc", (1, 1))
        cache.read("b.lrc", (1, 1))
        snapshot = cache.snapshot()
        self.assertEqual(snapshot["entries"], 1)
        self.assertLessEqual(snapshot["bytes"], snapshot["bytes_limit"])
        self.assertEqual(reader.call_count, 2)
        cache.read("a.lrc", (1, 1))
        self.assertEqual(reader.call_count, 3)

    def test_oversized_document_is_served_without_flushing_the_cache(self):
        # Budget eviction alone would also end up with nothing retained, so the
        # point of refusing an oversized document is the work already cached:
        # one huge lyric file must not flush every other song on every read.
        oversized = "x" * MIN_MAX_BYTES
        self.assertGreater(sys.getsizeof(oversized), MIN_MAX_BYTES)
        bodies = {"a.lrc": "short a", "b.lrc": "short b", "big.lrc": oversized}
        reader = Mock(side_effect=lambda path: bodies[path])
        cache = LocalLyricsCache(reader, max_bytes=MIN_MAX_BYTES)
        cache.read("a.lrc", (1, 1))
        cache.read("b.lrc", (1, 1))
        self.assertEqual(cache.read("big.lrc", (1, 1)), oversized)
        self.assertEqual(cache.snapshot()["entries"], 2)
        self.assertEqual(cache.snapshot()["bytes"],
                         sys.getsizeof("short a") + sys.getsizeof("short b"))
        self.assertEqual(reader.call_count, 3)
        # The neighbours survived, so they still hit without a read.
        self.assertEqual(cache.read("a.lrc", (1, 1)), "short a")
        self.assertEqual(cache.read("b.lrc", (1, 1)), "short b")
        self.assertEqual(reader.call_count, 3)

    def test_byte_budget_evicts_repeatedly_until_the_total_fits(self):
        # A small document can overshoot the budget by more than one entry, so a
        # single eviction is not enough. This asserts the invariant after every
        # insert, which is what a one-shot eviction would break.
        budget = MIN_MAX_BYTES
        reads = []

        def reader(path):
            reads.append(path)
            return "x" * 1000

        cache = LocalLyricsCache(reader, max_bytes=budget)
        for index in range(120):
            cache.read("p%d.lrc" % index, (1, index))
            snapshot = cache.snapshot()
            self.assertLessEqual(snapshot["bytes"], snapshot["bytes_limit"])
            self.assertLessEqual(snapshot["entries"], cache._limit)
        self.assertGreater(cache.snapshot()["entries"], 1)
        self.assertEqual(len(reads), 120)
        # The first document is long gone, so this is a miss, not a hit.
        self.assertEqual(cache.read("p0.lrc", (1, 0)), "x" * 1000)
        self.assertEqual(len(reads), 121)

    def test_releasing_an_unknown_key_leaves_the_total_intact(self):
        # The release helper pops with a default, so it must also skip the
        # subtraction. Otherwise a stale key would corrupt the running total.
        cache = LocalLyricsCache(lambda path: "x" * 1000, max_bytes=MIN_MAX_BYTES)
        cache.read("a.lrc", (1, 1))
        retained = cache.snapshot()["bytes"]
        cache._release(("missing.lrc", 9, 9))
        self.assertEqual(cache.snapshot()["bytes"], retained)

    def test_a_large_document_evicts_more_than_one_entry(self):
        # One eviction is only enough when the oldest entries are as large as the
        # newcomer. Many short lyric files followed by one long document makes the
        # overshoot bigger than a single pop, which is what the loop is for.
        cache = LocalLyricsCache(lambda path: "s" * 100 if path < "b" else "x" * 60000,
                                 max_bytes=MIN_MAX_BYTES)
        for index in range(30):
            cache.read("a%02d.lrc" % index, (1, index))
        cache.read("b01.lrc", (1, 1))
        cache.read("b02.lrc", (1, 2))
        snapshot = cache.snapshot()
        self.assertLessEqual(snapshot["bytes"], snapshot["bytes_limit"])
        self.assertEqual(snapshot["entries"], 1)

    def test_byte_budget_is_clamped_to_a_usable_range(self):
        # Pairs, not a dict: True hashes as 1, so a dict literal would silently
        # drop one of the two cases.
        cases = (
            (1, MIN_MAX_BYTES),
            (0, MIN_MAX_BYTES),
            (-1, MIN_MAX_BYTES),
            (10 ** 12, MAX_MAX_BYTES),
            ("8 MiB", DEFAULT_MAX_BYTES),
            (True, DEFAULT_MAX_BYTES),
            (None, DEFAULT_MAX_BYTES),
        )
        for value, expected in cases:
            with self.subTest(max_bytes=value):
                cache = LocalLyricsCache(Mock(return_value="x"), max_bytes=value)
                self.assertEqual(cache.snapshot()["bytes_limit"], expected)

    def test_snapshot_reports_only_bounded_counters(self):
        cache = LocalLyricsCache(Mock(return_value="secret lyrics"), max_bytes=MIN_MAX_BYTES)
        cache.read("/vol1/private/song.lrc", (1, 1))
        text = repr(cache.snapshot())
        self.assertNotIn("secret", text)
        self.assertNotIn("private", text)
        self.assertEqual(
            set(cache.snapshot()),
            {"entries", "limit", "bytes", "bytes_limit", "hits", "misses"},
        )

    def test_combined_snapshot_is_bounded_and_does_not_coerce_values(self):
        self.assertEqual(
            combined_snapshot(
                {"entries": 2, "limit": 3, "bytes": 40, "bytes_limit": 100, "hits": 4, "misses": 5},
                {"entries": 4, "limit": 5, "bytes": 60, "bytes_limit": 200, "hits": 6, "misses": 7},
            ),
            {"entries": 6, "limit": 8, "bytes": 100, "bytes_limit": 300, "hits": 10, "misses": 12},
        )
        self.assertEqual(
            combined_snapshot({
                "entries": 9, "limit": 1, "bytes": 900, "bytes_limit": 1,
                "hits": True, "misses": object(),
            }),
            {"entries": 1, "limit": 1, "bytes": 1, "bytes_limit": 1, "hits": 0, "misses": 0},
        )

    def test_combined_snapshot_keeps_byte_totals_out_of_the_count_ceiling(self):
        # MAX_COUNTER is one million. Aggregating two default budgets is 16 MiB,
        # so sharing that ceiling between counts and bytes under-reported the
        # cache by a factor of eight.
        budget = DEFAULT_MAX_BYTES
        aggregate = combined_snapshot(
            {"entries": 4, "limit": 256, "bytes": budget, "bytes_limit": budget, "hits": 1, "misses": 1},
            {"entries": 4, "limit": 256, "bytes": budget, "bytes_limit": budget, "hits": 1, "misses": 1},
        )
        self.assertEqual(aggregate["bytes"], budget * 2)
        self.assertEqual(aggregate["bytes_limit"], budget * 2)
        self.assertEqual(aggregate["hits"], 2)
        self.assertEqual(
            combined_snapshot({"bytes": 10 ** 15, "bytes_limit": 10 ** 15})["bytes"],
            MAX_BYTES_COUNTER,
        )


if __name__ == "__main__":
    unittest.main()