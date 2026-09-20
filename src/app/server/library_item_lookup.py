"""Small, testable lookup helpers for individual library items."""

from collections.abc import Mapping


def lookup_sqlite_item(conn, item_id, decode_row):
    """Fetch one item by normalized ID, isolating adapter/row failures."""
    if not isinstance(item_id, str) or not item_id or not callable(decode_row):
        return None
    try:
        row = conn.execute(
            "SELECT item_json FROM tracks WHERE id = ? LIMIT 1", (item_id,)
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    try:
        value = decode_row(row)
    except Exception:
        return None
    return value if isinstance(value, Mapping) else None


def lookup_memory_item(items, item_id):
    """Find an item in the in-memory fallback without coercing arbitrary values."""
    if not isinstance(item_id, str) or not item_id:
        return None
    try:
        iterator = iter(items)
    except Exception:
        return None
    while True:
        try:
            item = next(iterator)
        except (StopIteration, RuntimeError, TypeError, ValueError):
            return None
        if not isinstance(item, Mapping):
            continue
        try:
            candidate_id = item.get("id")
        except Exception:
            continue
        if candidate_id == item_id:
            return item


__all__ = ["lookup_memory_item", "lookup_sqlite_item"]
