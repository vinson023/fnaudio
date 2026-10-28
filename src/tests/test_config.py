import ast
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

from config import MAX_CONFIG_FILE_BYTES, load_config, save_config, save_proxy_port
from metadata_provider_config import default_metadata_provider_config


class ConfigTests(unittest.TestCase):
    def test_load_config_bounds_dac_profiles(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"dac_profiles": [{"name": str(index)} for index in range(100)]}, handle)
            loaded = load_config(path)
            self.assertEqual(len(loaded["dac_profiles"]), 64)

    def test_proxy_port_writer_normalizes_invalid_values(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertTrue(save_proxy_port(root, True))
            with open(os.path.join(root, "service_port.json"), "r", encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["server_port"], 53199)

    def test_numeric_settings_reject_booleans_and_keep_string_compatibility(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"server_port": True, "ffmpeg_max_waiters": "17", "scan_timeout_seconds": 10**1000}, fh)
            loaded = load_config(path)
            self.assertEqual(loaded["server_port"], 53199)
            self.assertEqual(loaded["ffmpeg_max_waiters"], 17)
            self.assertEqual(loaded["scan_timeout_seconds"], 86400)

    def test_boolean_settings_accept_only_json_booleans(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "mpd_dop": "false",
                    "metadata_enabled": "0",
                    "metadata_fingerprint_enabled": 1,
                    "metadata_tag_write_enabled": [],
                }, fh)
            loaded = load_config(path)
            self.assertFalse(loaded["mpd_dop"])
            self.assertFalse(loaded["metadata_enabled"])
            self.assertFalse(loaded["metadata_fingerprint_enabled"])
            self.assertFalse(loaded["metadata_tag_write_enabled"])

            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"mpd_dop": True, "metadata_enabled": True}, fh)
            loaded = load_config(path)
            self.assertTrue(loaded["mpd_dop"])
            self.assertTrue(loaded["metadata_enabled"])

    def test_library_connection_pool_defaults_on_and_survives_a_save(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            loaded = load_config(path)
            self.assertIs(loaded["library_connection_pool"], True)
            loaded["library_connection_pool"] = False
            self.assertTrue(save_config(path, loaded))
            with open(path, "r", encoding="utf-8") as fh:
                persisted = json.load(fh)
            self.assertIs(persisted["library_connection_pool"], False)
            self.assertIs(load_config(path)["library_connection_pool"], False)

    def test_dlna_type_detection_defaults_on_and_survives_a_save(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            self.assertIs(config["dlna_type_detection"], True)
            config["dlna_type_detection"] = False
            self.assertTrue(save_config(path, config))
            self.assertIs(load_config(path)["dlna_type_detection"], False)

    def test_renderer_name_defaults_and_survives_a_save(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            self.assertEqual(config["renderer_name"], "fnAudio Renderer")
            config["renderer_name"] = "客厅播放器"
            self.assertTrue(save_config(path, config))
            self.assertEqual(load_config(path)["renderer_name"], "客厅播放器")

    def test_renderer_name_is_bounded_and_invalid_values_fall_back(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"renderer_name": "  " + "R" * 140 + "  "}, handle)
            self.assertEqual(load_config(path)["renderer_name"], "R" * 128)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"renderer_name": ["bad"]}, handle)
            self.assertEqual(load_config(path)["renderer_name"], "fnAudio Renderer")

    def test_metadata_provider_config_defaults_and_round_trips(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            self.assertEqual(
                [entry["id"] for entry in config["metadata_providers"]],
                ["netease", "kuwo", "kugou", "migu", "joox", "musicbrainz"],
            )
            self.assertEqual(config["metadata_providers"], default_metadata_provider_config())
            config["metadata_providers"][-1] = {"id": "musicbrainz", "enabled": False}
            self.assertTrue(save_config(path, config))
            loaded = load_config(path)
            self.assertEqual(loaded["metadata_providers"][-1]["id"], "musicbrainz")
            self.assertFalse(loaded["metadata_providers"][-1]["enabled"])

    def test_invalid_metadata_provider_config_falls_back_to_safe_order_on_load_and_save(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"metadata_providers": [{"id": "musicbrainz", "enabled": True}]}, handle)
            self.assertEqual(load_config(path)["metadata_providers"], default_metadata_provider_config())

            config = load_config(path)
            config["metadata_providers"] = [{"id": "unknown", "enabled": True}]
            self.assertTrue(save_config(path, config))
            with open(path, encoding="utf-8") as handle:
                persisted = json.load(handle)
            self.assertEqual(persisted["metadata_providers"], default_metadata_provider_config())
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"renderer_name": "bad\nname"}, handle)
            self.assertEqual(load_config(path)["renderer_name"], "fnAudio Renderer")

    def test_library_connection_pool_accepts_only_json_booleans(self):
        # Text that merely looks like a refusal must not switch the pool off, the same
        # rule `_strict_bool` exists for everywhere else: the default stays put unless
        # the file carries a real JSON boolean.
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            for value in ("false", "0", 0, 1, [], {}, None):
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump({"library_connection_pool": value}, fh)
                self.assertIs(load_config(path)["library_connection_pool"], True, repr(value))
            for value in (True, False):
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump({"library_connection_pool": value}, fh)
                self.assertIs(load_config(path)["library_connection_pool"], value, repr(value))

    def test_load_and_save_agree_on_the_setting_key_set(self):
        # Both sides are literals: `load_config` starts from a default dictionary and
        # `save_config` writes a whitelist. They drifted apart once already, and the key
        # that lost the race kept working in the running process while disappearing from
        # disk, so compare the key sets themselves instead of hoping a round-trip test
        # happens to name the right key.
        with open("app/server/config.py", encoding="utf-8") as source_file:
            tree = ast.parse(source_file.read())
        literals = {}
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for inner in ast.walk(node):
                value = getattr(inner, "value", None)
                target = getattr(inner, "target", None) or getattr(inner, "targets", [None])[0]
                if not isinstance(value, ast.Dict) or not isinstance(target, ast.Name):
                    continue
                if target.id not in ("config", "payload"):
                    continue
                literals["%s.%s" % (node.name, target.id)] = sorted(
                    key.value for key in value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)
                )
        read_keys = literals["load_config.config"]
        write_keys = literals["save_config.payload"]
        self.assertEqual(len(read_keys), len(set(read_keys)))
        self.assertEqual(len(write_keys), len(set(write_keys)))
        self.assertEqual(read_keys, write_keys)
        self.assertIn("library_connection_pool", read_keys)

    def test_save_config_persists_every_setting_load_config_returns(self):
        # The write side is a whitelist, so a key registered only on the read side
        # disappears from disk on the first settings save: the running service keeps
        # its copy, every other reader and the next start fall back to the default.
        # `library_connection_pool` was in exactly that state, so pin the whole set.
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            loaded = load_config(path)
            self.assertTrue(save_config(path, loaded))
            with open(path, "r", encoding="utf-8") as fh:
                persisted = json.load(fh)
            self.assertEqual(sorted(set(loaded) - set(persisted)), [])
            self.assertIn("library_connection_pool", persisted)

    def test_text_settings_reject_non_text_json_values(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "metadata_fpcalc_path": ["/usr/bin/fpcalc"],
                    "dac_keepalive_mode": {"mode": "pcm_only"},
                    "mpd_mixer_type": ["hardware"],
                    "mpd_mixer_control": {"name": "PCM"},
                }, fh)
            loaded = load_config(path)
            self.assertEqual(loaded["metadata_fpcalc_path"], "")
            self.assertEqual(loaded["dac_keepalive_mode"], "off")
            self.assertEqual(loaded["mpd_mixer_type"], "none")
            self.assertEqual(loaded["mpd_mixer_control"], "")

    def test_library_and_mpd_identity_fields_reject_non_text_json_values(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "library_path": {"path": "/vol1/music"},
                        "library_paths": ["/vol1/music", {"path": "/vol2/music"}],
                        "mpd_output_alsa_id": ["hw:1"],
                        "mpd_output_stable_id": {"id": "usb:one"},
                    },
                    handle,
                )
            loaded = load_config(path)
            self.assertEqual(loaded["library_path"], "")
            self.assertEqual(loaded["library_paths"], ["/vol1/music"])
            self.assertEqual(loaded["mpd_output_alsa_id"], "")
            self.assertEqual(loaded["mpd_output_stable_id"], "")

    def test_save_config_safely_normalizes_invalid_resource_values(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            config.update({"server_port": True, "ffmpeg_max_concurrency": object(), "scan_timeout_seconds": "not-a-number"})
            self.assertTrue(save_config(path, config))
            loaded = load_config(path)
            self.assertEqual(loaded["server_port"], 53199)
            self.assertEqual(loaded["ffmpeg_max_concurrency"], 2)
            self.assertEqual(loaded["scan_timeout_seconds"], 3600)

    def test_save_config_rejects_untrusted_text_fields_without_serialization_failure(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            config.update({
                "library_path": {"path": "/vol1/music"},
                "library_paths": ["/vol1/music", {"path": "/vol2/music"}, 7],
                "server_name": ["bad"],
                "mpd_output_alsa_id": object(),
                "mpd_output_stable_id": {"id": "bad"},
            })
            self.assertTrue(save_config(path, config))
            loaded = load_config(path)
            self.assertEqual(loaded["library_path"], "")
            self.assertEqual(loaded["library_paths"], ["/vol1/music"])
            self.assertEqual(loaded["server_name"], "fnAudio")
            self.assertEqual(loaded["mpd_output_alsa_id"], "")
            self.assertEqual(loaded["mpd_output_stable_id"], "")

    def test_save_config_normalizes_enum_text_fields_symmetrically(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            config.update({
                "mpd_mixer_type": {"type": "hardware"},
                "dac_keepalive_mode": "invalid",
                "server_name": ["bad"],
            })
            self.assertTrue(save_config(path, config))
            loaded = load_config(path)
            self.assertEqual(loaded["mpd_mixer_type"], "none")
            self.assertEqual(loaded["dac_keepalive_mode"], "off")
            self.assertEqual(loaded["server_name"], "fnAudio")

    def test_metadata_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            self.assertFalse(config["metadata_enabled"])
            self.assertFalse(config["metadata_tag_write_enabled"])
            config.update(
                {
                    "library_path": "/vol1/music",
                    "library_paths": ["/vol1/music"],
                    "metadata_enabled": False,
                    "metadata_tag_write_enabled": True,
                    "metadata_orphan_grace_days": 14,
                }
            )

            self.assertTrue(save_config(path, config))
            loaded = load_config(path)

            self.assertFalse(loaded["metadata_enabled"])
            self.assertTrue(loaded["metadata_tag_write_enabled"])
            self.assertEqual(loaded["metadata_orphan_grace_days"], 14)
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            self.assertNotIn("spotify_client_id", payload)
            self.assertNotIn("spotify_client_secret", payload)

    def test_metadata_cleanup_grace_is_bounded(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"metadata_orphan_grace_days": 999}, fh)
            self.assertEqual(load_config(path)["metadata_orphan_grace_days"], 90)

    def test_airplay_settings_are_normalized_and_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            config.update(
                {
                    "airplay_enabled": True,
                    "airplay_command": " shairport-sync --name fnAudio ",
                    "airplay_alsa_device": " hw:2 ",
                    "shairport_sync_path": "/opt/shairport-sync",
                    "nqptp_path": "/opt/nqptp",
                    "airplay_log": "/tmp/airplay.log",
                }
            )
            self.assertTrue(save_config(path, config))
            loaded = load_config(path)
            self.assertTrue(loaded["airplay_enabled"])
            self.assertEqual(loaded["airplay_command"], "shairport-sync --name fnAudio")
            self.assertEqual(loaded["airplay_alsa_device"], "hw:2")
            self.assertEqual(loaded["shairport_sync_path"], "/opt/shairport-sync")
            self.assertEqual(loaded["nqptp_path"], "/opt/nqptp")
            self.assertEqual(loaded["airplay_log"], "/tmp/airplay.log")

    def test_airplay_settings_reject_invalid_json_values(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"airplay_enabled": "yes", "airplay_command": [], "airplay_alsa_device": {}}, handle)
            loaded = load_config(path)
            self.assertFalse(loaded["airplay_enabled"])
            self.assertEqual(loaded["airplay_command"], "")
            self.assertEqual(loaded["airplay_alsa_device"], "")

    def test_optional_runtime_path_overrides_are_normalized_and_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            config.update(
                {
                    "cache_dir": " /var/cache/fnaudio ",
                    "ffmpeg_path": " /opt/bin/ffmpeg ",
                    "ffprobe_path": " /opt/bin/ffprobe ",
                    "mpd_data_dir": " /var/lib/fnaudio/mpd ",
                    "structured_log_path": " /var/log/fnaudio.jsonl ",
                }
            )
            self.assertTrue(save_config(path, config))
            loaded = load_config(path)
            self.assertEqual(loaded["cache_dir"], "/var/cache/fnaudio")
            self.assertEqual(loaded["ffmpeg_path"], "/opt/bin/ffmpeg")
            self.assertEqual(loaded["ffprobe_path"], "/opt/bin/ffprobe")
            self.assertEqual(loaded["mpd_data_dir"], "/var/lib/fnaudio/mpd")
            self.assertEqual(loaded["structured_log_path"], "/var/log/fnaudio.jsonl")

    def test_optional_runtime_path_overrides_reject_non_text_values(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "cache_dir": [],
                        "ffmpeg_path": {},
                        "ffprobe_path": 7,
                        "mpd_data_dir": ["/var/lib/mpd"],
                        "structured_log_path": True,
                    },
                    handle,
                )
            loaded = load_config(path)
            for key in ("cache_dir", "ffmpeg_path", "ffprobe_path", "mpd_data_dir", "structured_log_path"):
                self.assertEqual(loaded[key], "")

    def test_oversized_config_is_rejected_before_json_decode(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            with open(path, "wb") as fh:
                fh.write(b"{" + b"x" * MAX_CONFIG_FILE_BYTES + b"}")
            loaded = load_config(path)
            self.assertEqual(loaded["server_port"], 53199)
            self.assertEqual(loaded["library_paths"], [])

    def test_non_object_json_config_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            for payload in ("null", "[]", '"text"'):
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(payload)
                loaded = load_config(path)
                self.assertEqual(loaded["server_port"], 53199)
                self.assertEqual(loaded["library_paths"], [])

    def test_audio_scheduling_settings_are_bounded_and_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            config.update({"mpd_nice": -99, "ffmpeg_nice": 99, "dac_keepalive_mode": "invalid"})
            self.assertTrue(save_config(path, config))
            loaded = load_config(path)
            self.assertEqual(loaded["mpd_nice"], -5)
            self.assertEqual(loaded["ffmpeg_nice"], 10)
            self.assertEqual(loaded["dac_keepalive_mode"], "off")

    def test_usb_presence_samples_are_bounded_and_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            config["mpd_device_presence_samples"] = 99
            self.assertTrue(save_config(path, config))
            loaded = load_config(path)
            self.assertEqual(loaded["mpd_device_presence_samples"], 5)

    def test_lyrics_cache_budget_is_clamped_on_load_alone(self):
        # The settings table is applied by load_config, not only by save_config.
        # Going through save_config first would clamp the value and let a missing
        # or wider load-side bound survive every check, which is exactly how a
        # hand-edited or externally written config.json reaches the service.
        from metadata_local_lyrics_cache import MAX_MAX_BYTES, MIN_MAX_BYTES
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            for value, expected in ((10 ** 12, MAX_MAX_BYTES), (1, MIN_MAX_BYTES), ("8 MiB", 8 * 1024 * 1024)):
                with self.subTest(value=value):
                    with open(path, "w", encoding="utf-8") as handle:
                        json.dump({"metadata_lyrics_cache_max_bytes": value}, handle)
                    self.assertEqual(load_config(path)["metadata_lyrics_cache_max_bytes"], expected)

    def test_lyrics_cache_setting_agrees_with_the_cache_owns_clamps(self):
        # The settings table and LocalLyricsCache clamp the same number in two
        # files. Nothing stops them from drifting except this check, and a
        # narrower setting range than the cache's own would silently discard a
        # value the cache would have accepted.
        from metadata_local_lyrics_cache import (
            DEFAULT_MAX_BYTES,
            MAX_MAX_BYTES,
            MIN_MAX_BYTES,
        )
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            loaded = load_config(path)
            self.assertEqual(loaded["metadata_lyrics_cache_max_bytes"], DEFAULT_MAX_BYTES)
            for value, expected in ((1, MIN_MAX_BYTES), (10**12, MAX_MAX_BYTES)):
                with self.subTest(value=value):
                    config = load_config(path)
                    config["metadata_lyrics_cache_max_bytes"] = value
                    self.assertTrue(save_config(path, config))
                    self.assertEqual(load_config(path)["metadata_lyrics_cache_max_bytes"], expected)

    def test_resource_limits_are_bounded_and_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            config = load_config(path)
            config.update(
                {
                    "metadata_max_pending_jobs": 1,
                    "metadata_cache_max_bytes": 10**15,
                    "metadata_lyrics_cache_max_bytes": 10**12,
                    "transcode_queue_max_jobs": 9999,
                    "transcode_cache_max_bytes": 1,
                    "cache_min_free_bytes": 1,
                    "ffmpeg_max_concurrency": 99,
                    "ffmpeg_max_waiters": 999,
                    "ffmpeg_job_timeout_seconds": 1,
                    "scan_timeout_seconds": 999999,
                    "http_max_workers": 9999,
                }
            )
            self.assertTrue(save_config(path, config))
            loaded = load_config(path)
            self.assertEqual(loaded["metadata_max_pending_jobs"], 100)
            self.assertEqual(loaded["metadata_cache_max_bytes"], 8 * 1024 * 1024 * 1024)
            self.assertEqual(loaded["metadata_lyrics_cache_max_bytes"], 64 * 1024 * 1024)
            self.assertEqual(loaded["transcode_queue_max_jobs"], 1000)
            self.assertEqual(loaded["transcode_cache_max_bytes"], 64 * 1024 * 1024)
            self.assertEqual(loaded["cache_min_free_bytes"], 64 * 1024 * 1024)
            self.assertEqual(loaded["ffmpeg_max_concurrency"], 8)
            self.assertEqual(loaded["ffmpeg_max_waiters"], 256)
            self.assertEqual(loaded["ffmpeg_job_timeout_seconds"], 30)
            self.assertEqual(loaded["scan_timeout_seconds"], 86400)
            self.assertEqual(loaded["http_max_workers"], 128)


if __name__ == "__main__":
    unittest.main()
