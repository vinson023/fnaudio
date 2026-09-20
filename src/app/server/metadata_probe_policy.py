"""Pure policy for deciding when local metadata fallback is required."""

from __future__ import annotations

from metadata_text import clean_tag
from scan_numeric_policy import safe_int


REQUIRED_TEXT_FIELDS = ("title", "artist", "album", "composer", "genre")


def probe_tags_complete(tags):
    if not isinstance(tags, dict):
        return False
    try:
        return all(clean_tag(tags.get(key)) for key in REQUIRED_TEXT_FIELDS) and safe_int(tags.get("track_no")) > 0
    except Exception:
        return False


def merge_missing_tags(tags, fallback):
    if isinstance(tags, dict):
        try:
            result = dict(tags)
        except Exception:
            result = {}
    else:
        result = {}
    if not isinstance(fallback, dict):
        return result
    try:
        for key, value in fallback.items():
            result.setdefault(key, value)
    except Exception:
        return result
    return result


__all__ = ["REQUIRED_TEXT_FIELDS", "merge_missing_tags", "probe_tags_complete"]
