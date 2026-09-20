"""Pure stop/continue policy for bounded track-candidate searches."""

from __future__ import annotations

import math


MIN_COMPLETE_CONFIDENCE = 0.94
MAX_DISPLAY_CANDIDATES = 8


def _confidence(value, default=None):
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if math.isfinite(result) else default


def finalize_track_candidates(candidates, *, minimum_confidence=0.55, limit=MAX_DISPLAY_CANDIDATES):
    """Filter, deduplicate and order provider candidates for presentation.

    This is deliberately independent from provider I/O and persistence. It
    gives every caller one bounded result contract and prevents malformed
    confidence/title values from escaping the provider boundary.
    """
    try:
        threshold = float(minimum_confidence)
    except (TypeError, ValueError, OverflowError):
        threshold = 0.55
    if not math.isfinite(threshold):
        threshold = 0.55
    try:
        if isinstance(limit, bool) or not isinstance(limit, (str, int, float)):
            raise TypeError
        numeric_limit = float(limit)
        if not math.isfinite(numeric_limit) or numeric_limit != math.trunc(numeric_limit):
            raise ValueError
        bound = max(0, min(MAX_DISPLAY_CANDIDATES, int(numeric_limit)))
    except (TypeError, ValueError, OverflowError):
        bound = MAX_DISPLAY_CANDIDATES
    if bound == 0 or not isinstance(candidates, (list, tuple)):
        return []
    deduped = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        confidence = _confidence(candidate.get("confidence"), 0.0)
        if confidence is None:
            continue
        title = candidate.get("title")
        if confidence < threshold or not isinstance(title, str) or not title.strip():
            continue
        key = "\x1f".join(
            value.casefold() if isinstance(value, str) else ""
            for value in (candidate.get("title"), candidate.get("artist"), candidate.get("album"))
        )
        if key and prefer_track_candidate(candidate, deduped.get(key)):
            deduped[key] = candidate
    return sorted(deduped.values(), key=lambda item: _confidence(item.get("confidence"), 0.0), reverse=True)[:bound]


def should_stop_track_candidate_search(candidate, *, minimum_confidence=MIN_COMPLETE_CONFIDENCE):
    """Stop provider fan-out once a high-confidence, display-complete match exists.

    A candidate must include title, artist, album and artwork.  This keeps the
    fallback chain available for sparse matches while avoiding several serial
    provider requests after the current song already has enough metadata for
    immediate playback/lyrics presentation.
    """
    if not isinstance(candidate, dict):
        return False
    try:
        raw_confidence = candidate.get("confidence")
        if isinstance(raw_confidence, bool):
            return False
        confidence = float(raw_confidence)
    except (TypeError, ValueError, OverflowError):
        return False
    if not math.isfinite(confidence):
        return False
    try:
        threshold = float(minimum_confidence)
    except (TypeError, ValueError, OverflowError):
        return False
    if not math.isfinite(threshold) or confidence < threshold:
        return False
    return all(isinstance(candidate.get(field), str) and candidate.get(field).strip()
               for field in ("title", "artist", "album", "image_url"))


def prefer_track_candidate(candidate, current):
    """Choose the more useful candidate for an equivalent recording.

    Provider scores are not directly comparable. A slightly lower-scoring
    result that includes artwork (or more display fields) is more useful than
    a sparse result, especially for the current-song presentation path.
    """
    if not isinstance(candidate, dict):
        return False
    if not isinstance(current, dict):
        return True
    def completeness(item):
        score = 0
        for field in ("title", "artist", "album", "album_artist", "image_url"):
            value = item.get(field)
            if isinstance(value, str) and value.strip():
                score += 1
        return score
    candidate_complete = completeness(candidate)
    current_complete = completeness(current)
    if candidate_complete != current_complete:
        return candidate_complete > current_complete
    candidate_confidence = _confidence(candidate.get("confidence"), 0.0)
    current_confidence = _confidence(current.get("confidence"), 0.0)
    return candidate_confidence > current_confidence


__all__ = ["MAX_DISPLAY_CANDIDATES", "MIN_COMPLETE_CONFIDENCE", "finalize_track_candidates", "prefer_track_candidate", "should_stop_track_candidate_search"]
