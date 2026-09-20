"""Bounded text projection for DLNA XML and URI presentation."""

from __future__ import annotations


MAX_DLNA_TEXT_CHARS = 1024
MAX_DLNA_ID_CHARS = 512


def dlna_text(value, limit=MAX_DLNA_TEXT_CHARS, fallback=""):
    """Keep only bounded text accepted by XML 1.0."""
    if not isinstance(value, str):
        return fallback
    try:
        limit = max(0, min(MAX_DLNA_TEXT_CHARS, int(limit)))
    except (TypeError, ValueError, OverflowError):
        limit = MAX_DLNA_TEXT_CHARS
    value = value[:limit]
    return "".join(
        character
        for character in value
        if character in ("\x09", "\x0a", "\x0d") or ord(character) >= 0x20
    )


__all__ = ["MAX_DLNA_TEXT_CHARS", "MAX_DLNA_ID_CHARS", "dlna_text"]
