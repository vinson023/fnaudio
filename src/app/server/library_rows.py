"""Small pure helpers for decoding SQLite library rows."""

from __future__ import annotations

import json

MAX_ITEM_JSON_BYTES = 1024 * 1024


def item_json_within_limit(payload):
    """Check SQLite JSON text against the byte budget without taxing small rows."""
    if not isinstance(payload, str) or len(payload) > MAX_ITEM_JSON_BYTES:
        return False
    # ASCII JSON is one byte per character; only encode the bounded near-limit
    # case so ordinary rows avoid an extra allocation.
    return (len(payload) < MAX_ITEM_JSON_BYTES // 2
            or len(payload.encode("utf-8", "ignore")) <= MAX_ITEM_JSON_BYTES)


def decode_item_payload(payload):
    """Decode one bounded item JSON object, returning None on bad input."""
    if not item_json_within_limit(payload):
        return None
    try:
        item = json.loads(payload)
    except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
        return None
    return item if isinstance(item, dict) else None


def decode_item_rows(rows):
    items = []
    if rows is None:
        return items
    try:
        iterator = iter(rows)
    except TypeError:
        return items
    for row in iterator:
        if not hasattr(row, "__getitem__"):
            continue
        try:
            payload = row["item_json"]
            item = decode_item_payload(payload)
            if item is not None:
                items.append(item)
        except Exception:
            # A database adapter may expose a row-like object whose field
            # accessor raises a non-standard exception.  One malformed row
            # must never abort decoding of the remaining page.
            continue
    return items


def decode_item_row(row):
    if not row:
        return None
    items = decode_item_rows((row,))
    return items[0] if items else None


__all__ = [
    "MAX_ITEM_JSON_BYTES", "decode_item_payload", "decode_item_row",
    "decode_item_rows", "item_json_within_limit",
]
