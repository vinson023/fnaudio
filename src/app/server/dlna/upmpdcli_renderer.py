from __future__ import annotations

import shutil
from typing import Any, Dict

from process_output import check_output_bounded


def upmpdcli_binary() -> str:
    return shutil.which("upmpdcli") or ""


def upmpdcli_version(binary: str = "") -> str:
    binary = binary or upmpdcli_binary()
    if not binary:
        return ""
    for args in ([binary, "-v"], [binary, "--version"]):
        try:
            output = check_output_bounded(args, max_bytes=16 * 1024, timeout=2)
            text = output.decode("utf-8", "replace").strip()
            if text:
                return text.splitlines()[0]
        except Exception:
            continue
    return ""


def process_running(name: str) -> bool:
    try:
        check_output_bounded(["pgrep", "-x", name], max_bytes=16 * 1024, timeout=2)
        return True
    except Exception:
        return False


def upmpdcli_probe() -> Dict[str, Any]:
    binary = upmpdcli_binary()
    running = process_running("upmpdcli")
    return {
        "available": bool(binary),
        "running": running,
        "binary": binary,
        "version": upmpdcli_version(binary),
        "role": "compatibility_probe_only",
        "managed_by_fnaudio": False,
        "selectable_output": False,
        "owns_audio_device": False,
        "message": (
            "upmpdcli is detected but remains an externally managed compatibility probe"
            if binary
            else "upmpdcli is not installed; fnAudio uses its built-in DLNA renderer"
        ),
    }
