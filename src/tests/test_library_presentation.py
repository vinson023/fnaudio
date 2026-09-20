import re
import sys
import unittest
from collections.abc import Mapping
from pathlib import Path
from unittest import mock

sys.path.insert(0, "app/server")

from library_presentation import MAX_PUBLIC_ITEM_FIELDS, MAX_PUBLIC_PAGE_ITEMS, public_library_item, public_library_page


class LibraryPresentationTests(unittest.TestCase):
    def test_public_item_skips_bulky_internal_fields_before_projection(self):
        item = {"id": "t1", "title": "Song", "item_json": "x" * 100000, "lyrics": "y" * 100000, "metadata_artwork_id": "a" * 64}
        result = public_library_item(item, {})
        self.assertNotIn("item_json", result)
        self.assertNotIn("lyrics", result)
        self.assertNotIn("metadata_artwork_id", result)
    def test_public_item_omits_path_and_uses_versioned_cover_urls(self):
        item = {"id": "track-1", "title": "Track", "path": "/private/music/track.flac", "modified_ns": 42}
        with mock.patch("library_presentation.cover_is_known_missing", return_value=False), mock.patch(
            "library_presentation.cover_source_version", return_value="v42"
        ), mock.patch("library_presentation.thumbnail_asset_id_for_item", return_value="asset-42"):
            result = public_library_item(item, {"library_path": "/private/music"})
        self.assertNotIn("path", result)
        self.assertEqual(result["url"], "media/track-1")
        self.assertEqual(result["cover_url"], "cover/track-1?v=v42")
        self.assertEqual(result["cover_thumbnail_url"], "cover-asset/asset-42?size=160")
        self.assertEqual(item["path"], "/private/music/track.flac")

    def test_known_missing_cover_omits_primary_cover_but_retains_cached_asset(self):
        with mock.patch("library_presentation.cover_is_known_missing", return_value=True), mock.patch(
            "library_presentation.thumbnail_asset_id_for_item", return_value="asset"
        ):
            result = public_library_item({"id": "track-2", "path": "/private/track.mp3"})
        self.assertEqual(result["cover_url"], "")
        self.assertEqual(result["cover_thumbnail_url"], "cover-asset/asset?size=160")

    def test_metadata_artwork_is_projected_for_coverless_track(self):
        with mock.patch("library_presentation.cover_is_known_missing", return_value=True), mock.patch(
            "library_presentation.thumbnail_asset_id_for_item", return_value=""
        ):
            result = public_library_item({
                "id": "track-3", "metadata_artwork_id": "a" * 64,
                "lyrics": "[00:01.00]cached lyric", "item_json": '{"private":true}',
            })
        self.assertEqual(result["cover_url"], "metadata/artwork/" + "a" * 64)
        self.assertNotIn("metadata_artwork_id", result)
        self.assertNotIn("lyrics", result)
        self.assertNotIn("item_json", result)

    def test_invalid_metadata_artwork_id_is_not_exposed_as_a_url(self):
        with mock.patch("library_presentation.thumbnail_asset_id_for_item", return_value=""):
            result = public_library_item({"id": "track-4", "metadata_artwork_id": "not-an-id"})
        self.assertTrue(result["cover_url"].startswith("cover/track-4"))

    def test_page_projection_is_bounded_and_skips_invalid_items(self):
        rows = [{"id": "track-%d" % index, "title": "Track"} for index in range(MAX_PUBLIC_PAGE_ITEMS + 10)]
        result = public_library_page({"items": [None, rows[0]] + rows[1:]}, {})
        self.assertEqual(len(result["items"]), MAX_PUBLIC_PAGE_ITEMS)
        self.assertNotIn("path", result["items"][0])

    def test_page_projection_uses_memory_only_cover_lookup(self):
        rows = [{"id": "track-1", "title": "Track", "path": "/private/track.flac", "modified_ns": 1}]
        with mock.patch("library_presentation.cover_is_known_missing", return_value=False) as missing, mock.patch(
            "library_presentation.thumbnail_asset_id_for_item", return_value=""
        ) as asset:
            result = public_library_page({"items": rows}, {})
        self.assertTrue(result["items"][0]["cover_url"].startswith("cover/track-1"))
        self.assertEqual(missing.call_args.kwargs.get("allow_disk"), False)
        self.assertEqual(asset.call_args.kwargs.get("allow_disk"), False)

    def test_page_projection_uses_non_blocking_cover_version(self):
        row = {"id": "track-2", "title": "Track", "path": "/slow/track.flac"}
        with mock.patch("library_presentation.cover_is_known_missing", return_value=False), mock.patch(
            "library_presentation.thumbnail_asset_id_for_item", return_value=""
        ), mock.patch("library_presentation.cover_source_version", return_value="0") as version:
            public_library_page({"items": [row]}, {})
        self.assertEqual(version.call_args.kwargs.get("allow_disk"), False)

    def test_page_projection_handles_non_mapping_page(self):
        self.assertEqual(public_library_page(None), {"items": []})

    def test_item_projection_is_bounded_and_isolates_broken_mapping(self):
        class Item(dict):
            def items(self):
                for index in range(MAX_PUBLIC_ITEM_FIELDS + 50):
                    yield ("field-%d" % index, index)
        result = public_library_item(Item({"id": "track"}))
        self.assertLessEqual(len(result), MAX_PUBLIC_ITEM_FIELDS + 3)

        class Broken(dict):
            def items(self):
                raise RuntimeError("broken")
            def get(self, key, default=None):
                raise RuntimeError("broken")
        self.assertEqual(public_library_item(Broken()), {"url": "media/", "cover_url": "", "cover_thumbnail_url": ""})

    def test_page_projection_does_not_copy_unbounded_top_level_mapping(self):
        class Page(dict):
            def items(self):
                for index in range(1000):
                    yield ("field-%d" % index, index)

        result = public_library_page(Page())
        self.assertEqual(len(result), 33)
        self.assertEqual(result["items"], [])

    def test_page_projection_keeps_items_after_unrelated_prefix(self):
        class Page(Mapping):
            def items(self):
                for index in range(40):
                    yield ("field-%d" % index, index)
                yield ("items", [{"id": "late-track", "title": "Late"}])
                yield ("count", 1)

            def __iter__(self):
                return iter(())

            def __len__(self):
                return 0

            def __getitem__(self, key):
                if key == "items":
                    return [{"id": "late-track", "title": "Late"}]
                if key == "count":
                    return 1
                raise KeyError(key)

        result = public_library_page(Page())
        self.assertEqual([item["id"] for item in result["items"]], ["late-track"])
        self.assertEqual(result["count"], 1)
        self.assertLessEqual(len(result), 32 + 7)
    def test_library_routes_enrich_before_projecting_track_rows(self):
        # The provider artwork id reaches a client only through
        # `enrich_track_page`, because the projection itself publishes just a
        # cover URL and drops the internal id.  A route that projects track
        # rows without first enriching them therefore loses cached covers, so
        # pin the wiring in the source instead of trusting a comment.  The
        # exact site count is part of the pin: a new track projection route
        # has to be considered here rather than silently skipping enrichment.
        server = Path(__file__).resolve().parents[1] / "app" / "server" / "server.py"
        lines = server.read_text(encoding="utf-8").splitlines()
        sites = [
            index for index, line in enumerate(lines)
            if re.search(r"\bpublic_(?:library_page|item)\(", line)
            and not line.lstrip().startswith("def ")
        ]
        self.assertEqual(len(sites), 3, "unexpected public track-projection call sites in server.py")
        for index in sites:
            window = "\n".join(lines[max(0, index - 8):index + 1])
            self.assertIn(
                "enrich_track_page",
                window,
                "library projection at server.py:%d has no metadata enrichment" % (index + 1),
            )
    def test_provider_artwork_does_not_replace_a_generated_thumbnail(self):
        # The provider cover is the slower asset path, so it only fills the
        # gap left by a missing thumbnail.  R107 rejected "always prefer
        # provider artwork" as the fix for the artwork-plumbing note; this
        # pin keeps that priority from drifting.
        item = {"id": "track-5", "metadata_artwork_id": "a" * 64, "path": "/private/t5.flac"}
        with mock.patch("library_presentation.cover_is_known_missing", return_value=False), mock.patch(
            "library_presentation.thumbnail_asset_id_for_item", return_value="asset-5"
        ):
            result = public_library_item(item, {})
        self.assertEqual(result["cover_thumbnail_url"], "cover-asset/asset-5?size=160")
        self.assertTrue(result["cover_url"].startswith("cover/track-5"))


if __name__ == "__main__":
    unittest.main()
