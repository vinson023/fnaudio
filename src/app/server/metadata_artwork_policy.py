"""Pure, bounded policy for persisted metadata artwork references."""

from __future__ import annotations

import re


ARTWORK_ID_LENGTH = 64
_ARTWORK_ID_PATTERN = re.compile(r"[0-9a-f]{64}")


def normalize_artwork_id(value):
    """Return a canonical content-addressed artwork id or an empty string."""
    if not isinstance(value, str):
        return ""
    candidate = value.strip().lower()
    return candidate if _ARTWORK_ID_PATTERN.fullmatch(candidate) else ""


def valid_artwork_id(value):
    """Accept only the SHA-256-shaped ids produced by the artwork cache."""
    return bool(normalize_artwork_id(value))


def artwork_url(value):
    """Project a valid artwork id to its relative public URL."""
    artwork_id = normalize_artwork_id(value)
    return "metadata/artwork/" + artwork_id if artwork_id else ""


def is_artwork_url(value):
    """Accept only canonical relative artwork URLs produced by this policy."""
    if not isinstance(value, str) or not value.startswith("metadata/artwork/"):
        return False
    artwork_id = value[len("metadata/artwork/"):]
    return bool(artwork_id) and value == artwork_url(artwork_id)


__all__ = ["ARTWORK_ID_LENGTH", "artwork_url", "is_artwork_url", "normalize_artwork_id", "valid_artwork_id"]
