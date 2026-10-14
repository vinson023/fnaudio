import base64
import json
import io
import gzip
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import threading
import urllib.error
import urllib.parse
import unittest
import zlib
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

sys.path.insert(0, "app/server")

import metadata_service
from library import read_cover, read_id3, save_items_to_sqlite
from metadata_service import (
    MAX_ARTWORK_BYTES, MetadataProviders, MetadataService, _ape_existing_items, _decode_lyrics_text, _decode_provider_json, _preserved_id3_frames, _write_ape_tags, _write_dsf_tags, _write_wav_tags,
    _NoMetadataRedirect, MAX_PROVIDER_LYRICS_BASE64_CHARS, MAX_PROVIDER_LYRICS_BYTES, entity_key, normalize_release_date,
)
from metadata_track_match_policy import valid_artwork_id
from metadata_local_lyrics_cache import DEFAULT_MAX_BYTES, LocalLyricsCache
from metadata_match_policy import MAX_NORMALIZED_TEXT, normalize_text


class _RecordingConnect:
    """Hand back the service connection while recording the SQL it runs."""

    def __init__(self, conn, manager):
        self._conn = conn
        self._manager = manager

    def __enter__(self):
        return self._conn

    def __exit__(self, *exc_info):
        return self._manager.__exit__(*exc_info)


