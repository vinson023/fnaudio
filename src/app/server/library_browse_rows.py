"""Bounded materialization for legacy unpaged library browse responses."""

from __future__ import annotations


MAX_UNPAGED_BROWSE_ROWS = 5000


def materialize_browse_rows(rows, limit=MAX_UNPAGED_BROWSE_ROWS):
    """Copy at most ``limit`` mapping rows without trusting iteration hooks."""
    if isinstance(limit, bool) or not isinstance(limit, int):
        limit = MAX_UNPAGED_BROWSE_ROWS
    limit = max(0, min(MAX_UNPAGED_BROWSE_ROWS, limit))
    result = []
    try:
        iterator = iter(rows)
    except Exception:
        return result
    for _ in range(limit):
        try:
            row = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        try:
            result.append(dict(row))
        except Exception:
            continue
    return result


__all__ = ["MAX_UNPAGED_BROWSE_ROWS", "materialize_browse_rows"]
