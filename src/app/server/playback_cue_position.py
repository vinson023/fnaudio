"""Pure CUE segment position normalization for playback status responses."""

from __future__ import annotations

import math


def _number(value):
    try:
        number = float(value) if value is not None else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def normalize_cue_position(status, item):
    """Return ``(status_copy, finished)`` for a CUE track, or unchanged state.

    MPD reports CUE+APE segments from zero, while native CUE playback reports
    the position in the source file.  The returned mapping is always copied
    so callers can safely reuse backend snapshots.
    """
    if not isinstance(item, dict) or not item.get("cue_track"):
        return dict(status or {}), False
    normalized = dict(status or {})
    position = dict(normalized.get("position") or {})
    whole_seconds = _number(position.get("rel_seconds"))
    cue_start = _number(item.get("cue_start"))
    # cue_end 0.0 is the stored marker for "no known boundary".  Every guard below
    # compares it against cue_start, so an unknown end leaves the position
    # unclamped and never reports the segment as finished, rather than inventing a
    # length for it.
    cue_end = _number(item.get("cue_end"))
    cue_duration = max(0.0, _number(item.get("duration")) or (cue_end - cue_start))
    cue_transcoded = str(item.get("path") or "").lower().endswith(".ape")
    rel = max(0.0, whole_seconds if cue_transcoded else whole_seconds - cue_start)
    if cue_duration > 0:
        rel = min(rel, cue_duration)
    position.update({
        "rel_seconds": rel,
        "duration_seconds": cue_duration,
        "cue_start": cue_start,
        "cue_end": cue_end,
        "cue_transcoded": cue_transcoded,
    })
    normalized["position"] = position
    finished = rel >= max(0.0, cue_duration - 0.25) if cue_transcoded else whole_seconds >= max(cue_start, cue_end - 0.25)
    return normalized, bool(cue_end > cue_start and finished)
