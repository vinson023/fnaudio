"""Safe public projection for paged library group rows."""

from collections.abc import Mapping

GROUP_FIELDS = ("name", "artist", "track_count", "cover_track_id")
FOLDER_FIELDS = ("path", "root", "parent", "name", "track_count", "cover_track_id")
MAX_PROJECTED_ROWS = 5000


def _project_row(row, fields):
    """Copy selected fields from mappings and sqlite3.Row-like objects."""
    if not isinstance(row, Mapping) and not callable(getattr(row, "keys", None)):
        return {}
    result = {}
    for field in fields:
        try:
            if isinstance(row, Mapping):
                present = field in row
            else:
                present = field in row.keys()
            if present:
                result[field] = row[field]
        except Exception:
            continue
    return result


def project_group_row(row):
    """Copy only public group fields, omitting SQL window metadata."""
    return _project_row(row, GROUP_FIELDS)


def _project_rows(rows, fields, limit=MAX_PROJECTED_ROWS):
    """Project a bounded iterable while isolating iterator and row errors."""
    if isinstance(limit, bool) or not isinstance(limit, int):
        limit = MAX_PROJECTED_ROWS
    limit = max(0, min(MAX_PROJECTED_ROWS, limit))
    if limit == 0:
        return []
    result = []
    try:
        iterator = iter(rows)
    except Exception:
        return result
    while len(result) < limit:
        try:
            row = next(iterator)
        except (StopIteration, RuntimeError, TypeError, ValueError):
            break
        projected = _project_row(row, fields)
        if projected:
            result.append(projected)
    return result


def project_group_rows(rows, limit=5000):
    """Project a bounded iterable of group rows without untrusted coercion."""
    return _project_rows(rows, GROUP_FIELDS, limit)


def project_folder_rows(rows, limit=5000):
    """Copy only public folder fields from a bounded row iterable."""
    return _project_rows(rows, FOLDER_FIELDS, limit)


__all__ = ["FOLDER_FIELDS", "GROUP_FIELDS", "MAX_PROJECTED_ROWS", "project_folder_rows", "project_group_row", "project_group_rows"]
