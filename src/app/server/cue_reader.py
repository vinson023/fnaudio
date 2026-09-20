"""Bounded CUE source-file reading, separated from parsing policy."""

from __future__ import annotations

MAX_CUE_FILE_BYTES = 8 * 1024 * 1024


def read_cue_lines(cue_path):
    """Decode a CUE file without materializing an unbounded source."""
    if not isinstance(cue_path, str):
        return []
    try:
        with open(cue_path, "rb") as handle:
            payload = handle.read(MAX_CUE_FILE_BYTES + 1)
    except OSError:
        return []
    if len(payload) > MAX_CUE_FILE_BYTES:
        return []
    for encoding in ("utf-8-sig", "gb18030", "big5", "latin1"):
        try:
            return payload.decode(encoding).splitlines()
        except UnicodeError:
            continue
    return []


__all__ = ["MAX_CUE_FILE_BYTES", "read_cue_lines"]
