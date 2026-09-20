import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from playback.mpd_client import MAX_MPD_COMMAND_BYTES, MAX_MPD_LINE_BYTES, MAX_MPD_RESPONSE_BYTES, MpdConnection, MpdError, mpd_replace_queue, mpd_status, mpd_update_and_wait, safe_float, safe_int
from playback.mpd_errors import (
    classify_mpd_exception,
    classify_mpd_log_errors,
    health_error_category,
    legacy_decoder_error_summary,
)
from services.mpd_service import (
    MAX_MPD_LOG_TAIL_BYTES,
    _tail_text,
    classify_decoder_errors,
    device_presence_transition,
    normalized_transport,
)


class MpdStatusTests(unittest.TestCase):
    def test_device_presence_does_not_coerce_corrupt_missing_flag(self):
        state, event = device_presence_transition({"missing": "false", "missing_samples": 0}, True, threshold=2)
        self.assertFalse(state["missing"])
        self.assertEqual(event, "")

    def test_safe_float_rejects_non_finite_and_boolean_values(self):
        self.assertEqual(safe_float(float("nan")), 0.0)
        self.assertEqual(safe_float(float("inf")), 0.0)
        self.assertEqual(safe_float(True), 0.0)

    def test_safe_int_rejects_extremely_large_values_without_overflow(self):
        self.assertEqual(safe_int(10 ** 10000), 0)

    def test_mpd_update_wait_rejects_nonfinite_timeout(self):
        connection = mock.MagicMock()
        with mock.patch("playback.mpd_client.MpdConnection", return_value=connection), \
             mock.patch("playback.mpd_client.time.monotonic", side_effect=[0.0, 0.1]), \
             mock.patch("playback.mpd_client.mpd_pairs", return_value={}):
            result = mpd_update_and_wait(timeout=float("nan"))
        self.assertTrue(result["ok"])
        self.assertTrue(result["updated"])

    def test_invalid_greeting_closes_socket_and_file(self):
        connection = MpdConnection()
        sock = mock.Mock()
        file = mock.Mock()
        sock.makefile.return_value = file
        file.readline.return_value = b"BROKEN\n"
        with mock.patch("playback.mpd_client.socket.create_connection", return_value=sock):
            with self.assertRaises(MpdError):
                connection.__enter__()
        file.close.assert_called_once_with()
        sock.close.assert_called_once_with()

    def test_readline_rejects_oversized_or_unterminated_response(self):
        for raw in (b"x" * (MAX_MPD_LINE_BYTES + 1), b"x" * MAX_MPD_LINE_BYTES):
            connection = MpdConnection()
            connection.file = mock.Mock()
            connection.file.readline.return_value = raw
            with self.assertRaises(MpdError):
                connection._readline()

    def test_command_rejects_an_unbounded_total_response(self):
        connection = MpdConnection()
        connection.file = mock.Mock()
        connection._readline = mock.Mock(side_effect=[
            "Tag: " + ("x" * (MAX_MPD_RESPONSE_BYTES // 2)),
            "Tag: " + ("y" * (MAX_MPD_RESPONSE_BYTES // 2)),
        ])
        with self.assertRaises(MpdError):
            connection.command("status")

    def test_command_list_ok_is_written_as_one_batch_and_splits_responses(self):
        connection = MpdConnection()
        connection.file = mock.Mock()
        connection._readline = mock.Mock(side_effect=["list_OK", "Id: 9", "list_OK", "OK"])

        result = connection.command_list_ok([("clear", ()), ("addid", ("file:///music/test.flac",))])

        self.assertEqual(result, [[], ["Id: 9"]])
        connection.file.write.assert_called_once_with(
            b'command_list_ok_begin\nclear\naddid "file:///music/test.flac"\ncommand_list_end\n'
        )

    def test_command_list_ok_rejects_an_oversized_outbound_batch_before_write(self):
        connection = MpdConnection()
        connection.file = mock.Mock()
        oversized = "x" * MAX_MPD_COMMAND_BYTES

        with self.assertRaisesRegex(MpdError, "command list is too large"):
            connection.command_list_ok([("addid", (oversized,))])

        connection.file.write.assert_not_called()

    def test_device_presence_requires_consecutive_missing_samples(self):
        state = {}
        state, event = device_presence_transition(state, False, threshold=2)
        self.assertEqual(event, "")
        state, event = device_presence_transition(state, False, threshold=2)
        self.assertEqual(event, "disconnected")
        self.assertTrue(state["missing"])

    def test_device_presence_requires_consecutive_present_samples_to_reconnect(self):
        state = {"missing": True, "missing_samples": 2, "present_samples": 0}
        state, event = device_presence_transition(state, True, threshold=2)
        self.assertEqual(event, "")
        state, event = device_presence_transition(state, True, threshold=2)
        self.assertEqual(event, "reconnected")
        self.assertFalse(state["missing"])

    def test_device_presence_resets_opposite_sample_counter(self):
        state, _ = device_presence_transition({}, False, threshold=3)
        state, _ = device_presence_transition(state, True, threshold=3)
        self.assertEqual(state["missing_samples"], 0)
        self.assertEqual(state["present_samples"], 1)

    def test_device_presence_recovers_corrupt_sample_counters(self):
        state, event = device_presence_transition(
            {"missing_samples": object(), "present_samples": float("nan"), "missing": False},
            False,
            threshold=2,
        )
        self.assertEqual(event, "")
        self.assertEqual(state["missing_samples"], 1)
        self.assertEqual(state["present_samples"], 0)

    def test_normalized_transport_falls_back_to_raw_play_state(self):
        self.assertEqual(
            normalized_transport({"status": {"raw": {"state": "play"}}}),
            "PLAYING",
        )

    def test_normalized_transport_prefers_explicit_normalized_state(self):
        self.assertEqual(
            normalized_transport(
                {"status": {"transport": {"state": "PAUSED"}, "raw": {"state": "play"}}}
            ),
            "PAUSED",
        )

    def test_decoder_errors_are_classified_without_becoming_underruns(self):
        result = classify_decoder_errors(
            'flac: invalid sync code\n'
            'exception: Decoder failed to seek\n'
            "decoder: Decoder plugin 'wildmidi' is unavailable\n"
            'player: played "healthy.flac"\n'
        )

        self.assertEqual(result["count"], 3)
        self.assertEqual(
            [item["category"] for item in result["items"]],
            ["source_corrupt", "seek_failed", "decoder_unavailable"],
        )
        self.assertEqual(result["last_category"], "decoder_unavailable")

    def test_unused_wildmidi_startup_notice_does_not_degrade_playback_health(self):
        result = classify_mpd_log_errors(
            "decoder: Decoder plugin 'wildmidi' is unavailable: "
            "configuration file does not exist: /etc/timidity/timidity.cfg\n"
            "player: played healthy.flac\n"
        )

        self.assertEqual(result["count"], 0)
        self.assertEqual(result["occurrences"], 0)

    def test_decoder_error_limit_is_bounded(self):
        result = classify_decoder_errors("invalid frame header\n" * 5, limit=2)

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["occurrences"], 5)

    def test_log_tail_reader_clamps_a_drifted_limit_instead_of_raising(self):
        # The `int(limit)` conversion sat inside `except OSError`, which only covers
        # the file work, so a non-numeric bound escaped as ValueError and took the
        # MPD diagnostics request down with it.
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "mpd.log")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("x" * 5000)
            for drifted in (None, "abc", {}, [], float("nan")):
                with self.subTest(limit=repr(drifted)):
                    self.assertEqual(len(_tail_text(path, drifted)), 4000)
            # Real numbers still mean what they say, and only absurd ones are clamped.
            self.assertEqual(len(_tail_text(path, -1)), 1)
            self.assertEqual(len(_tail_text(path, 3.7)), 3)
            self.assertEqual(len(_tail_text(path, 10)), 10)
            self.assertEqual(len(_tail_text(path, MAX_MPD_LOG_TAIL_BYTES * 2)),
                             min(5000, MAX_MPD_LOG_TAIL_BYTES))
            self.assertEqual(classify_decoder_errors("invalid frame header\n" * 3, "abc")["count"], 1)

    def test_playback_errors_distinguish_media_decoder_output_and_backend_domains(self):
        result = classify_mpd_log_errors(
            "flac: lost sync\n"
            "decoder: failed to seek\n"
            "decoder: Decoder plugin 'wildmidi' is unavailable\n"
            "output: Failed to open ALSA device: Device or resource busy\n"
            "output: sample rate is not supported\n"
            "output: buffer underrun\n"
            "exception: No such song\n"
            "exception: database is not ready\n"
        )

        self.assertEqual(
            [item["category"] for item in result["items"]],
            [
                "source_corrupt",
                "seek_failed",
                "decoder_unavailable",
                "output_device_busy",
                "output_format_unsupported",
                "buffer_underrun",
                "queue_stale",
                "database_unavailable",
            ],
        )
        self.assertEqual(result["by_category"]["buffer_underrun"], 1)
        self.assertEqual(result["last_domain"], "database")

    def test_classifier_keeps_latest_unique_errors_and_does_not_match_enabled_decoder(self):
        result = classify_mpd_log_errors(
            "decoder plugin flac is enabled\n"
            "invalid frame header\n"
            "invalid frame header\n"
            "failed to open audio output\n",
            limit=1,
        )

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["occurrences"], 3)
        self.assertEqual(result["items"][0]["category"], "output_io_failed")
        self.assertTrue(result["truncated"])

    def test_command_exception_has_stable_machine_readable_error(self):
        error = classify_mpd_exception("ACK [50@0] {addid} No such song")

        self.assertEqual(error["category"], "queue_stale")
        self.assertEqual(error["domain"], "queue")
        self.assertTrue(error["retryable"])

    def test_health_only_reports_severe_playback_errors(self):
        summary = classify_mpd_log_errors(
            "flac: invalid sync code\n"
            "exception: No such song\n"
        )

        self.assertEqual(summary["last_category"], "queue_stale")
        self.assertEqual(health_error_category(summary), "source_corrupt")

    def test_health_omits_recoverable_queue_warning(self):
        summary = classify_mpd_log_errors("exception: No such song\n")

        self.assertEqual(summary["last_category"], "queue_stale")
        self.assertEqual(health_error_category(summary), "")

    def test_health_projection_reads_only_plain_error_records(self):
        class BrokenRecord(dict):
            def keys(self):
                raise RuntimeError("records must not be copied through subclass accessors")

            def get(self, key, default=None):
                raise RuntimeError("records must not be read through subclass accessors")

        class BrokenSummary(dict):
            def get(self, key, default=None):
                raise RuntimeError("summaries must not run subclass accessors")

        self.assertEqual(health_error_category(BrokenSummary(items=[])), "")
        self.assertEqual(health_error_category({"items": "not a list"}), "")
        self.assertEqual(health_error_category({"items": 5}), "")
        self.assertEqual(health_error_category({"items": ["x", 7, None]}), "")
        # A record must be a mapping: without the type guard a list of pairs is
        # copied by dict() into a fully valid forged severe record.
        self.assertEqual(
            health_error_category({"items": [[["severity", "error"], ["category", "source_corrupt"]]]}),
            "",
        )
        self.assertEqual(
            health_error_category({"items": [{"severity": "ERROR", "category": "decoder_failed"}]}),
            "decoder_failed",
        )
        self.assertEqual(health_error_category(None), "")
        self.assertEqual(health_error_category("source_corrupt"), "")
        self.assertEqual(
            health_error_category({"items": [{"severity": "error", "category": 42}]}),
            "42",
        )
        self.assertEqual(health_error_category({"items": [{"severity": "error"}]}), "")

        # Only a real mapping is consulted: a duck-typed summary must never have
        # its accessors called while the health endpoint is being built.
        class DuckSummary:
            def __init__(self):
                self.calls = []

            def get(self, key, default=None):
                self.calls.append(key)
                return [{"severity": "error", "category": "source_corrupt"} if key == "items" else None][0]

        duck = DuckSummary()
        self.assertEqual(health_error_category(duck), "")
        self.assertEqual(duck.calls, [])
        self.assertEqual(
            health_error_category({
                "items": [
                    {"category": "source_corrupt", "severity": "error", "domain": "media"},
                    BrokenRecord(),
                ],
            }),
            "source_corrupt",
        )

    def test_health_reports_the_latest_of_several_severe_failures(self):
        summary = classify_mpd_log_errors(
            "flac: invalid sync code\n"
            "output: failed to open audio output\n"
        )

        self.assertEqual(
            [item["category"] for item in summary["items"]],
            ["source_corrupt", "output_io_failed"],
        )
        self.assertEqual(health_error_category(summary), "output_io_failed")

    def test_legacy_decoder_summary_accepts_every_summary_shape_health_sees(self):
        class BrokenSummary(dict):
            def get(self, key, default=None):
                raise RuntimeError("summaries must not run subclass accessors")

        for unusable in (None, "text", 5, BrokenSummary(), {"items": "not a list"}):
            with self.subTest(summary=type(unusable).__name__):
                result = legacy_decoder_error_summary(unusable)
                self.assertEqual(result["count"], 0)
                self.assertEqual(result["items"], [])
                self.assertEqual(result["last_category"], "")
                self.assertEqual(result["last_message"], "")

        result = legacy_decoder_error_summary({
            "items": [
                {"domain": "media", "category": "source_corrupt", "message": "bad frame"},
                "junk",
                {"domain": "output", "category": "output_io_failed", "message": "alsa"},
            ],
        })
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["last_category"], "source_corrupt")
        self.assertEqual(result["last_message"], "bad frame")

    def test_common_flac_and_alsa_variants_do_not_collapse_into_generic_decoder_error(self):
        result = classify_mpd_log_errors(
            "flac decoder: decoding error\n"
            "output: Failed to open ALSA device hw:3,0: No such file or directory\n"
            "output: snd_pcm_hw_params failed: Invalid argument\n"
        )

        self.assertEqual(
            [item["category"] for item in result["items"]],
            ["source_corrupt", "output_device_missing", "output_format_unsupported"],
        )

    @mock.patch("playback.mpd_client.mpd_pairs")
    def test_native_dsd_output_is_visible_in_normalized_stream(self, pairs):
        pairs.side_effect = [
            {"state": "play", "elapsed": "2", "duration": "20", "audio": "dsd128:2"},
            {"file": "test.dsf"},
        ]

        result = mpd_status()

        self.assertTrue(result["stream"]["dsd"])
        self.assertEqual(result["stream"]["format"], "dsd128:2")
        self.assertEqual(result["stream"]["channels"], 2)

    @mock.patch("playback.mpd_client.mpd_pairs")
    def test_pcm_output_reports_rate_depth_and_channels(self, pairs):
        pairs.side_effect = [
            {"state": "pause", "audio": "192000:24:2"},
            {"file": "test.flac"},
        ]

        result = mpd_status()

        self.assertFalse(result["stream"]["dsd"])
        self.assertEqual(result["stream"]["sample_rate"], 192000)
        self.assertEqual(result["stream"]["bit_depth"], 24)

    @mock.patch("playback.mpd_client.MpdConnection")
    def test_replace_queue_builds_native_mpd_queue_before_playing(self, connection_type):
        connection = connection_type.return_value.__enter__.return_value
        connection.command_list_ok.return_value = [
            [],
            ["Id: 7"],
            ["Id: 8"],
            [],
            [],
            [],
            [],
            [],
            [],
        ]

        result = mpd_replace_queue(
            [
                {"track_id": "first", "uri": "file:///music/first.flac"},
                {"track_id": "second", "uri": "file:///music/second.flac"},
            ],
            current_track_id="second",
            start=12.5,
            repeat="all",
            shuffle=True,
        )

        self.assertEqual(result["song_ids"], {"first": "7", "second": "8"})
        self.assertEqual(
            connection.command_list_ok.call_args_list,
            [
                mock.call([
                    ("clear", ()),
                    ("addid", ("file:///music/first.flac",)),
                    ("addid", ("file:///music/second.flac",)),
                    ("random", (1,)), ("repeat", (1,)), ("single", (0,)), ("consume", (0,)),
                ]),
            ],
        )
        self.assertEqual(connection.command.call_args_list, [mock.call("playid", "8"), mock.call("seekid", "8", 12.5)])
