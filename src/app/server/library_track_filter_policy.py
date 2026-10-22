"""Pure SQL filter assembly for ordinary track pagination."""

from __future__ import annotations

from library_folder_scope import folder_scope, folder_subtree_clause


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
    elif view == "folders":
        # A folder row is a container: ``tracks.folder`` only stores the leaf
        # directory, so the scope has to cover the container itself plus every
        # directory below it.  Matching ``folder = ?`` exactly (and ``folder = ''``
        # for a root) returned zero rows for containers holding only
        # subdirectories, which then fell through to a full Python scan.
        if root:
            where.append("root = ?")
            args.append(root)
        scope = folder_scope(folder)
        if scope:
            condition, values = folder_subtree_clause(scope)
            where.append(condition)
            args.extend(values)
    elif view == "dsd":
        where.append("is_dsd = 1")
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
