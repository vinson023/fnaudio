"""Pure, bounded decisions for the lyrics cache fast path."""

import math


def _finite_time(value, fallback=0):
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return fallback
        return number if math.isfinite(number) else fallback
    return fallback


def cached_lyrics_is_fresh(row, now):
    """Return true only for a non-empty, unexpired lyrics cache row.

    Artwork-only rows are deliberately incomplete because artwork and lyrics
    are produced by separate workers.  Invalid row shapes fail closed.
    """
    if not isinstance(row, dict):
        try:
            lyrics = row["lyrics"]
            expires_at = row["expires_at"]
        except (KeyError, TypeError, IndexError):
            return False
    else:
        lyrics = row.get("lyrics")
        expires_at = row.get("expires_at")
    if not isinstance(lyrics, str) or not lyrics.strip():
        return False
    expiry = _finite_time(expires_at)
    current = _finite_time(now)
    return expiry > current


__all__ = ["cached_lyrics_is_fresh"]
