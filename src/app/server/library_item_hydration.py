"""Bounded SQLite hydration for ordered library item identifiers.

The public HTTP endpoint limits IDs to one small request.  Playback restore,
however, may need to rebuild a persisted queue containing thousands of IDs.
This adapter keeps the query itself under SQLite's variable limit without
letting SQL's unspecified ``IN`` ordering leak into the playback queue.
"""

from __future__ import annotations

MAX_HYDRATION_ITEMS = 50_000

def hydrate_items_by_ids(conn, item_ids, decode_rows, batch_size, max_items=MAX_HYDRATION_ITEMS):
    """Read normalized IDs in bounded batches and restore requested order.

    ``item_ids`` must already have passed the transport/input normalizer.  A
    missing row is deliberately omitted: this is the expected result when a
    file disappeared after a queue was persisted.
    """
    if not isinstance(item_ids, (list, tuple)) or not callable(decode_rows):
        return []
    if isinstance(batch_size, bool) or not isinstance(batch_size, int):
        return []
    batch_size = max(1, batch_size)
    if isinstance(max_items, bool) or not isinstance(max_items, int):
        max_items = MAX_HYDRATION_ITEMS
    max_items = max(0, min(MAX_HYDRATION_ITEMS, max_items))
    if max_items == 0:
        return []
    # Playback restore may legitimately contain more IDs than one HTTP
    # request, but a damaged persisted queue must not create unbounded SQL
    # batches or retain an unbounded result map.
    bounded_ids = item_ids[:max_items]
    query_ids = list(dict.fromkeys(bounded_ids))
    by_id = {}
    for start in range(0, len(query_ids), batch_size):
        batch = query_ids[start:start + batch_size]
        placeholders = ",".join("?" for _ in batch)
        rows = conn.execute("SELECT item_json FROM tracks WHERE id IN (%s)" % placeholders, batch)
        for item in decode_rows(rows):
            item_id = item.get("id") if isinstance(item, dict) else None
            if isinstance(item_id, str):
                by_id[item_id] = item
    return [by_id[item_id] for item_id in bounded_ids if item_id in by_id]


__all__ = ["MAX_HYDRATION_ITEMS", "hydrate_items_by_ids"]
