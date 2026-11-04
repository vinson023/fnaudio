"""Folder browse scope: one directory page, or one directory *and below*.

``tracks.folder`` stores the leaf directory a file sits in, and the folder
browser lists containers one level at a time.  Opening a container therefore
shows the files that sit *directly* in it: the subdirectories are separate rows
on the same page, so folding their tracks into the page as well listed the same
file twice and buried a small album under the contents of its own subfolders.

Acting on a folder row as a whole -- queueing it, playing it -- still means
everything beneath it, which is the one request that asks for a subtree.  Both
rules share this module so the SQLite predicate and the memory reader can never
drift apart.
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

    An empty result is not an error here: it is the library root itself, where
    the files that sit directly in the root carry ``folder = ''``.
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
