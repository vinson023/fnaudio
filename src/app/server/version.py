from __future__ import annotations

import os


def _manifest_paths():
    server_dir = os.path.dirname(__file__)
    return (
        os.path.abspath(os.path.join(server_dir, "..", "manifest")),
        os.path.abspath(os.path.join(server_dir, "..", "..", "manifest")),
        "/var/apps/fnaudio/manifest",
    )


def _manifest_version() -> str:
    for manifest in _manifest_paths():
        try:
            with open(manifest, "r", encoding="utf-8") as handle:
                for line in handle:
                    key, separator, value = line.strip().partition("=")
                    if separator and key.strip().lower() == "version" and value.strip():
                        return value.strip()
        except OSError:
            continue
    return "0.0.0"


APP_VERSION = _manifest_version()
APP_USER_AGENT = "fnAudio/%s" % APP_VERSION
UPNP_SERVER = "fnOS/1.0 UPnP/1.1 %s" % APP_USER_AGENT


__all__ = ["APP_VERSION", "APP_USER_AGENT", "UPNP_SERVER"]
