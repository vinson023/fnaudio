"""Validation for saved library views.

A saved view is the library's current *filter* — not its page, not its scroll
position, not its queue. Storing the filter is what makes "最近添加的 DSD" a
one-click place instead of five clicks and a dropdown.

Everything here is pure: it turns untrusted JSON into a bounded, typed record or
raises ``ValueError``. Storage and HTTP live in ``library_saved_views`` and
``server`` respectively, so this module can be exercised without a database.

The whitelists below are deliberately duplicated from the query layer rather
than imported: a view that stores a sort key the query layer has dropped would
fail at click time, far from the write that created it. ``test_library_saved_view_policy``
asserts the two lists stay in sync.
"""

from __future__ import annotations

import hashlib
import time

VIEW_NAMES = (
    "all",
    "dsd",
    "recent",
    "random100",
    "favorites",
    "queue",
    "folders",
    "albums",
    "artists",
    "composers",
    "genres",
)
SORT_KEYS = ("title", "artist", "album", "format", "added", "track_no")
MAX_VIEWS = 24
MAX_NAME_CHARS = 48
MAX_ID_CHARS = 24
MAX_GROUP_CHARS = 256
MAX_ALBUM_CHARS = 256
MAX_SEARCH_CHARS = 512
MAX_PATH_CHARS = 4096
_ID_PREFIX = "sv_"
_ID_HEX_CHARS = 12
_CONTROL_CHARS = {code for code in range(0x20)} | {0x7F}


def _text(value, limit):
    if not isinstance(value, str):
        return ""
    cleaned = "".join(char for char in value if ord(char) not in _CONTROL_CHARS)
    return cleaned.strip()[:limit]


def _boolean(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return False


def normalize_criteria(raw):
    """Return a bounded criteria dict; unknown keys are dropped, not merged."""
    source = raw if isinstance(raw, dict) else {}
    view = _text(source.get("view"), 32).lower() or "all"
    if view not in VIEW_NAMES:
        raise ValueError("unsupported view: %s" % view)
    sort = _text(source.get("sort"), 32).lower() or "title"
    if sort not in SORT_KEYS:
        sort = "title"
    direction = "desc" if _text(source.get("dir"), 8).lower() == "desc" else "asc"
    return {
        "view": view,
        "group": _text(source.get("group"), MAX_GROUP_CHARS),
        "album": _text(source.get("album"), MAX_ALBUM_CHARS),
        "folder": _text(source.get("folder"), MAX_PATH_CHARS),
        "root": _text(source.get("root"), MAX_PATH_CHARS),
        "search": _text(source.get("search"), MAX_SEARCH_CHARS),
        "sort": sort,
        "dir": direction,
        "subtree": _boolean(source.get("subtree")),
    }


def view_identity(name):
    """Stable id for a view name.

    Identity follows the *name*, not the filter: saving "DSD" again after adding
    a genre filter must replace that place, not create a second one beside it.
    Two names that differ only by case collapse, which is what keeps
    "DSD"/"dsd" from becoming two indistinguishable rows.
    """
    payload = (name or "").casefold()
    digest = hashlib.sha1(payload.encode("utf-8", "surrogatepass")).hexdigest()
    return _ID_PREFIX + digest[:_ID_HEX_CHARS]


def _normalize_id(value, fallback):
    raw = _text(value, MAX_ID_CHARS).lower()
    if (
        raw.startswith(_ID_PREFIX)
        and len(raw) == len(_ID_PREFIX) + _ID_HEX_CHARS
        and all(char in "0123456789abcdef" for char in raw[len(_ID_PREFIX):])
    ):
        return raw
    return fallback


def _stamp(value):
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return number if 0 < number < 10**12 else 0


def normalize_view(raw, now=None):
    """Turn one untrusted view record into a storable one."""
    source = raw if isinstance(raw, dict) else None
    if source is None:
        raise ValueError("view must be an object")
    name = _text(source.get("name"), MAX_NAME_CHARS)
    if not name:
        raise ValueError("view name is required")
    criteria = normalize_criteria(source.get("criteria"))
    stamp = _stamp(now)
    if not stamp:
        # Reading a stored row keeps its own timestamp; only a write supplies
        # ``now``. Falling back to the wall clock here would make every read
        # reorder the list.
        stamp = _stamp(source.get("updated_at")) or int(time.time())
    created = _stamp(source.get("created_at")) or stamp
    return {
        "id": _normalize_id(source.get("id"), view_identity(name)),
        "name": name,
        "criteria": criteria,
        "created_at": created,
        "updated_at": stamp,
    }


def normalize_views(values):
    """Normalize a stored list: newest first, ids unique, count capped."""
    if not isinstance(values, list):
        return []
    views = []
    seen = set()
    for raw in values:
        try:
            view = normalize_view(raw, now=(raw or {}).get("updated_at") if isinstance(raw, dict) else None)
        except (ValueError, TypeError):
            continue
        if view["id"] in seen:
            continue
        seen.add(view["id"])
        views.append(view)
    views.sort(key=lambda item: (-int(item["updated_at"]), item["id"]))
    return views[:MAX_VIEWS]


def merge_view(views, view):
    """Insert or replace one view, keeping newest-first order and the cap."""
    current = [item for item in normalize_views(views) if item["id"] != view["id"]]
    return normalize_views([view] + current)


def remove_view(views, view_id):
    key = _text(view_id, MAX_ID_CHARS).lower()
    return [item for item in normalize_views(views) if item["id"] != key]


def view_query_params(view):
    """Project a stored view into the parameters ``/api/library`` accepts."""
    criteria = normalize_criteria(view.get("criteria") if isinstance(view, dict) else None)
    params = {
        "view": criteria["view"],
        "sort": criteria["sort"],
        "dir": criteria["dir"],
    }
    for key in ("group", "album", "folder", "root", "search"):
        if criteria[key]:
            params[key] = criteria[key]
    if criteria["subtree"]:
        params["subtree"] = "1"
    return params


__all__ = [
    "MAX_NAME_CHARS",
    "MAX_VIEWS",
    "SORT_KEYS",
    "VIEW_NAMES",
    "merge_view",
    "normalize_criteria",
    "normalize_view",
    "normalize_views",
    "remove_view",
    "view_identity",
    "view_query_params",
]
