import os
import os
import sys
import tempfile
import time
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, "app/server")

from library import read_cover, read_id3, save_items_to_sqlite
from metadata_service import (
    MetadataProviders, MetadataService, _ape_existing_items, _write_ape_tags, _write_dsf_tags, _write_wav_tags,
    entity_key, normalize_release_date,
)


class MetadataServiceTests(unittest.TestCase):
    def _config(self, root, grace=7):
        music = os.path.join(root, "music")
        os.makedirs(music, exist_ok=True)
        return {
            "cache_dir": os.path.join(root, "cache"),
            "library_paths": [music],
            "metadata_enabled": True,
            "metadata_orphan_grace_days": grace,
        }

    @staticmethod
    def _item(item_id, path, title, track_no):
        return {
            "id": item_id,
            "path": path,
            "title": title,
            "artist": "Example Artist",
            "album": "Example Album",
            "album_artist": "Example Artist",
            "composer": "Example Composer",
            "genre": "Pop",
            "track_no": track_no,
            "format": "FLAC",
            "mime": "audio/flac",
            "duration": 180,
        }

    @staticmethod
    def _syncsafe(value):
        return bytes(((value >> 21) & 0x7F, (value >> 14) & 0x7F, (value >> 7) & 0x7F, value & 0x7F))

    def _write_dsf_fixture(self, path, image=b"\x89PNG\r\n\x1a\nfixture"):
        frame = b"TXXX" + (9).to_bytes(4, "big") + b"\0\0" + b"\x03keep\0yes"
        apic_body = b"\x03image/png\0\x03\0" + image
        frame += b"APIC" + len(apic_body).to_bytes(4, "big") + b"\0\0" + apic_body
        tag = b"ID3\x03\0\0" + self._syncsafe(len(frame)) + frame
        metadata_offset = 64
        body = bytearray(b"DSD " + (28).to_bytes(8, "little") + (metadata_offset + len(tag)).to_bytes(8, "little") + metadata_offset.to_bytes(8, "little"))
        body.extend(b"\xaa" * (metadata_offset - len(body)))
        body.extend(tag)
        with open(path, "wb") as handle:
            handle.write(body)

    def _write_ape_fixture(self, path):
        audio = b"MAC " + b"\x00" * 64
        value = b"keep-value"
        item = len(value).to_bytes(4, "little") + b"\0\0\0\0" + b"Custom\0" + value
        footer = b"APETAGEX" + (2000).to_bytes(4, "little") + (len(item) + 32).to_bytes(4, "little") + (1).to_bytes(4, "little") + b"\0\0\0\0" + b"\0" * 8
        with open(path, "wb") as handle:
            handle.write(audio + item + footer)

    def test_reconcile_deduplicates_shared_entities_and_persists_lyrics_jobs(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            items = [
                self._item("one", os.path.join(music, "one.flac"), "One", 1),
                self._item("two", os.path.join(music, "two.flac"), "Two", 2),
            ]
            save_items_to_sqlite(config, items, "first")
            service = MetadataService(config)

            service.reconcile()

            with service._connect() as conn:
                jobs = {row["job_type"]: row["count"] for row in conn.execute("SELECT job_type,COUNT(*) AS count FROM metadata_jobs GROUP BY job_type")}
            self.assertEqual(jobs, {"album": 1, "artist": 1, "composer": 1, "lyrics": 2, "track": 2})

    def test_group_enrichment_reads_sqlite_without_provider_request(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            service = MetadataService(config)
            key = entity_key("album", "Example Album", "Example Artist")
            with service._connect() as conn:
                conn.execute(
                    """INSERT INTO metadata_entities(
                        entity_type,entity_key,name,artist,release_date,artwork_id,source,provider_id,confidence,fetched_at,expires_at,orphaned_at,raw_json
                    ) VALUES ('album',?,?,?,?,?,'musicbrainz','album-id',0.98,1,9999999999,0,'{}')""",
                    (key, "Example Album", "Example Artist", "2026-08-04", "a" * 64),
                )
            payload = {"groups": [{"name": "Example Album", "artist": "Example Artist", "track_count": 2}]}

            result = service.enrich_groups("albums", payload)

            self.assertEqual(result["groups"][0]["release_date"], "2026-08-04")
            self.assertEqual(result["groups"][0]["metadata_source"], "musicbrainz")
            self.assertTrue(result["groups"][0]["image_url"].endswith("a" * 64))

    def test_album_enrichment_reuses_compatible_legacy_artist_key(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            legacy_key = entity_key("album", "Faded", "")
            with service._connect() as conn:
                conn.execute(
                    """INSERT INTO metadata_entities(
                        entity_type,entity_key,name,artist,release_date,artwork_id,source,provider_id,confidence,fetched_at,expires_at,orphaned_at,raw_json
                    ) VALUES ('album',?,?,?,?,?,'netease','album-id',0.8,1,9999999999,123,'{}')""",
                    (legacy_key, "Faded", "Alan Walker", "2015-12-04", "c" * 64),
                )
            payload = {"groups": [{"name": "Faded", "artist": "Alan Walker;Iselin Solheim"}]}

            result = service.enrich_groups("albums", payload)

            self.assertEqual(result["groups"][0]["metadata_source"], "netease")
            self.assertTrue(result["groups"][0]["image_url"].endswith("c" * 64))

    def test_album_enrichment_rejects_wrong_artist_legacy_key(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            legacy_key = entity_key("album", "Hello World", "")
            with service._connect() as conn:
                conn.execute(
                    """INSERT INTO metadata_entities(
                        entity_type,entity_key,name,artist,release_date,artwork_id,source,provider_id,confidence,fetched_at,expires_at,orphaned_at,raw_json
                    ) VALUES ('album',?,?,?,?,?,'netease','wrong-id',0.7,1,9999999999,0,'{}')""",
                    (legacy_key, "Hello World", "airubreathe", "2026-08-01", "d" * 64),
                )
            payload = {"groups": [{"name": "Hello World", "artist": "Alan Walker;Torine"}]}

            result = service.enrich_groups("albums", payload)

            self.assertNotIn("image_url", result["groups"][0])

    def test_lyrics_cache_miss_only_queues_background_work(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)

            with patch.object(service.providers, "lyrics") as provider:
                result = service.lyrics("one")

            self.assertTrue(result["pending"])
            provider.assert_not_called()
            with service._connect() as conn:
                row = conn.execute("SELECT status,priority FROM metadata_jobs WHERE job_key='lyrics:one'").fetchone()
            self.assertEqual(row["status"], "pending")
            self.assertEqual(row["priority"], 0)

    def test_current_track_prioritizes_lyrics_ahead_of_library_scan(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            service.reconcile()

            self.assertTrue(service.prioritize_track("one"))
            with service._connect() as conn:
                row = conn.execute("SELECT priority,status FROM metadata_jobs WHERE job_key='lyrics:one'").fetchone()
                album = conn.execute("SELECT priority,status FROM metadata_jobs WHERE job_type='album'").fetchone()
                tag = conn.execute("SELECT priority,status FROM metadata_jobs WHERE job_key='tag:one'").fetchone()
            self.assertEqual(row["priority"], 0)
            self.assertEqual(row["status"], "pending")
            self.assertEqual(album["priority"], 1)
            self.assertEqual(tag["priority"], 2)

    def test_track_match_is_auto_applied_only_when_unambiguous(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "Example Artist - One.flac"), "One", 1)
            item["album"] = "Unknown Album"
            item["metadata_source"] = {"title": "filename", "artist": "filename", "album": "unknown"}
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            candidate = {"title": "One", "artist": "Example Artist", "album": "Resolved Album", "album_artist": "Example Artist", "track_no": 1, "source": "netease", "provider_id": "1", "confidence": 0.97}

            service._store_track_match("one", [candidate])

            with service._connect() as conn:
                row = conn.execute("SELECT status FROM metadata_track_matches WHERE track_id='one'").fetchone()
                tag = conn.execute("SELECT status FROM metadata_jobs WHERE job_key='tag:one'").fetchone()
                fields = service._track_match_fields(conn, "one")
            self.assertEqual(row["status"], "auto")
            self.assertEqual(tag["status"], "pending")
            self.assertEqual(fields["album"], "Resolved Album")

    def test_track_match_requires_confirmation_when_candidates_are_close(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            first = {"title": "One", "artist": "Artist", "album": "Album A", "source": "qq", "confidence": 0.93}
            second = {"title": "One", "artist": "Artist", "album": "Album B", "source": "netease", "confidence": 0.90}

            service._store_track_match("missing-track", [first, second])

            with service._connect() as conn:
                row = conn.execute("SELECT status FROM metadata_track_matches WHERE track_id='missing-track'").fetchone()
                self.assertEqual(row["status"], "review")
                self.assertEqual(service._track_match_fields(conn, "missing-track"), {})
            self.assertTrue(service.apply_track_match("missing-track", 1))
            with service._connect() as conn:
                self.assertEqual(service._track_match_fields(conn, "missing-track")["album"], "Album B")

    def test_track_match_rejects_an_index_not_owned_by_the_track(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service._store_track_match("missing-track", [{"title": "One", "source": "qq", "confidence": 0.93}])

            self.assertFalse(service.apply_track_match("missing-track", 1))
            with service._connect() as conn:
                row = conn.execute("SELECT status FROM metadata_track_matches WHERE track_id='missing-track'").fetchone()
            self.assertEqual(row["status"], "auto")

    def test_track_candidates_rank_recording_and_keep_provider_identity(self):
        providers = MetadataProviders({})
        track = {"title": "One", "artist": "Example Artist", "duration": 180}
        netease = {"result": {"songs": [{
            "id": 88, "name": "One", "artists": [{"name": "Example Artist"}], "duration": 180000,
            "album": {"name": "Resolved Album", "artists": [{"name": "Example Artist"}], "publishTime": 1700000000000, "picUrl": "https://example.test/cover.jpg"},
        }]}}
        with patch.object(providers, "_json", return_value=netease), \
             patch.object(providers, "_qq_songs", return_value=[]), \
             patch.object(providers, "_kugou_songs", return_value=[]), \
             patch.object(providers, "_migu_songs", return_value=[]), \
             patch.object(providers, "_joox_songs", return_value=[]), \
             patch.object(providers, "_qianqian_songs", return_value=[]):
            candidates = providers.track_candidates(track)
        self.assertEqual(candidates[0]["source"], "netease")
        self.assertEqual(candidates[0]["album"], "Resolved Album")
        self.assertEqual(candidates[0]["provider_id"], "88")
        self.assertGreaterEqual(candidates[0]["confidence"], 0.9)

    def test_priority_worker_claims_only_current_track_lyrics(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                service._upsert_job(conn, "album:ordinary", "album", "ordinary", {}, 10)
                service._upsert_job(conn, "lyrics:ordinary", "lyrics", "ordinary", {}, 100)
                service._upsert_job(conn, "lyrics:current", "lyrics", "current", {}, 0)

            job = service._claim_job(priority_max=0, lyrics_only=True)

            self.assertEqual(job["job_key"], "lyrics:current")
            with service._connect() as conn:
                states = {row["job_key"]: row["status"] for row in conn.execute("SELECT job_key,status FROM metadata_jobs")}
            self.assertEqual(states["lyrics:current"], "running")
            self.assertEqual(states["album:ordinary"], "pending")
            self.assertEqual(states["lyrics:ordinary"], "pending")

    def test_metadata_queue_is_bounded_and_current_track_can_evict_ordinary_work(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with patch("metadata_service.bounded_int", return_value=2):
                with service._connect() as conn:
                    self.assertTrue(service._upsert_job(conn, "album:one", "album", "one", {}, 10))
                    self.assertTrue(service._upsert_job(conn, "album:two", "album", "two", {}, 20))
                    self.assertFalse(service._upsert_job(conn, "album:three", "album", "three", {}, 30))
                    self.assertTrue(service._upsert_job(conn, "lyrics:current", "lyrics", "current", {}, 0))
                    rows = {
                        row["job_key"]: row["priority"]
                        for row in conn.execute("SELECT job_key,priority FROM metadata_jobs")
                    }

            self.assertEqual(rows, {"album:one": 10, "lyrics:current": 0})
            self.assertEqual(service.dropped_jobs, 2)

    def test_running_metadata_job_is_never_evicted(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with patch("metadata_service.bounded_int", return_value=1):
                with service._connect() as conn:
                    service._upsert_job(conn, "album:running", "album", "running", {}, 100)
                    conn.execute("UPDATE metadata_jobs SET status='running' WHERE job_key='album:running'")
                    self.assertTrue(service._upsert_job(conn, "lyrics:current", "lyrics", "current", {}, 0))
                    states = {
                        row["job_key"]: row["status"]
                        for row in conn.execute("SELECT job_key,status FROM metadata_jobs")
                    }
            self.assertEqual(states, {"album:running": "running", "lyrics:current": "pending"})

    def test_current_track_priority_survives_reconcile_and_previous_track_is_demoted(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            first = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            second = self._item("two", os.path.join(music, "two.flac"), "Two", 2)
            save_items_to_sqlite(config, [first, second], "first")
            service = MetadataService(config)
            service.reconcile()
            service.prioritize_track("one")
            service.reconcile()
            service.prioritize_track("two")
            with service._connect() as conn:
                first_priority = conn.execute("SELECT priority FROM metadata_jobs WHERE job_key='lyrics:one'").fetchone()["priority"]
                second_priority = conn.execute("SELECT priority FROM metadata_jobs WHERE job_key='lyrics:two'").fetchone()["priority"]
            self.assertEqual(first_priority, 100)
            self.assertEqual(second_priority, 0)

    def test_lyrics_and_album_artwork_queue_one_tag_write_per_track(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)

            service._store_lyrics("one", {"lyrics": "line", "source": "test"})
            service._store_lyrics("one", {"lyrics": "line two", "source": "test"})
            with service._connect() as conn:
                row = conn.execute("SELECT job_type,priority,COUNT(*) AS count FROM metadata_jobs WHERE job_key='tag:one'").fetchone()
            self.assertEqual(row["job_type"], "tag_write")
            self.assertEqual(row["priority"], 200)
            self.assertEqual(row["count"], 1)

    def test_track_artwork_update_preserves_existing_lyrics(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.ape"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            service._store_lyrics("one", {"lyrics": "keep lyrics", "source": "test"})
            service._store_lyrics("one", {"image_url": "", "source": "test"})
            with service._connect() as conn:
                row = conn.execute("SELECT lyrics FROM metadata_tracks WHERE track_id='one'").fetchone()
            self.assertEqual(row["lyrics"], "keep lyrics")

    def test_album_artwork_uses_index_artist_when_track_album_artist_is_missing(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            item["album_artist"] = ""
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            os.makedirs(service.artwork_dir, exist_ok=True)
            asset_id = "a" * 64
            artwork_path = os.path.join(service.artwork_dir, asset_id + ".jpg")
            with open(artwork_path, "wb") as handle:
                handle.write(b"image")
            key = entity_key("album", "Example Album", "Example Artist")
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_assets(id,path,mime,size) VALUES (?,?,?,?)",
                    (asset_id, artwork_path, "image/jpeg", 5),
                )
                conn.execute(
                    """INSERT INTO metadata_entities(
                        entity_type,entity_key,name,artist,artwork_id,orphaned_at
                    ) VALUES ('album',?,?,?,?,0)""",
                    (key, "Example Album", "Example Artist", asset_id),
                )

            data = service._tag_data("one")

            self.assertEqual(data["artwork_path"], artwork_path)
            self.assertEqual(data["artwork_mime"], "image/jpeg")

    def test_track_artwork_falls_back_when_album_is_unclassified(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.ape"), "One", 1)
            item["album"] = "未分类"
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            os.makedirs(service.artwork_dir, exist_ok=True)
            asset_id = "b" * 64
            artwork_path = os.path.join(service.artwork_dir, asset_id + ".jpg")
            with open(artwork_path, "wb") as handle:
                handle.write(b"image")
            with service._connect() as conn:
                conn.execute("INSERT INTO metadata_assets(id,path,mime,size) VALUES (?,?,?,?)", (asset_id, artwork_path, "image/jpeg", 5))
                conn.execute("INSERT INTO metadata_tracks(track_id,artwork_id) VALUES (?,?)", ("one", asset_id))
            data = service._tag_data("one")
            self.assertEqual(data["artwork_path"], artwork_path)
            self.assertEqual(data["artwork_mime"], "image/jpeg")

    def test_album_artwork_queues_tracks_when_album_artist_is_missing(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            first = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            second = self._item("two", os.path.join(music, "two.flac"), "Two", 2)
            first["album_artist"] = ""
            second["album_artist"] = ""
            save_items_to_sqlite(config, [first, second], "first")
            service = MetadataService(config)

            with service._connect() as conn:
                service._queue_album_tag_writes(conn, "Example Album", "Example Artist")
                jobs = {
                    row["entity_key"]
                    for row in conn.execute("SELECT entity_key FROM metadata_jobs WHERE job_type='tag_write'")
                }

            self.assertEqual(jobs, {"one", "two"})

    def test_tag_write_backfill_requeues_tracks_with_cached_album_artwork_once(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            item["album_artist"] = ""
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            key = entity_key("album", "Example Album", "Example Artist")
            with service._connect() as conn:
                conn.execute(
                    """INSERT INTO metadata_entities(
                        entity_type,entity_key,name,artist,artwork_id,orphaned_at
                    ) VALUES ('album',?,?,?,?,0)""",
                    (key, "Example Album", "Example Artist", "a" * 64),
                )
                conn.execute("DELETE FROM metadata_jobs WHERE job_type='tag_write'")
                conn.execute(
                    "DELETE FROM metadata_state WHERE key='tag_write_backfill_version'"
                )

            with service._connect() as conn:
                job = conn.execute(
                    "SELECT status,entity_key FROM metadata_jobs WHERE job_type='tag_write'"
                ).fetchone()
                version = conn.execute(
                    "SELECT value FROM metadata_state WHERE key='tag_write_backfill_version'"
                ).fetchone()["value"]
                conn.execute("UPDATE metadata_jobs SET status='done' WHERE job_type='tag_write'")

            with service._connect() as conn:
                status_after_second_open = conn.execute(
                    "SELECT status FROM metadata_jobs WHERE job_type='tag_write'"
                ).fetchone()["status"]

            self.assertEqual((job["status"], job["entity_key"]), ("pending", "one"))
            self.assertEqual(version, "1")
            self.assertEqual(status_after_second_open, "done")

    def test_dsf_tag_write_preserves_dsd_payload_and_embedded_cover(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "one.dsf")
            temporary = source + ".fnaudio-tagging.dsf"
            self._write_dsf_fixture(source)
            with open(source, "rb") as handle:
                original = handle.read()
            _write_dsf_tags(source, temporary, {"title": "Written", "artist": "Artist", "lyrics": "line"})
            from library import read_id3, read_id3_cover
            tags = read_id3(temporary)
            mime, cover = read_id3_cover(temporary)
            with open(temporary, "rb") as handle:
                written = handle.read()
            self.assertEqual(tags["title"], "Written")
            self.assertEqual(tags["artist"], "Artist")
            self.assertEqual((mime, cover), ("image/png", b"\x89PNG\r\n\x1a\nfixture"))
            self.assertEqual(original[28:64], written[28:64])
            self.assertEqual(int.from_bytes(written[12:20], "little"), len(written))

    def test_ape_tag_write_preserves_unmanaged_items(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "one.ape")
            temporary = source + ".tmp.ape"
            self._write_ape_fixture(source)
            _write_ape_tags(source, temporary, {"title": "Written", "artist": "Artist", "lyrics": "line"})
            _audio, items = _ape_existing_items(temporary)
            tags = {key: value.decode("utf-8") for key, _flags, value in items}
            self.assertEqual(tags["Title"], "Written")
            self.assertEqual(tags["Artist"], "Artist")
            self.assertEqual(tags["Custom"], "keep-value")

    def test_ape_cover_written_by_tag_service_is_read_by_cover_endpoint(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "one.ape")
            temporary = source + ".tmp.ape"
            self._write_ape_fixture(source)
            image = b"\xff\xd8\xff\xd9"
            artwork = os.path.join(root, "cover.jpg")
            with open(artwork, "wb") as handle:
                handle.write(image)
            _write_ape_tags(source, temporary, {"title": "Written", "artwork_path": artwork})
            mime, body = read_cover(temporary)
            self.assertEqual((mime, body), ("image/jpeg", image))

    def test_wav_id3_cover_write_is_read_without_remuxing_audio(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "one.wav")
            temporary = source + ".tmp.wav"
            fmt = b"\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00"
            payload = b"WAVE" + b"fmt " + len(fmt).to_bytes(4, "little") + fmt + b"data" + (4).to_bytes(4, "little") + b"\x00\x00\x00\x00"
            with open(source, "wb") as handle:
                handle.write(b"RIFF" + len(payload).to_bytes(4, "little") + payload)
            image = b"\xff\xd8\xff\xd9"
            artwork = os.path.join(root, "cover.jpg")
            with open(artwork, "wb") as handle:
                handle.write(image)
            _write_wav_tags(source, temporary, {"title": "Written", "artwork_path": artwork})
            self.assertEqual(read_id3(temporary)["title"], "Written")
            self.assertEqual(read_cover(temporary), ("image/jpeg", image))

    def test_cue_track_writes_only_shared_ape_cover(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "album.ape")
            self._write_ape_fixture(source)
            artwork = os.path.join(root, "cover.jpg")
            image = b"\xff\xd8\xff\xd9"
            with open(artwork, "wb") as handle:
                handle.write(image)
            service = MetadataService({"cache_dir": os.path.join(root, "cache")})
            cue_data = {
                "path": source,
                "cue_track": True,
                "title": "Virtual Track",
                "artist": "Virtual Artist",
                "lyrics": "virtual lyrics",
                "artwork_path": artwork,
                "artwork_mime": "image/jpeg",
            }
            with patch.object(service, "_tag_data", return_value=cue_data):
                self.assertTrue(service._write_track_tags("cue-item"))
            _audio, items = _ape_existing_items(source)
            tags = {key: value for key, _flags, value in items}
            self.assertEqual(tags["Custom"], b"keep-value")
            self.assertNotIn("Title", tags)
            self.assertNotIn("Lyrics", tags)
            self.assertIn("Cover Art (Front)", tags)
            self.assertEqual(read_cover(source), ("image/jpeg", image))

    def test_tag_write_replaces_source_only_after_successful_temp_output(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            path = os.path.join(music, "one.mp3")
            with open(path, "wb") as fh:
                fh.write(b"original")
            item = self._item("one", path, "One", 1)
            item.update({"format": "MP3", "mime": "audio/mpeg"})
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            service._store_lyrics("one", {"lyrics": "line", "source": "test"})
            captured_command = []

            def fake_run(command, **_kwargs):
                captured_command.extend(command)
                with open(command[-1], "wb") as fh:
                    fh.write(b"tagged")
                return type("Result", (), {"returncode": 0, "stderr": b""})()

            with patch("metadata_service.find_ffmpeg", return_value="ffmpeg"), patch("metadata_service.subprocess.run", side_effect=fake_run):
                self.assertTrue(service._write_track_tags("one"))
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), b"tagged")
            self.assertIn("-map", captured_command)
            self.assertIn("0:a?", captured_command)
            self.assertIn("0:v?", captured_command)
            mappings = [captured_command[index + 1] for index, value in enumerate(captured_command[:-1]) if value == "-map"]
            self.assertNotIn("0", mappings)

    def test_m4a_tag_write_omits_incompatible_text_and_data_streams(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            path = os.path.join(music, "one.m4a")
            with open(path, "wb") as fh:
                fh.write(b"original")
            item = self._item("one", path, "One", 1)
            item.update({"format": "M4A", "mime": "audio/mp4"})
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            service._store_lyrics("one", {"lyrics": "line", "source": "test"})
            captured_command = []

            def fake_run(command, **_kwargs):
                captured_command.extend(command)
                with open(command[-1], "wb") as fh:
                    fh.write(b"tagged")
                return type("Result", (), {"returncode": 0, "stderr": b""})()

            with patch("metadata_service.find_ffmpeg", return_value="ffmpeg"), patch("metadata_service.subprocess.run", side_effect=fake_run):
                self.assertTrue(service._write_track_tags("one"))

            mappings = [captured_command[index + 1] for index, value in enumerate(captured_command[:-1]) if value == "-map"]
            self.assertEqual(mappings, ["0:a?", "0:v?"])
            self.assertNotIn("0", mappings)

    def test_tag_write_failure_never_replaces_source(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            path = os.path.join(music, "one.mp3")
            with open(path, "wb") as fh:
                fh.write(b"original")
            item = self._item("one", path, "One", 1)
            item.update({"format": "MP3", "mime": "audio/mpeg"})
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            service._store_lyrics("one", {"lyrics": "line", "source": "test"})

            failed = type("Result", (), {"returncode": 1, "stderr": b"write failed"})()
            with patch("metadata_service.find_ffmpeg", return_value="ffmpeg"), patch("metadata_service.subprocess.run", return_value=failed):
                with self.assertRaisesRegex(RuntimeError, "tag write failed"):
                    service._write_track_tags("one")
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), b"original")

    def test_retry_failed_tag_writes_only_requeues_terminal_tag_failures(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                service._upsert_job(conn, "tag:failed", "tag_write", "failed", {}, 200)
                service._upsert_job(conn, "tag:pending", "tag_write", "pending", {}, 200)
                service._upsert_job(conn, "lyrics:failed", "lyrics", "failed", {}, 100)
                conn.execute("UPDATE metadata_jobs SET status='failed',attempts=5,last_error='ffmpeg failed' WHERE job_key IN ('tag:failed','lyrics:failed')")
            self.assertEqual(service.retry_failed_tag_writes(), 1)
            with service._connect() as conn:
                rows = {row["job_key"]: (row["status"], row["attempts"], row["last_error"]) for row in conn.execute("SELECT job_key,status,attempts,last_error FROM metadata_jobs")}
            self.assertEqual(rows["tag:failed"], ("pending", 0, ""))
            self.assertEqual(rows["tag:pending"][0], "pending")
            self.assertEqual(rows["lyrics:failed"][0], "failed")

    def test_status_exposes_tag_job_without_media_path(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "Visible Title", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            with service._connect() as conn:
                service._upsert_job(conn, "tag:one", "tag_write", "one", {}, 200)
                conn.execute("UPDATE metadata_jobs SET status='failed',attempts=5,last_error='write failed' WHERE job_key='tag:one'")
            job = service.status()["tag_jobs"][0]
            self.assertEqual(job["title"], "Visible Title")
            self.assertEqual(job["status"], "failed")
            self.assertNotIn("path", job)

    def test_shared_entity_survives_until_last_track_is_deleted(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root, grace=0)
            music = config["library_paths"][0]
            first = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            second = self._item("two", os.path.join(music, "two.flac"), "Two", 2)
            save_items_to_sqlite(config, [first, second], "first")
            service = MetadataService(config)
            service.reconcile()
            key = entity_key("album", "Example Album", "Example Artist")
            service._store_entity("album", key, {"name": "Example Album", "artist": "Example Artist"}, {"artist": "Example Artist", "source": "musicbrainz", "confidence": 1})

            save_items_to_sqlite(config, [first], "second")
            service.reconcile()
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_entities WHERE entity_type='album' AND entity_key=?", (key,)).fetchone()[0], 1)

            save_items_to_sqlite(config, [], "third")
            service.reconcile()
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_entities WHERE entity_type='album' AND entity_key=?", (key,)).fetchone()[0], 0)

    def test_reconcile_cancels_jobs_that_no_longer_have_library_references(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            service.reconcile()
            with service._connect() as conn:
                service._upsert_job(conn, "album:removed", "album", "removed", {"name": "Removed"}, 10)
                service._upsert_job(conn, "lyrics:removed", "lyrics", "removed", {"title": "Removed"}, 100)

            service.reconcile(force=True)

            with service._connect() as conn:
                self.assertIsNone(conn.execute("SELECT 1 FROM metadata_jobs WHERE job_key='album:removed'").fetchone())
                self.assertIsNone(conn.execute("SELECT 1 FROM metadata_jobs WHERE job_key='lyrics:removed'").fetchone())
                self.assertIsNotNone(conn.execute("SELECT 1 FROM metadata_jobs WHERE job_key='lyrics:one'").fetchone())

    def test_start_recovers_interrupted_jobs(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                service._upsert_job(conn, "album:example", "album", "example", {"name": "Example"}, 10)
                conn.execute("UPDATE metadata_jobs SET status='running' WHERE job_key='album:example'")

            with patch("metadata_service.threading.Thread.start"):
                service.start()

            with service._connect() as conn:
                status = conn.execute("SELECT status FROM metadata_jobs WHERE job_key='album:example'").fetchone()["status"]
            self.assertEqual(status, "pending")

    def test_expired_negative_entity_is_requeued(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            key = entity_key("album", "Missing Album", "Missing Artist")
            service._store_entity("album", key, {"name": "Missing Album", "artist": "Missing Artist"}, None)
            with service._connect() as conn:
                service._upsert_job(conn, "album:" + key, "album", key, {"name": "Missing Album", "artist": "Missing Artist"}, 10)
                conn.execute("UPDATE metadata_entities SET expires_at=1 WHERE entity_type='album' AND entity_key=?", (key,))
                conn.execute("UPDATE metadata_jobs SET status='no_match' WHERE job_key=?", ("album:" + key,))
                service._requeue_expired(conn, int(time.time()))

            with service._connect() as conn:
                status = conn.execute("SELECT status FROM metadata_jobs WHERE job_key=?", ("album:" + key,)).fetchone()["status"]
            self.assertEqual(status, "pending")

    def test_artwork_is_removed_only_after_last_entity_reference(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root, grace=0))
            os.makedirs(service.artwork_dir, exist_ok=True)
            asset_id = "b" * 64
            asset_path = os.path.join(service.artwork_dir, asset_id + ".jpg")
            with open(asset_path, "wb") as fh:
                fh.write(b"image")
            now = int(time.time())
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_assets(id,path,mime,size,source_url,fetched_at,last_accessed) VALUES (?,?,?,?,?,?,?)",
                    (asset_id, asset_path, "image/jpeg", 5, "https://example.test/image.jpg", now, now),
                )
                for key, orphaned_at in (("first", now), ("second", 0)):
                    conn.execute(
                        """INSERT INTO metadata_entities(
                            entity_type,entity_key,name,artist,artwork_id,fetched_at,expires_at,orphaned_at
                        ) VALUES ('artist',?,?,?, ?,?,?,?)""",
                        (key, key, key, asset_id, now, now + 60, orphaned_at),
                    )
                service._cleanup_orphans(conn, now)

            self.assertTrue(os.path.isfile(asset_path))
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_assets WHERE id=?", (asset_id,)).fetchone()[0], 1)
                conn.execute("UPDATE metadata_entities SET orphaned_at=? WHERE entity_key='second'", (now,))
                service._cleanup_orphans(conn, now)

            self.assertFalse(os.path.exists(asset_path))
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_assets WHERE id=?", (asset_id,)).fetchone()[0], 0)

    def test_artwork_pressure_clears_reference_and_allows_refetch(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            os.makedirs(service.artwork_dir, exist_ok=True)
            asset_id = "e" * 64
            asset_path = os.path.join(service.artwork_dir, asset_id + ".jpg")
            with open(asset_path, "wb") as fh:
                fh.write(b"old-image")
            now = int(time.time())
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_assets(id,path,mime,size,source_url,fetched_at,last_accessed) VALUES (?,?,?,?,?,?,?)",
                    (asset_id, asset_path, "image/jpeg", 9, "https://example.test/old.jpg", now, 1),
                )
                conn.execute(
                    """INSERT INTO metadata_entities(
                        entity_type,entity_key,name,artwork_id,fetched_at,expires_at
                    ) VALUES ('album','album-key','Album',?,?,?)""",
                    (asset_id, now, now + 3600),
                )
                with patch("metadata_service.bounded_int", side_effect=lambda _c, key, *_a: 1 if key == "metadata_cache_max_bytes" else 0), patch(
                    "metadata_service.disk_has_reserve", return_value=True
                ):
                    self.assertEqual(service._prune_artwork_cache(conn, incoming_bytes=1), 1)
                entity = conn.execute(
                    "SELECT artwork_id,expires_at FROM metadata_entities WHERE entity_key='album-key'"
                ).fetchone()

            self.assertFalse(os.path.exists(asset_path))
            self.assertEqual(entity["artwork_id"], "")
            self.assertEqual(entity["expires_at"], 0)

    def test_status_reports_bounded_pending_and_artwork_usage(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            config["metadata_max_pending_jobs"] = 100
            service = MetadataService(config)
            with service._connect() as conn:
                service._upsert_job(conn, "album:one", "album", "one", {}, 10)
            status = service.status()
            self.assertEqual(status["pending"], 1)
            self.assertEqual(status["pending_limit"], 100)
            self.assertFalse(status["saturated"])
            self.assertEqual(status["artwork_bytes"], 0)

    def test_tag_writes_are_claimed_by_the_dedicated_writer_only(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                service._upsert_job(conn, "tag:one", "tag_write", "one", {}, 200)
                service._upsert_job(conn, "lyrics:one", "lyrics", "one", {}, 100)
            self.assertEqual(service._claim_job(exclude_tag_writes=True)["job_type"], "lyrics")
            self.assertEqual(service._claim_job(tag_writes_only=True)["job_type"], "tag_write")

    def test_background_tag_write_is_debounced_to_merge_artwork_and_lyrics(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                service._queue_tag_write(conn, "one")
                row = conn.execute("SELECT next_attempt_at FROM metadata_jobs WHERE job_key='tag:one'").fetchone()
            self.assertGreaterEqual(int(row["next_attempt_at"]), int(time.time()) + 8)

    def test_tag_writer_does_not_strand_claimed_job_while_pacing(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            config["metadata_tag_idle_interval_ms"] = 10000
            service = MetadataService(config)
            with service._connect() as conn:
                service._upsert_job(conn, "tag:one", "tag_write", "one", {}, 200)
            service.last_tag_write_at = time.monotonic()
            worker = threading.Thread(target=service._run_tag_writer, daemon=True)
            worker.start()
            time.sleep(0.05)
            service.stop_event.set()
            worker.join(timeout=1)
            with service._connect() as conn:
                status = conn.execute("SELECT status FROM metadata_jobs WHERE job_key='tag:one'").fetchone()[0]
            self.assertEqual(status, "pending")

    def test_start_recovers_interrupted_running_jobs(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                service._upsert_job(conn, "tag:one", "tag_write", "one", {}, 200)
                conn.execute("UPDATE metadata_jobs SET status='running'")
            with patch.object(threading.Thread, "start"), patch.object(threading.Thread, "join"):
                service.start()
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT status FROM metadata_jobs WHERE job_key='tag:one'").fetchone()[0], "pending")

    def test_status_exposes_no_provider_credentials(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            status = MetadataService(config).status()
            self.assertNotIn("spotify_client_id", status)
            self.assertNotIn("spotify_client_secret", status)
            self.assertNotIn("spotify_configured", status)

    def test_provider_routing_prefers_musicbrainz_for_international_album(self):
        providers = MetadataProviders({})
        musicbrainz = {"name": "Album", "artist": "Artist", "source": "musicbrainz"}
        with patch.object(providers, "musicbrainz_album", return_value=musicbrainz) as musicbrainz_lookup, patch.object(providers, "netease_album") as netease_lookup:
            result = providers.album("Album", "Artist")
        self.assertEqual(result["source"], "musicbrainz")
        musicbrainz_lookup.assert_called_once()
        netease_lookup.assert_not_called()

    def test_provider_routing_prefers_netease_for_chinese_album(self):
        providers = MetadataProviders({})
        netease = {"name": "专辑", "artist": "歌手", "source": "netease"}
        with patch.object(providers, "netease_album", return_value=netease) as netease_lookup, patch.object(providers, "qq_album") as qq_lookup:
            result = providers.album("专辑", "歌手")
        self.assertEqual(result["source"], "netease")
        netease_lookup.assert_called_once()
        qq_lookup.assert_not_called()

    def test_migu_lyrics_fallback_uses_scored_song_and_returns_lrc(self):
        providers = MetadataProviders({})

        def fake_json(url, _headers=None, _data=None, _timeout=10):
            if "search_all.do" in url:
                return {"songResultData": {"result": [{"contentId": "123", "name": "Song", "singer": "Artist"}]}}
            if "resourceinfo.do" in url:
                return {"resource": [{"lrcUrl": "https://lyrics.example/song.lrc"}]}
            self.fail("unexpected URL: %s" % url)

        with patch.object(providers, "_json", side_effect=fake_json), patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = b"[00:01.00]first"
            result = providers.migu_lyrics({"title": "Song", "artist": "Artist"})

        self.assertEqual(result["source"], "migu")
        self.assertEqual(result["provider_id"], "123")
        self.assertEqual(result["lyrics"], "[00:01.00]first")

    def test_migu_album_uses_search_cover_metadata(self):
        providers = MetadataProviders({})
        with patch.object(providers, "_migu_songs", return_value=[{
            "albums": [{"id": "album-id", "name": "Album"}], "singer": "Artist", "imgItems": [{"img": "//img.example/cover.jpg"}],
        }]):
            result = providers.migu_album("Album", "Artist")

        self.assertEqual(result["source"], "migu")
        self.assertEqual(result["image_url"], "https://img.example/cover.jpg")
        self.assertEqual(result["provider_id"], "album-id")

    def test_kugou_album_uses_union_cover_from_music_lib_response_shape(self):
        providers = MetadataProviders({})
        with patch.object(providers, "_kugou_songs", return_value=[{
            "AlbumName": "Album", "SingerName": "Artist", "AlbumID": "album-id", "PublishDate": "2025-01-01",
            "trans_param": {"union_cover": "https://img.example/{size}/cover.jpg"},
        }]):
            result = providers.kugou_album("Album", "Artist")

        self.assertEqual(result["source"], "kugou")
        self.assertEqual(result["image_url"], "https://img.example/500/cover.jpg")
        self.assertEqual(result["release_date"], "2025-01-01")

    def test_provider_score_penalizes_same_title_with_wrong_artist(self):
        from metadata_service import provider_score

        compatible = provider_score("Hello World", "Hello World", "Alan Walker", "Alan Walker;Torine")
        incompatible = provider_score("Hello World", "Hello World", "airubreathe", "Alan Walker;Torine")

        self.assertGreaterEqual(compatible, 0.55)
        self.assertLess(incompatible, 0.55)

    def test_release_timestamp_is_normalized(self):
        self.assertEqual(normalize_release_date("1623340800"), "2021-06-11")
        self.assertEqual(normalize_release_date("2026-08-04"), "2026-08-04")


if __name__ == "__main__":
    unittest.main()
