"""Strict, bounded normalization for public metadata track identifiers."""

MAX_TRACK_ID_LENGTH = 256


def normalize_track_id(value, limit=MAX_TRACK_ID_LENGTH):
    """Return a stable track id or an empty string without coercing objects."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        limit = MAX_TRACK_ID_LENGTH
    limit = min(MAX_TRACK_ID_LENGTH, limit)
    if isinstance(value, bool):
        return ""
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
    else:
        return ""
    if not text or len(text) > limit:
        return ""
    return text


__all__ = ["MAX_TRACK_ID_LENGTH", "normalize_track_id"]
