"""What the library endpoint can do, as data instead of a version number.

Audio Station gates features on each endpoint's ``maxVersion`` (see
``WebAPI.resolveCapability``), which is why an old NAS loses a button instead of
erroring. fnAudio shipped one bundle for both sides, so the UI had no way to know
that this particular SQLite build lacks FTS5 or that a view name is unsupported.

This module projects the server's real abilities into a small, stable dict that
``/api/library/status`` returns and ``library_capability_policy.js`` reads once at
boot. It is pure: callers pass the already-decided search mode and format list.
"""

from __future__ import annotations

from library_saved_view_policy import MAX_VIEWS, SORT_KEYS, VIEW_NAMES
from library_search_index_policy import FTS_MODE, LIKE_MODE, search_index_status
from library_search_query_policy import FTS_MIN_TERM_CHARS, SEARCH_FIELDS

CAPABILITY_VERSION = 1


def _formats(values):
    if not isinstance(values, (list, tuple, set)):
        return []
    cleaned = {str(value).strip().upper() for value in values if isinstance(value, str) and value.strip()}
    return sorted(item for item in cleaned if item)[:64]


def library_capabilities(search_mode, formats=()):
    """Build the capability block; unknown inputs degrade instead of raising."""
    mode = search_mode if isinstance(search_mode, str) and search_mode in (FTS_MODE, LIKE_MODE) else LIKE_MODE
    status = search_index_status(mode)
    return {
        "version": CAPABILITY_VERSION,
        "saved_views": {"enabled": True, "limit": MAX_VIEWS},
        "search": {
            "mode": status["mode"],
            "min_chars": status["substring_minimum_chars"],
            "field_syntax": True,
            "fields": list(SEARCH_FIELDS),
            "field_min_chars": FTS_MIN_TERM_CHARS if mode == FTS_MODE else 0,
        },
        "sort": {"keys": list(SORT_KEYS), "directions": ["asc", "desc"]},
        "views": list(VIEW_NAMES),
        "formats": _formats(formats),
    }


def supports_field_syntax(capabilities, field=None):
    """True when the client may offer ``field:term`` search."""
    try:
        search = capabilities["search"]
    except (TypeError, KeyError):
        return False
    if not isinstance(search, dict) or search.get("field_syntax") is not True:
        return False
    if field is None:
        return True
    fields = search.get("fields")
    return isinstance(fields, list) and field in fields


__all__ = [
    "CAPABILITY_VERSION",
    "library_capabilities",
    "supports_field_syntax",
]
