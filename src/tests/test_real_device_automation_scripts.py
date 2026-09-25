import json
import pathlib
import re
import unittest
import tempfile
import subprocess
import sys


class RealDeviceAutomationScriptTests(unittest.TestCase):
    def test_log_analyzer_bounds_input_and_ignores_malformed_counters(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        script = root / "tools" / "analyze_real_device_playback_log.py"
        with tempfile.TemporaryDirectory() as temporary:
            log = pathlib.Path(temporary) / "capture.log"
            log.write_text(
                'sample=1 at=now {"status":{"raw":{"songid":"a","state":"play"}},"idle":{"underrun":{"count":"bad"}}}\n',
                encoding="utf-8",
            )
            result = subprocess.run([sys.executable, str(script), str(log)], text=True, errors="replace", capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"max_underrun": 0', result.stdout)

    def test_pcm_stability_runner_uses_safe_numeric_projection(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        script = (root / "tools" / "real_device_pcm_stability_run.py").read_text(encoding="utf-8")
        self.assertIn("def safe_int", script)
        self.assertIn("def safe_float", script)
        self.assertIn('safe_int((idle.get("underrun") or {}).get("count"))', script)
        self.assertIn('safe_float((status.get("position") or {}).get("rel_seconds"))', script)

    def test_pcm_control_runner_uses_safe_position_projection(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        script = (root / "tools" / "real_device_pcm_control_run.py").read_text(encoding="utf-8")
        self.assertIn("def safe_float", script)
        self.assertIn('return safe_float(((payload.get("status") or {}).get("position") or {}).get("rel_seconds"))', script)

    def test_restore_scripts_do_not_truthiness_coerce_shuffle(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        for name in ("real_device_pcm_control_run.py", "real_device_pcm_stability_run.py"):
            script = (root / "tools" / name).read_text(encoding="utf-8")
            self.assertIn("def safe_bool", script)
            self.assertNotIn('"shuffle": bool(state.get("shuffle"))', script)
        for name in ("real_device_mpd_restart_run.sh", "real_device_dac_queue_run.sh"):
            script = (root / "tools" / name).read_text(encoding="utf-8")
            self.assertNotIn('"shuffle": bool(s.get("shuffle"))', script)
            self.assertNotIn('"shuffle": bool(state.get("shuffle"))', script)

    def test_short_queue_and_recovery_use_the_verified_original_queue(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        expected = [
            "6d6e5ed0a8c0cf70", "676735c3075e949f", "3074ec5101f0c8b0",
            "da316cf2d8649c32", "df5702643ae3c3a5", "b2feef28c42d7070",
            "a42a74e5232023fb", "302d829ea32146e3", "3d76165d1d64c720",
            "38323e37bdbf9269", "656543c542d57326", "5b95adee70bc7585",
            "3ff16dc11d2c2450", "15db0d446f9655a6", "bb81c1f83bd6dfbe",
            "07437485ae9441fd", "17dd6b1148a6bf37", "f019d3578e9831b5",
            "992b2e65afc28859", "df394c51eb4378d6",
        ]
        for name in (
            "real_device_short_queue_after_long.sh",
            "real_device_restore_original_queue_0.1.205.sh",
        ):
            script = (root / "tools" / name).read_text(encoding="utf-8")
            match = re.search(r"^ORIGINAL_QUEUE='([^']+)'$", script, re.MULTILINE)
            self.assertIsNotNone(match, name)
            self.assertEqual(json.loads(match.group(1)), expected, name)

    def test_dynamic_dac_runner_snapshots_and_verifies_the_real_queue(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        script = (root / "tools" / "real_device_dac_queue_run.sh").read_text(encoding="utf-8")
        self.assertIn("X-Fnaudio-Internal: 1", script)
        self.assertIn('api "$BASE/api/playback/core" > "$SNAPSHOT"', script)
        self.assertIn('"queue": state["queue"]', script)
        self.assertIn('"restore_verified="', script)
        self.assertNotIn("ORIGINAL_QUEUE=", script)
        self.assertIn('FNAUDIO_TEST_QUEUE', script)
        self.assertIn('expected_queue_length=', script)
        self.assertIn('observed_queue_positions=', script)
        self.assertIn('queue_traversal_verified=', script)
        self.assertIn('missing_queue_positions=', script)
        self.assertIn('range(expected)', script)
        self.assertIn('queue_positions_complete_at_sample=', script)
        self.assertIn('seen_positions=', script)

    def test_all_real_device_scripts_use_loopback_internal_authentication(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        for name in (
            "real_device_dac_queue_run.sh",
            "real_device_mpd_restart_run.sh",
            "real_device_usb_hotplug_capture.sh",
        ):
            script = (root / "tools" / name).read_text(encoding="utf-8")
            self.assertIn("X-Fnaudio-Internal: 1", script, name)

    def test_restore_scripts_encode_json_values_structurally(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        for name in (
            "real_device_mpd_restart_run.sh",
            "real_device_dac_queue_run.sh",
            "real_device_short_queue_after_long.sh",
            "real_device_restore_original_queue_0.1.205.sh",
        ):
            script = (root / "tools" / name).read_text(encoding="utf-8")
            self.assertIn("json.dumps", script, name)
            self.assertNotRegex(script, r"printf '\\{.*(?:target_id|track_id|current_id).*%s")


if __name__ == "__main__":
    unittest.main()
