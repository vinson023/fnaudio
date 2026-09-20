"""Pure projection helpers for SQLite track-page responses."""

from __future__ import annotations

from library_cursor_policy import anchor_is_encodable, encode_track_cursor
from library_rows import decode_item_payload


def _safe_page_limit(value, default=1):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    try:
        if isinstance(value, str):
            value = value.strip()
            if not value or not value.isascii() or not value.isdecimal():
                return default
        value = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(1, min(500, value))


def _row_anchor(row):
    """Return the private ordering key of one projected row."""
    return {
        "primary": row["_cursor_primary"],
        "title": row["_cursor_title"],
        "id": row["_cursor_id"],
    }


def _anchor_is_encodable(anchor):
    if not isinstance(anchor, dict):
        return False
    return anchor_is_encodable(anchor.get("primary"), anchor.get("title"), anchor.get("id"))


def _continuation_anchor(anchor, look_ahead):
    """Keep the served anchor, or move onto the look-ahead row when it cannot anchor.

    A legacy library keeps SQL NULL for an untagged title, artist, album, or
    format, and no comparison predicate can express NULL, so a page that ends on
    such a row used to answer ``has_more`` with no cursor and push the client back
    onto OFFSET pagination. The look-ahead row is the immediate successor in the
    page order, so when it can name a position the page anchors on it and marks it
    inclusive. That substitution is only possible where the unrepresentable group
    ends: NULL values sort as one contiguous block, so a look-ahead row that is
    itself NULL keeps the page on its old no-cursor answer instead of silently
    skipping the rest of that block.
    """
    if _anchor_is_encodable(anchor):
        return anchor
    try:
        pending = _row_anchor(look_ahead)
    except Exception:
        return anchor
    if not _anchor_is_encodable(pending):
        return anchor
    pending["inclusive"] = True
    return pending


def decode_track_cursor_page_rows(rows, limit):
    """Decode one page of at most ``limit`` items plus its continuation anchor.

    Both track-page paths call this: the keyset path reads ``limit + 1`` rows to
    know whether more rows exist, and the offset path reads the same extra row so
    that a page ending on an unrepresentable key can continue as well.
    """
    safe_limit = _safe_page_limit(limit)
    items = []
    anchor = None
    has_more = False
    try:
        iterator = iter(rows)
    except TypeError:
        return items, anchor, has_more
    for row in iterator:
        try:
            item = decode_item_payload(row["item_json"])
            if item is None:
                continue
        except Exception:
            continue
        if len(items) >= safe_limit:
            has_more = True
            anchor = _continuation_anchor(anchor, row)
            break
        items.append(item)
        anchor = _row_anchor(row)
    return items, anchor, has_more


def track_page_select(page_query, window=False):
    """Build the bounded SQL projection shared by page and window queries."""
    select = "SELECT item_json, (%s) AS _cursor_primary, title AS _cursor_title, id AS _cursor_id" % page_query.sql_order
    if window:
        select += ", COUNT(*) OVER() AS total_count"
    return select


def track_page_result(items, count, limit, offset, page_query, anchor=None, has_more=None):
    """Project a page and add a continuation cursor when its last row is usable."""
    result = {"items": items, "count": count, "limit": limit, "offset": offset, "paged": True}
    if items:
        resolved_has_more = (len(items) == limit and offset + len(items) < count) if has_more is None else bool(has_more)
        result["has_more"] = resolved_has_more
        # A terminal page has no valid continuation. Returning an anchor anyway
        # makes clients retain a cursor that can only produce an empty request.
        if not resolved_has_more:
            return result
        last = items[-1] if isinstance(items[-1], dict) else {}
        keyed = isinstance(anchor, dict)
        primary = anchor.get("primary") if keyed else (last.get("added_ns") if page_query.sort_key == "added" else last.get(page_query.sort_key))
        cursor_title = anchor.get("title") if keyed else last.get("title")
        cursor_id = anchor.get("id") if keyed else last.get("id")
        # The flag is only ever set by the decoder, and only when the last served
        # row could not name its own position; a row the client saw stays excluded.
        inclusive = bool(anchor.get("inclusive")) if keyed else False
        if page_query.sort_key == "track_no":
            try:
                primary = int(primary) if int(primary) > 0 else 2147483647
            except (TypeError, ValueError, OverflowError):
                primary = 2147483647
        elif page_query.sort_key == "added":
            try:
                primary = int(primary)
            except (TypeError, ValueError, OverflowError):
                primary = 0
        token = encode_track_cursor(page_query.sort_key, page_query.sort_dir, primary, cursor_title, cursor_id, inclusive)
        if token:
            result["next_cursor"] = token
    return result


__all__ = ["decode_track_cursor_page_rows", "track_page_result", "track_page_select"]
