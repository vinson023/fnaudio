import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, "app/server")

from library import save_items_to_sqlite
from metadata_service import MetadataProviders, MetadataService, entity_key, normalize_release_date


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
            self.assertEqual(jobs, {"album": 1, "artist": 1, "composer": 1, "lyrics": 2})

    def test_group_enrichment_reads_sqlite_without_provider_request(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            service = MetadataService(config)
            key = entity_key("album", "Example Album", "Example Artist")
            with service._connect() as conn:
                conn.execute(
                    """INSERT INTO metadata_entities(
                        entity_type,entity_key,name,artist,release_date,artwork_id,source,provider_id,confidence,fetched_at,expires_at,orphaned_at,raw_json
                    ) VALUES ('album',?,?,?,?,?,'spotify','album-id',0.98,1,9999999999,0,'{}')""",
                    (key, "Example Album", "Example Artist", "2026-08-04", "a" * 64),
                )
            payload = {"groups": [{"name": "Example Album", "artist": "Example Artist", "track_count": 2}]}

            result = service.enrich_groups("albums", payload)

            self.assertEqual(result["groups"][0]["release_date"], "2026-08-04")
            self.assertEqual(result["groups"][0]["metadata_source"], "spotify")
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
            self.assertEqual(row["priority"], 5)

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
            service._store_entity("album", key, {"name": "Example Album", "artist": "Example Artist"}, {"artist": "Example Artist", "source": "spotify", "confidence": 1})

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

    def test_status_never_returns_spotify_secret(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            config.update({"spotify_client_id": "client-id", "spotify_client_secret": "private-secret"})
            status = MetadataService(config).status()
            self.assertEqual(status["spotify_client_id"], "client-id")
            self.assertTrue(status["spotify_configured"])
            self.assertNotIn("spotify_client_secret", status)
            self.assertNotIn("private-secret", repr(status))

    def test_provider_routing_prefers_spotify_for_international_album(self):
        providers = MetadataProviders({"spotify_client_id": "id", "spotify_client_secret": "secret"})
        spotify = {"name": "Album", "artist": "Artist", "source": "spotify"}
        with patch.object(providers, "spotify_album", return_value=spotify) as spotify_lookup, patch.object(providers, "musicbrainz_album") as musicbrainz_lookup:
            result = providers.album("Album", "Artist")
        self.assertEqual(result["source"], "spotify")
        spotify_lookup.assert_called_once()
        musicbrainz_lookup.assert_not_called()

    def test_provider_routing_prefers_netease_for_chinese_album(self):
        providers = MetadataProviders({})
        netease = {"name": "专辑", "artist": "歌手", "source": "netease"}
        with patch.object(providers, "netease_album", return_value=netease) as netease_lookup, patch.object(providers, "qq_album") as qq_lookup:
            result = providers.album("专辑", "歌手")
        self.assertEqual(result["source"], "netease")
        netease_lookup.assert_called_once()
        qq_lookup.assert_not_called()

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
