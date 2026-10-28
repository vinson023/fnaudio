"""Exercise the real service boundary, not a permissive HTTP test double."""
import threading
import os
import hashlib
import io
import tempfile
import unittest
from contextlib import contextmanager
from email.message import Message
from unittest.mock import patch

from metadata_service import MetadataProviders, MetadataService, entity_key
from resource_limits import ConcurrencyGate, ResourceLimitError
from library import read_cover, read_id3, save_items_to_sqlite
from library_presentation import public_library_item


class InteractiveSearchTests(unittest.TestCase):
    def test_lyrics_cover_fallback_preserves_orphaned_lyrics(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            service._store_lyrics("t1", {"lyrics": "cached lyrics", "source": "original"})
            with service._connect() as conn:
                conn.execute("UPDATE metadata_tracks SET orphaned_at=1 WHERE track_id='t1'")
            with patch.object(service, "_download_artwork", return_value="a" * 64):
                service._store_lyrics("t1", self.candidate("fallback"))
            with service._connect() as conn:
                row = conn.execute("SELECT lyrics,artwork_id,orphaned_at FROM metadata_tracks WHERE track_id='t1'").fetchone()
            self.assertEqual(tuple(row), ("cached lyrics", "a" * 64, 0))

    def test_artwork_commit_preserves_concurrent_lyrics_and_first_cover(self):
        for field, value in (("lyrics", "new lyrics"), ("artwork_id", "b" * 64)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as root:
                service = MetadataService({"cache_dir": root, "metadata_tag_write_enabled": True})
                service._store_lyrics("t1", {"lyrics": "cached lyrics"})
                original_connect = service._connect
                armed = True

                class ConnectionProxy:
                    def __init__(self, connection):
                        self.connection = connection

                    def execute(self, sql, parameters=()):
                        nonlocal armed
                        if armed and sql.lstrip().startswith("INSERT") and "metadata_tracks(" in sql:
                            armed = False
                            with original_connect() as other:
                                other.execute("UPDATE metadata_tracks SET " + field + "=? WHERE track_id='t1'", (value,))
                        return self.connection.execute(sql, parameters)

                    def __getattr__(self, name):
                        return getattr(self.connection, name)

                @contextmanager
                def interleaved_connect():
                    with original_connect() as connection:
                        yield ConnectionProxy(connection)

                with patch.object(service, "_connect", side_effect=interleaved_connect), \
                     patch.object(service, "_download_artwork", return_value="a" * 64):
                    stored = service._store_track_artwork("t1", self.candidate("fallback"))
                self.assertFalse(armed)
                self.assertEqual(stored, field == "lyrics")
                with service._connect() as conn:
                    row = conn.execute("SELECT lyrics,artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone()
                expected = ("new lyrics", "a" * 64) if field == "lyrics" else ("cached lyrics", "b" * 64)
                self.assertEqual(tuple(row), expected)

    def test_lyrics_cover_queues_tags_only_after_both_fields_commit(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root, "metadata_tag_write_enabled": True})
            snapshots = []

            def queue(conn, track_id):
                snapshots.append(tuple(conn.execute("SELECT lyrics,artwork_id FROM metadata_tracks WHERE track_id=?", (track_id,)).fetchone()))

            with patch.object(service, "_download_artwork", return_value="a" * 64), \
                 patch.object(service, "_queue_tag_write", side_effect=queue):
                service._store_lyrics("t1", dict(self.candidate("first"), lyrics="new lyrics"))
            self.assertEqual(snapshots, [("new lyrics", "a" * 64)])

    def test_late_lyrics_keep_confirmed_cover_and_still_store_lyrics(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            chosen = self.candidate("chosen")
            search_id = service.cache_interactive_track_candidates("t1", [chosen])
            self.assertTrue(service.apply_track_match("t1", search_id=search_id))
            with patch.object(service, "_download_artwork", return_value="b" * 64):
                service._store_confirmed_track_artwork("t1")
            with patch.object(service, "_download_artwork", return_value="a" * 64) as download:
                service._store_lyrics("t1", dict(self.candidate("late"), lyrics="new lyrics"))
            download.assert_not_called()
            with service._connect() as conn:
                row = conn.execute("SELECT lyrics,artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone()
            self.assertEqual(tuple(row), ("new lyrics", "b" * 64))

    def test_lyrics_cover_download_cannot_cross_a_manual_confirmation(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            search_id = service.cache_interactive_track_candidates("t1", [self.candidate("chosen")])

            def complete_download(*args):
                self.assertTrue(service.apply_track_match("t1", search_id=search_id))
                return "a" * 64

            with patch.object(service, "_download_artwork", side_effect=complete_download):
                service._store_lyrics("t1", dict(self.candidate("late"), lyrics="new lyrics"))
            with service._connect() as conn:
                row = conn.execute("SELECT lyrics,artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone()
            self.assertEqual(tuple(row), ("new lyrics", ""))
            with patch.object(service, "_download_artwork", return_value="b" * 64):
                service._store_confirmed_track_artwork("t1")
            with service._connect() as conn:
                row = conn.execute("SELECT lyrics,artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone()
            self.assertEqual(tuple(row), ("new lyrics", "b" * 64))

    def test_lyrics_commit_does_not_restore_a_stale_artwork_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root, "metadata_tag_write_enabled": True})
            service._store_lyrics("t1", {"lyrics": "old lyrics"})
            with service._connect() as conn:
                conn.execute("UPDATE metadata_tracks SET artwork_id=? WHERE track_id='t1'", ("a" * 64,))
            original_connect = service._connect
            armed = True

            class ConnectionProxy:
                def __init__(self, connection):
                    self.connection = connection

                def execute(self, sql, parameters=()):
                    nonlocal armed
                    if armed and sql.lstrip().startswith("INSERT") and "metadata_tracks(" in sql:
                        armed = False
                        # A concurrent artwork worker commits after the lyric
                        # worker read its snapshot, before the final write.
                        with original_connect() as other:
                            other.execute("UPDATE metadata_tracks SET artwork_id=? WHERE track_id='t1'", ("b" * 64,))
                    return self.connection.execute(sql, parameters)

                def __getattr__(self, name):
                    return getattr(self.connection, name)

            @contextmanager
            def interleaved_connect():
                with original_connect() as connection:
                    yield ConnectionProxy(connection)

            with patch.object(service, "_connect", side_effect=interleaved_connect):
                service._store_lyrics("t1", {"lyrics": "new lyrics"})
            self.assertFalse(armed)
            with service._connect() as conn:
                row = conn.execute("SELECT lyrics,artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone()
            self.assertEqual(tuple(row), ("new lyrics", "b" * 64))

    def test_lyrics_cover_fallback_uses_first_cached_artwork(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            with patch.object(service, "_download_artwork", return_value="a" * 64) as download:
                service._store_lyrics("t1", dict(self.candidate("first"), lyrics="old lyrics"))
            download.assert_called_once()
            revision = service.metadata_projection_revision
            with patch.object(service, "_download_artwork", return_value="b" * 64) as download:
                service._store_lyrics("t1", dict(self.candidate("later"), lyrics="new lyrics"))
            download.assert_not_called()
            with service._connect() as conn:
                row = conn.execute("SELECT lyrics,artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone()
            self.assertEqual(tuple(row), ("new lyrics", "a" * 64))
            self.assertEqual(service.metadata_projection_revision, revision + 1)

    def test_failed_lyrics_artwork_download_still_saves_lyrics(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            with patch.object(service, "_download_artwork", side_effect=OSError("offline")):
                service._store_lyrics("t1", dict(self.candidate("first"), lyrics="new lyrics"))
            with service._connect() as conn:
                row = conn.execute("SELECT lyrics,artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone()
            self.assertEqual(tuple(row), ("new lyrics", ""))

    def test_lyrics_worker_preserves_confirmed_artwork(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            search_id = service.cache_interactive_track_candidates("t1", [self.candidate("chosen")])
            self.assertTrue(service.apply_track_match("t1", search_id=search_id))
            with service._connect() as conn:
                self.assertTrue(service._upsert_job(conn, "lyrics:t1", "lyrics", "t1", {}, 0, True))
            job = service._claim_job()
            self.assertEqual(job["job_type"], "lyrics")
            with patch.object(service.providers, "lyrics", return_value=dict(self.candidate("late"), lyrics="new lyrics")), \
                 patch.object(service, "_download_artwork", return_value="a" * 64) as download:
                service._process_job(job)
            download.assert_not_called()
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT lyrics,artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone()[:], ("new lyrics", ""))
                self.assertEqual(conn.execute("SELECT status FROM metadata_jobs WHERE job_key='lyrics:t1'").fetchone()[0], "done")

    def test_reconfirming_another_candidate_replaces_cached_cover(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root, "metadata_tag_write_enabled": True})
            first = self.candidate("first")
            first_id = service.cache_interactive_track_candidates("t1", [first])
            self.assertTrue(service.apply_track_match("t1", search_id=first_id))
            with patch.object(service, "_download_artwork", return_value="a" * 64):
                service._process_job(service._claim_job(priority_max=10, track_only=True))
            second = dict(self.candidate("second"), image_url="https://example.test/second.jpg")
            second_id = service.cache_interactive_track_candidates("t1", [second])
            self.assertTrue(service.apply_track_match("t1", search_id=second_id))
            with patch.object(service, "_download_artwork", return_value="b" * 64) as download:
                service._process_job(service._claim_job(priority_max=10, track_only=True))
            download.assert_called_once_with(second["image_url"], second["source"])
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone()[0], "b" * 64)

    def test_failed_confirmed_cover_replacement_keeps_old_asset_and_retries(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            with service._connect() as conn:
                conn.execute("INSERT INTO metadata_tracks(track_id,artwork_id) VALUES ('t1',?)", ("a" * 64,))
            search_id = service.cache_interactive_track_candidates("t1", [self.candidate("second")])
            self.assertTrue(service.apply_track_match("t1", search_id=search_id))
            job = service._claim_job(track_only=True)
            with patch.object(service, "_download_artwork", side_effect=OSError("offline")) as download:
                service._process_job(job)
            download.assert_called_once()
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone()[0], "a" * 64)
                self.assertEqual(conn.execute("SELECT status FROM metadata_jobs WHERE job_key='track-artwork:t1'").fetchone()[0], "retry")

    def test_explicit_artwork_replacement_requires_confirmation_at_commit(self):
        for change in ("DELETE FROM metadata_track_matches WHERE track_id='t1'",
                       "UPDATE metadata_track_matches SET orphaned_at=1 WHERE track_id='t1'",
                       "UPDATE metadata_track_matches SET status='review' WHERE track_id='t1'"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as root:
                service = MetadataService({"cache_dir": root})
                candidate = self.candidate("chosen")
                search_id = service.cache_interactive_track_candidates("t1", [candidate])
                self.assertTrue(service.apply_track_match("t1", search_id=search_id))

                def complete_download(*args):
                    with service._connect() as conn:
                        conn.execute(change)
                    return "a" * 64

                with patch.object(service, "_download_artwork", side_effect=complete_download):
                    self.assertFalse(service._store_track_artwork("t1", candidate, replace_existing=True))
                with service._connect() as conn:
                    self.assertIsNone(conn.execute("SELECT artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone())

    def test_reselection_after_cover_commit_is_not_reported_as_completed(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            search_id = service.cache_interactive_track_candidates("t1", [self.candidate("first")])
            self.assertTrue(service.apply_track_match("t1", search_id=search_id))
            job = service._claim_job(track_only=True)
            latest_id = service.cache_interactive_track_candidates("t1", [self.candidate("latest")])
            original_store = service._store_track_artwork

            def store_then_reselect(*args, **kwargs):
                stored = original_store(*args, **kwargs)
                self.assertTrue(service.apply_track_match("t1", search_id=latest_id))
                return stored

            with patch.object(service, "_store_track_artwork", side_effect=store_then_reselect), \
                 patch.object(service, "_download_artwork", return_value="a" * 64):
                service._process_job(job)
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT status FROM metadata_jobs WHERE job_key='track-artwork:t1'").fetchone()[0], "retry")
                self.assertEqual(service._track_match_fields(conn, "t1")["source"], "latest")

    def test_reselection_during_running_cover_job_retries_the_latest_choice(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            with service._connect() as conn:
                conn.execute("INSERT INTO metadata_tracks(track_id,artwork_id) VALUES ('t1',?)", ("a" * 64,))
            search_id = service.cache_interactive_track_candidates("t1", [self.candidate("second")])
            self.assertTrue(service.apply_track_match("t1", search_id=search_id))
            job = service._claim_job(track_only=True)
            latest_id = service.cache_interactive_track_candidates("t1", [self.candidate("latest")])

            def complete_old_download(*args):
                self.assertTrue(service.apply_track_match("t1", search_id=latest_id))
                return "b" * 64

            with patch.object(service, "_download_artwork", side_effect=complete_old_download):
                service._process_job(job)
            self.assertEqual(service.track_match("t1")["best"]["source"], "latest")
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone()[0], "a" * 64)
                self.assertEqual(conn.execute("SELECT status FROM metadata_jobs WHERE job_key='track-artwork:t1'").fetchone()[0], "retry")
                conn.execute("UPDATE metadata_jobs SET next_attempt_at=0 WHERE job_key='track-artwork:t1'")
            with patch.object(service, "_download_artwork", return_value="c" * 64):
                service._process_job(service._claim_job(track_only=True))
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone()[0], "c" * 64)
                self.assertEqual(conn.execute("SELECT status FROM metadata_jobs WHERE job_key='track-artwork:t1'").fetchone()[0], "done")

    def test_confirmed_reselection_writes_selected_wav_cover_over_album_fallback(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [root], "metadata_tag_write_enabled": True}
            source = os.path.join(root, "blank.wav")
            audio = b"\x00\x01" * 200
            fmt = bytes.fromhex("0100010044ac00008858010002001000")
            payload = b"WAVEfmt " + len(fmt).to_bytes(4, "little") + fmt + b"data" + len(audio).to_bytes(4, "little") + audio
            with open(source, "wb") as handle:
                handle.write(b"RIFF" + len(payload).to_bytes(4, "little") + payload)
            item = {"id": "t1", "path": source, "title": "blank", "artist": "Artist", "album": "Album", "album_artist": "Artist",
                    "format": "WAV", "metadata_source": {"title": "filename"}}
            save_items_to_sqlite(config, [item], root)
            service = MetadataService(config)
            os.makedirs(service.artwork_dir, exist_ok=True)
            candidates = [dict(self.candidate(name), image_url="https://example.test/" + name + ".jpg") for name in ("first", "second")]
            images = {}
            assets = {}
            with service._connect() as conn:
                for marker, name in (("a", "first"), ("b", "second"), ("c", "album")):
                    image = b"\xff\xd8\xff\xd9" + name.encode("ascii")
                    asset_id = hashlib.sha256(image).hexdigest()
                    assets[name] = asset_id
                    path = os.path.join(service.artwork_dir, asset_id + ".jpg")
                    with open(path, "wb") as handle:
                        handle.write(image)
                    images[name] = image
                    conn.execute("INSERT INTO metadata_assets(id,path,mime,size,source_url) VALUES (?,?,?,?,?)",
                                 (asset_id, path, "image/jpeg", len(image), "https://example.test/" + name + ".jpg"))
                conn.execute("INSERT INTO metadata_entities(entity_type,entity_key,name,artist,artwork_id) VALUES ('album',?,?,?,?)",
                             (entity_key("album", "Album", "Artist"), "Album", "Artist", assets["album"]))
            display_item = dict(item)
            for name, candidate in zip(("first", "second"), candidates):
                search_id = service.cache_interactive_track_candidates("t1", [candidate])
                self.assertTrue(service.apply_track_match("t1", search_id=search_id))
                if name == "second":
                    self.assertEqual(service._tag_data("t1")["artwork_path"], os.path.join(service.artwork_dir, assets["album"] + ".jpg"))
                with patch.object(service, "_download_artwork", return_value=assets[name]):
                    service._process_job(service._claim_job(track_only=True))
                display_item = service.enrich_track_page({"items": [display_item]})["items"][0]
            with patch("library_presentation.thumbnail_asset_id_for_item", return_value="f" * 64):
                public = public_library_item(display_item, config)
            self.assertEqual(public["cover_url"], "metadata/artwork/" + assets["second"])
            self.assertEqual(public["cover_thumbnail_url"], "")
            self.assertNotIn("metadata_artwork_confirmed", public)
            response = io.BytesIO(images["second"])
            response.headers = Message()
            response.headers["Content-Type"] = "image/jpeg"
            response.headers["Content-Length"] = str(len(images["second"]))
            with patch("metadata_service._open_metadata_url", return_value=response), \
                 patch("metadata_service.public_metadata_http_url", side_effect=lambda value, *args: value), \
                 patch("metadata_service.disk_has_reserve", return_value=True):
                self.assertEqual(service._download_artwork("https://example.test/mirror.jpg"), assets["second"])
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT source_url FROM metadata_assets WHERE id=?", (assets["second"],)).fetchone()[0], "https://example.test/mirror.jpg")
            with service._connect() as conn:
                conn.execute("UPDATE metadata_jobs SET next_attempt_at=0 WHERE job_type='tag_write'")
            service._process_job(service._claim_job(tag_writes_only=True))
            self.assertEqual(read_cover(source), ("image/jpeg", images["second"]))
            with open(source, "rb") as handle:
                self.assertIn(b"data" + len(audio).to_bytes(4, "little") + audio, handle.read())

    def test_existing_match_cache_migrates_confirmed_artwork_binding_once(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            search_id = service.cache_interactive_track_candidates("t1", [self.candidate("chosen")])
            self.assertTrue(service.apply_track_match("t1", search_id=search_id))
            with service._connect() as conn:
                original = tuple(conn.execute("SELECT status,fields_json FROM metadata_track_matches WHERE track_id='t1'").fetchone())
                if "confirmed_artwork_id" in {row["name"] for row in conn.execute("PRAGMA table_info(metadata_track_matches)")}:
                    conn.execute("ALTER TABLE metadata_track_matches DROP COLUMN confirmed_artwork_id")
            for _ in range(2):
                with service._connect() as conn:
                    self.assertEqual([row["name"] for row in conn.execute("PRAGMA table_info(metadata_track_matches)")].count("confirmed_artwork_id"), 1)
                    row = conn.execute("SELECT status,fields_json,confirmed_artwork_id FROM metadata_track_matches WHERE track_id='t1'").fetchone()
                    self.assertEqual(tuple(row), original + ("",))

    def test_late_background_matches_preserve_manual_confirmation(self):
        for background in ([self.candidate("late-auto")],
                           [dict(self.candidate("late-review"), confidence=0.6)], []):
            with self.subTest(background=background), tempfile.TemporaryDirectory() as root:
                service = MetadataService({"cache_dir": root})
                chosen = self.candidate("chosen")
                search_id = service.cache_interactive_track_candidates("t1", [chosen])
                self.assertTrue(service.apply_track_match("t1", search_id=search_id))
                with service._connect() as conn:
                    before = dict(conn.execute("SELECT * FROM metadata_track_matches WHERE track_id='t1'").fetchone())
                revision = service.metadata_projection_revision
                service._store_track_match("t1", background)
                with service._connect() as conn:
                    after = dict(conn.execute("SELECT * FROM metadata_track_matches WHERE track_id='t1'").fetchone())
                self.assertEqual(after, before, "late automatic work must not replace a user's choice")
                self.assertEqual(service.metadata_projection_revision, revision)

    def test_confirmation_between_background_read_and_write_wins(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root, "metadata_tag_write_enabled": True})
            service._store_track_match("t1", [self.candidate("before")])
            search_id = service.cache_interactive_track_candidates("t1", [self.candidate("chosen")])
            original_connect = service._connect
            armed = True

            class ConnectionProxy:
                def __init__(self, connection):
                    self.connection = connection

                def execute(self, sql, parameters=()):
                    nonlocal armed
                    if armed and sql.lstrip().startswith("INSERT") and "metadata_track_matches" in sql:
                        armed = False
                        self_test.assertTrue(service.apply_track_match("t1", search_id=search_id))
                    return self.connection.execute(sql, parameters)

                def __getattr__(self, name):
                    return getattr(self.connection, name)

            self_test = self

            @contextmanager
            def interleaved_connect():
                with original_connect() as connection:
                    yield ConnectionProxy(connection)

            with patch.object(service, "_connect", side_effect=interleaved_connect):
                result = service._store_track_match("t1", [self.candidate("late")])
            self.assertFalse(armed, "the test must exercise the write boundary")
            self.assertEqual(result["source"], "chosen")
            with service._connect() as conn:
                row = conn.execute("SELECT status,source FROM metadata_track_matches WHERE track_id='t1'").fetchone()
            self.assertEqual(tuple(row), ("confirmed", "chosen"))

    def test_background_refresh_still_replaces_auto_and_orphaned_matches(self):
        for orphaned in (False, True):
            with self.subTest(orphaned=orphaned), tempfile.TemporaryDirectory() as root:
                service = MetadataService({"cache_dir": root})
                service._store_track_match("t1", [self.candidate("old")])
                if orphaned:
                    with service._connect() as conn:
                        conn.execute("UPDATE metadata_track_matches SET status='confirmed',orphaned_at=1 WHERE track_id='t1'")
                self.assertEqual(service._store_track_match("t1", [self.candidate("new")])["source"], "new")
                with service._connect() as conn:
                    row = conn.execute("SELECT status,source,orphaned_at FROM metadata_track_matches WHERE track_id='t1'").fetchone()
                self.assertEqual(tuple(row), ("auto", "new", 0))

    def test_background_artwork_cannot_replace_a_confirmed_choice(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            search_id = service.cache_interactive_track_candidates("t1", [self.candidate("chosen")])
            self.assertTrue(service.apply_track_match("t1", search_id=search_id))
            with patch.object(service, "_download_artwork", return_value="a" * 64) as download:
                self.assertFalse(service._store_track_artwork("t1", self.candidate("late")))
            download.assert_not_called()
            with service._connect() as conn:
                self.assertIsNone(conn.execute("SELECT artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone())

    def test_confirmation_during_artwork_download_rejects_old_result(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            search_id = service.cache_interactive_track_candidates("t1", [self.candidate("chosen")])

            def complete_old_download(*args):
                self.assertTrue(service.apply_track_match("t1", search_id=search_id))
                return "a" * 64

            with patch.object(service, "_download_artwork", side_effect=complete_old_download):
                self.assertFalse(service._store_track_artwork("t1", self.candidate("late")))
            with service._connect() as conn:
                self.assertIsNone(conn.execute("SELECT artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone())

    def test_new_selection_during_confirmed_cover_download_rejects_old_result(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            original = self.candidate("original")
            first_id = service.cache_interactive_track_candidates("t1", [original])
            self.assertTrue(service.apply_track_match("t1", search_id=first_id))
            new_id = service.cache_interactive_track_candidates("t1", [self.candidate("new")])

            def complete_old_download(*args):
                self.assertTrue(service.apply_track_match("t1", search_id=new_id))
                return "a" * 64

            with patch.object(service, "_download_artwork", side_effect=complete_old_download):
                self.assertFalse(service._store_track_artwork("t1", original))
            with service._connect() as conn:
                self.assertIsNone(conn.execute("SELECT artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone())
                self.assertEqual(service._track_match_fields(conn, "t1")["source"], "new")

    def test_background_job_does_not_use_cover_fallback_after_manual_no_cover_choice(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            chosen = dict(self.candidate("chosen"), image_url="")
            search_id = service.cache_interactive_track_candidates("t1", [chosen])
            self.assertTrue(service.apply_track_match("t1", search_id=search_id))
            with service._connect() as conn:
                self.assertTrue(service._upsert_job(conn, "track:t1", "track", "t1", {}, 1, True))
            job = service._claim_job()
            self.assertIsNotNone(job)
            with patch.object(service.providers, "track_candidates", return_value=[self.candidate("late")]), \
                 patch.object(service, "_download_artwork", return_value="a" * 64) as download:
                service._process_job(job)
            download.assert_not_called()
            with service._connect() as conn:
                self.assertEqual(service._track_match_fields(conn, "t1")["source"], "chosen")
                self.assertEqual(conn.execute("SELECT status FROM metadata_jobs WHERE job_key='track:t1'").fetchone()[0], "done")

    def test_full_queue_does_not_accept_a_confirmation_without_its_cover_job(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            search_id = service.cache_interactive_track_candidates("t1", [self.candidate("kugou")])
            with patch.object(service, "_upsert_job", return_value=False):
                self.assertFalse(service.apply_track_match("t1", search_id=search_id))
            with service._connect() as conn:
                self.assertIsNone(conn.execute("SELECT status FROM metadata_track_matches WHERE track_id='t1'").fetchone())

    def test_artwork_completion_survives_an_already_running_tag_write(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root, "metadata_tag_write_enabled": True})
            search_id = service.cache_interactive_track_candidates("t1", [self.candidate("kugou")])
            with patch.object(service, "ensure_workers"):
                self.assertTrue(service.apply_track_match("t1", search_id=search_id))
            with service._connect() as conn:
                service._upsert_job(conn, "tag:t1", "tag_write", "t1", {}, 2)
                conn.execute("UPDATE metadata_jobs SET next_attempt_at=0 WHERE job_key='tag:t1'")
            writing = service._claim_job(tag_writes_only=True)
            self.assertIsNotNone(writing)
            with patch.object(service, "_download_artwork", return_value="b" * 64):
                service._store_confirmed_track_artwork("t1")
            service._finish_job(writing["job_key"], "done", "", expected_attempts=1)
            with service._connect() as conn:
                waiting = conn.execute("SELECT COUNT(*) FROM metadata_jobs WHERE job_type='tag_write' AND status IN ('pending','retry')").fetchone()[0]
            self.assertGreater(waiting, 0, "a writer that read pre-cover data must be followed by a new write")

    def test_confirmed_wav_downloads_selected_cover_without_another_search(self):
        with tempfile.TemporaryDirectory() as root:
            config = {"cache_dir": os.path.join(root, "cache"), "library_paths": [root],
                      "metadata_enabled": False, "metadata_tag_write_enabled": True}
            source = os.path.join(root, "blank.wav")
            audio = b"\x00\x01" * 200
            fmt = bytes.fromhex("0100010044ac00008858010002001000")
            payload = b"WAVEfmt " + len(fmt).to_bytes(4, "little") + fmt + b"data" + len(audio).to_bytes(4, "little") + audio
            with open(source, "wb") as handle:
                handle.write(b"RIFF" + len(payload).to_bytes(4, "little") + payload)
            item = {"id": "wav1", "path": source, "title": "blank", "artist": "", "album": "",
                    "format": "WAV", "metadata_source": {"title": "filename"}}
            save_items_to_sqlite(config, [item], root)
            service = MetadataService(config)
            search_id = service.cache_interactive_track_candidates("wav1", [self.candidate("kugou")])
            # Confirmation is local and prompt: downloading belongs to a durable
            # worker job, even when background metadata enrichment is disabled.
            with patch.object(service, "ensure_workers"), patch.object(service, "_download_artwork") as download:
                self.assertTrue(service.apply_track_match("wav1", search_id=search_id))
                download.assert_not_called()
            job = service._claim_job(priority_max=10, exclude_tag_writes=True)
            self.assertIsNotNone(job, "manual confirmation must queue the chosen artwork")
            self.assertEqual(job["job_type"], "track_artwork")
            image = b"\xff\xd8\xff\xd9"
            artwork_id = "b" * 64
            artwork = os.path.join(service.artwork_dir, artwork_id + ".jpg")
            os.makedirs(service.artwork_dir, exist_ok=True)
            with open(artwork, "wb") as handle:
                handle.write(image)
            with service._connect() as conn:
                conn.execute("INSERT INTO metadata_assets(id,path,mime,size) VALUES (?,?,?,?)",
                             (artwork_id, artwork, "image/jpeg", len(image)))
            with patch.object(service, "_download_artwork", return_value=artwork_id) as download, \
                 patch.object(service.providers, "track_candidates", side_effect=AssertionError("must use confirmed candidate")):
                service._process_job(job)
            download.assert_called_once_with("https://example.test/cover.jpg", "kugou")
            row = service.enrich_track_page({"items": [item]})["items"][0]
            self.assertEqual(public_library_item(row, config)["cover_url"], "metadata/artwork/" + artwork_id)
            self.assertTrue(service._write_track_tags("wav1"))
            self.assertEqual(read_id3(source)["title"], "Song")
            self.assertEqual(read_cover(source), ("image/jpeg", image))
            with open(source, "rb") as handle:
                body = handle.read()
            self.assertIn(b"data" + len(audio).to_bytes(4, "little") + audio, body)

    def test_confirmed_artwork_is_cached_when_tag_write_is_disabled(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root, "metadata_tag_write_enabled": False})
            search_id = service.cache_interactive_track_candidates("t1", [self.candidate("kugou")])
            with patch.object(service, "ensure_workers"):
                self.assertTrue(service.apply_track_match("t1", search_id=search_id))
            job = service._claim_job(priority_max=10, exclude_tag_writes=True)
            self.assertIsNotNone(job, "cover display must not depend on destructive Tag writes")
            with patch.object(service, "_download_artwork", return_value="b" * 64):
                service._process_job(job)
            self.assertEqual(service.track_match("t1")["image_url"], "metadata/artwork/" + "b" * 64)
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_jobs WHERE job_type='tag_write'").fetchone()[0], 0)

    def service(self):
        service = object.__new__(MetadataService)
        service.providers = MetadataProviders({})
        service._interactive_search_gate = ConcurrencyGate("metadata-search", max_waiters=0)
        return service

    def candidate(self, source, index=0):
        return {"title": "Song", "artist": "Artist", "album": "Album",
                "image_url": "https://example.test/cover.jpg", "source": source,
                "provider_id": "%s-%s" % (source, index), "confidence": 0.99}

    def test_interactive_search_has_two_global_requests_and_six_provider_lanes(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            sources = ["netease", "kuwo", "kugou"]
            all_started = threading.Event()
            release = threading.Event()
            lock = threading.Lock()
            started = 0

            def held(source, _track):
                nonlocal started
                with lock:
                    started += 1
                    if started == 6:
                        all_started.set()
                release.wait(4)
                return [self.candidate(source)]

            with patch.object(service.providers, "_provider_ids", return_value=sources), \
                 patch.object(service.providers, "_track_candidates_for_provider", side_effect=held), \
                 ThreadPoolExecutor(max_workers=2) as clients:
                futures = [clients.submit(service.track_candidates, {"title": "Song " + str(i)}) for i in range(2)]
                try:
                    self.assertTrue(all_started.wait(2), "two requests must run three source lanes each")
                    with self.assertRaises(ResourceLimitError):
                        service.track_candidates({"title": "Overflow"}, provider_id="netease")
                    self.assertEqual(started, 6, "rejected work must not create another provider lane")
                finally:
                    release.set()
                for future in futures:
                    result = future.result(timeout=2)
                    self.assertEqual([row["source"] for row in result], sources)
            self.assertEqual(service._interactive_search_gate.snapshot()["active"], 0)
            self.assertEqual(service._interactive_search_gate.snapshot()["waited"], 0, "overflow must never queue behind active searches")

    def test_interactive_search_capacity_recovers_after_worker_failure_and_early_return(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            for _ in range(3):
                with patch.object(service.providers, "track_candidates", side_effect=RuntimeError("worker failed")):
                    with self.assertRaisesRegex(RuntimeError, "worker failed"):
                        service.track_candidates({"title": "Song"}, provider_id="netease")
            for count in (0, 1, 8):
                with patch.object(service.providers, "track_candidates",
                                  return_value=[self.candidate("netease", i) for i in range(count)]):
                    for _ in range(3):
                        self.assertEqual(len(service.track_candidates({"title": "Song"}, provider_id="netease")), count)
                        self.assertEqual(service._interactive_search_gate.snapshot()["active"], 0)

    def test_interactive_search_capacity_recovers_after_pool_start_failure(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root})
            for _ in range(3):
                with patch("metadata_service.ThreadPoolExecutor", side_effect=RuntimeError("pool could not start")):
                    with self.assertRaisesRegex(RuntimeError, "pool could not start"):
                        service.track_candidates({"title": "Song"}, provider_id="netease")
            with patch.object(service.providers, "_track_candidates_for_provider",
                              return_value=[self.candidate("netease")]):
                self.assertEqual(len(service.track_candidates({"title": "Song"}, provider_id="netease")), 1)

    def test_selected_provider_reaches_real_service_and_provider(self):
        service = self.service()
        with patch.object(service.providers, "_track_candidates_for_provider",
                          return_value=[self.candidate("netease")]) as search:
            results = service.track_candidates({"title": "Song"}, provider_id="netease")
        self.assertEqual([call.args[0] for call in search.call_args_list], ["netease"])
        self.assertEqual(results[0]["source"], "netease")

    def test_automatic_interactive_search_keeps_each_source_even_for_same_song(self):
        service = self.service()
        sources = service.providers._provider_ids("search")
        with patch.object(service.providers, "_track_candidates_for_provider",
                          side_effect=lambda source, _track: [self.candidate(source)]) as search:
            results = service.track_candidates({"title": "Song"})
        self.assertCountEqual([call.args[0] for call in search.call_args_list], sources)
        self.assertEqual([item["source"] for item in results], sources)
        self.assertLessEqual(len(results), 8)

    def test_slow_source_does_not_serialize_other_sources_and_budget_is_cleared(self):
        service = self.service()
        sources = service.providers._provider_ids("search")
        arrived = threading.Event()
        deadlines = []
        def search(source, _track):
            deadlines.append(getattr(service.providers._failure_local, "deadline", None))
            if source == sources[0]:
                self.assertTrue(arrived.wait(2), "next source must run while first is waiting")
            else:
                arrived.set()
            return [self.candidate(source)]
        with patch.object(service.providers, "_track_candidates_for_provider", side_effect=search):
            result = service.track_candidates({"title": "Song"})
        self.assertEqual(len(result), len(sources))
        self.assertTrue(all(isinstance(deadline, float) for deadline in deadlines))
        self.assertIsNone(getattr(service.providers._failure_local, "deadline", None))

    def test_failed_source_does_not_hide_successful_sources(self):
        service = self.service()
        def search(source, _track):
            if source == "netease":
                raise ValueError("provider unavailable")
            return [self.candidate(source)]
        with patch.object(service.providers, "_track_candidates_for_provider", side_effect=search):
            result = service.track_candidates({"title": "Song"})
        self.assertNotIn("netease", [item["source"] for item in result])
        self.assertGreater(len(result), 1)

    def test_unknown_scope_never_falls_back_to_all_sources(self):
        service = self.service()
        with patch.object(service.providers, "_track_candidates_for_provider") as search:
            self.assertEqual(service.track_candidates({"title": "Song"}, provider_id="bad"), [])
        search.assert_not_called()

    def test_manual_keyword_results_do_not_use_automatic_identity_threshold(self):
        service = self.service()
        candidate = dict(self.candidate("netease"), title="Song", artist="Artist", confidence=0.45)
        with patch.object(service.providers, "_track_candidates_for_provider", return_value=[candidate]):
            results = service.track_candidates({"title": "Artist Song"}, provider_id="netease")
        self.assertEqual(results[0]["title"], "Song")

    def test_search_results_preserve_confirmed_match_and_bind_exact_result(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root, "library_paths": [root], "metadata_tag_write_enabled": False})
            service.store_interactive_track_candidates("t1", [self.candidate("original")])
            self.assertTrue(service.apply_track_match("t1", 0))
            a = service.cache_interactive_track_candidates("t1", [self.candidate("search-a")])
            b = service.cache_interactive_track_candidates("t1", [self.candidate("search-b")])
            self.assertNotEqual(a, b)
            self.assertEqual(service.track_match("t1")["status"], "confirmed")
            self.assertEqual(service.track_match("t1")["best"]["source"], "original")
            self.assertFalse(service.apply_track_match("wrong-track", 0, search_id=b))
            self.assertFalse(service.apply_track_match("t1", 0, search_id="expired"))
            self.assertTrue(service.apply_track_match("t1", 0, search_id=b))
            self.assertEqual(service.track_match("t1")["best"]["source"], "search-b")

    def test_confirming_search_refreshes_an_expired_match(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({"cache_dir": root, "library_paths": [root]})
            service.store_interactive_track_candidates("t1", [self.candidate("old")])
            with service._connect() as conn:
                conn.execute("UPDATE metadata_track_matches SET fetched_at=1,expires_at=2 WHERE track_id='t1'")
            search_id = service.cache_interactive_track_candidates("t1", [self.candidate("chosen")])
            self.assertTrue(service.apply_track_match("t1", 0, search_id=search_id))
            with service._connect() as conn:
                row = conn.execute("SELECT fetched_at,expires_at FROM metadata_track_matches WHERE track_id='t1'").fetchone()
            self.assertGreater(row["fetched_at"], 2)
            self.assertGreater(row["expires_at"], row["fetched_at"])
            self.assertEqual(service.track_match("t1")["status"], "confirmed")
            self.assertEqual(service.track_match("t1")["best"]["source"], "chosen")


if __name__ == "__main__":
    unittest.main()
