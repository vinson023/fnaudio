"""Shared folder-scope semantics for the SQLite and the memory library reader.

``tracks.folder`` stores the leaf directory a file sits in, while the folder
browser lists containers whose ``track_count`` covers the whole subtree beneath
them.  Both query engines therefore need one rule for "is this row inside that
container": an exact ``folder = ?`` matched zero rows for every container that
only holds subdirectories, and the resulting empty page used to fall through to
a Python filter-and-sort over the entire library.
"""

from __future__ import annotations

FOLDER_SEPARATOR = "/"
# ``folder`` is compared with SQLite's BINARY collation, i.e. raw UTF-8 bytes.
# '/' is 0x2F and '0' is 0x30 with nothing between them, so the half-open range
# (scope + "/", scope + "0") holds exactly the strings starting with
# scope + "/" and cannot leak a sibling such as "DSD!" or "DSD1".
FOLDER_SUBTREE_STOP = "0"


def folder_scope(value):
    """Return the normalized relative folder a browse scope refers to.

    Empty segments and ``.`` are dropped because ``relative_folder_for_path()``
    stores the same form, so a scope sent as ``/DSD/`` still addresses ``DSD``.
    A scope reaching above its root (``..``) can never exist in the index, so it
    is returned verbatim and the predicate simply matches nothing instead of
    silently widening the scope.
    """
    if not isinstance(value, str) or not value:
        return ""
    parts = value.split(FOLDER_SEPARATOR)
    cleaned = [part for part in parts if part and part != "."]
    if not cleaned:
        return ""
    if any(part == ".." for part in cleaned):
        return value
    return FOLDER_SEPARATOR.join(cleaned)


def folder_subtree_clause(scope):
    """Return ``(sql, args)`` matching ``scope`` itself and everything below it.

    An empty scope is a caller error: it would widen the predicate to the whole
    table, so it is rejected instead of silently becoming "no filter".
    """
    normalized = folder_scope(scope)
    if not normalized:
        raise ValueError("folder subtree needs a non-empty scope")
    return (
        "(folder = ? OR (folder > ? AND folder < ?))",
        [normalized, normalized + FOLDER_SEPARATOR, normalized + FOLDER_SUBTREE_STOP],
    )


def folder_in_subtree(value, scope):
    """Python mirror of :func:`folder_subtree_clause` for the memory reader."""
    normalized = folder_scope(scope)
    if not normalized:
        return True
    if not isinstance(value, str):
        return False
    return value == normalized or value.startswith(normalized + FOLDER_SEPARATOR)


__all__ = ["FOLDER_SEPARATOR", "FOLDER_SUBTREE_STOP", "folder_in_subtree", "folder_scope", "folder_subtree_clause"]
