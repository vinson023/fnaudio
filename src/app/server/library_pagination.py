"""Compatibility-safe SQLite window pagination execution."""

from __future__ import annotations

import sqlite3
import math


MAX_PAGE_ROWS = 500


def _bounded_rows(rows, limit=MAX_PAGE_ROWS):
    """Materialize only the bounded page prefix, isolating cursor failures."""
    iterator = iter(rows)
    result = []
    for _ in range(max(0, limit)):
        try:
            result.append(next(iterator))
        except StopIteration:
            break
        except Exception:
            # Let the caller select its precise count/page fallback when a
            # cursor fails mid-iteration; silently returning a partial page
            # would make the total ambiguous.
            raise
    return result


def _safe_total(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return max(0, int(value))
    return None


def _count_total(conn, count_sql, count_args):
    try:
        row = conn.execute(count_sql, count_args).fetchone()
        value = row[0] if row is not None else None
    except (AttributeError, IndexError, KeyError, TypeError, RuntimeError, ValueError, sqlite3.Error):
        value = None
    total = _safe_total(value)
    return total if total is not None else 0


def paged_rows_with_total(conn, window_sql, window_args, count_sql, count_args, page_sql, page_args):
    """Read a page and its total with a one-query modern SQLite fast path.

    An empty out-of-range page has no row from which to read the window total,
    and old SQLite builds may not support window functions. Both cases retain
    the precise historical count-then-page fallback.
    """
    try:
        rows = _bounded_rows(conn.execute(window_sql, window_args))
    except (AttributeError, sqlite3.OperationalError, TypeError, ValueError, RuntimeError):
        count = _count_total(conn, count_sql, count_args)
        try:
            rows = _bounded_rows(conn.execute(page_sql, page_args))
        except (AttributeError, TypeError, ValueError, RuntimeError, sqlite3.Error):
            rows = []
        return rows, count
    if rows:
        try:
            total = _safe_total(rows[0]["total_count"])
        except (KeyError, IndexError, TypeError):
            total = None
        if total is not None:
            return rows, total
    return rows, _count_total(conn, count_sql, count_args)


def counted_page_rows(conn, page_sql, page_args, count_sql, count_args):
    """Read a page and its total as two independent statements.

    ``paged_rows_with_total`` carries the total inside a window function, which
    only pays off when the page has to touch every matching row anyway.  A page
    that an ordering index can seek stops at the page size, so the window would
    force back the full sort the index just avoided.  Both statements keep the
    same isolation as the window path: a failed page yields no rows and a failed
    count yields zero.
    """
    try:
        rows = _bounded_rows(conn.execute(page_sql, page_args))
    except (AttributeError, TypeError, ValueError, RuntimeError, sqlite3.Error):
        rows = []
    return rows, _count_total(conn, count_sql, count_args)


__all__ = ["MAX_PAGE_ROWS", "counted_page_rows", "paged_rows_with_total"]
