"""Pure SQL filter assembly for ordinary track pagination."""

from __future__ import annotations


def _safe_attr(value, name, default=""):
    try:
        return getattr(value, name, default)
    except Exception:
        return default


def build_track_filters(page_query, *, search_condition, group_condition, use_fts=False):
    """Return ``(where_clauses, args)`` for a normalized page query.

    The callbacks own SQL generation; this module only decides which indexed
    fields participate, keeping query semantics testable without SQLite.
    """
    where = []
    args = []
    view = _safe_attr(page_query, "view")
    group = _safe_attr(page_query, "group")
    album = _safe_attr(page_query, "album")
    folder = _safe_attr(page_query, "folder")
    root = _safe_attr(page_query, "root")
    search = _safe_attr(page_query, "search")
    use_fts = bool(use_fts)

    if view in ("albums", "artists", "composers", "genres") and group:
        condition, values = group_condition(_safe_attr(page_query, "group_column"), group)
        where.append(condition)
        args.extend(values)
    elif view == "folders" and folder:
        if root:
            where.append("root = ?")
            args.append(root)
        where.append("folder = ?")
        args.append(folder)
    elif view == "folders" and root:
        where.extend(("root = ?", "folder = ?"))
        args.extend((root, ""))

    if view in ("artists", "composers") and group and album:
        condition, values = group_condition("album", album)
        where.append(condition)
        args.extend(values)
    if search:
        condition, values = search_condition(search, use_fts=use_fts)
        where.append(condition)
        args.extend(values)
    return where, args


__all__ = ["build_track_filters"]
