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
        # Opening a folder shows the files that sit directly in it.  Its
        # subdirectories are separate rows on the same page, so widening the
        # predicate to the whole subtree listed those files twice and made a
        # small album look like it contained everything its subfolders held.
        # ``tracks.folder`` holds the leaf directory, so the page is an exact
        # match on the normalized scope -- including the empty scope, which is
        # the files that sit directly in the library root.
        if root:
            where.append("root = ?")
            args.append(root)
        scope = folder_scope(folder)
        if bool(_safe_attr(page_query, "subtree", False)):
            # Queueing or playing a folder row means everything beneath it, so
            # that one request asks for the subtree.  An empty scope has no
            # narrower form: it is the whole root.
            if scope:
                condition, values = folder_subtree_clause(scope)
                where.append(condition)
                args.extend(values)
        else:
            where.append("folder = ?")
            args.append(scope)
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
