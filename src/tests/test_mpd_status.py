import sys
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from playback.mpd_client import mpd_replace_queue, mpd_status
from playback.mpd_errors import classify_mpd_exception, classify_mpd_log_errors
from services.mpd_service import classify_decoder_errors, device_presence_transition, normalized_transport


class MpdStatusTests(unittest.TestCase):
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
        connection.command.side_effect = [
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
            connection.command.call_args_list,
            [
                mock.call("clear"),
                mock.call("addid", "file:///music/first.flac"),
                mock.call("addid", "file:///music/second.flac"),
                mock.call("random", 1),
                mock.call("repeat", 1),
                mock.call("single", 0),
                mock.call("consume", 0),
                mock.call("playid", "8"),
                mock.call("seekid", "8", 12.5),
            ],
        )
