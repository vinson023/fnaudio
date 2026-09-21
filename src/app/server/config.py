from __future__ import annotations

import json
import os
from typing import Any, Dict

from file_permissions import PUBLIC_FILE_MODE, atomic_write_json, atomic_write_text, secure_file
from library_paths import MAX_LIBRARY_PATHS, MAX_LIBRARY_PATH_TEXT
from services.dac_profiles import bounded_custom_profiles


# The internal HTTP service defaults to this high port. Installation and App
# Center settings may override it; startup must use the configured value so
# the displayed port and the actual listener cannot silently diverge.
DEFAULT_PORT = 53199
DEFAULT_MPD_PORT = 56660
MAX_CONFIG_FILE_BYTES = 2 * 1024 * 1024
# Reusing idle read handles for the library index is the shipped behaviour, so its
# default is a configuration value rather than something one startup path invents.
# Only a real JSON boolean can turn it off, and turning it off releases the idle
# handles it already parked (library.apply_library_connection_pool_config).
DEFAULT_LIBRARY_CONNECTION_POOL = True


def load_config(path: str) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "library_path": os.environ.get("FNAUDIO_LIBRARY", "."),
        "library_paths": [],
        "library_connection_pool": DEFAULT_LIBRARY_CONNECTION_POOL,
        "server_name": "fnAudio",
        "server_port": DEFAULT_PORT,
        "mpd_port": DEFAULT_MPD_PORT,
        "mpd_output_alsa_id": "",
        "mpd_output_stable_id": "",
        "mpd_device_presence_samples": 2,
        "mpd_mixer_type": "none",
        "mpd_mixer_control": "",
        "mpd_dop": False,
        "mpd_nice": 0,
        "ffmpeg_nice": 0,
        "dac_keepalive_mode": "off",
        "dac_profiles": [],
        "metadata_enabled": False,
        "metadata_tag_write_enabled": False,
        "metadata_orphan_grace_days": 7,
        "metadata_max_pending_jobs": 20000,
        "metadata_cache_max_bytes": 512 * 1024 * 1024,
        "metadata_lyrics_cache_max_bytes": 8 * 1024 * 1024,
        "metadata_fetch_workers": 3,
        "metadata_fingerprint_enabled": False,
        "metadata_fpcalc_path": "",
        "metadata_tag_idle_interval_ms": 250,
        "metadata_tag_playing_interval_ms": 2000,
        "transcode_queue_max_jobs": 64,
        "transcode_cache_max_bytes": 2 * 1024 * 1024 * 1024,
        "cache_min_free_bytes": 512 * 1024 * 1024,
        "ffmpeg_max_concurrency": 2,
        "ffmpeg_max_waiters": 32,
        "ffmpeg_job_timeout_seconds": 900,
        "http_max_workers": 32,
        "scan_timeout_seconds": 3600,
        "cache_dir": "",
        "ffmpeg_path": "",
        "ffprobe_path": "",
        "mpd_data_dir": "",
        "structured_log_path": "",
        "airplay_enabled": False,
        "airplay_command": "",
        "airplay_alsa_device": "",
        "shairport_sync_path": "",
        "nqptp_path": "",
        "airplay_log": "",
    }
    try:
        if os.path.getsize(path) > MAX_CONFIG_FILE_BYTES:
            raise ValueError("configuration file exceeds size limit")
        with open(path, "rb") as fh:
            raw = fh.read(MAX_CONFIG_FILE_BYTES + 1)
        if len(raw) > MAX_CONFIG_FILE_BYTES:
            raise ValueError("configuration file exceeds size limit")
        decoded = json.loads(raw.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("configuration root must be an object")
        config.update(decoded)
    except (OSError, TypeError, ValueError):
        pass

    # Spotify credentials are no longer supported and must not survive a
    # configuration round trip after the metadata provider migration.
    config.pop("spotify_client_id", None)
    config.pop("spotify_client_secret", None)
    config["library_path"] = _bounded_text(config.get("library_path"), MAX_LIBRARY_PATH_TEXT)
    config["library_paths"] = _bounded_text_list(config.get("library_paths"), MAX_LIBRARY_PATHS, MAX_LIBRARY_PATH_TEXT)
    config["library_connection_pool"] = _strict_bool(
        config.get("library_connection_pool"), DEFAULT_LIBRARY_CONNECTION_POOL
    )
    config["mpd_dop"] = _strict_bool(config.get("mpd_dop"), False)
    config["metadata_enabled"] = _strict_bool(config.get("metadata_enabled"), False)
    config["metadata_fingerprint_enabled"] = _strict_bool(config.get("metadata_fingerprint_enabled"), False)
    config["metadata_tag_write_enabled"] = _strict_bool(config.get("metadata_tag_write_enabled"), False)
    config["metadata_fpcalc_path"] = _bounded_text(config.get("metadata_fpcalc_path"), 512)
    config["mpd_output_alsa_id"] = _bounded_text(config.get("mpd_output_alsa_id"), 512)
    config["mpd_output_stable_id"] = _bounded_text(config.get("mpd_output_stable_id"), 512)
    config["cache_dir"] = _bounded_text(config.get("cache_dir"), 1024)
    config["ffmpeg_path"] = _bounded_text(config.get("ffmpeg_path"), 512)
    config["ffprobe_path"] = _bounded_text(config.get("ffprobe_path"), 512)
    config["mpd_data_dir"] = _bounded_text(config.get("mpd_data_dir"), 1024)
    config["structured_log_path"] = _bounded_text(config.get("structured_log_path"), 1024)
    config["airplay_enabled"] = _strict_bool(config.get("airplay_enabled"), False)
    config["airplay_command"] = _bounded_text(config.get("airplay_command"), 4096)
    config["airplay_alsa_device"] = _bounded_text(config.get("airplay_alsa_device"), 512)
    config["shairport_sync_path"] = _bounded_text(config.get("shairport_sync_path"), 512)
    config["nqptp_path"] = _bounded_text(config.get("nqptp_path"), 512)
    config["airplay_log"] = _bounded_text(config.get("airplay_log"), 512)
    config["dac_profiles"] = bounded_custom_profiles(config.get("dac_profiles"))
    config["server_name"] = _bounded_text(config.get("server_name"), 128) or "fnAudio"

    if config.get("library_path") == "/var/apps/share/music" and os.path.isdir("/var/apps/fnaudio/share/music"):
        config["library_path"] = "/var/apps/fnaudio/share/music"
    config["server_port"] = _bounded_int(config.get("server_port"), DEFAULT_PORT, 1024, 65535)
    config["mpd_port"] = _bounded_int(config.get("mpd_port"), DEFAULT_MPD_PORT, 1024, 65535)
    config["mpd_device_presence_samples"] = _bounded_int(config.get("mpd_device_presence_samples"), 2, 1, 5)
    config["metadata_orphan_grace_days"] = _bounded_int(config.get("metadata_orphan_grace_days"), 7, 0, 90)
    bounds = {
        "metadata_max_pending_jobs": (20000, 100, 200000),
        "metadata_cache_max_bytes": (512 * 1024 * 1024, 16 * 1024 * 1024, 8 * 1024 * 1024 * 1024),
        "metadata_lyrics_cache_max_bytes": (8 * 1024 * 1024, 64 * 1024, 64 * 1024 * 1024),
        "metadata_fetch_workers": (3, 1, 6),
        "metadata_tag_idle_interval_ms": (250, 50, 5000),
        "metadata_tag_playing_interval_ms": (2000, 250, 10000),
        "transcode_queue_max_jobs": (64, 1, 1000),
        "transcode_cache_max_bytes": (2 * 1024 * 1024 * 1024, 64 * 1024 * 1024, 64 * 1024 * 1024 * 1024),
        "cache_min_free_bytes": (512 * 1024 * 1024, 64 * 1024 * 1024, 16 * 1024 * 1024 * 1024),
        "ffmpeg_max_concurrency": (2, 1, 8),
        "ffmpeg_max_waiters": (32, 0, 256),
        "ffmpeg_job_timeout_seconds": (900, 30, 3600),
        "http_max_workers": (32, 4, 128),
        "scan_timeout_seconds": (3600, 60, 86400),
    }
    for key, (default, minimum, maximum) in bounds.items():
        config[key] = _bounded_int(config.get(key), default, minimum, maximum)
    config["mpd_nice"] = _bounded_int(config.get("mpd_nice"), 0, -5, 10)
    config["ffmpeg_nice"] = _bounded_int(config.get("ffmpeg_nice"), 0, -5, 10)
    config["dac_keepalive_mode"] = _normalized_keepalive_mode(config.get("dac_keepalive_mode"))
    config["mpd_mixer_type"] = _normalized_mixer_type(config.get("mpd_mixer_type"))
    config["mpd_mixer_control"] = _bounded_text(config.get("mpd_mixer_control"), 128)
    return config


def save_config(path: str, config: Dict[str, Any]) -> bool:
    library_paths = _bounded_text_list(config.get("library_paths"), MAX_LIBRARY_PATHS, MAX_LIBRARY_PATH_TEXT)
    payload = {
        "library_path": _bounded_text(config.get("library_path"), MAX_LIBRARY_PATH_TEXT),
        "library_paths": library_paths,
        "library_connection_pool": _strict_bool(
            config.get("library_connection_pool"), DEFAULT_LIBRARY_CONNECTION_POOL
        ),
        "server_name": _bounded_text(config.get("server_name"), 128) or "fnAudio",
        "server_port": _bounded_int(config.get("server_port"), DEFAULT_PORT, 1024, 65535),
        "mpd_port": _bounded_int(config.get("mpd_port"), DEFAULT_MPD_PORT, 1024, 65535),
        "mpd_output_alsa_id": _bounded_text(config.get("mpd_output_alsa_id"), 512),
        "mpd_output_stable_id": _bounded_text(config.get("mpd_output_stable_id"), 512),
        "mpd_device_presence_samples": _bounded_int(config.get("mpd_device_presence_samples"), 2, 1, 5),
        "mpd_mixer_type": _normalized_mixer_type(config.get("mpd_mixer_type")),
        "mpd_mixer_control": _bounded_text(config.get("mpd_mixer_control"), 128),
        "mpd_dop": _strict_bool(config.get("mpd_dop"), False),
        "mpd_nice": _bounded_int(config.get("mpd_nice"), 0, -5, 10),
        "ffmpeg_nice": _bounded_int(config.get("ffmpeg_nice"), 0, -5, 10),
        "dac_keepalive_mode": _normalized_keepalive_mode(config.get("dac_keepalive_mode")),
        "dac_profiles": bounded_custom_profiles(config.get("dac_profiles")),
        "metadata_enabled": _strict_bool(config.get("metadata_enabled"), False),
        "metadata_tag_write_enabled": _strict_bool(config.get("metadata_tag_write_enabled"), False),
        "metadata_orphan_grace_days": _bounded_int(config.get("metadata_orphan_grace_days"), 7, 0, 90),
        "metadata_max_pending_jobs": _bounded_int(config.get("metadata_max_pending_jobs"), 20000, 100, 200000),
        "metadata_cache_max_bytes": _bounded_int(config.get("metadata_cache_max_bytes"), 512 * 1024 * 1024, 16 * 1024 * 1024, 8 * 1024 * 1024 * 1024),
        "metadata_lyrics_cache_max_bytes": _bounded_int(config.get("metadata_lyrics_cache_max_bytes"), 8 * 1024 * 1024, 64 * 1024, 64 * 1024 * 1024),
        "metadata_fetch_workers": _bounded_int(config.get("metadata_fetch_workers"), 3, 1, 6),
        "metadata_fingerprint_enabled": _strict_bool(config.get("metadata_fingerprint_enabled"), False),
        "metadata_fpcalc_path": _bounded_text(config.get("metadata_fpcalc_path"), 512),
        "metadata_tag_idle_interval_ms": _bounded_int(config.get("metadata_tag_idle_interval_ms"), 250, 50, 5000),
        "metadata_tag_playing_interval_ms": _bounded_int(config.get("metadata_tag_playing_interval_ms"), 2000, 250, 10000),
        "transcode_queue_max_jobs": _bounded_int(config.get("transcode_queue_max_jobs"), 64, 1, 1000),
        "transcode_cache_max_bytes": _bounded_int(config.get("transcode_cache_max_bytes"), 2 * 1024 * 1024 * 1024, 64 * 1024 * 1024, 64 * 1024 * 1024 * 1024),
        "cache_min_free_bytes": _bounded_int(config.get("cache_min_free_bytes"), 512 * 1024 * 1024, 64 * 1024 * 1024, 16 * 1024 * 1024 * 1024),
        "ffmpeg_max_concurrency": _bounded_int(config.get("ffmpeg_max_concurrency"), 2, 1, 8),
        "ffmpeg_max_waiters": _bounded_int(config.get("ffmpeg_max_waiters"), 32, 0, 256),
        "ffmpeg_job_timeout_seconds": _bounded_int(config.get("ffmpeg_job_timeout_seconds"), 900, 30, 3600),
        "http_max_workers": _bounded_int(config.get("http_max_workers"), 32, 4, 128),
        "scan_timeout_seconds": _bounded_int(config.get("scan_timeout_seconds"), 3600, 60, 86400),
        "cache_dir": _bounded_text(config.get("cache_dir"), 1024),
        "ffmpeg_path": _bounded_text(config.get("ffmpeg_path"), 512),
        "ffprobe_path": _bounded_text(config.get("ffprobe_path"), 512),
        "mpd_data_dir": _bounded_text(config.get("mpd_data_dir"), 1024),
        "structured_log_path": _bounded_text(config.get("structured_log_path"), 1024),
        "airplay_enabled": _strict_bool(config.get("airplay_enabled"), False),
        "airplay_command": _bounded_text(config.get("airplay_command"), 4096),
        "airplay_alsa_device": _bounded_text(config.get("airplay_alsa_device"), 512),
        "shairport_sync_path": _bounded_text(config.get("shairport_sync_path"), 512),
        "nqptp_path": _bounded_text(config.get("nqptp_path"), 512),
        "airplay_log": _bounded_text(config.get("airplay_log"), 512),
    }
    try:
        atomic_write_json(path, payload)
        return True
    except (OSError, TypeError, ValueError):
        return False


def save_proxy_port(web_root: str, server_port: int) -> bool:
    target = os.path.join(web_root, "service_port.json")
    try:
        atomic_write_json(
            target,
            {"server_port": _bounded_int(server_port, DEFAULT_PORT, 1024, 65535)},
            PUBLIC_FILE_MODE,
        )
        return True
    except OSError:
        return False


def _bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    """Accept basic integer text/numbers while rejecting booleans and coercion hooks."""
    if isinstance(value, bool) or value is None:
        return default
    if not isinstance(value, (int, str)):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(minimum, min(maximum, number))


def _strict_bool(value, default: bool) -> bool:
    """Accept only JSON booleans so text values cannot silently enable a feature."""
    return value if isinstance(value, bool) else default


def _bounded_text(value, maximum: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:maximum]


def _bounded_text_list(value, maximum_items: int, maximum_text: int):
    if not isinstance(value, (list, tuple)):
        return []
    result = []
    for item in value[:maximum_items]:
        text = _bounded_text(item, maximum_text)
        if text:
            result.append(text)
    return result


def _normalized_keepalive_mode(value) -> str:
    mode = _bounded_text(value, 32).lower()
    return mode if mode in ("off", "pcm_only") else "off"


def _normalized_mixer_type(value) -> str:
    mixer_type = _bounded_text(value, 32).lower() or "none"
    return mixer_type if mixer_type in ("none", "software", "hardware") else "none"


__all__ = ["load_config", "save_config", "save_proxy_port"]
