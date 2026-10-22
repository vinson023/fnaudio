import unittest
import sys
import subprocess
import os
from unittest.mock import Mock
from unittest.mock import patch

sys.path.insert(0, "app/server")

import probe_runner
from probe_runner import read_audio_info, read_probe_metadata
from probe_metadata import normalize_probe_payload


class ProbeRunnerTests(unittest.TestCase):
    def test_native_fallback_isolated_when_reader_raises(self):
        result = read_probe_metadata(
            "track.flac",
            {},
            ffprobe_resolver=lambda _config: "",
            native_reader=lambda _path: (_ for _ in ()).throw(RuntimeError("broken")),
            payload_normalizer=lambda _payload: ({}, {}),
        )
        self.assertEqual(result, ({}, {}))

    def test_successful_probe_merges_only_safe_native_mapping(self):
        with patch("probe_runner.subprocess.run") as run:
            run.return_value = type("Result", (), {"stdout": b'{"streams": []}'})()
            result = read_probe_metadata(
                "track.flac",
                {},
                ffprobe_resolver=lambda _config: "ffprobe",
                native_reader=lambda _path: {"sample_rate": 96000},
                payload_normalizer=lambda _payload: ({"title": "Song"}, {"duration": 1.0}),
            )
        self.assertEqual(result, ({"title": "Song"}, {"duration": 1.0, "sample_rate": 96000}))

    def test_non_mapping_native_result_is_ignored(self):
        with patch("probe_runner.subprocess.run") as run:
            run.return_value = type("Result", (), {"stdout": b'{}'})()
            result = read_probe_metadata(
                "track.flac",
                {},
                ffprobe_resolver=lambda _config: "ffprobe",
                native_reader=lambda _path: ["invalid"],
                payload_normalizer=lambda _payload: ({}, {"duration": 1.0}),
            )
        self.assertEqual(result, ({}, {"duration": 1.0}))

    def test_broken_or_non_text_probe_resolver_falls_back_safely(self):
        self.assertEqual(
            read_probe_metadata(
                "track.flac",
                {},
                ffprobe_resolver=lambda _config: (_ for _ in ()).throw(RuntimeError("broken")),
                native_reader=lambda _path: {"sample_rate": 44100},
                payload_normalizer=lambda _payload: ({}, {}),
            ),
            ({}, {"sample_rate": 44100}),
        )

    def test_oversized_probe_output_falls_back_without_decoding(self):
        with patch("probe_runner.subprocess.run") as run:
            run.return_value = type("Result", (), {"stdout": b"x" * (2 * 1024 * 1024 + 1)})()
            result = read_probe_metadata(
                "track.flac",
                {},
                ffprobe_resolver=lambda _config: "ffprobe",
                native_reader=lambda _path: {"sample_rate": 44100},
                payload_normalizer=lambda _payload: (_ for _ in ()).throw(AssertionError("must not decode")),
            )
        self.assertEqual(result, ({}, {"sample_rate": 44100}))
        self.assertEqual(
            read_probe_metadata(
                "track.flac",
                {},
                ffprobe_resolver=lambda _config: 123,
                native_reader=lambda _path: {"sample_rate": 48000},
                payload_normalizer=lambda _payload: ({}, {}),
            ),
            ({}, {"sample_rate": 48000}),
        )

    def test_nonzero_probe_exit_falls_back_instead_of_accepting_partial_json(self):
        with patch("probe_runner.subprocess.run") as run:
            run.return_value = type("Result", (), {
                "returncode": 1,
                "stdout": b'{"streams":[{"sample_rate":96000}]}'
            })()
            result = read_probe_metadata(
                "track.flac",
                {},
                ffprobe_resolver=lambda _config: "ffprobe",
                native_reader=lambda _path: {"sample_rate": 44100},
                payload_normalizer=lambda _payload: ({"title": "incorrect"}, {"sample_rate": 96000}),
            )
        self.assertEqual(result, ({}, {"sample_rate": 44100}))

    def test_nonzero_audio_info_probe_exit_uses_native_fallback(self):
        with patch("probe_runner.subprocess.run") as run:
            run.return_value = type("Result", (), {
                "returncode": 1,
                "stdout": b'{"streams":[{"sample_rate":96000}]}'
            })()
            result = read_audio_info(
                "track.flac", {},
                ffprobe_resolver=lambda _config: "ffprobe",
                native_reader=lambda _path: {"sample_rate": 44100, "bit_depth": 16},
            )
        self.assertEqual(result, {"sample_rate": 44100, "bit_depth": 16})

    def test_malformed_audio_info_probe_uses_native_fallback(self):
        with patch("probe_runner.subprocess.run") as run:
            run.return_value = type("Result", (), {
                "returncode": 0,
                "stdout": b'{"streams":['
            })()
            result = read_audio_info(
                "track.flac", {},
                ffprobe_resolver=lambda _config: "ffprobe",
                native_reader=lambda _path: {"sample_rate": 44100, "bit_depth": 16},
            )
        self.assertEqual(result, {"sample_rate": 44100, "bit_depth": 16})

    def test_real_probe_path_uses_a_private_process_session(self):
        process = Mock()
        process.wait.return_value = 0
        process.returncode = 0
        def real_run_marker(*_args, **_kwargs):
            raise AssertionError("the real probe path must use Popen")
        real_run_marker.__module__ = "subprocess"
        with patch("probe_runner.subprocess.run", real_run_marker), \
             patch("probe_runner.subprocess.Popen", return_value=process) as popen:
            result = read_probe_metadata(
                "track.flac",
                {},
                ffprobe_resolver=lambda _config: "ffprobe",
                native_reader=lambda _path: {},
                payload_normalizer=lambda _payload: ({}, {}),
            )
        self.assertEqual(result, ({}, {}))
        self.assertEqual(popen.call_args.kwargs["start_new_session"], os.name != "nt")

    def test_real_probe_path_stops_when_output_grows_past_limit(self):
        process = Mock()
        process.pid = 789
        process.poll.side_effect = [None, 0]
        process.wait.return_value = 0

        def real_run_marker(*_args, **_kwargs):
            raise AssertionError("the real probe path must use Popen")
        real_run_marker.__module__ = "subprocess"
        with patch("probe_runner.subprocess.run", real_run_marker), \
             patch("probe_runner.subprocess.Popen", return_value=process), \
             patch("probe_runner.os.killpg", create=True) as killpg, \
             patch("probe_runner.tempfile.TemporaryFile") as temporary:
            output = Mock()
            output.tell.return_value = probe_runner.MAX_PROBE_OUTPUT_BYTES + 1
            temporary.return_value.__enter__.return_value = output
            result = read_probe_metadata(
                "track.flac", {}, ffprobe_resolver=lambda _config: "ffprobe",
                native_reader=lambda _path: {"sample_rate": 44100},
                payload_normalizer=lambda _payload: (_ for _ in ()).throw(AssertionError("must not decode")),
            )
        self.assertEqual(result, ({}, {"sample_rate": 44100}))
        if os.name != "nt":
            killpg.assert_called_once_with(789, probe_runner.signal.SIGKILL)
        else:
            process.kill.assert_called_once_with()

    def test_real_probe_path_reaps_process_when_wait_fails(self):
        process = Mock()
        process.pid = 456
        process.wait.side_effect = [RuntimeError("wait failed"), 0]
        def real_run_marker(*_args, **_kwargs):
            raise AssertionError("the real probe path must use Popen")
        real_run_marker.__module__ = "subprocess"
        with patch("probe_runner.subprocess.run", real_run_marker), \
             patch("probe_runner.subprocess.Popen", return_value=process), \
             patch("probe_runner.os.killpg", create=True) as killpg:
            result = read_probe_metadata(
                "track.flac",
                {},
                ffprobe_resolver=lambda _config: "ffprobe",
                native_reader=lambda _path: {},
                payload_normalizer=lambda _payload: ({}, {}),
            )
        self.assertEqual(result, ({}, {}))
        if os.name != "nt":
            killpg.assert_called_once_with(456, probe_runner.signal.SIGKILL)
        else:
            process.kill.assert_called_once_with()
        self.assertEqual(process.wait.call_count, 2)

    def test_audio_info_rejects_boolean_and_fractional_probe_numbers(self):
        with patch("probe_runner.subprocess.run") as run:
            run.return_value = type("Result", (), {
                "stdout": b'{"streams":[{"sample_rate":true,"bits_per_sample":24.5,"bit_rate":"not-a-rate"}]}'
            })()
            result = read_audio_info(
                "track.flac", {}, ffprobe_resolver=lambda _config: "ffprobe",
                native_reader=lambda _path: {},
            )
        self.assertEqual(result, {"sample_rate": 0, "bit_depth": 0, "bit_rate": 0})

    def test_audio_info_accepts_integral_text_numbers(self):
        with patch("probe_runner.subprocess.run") as run:
            run.return_value = type("Result", (), {
                "stdout": b'{"streams":[{"sample_rate":"96000","bits_per_sample":"24","bit_rate":"4608000"}]}'
            })()
            result = read_audio_info(
                "track.flac", {}, ffprobe_resolver=lambda _config: "ffprobe",
                native_reader=lambda _path: {},
            )
        self.assertEqual(result, {"sample_rate": 96000, "bit_depth": 24, "bit_rate": 4608000})

    def test_dsf_native_container_facts_override_transport_rate_from_ffprobe(self):
        with patch("probe_runner.subprocess.run") as run:
            run.return_value = type("Result", (), {
                "stdout": b'{"streams":[{"sample_rate":"705600","bits_per_sample":8,"bit_rate":"11289600"}]}'
            })()
            result = read_audio_info(
                "track.dsf", {},
                ffprobe_resolver=lambda _config: "ffprobe",
                native_reader=lambda _path: {
                    "sample_rate": 5644800, "bit_depth": 1,
                    "bit_rate": 11289600, "duration": 10.0,
                },
            )
        self.assertEqual(result["sample_rate"], 5644800)
        self.assertEqual(result["bit_depth"], 1)
        self.assertEqual(result["bit_rate"], 11289600)
        self.assertEqual(result["duration"], 10.0)

    def test_both_probe_entry_points_prefer_dff_native_rate_and_preserve_tags(self):
        native = {"sample_rate": 5644800, "bit_depth": 1, "bit_rate": 11289600, "duration": 10.0}
        with patch("probe_runner.subprocess.run") as run:
            run.return_value = type("Result", (), {
                "stdout": b'{"format":{"duration":"10","tags":{"title":"DSD128"}},"streams":[{"sample_rate":"705600","bits_per_sample":8,"bit_rate":"11289600"}]}'
            })()
            info = read_audio_info("track.dff", {}, ffprobe_resolver=lambda _: "ffprobe", native_reader=lambda _: native)
            tags, metadata_info = read_probe_metadata(
                "track.dff", {}, ffprobe_resolver=lambda _: "ffprobe",
                native_reader=lambda _: native, payload_normalizer=normalize_probe_payload)
        self.assertEqual(info, native)
        self.assertEqual(metadata_info, native)
        self.assertEqual(tags["title"], "DSD128")


if __name__ == "__main__":
    unittest.main()
