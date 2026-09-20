"""Pure wire-policy helpers for the authoritative playback SSE stream."""

from __future__ import annotations

import json

MAX_SSE_FRAME_BYTES = 512 * 1024

def snapshot_changed(version, last_version):
    return isinstance(version, int) and not isinstance(version, bool) and version != last_version


def snapshot_frame(version, payload):
    try:
        version_text = str(int(version))
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError):
        version_text = "0"
    source = payload if isinstance(payload, dict) else {}
    try:
        wire = json.dumps(source, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError):
        wire = b'{"type":"playback","state_version":0,"truncated":true}'
    prefix = ("id: %s\nevent: playback\ndata: " % version_text).encode("ascii")
    suffix = b"\n\n"
    if len(prefix) + len(wire) + len(suffix) > MAX_SSE_FRAME_BYTES:
        try:
            safe_version = int(version) if version_text != "0" else 0
        except (TypeError, ValueError, OverflowError):
            safe_version = 0
        wire = json.dumps({"type": "playback", "state_version": safe_version, "truncated": True}, separators=(",", ":")).encode("ascii")
    return prefix + wire + suffix


def keepalive_frame():
    return b": keepalive\n\n"


__all__ = ["MAX_SSE_FRAME_BYTES", "keepalive_frame", "snapshot_changed", "snapshot_frame"]
