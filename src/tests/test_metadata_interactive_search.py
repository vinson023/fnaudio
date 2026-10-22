"""Exercise the real service boundary, not a permissive HTTP test double."""
import threading
import os
import tempfile
import unittest
from unittest.mock import patch

from metadata_service import MetadataProviders, MetadataService
from library import read_cover, read_id3, save_items_to_sqlite
from library_presentation import public_library_item


class InteractiveSearchTests(unittest.TestCase):
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
        return service

    def candidate(self, source, index=0):
        return {"title": "Song", "artist": "Artist", "album": "Album",
                "image_url": "https://example.test/cover.jpg", "source": source,
                "provider_id": "%s-%s" % (source, index), "confidence": 0.99}

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
