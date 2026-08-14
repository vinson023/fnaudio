from __future__ import annotations

import json
import os
from typing import Any, Dict

from file_permissions import PUBLIC_FILE_MODE, atomic_write_json, atomic_write_text, secure_file


# The internal HTTP service defaults to this high port. Installation and App
# Center settings may override it; startup must use the configured value so
# the displayed port and the actual listener cannot silently diverge.
DEFAULT_PORT = 53199
DEFAULT_MPD_PORT = 56660


def load_config(path: str) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "library_path": os.environ.get("FNAUDIO_LIBRARY", "."),
        "library_paths": [],
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
        "metadata_enabled": True,
        "metadata_orphan_grace_days": 7,
        "metadata_max_pending_jobs": 20000,
        "metadata_cache_max_bytes": 512 * 1024 * 1024,
        "metadata_fetch_workers": 3,
        "metadata_fingerprint_enabled": False,
        "metadata_fpcalc_path": "",
        "metadata_tag_idle_interval_ms": 250,
        "metadata_tag_playing_interval_ms": 2000,
        "transcode_queue_max_jobs": 64,
        "transcode_cache_max_bytes": 2 * 1024 * 1024 * 1024,
        "cache_min_free_bytes": 512 * 1024 * 1024,
        "ffmpeg_max_concurrency": 2,
        "ffmpeg_job_timeout_seconds": 900,
        "scan_timeout_seconds": 3600,
    }
    try:
        with open(path, "r", encoding="utf-8") as fh:
            config.update(json.load(fh))
    except (OSError, ValueError):
        pass

    # Spotify credentials are no longer supported and must not survive a
    # configuration round trip after the metadata provider migration.
    config.pop("spotify_client_id", None)
    config.pop("spotify_client_secret", None)
    config["metadata_fingerprint_enabled"] = bool(config.get("metadata_fingerprint_enabled", False))
    config["metadata_fpcalc_path"] = str(config.get("metadata_fpcalc_path") or "").strip()[:512]

    if config.get("library_path") == "/var/apps/share/music" and os.path.isdir("/var/apps/fnaudio/share/music"):
        config["library_path"] = "/var/apps/fnaudio/share/music"
    try:
        config["server_port"] = max(1024, min(65535, int(config.get("server_port", DEFAULT_PORT))))
    except (TypeError, ValueError):
        config["server_port"] = DEFAULT_PORT
    try:
        config["mpd_port"] = max(1024, min(65535, int(config.get("mpd_port", DEFAULT_MPD_PORT))))
    except (TypeError, ValueError):
        config["mpd_port"] = DEFAULT_MPD_PORT
    try:
        config["mpd_device_presence_samples"] = max(1, min(5, int(config.get("mpd_device_presence_samples", 2))))
    except (TypeError, ValueError):
        config["mpd_device_presence_samples"] = 2
    try:
        config["metadata_orphan_grace_days"] = max(0, min(90, int(config.get("metadata_orphan_grace_days", 7))))
    except (TypeError, ValueError):
        config["metadata_orphan_grace_days"] = 7
    bounds = {
        "metadata_max_pending_jobs": (20000, 100, 200000),
        "metadata_cache_max_bytes": (512 * 1024 * 1024, 16 * 1024 * 1024, 8 * 1024 * 1024 * 1024),
        "metadata_fetch_workers": (3, 1, 6),
        "metadata_tag_idle_interval_ms": (250, 50, 5000),
        "metadata_tag_playing_interval_ms": (2000, 250, 10000),
        "transcode_queue_max_jobs": (64, 1, 1000),
        "transcode_cache_max_bytes": (2 * 1024 * 1024 * 1024, 64 * 1024 * 1024, 64 * 1024 * 1024 * 1024),
        "cache_min_free_bytes": (512 * 1024 * 1024, 64 * 1024 * 1024, 16 * 1024 * 1024 * 1024),
        "ffmpeg_max_concurrency": (2, 1, 8),
        "ffmpeg_job_timeout_seconds": (900, 30, 3600),
        "scan_timeout_seconds": (3600, 60, 86400),
    }
    for key, (default, minimum, maximum) in bounds.items():
        try:
            config[key] = max(minimum, min(maximum, int(config.get(key, default))))
        except (TypeError, ValueError):
            config[key] = default
    try:
        config["mpd_nice"] = max(-5, min(10, int(config.get("mpd_nice", 0))))
    except (TypeError, ValueError):
        config["mpd_nice"] = 0
    try:
        config["ffmpeg_nice"] = max(-5, min(10, int(config.get("ffmpeg_nice", 0))))
    except (TypeError, ValueError):
        config["ffmpeg_nice"] = 0
    if str(config.get("dac_keepalive_mode") or "off").lower() not in ("off", "pcm_only"):
        config["dac_keepalive_mode"] = "off"
    else:
        config["dac_keepalive_mode"] = str(config.get("dac_keepalive_mode") or "off").lower()
    mixer_type = str(config.get("mpd_mixer_type") or "none").strip().lower()
    config["mpd_mixer_type"] = mixer_type if mixer_type in ("none", "software", "hardware") else "none"
    config["mpd_mixer_control"] = str(config.get("mpd_mixer_control") or "").strip()[:128]
    return config