class MetadataServiceTests(unittest.TestCase):
    def test_media_process_mock_path_enforces_output_limit(self):
        output = tempfile.TemporaryFile(mode="w+b")
        try:
            output.write(b"x" * 11)
            with patch("metadata_service.subprocess.run", return_value=MagicMock(returncode=0)):
                with self.assertRaises(metadata_service.ResourceLimitError):
                    metadata_service._run_media_process(
                        ["helper"], stdout=output, stderr=subprocess.DEVNULL,
                        timeout=1, env={}, output_limit=10,
                    )
        finally:
            output.close()

    def test_normalize_text_bounds_locally_stored_and_provider_values(self):
        value = "A" * (MAX_NORMALIZED_TEXT + 500)
        normalized = normalize_text(value)
        self.assertLessEqual(len(normalized), MAX_NORMALIZED_TEXT)
        self.assertTrue(normalized)

    def test_background_reconcile_windows_use_monotonic_clock(self):
        with open(os.path.join("app", "server", "metadata_service.py"), encoding="utf-8") as handle:
            source = handle.read()
        # R201 (F5): the window is still monotonic; only its length moved into
        # metadata_queue_backlog_policy so a saturated queue can back off.
        self.assertIn(
            "due = metadata_queue_backlog_policy.should_run_reconcile(\n"
            "                        time.monotonic() - self._last_reconcile_monotonic,\n"
            "                        force=force,\n"
            "                        backlogged=self._queue_is_backlogged(),\n"
            "                    )",
            source,
        )
        self.assertNotIn("self._last_reconcile_monotonic > 15", source)
        self.assertIn("if time.monotonic() - self._last_cleanup_monotonic > 3600:", source)
        self.assertIn("self.last_reconcile = time.time()", source)
        self.assertIn("self._last_reconcile_monotonic = time.monotonic()", source)

    def test_lyrics_cache_budget_is_read_from_config_on_both_lanes(self):
        # R138 (ruling X7=A): LocalLyricsCache accepted `max_bytes` all along and
        # nothing ever passed it. There are two independent construction sites,
        # so a test that checks only one would let the other stay pinned at the
        # built-in default while the deployment believes it configured both.
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            config["metadata_lyrics_cache_max_bytes"] = 256 * 1024
            providers = MetadataProviders(config)
            service = MetadataService(config)
            for label, cache in (
                ("providers", providers._local_lyrics_cache),
                ("service", service._local_lyrics_cache),
                ("service.providers", service.providers._local_lyrics_cache),
            ):
                with self.subTest(lane=label):
                    self.assertEqual(cache.snapshot()["bytes_limit"], 256 * 1024)

    def test_lyrics_cache_budget_keeps_the_default_without_the_setting(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            self.assertEqual(service._local_lyrics_cache.snapshot()["bytes_limit"], DEFAULT_MAX_BYTES)
            self.assertEqual(
                service.providers._local_lyrics_cache.snapshot()["bytes_limit"], DEFAULT_MAX_BYTES
            )

    def test_apply_lyrics_cache_config_reaches_both_lanes(self):
        # There are two independent LocalLyricsCache instances per service. A
        # settings change that only re-trains one of them would report a budget
        # the process does not actually honour.
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            service = MetadataService(config)
            self.assertEqual(service.apply_lyrics_cache_config(
                {"metadata_lyrics_cache_max_bytes": 256 * 1024}), 256 * 1024)
            self.assertEqual(len(service._lyrics_cache_lanes()), 2)
            for lane in service._lyrics_cache_lanes():
                self.assertEqual(lane.snapshot()["bytes_limit"], 256 * 1024)

    def test_apply_lyrics_cache_config_drains_entries_when_it_shrinks(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            body = "l" * 60000
            with patch.object(metadata_service, "read_local_lyrics", return_value=body):
                service._read_local_lyrics_cached("a.lrc", (1, 1))
                service._read_local_lyrics_cached("b.lrc", (2, 2))
            before = service._local_lyrics_cache.snapshot()
            self.assertEqual(before["entries"], 2)
            service.apply_lyrics_cache_config({"metadata_lyrics_cache_max_bytes": 64 * 1024})
            after = service._local_lyrics_cache.snapshot()
            self.assertLess(after["entries"], before["entries"])
            self.assertLessEqual(after["bytes"], after["bytes_limit"])

    def test_apply_lyrics_cache_config_survives_a_missing_providers_lane(self):
        # Diagnostics and some tests build a MetadataService without providers;
        # the retraining hook must degrade to the lane that exists.
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            del service.providers
            self.assertEqual(service.apply_lyrics_cache_config(
                {"metadata_lyrics_cache_max_bytes": 65536}), 65536)
            self.assertEqual(service._local_lyrics_cache.snapshot()["bytes_limit"], 65536)

    def test_apply_lyrics_cache_config_without_an_argument_reads_the_stored_config(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            service = MetadataService(config)
            config["metadata_lyrics_cache_max_bytes"] = 2 * 1024 * 1024
            self.assertEqual(service.apply_lyrics_cache_config(), 2 * 1024 * 1024)
            self.assertEqual(service.lyrics_cache_bytes_limit(), 2 * 1024 * 1024)

    def test_lyrics_cache_bytes_limit_reports_the_tightest_lane(self):
        # The aggregate status deliberately adds both lanes; a settings page has
        # to show what is really enforced, and the tightest lane is the one a
        # lyric can overflow.
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service._local_lyrics_cache.apply_bytes_limit(64 * 1024)
            service.providers._local_lyrics_cache.apply_bytes_limit(64 * 1024 * 1024)
            self.assertEqual(service.lyrics_cache_bytes_limit(), 64 * 1024)
            # Widening the tight lane moves the answer; reading one fixed lane or
            # adding the two together would not.
            service._local_lyrics_cache.apply_bytes_limit(2 * 1024 * 1024)
            self.assertEqual(service.lyrics_cache_bytes_limit(), 2 * 1024 * 1024)

    def test_lyrics_cache_bytes_limit_falls_back_when_no_lane_exists(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            config["metadata_lyrics_cache_max_bytes"] = 3 * 1024 * 1024
            service = MetadataService(config)
            del service.providers
            del service._local_lyrics_cache
            self.assertEqual(service.lyrics_cache_bytes_limit(), 3 * 1024 * 1024)

    def test_connect_preserves_body_failure_when_rollback_fails(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            conn = MagicMock()
            conn.rollback.side_effect = RuntimeError("rollback failed")
            with patch.object(service, "_ensure_schema"), \
                 patch("metadata_service.secure_directory"), \
                 patch("metadata_service.secure_sqlite_files"), \
                 patch("metadata_service.sqlite3.connect", return_value=conn):
                with self.assertRaisesRegex(ValueError, "body failed"):
                    with service._connect():
                        raise ValueError("body failed")
            conn.rollback.assert_called_once()
            conn.close.assert_called_once()

    def test_connect_preserves_body_failure_when_failed_cleanup_fails(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            conn = MagicMock()
            conn.close.side_effect = RuntimeError("close failed")
            secure_files = MagicMock(side_effect=[None, None, RuntimeError("permission failed")])
            with patch.object(service, "_ensure_schema"), \
                 patch("metadata_service.secure_directory"), \
                 patch("metadata_service.secure_sqlite_files", secure_files), \
                 patch("metadata_service.sqlite3.connect", return_value=conn):
                with self.assertRaisesRegex(ValueError, "body failed"):
                    with service._connect():
                        raise ValueError("body failed")
            conn.rollback.assert_called_once()
            conn.close.assert_called_once()

    def test_connect_does_not_turn_committed_metadata_into_cleanup_failure(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            conn = MagicMock()
            secure_files = MagicMock(side_effect=[None, None, RuntimeError("permission failed")])
            with patch.object(service, "_ensure_schema"), \
                 patch("metadata_service.secure_directory"), \
                 patch("metadata_service.secure_sqlite_files", secure_files), \
                 patch("metadata_service.sqlite3.connect", return_value=conn):
                with service._connect():
                    pass
            conn.commit.assert_called_once()
            conn.close.assert_called_once()

    def test_metadata_provider_opener_never_follows_redirects(self):
        self.assertIsNone(_NoMetadataRedirect().redirect_request(
            None, None, 302, "Found", {}, "http://127.0.0.1/private"
        ))

    def test_provider_and_service_share_local_lyrics_cache_implementation(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            self.assertIsInstance(service.providers._local_lyrics_cache, LocalLyricsCache)
            self.assertIsInstance(service._local_lyrics_cache, LocalLyricsCache)
            self.assertIsNot(service.providers._local_lyrics_cache, service._local_lyrics_cache)

    def test_provider_lyrics_reuses_cached_local_reader(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            track = {"path": os.path.join(root, "song.mp3"), "title": "Song", "artist": "Artist"}
            with patch.object(service.providers, "_read_local_lyrics_cached", return_value="[00:01.00]cached") as reader:
                result = service.providers.lyrics(track)
            self.assertEqual(result["source"], "本地歌词")
        reader.assert_called_once_with(track["path"])

    def test_entity_provider_empty_result_is_observed_without_clearing_failure_state(self):
        providers = MetadataProviders({})
        providers._provider_cooldown_until["first"] = 0
        providers._provider_failures["first"] = {"count": 2, "last_error": "timeout", "last_at": 1}
        first = lambda _name: None
        first.__name__ = "first"
        second = lambda _name: {"name": "Recovered"}
        second.__name__ = "second"

        self.assertEqual(providers._first_match((first, second), "Album"), {"name": "Recovered"})
        self.assertEqual(providers._provider_empty_results["first"], 1)
        self.assertEqual(providers._provider_failures["first"]["count"], 2)
        self.assertNotIn("first", providers._provider_successes)
        self.assertEqual(providers._provider_successes["second"]["count"], 1)

    def test_provider_state_eviction_breaks_ties_by_name(self):
        providers = MetadataProviders({})
        for index in range(metadata_service.PROVIDER_STATE_MAX_ENTRIES):
            name = "provider-%02d" % index
            providers._provider_empty_results[name] = 1
            providers._provider_no_valid_candidates[name] = 1

        providers._ensure_provider_slot_locked("newcomer")

        self.assertNotIn("provider-00", providers._provider_empty_results)
        self.assertNotIn("provider-00", providers._provider_no_valid_candidates)
        self.assertIn("provider-01", providers._provider_empty_results)
        self.assertEqual(
            len(providers._provider_empty_results),
            metadata_service.PROVIDER_STATE_MAX_ENTRIES - 1,
        )

    def test_provider_state_eviction_prefers_the_least_recently_seen_name(self):
        providers = MetadataProviders({})
        for index in range(metadata_service.PROVIDER_STATE_MAX_ENTRIES):
            name = "provider-%02d" % index
            last_at = 1000.0 if name == "provider-00" else 0.0
            providers._provider_successes[name] = {"count": 1, "last_at": last_at}

        providers._ensure_provider_slot_locked("newcomer")

        self.assertIn("provider-00", providers._provider_successes)
        self.assertNotIn("provider-01", providers._provider_successes)
        self.assertIn("provider-02", providers._provider_successes)

    def test_lyrics_provider_empty_result_does_not_clear_failure_state(self):
        providers = MetadataProviders({})
        providers._provider_cooldown_until["first_lyrics"] = 0
        providers._provider_failures["first_lyrics"] = {"count": 2, "last_error": "timeout", "last_at": 1}
        first = lambda _track: None
        first.__name__ = "first_lyrics"
        second = lambda _track: {"lyrics": "[00:01.00]Recovered", "source": "second"}
        second.__name__ = "second_lyrics"
        with patch.object(providers, "_read_local_lyrics_cached", return_value=""), \
             patch.object(providers, "_provider_is_available", return_value=True):
            with patch.object(providers, "netease_lyrics", first), \
                 patch.object(providers, "qq_lyrics", second), \
                 patch.object(providers, "kugou_lyrics", lambda _track: None), \
                 patch.object(providers, "migu_lyrics", lambda _track: None), \
                 patch.object(providers, "joox_lyrics", lambda _track: None), \
                 patch.object(providers, "qianqian_lyrics", lambda _track: None):
                result = providers.lyrics({"path": "song.mp3", "title": "Song", "artist": "Artist"})
        self.assertEqual(result["source"], "second")
        self.assertEqual(providers._provider_empty_results["first_lyrics"], 1)
        self.assertNotIn("first_lyrics", providers._provider_successes)
        self.assertEqual(providers._provider_successes["second_lyrics"]["count"], 1)

    def test_provider_text_limit_rejects_untrusted_numeric_objects(self):
        providers = MetadataProviders({})
        class Exploding:
            def __int__(self):
                raise AssertionError("limit must not invoke custom conversion")
        class Response:
            headers = {}
            def __init__(self):
                self.done = False
            def read(self, _size=-1):
                if self.done:
                    return b""
                self.done = True
                return b"[00:01.00]safe"
            def __enter__(self): return self
            def __exit__(self, *_args): return False
        with patch("metadata_service._open_metadata_url", return_value=Response()):
            self.assertEqual(providers._text("https://example.invalid", limit=Exploding()), "[00:01.00]safe")

    def test_provider_http_error_response_is_closed_before_json_fallback(self):
        providers = MetadataProviders({})
        error = urllib.error.HTTPError("https://example.invalid", 500, "error", {}, io.BytesIO())
        with patch.object(error, "close", wraps=error.close) as close, \
             patch("metadata_service._open_metadata_url", side_effect=error):
            with self.assertRaises(urllib.error.HTTPError): providers._json("https://example.invalid")
        close.assert_called_once()

    def test_provider_json_request_preserves_bounded_post_body_and_headers(self):
        providers = MetadataProviders({})
        class Response:
            headers = {}
            def __init__(self):
                self.done = False
            def read(self, _size=-1):
                if self.done:
                    return b""
                self.done = True
                return b'{"ok":true}'
            def __enter__(self): return self
            def __exit__(self, *_args): return False
        with patch("metadata_service._open_metadata_url", return_value=Response()) as opener:
            self.assertEqual(providers._json(
                "https://example.invalid/lookup",
                {"Content-Type": "application/x-www-form-urlencoded"},
                data=b"fingerprint=abc",
            ), {"ok": True})
        request = opener.call_args.args[0]
        self.assertEqual(request.data, b"fingerprint=abc")
        self.assertEqual(request.get_header("Content-type"), "application/x-www-form-urlencoded")

    def test_acoustid_lookup_uses_compressed_form_post(self):
        providers = MetadataProviders({"metadata_fingerprint_enabled": True})
        track = {"path": "track.flac", "title": "Song", "artist": "Artist"}
        with patch("metadata_service.fingerprint_capability", return_value={"available": True}), \
             patch("metadata_service.audio_fingerprint", return_value={"duration": 12, "fingerprint": "abc"}), \
             patch.dict(os.environ, {"FNAUDIO_ACOUSTID_CLIENT_KEY": "client-key"}), \
             patch.object(providers, "_json", return_value={"results": []}) as request:
            providers.track_candidates(track)
        acoustid = next(call for call in request.call_args_list if call.args[0] == "https://api.acoustid.org/v2/lookup")
        _url, headers = acoustid.args[:2]
        body = acoustid.kwargs["data"]
        self.assertEqual(headers["Content-Encoding"], "gzip")
        self.assertEqual(
            urllib.parse.parse_qs(gzip.decompress(body).decode("ascii")),
            {"client": ["client-key"], "meta": ["recordings+releasegroups"], "duration": ["12"], "fingerprint": ["abc"]},
        )

    def test_acoustid_boolean_score_does_not_become_high_confidence(self):
        providers = MetadataProviders({"metadata_fingerprint_enabled": True})
        track = {"path": "track.flac", "title": "Song", "artist": "Artist"}
        payload = {
            "results": [{
                "score": True,
                "recordings": [{
                    "title": "Song",
                    "artists": [{"name": "Artist"}],
                    "releasegroups": [{"title": "Album"}],
                }],
            }],
        }
        with patch("metadata_service.fingerprint_capability", return_value={"available": True}), \
             patch("metadata_service.audio_fingerprint", return_value={"duration": 12, "fingerprint": "abc"}), \
             patch.object(providers, "_json", return_value=payload), \
             patch.object(providers, "_provider_is_available", return_value=False):
            result = providers.track_candidates(track)
        acoustid = next(item for item in result if item.get("source") == "acoustid")
        self.assertEqual(acoustid["confidence"], 0.95)

    def test_provider_http_error_response_is_closed_before_lyrics_fallback(self):
        providers = MetadataProviders({})
        error = urllib.error.HTTPError("https://example.invalid", 500, "error", {}, io.BytesIO())
        with patch.object(error, "close", wraps=error.close) as close, \
             patch("metadata_service._open_metadata_url", side_effect=error):
            with self.assertRaises(urllib.error.HTTPError): providers._text("https://example.invalid")
        close.assert_called_once()

    def test_job_error_projection_is_safe_for_non_text_values(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                conn.execute("INSERT INTO metadata_jobs(job_key,job_type,entity_key,payload_json,priority,status,attempts,next_attempt_at,updated_at,last_error) VALUES (?,?,?,?,?,?,?,?,?,?)", ("x", "track", "x", "{}", 1, "running", 1, 0, 0, ""))
            service._finish_job("x", "failed", object())
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT last_error FROM metadata_jobs WHERE job_key='x'").fetchone()[0], "")

    def test_late_job_completion_cannot_overwrite_reclaimed_attempt(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_jobs(job_key,job_type,entity_key,payload_json,priority,status,attempts,next_attempt_at,updated_at,last_error) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    ("x", "track", "x", "{}", 1, "running", 2, 0, 0, "new worker"),
                )
            service._finish_job("x", "done", "late", expected_attempts=1)
            service._retry_job("x", 1, "late", expected_attempts=1)
            with service._connect() as conn:
                row = conn.execute("SELECT status,attempts,last_error FROM metadata_jobs WHERE job_key='x'").fetchone()
            self.assertEqual((row[0], row[1], row[2]), ("running", 2, "new worker"))

    def test_apply_track_match_invalidates_visible_page_projection(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            fields = {"candidates": [{"title": "New title", "confidence": 0.8, "source": "test"}]}
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_track_matches(track_id,fields_json,source,provider_id,confidence,status,fetched_at,expires_at,orphaned_at) VALUES (?,?,?,?,?,?,?,?,0)",
                    ("track-1", json.dumps(fields), "test", "", 0.8, "review", 1, 9999999999),
                )
            with patch.object(service, "_queue_tag_write"):
                before = service.metadata_projection_revision
                self.assertTrue(service.apply_track_match("track-1"))
            self.assertEqual(service.metadata_projection_revision, before + 1)

    def test_provider_lyrics_uses_indexed_file_version_without_stat(self):
        providers = MetadataProviders({})
        track = {"path": "C:/music/song.mp3", "title": "Song", "artist": "Artist", "modified_ns": 7, "size": 42}
        with patch.object(providers, "_read_local_lyrics_cached", return_value="") as reader, \
             patch("metadata_service.os.stat", side_effect=AssertionError("indexed version should avoid stat")), \
             patch.object(providers, "netease_lyrics", return_value=None), \
             patch.object(providers, "qq_lyrics", return_value=None), \
             patch.object(providers, "kugou_lyrics", return_value=None), \
             patch.object(providers, "migu_lyrics", return_value=None), \
             patch.object(providers, "joox_lyrics", return_value=None), \
             patch.object(providers, "qianqian_lyrics", return_value=None):
            providers.lyrics(track)
        reader.assert_called_once_with(track["path"], (7, 42))

    def test_joox_album_skips_malformed_numeric_schema_fields(self):
        providers = MetadataProviders({})
        payload = {"section_list": [{
            "section_type": object(),
            "item_list": [{"type": object(), "album": {"id": "ignored"}}],
        }]}
        with patch.object(providers, "_json", return_value=payload):
            self.assertEqual(providers._joox_albums("Album"), ())

    def test_kugou_lyrics_hands_the_decoder_the_whole_base64_field(self):
        # Slicing the encoded field to the document budget used to look safe
        # because it stayed inside the byte ceiling afterwards. It is not: the
        # slice still decodes, into a shortened document whose tail is a split
        # multi-byte character, and the GB18030 fallback reads that mojibake as
        # valid text, so a corrupted lyric would be stored for good.
        seen = []
        providers = MetadataProviders({})
        song = {"SongName": "Song", "SingerName": "Artist", "FileHash": "hash"}
        with patch.object(providers, "_kugou_songs", return_value=[song]), \
             patch("metadata_service.provider_score", return_value=0.9), \
             patch.object(providers, "_json", side_effect=[{"candidates": [{"id": "1", "accesskey": "key"}]},
                                                           {"content": "A" * (MAX_PROVIDER_LYRICS_BASE64_CHARS + 400)}]), \
             patch("metadata_service._decode_base64_lyrics", side_effect=lambda value, *args: seen.append(value) or ""):
            self.assertIsNone(providers.kugou_lyrics({"title": "Song", "artist": "Artist"}))
        self.assertEqual(len(seen), 1)
        self.assertGreater(len(seen[0]), MAX_PROVIDER_LYRICS_BASE64_CHARS)

    def test_kugou_lyrics_refuses_an_over_budget_document(self):
        providers = MetadataProviders({})
        song = {"SongName": "Song", "SingerName": "Artist", "FileHash": "hash"}
        oversized = "A" * (MAX_PROVIDER_LYRICS_BASE64_CHARS + 4)
        with patch.object(providers, "_kugou_songs", return_value=[song]), \
             patch("metadata_service.provider_score", return_value=0.9), \
             patch.object(providers, "_json", side_effect=[{"candidates": [{"id": "1", "accesskey": "key"}]},
                                                           {"content": oversized}]):
            self.assertIsNone(providers.kugou_lyrics({"title": "Song", "artist": "Artist"}))

    def test_joox_lyrics_moves_to_the_next_candidate_on_an_over_budget_document(self):
        # One unusable candidate must not abort the bounded fallback list, which
        # is what an uncaught size rejection would do.
        providers = MetadataProviders({})
        first = {"id": "first", "name": "Song", "artist_list": [{"name": "Artist"}]}
        second = {"id": "second", "name": "Song", "artist_list": [{"name": "Artist"}]}
        oversized = {"code": 0, "lyric": "A" * (MAX_PROVIDER_LYRICS_BASE64_CHARS + 4)}
        recovered = {"code": 0, "lyric": base64.b64encode(b"[00:01.00]Recovered").decode("ascii")}
        with patch.object(providers, "_joox_songs", return_value=[first, second]), \
             patch("metadata_service.provider_score", side_effect=[0.9, 0.8]), \
             patch.object(providers, "_text", side_effect=[json.dumps(oversized), "cb(" + json.dumps(recovered) + ")"]):
            result = providers.joox_lyrics({"title": "Song", "artist": "Artist"})
        self.assertEqual(result["lyrics"], "[00:01.00]Recovered")
        self.assertEqual(result["provider_id"], "second")

    def test_joox_lyrics_skips_malformed_jsonp_candidate(self):
        providers = MetadataProviders({})
        first = {"id": "first", "name": "Song", "artist_list": [{"name": "Artist"}]}
        second = {"id": "second", "name": "Song", "artist_list": [{"name": "Artist"}]}
        valid = {"code": 0, "lyric": base64.b64encode(b"[00:01.00]Recovered").decode("ascii")}
        with patch.object(providers, "_joox_songs", return_value=[first, second]), \
             patch("metadata_service.provider_score", side_effect=[0.9, 0.8]), \
             patch.object(providers, "_text", side_effect=["not-json", "MusicJsonCallback(" + json.dumps(valid) + ")"]):
            result = providers.joox_lyrics({"title": "Song", "artist": "Artist"})
        self.assertEqual(result["lyrics"], "[00:01.00]Recovered")
        self.assertEqual(result["provider_id"], "second")

    def test_artwork_projection_accepts_only_sha256_hex_ids(self):
        self.assertTrue(valid_artwork_id("a" * 64))
        self.assertTrue(valid_artwork_id("A" * 64))
        self.assertFalse(valid_artwork_id("a" * 63))
        self.assertFalse(valid_artwork_id("../cover.jpg"))
        self.assertFalse(valid_artwork_id(None))

    def test_entity_cache_diagnostics_do_not_persist_unbounded_provider_payloads(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service._store_entity(
                "album", "album-key", {"name": "Album", "artist": "Artist"},
                {
                    "artist": "Artist", "release_date": "2026-09-15",
                    "source": "test", "provider_id": "provider",
                    "opaque_payload": "音" * (2 * 1024 * 1024),
                },
            )
            with service._connect() as conn:
                raw = conn.execute(
                    "SELECT raw_json FROM metadata_entities WHERE entity_type='album' AND entity_key='album-key'"
                ).fetchone()[0]
            self.assertLessEqual(len(raw.encode("utf-8")), metadata_service.MAX_ENTITY_RAW_JSON_BYTES)
            self.assertNotIn("opaque_payload", raw)
            self.assertEqual(json.loads(raw)["source"], "test")

    def test_download_artwork_ignores_malformed_cached_asset_id(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            path = os.path.join(root, "bad.jpg")
            with open(path, "wb") as handle:
                handle.write(b"\xff\xd8fixture")
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_assets(id,path,mime,size,source_url,fetched_at,last_accessed) VALUES (?,?,?,?,?,?,?)",
                    ("../bad", path, "image/jpeg", 9, "https://example.test/cover.jpg", int(time.time()), int(time.time())),
                )
            with patch("metadata_service._open_metadata_url") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.headers.get_content_type.return_value = "image/jpeg"
                response.read.side_effect = [b"\xff\xd8new", b""]
                result = service._download_artwork("https://example.test/cover.jpg")
            self.assertEqual(result, __import__("hashlib").sha256(b"\xff\xd8new").hexdigest())

    def test_apic_frame_persists_only_a_type_the_picture_supports(self):
        png = b"\x89PNG\r\n\x1a\ncover"
        frame = metadata_service._id3_apic_frame("image/png\r\nSet-Cookie: a=b", png)
        self.assertTrue(frame.startswith(b"APIC"))
        self.assertIn(b"\x03image/png\x00", frame)
        self.assertNotIn(b"Set-Cookie", frame)
        # An unusable declaration degrades to the historical JPEG default rather
        # than writing tagger free text into the user file.
        frame = metadata_service._id3_apic_frame("text/html", b"opaque-but-real-enough")
        self.assertIn(b"\x03image/jpeg\x00", frame)

    def test_download_artwork_stores_the_type_the_pixels_prove(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            png = b"\x89PNG\r\n\x1a\nprovider"
            with patch("metadata_service._open_metadata_url") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.headers.get_content_type.return_value = "image/svg+xml"
                response.read.side_effect = [png, b""]
                asset_id = service._download_artwork("https://example.test/cover")
            with service._connect() as conn:
                row = conn.execute("SELECT mime FROM metadata_assets WHERE id=?", (asset_id,)).fetchone()
            self.assertEqual(row[0], "image/png")

    def test_download_artwork_rejects_a_document_dressed_as_an_image(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with patch("metadata_service._open_metadata_url") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.headers.get_content_type.return_value = "image/svg+xml"
                response.read.side_effect = [b"<svg onload=alert(1)></svg>", b""]
                self.assertEqual(service._download_artwork("https://example.test/svg"), "")
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_assets").fetchone()[0], 0)

    def test_download_artwork_rejects_overlong_url_before_database_or_network_access(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with patch.object(service, "_connect") as connect, patch("metadata_service._open_metadata_url") as urlopen:
                self.assertEqual(service._download_artwork("https://example.test/" + ("x" * 2048)), "")
                connect.assert_not_called()
                urlopen.assert_not_called()

    def test_metadata_remote_url_rejection_happens_before_network_access(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with patch("metadata_service._open_metadata_url") as urlopen:
                self.assertEqual(service._download_artwork("http://127.0.0.1/private"), "")
                with self.assertRaises(ValueError):
                    service.providers._json("http://169.254.169.254/latest/meta-data")
                with self.assertRaises(ValueError):
                    service.providers._text("https://user:password@example.test/lyrics")
                urlopen.assert_not_called()

    def test_download_artwork_honors_active_provider_budget(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service.providers.begin_job_observation(1)
            with patch("metadata_service._open_metadata_url") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.headers.get_content_type.return_value = "image/jpeg"
                response.read.side_effect = [b"\xff\xd8new", b""]
                service._download_artwork("https://example.test/cover.jpg")
                timeout = urlopen.call_args.args[1]
                self.assertGreaterEqual(timeout, 1)
                self.assertLessEqual(timeout, 15)
            service.providers.end_job_observation()

    def test_download_artwork_accumulates_short_response_chunks(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with patch("metadata_service._open_metadata_url") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.headers.get_content_type.return_value = "image/jpeg"
                response.read.side_effect = [b"\xff\xd8", b"\xff\xd9", b""]
                result = service._download_artwork("https://example.test/short-chunks.jpg")
            expected = __import__("hashlib").sha256(b"\xff\xd8\xff\xd9").hexdigest()
            self.assertEqual(result, expected)

    def test_download_artwork_rejects_truncated_declared_response(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with patch("metadata_service._open_metadata_url") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.headers.get_content_type.return_value = "image/jpeg"
                response.headers.get.return_value = "4"
                response.read.side_effect = [b"\xff\xd8", b""]
                self.assertEqual(service._download_artwork("https://example.test/truncated.jpg"), "")

    def test_download_artwork_rejects_oversized_declared_response_before_reading(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with patch("metadata_service._open_metadata_url") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.headers.get_content_type.return_value = "image/jpeg"
                response.headers.get.return_value = str(MAX_ARTWORK_BYTES + 1)
                self.assertEqual(service._download_artwork("https://example.test/cover.jpg"), "")
                response.read.assert_not_called()

    def test_download_artwork_redownloads_when_cached_source_file_is_oversized(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            stale_path = os.path.join(root, "stale.jpg")
            with open(stale_path, "wb") as handle:
                handle.truncate(MAX_ARTWORK_BYTES + 1)
            cached_id = "a" * 64
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_assets(id,path,mime,size,source_url,fetched_at,last_accessed) VALUES (?,?,?,?,?,?,?)",
                    (cached_id, stale_path, "image/jpeg", MAX_ARTWORK_BYTES, "https://example.test/cover.jpg", int(time.time()), int(time.time())),
                )
            with patch("metadata_service._open_metadata_url") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.headers.get_content_type.return_value = "image/jpeg"
                response.read.side_effect = [b"\xff\xd8fresh", b""]
                result = service._download_artwork("https://example.test/cover.jpg")
            self.assertEqual(result, __import__("hashlib").sha256(b"\xff\xd8fresh").hexdigest())
            urlopen.assert_called_once()

    def test_download_artwork_uses_unique_temporary_file_and_cleans_failed_write(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            response = MagicMock()
            response.__enter__.return_value = response
            response.__exit__.return_value = False
            response.headers.get_content_type.return_value = "image/jpeg"
            response.read.side_effect = [b"\xff\xd8fresh", b""]
            artwork_root = service.artwork_dir
            with patch("metadata_service._open_metadata_url", return_value=response), patch.object(
                os, "replace", side_effect=OSError("replace failed")
            ):
                with self.assertRaises(OSError):
                    service._download_artwork("https://example.test/unique.jpg")
            self.assertEqual(
                [name for name in os.listdir(artwork_root) if name.endswith(".tmp")],
                [],
            )

    def test_download_artwork_closes_mkstemp_descriptor_when_fdopen_fails(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            response = MagicMock()
            response.__enter__.return_value = response
            response.__exit__.return_value = False
            response.headers.get_content_type.return_value = "image/jpeg"
            response.read.side_effect = [b"\xff\xd8fresh", b""]
            descriptor = 987654
            with patch("metadata_service._open_metadata_url", return_value=response), patch.object(
                tempfile, "mkstemp", return_value=(descriptor, os.path.join(service.artwork_dir, "failed.tmp"))
            ), patch.object(os, "fdopen", side_effect=OSError("fdopen failed")), patch.object(
                os, "close"
            ) as close:
                with self.assertRaises(OSError):
                    service._download_artwork("https://example.test/fdopen.jpg")
            close.assert_called_once_with(descriptor)

    def test_download_artwork_preserves_mkstemp_error_when_temp_file_creation_fails(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            response = MagicMock()
            response.__enter__.return_value = response
            response.__exit__.return_value = False
            response.headers.get_content_type.return_value = "image/jpeg"
            response.read.side_effect = [b"\xff\xd8fresh", b""]
            with patch(
                "metadata_service._open_metadata_url", return_value=response
            ), patch.object(tempfile, "mkstemp", side_effect=OSError("mkstemp failed")):
                with self.assertRaisesRegex(OSError, "mkstemp failed"):
                    service._download_artwork("https://example.test/mkstemp.jpg")

    def test_artwork_uses_bounded_actual_file_size_instead_of_stale_cache_size(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            asset_id = "a" * 64
            os.makedirs(service.artwork_dir, exist_ok=True)
            asset_path = os.path.join(service.artwork_dir, asset_id + ".jpg")
            with open(asset_path, "wb") as handle:
                handle.write(b"image")
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_assets(id,path,mime,size) VALUES (?,?,?,?)",
                    (asset_id, asset_path, "image/jpeg", 1),
                )
            asset = service.artwork(asset_id)
            self.assertEqual(asset["size"], 5)
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT size FROM metadata_assets WHERE id=?", (asset_id,)).fetchone()[0], 5)
            with open(asset_path, "wb") as handle:
                handle.truncate(MAX_ARTWORK_BYTES + 1)
            self.assertIsNone(service.artwork(asset_id))

    def test_an_unservable_asset_is_not_renewed_in_the_eviction_queue(self):
        # A row whose bytes open a document can only ever produce a 404, and reclamation
        # evicts by `last_accessed ASC` (see the pruning pass in metadata_service.py). The
        # bookkeeping used to happen before that decision, so every doomed request renewed the
        # row and pushed the assets no browser can display to the back of the queue, which is
        # the opposite of giving that cache space back (TODO.md:91).
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            asset_id = "b" * 64
            os.makedirs(service.artwork_dir, exist_ok=True)
            path = os.path.join(service.artwork_dir, asset_id + ".jpg")
            with open(path, "wb") as handle:
                handle.write(b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>')
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_assets(id,path,mime,size,last_accessed) VALUES (?,?,?,?,?)",
                    (asset_id, path, "image/jpeg", 1, 123),
                )
            self.assertIsNone(service.artwork(asset_id))
            with service._connect() as conn:
                row = conn.execute("SELECT last_accessed,mime FROM metadata_assets WHERE id=?", (asset_id,)).fetchone()
            self.assertEqual(row[0], 123, "an asset the route can only refuse was marked recently used")
            self.assertEqual(row[1], "image/jpeg", "the stored history row was rewritten as a side effect")
            # The same row with decodable pixels is served and does get renewed, and the type
            # handed to the caller is the one the bytes prove rather than the one stored: this
            # is about refusing to renew unservable assets, not about stopping the bookkeeping.
            with open(path, "wb") as handle:
                handle.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 24)
            asset = service.artwork(asset_id)
            self.assertEqual(asset["mime"], "image/png")
            self.assertGreater(asset["size"], 0)
            with service._connect() as conn:
                renewed = conn.execute("SELECT last_accessed FROM metadata_assets WHERE id=?", (asset_id,)).fetchone()[0]
                stored_after_serving = conn.execute("SELECT mime FROM metadata_assets WHERE id=?", (asset_id,)).fetchone()[0]
            self.assertGreater(renewed, 123)
            # Serving must not repair history as a side effect of a GET. Rewriting the row
            # here would cost a write transaction on every artwork request, and would make
            # the stored corpus depend on which tiles happened to be looked at; normalising
            # old rows is a migration's job, and the next real store overwrites the value.
            self.assertEqual(stored_after_serving, "image/jpeg", "a read path rewrote the stored row")

    def test_artwork_database_path_cannot_read_or_delete_outside_cache(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root, grace=0))
            asset_id = "d" * 64
            outside = os.path.join(root, "outside.jpg")
            with open(outside, "wb") as handle:
                handle.write(b"private")
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_assets(id,path,mime,size) VALUES (?,?,?,?)",
                    (asset_id, outside, "image/jpeg", 7),
                )
                service._cleanup_orphans(conn, int(time.time()))

            self.assertIsNone(service.artwork(asset_id))
            self.assertTrue(os.path.isfile(outside))
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_assets WHERE id=?", (asset_id,)).fetchone()[0], 0)

    def test_artwork_rejects_non_text_ids_without_stringifying(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))

            class Explosive:
                def __str__(self):
                    raise AssertionError("artwork id must not be stringified")

            self.assertIsNone(service.artwork(Explosive()))

    def test_metadata_track_entrypoints_reject_untrusted_ids_without_stringifying(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))

            class Explosive:
                def __str__(self):
                    raise AssertionError("track id must not be stringified")

            value = Explosive()
            self.assertEqual(service.track_match(value)["status"], "invalid")
            self.assertEqual(service.lyrics(value)["status"], "invalid")
            self.assertFalse(service.prioritize_track(value))
            self.assertFalse(service.apply_track_match(value))

    def test_metadata_track_entrypoints_reject_oversized_ids(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            oversized = "x" * 257
            self.assertEqual(service.track_match(oversized)["status"], "invalid")
            self.assertEqual(service.lyrics(oversized)["status"], "invalid")
            self.assertFalse(service.prioritize_track(oversized))
            self.assertFalse(service.apply_track_match(oversized))

    def test_track_artwork_replaces_malformed_existing_reference(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_tracks(track_id,lyrics,artwork_id,lyrics_source,provider_id,confidence,fetched_at,expires_at,orphaned_at) VALUES (?,?,?,?,?,?,?,?,0)",
                    ("t1", "", "../bad", "", "", 0.5, int(time.time()), int(time.time()) + 100),
                )
            valid = "b" * 64
            with patch.object(service, "_download_artwork", return_value=valid):
                self.assertTrue(service._store_track_artwork("t1", {"image_url": "https://example.test/cover.jpg", "source": "test"}))
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT artwork_id FROM metadata_tracks WHERE track_id='t1'").fetchone()[0], valid)

    def test_schema_migration_clears_malformed_artwork_ids_once(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                conn.execute("INSERT INTO metadata_tracks(track_id,artwork_id) VALUES ('bad','../cover')")
                conn.execute("INSERT INTO metadata_entities(entity_type,entity_key,name,artwork_id) VALUES ('album','bad','Album','xyz')")
                conn.execute("DELETE FROM metadata_state WHERE key='artwork_id_sanitize_version'")
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT artwork_id FROM metadata_tracks WHERE track_id='bad'").fetchone()[0], "")
                self.assertEqual(conn.execute("SELECT artwork_id FROM metadata_entities WHERE entity_key='bad'").fetchone()[0], "")

    def test_invalid_cached_artwork_does_not_suppress_priority_enrichment(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            service = MetadataService(config)
            music = os.path.join(root, "music", "Artist - Song.flac")
            with open(music, "wb") as handle:
                handle.write(b"fixture")
            save_items_to_sqlite(config, [self._item("t1", music, "Song", 1)], "first")
            with service._connect() as conn:
                conn.execute("INSERT INTO metadata_tracks(track_id,artwork_id) VALUES ('t1','../bad')")
            with patch.object(service, "_upsert_job") as queue:
                self.assertTrue(service.prioritize_track("t1"))
                keys = [call.args[1] for call in queue.call_args_list]
            self.assertIn("track:t1", keys)

    def test_lyrics_fast_path_drops_invalid_artwork_reference(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = os.path.join(root, "music", "Artist - Song.flac")
            with open(music, "wb") as handle:
                handle.write(b"fixture")
            save_items_to_sqlite(config, [self._item("t1", music, "Song", 1)], "first")
            service = MetadataService(config)
            with service._connect() as conn:
                conn.execute("UPDATE metadata_tracks SET lyrics='[00:01]x',artwork_id='../bad' WHERE track_id='t1'")
            with patch.object(service, "_read_local_lyrics_cached", return_value=""):
                result = service.lyrics("t1")
            self.assertEqual(result["image_url"], "")

    def test_lyrics_fast_path_projects_cached_album_artwork(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = os.path.join(root, "music", "Artist - Song.flac")
            with open(music, "wb") as handle:
                handle.write(b"fixture")
            item = self._item("t1", music, "Song", 1)
            item.update({"artist": "Featured Singer", "album_artist": "Release Artist"})
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            artwork_id = "e" * 64
            album_key = entity_key("album", item["album"], item["album_artist"])
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_tracks(track_id,lyrics,expires_at) VALUES (?,?,?)",
                    ("t1", "[00:01]cached", int(time.time()) + 60),
                )
                conn.execute(
                    "INSERT INTO metadata_entities(entity_type,entity_key,name,artist,artwork_id) VALUES ('album',?,?,?,?)",
                    (album_key, item["album"], item["album_artist"], artwork_id),
                )
            result = service.lyrics("t1")
            self.assertFalse(result["pending"])
            self.assertEqual(result["lyrics"], "[00:01]cached")
            self.assertEqual(result["image_url"], "metadata/artwork/" + artwork_id)

    def test_cached_entity_drops_invalid_artwork_reference(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                conn.execute("INSERT INTO metadata_entities(entity_type,entity_key,name,artwork_id) VALUES ('album','album:bad','Album','../bad')")
            self.assertEqual(service.cached_entity("album", "Album")["image_url"], "")

    def test_entity_and_lyrics_storage_reject_invalid_downloader_ids(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with patch.object(service, "_download_artwork", return_value="../bad"):
                service._store_entity("album", "album:one", {"name": "Album", "artist": "Artist"}, {"image_url": "https://example.test/a.jpg", "source": "test"})
                service._store_lyrics("track-1", {"lyrics": "[00:01]x", "image_url": "https://example.test/a.jpg", "source": "test"})
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT artwork_id FROM metadata_entities WHERE entity_key='album:one'").fetchone()[0], "")
                self.assertEqual(conn.execute("SELECT artwork_id FROM metadata_tracks WHERE track_id='track-1'").fetchone()[0], "")
    def _config(self, root, grace=7):
        music = os.path.join(root, "music")
        os.makedirs(music, exist_ok=True)
        return {
            "cache_dir": os.path.join(root, "cache"),
            "library_paths": [music],
            "metadata_enabled": True,
            # These service tests exercise the explicit tag-writer path. The
            # production default remains disabled; tests opt in deliberately.
            "metadata_tag_write_enabled": True,
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

    def test_provider_json_prefers_utf8_when_a_catalog_mislabels_the_charset(self):
        """A permissive latin-1 label must not turn a valid Chinese result into mojibake."""
        payload = '{"song":"周杰伦 - 威廉古堡"}'.encode("utf-8")
        result = _decode_provider_json(payload, "application/json; charset=iso-8859-1")
        self.assertEqual(result["song"], "周杰伦 - 威廉古堡")

    def test_lyrics_decoder_rejects_replacement_text(self):
        with self.assertRaisesRegex(ValueError, "replacement"):
            _decode_lyrics_text("[00:01.00]晴\ufffd天".encode("utf-8"))

    def test_lyrics_decoder_can_fall_back_after_a_bad_first_encoding(self):
        # The first UTF-8 attempt is intentionally invalid; GB18030 remains
        # a valid bounded fallback for legacy lyric exports.
        payload = "[00:01.00]晴天".encode("gb18030")
        self.assertEqual(_decode_lyrics_text(payload), "[00:01.00]晴天")

    def test_provider_json_accepts_only_bounded_jsonp_wrappers(self):
        payload = b'catalog.callback({"title":"Song","artist":"Artist"});'
        self.assertEqual(_decode_provider_json(payload, "application/javascript"), {
            "title": "Song", "artist": "Artist",
        })
        with self.assertRaises(ValueError):
            _decode_provider_json(b'alert("not json")', "application/javascript")

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

    def test_group_enrichment_bounds_projection_input_without_truncating_result(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))

            class ExplodingGroup(dict):
                def get(self, *_args, **_kwargs):
                    raise AssertionError("group enrichment read past its bounded prefix")

            groups = [{"name": "", "artist": ""} for _ in range(5000)]
            groups.extend(ExplodingGroup() for _ in range(1000))
            payload = {"groups": groups}

            result = service.enrich_groups("albums", payload)

            self.assertIs(result, payload)
            self.assertEqual(len(result["groups"]), 6000)

    def test_group_enrichment_batches_sqlite_parameters(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            groups = [
                {"name": "Album %04d" % index, "artist": "Artist %04d" % index}
                for index in range(1200)
            ]
            target = groups[1100]
            key = entity_key("album", target["name"], target["artist"])
            with service._connect() as conn:
                conn.execute(
                    """INSERT INTO metadata_entities(
                        entity_type,entity_key,name,artist,release_date,artwork_id,source,provider_id,confidence,fetched_at,expires_at,orphaned_at,raw_json
                    ) VALUES ('album',?,?,?,?,?,'musicbrainz','album-id',0.98,1,9999999999,0,'{}')""",
                    (key, target["name"], target["artist"], "2026-08-04", "a" * 64),
                )

            parameter_counts = []
            real_connect = service._connect

            class ObservedConnection:
                def __enter__(self):
                    self.managed = real_connect()
                    self.connection = self.managed.__enter__()
                    return self

                def __exit__(self, *args):
                    return self.managed.__exit__(*args)

                def execute(self, sql, parameters=()):
                    if "FROM metadata_entities" in sql:
                        parameter_counts.append(len(parameters))
                    return self.connection.execute(sql, parameters)

            with patch.object(service, "_connect", return_value=ObservedConnection()):
                result = service.enrich_groups("albums", {"groups": groups})

            self.assertEqual(result["groups"][1100]["metadata_source"], "musicbrainz")
            self.assertGreater(len(parameter_counts), 2)
            self.assertLessEqual(max(parameter_counts), 401)

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

    def test_lyrics_request_does_not_enqueue_database_writes_during_library_scan(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            save_items_to_sqlite(config, [self._item("one", os.path.join(music, "one.flac"), "One", 1)], "first")
            service = MetadataService(config)
            with patch("metadata_service.library_scan_is_running", return_value=True), \
                 patch.object(service, "_read_local_lyrics_cached", return_value=""):
                result = service.lyrics("one")
            self.assertEqual(result["status"], "scan_busy")
            with service._connect() as conn:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM metadata_jobs WHERE job_key='lyrics:one'").fetchone()[0],
                    0,
                )

    def test_lyrics_pending_projection_drops_invalid_artwork_reference(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            save_items_to_sqlite(config, [self._item("one", os.path.join(music, "one.flac"), "One", 1)], "first")
            service = MetadataService(config)
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_tracks(track_id,artwork_id,lyrics,expires_at,orphaned_at) VALUES (?,?,?,?,0)",
                    ("one", "../bad", "", 0),
                )
            with patch.object(service, "_read_local_lyrics_cached", return_value=""):
                result = service.lyrics("one")
            self.assertTrue(result["pending"])
            self.assertEqual(result["image_url"], "")

    def test_local_lyrics_hit_still_queues_missing_artwork(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            path = os.path.join(music, "one.flac")
            item = self._item("one", path, "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            with patch.object(service, "_read_local_lyrics_cached", return_value="[00:01.00]local"), \
                 patch.object(service, "_needs_track_enrichment", return_value=False), \
                 patch("metadata_service.has_local_artwork", return_value=False):
                result = service.lyrics("one")
            self.assertEqual(result["source"], "本地歌词")
            with service._connect() as conn:
                row = conn.execute("SELECT status,priority FROM metadata_jobs WHERE job_key='track:one'").fetchone()
            self.assertEqual(row["status"], "pending")
            self.assertEqual(row["priority"], 1)

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
                row = conn.execute("SELECT priority,status,payload_json FROM metadata_jobs WHERE job_key='lyrics:one'").fetchone()
                album = conn.execute("SELECT priority,status FROM metadata_jobs WHERE job_type='album'").fetchone()
                tag = conn.execute("SELECT priority,status FROM metadata_jobs WHERE job_key='tag:one'").fetchone()
            self.assertEqual(row["priority"], 0)
            self.assertEqual(row["status"], "pending")
            payload = json.loads(row["payload_json"])
            self.assertIsInstance(payload["modified_ns"], int)
            self.assertIsInstance(payload["size"], int)
            self.assertEqual(album["priority"], 1)
            self.assertEqual(tag["priority"], 2)

    def test_explicit_track_lookup_runs_when_background_enrichment_is_disabled(self):
        """The per-track UI lane must not depend on the opt-in library crawler."""
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            config["metadata_enabled"] = False
            config["metadata_tag_write_enabled"] = False
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            candidate = {
                "title": "Resolved One",
                "artist": "Example Artist",
                "album": "Resolved Album",
                "source": "fixture",
                "provider_id": "fixture-one",
                "confidence": 0.98,
            }
            try:
                with patch.object(service.providers, "track_candidates", return_value=[candidate]):
                    service.start()
                    pending = service.track_match("one")
                    self.assertTrue(pending["pending"])
                    for _ in range(60):
                        result = service.track_match("one")
                        if result and result.get("status") == "auto":
                            break
                        time.sleep(0.05)
                    else:
                        self.fail("explicit metadata lookup did not finish while background enrichment was disabled")
                self.assertEqual(result["best"]["album"], "Resolved Album")
            finally:
                service.shutdown()

    def test_explicit_retry_clears_provider_cooldown(self):
        providers = MetadataProviders({})
        providers._provider_cooldown_until["fixture"] = time.monotonic() + 60
        providers.reset_provider_cooldowns()
        self.assertEqual(providers._provider_cooldown_until, {})

    def test_track_match_poll_does_not_requeue_an_existing_pending_job(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            save_items_to_sqlite(config, [self._item("one", os.path.join(music, "one.flac"), "One", 1)], "first")
            service = MetadataService(config)
            with service._connect() as conn:
                service._upsert_job(conn, "track:one", "track", "one", {"title": "One"}, 1)
                conn.execute("UPDATE metadata_jobs SET updated_at=1 WHERE job_key='track:one'")
            result = service.track_match("one")
            self.assertTrue(result["pending"])
            with service._connect() as conn:
                row = conn.execute("SELECT status,updated_at FROM metadata_jobs WHERE job_key='track:one'").fetchone()
            self.assertEqual(row["status"], "pending")
            self.assertEqual(row["updated_at"], 1)

    def _provider_request_parked(self, service):
        """Hold every provider request at the module's single HTTP seam.

        What the `before provider finishes` tests pin is an *ordering*: the answer
        has to be `pending` while the job is still running, so that state must be a
        fact the test creates. Unpatched, the background workers called the real
        providers: the assertion raced live network latency, the round trip decided
        how long the test took, and the supposedly offline gate sent real HTTPS
        requests to seven music services.

        The gate cannot sit on one provider method: one lookup fans out into track,
        album and lyrics jobs, and patching a single entry point left its siblings
        dialing. ``_open_metadata_url`` is the only function that can put bytes on
        the wire, so that is where the hold belongs.

        Callers must open the gate before ``shutdown`` joins the workers; the join
        lasts exactly as long as the gate stays closed.
        """
        release = threading.Event()

        def parked(_request, *_args, **_kwargs):
            release.wait(10)
            raise urllib.error.URLError("fixture: provider held by the test")

        patcher = patch("metadata_service._open_metadata_url", side_effect=parked)
        seam = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(release.set)
        return release, seam

    def _deferred_lane_starts(self, service):
        """Replace the real lane start with a recorder of (lane, committed job count)."""
        starts = []

        def record(lane="fetch"):
            with service._connect() as conn:
                queued = conn.execute(
                    "SELECT count(*) FROM metadata_jobs WHERE status='pending'"
                ).fetchone()[0]
            starts.append((lane, queued))
            return True

        patcher = patch.object(metadata_service.MetadataService, "_start_lane", side_effect=record)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        mock.real_starts = starts
        return mock

    def _queued_service(self, root, track_id="lane"):
        config = self._config(root)
        music = config["library_paths"][0]
        save_items_to_sqlite(config, [self._item(track_id, os.path.join(music, track_id + ".flac"), "Lane", 1)], "first")
        return MetadataService(config)

    def test_first_lookup_on_a_fresh_database_does_not_wait_on_itself(self):
        """The queued-job transaction must not become the thing the pool waits for.

        Before the deferral, the first metadata lookup on a fresh (or version
        bumped) database took 5.7 s: the outer connection's migration write was
        still uncommitted, so the worker start's own migration write waited on it
        for the whole ``busy_timeout``.
        """
        with tempfile.TemporaryDirectory() as root:
            service = self._queued_service(root)
            gate, requests = self._provider_request_parked(service)
            began = time.perf_counter()
            try:
                result = service.track_match("lane")
                elapsed = time.perf_counter() - began
                self.assertTrue(result["pending"])
            finally:
                gate.set()
                service.shutdown()
            self.assertLess(elapsed, 1.0, "a first lookup must not pay a busy_timeout")
            self.assertTrue(requests.called, "the pool did not actually start")

    def test_metadata_write_lanes_pause_while_library_scan_holds_database(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with patch("metadata_service.library_scan_is_running", return_value=True):
                self.assertTrue(service._metadata_writes_paused())

    def test_job_state_write_retries_a_transient_sqlite_lock(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                service._upsert_job(conn, "track:locked", "track", "locked", {}, 1)
            original_connect = service._connect
            attempts = {"count": 0}

            @contextmanager
            def flaky_connect():
                attempts["count"] += 1
                if attempts["count"] == 1:
                    raise sqlite3.OperationalError("database is locked")
                with original_connect() as conn:
                    yield conn

            with patch.object(service, "_connect", flaky_connect):
                service._finish_job("track:locked", "done", "")
            self.assertEqual(attempts["count"], 2)
            with service._connect() as conn:
                self.assertEqual(
                    conn.execute("SELECT status FROM metadata_jobs WHERE job_key='track:locked'").fetchone()[0],
                    "done",
                )

    def test_a_lane_requested_inside_a_transaction_starts_after_the_commit(self):
        with tempfile.TemporaryDirectory() as root:
            service = self._queued_service(root)
            starts = self._deferred_lane_starts(service)
            with service._connect() as conn:
                service._upsert_job(conn, "track:lane", "track", "lane", {"title": "Lane"}, 1, True)
                self.assertTrue(service.ensure_workers("fetch"))
                self.assertTrue(service.ensure_workers("fetch"))
                self.assertEqual(starts.real_starts, [], "the lane cannot start while its own job is uncommitted")
            self.assertEqual([entry[0] for entry in starts.real_starts], ["fetch"], "started once, after the commit")
            self.assertGreaterEqual(starts.real_starts[0][1], 1, "the worker starts with its job visible")

    def test_a_deferred_lane_starts_even_when_the_transaction_fails(self):
        with tempfile.TemporaryDirectory() as root:
            service = self._queued_service(root)
            starts = self._deferred_lane_starts(service)
            with self.assertRaises(RuntimeError):
                with service._connect() as conn:
                    service._upsert_job(conn, "track:lane", "track", "lane", {"title": "Lane"}, 1, True)
                    service.ensure_workers("lyrics")
                    raise RuntimeError("request body failed")
            self.assertEqual([entry[0] for entry in starts.real_starts], ["lyrics"])

    def test_each_lane_requested_in_one_transaction_starts(self):
        with tempfile.TemporaryDirectory() as root:
            service = self._queued_service(root)
            starts = self._deferred_lane_starts(service)
            with service._connect():
                service.ensure_workers("fetch")
                service.ensure_workers("lyrics")
            self.assertEqual(sorted(entry[0] for entry in starts.real_starts), ["fetch", "lyrics"])

    def test_a_lane_started_outside_a_transaction_still_starts_immediately(self):
        with tempfile.TemporaryDirectory() as root:
            service = self._queued_service(root)
            starts = self._deferred_lane_starts(service)
            self.assertTrue(service.ensure_workers("fetch"))
            self.assertEqual([entry[0] for entry in starts.real_starts], ["fetch"])

    def test_a_failing_lane_start_is_recorded_and_does_not_rewrite_the_response(self):
        with tempfile.TemporaryDirectory() as root:
            service = self._queued_service(root)
            with patch.object(metadata_service.MetadataService, "_start_lane",
                              side_effect=OSError("thread limit")) as start:
                with service._connect() as conn:
                    service._upsert_job(conn, "track:lane", "track", "lane", {"title": "Lane"}, 1, True)
                    self.assertTrue(service.ensure_workers("fetch"))
            start.assert_called_once()
            self.assertIn("metadata worker startup deferred", service.last_error)

    def test_track_match_pending_exposes_local_tags_before_provider_finishes(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("tagged", os.path.join(music, "tagged.flac"), "Tagged title", 1)
            item.update({"artist": "Tagged artist", "album": "Tagged album", "album_artist": "Tagged artist", "genre": "Pop"})
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            gate, requests = self._provider_request_parked(service)
            try:
                result = service.track_match("tagged")
                self.assertTrue(result["pending"])
                self.assertEqual(result["best"]["title"], "Tagged title")
                self.assertEqual(result["best"]["album"], "Tagged album")
                self.assertEqual(result["best"]["source"], "local")
            finally:
                gate.set()
                service.shutdown()
            self.assertTrue(requests.called, "the answer was only pending because a request was in flight")

    def test_track_match_pending_projects_independent_cached_artwork(self):
        """Artwork/lyrics caches remain visible before a match row exists."""
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("cached-art", os.path.join(music, "cached-art.flac"), "Cached art", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            artwork_id = "b" * 64
            gate, requests = self._provider_request_parked(service)
            try:
                with service._connect() as conn:
                    conn.execute(
                        "INSERT INTO metadata_tracks(track_id,lyrics,artwork_id,lyrics_source) VALUES (?,?,?,?)",
                        ("cached-art", "[00:01.00]Cached lyric", artwork_id, "fixture"),
                    )
                result = service.track_match("cached-art")
                self.assertTrue(result["pending"])
                self.assertEqual(result["image_url"], "metadata/artwork/" + artwork_id)
                self.assertEqual(result["lyrics"], "[00:01.00]Cached lyric")
            finally:
                gate.set()
                service.shutdown()
            self.assertTrue(requests.called, "the projection had to survive a request in flight")

    def test_track_match_repairs_empty_success_projection_without_hiding_cache(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("empty-success", os.path.join(music, "empty-success.flac"), "Empty success", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            artwork_id = "c" * 64
            try:
                with service._connect() as conn:
                    conn.execute(
                        "INSERT INTO metadata_track_matches(track_id,fields_json,status,fetched_at,expires_at) VALUES (?,?,?,?,?)",
                        ("empty-success", '{"best":{},"candidates":[]}', "auto", int(time.time()), int(time.time()) + 3600),
                    )
                    conn.execute(
                        "INSERT INTO metadata_tracks(track_id,lyrics,artwork_id,lyrics_source) VALUES (?,?,?,?)",
                        ("empty-success", "[00:02.00]Recovered", artwork_id, "fixture"),
                    )
                result = service.track_match("empty-success")
                self.assertTrue(result["pending"])
                self.assertEqual(result["image_url"], "metadata/artwork/" + artwork_id)
                self.assertEqual(result["lyrics"], "[00:02.00]Recovered")
            finally:
                service.shutdown()

    def test_terminal_no_match_preserves_local_tags_before_filename_fallback(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("tagged", os.path.join(music, "Filename Artist - Filename title.flac"), "Tagged title", 1)
            item.update({"artist": "Tagged artist", "album": "Tagged album", "album_artist": "Tagged artist"})
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            with service._connect() as conn:
                conn.execute(
                    """INSERT INTO metadata_track_matches(
                       track_id,fields_json,source,provider_id,confidence,status,
                       fetched_at,expires_at,orphaned_at)
                       VALUES (?,?,?,?,?,?,?,?,0)""",
                    ("tagged", "{}", "", "", 0, "no_match", int(time.time()), int(time.time()) + 60),
                )
            result = service.track_match("tagged")
            self.assertEqual(result["status"], "no_match")
            self.assertEqual(result["best"]["title"], "Tagged title")
            self.assertEqual(result["best"]["artist"], "Tagged artist")
            self.assertEqual(result["best"]["album"], "Tagged album")
            self.assertEqual(result["best"]["source"], "local")

    def test_lyrics_poll_does_not_requeue_an_existing_pending_job(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            save_items_to_sqlite(config, [self._item("one", os.path.join(music, "one.flac"), "One", 1)], "first")
            service = MetadataService(config)
            with service._connect() as conn:
                service._upsert_job(conn, "lyrics:one", "lyrics", "one", {"title": "One"}, 0)
                conn.execute("UPDATE metadata_jobs SET updated_at=1 WHERE job_key='lyrics:one'")
            with patch.object(service, "_read_local_lyrics_cached", return_value=""):
                result = service.lyrics("one")
            self.assertTrue(result["pending"])
            with service._connect() as conn:
                row = conn.execute("SELECT status,updated_at FROM metadata_jobs WHERE job_key='lyrics:one'").fetchone()
            self.assertEqual(row["status"], "pending")
            self.assertEqual(row["updated_at"], 1)

    def test_two_recovery_rounds_do_not_give_two_workers_the_same_name(self):
        # Names are the only handle a thread dump gives you.  `range(count)` restarted
        # at zero every round, so after two recoveries `threading.enumerate()` showed
        # two threads called `fnaudio-metadata-fetch-recovery-0` and a real-device
        # investigation could not say which round started which worker.  Threads are
        # recorded instead of started: a live pool from a previous round would keep the
        # temporary database open past the test.
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            service = MetadataService(config)
            self.addCleanup(service.shutdown)
            started = []

            class Recorded:
                def __init__(self, name):
                    self.name = name
                    self.daemon = True

                def start(self):
                    started.append(self.name)

                def is_alive(self):
                    return False

            dead = type("Dead", (), {"is_alive": lambda _self: False})

            def build(_target=None, name="", **_kwargs):
                return Recorded(name)

            with patch("metadata_service.threading.Thread", side_effect=build):
                for _round in range(3):
                    service.fetch_threads = [dead()]
                    service.priority_thread = dead()
                    self.assertTrue(service._start_lane("fetch"))
            recovery = [name for name in started if "recovery-" in name]
            self.assertGreaterEqual(len(recovery), 6, "expected several workers across the rounds")
            self.assertEqual(len(set(recovery)), len(recovery),
                             "recovery rounds reused thread names: %s" % sorted(recovery))
            self.assertEqual([name for name in started if name == "fnaudio-metadata-priority"],
                             ["fnaudio-metadata-priority"] * 3,
                             "the single priority worker is replaced, never duplicated")
            for name in recovery:
                self.assertRegex(name, r"^fnaudio-metadata-fetch-recovery-\d+$")

    def test_lyrics_lookup_recovers_started_dead_workers_when_queuing_new_job(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            save_items_to_sqlite(config, [self._item("one", os.path.join(music, "one.flac"), "One", 1)], "first")
            service = MetadataService(config)
            # A started service with dead workers must lazily recover when a
            # lyrics request creates the priority job.
            service.fetch_threads = [type("Dead", (), {"is_alive": lambda _self: False})()]
            service.priority_thread = type("Dead", (), {"is_alive": lambda _self: False})()
            with patch.object(service, "ensure_workers", return_value=True) as recover, \
                 patch.object(service, "_read_local_lyrics_cached", return_value=""):
                result = service.lyrics("one")
            self.assertTrue(result["pending"])
            recover.assert_any_call("lyrics")

    def test_lyrics_auto_retry_recovers_started_dead_workers(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            save_items_to_sqlite(config, [self._item("one", os.path.join(music, "one.flac"), "One", 1)], "first")
            service = MetadataService(config)
            service.fetch_threads = [type("Dead", (), {"is_alive": lambda _self: False})()]
            service.priority_thread = type("Dead", (), {"is_alive": lambda _self: False})()
            with service._connect() as conn:
                service._upsert_job(conn, "lyrics:one", "lyrics", "one", {"title": "One"}, 0)
                conn.execute("UPDATE metadata_jobs SET status='failed',updated_at=1 WHERE job_key='lyrics:one'")
            with patch.object(service, "ensure_workers", return_value=True) as recover, \
                 patch.object(service, "_read_local_lyrics_cached", return_value=""):
                result = service.lyrics("one")
            self.assertTrue(result["pending"])
            recover.assert_any_call("lyrics")

    def test_upsert_promotes_active_job_without_resetting_its_fifo_or_backoff(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                service._upsert_job(conn, "track:one", "track", "one", {"title": "Old"}, 80)
                conn.execute(
                    "UPDATE metadata_jobs SET status='retry',attempts=3,next_attempt_at=1234,updated_at=17,last_error='temporary' WHERE job_key='track:one'"
                )
                service._upsert_job(conn, "track:one", "track", "one", {"title": "Fresh"}, 1, True)
                row = conn.execute(
                    "SELECT payload_json,priority,status,attempts,next_attempt_at,updated_at,last_error FROM metadata_jobs WHERE job_key='track:one'"
                ).fetchone()
            self.assertEqual(json.loads(row["payload_json"])["title"], "Fresh")
            self.assertEqual(row["priority"], 1)
            self.assertEqual(row["status"], "retry")
            self.assertEqual(row["attempts"], 3)
            self.assertEqual(row["next_attempt_at"], 1234)
            self.assertEqual(row["updated_at"], 17)
            self.assertEqual(row["last_error"], "temporary")

    def test_upsert_job_projects_large_library_json_out_of_worker_payload(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                service._upsert_job(
                    conn,
                    "lyrics:one",
                    "lyrics",
                    "one",
                    {
                        "title": "One",
                        "path": "/music/one.flac",
                        "modified_ns": 1,
                        "size": 2,
                        "item_json": "音" * (2 * 1024 * 1024),
                    },
                    1,
                )
                row = conn.execute("SELECT payload_json FROM metadata_jobs WHERE job_key='lyrics:one'").fetchone()
            payload = json.loads(row["payload_json"])
            self.assertNotIn("item_json", payload)
            self.assertEqual(payload["title"], "One")
            self.assertEqual(payload["modified_ns"], 1)

    def test_parallel_job_completion_keeps_the_other_active_job_visible(self):
        service = MetadataService(self._config(tempfile.gettempdir()))
        service._mark_job_active("lyrics:one")
        service._mark_job_active("track:two")
        service._clear_active_job("lyrics:one")

        self.assertEqual(service._active_job_snapshot(), "track:two")
        self.assertEqual(service.active_job, "track:two")

        service._clear_active_job("track:two")
        self.assertEqual(service._active_job_snapshot(), "")

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

    def test_corrupt_json_roots_do_not_break_track_match_or_tag_data(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            save_items_to_sqlite(config, [self._item("one", os.path.join(music, "one.flac"), "One", 1)], "first")
            service = MetadataService(config)
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_track_matches(track_id,fields_json,status,fetched_at,expires_at) VALUES (?,?,?,?,?)",
                    ("one", "[]", "auto", 0, 0),
                )
                conn.execute("UPDATE tracks SET item_json='[]' WHERE id='one'")
                self.assertEqual(service._track_match_fields(conn, "one"), {})
            data = service._tag_data("one")
            self.assertIsNotNone(data)
            self.assertEqual(data["title"], "One")

    def test_track_match_projects_cached_artwork_for_restored_current_track(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            candidate = {"title": "One", "artist": "Artist", "album": "Album", "source": "fixture", "confidence": 0.98}
            service._store_track_match("one", [candidate])
            artwork_id = "a" * 64
            with service._connect() as conn:
                conn.execute("INSERT INTO metadata_tracks(track_id, artwork_id) VALUES (?, ?)", ("one", artwork_id))
            result = service.track_match("one")
            self.assertEqual(result["status"], "auto")
            self.assertEqual(result["image_url"], "metadata/artwork/" + artwork_id)

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

    def test_apply_track_match_rejects_non_integer_indices_without_truncating(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service._store_track_match("missing-track", [{"title": "One", "source": "qq", "confidence": 0.93}])
            self.assertFalse(service.apply_track_match("missing-track", 0.9))
            self.assertFalse(service.apply_track_match("missing-track", True))
            self.assertFalse(service.apply_track_match("missing-track", ""))

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
        self.assertGreaterEqual(providers.activity_snapshot()["netease"]["successes"], 1)

    def test_track_candidates_exposes_filename_artist_when_title_tag_is_partial(self):
        providers = MetadataProviders({})
        track = {
            "title": "Song Title",
            "artist": "",
            "album": "",
            "path": "/music/Artist Name - Song Title.flac",
        }
        with patch.object(providers, "_musicbrainz_recordings", return_value=[]), \
             patch.object(providers, "_json", return_value={}), \
             patch.object(providers, "_qq_songs", return_value=[]), \
             patch.object(providers, "_kugou_songs", return_value=[]), \
             patch.object(providers, "_migu_songs", return_value=[]), \
             patch.object(providers, "_joox_songs", return_value=[]), \
             patch.object(providers, "_qianqian_songs", return_value=[]):
            candidates = providers.track_candidates(track)
        self.assertTrue(candidates)
        self.assertEqual(candidates[0]["source"], "filename")
        self.assertEqual(candidates[0]["artist"], "Artist Name")
        self.assertEqual(candidates[0]["title"], "Song Title")
        self.assertLess(candidates[0]["confidence"], 0.7)

    def test_track_candidates_reuses_short_lived_positive_cache(self):
        providers = MetadataProviders({})
        track = {"title": "One", "artist": "Example Artist", "duration": 180}
        payload = {"result": {"songs": [{
            "id": 88, "name": "One", "artists": [{"name": "Example Artist"}],
            "duration": 180000, "album": {"name": "Album", "artists": [{"name": "Example Artist"}], "picUrl": "https://example.test/a.jpg"},
        }]}}
        with patch.object(providers, "_json", return_value=payload) as request, \
             patch.object(providers, "_qq_songs", return_value=[]), \
             patch.object(providers, "_kugou_songs", return_value=[]), \
             patch.object(providers, "_migu_songs", return_value=[]), \
             patch.object(providers, "_joox_songs", return_value=[]), \
             patch.object(providers, "_qianqian_songs", return_value=[]):
            first = providers.track_candidates(track)
            calls_after_first = request.call_count
            second = providers.track_candidates(track)
        self.assertEqual(first, second)
        self.assertEqual(request.call_count, calls_after_first)
        self.assertGreater(calls_after_first, 0)
        cache = providers.candidate_cache_snapshot()
        self.assertEqual(cache["hits"], 1)
        self.assertEqual(cache["entries"], 1)

    def test_candidate_cache_separates_filename_identity_for_partial_tags(self):
        providers = MetadataProviders({})
        first_track = {
            "title": "One", "artist": "", "album": "", "duration": 180,
            "path": "/music/Artist A - One.flac",
        }
        second_track = {
            "title": "One", "artist": "", "album": "", "duration": 180,
            "path": "/music/Artist B - One.flac",
        }
        with patch.object(providers, "_json", return_value={}), \
             patch.object(providers, "_qq_songs", return_value=[]), \
             patch.object(providers, "_kugou_songs", return_value=[]), \
             patch.object(providers, "_migu_songs", return_value=[]), \
             patch.object(providers, "_joox_songs", return_value=[]), \
             patch.object(providers, "_qianqian_songs", return_value=[]):
            first = providers.track_candidates(first_track)
            second = providers.track_candidates(second_track)

        self.assertEqual(first[0]["artist"], "Artist A")
        self.assertEqual(second[0]["artist"], "Artist B")
        cache = providers.candidate_cache_snapshot()
        self.assertEqual(cache["hits"], 0)
        self.assertEqual(cache["entries"], 2)

    def test_candidate_cache_snapshot_recovers_from_malformed_counters(self):
        providers = MetadataProviders({})
        providers._candidate_cache_hits = object()
        providers._candidate_cache_misses = float("nan")
        snapshot = providers.candidate_cache_snapshot()
        self.assertEqual(snapshot["hits"], 0)
        self.assertEqual(snapshot["misses"], 0)
        # A subsequent cache access must also repair the counter boundary
        # instead of raising while recording a hit/miss.
        providers._candidate_cache_hits = object()
        providers._candidate_cache_misses = object()
        with patch.object(providers, "_json", return_value={}):
            providers.track_candidates({"title": "One", "artist": "Example"})
        self.assertLessEqual(providers.candidate_cache_snapshot()["misses"], 1000000)

    def test_candidate_cache_discards_malformed_entry_and_retries_provider(self):
        providers = MetadataProviders({})
        track = {"title": "One", "artist": "Example Artist", "duration": 180}
        payload = {"result": {"songs": [{
            "id": 88, "name": "One", "artists": [{"name": "Example Artist"}],
            "duration": 180000, "album": {"name": "Album", "artists": [{"name": "Example Artist"}]},
        }]}}
        with patch.object(providers, "_json", return_value=payload) as request, \
             patch.object(providers, "_qq_songs", return_value=[]), \
             patch.object(providers, "_kugou_songs", return_value=[]), \
             patch.object(providers, "_migu_songs", return_value=[]), \
             patch.object(providers, "_joox_songs", return_value=[]), \
             patch.object(providers, "_qianqian_songs", return_value=[]):
            providers.track_candidates(track)
            cache_key = next(iter(providers._candidate_cache))
            providers._candidate_cache[cache_key] = (object(), [])
            calls_before_retry = request.call_count
            providers.track_candidates(track)

        self.assertGreater(request.call_count, calls_before_retry)
        self.assertEqual(providers.candidate_cache_snapshot()["entries"], 1)
        self.assertGreaterEqual(providers.candidate_cache_snapshot()["misses"], 2)

    def test_candidate_cache_copy_does_not_block_status_reads(self):
        providers = MetadataProviders({})
        track = {"title": "One", "artist": "Example Artist", "duration": 180}
        hinted_artist, hinted_title = metadata_service.filename_track_hint(track)
        cache_key = metadata_service.build_candidate_cache_key(
            track,
            query=metadata_service.track_search_query(track),
            hinted_artist=hinted_artist,
            hinted_title=hinted_title,
        )
        with providers._candidate_cache_lock:
            providers._candidate_cache[cache_key] = (time.monotonic(), [{"title": "One"}])
        entered = threading.Event()
        release = threading.Event()

        def blocked_deepcopy(value):
            entered.set()
            release.wait(2)
            return list(value)

        with patch("metadata_service.copy.deepcopy", side_effect=blocked_deepcopy):
            reader = threading.Thread(target=lambda: providers.track_candidates(track))
            reader.start()
            self.assertTrue(entered.wait(1))
            started = time.monotonic()
            providers.candidate_cache_snapshot()
            self.assertLess(time.monotonic() - started, 0.25)
            release.set()
            reader.join(2)
            self.assertFalse(reader.is_alive())

    def test_candidate_cache_copy_does_not_return_entry_replaced_during_copy(self):
        providers = MetadataProviders({})
        track = {"title": "One", "artist": "Example Artist", "duration": 180}
        hinted_artist, hinted_title = metadata_service.filename_track_hint(track)
        cache_key = metadata_service.build_candidate_cache_key(
            track,
            query=metadata_service.track_search_query(track),
            hinted_artist=hinted_artist,
            hinted_title=hinted_title,
        )
        with providers._candidate_cache_lock:
            providers._candidate_cache[cache_key] = (time.monotonic(), [{"title": "Old"}])
        entered = threading.Event()
        release = threading.Event()

        def blocked_deepcopy(value):
            entered.set()
            release.wait(2)
            return list(value)

        with patch("metadata_service.copy.deepcopy", side_effect=blocked_deepcopy), \
             patch.object(providers, "_musicbrainz_recordings", return_value=[]), \
             patch.object(providers, "_json", return_value={}), \
             patch.object(providers, "_qq_songs", return_value=[]), \
             patch.object(providers, "_kugou_songs", return_value=[]), \
             patch.object(providers, "_migu_songs", return_value=[]), \
             patch.object(providers, "_joox_songs", return_value=[]), \
             patch.object(providers, "_qianqian_songs", return_value=[]):
            result = []
            reader = threading.Thread(target=lambda: result.append(providers.track_candidates(track)))
            reader.start()
            self.assertTrue(entered.wait(1))
            with providers._candidate_cache_lock:
                providers._candidate_cache[cache_key] = (time.monotonic(), [{"title": "New"}])
            release.set()
            reader.join(2)
        self.assertFalse(reader.is_alive())
        self.assertEqual(result, [[]])
        self.assertEqual(providers.candidate_cache_snapshot()["hits"], 0)

    def test_track_candidates_skip_schema_drift_and_use_next_provider(self):
        providers = MetadataProviders({})
        track = {"title": "One", "artist": "Example Artist", "duration": 180}
        kugou_item = {
            "SongName": "One", "SingerName": "Example Artist",
            "AlbumName": "Resolved Album", "FileHash": "song-hash",
            "Image": "https://example.test/{size}/cover.jpg",
        }
        with patch.object(providers, "_json", return_value={}), \
             patch.object(providers, "_qq_songs", return_value={"error": "unexpected shape"}), \
             patch.object(providers, "_kugou_songs", return_value=[kugou_item]), \
             patch.object(providers, "_migu_songs", return_value=[]), \
             patch.object(providers, "_joox_songs", return_value=[]), \
             patch.object(providers, "_qianqian_songs", return_value=[]):
            candidates = providers.track_candidates(track)
        self.assertEqual(candidates[0]["source"], "kugou")
        self.assertIn("qq", providers.failure_snapshot())

    def test_track_candidates_cache_key_ignores_untrusted_non_text_fields(self):
        providers = MetadataProviders({})

        class ExplodingValue:
            def __str__(self):
                raise AssertionError("cache key must not stringify arbitrary values")

        track = {
            "title": "One",
            "artist": "Example Artist",
            "album": ExplodingValue(),
            "duration": ExplodingValue(),
        }
        with patch.object(providers, "_json", return_value={}), \
             patch.object(providers, "_qq_songs", return_value=[]), \
             patch.object(providers, "_kugou_songs", return_value=[]), \
             patch.object(providers, "_migu_songs", return_value=[]), \
             patch.object(providers, "_joox_songs", return_value=[]), \
             patch.object(providers, "_qianqian_songs", return_value=[]):
            self.assertIsInstance(providers.track_candidates(track), list)

    def test_track_candidate_ignores_untrusted_local_fields(self):
        providers = MetadataProviders({})
        class Exploding:
            def __str__(self):
                raise AssertionError("must not stringify local tag")
        candidate = providers._track_candidate(
            {"title": Exploding(), "artist": Exploding(), "album": Exploding(), "duration": Exploding()},
            {}, "test", "Song", "Artist", "Album",
        )
        self.assertEqual(candidate["title"], "Song")

    def test_track_candidates_record_empty_source_and_continue_to_fallback(self):
        providers = MetadataProviders({})
        track = {"title": "One", "artist": "Example Artist", "duration": 180}
        kugou_item = {
            "SongName": "One", "SingerName": "Example Artist",
            "AlbumName": "Resolved Album", "FileHash": "song-hash",
        }
        with patch.object(providers, "_json", return_value={}), \
             patch.object(providers, "_qq_songs", return_value=[]), \
             patch.object(providers, "_kugou_songs", return_value=[kugou_item]), \
             patch.object(providers, "_migu_songs", return_value=[]), \
             patch.object(providers, "_joox_songs", return_value=[]), \
             patch.object(providers, "_qianqian_songs", return_value=[]):
            candidates = providers.track_candidates(track)
        self.assertEqual(candidates[0]["source"], "kugou")
        activity = providers.activity_snapshot()
        self.assertGreaterEqual(activity["qq"]["empty_results"], 1)
        self.assertEqual(activity["qq"].get("no_valid_candidates", 0), 0)
        self.assertNotIn("qq", providers._provider_successes)

    def test_track_candidates_empty_source_does_not_clear_failure_cooldown(self):
        providers = MetadataProviders({})
        providers._provider_failures["qq"] = {"count": 2, "last_error": "timeout", "last_at": 1}
        providers._provider_cooldown_until["qq"] = 9999999999
        with patch.object(providers, "_qq_songs", return_value=[]), \
             patch.object(providers, "_provider_is_available", side_effect=lambda name: name == "qq"), \
             patch.object(providers, "_record_provider_success") as success:
            providers.track_candidates({"title": "One", "artist": "Artist"})
        success.assert_not_called()
        self.assertIn("qq", providers._provider_cooldown_until)

    def test_track_candidates_record_unusable_source_and_continue_to_fallback(self):
        providers = MetadataProviders({})
        track = {"title": "One", "artist": "Example Artist", "duration": 180}
        unusable = None
        kugou_item = {
            "SongName": "One", "SingerName": "Example Artist",
            "AlbumName": "Resolved Album", "FileHash": "song-hash",
        }
        with patch.object(providers, "_json", return_value={}), \
             patch.object(providers, "_qq_songs", return_value=[unusable]), \
             patch.object(providers, "_kugou_songs", return_value=[kugou_item]), \
             patch.object(providers, "_migu_songs", return_value=[]), \
             patch.object(providers, "_joox_songs", return_value=[]), \
             patch.object(providers, "_qianqian_songs", return_value=[]):
            candidates = providers.track_candidates(track)
        self.assertEqual(candidates[0]["source"], "kugou")
        self.assertGreaterEqual(providers.activity_snapshot()["qq"]["no_valid_candidates"], 1)

    def test_provider_diagnostics_have_bounded_internal_state(self):
        providers = MetadataProviders({})
        for index in range(40):
            providers._record_provider_failure("drift-failure-%02d" % index, RuntimeError("boom"))
            providers._record_provider_failure("drift-failure-%02d" % index, RuntimeError("boom"))
        names = set(providers._provider_failures) | set(providers._provider_successes) | set(providers._provider_empty_results) | set(providers._provider_no_valid_candidates) | set(providers._provider_cooldown_until)
        self.assertLessEqual(len(names), 32)
        self.assertLessEqual(len(providers._provider_failures), 32)
        self.assertLessEqual(len(providers._provider_successes), 32)
        self.assertLessEqual(len(providers._provider_cooldown_until), 32)
        self.assertNotIn("drift-failure-00", providers._provider_failures)
        self.assertIn("drift-failure-39", providers._provider_failures)
        self.assertTrue(set(providers._provider_cooldown_until).issubset(providers._provider_failures))

        for index in range(40):
            providers._record_provider_success("drift-success-%02d" % index)
        names = set(providers._provider_failures) | set(providers._provider_successes) | set(providers._provider_empty_results) | set(providers._provider_no_valid_candidates) | set(providers._provider_cooldown_until)
        self.assertLessEqual(len(names), 32)
        self.assertIn("drift-success-39", providers._provider_successes)

        # Corrupt mutable counters must be repaired at mutation time too;
        # status projection alone is not enough because the next provider
        # response would otherwise raise before it can be diagnosed.
        repair = MetadataProviders({})
        repair._provider_successes["qq"] = {"count": object(), "last_at": 0}
        repair._provider_empty_results["qq"] = object()
        repair._provider_no_valid_candidates["qq"] = float("nan")
        repair._provider_failures["qq"] = {"count": object(), "last_error": "", "last_at": 0}
        repair._record_provider_success("qq")
        repair._record_provider_outcome("qq", "empty")
        repair._record_provider_outcome("qq", "no_valid_candidates")
        repair._record_provider_failure("qq", RuntimeError("boom"))
        self.assertGreaterEqual(repair.activity_snapshot()["qq"]["successes"], 1)

    def test_provider_activity_and_track_page_cache_status_recover_malformed_counters(self):
        providers = MetadataProviders({})
        providers._provider_successes["qq"] = {"count": 1, "last_at": object()}
        providers._provider_empty_results["qq"] = object()
        providers._provider_no_valid_candidates["qq"] = float("nan")
        activity = providers.activity_snapshot()
        self.assertEqual(activity["qq"]["successes"], 1)
        self.assertNotIn("empty_results", activity["qq"])
        self.assertNotIn("no_valid_candidates", activity["qq"])

        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service._track_page_cache_hits = object()
            service._track_page_cache_misses = float("nan")
            cache = service._track_page_cache_status()
            self.assertEqual(cache["hits"], 0)
            self.assertEqual(cache["misses"], 0)

    def test_provider_activity_ignores_custom_numeric_objects(self):
        providers = MetadataProviders({})
        providers._provider_successes["qq"] = {"count": 1, "last_at": object()}
        providers._provider_cooldown_until["qq"] = object()
        self.assertEqual(providers.activity_snapshot()["qq"]["last_success_seconds_ago"], 3600)
        self.assertEqual(providers.failure_snapshot(), {})

    def test_track_candidates_skip_corrupt_replacement_text(self):
        providers = MetadataProviders({})
        track = {"title": "One", "artist": "Example Artist", "duration": 180}
        qq_corrupt = {
            "songname": "\ufffd\ufffd", "singer": [{"name": "\ufffd\ufffd"}],
            "albumname": "\ufffd\ufffd", "albummid": "album-mid", "songmid": "song-mid",
        }
        kugou_valid = {
            "SongName": "One", "SingerName": "Example Artist",
            "AlbumName": "Resolved Album", "FileHash": "song-hash",
        }
        with patch.object(providers, "_json", return_value={}), \
             patch.object(providers, "_qq_songs", return_value=[qq_corrupt]), \
             patch.object(providers, "_kugou_songs", return_value=[kugou_valid]), \
             patch.object(providers, "_migu_songs", return_value=[]), \
             patch.object(providers, "_joox_songs", return_value=[]), \
             patch.object(providers, "_qianqian_songs", return_value=[]):
            candidates = providers.track_candidates(track)
        self.assertEqual(candidates[0]["source"], "kugou")
        self.assertNotIn("\ufffd", str(candidates[0]))
        self.assertIn("qq", providers.failure_snapshot())

    def test_lyrics_skip_corrupt_provider_and_use_next_source(self):
        providers = MetadataProviders({})
        track = {"title": "Song", "artist": "Artist"}
        with patch.object(providers, "netease_lyrics", return_value={"lyrics": "[00:01.00]\ufffd", "source": "netease"}), \
             patch.object(providers, "qq_lyrics", return_value={"lyrics": "[00:01.00]valid", "source": "qq"}), \
             patch.object(providers, "kugou_lyrics", return_value=None), \
             patch.object(providers, "migu_lyrics", return_value=None), \
             patch.object(providers, "joox_lyrics", return_value=None), \
             patch.object(providers, "qianqian_lyrics", return_value=None):
            result = providers.lyrics(track)
        self.assertEqual(result["source"], "qq")
        self.assertIn("netease_lyrics", providers.failure_snapshot())

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

    def test_track_artwork_priority_can_evict_lower_priority_entity_backfill(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with patch("metadata_service.bounded_int", return_value=2):
                with service._connect() as conn:
                    self.assertTrue(service._upsert_job(conn, "album:one", "album", "one", {}, 10))
                    self.assertTrue(service._upsert_job(conn, "composer:two", "composer", "two", {}, 30))
                    self.assertTrue(service._upsert_job(conn, "track:cover", "track", "cover", {}, 25))
                    rows = {
                        row["job_key"]: row["priority"]
                        for row in conn.execute("SELECT job_key,priority FROM metadata_jobs")
                    }
            self.assertEqual(rows, {"album:one": 10, "track:cover": 25})

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

    def test_empty_entity_refresh_preserves_last_usable_projection(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            key = entity_key("album", "Album", "Artist")
            service._store_entity("album", key, {"name": "Album", "artist": "Artist"}, {
                "artist": "Artist", "release_date": "2020", "source": "provider",
                "provider_id": "album-1", "confidence": 0.9,
            })
            service._store_entity("album", key, {"name": "Album", "artist": "Artist"}, {})
            with service._connect() as conn:
                row = conn.execute(
                    "SELECT artist,release_date,source,provider_id,confidence FROM metadata_entities WHERE entity_key=?",
                    (key,),
                ).fetchone()
            self.assertEqual(tuple(row), ("Artist", "2020", "provider", "album-1", 0.9))

    def test_empty_entity_refresh_keeps_projection_but_uses_negative_ttl(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            key = entity_key("album", "Album", "Artist")
            service._store_entity("album", key, {"name": "Album", "artist": "Artist"}, {
                "artist": "Artist", "release_date": "2020", "source": "provider",
                "provider_id": "album-1", "confidence": 0.9,
            })
            before = int(time.time())
            service._store_entity("album", key, {"name": "Album", "artist": "Artist"}, {})
            with service._connect() as conn:
                row = conn.execute(
                    "SELECT artist,release_date,expires_at FROM metadata_entities WHERE entity_key=?",
                    (key,),
                ).fetchone()
            self.assertEqual((row["artist"], row["release_date"]), ("Artist", "2020"))
            self.assertGreaterEqual(row["expires_at"], before + metadata_service.NEGATIVE_TTL - 1)
            self.assertLessEqual(row["expires_at"], int(time.time()) + metadata_service.NEGATIVE_TTL + 1)

    def test_empty_lyrics_refresh_preserves_source_and_confidence(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service._store_lyrics("track-1", {
                "lyrics": "cached lyrics", "source": "provider", "provider_id": "lyric-1", "confidence": 0.8,
            })
            service._store_lyrics("track-1", {})
            with service._connect() as conn:
                row = conn.execute(
                    "SELECT lyrics,lyrics_source,provider_id,confidence FROM metadata_tracks WHERE track_id='track-1'"
                ).fetchone()
            self.assertEqual(tuple(row), ("cached lyrics", "provider", "lyric-1", 0.8))

    def test_non_projection_queue_state_keeps_track_page_overlay_cache(self):
        """Queue churn must not defeat the short-lived first-page overlay cache."""
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            page = {"items": [item]}

            service.enrich_track_page(page)
            service.enrich_track_page(page)
            before = service._track_page_cache_status()
            self.assertGreaterEqual(before["hits"], 1)
            self.assertGreaterEqual(before["entries"], 1)

            service._invalidate_status_cache(projection_changed=False)
            retained = service._track_page_cache_status()
            self.assertEqual(retained["entries"], before["entries"])

            service._invalidate_status_cache(projection_changed=True)
            self.assertEqual(service._track_page_cache_status()["entries"], 0)

    def test_track_page_cache_discards_malformed_entry_and_reads_sqlite(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            page = {"items": [item]}

            service.enrich_track_page(page)
            cache_key = next(iter(service._track_page_cache))
            before = service._track_page_cache_status()
            service._track_page_cache[cache_key] = (object(), [])

            result = service.enrich_track_page(page)

            self.assertEqual(result["items"][0]["title"], "One")
            after = service._track_page_cache_status()
            self.assertEqual(after["hits"], before["hits"])
            self.assertEqual(after["misses"], before["misses"] + 1)
            self.assertEqual(after["entries"], 1)

    def test_track_page_cache_copy_does_not_block_status_reads(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service._track_page_cache_put(("page",), {"items": [{"id": "one"}]})
            entered = threading.Event()
            release = threading.Event()

            def blocked_deepcopy(value):
                entered.set()
                release.wait(2)
                return {"items": list(value["items"])}

            with patch("metadata_service.copy.deepcopy", side_effect=blocked_deepcopy):
                reader = threading.Thread(target=lambda: service._track_page_cache_get(("page",)))
                reader.start()
                self.assertTrue(entered.wait(1))
                started = time.monotonic()
                service._track_page_cache_status()
                self.assertLess(time.monotonic() - started, 0.25)
                release.set()
                reader.join(2)
                self.assertFalse(reader.is_alive())

    def test_track_page_cache_copy_does_not_return_entry_replaced_during_copy(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service._track_page_cache_put(("page",), {"items": [{"id": "old"}]})
            entered = threading.Event()
            release = threading.Event()

            def blocked_deepcopy(value):
                entered.set()
                release.wait(2)
                return {"items": list(value["items"])}

            result = []
            with patch("metadata_service.copy.deepcopy", side_effect=blocked_deepcopy):
                reader = threading.Thread(target=lambda: result.append(service._track_page_cache_get(("page",))))
                reader.start()
                self.assertTrue(entered.wait(1))
                with service._track_page_cache_lock:
                    service._track_page_cache[("page",)] = (time.monotonic(), {"items": [{"id": "new"}]})
                release.set()
                reader.join(2)
            self.assertFalse(reader.is_alive())
            self.assertEqual(result, [None])
            self.assertEqual(service._track_page_cache_status()["hits"], 0)

    def test_track_page_cache_put_ignores_non_copyable_projection(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            value = {"items": [object()]}
            with patch("metadata_service.copy.deepcopy", side_effect=TypeError("not copyable")):
                service._track_page_cache_put(("page",), value)
            self.assertEqual(service._track_page_cache_status()["entries"], 0)

    def _seed_page_overlay_fixture(self, root, count=2):
        """Seed `count` rows, each with a stored auto match and provider artwork."""
        config = self._config(root)
        music = config["library_paths"][0]
        items = [
            self._item("track-%03d" % index, os.path.join(music, "track-%03d.flac" % index),
                       "Song %d" % index, index + 1)
            for index in range(count)
        ]
        save_items_to_sqlite(config, items, "first")
        service = MetadataService(config)
        now = int(time.time())
        with service._connect() as conn:
            for index, item in enumerate(items):
                best = {
                    "title": "Matched %d" % index, "artist": "Matched Artist",
                    "album": "Matched Album", "album_artist": "Matched Artist",
                    "source": "musicbrainz", "provider_id": "rec-%d" % index,
                    "confidence": 0.93,
                }
                payload = {"best": best, "candidates": [best, dict(best, confidence=0.41)]}
                conn.execute(
                    """INSERT OR REPLACE INTO metadata_track_matches(
                        track_id,fields_json,source,provider_id,confidence,status,fetched_at,expires_at,orphaned_at
                    ) VALUES (?,?,?,?,?,?,?,?,0)""",
                    (item["id"], json.dumps(payload, ensure_ascii=False, sort_keys=True),
                     "musicbrainz", "rec-%d" % index, 0.93, "auto", now, now + 3600),
                )
                conn.execute(
                    """INSERT OR REPLACE INTO metadata_tracks(
                        track_id,lyrics,artwork_id,lyrics_source,provider_id,confidence,fetched_at,expires_at,orphaned_at
                    ) VALUES (?,?,?,?,?,?,?,?,0)""",
                    (item["id"], "[00:01.00]cached", "AB" * 32, "lrclib", "lyr-%d" % index,
                     0.8, now, now + 3600),
                )
        return config, items, service

    def test_track_page_overlay_projects_each_match_once_not_on_every_hit(self):
        """A repeated first page must reuse the finished projection, not re-decode it.

        The stored match text used to be decoded and re-bounded for every row of
        every request that hit the overlay cache, which cost more than the copy it
        was protecting. Discriminating: serving the cached text again doubles the
        decode count relative to the row count.
        """
        with tempfile.TemporaryDirectory() as root:
            _, items, service = self._seed_page_overlay_fixture(root)
            real = metadata_service.project_match_fields
            decoded = []

            def counting(fields_json):
                decoded.append(fields_json)
                return real(fields_json)

            def page():
                return {"items": [dict(item) for item in items]}

            with patch("metadata_service.project_match_fields", side_effect=counting):
                first = service.enrich_track_page(page())
                cold = len(decoded)
                second = service.enrich_track_page(page())
                third = service.enrich_track_page(page())
            self.assertEqual(cold, len(items))
            self.assertEqual(len(decoded), cold)
            self.assertGreaterEqual(service._track_page_cache_status()["hits"], 2)
            self.assertEqual(first, second)
            self.assertEqual(second, third)
            self.assertEqual(second["items"][0]["title"], "Matched 0")
            self.assertEqual(second["items"][0]["metadata_artwork_id"], "ab" * 32)

    def test_track_page_cache_stores_the_finished_overlay_projection(self):
        """The cache entry holds a bounded projection and a folded artwork id."""
        with tempfile.TemporaryDirectory() as root:
            _, items, service = self._seed_page_overlay_fixture(root)
            service.enrich_track_page({"items": [dict(item) for item in items]})
            cached = next(iter(service._track_page_cache.values()))[1]
            row = cached[items[0]["id"]]
            self.assertEqual(sorted(row), ["artwork_id", "projected"])
            self.assertNotIn("fields_json", row)
            self.assertEqual(row["artwork_id"], "ab" * 32)
            self.assertEqual(row["projected"]["album"], "Matched Album")

    def test_track_page_enrichment_normalizes_each_row_identity_once(self):
        """One page of rows pays for exactly one identity normalisation pass."""
        with tempfile.TemporaryDirectory() as root:
            _, items, service = self._seed_page_overlay_fixture(root)
            real = metadata_service.normalize_track_id
            seen = []

            def counting(value):
                seen.append(value)
                return real(value)

            with patch("metadata_service.normalize_track_id", side_effect=counting):
                service.enrich_track_page({"items": [dict(item) for item in items]})
            self.assertEqual(len(seen), len(items))

    def test_track_page_enrichment_bounds_oversized_input_before_projection(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            page = {"items": [{"id": "track-%04d" % index, "title": "Song"} for index in range(700)]}
            result = service.enrich_track_page(page)
            self.assertEqual(len(result["items"]), 500)
            self.assertEqual(result["items"][0]["id"], "track-0000")
            self.assertEqual(result["items"][-1]["id"], "track-0499")

    def test_track_page_enrichment_does_not_stringify_untrusted_cache_identity(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("track-page enrichment must not stringify page fields")

        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            page = {"items": [{"id": Explosive(), "title": Explosive(), "artist": Explosive()}]}
            self.assertIs(service.enrich_track_page(page), page)

    def test_projection_revision_is_part_of_overlay_cache_identity(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            page = {"items": [item]}
            service.enrich_track_page(page)
            first = service._track_page_cache_status()
            service.metadata_projection_revision = 1
            service.enrich_track_page(page)
            second = service._track_page_cache_status()
            self.assertEqual(second["entries"], 2)
            self.assertEqual(second["misses"], first["misses"] + 1)

    def test_track_page_enrichment_tolerates_a_corrupt_projection_revision(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            service.metadata_projection_revision = float("nan")
            result = service.enrich_track_page({"items": [item]})
            self.assertEqual(result["items"][0]["id"], "one")

    def test_orphan_cleanup_and_status_tolerate_a_corrupt_grace_period(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service.config["metadata_orphan_grace_days"] = object()
            with service._connect() as conn:
                service._cleanup_orphans(conn, int(time.time()))
            self.assertEqual(service.status()["orphan_grace_days"], 7)

    def test_track_page_overlay_omits_lyrics_unless_explicitly_requested(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            service._store_lyrics("one", {"lyrics": "[00:01.00]cached", "source": "test"})
            page = {"items": [item]}
            compact = service.enrich_track_page(page)
            detailed = service.enrich_track_page(page, include_lyrics=True)
            self.assertNotIn("lyrics", compact["items"][0])
            self.assertEqual(detailed["items"][0]["lyrics"], "[00:01.00]cached")

    def test_store_lyrics_bounds_the_document_in_bytes_not_characters(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            # 900k CJK characters are 2.7 MB: inside the old character budget,
            # outside the byte budget every reader was told to honour.
            service._store_lyrics("one", {"lyrics": chr(0x4e2d) * 900000, "source": "test"})
            service._store_lyrics("two", {"lyrics": chr(0x4e2d) * 500000, "source": "test"})
            with service._connect() as conn:
                rows = dict(conn.execute("SELECT track_id,lyrics FROM metadata_tracks").fetchall())
            self.assertEqual(rows["one"], "")
            self.assertEqual(len(rows["two"]), 500000)

    def test_cached_lyrics_endpoint_refuses_an_oversized_legacy_row(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            service._store_lyrics("one", {"lyrics": "[00:01.00]cached", "source": "test"})
            self.assertEqual(service.lyrics("one")["lyrics"], "[00:01.00]cached")
            with service._connect() as conn:
                conn.execute(
                    "UPDATE metadata_tracks SET lyrics=? WHERE track_id=?",
                    (chr(0x4e2d) * 900000, "one"),
                )
            self.assertEqual(service.lyrics("one")["lyrics"], "")
            # The same bound has to hold on the page overlay, or one endpoint
            # would keep serving a body the other one refuses.
            oversized_page = service.enrich_track_page({"items": [dict(item)]}, include_lyrics=True)
            self.assertNotIn("lyrics", oversized_page["items"][0])

    def test_oversized_legacy_body_is_not_resurrected_by_a_later_write(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            service._store_lyrics("one", {"lyrics": "[00:01.00]cached", "source": "test"})
            with service._connect() as conn:
                conn.execute(
                    "UPDATE metadata_tracks SET lyrics=? WHERE track_id=?",
                    (chr(0x4e2d) * 900000, "one"),
                )
            # A later write that carries no lyric text must not quietly keep an
            # unservable body alive: every reader refuses it, so it is dead
            # weight in the database and on the tag write-back.
            service._store_lyrics("one", {"source": "test"})
            with service._connect() as conn:
                row = conn.execute("SELECT lyrics FROM metadata_tracks WHERE track_id=?", ("one",)).fetchone()
            self.assertEqual(row["lyrics"], "")

    def test_ordinary_track_page_never_reads_or_caches_the_lyrics_column(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            item = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            save_items_to_sqlite(config, [item], "first")
            service = MetadataService(config)
            service._store_lyrics("one", {"lyrics": "[00:01.00]cached", "source": "test"})
            statements = []
            original_connect = service._connect

            def traced_connect():
                manager = original_connect()
                conn = manager.__enter__()
                conn.set_trace_callback(statements.append)
                return _RecordingConnect(conn, manager)

            page = {"items": [dict(item)]}
            service._connect = traced_connect
            try:
                compact = service.enrich_track_page(page)
                compact_reads = [text for text in statements if "tracks.lyrics" in text]
                statements.clear()
                detailed = service.enrich_track_page(page, include_lyrics=True)
                detailed_reads = [text for text in statements if "tracks.lyrics" in text]
                # A truthy non-True request normalises to the compact shape, so it
                # reuses the compact overlay instead of reading bodies again.
                statements.clear()
                loose = service.enrich_track_page({"items": [dict(item)]}, include_lyrics="yes")
                loose_reads = [text for text in statements if "tracks.lyrics" in text]
            finally:
                service._connect = original_connect
            self.assertEqual(compact_reads, [], "a compact page must not read cached lyric text")
            self.assertTrue(detailed_reads, "an explicit lyrics request must still read them")
            self.assertNotIn("lyrics", compact["items"][0])
            self.assertEqual(detailed["items"][0]["lyrics"], "[00:01.00]cached")
            self.assertEqual(loose_reads, [], "a truthy non-True request must stay compact")
            self.assertNotIn("lyrics", loose["items"][0])
            # The two shapes must not share one overlay entry, or the detailed
            # page would be served from the compact cache and lose the body.
            self.assertEqual(service._track_page_cache_status()["entries"], 2)

    def test_review_candidates_do_not_advance_visible_projection_revision(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            review = {"title": "Possible Song", "artist": "Artist", "confidence": 0.70}
            auto = {"title": "Resolved Song", "artist": "Artist", "confidence": 0.98}

            service._store_track_match("one", [review])
            self.assertEqual(service.metadata_projection_revision, 0)

            service._store_track_match("one", [auto])
            self.assertEqual(service.metadata_projection_revision, 1)

            # Removing an automatic result changes normal library rows even
            # when the replacement is dialog-only review data.
            service._store_track_match("one", [review])
            self.assertEqual(service.metadata_projection_revision, 2)

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

    def test_tag_write_backfill_pages_cached_albums_in_bounded_batches(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                for index in range(130):
                    name = "Album %03d" % index
                    conn.execute(
                        """INSERT INTO metadata_entities(
                            entity_type,entity_key,name,artist,artwork_id,orphaned_at
                        ) VALUES ('album',?,?,?,?,0)""",
                        (entity_key("album", name, "Artist"), name, "Artist", "a" * 64),
                    )
                conn.execute("DELETE FROM metadata_state WHERE key='tag_write_backfill_version'")

            queued = []
            with patch.object(service, "_queue_album_tag_writes", side_effect=lambda _conn, name, artist: queued.append((name, artist))):
                with service._connect() as conn:
                    version = conn.execute(
                        "SELECT value FROM metadata_state WHERE key='tag_write_backfill_version'"
                    ).fetchone()["value"]

            self.assertEqual(len(queued), 130)
            self.assertEqual(queued[0], ("Album 000", "Artist"))
            self.assertEqual(queued[-1], ("Album 129", "Artist"))
            self.assertEqual(version, "1")

    def test_album_artwork_ignores_an_empty_album_name(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            first = self._item("one", os.path.join(music, "one.flac"), "One", 1)
            second = self._item("two", os.path.join(music, "two.flac"), "Two", 2)
            first["album"] = ""
            second["album"] = ""
            save_items_to_sqlite(config, [first, second], "first")
            service = MetadataService(config)

            with service._connect() as conn:
                conn.execute("DELETE FROM metadata_jobs")
                service._queue_album_tag_writes(conn, "", "Example Artist")
                jobs = conn.execute(
                    "SELECT COUNT(*) FROM metadata_jobs WHERE job_type='tag_write'"
                ).fetchone()[0]

            self.assertEqual(jobs, 0)

    def test_album_artwork_bounds_the_track_fanout(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = config["library_paths"][0]
            items = []
            for index in range(4):
                item = self._item(
                    "t%d" % index, os.path.join(music, "t%d.flac" % index), "T%d" % index, index + 1
                )
                item["album"] = "Shared Album"
                items.append(item)
            save_items_to_sqlite(config, items, "first")
            service = MetadataService(config)

            with service._connect() as conn:
                conn.execute("DELETE FROM metadata_jobs")
                with patch.object(metadata_service, "MAX_ALBUM_TAG_WRITE_TRACKS", 2):
                    service._queue_album_tag_writes(conn, "Shared Album", "Example Artist")
                queued = sorted(
                    str(row["entity_key"])
                    for row in conn.execute("SELECT entity_key FROM metadata_jobs WHERE job_type='tag_write'")
                )

            self.assertEqual(queued, ["t0", "t1"])

    def test_tag_write_backfill_stops_when_the_cursor_stalls(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))

        class StalledCursor:
            def __init__(self):
                self.queries = 0

            def execute(self, _sql, _params):
                self.queries += 1
                if self.queries > 5:
                    raise AssertionError("album backfill must terminate on its own")
                return self

            def fetchall(self):
                # A stored BLOB key does not sort like the str() form used for the
                # cursor, so the same batch keeps coming back.
                return [{"entity_key": b"\x00stale", "name": "Album", "artist": "Artist"}]

        conn = StalledCursor()
        with patch.object(service, "_queue_album_tag_writes") as queue_album:
            service._backfill_album_tag_writes(conn)

        self.assertEqual(conn.queries, 2)
        self.assertEqual(queue_album.call_count, 1)

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

    def test_dsf_tag_write_keeps_one_frame_of_each_kind_per_write(self):
        # The replacement tag is rebuilt from preserved frames plus the frames
        # this write supplies.  Claiming every re-written frame as replaced is
        # what stops each metadata write from adding another copy of the same
        # picture, lyrics, or title.
        from id3_container import id3_tag
        from id3_parser import iter_id3_frames
        from library import read_id3_cover
        image = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"J" * 512 + bytes([0xFF, 0xD9])
        replacement = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) + b"P" * 64
        with tempfile.TemporaryDirectory() as root:
            artwork = os.path.join(root, "cover.png")
            with open(artwork, "wb") as handle:
                handle.write(replacement)
            current = os.path.join(root, "one.dsf")
            self._write_dsf_fixture(current, image=image)
            before = os.path.getsize(current)
            sizes = []
            for turn in range(1, 4):
                written = os.path.join(root, "round%d.dsf" % turn)
                _write_dsf_tags(current, written, {
                    "title": "Written",
                    "artist": "Artist",
                    "lyrics": "line",
                    "artwork_path": artwork if turn > 1 else None,
                })
                header, payload = id3_tag(written)
                frame_ids = [frame_id for frame_id, _ in iter_id3_frames(payload, header[3], header[5])]
                for frame_id in ("TIT2", "TPE1", "USLT", "APIC", "TXXX"):
                    self.assertEqual(frame_ids.count(frame_id), 1, (turn, frame_ids))
                self.assertEqual(read_id3_cover(written)[1], replacement if turn > 1 else image)
                sizes.append(os.path.getsize(written))
                current = written
            self.assertEqual(sizes[1], sizes[2], "a repeated write must not grow the tag")
            self.assertGreater(sizes[0], before)
    def _write_flagged_dsf_fixture(self, path, image):
        """A DSF whose ID3v2.3 block has an extended header and is unsynchronised."""
        custom = b"\x03keep\x00yes"
        apic = b"\x03image/jpeg\x00\x03\x00" + image
        frames = (b"TXXX" + len(custom).to_bytes(4, "big") + b"\x00\x00" + custom
                  + b"APIC" + len(apic).to_bytes(4, "big") + b"\x00\x00" + apic)
        payload = (6).to_bytes(4, "big") + b"\x00\x08\x00\x00\x00\x00" + frames.replace(b"\xff", b"\xff\x00")
        tag = b"ID3\x03\x00\xc0" + self._syncsafe(len(payload)) + payload
        metadata_offset = 64
        body = bytearray(b"DSD " + (28).to_bytes(8, "little") + (metadata_offset + len(tag)).to_bytes(8, "little") + metadata_offset.to_bytes(8, "little"))
        body.extend(b"\xaa" * (metadata_offset - len(body)))
        body.extend(tag)
        with open(path, "wb") as handle:
            handle.write(body)

    def test_dsf_tag_write_keeps_frames_hidden_behind_tag_flags(self):
        # A walker that cannot get past the extended header stopped at offset 0,
        # so a tag write deleted the user's own TXXX frame and picture.
        image = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"J" * 64 + bytes([0xFF, 0xD9])
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "flagged.dsf")
            temporary = source + ".fnaudio-tagging.dsf"
            from id3_parser import iter_id3_frames
            from library import read_id3_cover
            self._write_flagged_dsf_fixture(source, image)
            # A title-only write replaces TIT2, so both frames are unmanaged.
            rebuilt = b"".join(_preserved_id3_frames(source, {"TIT2"}))
            self.assertEqual(
                dict(iter_id3_frames(rebuilt, 3, 0)),
                {"TXXX": b"\x03keep\x00yes", "APIC": b"\x03image/jpeg\x00\x03\x00" + image},
            )
            _write_dsf_tags(source, temporary, {"title": "Written"})
            tags = read_id3(temporary)
            self.assertEqual(tags["title"], "Written")
            self.assertEqual(read_id3_cover(temporary), ("image/jpeg", image))
            with open(temporary, "rb") as handle:
                self.assertEqual(handle.read(6)[5], 0)

    def _write_flagless_id3_dsf(self, path, frames, major=3):
        """A DSF whose ID3 block holds exactly ``frames`` and no tag-level flags."""
        tag = b"ID3" + bytes((major, 0, 0)) + self._syncsafe(len(frames)) + frames
        metadata_offset = 64
        body = bytearray(
            b"DSD "
            + (28).to_bytes(8, "little")
            + (metadata_offset + len(tag)).to_bytes(8, "little")
            + metadata_offset.to_bytes(8, "little")
        )
        body.extend(b"\xaa" * (metadata_offset - len(body)))
        body.extend(tag)
        with open(path, "wb") as handle:
            handle.write(body)

    @staticmethod
    def _flagged_frame(frame_id, payload, major, flags):
        size = len(payload)
        if major == 4:
            encoded = bytes(((size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F))
        else:
            encoded = size.to_bytes(4, "big")
        return frame_id.encode("ascii") + encoded + flags.to_bytes(2, "big") + payload

    def test_tag_write_cannot_relabel_frames_it_cannot_decode(self):
        # _id3_frame hard-codes zero flag bytes, so preserving a compressed or
        # encrypted frame used to emit its zlib or cipher body as a plain-text
        # frame: the bytes survived and their meaning did not.
        from id3_parser import iter_id3_frames
        secret = b"\x03Never Gonna Give You Up"
        opaque = zlib.compress(secret)
        for major, flag in ((3, 0x0080), (3, 0x0040), (3, 0x0020), (4, 0x0008), (4, 0x0004), (4, 0x0040)):
            with self.subTest(major=major, flag=flag):
                data = self._flagged_frame("TXXX", opaque, major, flag)
                data += self._flagged_frame("TXXX", b"\x03keep\x00yes", major, 0)
                with tempfile.TemporaryDirectory() as root:
                    source = os.path.join(root, "one.dsf")
                    self._write_flagless_id3_dsf(source, data, major)
                    rebuilt = b"".join(_preserved_id3_frames(source, {"TIT2"}))
                    self.assertNotIn(opaque, rebuilt)
                    self.assertEqual(
                        dict(iter_id3_frames(rebuilt, 3, 0)),
                        {"TXXX": b"\x03keep\x00yes"},
                    )

    def test_tag_write_promotes_undoable_v24_frames_to_plain_text(self):
        # The undoable v2.4 transforms are applied on the way in, so the flagless
        # copy the writer emits is correct text rather than a body that still
        # opens with four data-length-indicator bytes.
        from id3_parser import iter_id3_frames
        body = b"\x01\xff\xfea\x00\xff\x00b\x00"
        payload = len(body).to_bytes(4, "big") + body.replace(b"\xff", b"\xff\x00")
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "undo.dsf")
            self._write_flagless_id3_dsf(source, self._flagged_frame("TXXX", payload, 4, 0x0003), 4)
            rebuilt = b"".join(_preserved_id3_frames(source, {"TIT2"}))
            self.assertEqual(dict(iter_id3_frames(rebuilt, 3, 0)), {"TXXX": body})

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
            service = MetadataService({
                "cache_dir": os.path.join(root, "cache"),
                "metadata_tag_write_enabled": True,
            })
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

    def test_tag_write_does_not_replace_source_changed_during_temp_build(self):
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

            def fake_run(command, **_kwargs):
                with open(command[-1], "wb") as fh:
                    fh.write(b"tagged")
                with open(path, "wb") as fh:
                    fh.write(b"new-user-content")
                return type("Result", (), {"returncode": 0, "stderr": b""})()

            with patch("metadata_service.find_ffmpeg", return_value="ffmpeg"), patch("metadata_service.subprocess.run", side_effect=fake_run):
                with self.assertRaisesRegex(RuntimeError, "source changed during metadata write"):
                    service._write_track_tags("one")
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), b"new-user-content")

    def test_tag_write_captures_stderr_to_a_bounded_file_not_memory_pipe(self):
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
            failed = type("Result", (), {"returncode": 1, "stderr": b""})()
            with patch("metadata_service.find_ffmpeg", return_value="ffmpeg"), \
                 patch("metadata_service.subprocess.run", return_value=failed) as run:
                with self.assertRaisesRegex(RuntimeError, "tag write failed"):
                    service._write_track_tags("one")
            self.assertNotEqual(run.call_args.kwargs.get("stderr"), subprocess.PIPE)

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

    def test_disabled_tag_writeback_does_not_leave_or_enqueue_jobs(self):
        with tempfile.TemporaryDirectory() as root:
            enabled_config = self._config(root)
            service = MetadataService(enabled_config)
            with service._connect() as conn:
                service._upsert_job(conn, "tag:old", "tag_write", "old", {}, 200)
                conn.execute("UPDATE metadata_jobs SET status='failed' WHERE job_key='tag:old'")

            disabled_config = {**enabled_config, "metadata_tag_write_enabled": False}
            disabled = MetadataService(disabled_config)
            with disabled._connect() as conn:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM metadata_jobs WHERE job_type='tag_write'").fetchone()[0],
                    0,
                )
                self.assertFalse(disabled._queue_tag_write(conn, "new"))
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM metadata_jobs WHERE job_type='tag_write'").fetchone()[0],
                    0,
                )

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

    def test_expired_track_match_is_requeued_without_requeuing_fresh_match(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            now = int(time.time())
            with service._connect() as conn:
                service._upsert_job(conn, "track:expired", "track", "expired", {}, 80)
                service._upsert_job(conn, "track:fresh", "track", "fresh", {}, 80)
                conn.execute(
                    "UPDATE metadata_jobs SET status='no_match' WHERE job_key IN ('track:expired','track:fresh')"
                )
                conn.execute(
                    "INSERT INTO metadata_track_matches(track_id,fields_json,status,fetched_at,expires_at,orphaned_at) VALUES (?,?,?,?,?,0)",
                    ("expired", "{}", "no_match", now - 100, now - 1),
                )
                conn.execute(
                    "INSERT INTO metadata_track_matches(track_id,fields_json,status,fetched_at,expires_at,orphaned_at) VALUES (?,?,?,?,?,0)",
                    ("fresh", "{}", "auto", now, now + 3600),
                )
                service._requeue_expired(conn, now)

            with service._connect() as conn:
                states = {
                    row["job_key"]: row["status"]
                    for row in conn.execute("SELECT job_key,status FROM metadata_jobs ORDER BY job_key")
                }
            self.assertEqual(states, {"track:expired": "pending", "track:fresh": "no_match"})

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

    def test_artwork_is_retained_for_a_track_reference_after_entities_are_orphaned(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root, grace=0))
            os.makedirs(service.artwork_dir, exist_ok=True)
            asset_id = "c" * 64
            asset_path = os.path.join(service.artwork_dir, asset_id + ".jpg")
            with open(asset_path, "wb") as fh:
                fh.write(b"image")
            now = int(time.time())
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_assets(id,path,mime,size,fetched_at,last_accessed) VALUES (?,?,?,?,?,?)",
                    (asset_id, asset_path, "image/jpeg", 5, now, now),
                )
                conn.execute(
                    "INSERT INTO metadata_entities(entity_type,entity_key,name,artwork_id,orphaned_at) VALUES ('album','album-key','Album',?,?)",
                    (asset_id, now),
                )
                conn.execute(
                    "INSERT INTO metadata_tracks(track_id,artwork_id,orphaned_at) VALUES (?,?,0)",
                    ("track-1", asset_id),
                )
                service._cleanup_orphans(conn, now)
                self.assertTrue(os.path.isfile(asset_path))
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_assets WHERE id=?", (asset_id,)).fetchone()[0], 1)
                conn.execute("UPDATE metadata_tracks SET orphaned_at=? WHERE track_id='track-1'", (now,))
                service._cleanup_orphans(conn, now)

            self.assertFalse(os.path.exists(asset_path))
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_assets WHERE id=?", (asset_id,)).fetchone()[0], 0)

    def test_orphan_cleanup_handles_expired_rows_across_bounded_batches(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root, grace=0))
            now = int(time.time())
            with service._connect() as conn:
                for index in range(130):
                    entity_key_value = "old-%03d" % index
                    track_id = "track-%03d" % index
                    conn.execute(
                        "INSERT INTO metadata_entities(entity_type,entity_key,name,orphaned_at) VALUES (?,?,?,?)",
                        ("album", entity_key_value, entity_key_value, now),
                    )
                    conn.execute(
                        "INSERT INTO metadata_tracks(track_id,orphaned_at) VALUES (?,?)",
                        (track_id, now),
                    )
                    service._upsert_job(conn, "album:" + entity_key_value, "album", entity_key_value, {}, 1)
                    service._upsert_job(conn, "lyrics:" + track_id, "lyrics", track_id, {}, 1)
                    service._upsert_job(conn, "tag:" + track_id, "tag_write", track_id, {}, 1)
                service._cleanup_orphans(conn, now)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_entities").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_tracks").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_jobs").fetchone()[0], 0)

    def test_artwork_pressure_preserves_referenced_asset(self):
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
                conn.execute(
                    "INSERT INTO metadata_tracks(track_id,artwork_id,expires_at,orphaned_at) VALUES (?,?,?,0)",
                    ("track-1", asset_id, now + 3600),
                )
                with patch("metadata_service.bounded_int", side_effect=lambda _c, key, *_a: 1 if key == "metadata_cache_max_bytes" else 0), patch(
                    "metadata_service.disk_has_reserve", return_value=True
                ):
                    self.assertEqual(service._prune_artwork_cache(conn, incoming_bytes=1), 0)
                entity = conn.execute(
                    "SELECT artwork_id,expires_at FROM metadata_entities WHERE entity_key='album-key'"
                ).fetchone()
                track = conn.execute(
                    "SELECT artwork_id,expires_at FROM metadata_tracks WHERE track_id='track-1'"
                ).fetchone()

            self.assertTrue(os.path.exists(asset_path))
            self.assertEqual(entity["artwork_id"], asset_id)
            self.assertEqual(entity["expires_at"], now + 3600)
            self.assertEqual(track["artwork_id"], asset_id)
            self.assertEqual(track["expires_at"], now + 3600)


    def test_artwork_prune_consumes_large_asset_sets_in_bounded_batches(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            now = int(time.time())
            with service._connect() as conn:
                for index in range(130):
                    conn.execute(
                        "INSERT INTO metadata_assets(id,path,mime,size,fetched_at,last_accessed) VALUES (?,?,?,?,?,?)",
                        ("a%063d" % index, "", "image/jpeg", 1, now, index),
                    )
                with patch("metadata_service.bounded_int", side_effect=lambda _c, key, *_a: 1 if key == "metadata_cache_max_bytes" else 0), patch(
                    "metadata_service.disk_has_reserve", return_value=True
                ):
                    self.assertEqual(service._prune_artwork_cache(conn, incoming_bytes=1), 130)
            with service._connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM metadata_assets").fetchone()[0], 0)

    def test_artwork_prune_reclaims_rows_for_files_removed_externally(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            asset_id = "f" * 64
            missing_path = os.path.join(service.artwork_dir, asset_id + ".jpg")
            now = int(time.time())
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_assets(id,path,mime,size,fetched_at,last_accessed) VALUES (?,?,?,?,?,?)",
                    (asset_id, missing_path, "image/jpeg", 4096, now, 1),
                )
                with patch("metadata_service.bounded_int", side_effect=lambda _c, key, *_a: 1 if key == "metadata_cache_max_bytes" else 0), patch(
                    "metadata_service.disk_has_reserve", return_value=True
                ):
                    self.assertEqual(service._prune_artwork_cache(conn, incoming_bytes=1), 1)
                self.assertIsNone(conn.execute("SELECT id FROM metadata_assets WHERE id=?", (asset_id,)).fetchone())

    def test_status_reports_bounded_pending_and_artwork_usage(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            config["metadata_max_pending_jobs"] = 100
            service = MetadataService(config)
            with service._connect() as conn:
                service._upsert_job(conn, "album:one", "album", "one", {}, 10)
            # The retained-byte budget has to survive the whole projection
            # chain, cache to aggregated status, or a memory leak stays invisible
            # on exactly the endpoint an operator would open.
            lyric_path = os.path.join(root, "song.lrc")
            with open(lyric_path, "w", encoding="utf-8") as handle:
                handle.write("x" * 4096)
            with patch("metadata_service.read_embedded_lyrics", return_value=""):
                self.assertEqual(len(service._read_local_lyrics_cached(lyric_path)), 4096)
            status = service.status()
            self.assertEqual(status["pending"], 1)
            self.assertEqual(status["pending_limit"], 100)
            self.assertFalse(status["saturated"])
            self.assertEqual(status["artwork_bytes"], 0)
            lyrics_cache = status["local_lyrics_cache"]
            self.assertEqual(lyrics_cache["entries"], 1)
            # Two lane caches each get a budget, so an aggregated limit is the
            # combined worst case, the same way "limit" already works.
            self.assertEqual(lyrics_cache["bytes_limit"], DEFAULT_MAX_BYTES * 2)
            self.assertEqual(lyrics_cache["bytes"], sys.getsizeof("x" * 4096))

    def test_status_releases_coalesced_snapshot_slot_after_non_sqlite_failure(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with patch.object(service, "_status_database_snapshot", side_effect=RuntimeError("filesystem unavailable")):
                status = service.status()
            self.assertTrue(status["ok"])
            self.assertEqual(status["jobs"], {})
            self.assertEqual(service.last_error, "filesystem unavailable")
            with service._status_cache_lock:
                self.assertFalse(service._status_cache_loading)
            # A failed owner must not strand the condition variable: force a
            # fresh read and prove ordinary status collection can recover.
            service._invalidate_status_cache()
            self.assertTrue(service.status()["ok"])

    def test_claim_job_refuses_new_work_once_shutdown_has_started(self):
        """A job claimed after shutdown began always outlives the join budget."""
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                service._upsert_job(conn, "track:one", "track", "one", {}, 1)
                service._upsert_job(conn, "tag:one", "tag_write", "one", {}, 200)
            service.stop_event.set()
            self.assertIsNone(service._claim_job(exclude_tag_writes=True))
            self.assertIsNone(service._claim_job(tag_writes_only=True))
            self.assertIsNone(service._claim_job(priority_max=10))
            with service._connect() as conn:
                rows = dict(conn.execute("SELECT job_key,status FROM metadata_jobs").fetchall())
                attempts = dict(conn.execute("SELECT job_key,attempts FROM metadata_jobs").fetchall())
            # Refusing the claim must leave the queue truthful: the next lifecycle
            # generation sees pending work, not a row abandoned as "running".
            self.assertEqual(rows["track:one"], "pending")
            self.assertEqual(rows["tag:one"], "pending")
            self.assertEqual((attempts["track:one"], attempts["tag:one"]), (0, 0))

    def test_shutdown_waits_out_a_job_whose_deadline_lands_after_the_measurement(self):
        """A provider chain claimed before the signal still has to be joined.

        ``_worker_shutdown_timeout`` is measured once, at the top of
        ``shutdown``.  A job claimed microseconds earlier registers *its*
        deadline from inside ``_process_job``, after that measurement, so a
        join budget that never refreshes gives up while a bounded provider
        call is still in flight and returns with live workers.  That is the
        shape which leaves ``library.sqlite3`` open (Windows then fails the
        next temp-directory cleanup).
        """
        with tempfile.TemporaryDirectory() as root:
            config = {**self._config(root), "metadata_enabled": False, "metadata_fetch_workers": 2}
            service = MetadataService(config)
            with service._connect() as conn:
                service._upsert_job(conn, "track:late", "track", "late", {}, 1)
            claimed = threading.Event()
            measured = threading.Event()
            finished = threading.Event()
            # Longer than the 3s idle budget, so a budget that never refreshes
            # is distinguishable from one that follows the registered deadline.
            job_budget = 4.0

            def late_deadline_process(job):
                # The claim already happened; this body stands in for the
                # provider chain and registers the deadline the shutdown
                # thread could not have seen yet.
                claimed.set()
                if not measured.wait(10):
                    return None
                ends_at = time.monotonic() + job_budget
                with service._active_jobs_lock:
                    service._active_job_deadlines["track:late"] = ends_at
                while time.monotonic() < ends_at:
                    time.sleep(0.05)
                with service._active_jobs_lock:
                    service._active_job_deadlines.pop("track:late", None)
                finished.set()
                return None

            service._process_job = late_deadline_process
            service.start()
            self.assertTrue(claimed.wait(10), "a worker must claim the pending job")
            outcome = []
            tester = threading.Thread(target=lambda: outcome.append(service.shutdown()))
            tester.start()
            # Let shutdown take its one-shot measurement first: registering the
            # deadline before that measurement would hide the race.
            time.sleep(0.3)
            measured.set()
            tester.join(30)
            self.assertFalse(tester.is_alive(), "shutdown must return within the job budget")
            self.assertEqual(
                outcome, [True],
                "shutdown gave up while a bounded provider job was still in flight",
            )
            self.assertTrue(finished.wait(10), "the claimed job must run through its own deadline")
            self.assertFalse(service._has_live_workers(), "no metadata worker may outlive shutdown")
            for worker in list(service.fetch_threads):
                worker.join(15)
                self.assertFalse(worker.is_alive())

    def test_tag_writes_are_claimed_by_the_dedicated_writer_only(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                service._upsert_job(conn, "tag:one", "tag_write", "one", {}, 200)
                service._upsert_job(conn, "lyrics:one", "lyrics", "one", {}, 100)
            self.assertEqual(service._claim_job(exclude_tag_writes=True)["job_type"], "lyrics")
            self.assertEqual(service._claim_job(tag_writes_only=True)["job_type"], "tag_write")

    def test_tag_write_claim_is_serial_across_service_instances(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            first = MetadataService(config)
            second = MetadataService(config)
            with first._connect() as conn:
                first._upsert_job(conn, "tag:one", "tag_write", "one", {}, 200)
                first._upsert_job(conn, "tag:two", "tag_write", "two", {}, 200)
            self.assertIsNotNone(first._claim_job(tag_writes_only=True))
            self.assertIsNone(second._claim_job(tag_writes_only=True))

    def test_explicit_playback_lane_can_claim_track_related_album_job(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({**self._config(root), "metadata_enabled": False})
            with service._connect() as conn:
                service._upsert_job(conn, "album:one", "album", "one", {}, 10)
                service._upsert_job(conn, "album:later", "album", "later", {}, 11)
            claimed = service._claim_job(priority_max=10)
            self.assertEqual(claimed["job_key"], "album:one")

    def test_disabled_background_fetch_lane_keeps_tag_writes_on_dedicated_writer(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({**self._config(root), "metadata_enabled": False})

            def claim(**kwargs):
                self.assertEqual(kwargs, {"priority_max": 10, "exclude_tag_writes": True})
                service.stop_event.set()
                service.fetch_wake_event.set()
                return None

            with patch.object(service, "_claim_job", side_effect=claim):
                service._run()

    def test_disabled_background_worker_survives_claim_failure(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService({**self._config(root), "metadata_enabled": False})
            claim = MagicMock(side_effect=RuntimeError("temporary sqlite failure"))
            wait = MagicMock(side_effect=lambda _seconds: service.stop_event.set())
            service._claim_job = claim
            service.fetch_wake_event.wait = wait
            worker = threading.Thread(target=service._run, daemon=True)
            worker.start()
            worker.join(timeout=1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(service.last_error, "temporary sqlite failure")

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

    def test_start_after_shutdown_clears_stop_event_before_restarting(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service.stop_event.set()
            with patch.object(service, "_start_workers") as start_workers:
                service.start()
            self.assertFalse(service.stop_event.is_set())
            start_workers.assert_called_once_with()

    def test_partial_worker_start_is_rolled_back_and_can_retry(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with patch.object(threading.Thread, "start", side_effect=[None, RuntimeError("no threads")]):
                with self.assertRaises(RuntimeError):
                    service.start()
            self.assertTrue(service.stop_event.is_set())
            self.assertFalse(any(worker.is_alive() for worker in service.fetch_threads))
            with patch.object(service, "_start_workers") as start_workers:
                service.start()
            self.assertFalse(service.stop_event.is_set())
            start_workers.assert_called_once_with()

    def test_start_rebuilds_when_only_one_metadata_lane_is_alive(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            class Alive:
                alive = True

                def is_alive(self):
                    return self.alive

                def join(self, timeout=None):
                    self.alive = False

            alive = Alive()
            service.fetch_threads = [alive]
            service.thread = alive
            service.tag_thread = None
            service.priority_thread = None
            with patch.object(service, "_start_workers") as start_workers:
                service.start()
            start_workers.assert_called_once_with()
            self.assertFalse(service.stop_event.is_set())

    def test_start_does_not_overlap_a_worker_that_ignored_shutdown(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            stubborn = type(
                "Stubborn",
                (),
                {"is_alive": lambda _self: True, "join": lambda _self, timeout=None: None},
            )()
            service.fetch_threads = [stubborn]
            service.thread = stubborn
            with patch.object(service, "_start_workers") as start_workers:
                service.start()
            start_workers.assert_not_called()
            self.assertTrue(service.stop_event.is_set())
            self.assertEqual(service.last_error, "metadata workers did not stop")

    def test_ensure_workers_keeps_stop_signal_when_recovery_leaves_old_worker_alive(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            stubborn = type(
                "Stubborn",
                (),
                {"is_alive": lambda _self: True, "join": lambda _self, timeout=None: None},
            )()
            dead = type("Dead", (), {"is_alive": lambda _self: False})()
            service.config["metadata_fetch_workers"] = 2
            service.fetch_threads = [stubborn, dead]
            service.thread = stubborn
            service.tag_thread = type(
                "AliveTag", (),
                {"is_alive": lambda _self: True, "join": lambda _self, timeout=None: None},
            )()
            service.priority_thread = type(
                "AlivePriority", (),
                {"is_alive": lambda _self: True, "join": lambda _self, timeout=None: None},
            )()
            with patch.object(threading.Thread, "start", side_effect=RuntimeError("start failed")):
                result = service.ensure_workers()
            self.assertFalse(result)
            self.assertTrue(service.stop_event.is_set())

    def test_shutdown_and_restart_are_serialized_by_lifecycle_lock(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            entered = threading.Event()
            release = threading.Event()

            class BlockingWorker:
                alive = True

                def is_alive(self):
                    return self.alive

                def join(self, timeout=None):
                    entered.set()
                    release.wait(1)
                    self.alive = False

            service.fetch_threads = [BlockingWorker()]
            service.thread = service.fetch_threads[0]
            shutdown = threading.Thread(target=service.shutdown)
            shutdown.start()
            self.assertTrue(entered.wait(1))
            with patch.object(service, "_start_workers") as start_workers:
                starter = threading.Thread(target=service.start)
                starter.start()
                time.sleep(0.05)
                self.assertFalse(start_workers.called)
                release.set()
                shutdown.join(timeout=1)
                starter.join(timeout=1)
            start_workers.assert_called_once_with()
            self.assertFalse(service.stop_event.is_set())

    def test_active_job_ends_at_accepts_only_usable_budgets(self):
        # This value is the only thing allowed to extend a shutdown budget, so
        # a poisoned entry must read as "no active job" instead of either
        # crashing the drain or stretching it to the ceiling.
        service = MetadataService(self._config(tempfile.gettempdir()))
        self.assertIsNone(service._active_job_ends_at())
        with service._active_jobs_lock:
            service._active_job_deadlines.update({
                "nan": float("nan"),
                "inf": float("inf"),
                "text": "99999999999",
                "none": None,
                "bool": True,
            })
        self.assertIsNone(service._active_job_ends_at())
        self.assertEqual(service._worker_shutdown_timeout(), 3)
        ends_at = time.monotonic() + 12.0
        with service._active_jobs_lock:
            service._active_job_deadlines["track:one"] = ends_at
            service._active_job_deadlines["bool"] = True
        self.assertEqual(service._active_job_ends_at(), ends_at)
        self.assertAlmostEqual(service._worker_shutdown_timeout(), 13.0, delta=1.0)
        with service._active_jobs_lock:
            service._active_job_deadlines["track:one"] = time.monotonic() + 10000.0
        self.assertEqual(
            service._worker_shutdown_timeout(),
            float(metadata_service.MAX_JOB_BUDGET_SECONDS + 1),
            "an active job may not stretch shutdown past one maximum job budget",
        )

    def test_shutdown_shares_one_join_budget_across_all_workers(self):
        # Virtual clock: every join slice advances it, so the budget a worker
        # still has is observable.  One permanently stuck worker must not buy
        # each later worker a fresh budget, and the idle base timeout must not
        # slide the deadline forward slice by slice; that is what makes the
        # whole drain bounded by a single wait.
        service = MetadataService(self._config(tempfile.gettempdir()))
        clock = [100.0]
        slices = []

        class Worker:
            def __init__(self, name):
                self.name = name

            def is_alive(self):
                return True

            def join(self, timeout=None):
                slices.append((self.name, timeout))
                clock[0] += timeout or 0.0

        service.fetch_threads = [Worker("fetch-a"), Worker("fetch-b")]
        service.tag_thread = Worker("tag")
        service.priority_thread = Worker("priority")
        with patch.object(service, "_worker_shutdown_timeout", return_value=3.0), \
             patch("metadata_service.time.monotonic", lambda: clock[0]):
            self.assertFalse(service.shutdown())
        total = sum(timeout or 0.0 for _name, timeout in slices)
        self.assertLessEqual(total, 3.25, "shutdown spent more than one shared budget on joins")
        self.assertEqual(
            {name for name, _timeout in slices},
            {"fetch-a", "fetch-b", "tag", "priority"},
            "every lane has to be joined, not just the first one",
        )

    def test_shutdown_re_signals_every_wake_event_for_each_join_slice(self):
        # Why the re-signal exists: the fetch lanes share one wake event and each lane
        # clears it after waking, while the park itself is a full ``wait(10)``.  A lane
        # that clears first can therefore leave a sibling asleep ten seconds past
        # shutdown - far longer than the 0.25 s join slice suggests - with its SQLite
        # handles open.  Reproducing that interleaving with real threads would be a coin
        # flip, so this pins the contract instead: while a worker is still alive, every
        # slice re-signals all three wake events.
        service = MetadataService(self._config(tempfile.gettempdir()))

        class Signalled:
            def __init__(self, event):
                self._event = event
                self.sets = 0

            def set(self):
                self.sets += 1
                self._event.set()

            def clear(self):
                self._event.clear()

            def is_set(self):
                return self._event.is_set()

            def wait(self, timeout=None):
                return self._event.wait(timeout)

        events = {}
        for name in ("fetch_wake_event", "tag_wake_event", "priority_wake_event"):
            proxy = Signalled(getattr(service, name))
            events[name] = proxy
            setattr(service, name, proxy)

        class Worker:
            def __init__(self, slices):
                self.joined = 0
                self.slices = slices

            def is_alive(self):
                return self.joined < self.slices

            def join(self, timeout=None):
                self.joined += 1

        service.fetch_threads = [Worker(3)]
        service.tag_thread = None
        service.priority_thread = None
        self.assertTrue(service.shutdown(), "the drained worker must count as stopped")
        for name, proxy in events.items():
            self.assertEqual(proxy.sets, 4,
                             "%s: once before the loop plus once per join slice" % name)

    def test_ensure_workers_requeues_stale_running_job_after_pool_loss(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            with service._connect() as conn:
                service._upsert_job(conn, "track:stale", "track", "stale", {}, 1)
                conn.execute(
                    "UPDATE metadata_jobs SET status='running', updated_at=?",
                    (int(time.time()) - 3600,),
                )
            # Simulate a dead fetch pool. Thread.start is patched so the
            # regression remains fully offline and does not leak workers.
            with patch.object(threading.Thread, "start"):
                self.assertTrue(service.ensure_workers("fetch"))
            with service._connect() as conn:
                row = conn.execute(
                    "SELECT status,next_attempt_at,last_error FROM metadata_jobs WHERE job_key='track:stale'"
                ).fetchone()
            self.assertEqual(row[0], "retry")
            self.assertEqual(row[1], 0)
            self.assertEqual(row[2], "worker recovered")

    def test_ensure_lyrics_workers_does_not_hide_dead_priority_lane_behind_fetch_pool(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            fetch_worker = type("Alive", (), {"is_alive": lambda _self: True})()
            dead_priority = type("Dead", (), {"is_alive": lambda _self: False})()
            service.fetch_threads = [fetch_worker]
            service.thread = fetch_worker
            service.priority_thread = dead_priority
            service.tag_thread = type("AliveTag", (), {"is_alive": lambda _self: True})()
            with patch.object(threading.Thread, "start"):
                self.assertTrue(service.ensure_workers("lyrics"))
            self.assertEqual(service.fetch_threads, [fetch_worker])
            self.assertIsNot(service.priority_thread, dead_priority)
            self.assertFalse(service.stop_event.is_set())

    def test_ensure_fetch_workers_replaces_only_dead_slots_without_recovering_live_jobs(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service.config["metadata_fetch_workers"] = 3
            alive = type("Alive", (), {"is_alive": lambda _self: True})()
            dead = type("Dead", (), {"is_alive": lambda _self: False})()
            service.fetch_threads = [alive, dead, dead]
            service.thread = alive
            service.priority_thread = type("AlivePriority", (), {"is_alive": lambda _self: True})()
            service.tag_thread = type("AliveTag", (), {"is_alive": lambda _self: True})()
            with patch.object(threading.Thread, "start") as start, \
                 patch.object(service, "_connect", side_effect=AssertionError("live pool must not reclaim jobs")):
                self.assertTrue(service.ensure_workers("fetch"))
            self.assertEqual(len(service.fetch_threads), 3)
            self.assertIs(service.fetch_threads[0], alive)
            self.assertEqual(start.call_count, 2)
            self.assertFalse(service.stop_event.is_set())

    def test_ensure_fetch_workers_restarts_a_dead_tag_writer_when_fetch_pool_is_healthy(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service.config["metadata_fetch_workers"] = 1
            fetch = type("AliveFetch", (), {"is_alive": lambda _self: True})()
            priority = type("AlivePriority", (), {"is_alive": lambda _self: True})()
            dead_tag = type("DeadTag", (), {"is_alive": lambda _self: False})()
            service.fetch_threads = [fetch]
            service.thread = fetch
            service.priority_thread = priority
            service.tag_thread = dead_tag
            with patch.object(threading.Thread, "start") as start:
                self.assertTrue(service.ensure_workers("fetch"))
            self.assertEqual(service.fetch_threads, [fetch])
            self.assertIsNot(service.tag_thread, dead_tag)
            start.assert_called_once_with()

    def test_dead_local_tag_writer_requeues_only_its_own_claimed_job(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service.config["metadata_fetch_workers"] = 1
            with service._connect() as conn:
                service._upsert_job(conn, "tag:one", "tag_write", "one", {}, 200)
            claimed = service._claim_job(tag_writes_only=True)
            service._mark_job_active(claimed["job_key"], int(claimed["attempts"]) + 1)
            service.fetch_threads = [type("AliveFetch", (), {"is_alive": lambda _self: True})()]
            service.thread = service.fetch_threads[0]
            service.priority_thread = type("AlivePriority", (), {"is_alive": lambda _self: True})()
            service.tag_thread = type("DeadTag", (), {"is_alive": lambda _self: False})()
            with patch.object(threading.Thread, "start"):
                self.assertTrue(service.ensure_workers("fetch"))
            with service._connect() as conn:
                row = conn.execute(
                    "SELECT status,next_attempt_at,last_error FROM metadata_jobs WHERE job_key='tag:one'"
                ).fetchone()
            self.assertEqual(row[0], "retry")
            self.assertEqual(row[1], 0)
            self.assertEqual(row[2], "tag writer recovered")

    def test_dead_tag_writer_does_not_requeue_another_service_claim(self):
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            owner = MetadataService(config)
            recovering = MetadataService(config)
            with owner._connect() as conn:
                owner._upsert_job(conn, "tag:one", "tag_write", "one", {}, 200)
            self.assertIsNotNone(owner._claim_job(tag_writes_only=True))
            recovering.config["metadata_fetch_workers"] = 1
            recovering.fetch_threads = [type("AliveFetch", (), {"is_alive": lambda _self: True})()]
            recovering.thread = recovering.fetch_threads[0]
            recovering.priority_thread = type("AlivePriority", (), {"is_alive": lambda _self: True})()
            recovering.tag_thread = type("DeadTag", (), {"is_alive": lambda _self: False})()
            with patch.object(threading.Thread, "start"):
                self.assertTrue(recovering.ensure_workers("fetch"))
            with owner._connect() as conn:
                row = conn.execute("SELECT status FROM metadata_jobs WHERE job_key='tag:one'").fetchone()
            self.assertEqual(row[0], "running")

    def test_ensure_workers_reports_failed_tag_lane_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service.config["metadata_fetch_workers"] = 1
            service.fetch_threads = [type("AliveFetch", (), {"is_alive": lambda _self: True})()]
            service.thread = service.fetch_threads[0]
            service.priority_thread = type("AlivePriority", (), {"is_alive": lambda _self: True})()
            service.tag_thread = type("DeadTag", (), {"is_alive": lambda _self: False})()
            with patch.object(service, "_ensure_tag_worker", return_value=False) as recover:
                self.assertFalse(service.ensure_workers("fetch"))
            recover.assert_called_once_with()

    def test_queue_tag_write_recovers_an_already_started_dead_tag_writer(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service.tag_thread = type("DeadTag", (), {"is_alive": lambda _self: False})()
            with service._connect() as conn, patch.object(service, "_ensure_tag_worker") as recover:
                service._queue_tag_write(conn, "track-1")
            recover.assert_called_once_with()

    def test_queue_tag_write_counts_one_recovered_tag_worker(self):
        with tempfile.TemporaryDirectory() as root:
            service = MetadataService(self._config(root))
            service.tag_thread = type("DeadTag", (), {"is_alive": lambda _self: False})()
            service.worker_restarts = 4
            with service._connect() as conn, patch.object(service, "_ensure_tag_worker", return_value=True):
                service._queue_tag_write(conn, "track-1")
            self.assertEqual(service.worker_restarts, 5)

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

    def test_person_requires_a_usable_entity_name_before_providers(self):
        providers = MetadataProviders({})
        with patch.object(providers, "netease_person") as netease_lookup, patch.object(providers, "qq_person") as qq_lookup:
            for unusable in (None, "", "   ", 12345, "unknown artist"):
                self.assertIsNone(providers.person(unusable), "unusable artist name must not reach a provider")
        netease_lookup.assert_not_called()
        qq_lookup.assert_not_called()
        self.assertEqual(providers.failure_snapshot(), {}, "guarding the entry must not cool a provider")
        matched = {"name": "Artist", "source": "netease"}
        with patch.object(providers, "netease_person", return_value=matched) as netease_lookup:
            self.assertEqual(providers.person("Artist")["source"], "netease")
        netease_lookup.assert_called_once_with("Artist")

    def test_netease_album_ignores_out_of_range_publish_time(self):
        providers = MetadataProviders({})
        payload = {"result": {"albums": [{
            "name": "Album",
            "artist": {"name": "Artist"},
            "publishTime": 10 ** 400,
            "picUrl": "",
            "id": "album-id",
        }]}}
        with patch.object(providers, "_json", return_value=payload):
            result = providers.netease_album("Album", "Artist")
        self.assertEqual(result["name"], "Album")
        self.assertEqual(result["release_date"], "")

    def test_migu_lyrics_fallback_uses_scored_song_and_returns_lrc(self):
        providers = MetadataProviders({})

        def fake_json(url, _headers=None, _data=None, _timeout=10):
            if "search_all.do" in url:
                return {"songResultData": {"result": [{"contentId": "123", "name": "Song", "singer": "Artist"}]}}
            if "resourceinfo.do" in url:
                return {"resource": [{"lrcUrl": "https://lyrics.example/song.lrc"}]}
            self.fail("unexpected URL: %s" % url)

        with patch.object(providers, "_json", side_effect=fake_json), patch("metadata_service._open_metadata_url") as urlopen:
            urlopen.return_value.__enter__.return_value.read.side_effect = [b"[00:01.00]first", b""]
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

    def test_migu_image_is_bounded_before_candidate_projection(self):
        providers = MetadataProviders({})
        image = "https://img.example/" + ("x" * 3000)
        with patch.object(providers, "_migu_songs", return_value=[{
            "albums": [{"id": "album-id", "name": "Album"}],
            "singer": "Artist", "imgItems": [{"img": image}],
        }]):
            result = providers.migu_album("Album", "Artist")
        self.assertLessEqual(len(result["image_url"]), 2048)

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

    def test_provider_adapter_does_not_stringify_or_forward_malformed_identifiers(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("provider field must not be stringified")

        providers = MetadataProviders({})
        with patch.object(providers, "_qq_songs", return_value=[{
            "songname": "Song", "singer": [{"name": "Artist"}], "songmid": Explosive(),
        }]), patch.object(providers, "_json") as request:
            self.assertIsNone(providers.qq_lyrics({"title": "Song", "artist": "Artist"}))
        request.assert_not_called()

        with patch.object(providers, "_kugou_songs", return_value=[{
            "AlbumName": "Album", "SingerName": "Artist", "AlbumID": Explosive(),
            "Image": Explosive(), "PublishDate": Explosive(),
        }]):
            result = providers.kugou_album("Album", "Artist")
        self.assertEqual(result["provider_id"], "")
        self.assertEqual(result["image_url"], "")
        self.assertEqual(result["release_date"], "")

    def test_provider_score_penalizes_same_title_with_wrong_artist(self):
        from metadata_service import provider_score

        compatible = provider_score("Hello World", "Hello World", "Alan Walker", "Alan Walker;Torine")
        incompatible = provider_score("Hello World", "Hello World", "airubreathe", "Alan Walker;Torine")

        self.assertGreaterEqual(compatible, 0.55)
        self.assertLess(incompatible, 0.55)

    def test_provider_score_ignores_untrusted_artist_objects_without_coercion(self):
        from metadata_service import provider_score

        class Explosive:
            def __bool__(self):
                raise AssertionError("artist truthiness must not be evaluated")

            def __str__(self):
                raise AssertionError("artist must not be stringified")

        self.assertEqual(
            provider_score("Song", "Song", "Artist", Explosive()),
            0.75,
        )

    def test_release_timestamp_is_normalized(self):
        self.assertEqual(normalize_release_date("1623340800"), "2021-06-11")
        self.assertEqual(normalize_release_date("2026-08-04"), "2026-08-04")
        self.assertEqual(normalize_release_date(10 ** 14), "")
class MetadataArtworkPlumbingTests(unittest.TestCase):
    """R107: the provider artwork id has one authoritative reader.

    These cases pin why the 2026-09-17 note's proposed fix - carry the id
    from metadata_tracks into prepare_track_persistence so it lands in
    item_json, and tighten has_local_artwork to match - was rejected: the
    page projection already reaches the value with no second copy, and a
    second copy is read back as if it were local artwork, which cannot heal.
    """

    @staticmethod
    def _config(root):
        music = os.path.join(root, "music")
        os.makedirs(music, exist_ok=True)
        return {
            "cache_dir": os.path.join(root, "cache"),
            "library_paths": [music],
            "metadata_enabled": True,
            "metadata_tag_write_enabled": False,
            "metadata_orphan_grace_days": 7,
        }

    @staticmethod
    def _item(item_id, path):
        return {
            "id": item_id,
            "path": path,
            "title": "Song",
            "artist": "Example Artist",
            "album": "Example Album",
            "album_artist": "Example Artist",
            "duration": 180,
            "size": 10,
            "metadata_source": {"title": "tag", "artist": "tag", "album": "tag"},
        }

    def _seed_library(self, root, artwork_id=None, orphaned=False, lyrics="", copy_into_item_json=False):
        config = self._config(root)
        music = os.path.join(config["library_paths"][0], "song.flac")
        with open(music, "wb") as handle:
            handle.write(b"fixture")
        item = self._item("t1", music)
        save_items_to_sqlite(config, [item], "first")
        service = MetadataService(config)
        now = int(time.time())
        if artwork_id is not None:
            with service._connect() as conn:
                conn.execute(
                    "INSERT INTO metadata_tracks(track_id,lyrics,artwork_id,provider_id,"
                    "confidence,fetched_at,expires_at,orphaned_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    ("t1", lyrics, artwork_id, "test", 0.9, now, now + 3600, 1 if orphaned else 0),
                )
        if copy_into_item_json:
            with service._connect() as conn:
                stored = json.loads(conn.execute("SELECT item_json FROM tracks WHERE id='t1'").fetchone()[0])
                stored["metadata_artwork_id"] = artwork_id or "f" * 64
                conn.execute("UPDATE tracks SET item_json=? WHERE id='t1'", (json.dumps(stored, ensure_ascii=False),))
        return config, item, service

    def test_projection_serves_cached_artwork_without_an_item_json_copy(self):
        from library_presentation import public_library_page

        artwork_id = "a" * 64
        with tempfile.TemporaryDirectory() as root:
            config, item, service = self._seed_library(root, artwork_id=artwork_id)
            page = service.enrich_track_page({"items": [dict(item)]})
            self.assertEqual(page["items"][0]["metadata_artwork_id"], artwork_id)
            public = public_library_page(page, config)
            row = public["items"][0]
            self.assertEqual(row["cover_url"], "metadata/artwork/" + artwork_id)
            self.assertNotIn("metadata_artwork_id", row)
            self.assertNotIn("item_json", row)
            with service._connect() as conn:
                stored = json.loads(conn.execute("SELECT item_json FROM tracks WHERE id='t1'").fetchone()[0])
            self.assertEqual(
                [key for key in stored if "artwork" in key or key.startswith("cover_")], [],
            )

    def test_valid_authoritative_artwork_keeps_the_track_lane_quiet(self):
        with tempfile.TemporaryDirectory() as root:
            _config, _item, service = self._seed_library(
                root, artwork_id="a" * 64, lyrics="[00:01]cached",
            )
            with patch.object(service, "_upsert_job") as queue:
                self.assertTrue(service.prioritize_track("t1"))
            keys = [call.args[1] for call in queue.call_args_list]
            self.assertNotIn("track:t1", keys)

    def test_orphaned_authoritative_artwork_requeues_the_track_lane(self):
        # The authoritative row can disappear underneath a row that still
        # advertises complete tags, so the lane has to reopen: this is the
        # self-heal property a persisted copy would break.
        with tempfile.TemporaryDirectory() as root:
            _config, _item, service = self._seed_library(
                root, artwork_id="a" * 64, lyrics="[00:01]cached", orphaned=True,
            )
            with patch.object(service, "_upsert_job") as queue:
                self.assertTrue(service.prioritize_track("t1"))
            keys = [call.args[1] for call in queue.call_args_list]
            self.assertIn("track:t1", keys)

    def test_persisted_copy_suppresses_the_lane_without_an_authoritative_row(self):
        with tempfile.TemporaryDirectory() as root:
            _config, _item, service = self._seed_library(
                root, copy_into_item_json=True,
            )
            with patch.object(service, "_upsert_job") as queue:
                self.assertTrue(service.prioritize_track("t1"))
            keys = [call.args[1] for call in queue.call_args_list]
            self.assertNotIn("track:t1", keys)
    def test_lyrics_cache_miss_queues_artwork_lane_for_a_coverless_track(self):
        # Third artwork gate: the pending lyrics path.  A fully tagged row
        # still has to reopen the track lane when no cover is known, so this
        # is the pin that keeps that clause from being dropped.
        with tempfile.TemporaryDirectory() as root:
            config = self._config(root)
            music = os.path.join(config["library_paths"][0], "one.flac")
            with open(music, "wb") as handle:
                handle.write(b"fixture")
            save_items_to_sqlite(config, [self._item("t1", music)], "first")
            service = MetadataService(config)
            with (
                patch.object(service, "_read_local_lyrics_cached", return_value=""),
                patch.object(service, "_needs_track_enrichment", return_value=False),
                patch("metadata_service.has_local_artwork", return_value=False),
            ):
                result = service.lyrics("t1")
            self.assertTrue(result["pending"])
            with service._connect() as conn:
                row = conn.execute(
                    "SELECT status,priority FROM metadata_jobs WHERE job_key='track:t1'",
                ).fetchone()
            self.assertEqual(row["status"], "pending")
            self.assertEqual(row["priority"], 1)


if __name__ == "__main__":
    unittest.main()
