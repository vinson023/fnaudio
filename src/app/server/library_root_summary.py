"""Validation boundary for the persisted root-browser summary."""

from __future__ import annotations

import json
from summary_values import nonnegative_int


MAX_ROOT_SUMMARY_CHARS = 65536


def decode_root_summary(raw_summary, roots):
    """Return validated root rows, or ``None`` when SQL must be authoritative."""
    if not isinstance(raw_summary, str) or len(raw_summary) > MAX_ROOT_SUMMARY_CHARS:
        return None
    try:
        source = json.loads(raw_summary)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(source, dict):
        return None
    rows = {}
    for root in roots:
        value = source.get(root)
        if not isinstance(value, dict):
            return None
        count = nonnegative_int(value.get("track_count", 0), maximum=1000000000)
        cover_track_id = value.get("cover_track_id", "")
        if not isinstance(cover_track_id, str):
            return None
        rows[root] = {"root": root, "track_count": count, "cover_track_id": cover_track_id}
    return rows
