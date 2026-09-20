"""Pure CUE segment position normalization for playback status responses."""

from __future__ import annotations

import math


def _number(value):
    try:
        number = float(value) if value is not None else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def cue_is_transcoded(item):
    """True when a CUE segment is served from a separately decoded file.

    A native CUE track is played from the whole source file, so MPD reports
    source seconds and :func:`normalize_cue_position` folds them down.  An
    APE-backed segment is decoded into its own file and already starts at
    zero, so folding it would move the position by ``cue_start`` twice.  The
    predicate lives here so the fold and :func:`project_cue_seek` can never
    disagree about which shape needs converting.
    """
    if not isinstance(item, dict) or not item.get("cue_track"):
        return False
    return str(item.get("path") or "").lower().endswith(".ape")


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
    cue_transcoded = cue_is_transcoded(item)
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


def cue_segment_declaration(item):
    """Whether a status payload is expressed in CUE-segment seconds.

    Both CUE shapes are segment-relative once they reach a client: an APE
    segment is its own decoded file, and a FLAC segment has its source offset
    folded out by :func:`normalize_cue_position`.  A client must not apply a
    second offset, so every projection carries this declaration instead of
    letting the frontend re-derive it from queue metadata alone.
    """
    return bool(isinstance(item, dict) and item.get("cue_track"))


def public_cue_position(rel_seconds, duration_seconds, item):
    """Project backend-reported seconds onto the units a client displays.

    The fold is delegated to :func:`normalize_cue_position` so the polling
    route, the MPD listener and the authoritative core state share one unit.
    The returned mapping stays bounded to the two keys the progress bar reads.
    """
    normalized, _finished = normalize_cue_position(
        {"position": {
            "rel_seconds": _number(rel_seconds),
            "duration_seconds": _number(duration_seconds),
        }},
        item,
    )
    position = dict(normalized.get("position") or {})
    return {
        "rel_seconds": _number(position.get("rel_seconds")),
        "duration_seconds": _number(position.get("duration_seconds")),
    }


def project_cue_seek(position, item):
    """Map a client seek onto the seconds the backend expects.

    This is the exact inverse of the fold in :func:`normalize_cue_position`:
    a native CUE track is seeked in source-file seconds, while a transcoded
    APE segment and an ordinary track are already in the reported units.
    """
    requested = max(0.0, _number(position))
    if not isinstance(item, dict) or not item.get("cue_track"):
        return requested
    if cue_is_transcoded(item):
        return requested
    return max(0.0, requested + _number(item.get("cue_start")))
