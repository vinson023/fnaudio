import pathlib
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, "app/server")

from app.server.metadata_unavailable_policy import _MAX_LYRICS_CHARS, _MAX_TEXT, local_cached_projection, local_lyrics_projection, local_pending_projection, lyrics_pending_projection, merge_pending_projection
from cue_item_presentation import build_cue_item
from library_metadata_presentation import library_metadata
from library_presentation import public_library_item
from library_scan_presentation import build_audio_item

SERVER_SOURCE = pathlib.Path(__file__).resolve().parents[2] / "src" / "app" / "server" / "server.py"
_SUPPLIER_KEYS = ("lyrics", "cover_url", "cover_thumbnail_url", "metadata_artwork_id")


class MetadataUnavailablePolicyTests(unittest.TestCase):
    def test_pending_projection_keeps_local_cover_without_tags(self):
        result = local_pending_projection("t1", {"cover_url": "cover/t1?size=512", "lyrics": "[00:01]x"})
        self.assertEqual(result["image_url"], "cover/t1?size=512")
        self.assertEqual(result["lyrics"], "[00:01]x")
        self.assertTrue(result["pending"])
    def test_projects_embedded_lyrics_during_service_startup(self):
        result = local_lyrics_projection({
            "lyrics": " [00:01.00]hello ", "cover_url": "cover/track-1?v=2",
        })
        self.assertEqual(result["status"], "local")
        self.assertEqual(result["lyrics"], "[00:01.00]hello")
        self.assertEqual(result["source"], "本地歌词")
        self.assertEqual(result["image_url"], "cover/track-1?v=2")
        self.assertIsNone(local_lyrics_projection({"lyrics": ""}))

    def test_full_document_lyrics_survive_every_recovery_projection(self):
        lyric = "\n".join("[00:%02d.00]line %d" % (index % 60, index) for index in range(200))
        self.assertGreater(len(lyric), _MAX_TEXT)
        item = {"title": "Song", "lyrics": lyric, "cover_url": "cover/track-1?v=2"}
        self.assertEqual(local_lyrics_projection(item)["lyrics"], lyric)
        self.assertEqual(local_cached_projection("track-1", item)["lyrics"], lyric)
        self.assertEqual(local_pending_projection("track-1", item)["lyrics"], lyric)

    def test_document_lyrics_keep_the_document_size_budget(self):
        lyric = "x" * (_MAX_LYRICS_CHARS + 100)
        result = local_lyrics_projection({"lyrics": lyric})
        self.assertEqual(len(result["lyrics"]), _MAX_LYRICS_CHARS)

    def test_recovery_projections_still_bound_tag_fields(self):
        result = local_cached_projection("track-1", {"title": "x" * 4000, "artist": "Artist"})
        # The budget is spelled out rather than read back from the module, so
        # widening the tag limit to the document limit cannot satisfy this.
        self.assertEqual(len(result["best"]["title"]), 512)
        self.assertLess(_MAX_TEXT, _MAX_LYRICS_CHARS)

    def test_projects_local_tags_during_metadata_service_startup(self):
        result = local_cached_projection("track-1", {
            "title": " Song ", "artist": "Artist", "album": "Album",
            "lyrics": "[00:01.00]hello", "cover_thumbnail_url": "cover-asset/a?size=160", "path": "/private/source.flac",
        })
        self.assertEqual(result["status"], "local")
        self.assertFalse(result["pending"])
        self.assertEqual(result["source"], "本地标签")
        self.assertEqual(result["best"], {"title": "Song", "artist": "Artist", "album": "Album"})
        self.assertEqual(result["lyrics"], "[00:01.00]hello")
        self.assertEqual(result["image_url"], "cover-asset/a?size=160")
        self.assertNotIn("path", result)

    def test_projects_bounded_local_identity_as_retryable_pending(self):
        result = local_pending_projection("track-1", {
            "title": "  Song ", "artist": "Artist", "album": "Album",
            "path": "/private/source.flac",
        }, "worker restarting")
        self.assertEqual(result["status"], "pending")
        self.assertTrue(result["retryable"])
        self.assertEqual(result["best"], {"title": "Song", "artist": "Artist", "album": "Album"})
        self.assertNotIn("path", result["best"])

    def test_pending_projection_uses_filename_identity_when_tags_are_empty(self):
        result = local_pending_projection("track-1", {
            "path": "/music/Artist - Song.flac",
            "title": "", "artist": "", "album": "",
        })
        self.assertEqual(result["status"], "pending")
        self.assertTrue(result["retryable"])
        self.assertEqual(result["best"].get("artist"), "Artist")
        self.assertEqual(result["best"].get("title"), "Song")

    def test_rejects_arbitrary_objects_without_coercion(self):
        result = local_pending_projection(object(), {"title": object(), "artist": True})
        self.assertEqual(result["track_id"], "")
        self.assertEqual(result["best"], {})
        self.assertEqual(result["candidates"], [])

    def test_rejects_non_finite_local_metadata_values(self):
        result = local_pending_projection("track-1", {
            "title": float("nan"), "artist": float("inf"), "album": "Album",
        })
        self.assertEqual(result["best"], {"album": "Album"})

    def test_lyrics_projection_is_retryable_and_bounded(self):
        result = lyrics_pending_projection("worker restarting")
        self.assertEqual(result["status"], "pending")
        self.assertTrue(result["retryable"])
        self.assertEqual(result["error"], "worker restarting")
        self.assertEqual(result["lyrics"], "")

    def test_merge_pending_projection_preserves_provider_fields_and_adds_local_fields(self):
        pending = {
            "status": "pending", "pending": True,
            "best": {"title": "Provider title"}, "candidates": [],
        }
        local = {
            "best": {"title": "Local title", "artist": "Local artist", "album": "Local album"},
            "image_url": "cover/local?v=1", "lyrics": "[00:01.00]local",
        }
        result = merge_pending_projection(pending, local)
        self.assertEqual(result["best"]["title"], "Provider title")
        self.assertEqual(result["best"]["artist"], "Local artist")
        self.assertEqual(result["image_url"], "cover/local?v=1")
        self.assertEqual(result["lyrics"], "[00:01.00]local")
        self.assertEqual(result["candidates"], [{"title": "Provider title", "artist": "Local artist", "album": "Local album"}])

    def test_merge_pending_projection_does_not_mutate_inputs(self):
        pending = {"best": {}, "candidates": []}
        local = {"best": {"title": "Song"}}
        result = merge_pending_projection(pending, local)
        self.assertEqual(result["candidates"], [{"title": "Song"}])
        self.assertEqual(pending, {"best": {}, "candidates": []})
        self.assertEqual(local, {"best": {"title": "Song"}})



