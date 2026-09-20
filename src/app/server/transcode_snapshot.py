"""Bounded, privacy-safe transcode scheduler status for public APIs."""

from __future__ import annotations

import math
import re

from summary_values import nonnegative_int

_DECIMAL_TEXT = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


def _float(value):
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, str):
        if not _DECIMAL_TEXT.fullmatch(value.strip()):
            return 0.0
        value = float(value)
    elif not isinstance(value, (int, float)):
        return 0.0
    normalized = float(value)
    return max(0.0, normalized) if math.isfinite(normalized) else 0.0


def _safe_get(source, key, default=None):
    if not isinstance(source, dict):
        return default
    try:
        return source.get(key, default)
    except Exception:
        return default


def transcode_summary(transcode):
    """Expose scheduler pressure without paths, commands or media details."""
    source = transcode if isinstance(transcode, dict) else {}
    ffmpeg = _safe_get(source, "ffmpeg")
    ffmpeg = ffmpeg if isinstance(ffmpeg, dict) else {}
    return {
        "queued": nonnegative_int(_safe_get(source, "queued")),
        "tracked": nonnegative_int(_safe_get(source, "tracked")),
        "queue_limit": nonnegative_int(_safe_get(source, "queue_limit")),
        "ffmpeg": {
            "active": nonnegative_int(_safe_get(ffmpeg, "active")),
            "limit": nonnegative_int(_safe_get(ffmpeg, "limit")),
            "waiting": nonnegative_int(_safe_get(ffmpeg, "waiting")),
            "peak": nonnegative_int(_safe_get(ffmpeg, "peak")),
            "peak_waiting": nonnegative_int(_safe_get(ffmpeg, "peak_waiting")),
            "acquired": nonnegative_int(_safe_get(ffmpeg, "acquired")),
            "waited": nonnegative_int(_safe_get(ffmpeg, "waited")),
            "rejected": nonnegative_int(_safe_get(ffmpeg, "rejected")),
            "waiter_rejected": nonnegative_int(_safe_get(ffmpeg, "waiter_rejected")),
            "timed_out": nonnegative_int(_safe_get(ffmpeg, "timed_out")),
            "waiter_limit": nonnegative_int(_safe_get(ffmpeg, "waiter_limit")),
            "wait_seconds": round(_float(_safe_get(ffmpeg, "wait_seconds")), 3),
        },
    }
