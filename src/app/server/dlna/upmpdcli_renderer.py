from __future__ import annotations

import shutil
import subprocess
from typing import Any, Dict


def upmpdcli_binary() -> str:
    return shutil.which("upmpdcli") or ""


def upmpdcli_version(binary: str = "") -> str:
    binary = binary or upmpdcli_binary()
    if not binary:
        return ""
    for args in ([binary, "-v"], [binary, "--version"]):
        try:
            output = subprocess.check_output(args, stderr=subprocess.STDOUT, timeout=2)
            text = output.decode("utf-8", "replace").strip()
            if text:
                return text.splitlines()[0]
        except Exception:
            continue
    return ""


def process_running(name: str) -> bool:
    try:
        subprocess.check_output(["pgrep", "-x", name], stderr=subprocess.DEVNULL, timeout=2)
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
        "role": "dlna_openhome_renderer",
        "message": "" if binary else "upmpdcli is not installed",
    }