class MetadataRecoverySupplierTests(unittest.TestCase):
    """Pin who can supply the fields the recovery projections read.

    Two audit rounds called these reads dead because the scanner never writes
    them.  That half is true and is asserted below; the other half -- that
    nothing else can reach them -- was disproved by the legacy-cache
    reproduction, whose full chain is pinned in tests.test_library_cache.
    """

    def test_scanner_row_builders_never_supply_the_recovery_keys(self):
        metadata = library_metadata(
            "/music/01_Artist - Song.flac", {"title": "Song"}, "Album", "Music")
        stat = SimpleNamespace(st_mtime=12.9, st_mtime_ns=12900000000)
        audio = build_audio_item(
            "abc", metadata, ".flac", "audio/flac", False, 1234,
            {"duration": 42.5, "sample_rate": 96000}, "/music/song.flac", 10.75, stat)
        cue = build_cue_item(
            "cue-1", metadata, ".ape", "audio/ape", False, 99,
            {"sample_rate": 192000}, "/music/a.ape", "/music/a.cue", True,
            10.0, 35.5, 100.25, 12, 1234, 16)
        for label, row in (("metadata", metadata), ("audio", audio), ("cue", cue)):
            for key in _SUPPLIER_KEYS:
                self.assertNotIn(key, row, label)

    def test_feeding_public_rows_would_lose_both_recovery_fields(self):
        # The alternative proposed by the audit -- project first, read later --
        # is not a superset: the public row drops the lyric body outright and
        # re-synthesises the cover URL from the cover cache, so a legacy
        # value that is still valid would be replaced by a different one.
        legacy = {
            "id": "legacy-1", "path": "/music/song.flac", "title": "Legacy",
            "lyrics": "[00:01.00]cached body", "cover_url": "cover/legacy?v=1",
        }
        projected = public_library_item(legacy, {}, allow_cover_disk_lookup=False)
        self.assertNotIn("lyrics", projected)
        self.assertNotEqual(projected["cover_url"], "cover/legacy?v=1")
        self.assertEqual(local_cached_projection("legacy-1", legacy)["lyrics"],
                         "[00:01.00]cached body")
        self.assertNotIn("lyrics", local_cached_projection("legacy-1", projected))
        self.assertEqual(local_cached_projection("legacy-1", legacy)["image_url"],
                         "cover/legacy?v=1")
        self.assertEqual(
            merge_pending_projection({"pending": True}, local_cached_projection("legacy-1", legacy))["image_url"],
            "cover/legacy?v=1")

    def test_cold_start_track_projection_reads_the_raw_library_row(self):
        source = SERVER_SOURCE.read_text(encoding="utf-8")
        # The startup branch used to be spelled "elif not METADATA_SERVICE",
        # which reads like an unreachable tautology and was reported as a
        # permanently false branch.  It is a plain else now, and the input to
        # the projection is pinned to the un-projected library row.
        self.assertNotIn("elif not METADATA_SERVICE", source)
        start = source.index("# Read an already persisted projection")
        end = source.index('if not metadata_service_available(METADATA_SERVICE, "fetch"):')
        block = source[start:end]
        self.assertIn("else:", block)
        self.assertIn("local_item = find_library_item(self.server.config, track_id) or {}", block)
        self.assertIn("local_cached_projection(track_id, local_item)", block)
        self.assertIn("merge_pending_projection(cached_result, local_projection)", block)
        self.assertNotIn("public_library_item", block)
        self.assertEqual(
            source.count("local_item = find_library_item(self.server.config, track_id) or {}"), 5)

    def test_lyrics_startup_projection_reads_the_raw_library_row(self):
        source = SERVER_SOURCE.read_text(encoding="utf-8")
        start = source.index('if path == "/api/lyrics":')
        end = source.index("result = METADATA_SERVICE.lyrics(item_id, retry_failed=retry_failed)")
        block = source[start:end]
        self.assertIn("item = find_library_item(self.server.config, item_id)", block)
        self.assertIn("local = local_lyrics_projection(item)", block)
        # Only the startup branch may answer from the row: once the service
        # exists its own bounded local reader is authoritative.
        self.assertEqual(block.count("local_lyrics_projection("), 1)

if __name__ == "__main__":
    unittest.main()
