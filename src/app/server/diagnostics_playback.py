"""Pure playback portion of the privacy-safe diagnostics snapshot."""

from __future__ import annotations

from summary_values import bounded_text, nonnegative_int


def _safe_get(source, key, default=None):
    if not isinstance(source, dict):
        return default
    try:
        return source.get(key, default)
    except Exception:
        return default


def playback_summary(playback):
    """Project playback diagnostics without exposing current media details."""
    source = playback if isinstance(playback, dict) else {}
    current = _safe_get(source, "current")
    has_current = False
    if isinstance(current, dict):
        try:
            has_current = dict.__len__(current) > 0
        except Exception:
            has_current = False
    return {
        "target_id": bounded_text(_safe_get(source, "target_id"), "", 160),
        "transport": bounded_text(_safe_get(source, "transport"), "", 64),
        "queue_length": nonnegative_int(_safe_get(source, "queue_length")),
        "has_current_track": has_current,
    }


__all__ = ["playback_summary"]
