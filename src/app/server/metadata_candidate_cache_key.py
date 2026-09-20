"""Bounded identity for the short-lived provider candidate cache."""

from __future__ import annotations

import math

from metadata_query_policy import filename_track_hint, track_search_query

MAX_CACHE_TEXT = 256


def _part(value):
    if isinstance(value, str):
        return value.replace("\x00", "").strip()[:MAX_CACHE_TEXT].casefold()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return ""
    return str(number)[:64] if math.isfinite(number) else ""


_UNSET = object()


def build_candidate_cache_key(track, query=_UNSET, hinted_artist=_UNSET, hinted_title=_UNSET):
    """Return a stable key including every input used for local fallback."""
    if query is _UNSET:
        query = track_search_query(track)
    if not query:
        return None
    if hinted_artist is _UNSET or hinted_title is _UNSET:
        hinted_artist, hinted_title = filename_track_hint(track)
    try:
        fields = tuple(track.get(field) for field in ("title", "artist", "album", "duration"))
    except (AttributeError, KeyError, IndexError, TypeError):
        fields = (None, None, None, None)
    return (
        _part(query),
        _part(hinted_artist),
        _part(hinted_title),
        *(_part(value) for value in fields),
    )


__all__ = ["MAX_CACHE_TEXT", "build_candidate_cache_key"]