def save_config(path: str, config: Dict[str, Any]) -> bool:
    payload = {
        "library_path": config.get("library_path", ""),
        "library_paths": config.get("library_paths", []),
        "server_name": config.get("server_name", "fnAudio"),
        "server_port": int(config.get("server_port", DEFAULT_PORT)),
        "mpd_port": int(config.get("mpd_port", DEFAULT_MPD_PORT)),
        "mpd_output_alsa_id": config.get("mpd_output_alsa_id", ""),
        "mpd_output_stable_id": config.get("mpd_output_stable_id", ""),
        "mpd_device_presence_samples": int(config.get("mpd_device_presence_samples", 2)),
        "mpd_mixer_type": config.get("mpd_mixer_type", "none"),
        "mpd_mixer_control": str(config.get("mpd_mixer_control") or ""),
        "mpd_dop": bool(config.get("mpd_dop", False)),
        "mpd_nice": int(config.get("mpd_nice", 0)),
        "ffmpeg_nice": int(config.get("ffmpeg_nice", 0)),
        "dac_keepalive_mode": str(config.get("dac_keepalive_mode") or "off"),
        "dac_profiles": list(config.get("dac_profiles") or []),
        "metadata_enabled": bool(config.get("metadata_enabled", True)),
        "metadata_orphan_grace_days": int(config.get("metadata_orphan_grace_days", 7)),
        "metadata_max_pending_jobs": int(config.get("metadata_max_pending_jobs", 20000)),
        "metadata_cache_max_bytes": int(config.get("metadata_cache_max_bytes", 512 * 1024 * 1024)),
        "metadata_fetch_workers": int(config.get("metadata_fetch_workers", 3)),
        "metadata_fingerprint_enabled": bool(config.get("metadata_fingerprint_enabled", False)),
        "metadata_fpcalc_path": str(config.get("metadata_fpcalc_path") or ""),
        "metadata_tag_idle_interval_ms": int(config.get("metadata_tag_idle_interval_ms", 250)),
        "metadata_tag_playing_interval_ms": int(config.get("metadata_tag_playing_interval_ms", 2000)),
        "transcode_queue_max_jobs": int(config.get("transcode_queue_max_jobs", 64)),
        "transcode_cache_max_bytes": int(config.get("transcode_cache_max_bytes", 2 * 1024 * 1024 * 1024)),
        "cache_min_free_bytes": int(config.get("cache_min_free_bytes", 512 * 1024 * 1024)),
        "ffmpeg_max_concurrency": int(config.get("ffmpeg_max_concurrency", 2)),
        "ffmpeg_job_timeout_seconds": int(config.get("ffmpeg_job_timeout_seconds", 900)),
        "scan_timeout_seconds": int(config.get("scan_timeout_seconds", 3600)),
    }
    try:
        atomic_write_json(path, payload)
        return True
    except OSError:
        return False


def save_proxy_port(web_root: str, server_port: int) -> bool:
    target = os.path.join(web_root, "service_port.json")
    try:
        atomic_write_json(target, {"server_port": int(server_port)}, PUBLIC_FILE_MODE)
        return True
    except OSError:
        return False


__all__ = ["load_config", "save_config", "save_proxy_port"]
