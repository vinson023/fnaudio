"""Pure policy for selecting an embedded-cover reader by media path."""

from __future__ import annotations

import os

SUPPORTED_COVER_KINDS = {
    ".mp3": "id3",
    ".dsf": "id3",
    ".dff": "id3",
    ".ape": "ape",
    ".wav": "wav",
    ".flac": "flac",
    ".m4a": "mp4",
    ".mp4": "mp4",
}


def cover_kind(path):
    """Return a bounded reader key without coercing arbitrary path objects."""
    if not isinstance(path, str):
        return ""
    try:
        return SUPPORTED_COVER_KINDS.get(os.path.splitext(path[:4096])[1].lower(), "")
    except (OSError, ValueError):
        return ""


__all__ = ["SUPPORTED_COVER_KINDS", "cover_kind"]
