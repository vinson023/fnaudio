"""Guards for sharing one album's cover render across its tracks (R585, P3).

The rendered JPEG was already content-addressed, so a 12-track album stored one
image and twelve 64-byte aliases.  What it still paid was twelve renders of the
same bytes.  These tests pin the behaviour that made it one: the artwork-digest
memo, and the three ways it must refuse to answer — different artwork, a
reclaimed asset, a different cache directory or size.

See docs/LIBRARY_VIEWS_PLAN.md, P3.
"""

import hashlib
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

import cover_cache


def _item(index, size=1024):
    return {
        "id": "track-%03d" % index,
        "modified_ns": 1_700_000_000_000_000_000 + index,
        "size": size,
    }


def _reader(body):
    return lambda item, config: ("image/jpeg", body)


class CoverArtworkReuseTests(unittest.TestCase):
    def setUp(self):
        cover_cache.clear_memory_cache()
        self._temp = tempfile.TemporaryDirectory()
        self.config = {"cache_dir": self._temp.name}
        self.body = b"\xff\xd8" + b"artwork" * 64
        self.thumb = b"\xff\xd8thumbnail"

    def tearDown(self):
        cover_cache.clear_memory_cache()
        self._temp.cleanup()

    def _render(self, item, body=None, size=160, thumb=None):
        with mock.patch.object(cover_cache, "_thumbnail_bytes",
                               return_value=self.thumb if thumb is None else thumb) as resize:
            value = cover_cache.cached_thumbnail_for_item(
                item, self.config, size, _reader(self.body if body is None else body)
            )
        return value, resize.call_count

    def test_second_track_with_the_same_artwork_reuses_the_first_render(self):
        first, calls_first = self._render(_item(0))
        second, calls_second = self._render(_item(1))
        self.assertEqual(first, ("image/jpeg", self.thumb))
        self.assertEqual(second, first, "a shared render must produce the same bytes")
        self.assertEqual(calls_first, 1)
        self.assertEqual(calls_second, 0, "the second track must not render again")

    def test_a_whole_album_costs_one_render(self):
        calls = 0
        for index in range(12):
            _value, count = self._render(_item(index))
            calls += count
        self.assertEqual(calls, 1, "twelve tracks sharing artwork must render once")

    def test_different_artwork_still_renders_separately(self):
        self._render(_item(0))
        _value, calls = self._render(_item(1), body=b"\xff\xd8different")
        self.assertEqual(calls, 1, "different artwork must never reuse another render")

    def test_different_sizes_do_not_share_a_render(self):
        self._render(_item(0), size=160)
        _value, calls = self._render(_item(1), size=512)
        self.assertEqual(calls, 1, "a thumbnail size is part of what was rendered")

    def test_different_cache_directories_do_not_share_a_render(self):
        self._render(_item(0))
        with tempfile.TemporaryDirectory() as other:
            with mock.patch.object(cover_cache, "_thumbnail_bytes",
                                   return_value=self.thumb) as resize:
                cover_cache.cached_thumbnail_for_item(
                    _item(1), {"cache_dir": other}, 160, _reader(self.body)
                )
        self.assertEqual(resize.call_count, 1, "a hint must not cross cache directories")

    def test_reuse_still_writes_the_per_track_alias(self):
        self._render(_item(0))
        item = _item(1)
        self._render(item)
        version = cover_cache.cover_source_version(item)
        _root, target, _missing = cover_cache._cache_paths(item, self.config, 160, version)
        alias = target[:-4] + ".asset"
        self.assertTrue(os.path.isfile(alias), "each track keeps its own alias file")
        with open(alias, "rb") as handle:
            asset_key = handle.read().decode("ascii")
        expected = hashlib.sha256(self.body).hexdigest()
        self.assertEqual(asset_key, expected, "the alias must name the artwork's own asset")
        _asset_root, asset_file = cover_cache._asset_path(self.config, 160, expected)
        self.assertTrue(os.path.isfile(asset_file), "the shared image is stored once")

    def test_a_restart_serves_the_second_track_without_rendering(self):
        self._render(_item(0))
        item = _item(1)
        self._render(item)
        # A new process has no memo, no alias cache and no memory cache; only the
        # alias file on disk can answer.
        cover_cache.clear_memory_cache()
        with mock.patch.object(cover_cache, "_thumbnail_bytes") as resize:
            value = cover_cache.cached_thumbnail_for_item(
                item, self.config, 160, _reader(self.body)
            )
        resize.assert_not_called()
        self.assertEqual(value, ("image/jpeg", self.thumb))

    def test_a_reclaimed_asset_falls_back_to_rendering(self):
        self._render(_item(0))
        asset_file = cover_cache._asset_path(
            self.config, 160, hashlib.sha256(self.body).hexdigest()
        )[1]
        os.unlink(asset_file)
        cover_cache.clear_memory_cache()
        _value, calls = self._render(_item(1))
        self.assertEqual(calls, 1, "a hint may not outlive the asset it names")

    def test_a_failed_alias_write_during_reuse_still_answers(self):
        self._render(_item(0))
        real = cover_cache._atomic_bytes

        def fail_aliases(path, body, config, durable=True):
            if path.endswith(".asset"):
                raise OSError("read-only volume")
            return real(path, body, config, durable=durable)

        with mock.patch.object(cover_cache, "_atomic_bytes", side_effect=fail_aliases), \
             mock.patch.object(cover_cache, "_thumbnail_bytes") as resize:
            value = cover_cache.cached_thumbnail_for_item(
                _item(1), self.config, 160, _reader(self.body)
            )
        resize.assert_not_called()
        self.assertEqual(value, ("image/jpeg", self.thumb),
                         "a cache write must never fail the response")

    def test_clear_memory_cache_drops_the_hint(self):
        self._render(_item(0))
        cover_cache.clear_memory_cache()
        _value, calls = self._render(_item(1))
        self.assertEqual(calls, 1)

    def test_the_hint_is_bounded(self):
        limit = cover_cache._ARTWORK_ASSET_CACHE_LIMIT
        for index in range(limit + 8):
            cover_cache._remember_artwork_asset(
                self.config["cache_dir"], "d%063d" % index, 160, "a" * 64
            )
        self.assertLessEqual(len(cover_cache._ARTWORK_ASSET_CACHE), limit)

    def test_the_hint_rejects_empty_values(self):
        cover_cache._remember_artwork_asset(self.config["cache_dir"], "", 160, "a" * 64)
        cover_cache._remember_artwork_asset(self.config["cache_dir"], "d" * 64, 0, "a" * 64)
        cover_cache._remember_artwork_asset(self.config["cache_dir"], "d" * 64, 160, "")
        self.assertEqual(len(cover_cache._ARTWORK_ASSET_CACHE), 0)
        self.assertEqual(cover_cache._artwork_asset_key(self.config["cache_dir"], "", 160), "")

    def test_status_reports_the_hint_size(self):
        self._render(_item(0))
        snapshot = cover_cache.thumbnail_prewarm_status()
        memory = snapshot["memory_cache"]
        self.assertGreaterEqual(memory["artwork_entries"], 1)
        self.assertLessEqual(memory["artwork_entries"], memory["artwork_limit"])


if __name__ == "__main__":
    unittest.main()
