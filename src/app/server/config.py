from __future__ import annotations

import json
import os
from typing import Any, Dict


DEFAULT_PORT = 18080
DEFAULT_MPD_PORT = 56660


def load_config(path: str) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "library_path": os.environ.get("FNAUDIO_LIBRARY", "."),
        "library_paths": [],
        "server_name": "fnAudio",
        "server_port": DEFAULT_PORT,
        "mpd_port": DEFAULT_MPD_PORT,
        "mpd_output_alsa_id": "",
        "metadata_enabled": True,
        "spotify_client_id": os.environ.get("FNAUDIO_SPOTIFY_CLIENT_ID", ""),
        "spotify_client_secret": os.environ.get("FNAUDIO_SPOTIFY_CLIENT_SECRET", ""),
        "metadata_orphan_grace_days": 7,
    }
    try:
        with open(path, "r", encoding="utf-8") as fh:
            config.update(json.load(fh))
    except (OSError, ValueError):
        pass

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
        config["metadata_orphan_grace_days"] = max(0, min(90, int(config.get("metadata_orphan_grace_days", 7))))
    except (TypeError, ValueError):
        config["metadata_orphan_grace_days"] = 7
    return config


def save_config(path: str, config: Dict[str, Any]) -> bool:
    payload = {
        "library_path": config.get("library_path", ""),
        "library_paths": config.get("library_paths", []),
        "server_name": config.get("server_name", "fnAudio"),
        "server_port": int(config.get("server_port", DEFAULT_PORT)),
        "mpd_port": int(config.get("mpd_port", DEFAULT_MPD_PORT)),
        "mpd_output_alsa_id": config.get("mpd_output_alsa_id", ""),
        "metadata_enabled": bool(config.get("metadata_enabled", True)),
        "spotify_client_id": config.get("spotify_client_id", ""),
        "spotify_client_secret": config.get("spotify_client_secret", ""),
        "metadata_orphan_grace_days": int(config.get("metadata_orphan_grace_days", 7)),
    }
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        return True
    except OSError:
        return False


def save_proxy_port(web_root: str, server_port: int) -> bool:
    target = os.path.join(web_root, "service_port.json")
    temp = target + ".tmp"
    try:
        with open(temp, "w", encoding="utf-8") as fh:
            json.dump({"server_port": int(server_port)}, fh)
        os.replace(temp, target)
        return True
    except OSError:
        try:
            os.remove(temp)
        except OSError:
            pass
        return False


def save_manifest_port(manifest_path: str, server_port: int) -> bool:
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return False
    updated = False
    new_lines = []
    for line in lines:
        if line.lstrip().startswith("service_port"):
            prefix = line.split("=", 1)[0]
            newline = "\r\n" if line.endswith("\r\n") else "\n"
            new_lines.append(f"{prefix}= {int(server_port)}{newline}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        newline = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
        new_lines.append(f"service_port          = {int(server_port)}{newline}")
    try:
        with open(manifest_path, "w", encoding="utf-8", newline="") as fh:
            fh.writelines(new_lines)
        return True
    except OSError:
        return False


__all__ = ["load_config", "save_config", "save_proxy_port", "save_manifest_port"]
