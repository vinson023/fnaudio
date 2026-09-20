"""Bounded keyset cursors for stable track-page continuation."""

from __future__ import annotations

import base64
import binascii
import json
import math

from library_query_spec import TRACK_SORT_COLUMNS


MAX_CURSOR_CHARS = 768
MAX_CURSOR_TEXT = 512
VALID_SORT_KEYS = {"title", "artist", "album", "format", "added", "track_no"}


def _optional_text(value, maximum=MAX_CURSOR_TEXT):
    """Return a bounded text that may be empty, or None when the value is unusable.

    Absent and empty are different facts on the wire: a track whose tag has no
    title stores "", while a payload that omits the key is malformed. This is
    also the check for the row id. ``tracks.id`` is a TEXT primary key, so "" is
    a value a row can actually hold - ``prepare_track_persistence`` falls back to
    it for an item that lost its id - and "" is the smallest possible id, so a
    cursor naming it still resolves its group exactly: the strict tail predicate
    skips that one row and keeps every row that follows it.
    """
    return value if isinstance(value, str) and len(value) <= maximum else None


def _primary(value):
    """Return the value a continuation can resume from, or None when it cannot.

    An empty string *is* a key. ``prepare_track_persistence`` indexes an untagged
    file with ``''`` for artist, album, and format, so in a real library the empty
    group is often one of the largest ones; refusing to encode it dropped
    ``next_cursor`` from every page that ended inside that group and pushed the
    client back onto OFFSET pagination. NULL stays unencodable because neither
    the range nor the equality predicate can express it.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if abs(value) <= 2 ** 63 - 1 else None
    if isinstance(value, str):
        return value if len(value) <= MAX_CURSOR_TEXT else None
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        number = int(value)
        return number if abs(number) <= 2 ** 63 - 1 else None
    return None


def anchor_is_encodable(primary, title, item_id):
    """Return whether one row can name a continuation at all.

    Page decoding has to ask this before it knows the sort key, so it is exactly
    the three shape tests the encoder performs, kept in one place on purpose:
    a page may not offer a row as anchor that the encoder would then refuse.
    """
    return (
        _primary(primary) is not None
        and _optional_text(title) is not None
        and _optional_text(item_id) is not None
    )


def encode_track_cursor(sort_key, sort_dir, primary, title, item_id, inclusive=False):
    """Return the token that continues after an anchor row.

    ``inclusive`` is False for the ordinary case: the anchor row was served, so
    the continuation must exclude it. A page whose last served row carries a key
    no predicate can express (SQL NULL) anchors on its look-ahead row instead,
    and that row has *not* been served, so the continuation includes it.
    """
    if sort_key not in VALID_SORT_KEYS or sort_dir not in {"asc", "desc"}:
        return ""
    primary = _primary(primary)
    title = _optional_text(title)
    item_id = _optional_text(item_id)
    if primary is None or title is None or item_id is None:
        return ""
    payload = {"v": 1, "sort": sort_key, "dir": sort_dir, "p": primary, "t": title, "id": item_id}
    if inclusive:
        # Sparse on purpose. Every token issued before this field existed is
        # exclusive, and an exclusive payload has to keep encoding byte-identical.
        payload["i"] = 1
    try:
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    except (TypeError, ValueError, UnicodeError):
        return ""
    return token if len(token) <= MAX_CURSOR_CHARS else ""


def decode_track_cursor(value):
    if not isinstance(value, str) or not value or len(value) > MAX_CURSOR_CHARS:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (ValueError, TypeError, UnicodeError, binascii.Error, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("v") != 1:
        return None
    sort_key = payload.get("sort")
    sort_dir = payload.get("dir")
    primary = _primary(payload.get("p"))
    title = _optional_text(payload.get("t"))
    item_id = _optional_text(payload.get("id"))
    inclusive = payload.get("i", 0)
    # A missing "p"/"t"/"id" key is malformed, while an empty one is a real key.
    if sort_key not in VALID_SORT_KEYS or sort_dir not in {"asc", "desc"} or primary is None or title is None or item_id is None:
        return None
    # The inclusive flag is opt-in and the payload is untrusted, so anything but
    # an absent key, 0/False or 1/True is refused rather than rounded.
    if not isinstance(inclusive, int) or inclusive not in (0, 1):
        return None
    return {
        "sort": sort_key,
        "dir": sort_dir,
        "primary": primary,
        "title": title,
        "id": item_id,
        "inclusive": bool(inclusive),
    }


def _position(page_query, cursor):
    """Return the ordering expression plus the value the cursor sits on.

    The title sort keys directly on the title, so it ignores the separately
    stored primary value: an inconsistent cursor must not be able to move the
    window away from the row the client actually saw.
    """
    expression = page_query.sql_order
    tie = TRACK_SORT_COLUMNS["title"]
    if expression == tie:
        return tie, True, cursor["title"]
    return expression, False, cursor["primary"]


def cursor_page(cursor, page_query):
    """Return the cursor when it addresses this exact page ordering, else None."""
    if cursor and cursor.get("sort") == page_query.sort_key and cursor.get("dir") == page_query.sort_dir:
        return cursor
    return None


def cursor_group_tail_where(page_query, cursor):
    """Return the rows that are still inside the cursor's own key group.

    Ordering inside one group is the tie-break, and ``sql_order_by`` keeps that
    ascending whichever way the primary key runs, so this predicate deliberately
    ignores ``sort_dir``. Matching the page order exactly is what keeps a page
    from repeating or skipping a track whose artist, album, or format is shared
    by thousands of files.

    The comparison is strict unless the anchor is inclusive: an inclusive cursor
    names a row the client has not seen yet, so the tail has to start at it.
    """
    if not cursor_page(cursor, page_query):
        return "", []
    expression, title_sort, value = _position(page_query, cursor)
    tie = TRACK_SORT_COLUMNS["title"]
    operator = ">=" if cursor.get("inclusive") else ">"
    if title_sort:
        return "%s = ? AND id %s ?" % (expression, operator), [value, cursor["id"]]
    return "%s = ? AND (%s, id) %s (?, ?)" % (expression, tie, operator), [value, cursor["title"], cursor["id"]]


def cursor_next_group_where(page_query, cursor):
    """Return the key groups that follow the cursor's own group.

    A *single* strict comparison on the ordering prefix, for the same reason the
    inclusive range it replaced was one: SQLite only turns a contiguous range
    into a seek, and it cannot prove that an OR over the same prefix is
    contiguous once every value arrives as its own anonymous parameter, which is
    how the page queries bind. On a 100000-track library a three-branch OR
    measured 2.8-6.5ms at a 50000-row depth against 0.07ms for this shape.

    Callers read the group tail first and only then this range, which is what
    removes the counted OFFSET from a continuation: the two statements together
    still visit no row that is not on the page.
    """
    if not cursor_page(cursor, page_query):
        return "", []
    expression, _title_sort, value = _position(page_query, cursor)
    operator = "<" if page_query.sort_dir == "desc" else ">"
    return "%s %s ?" % (expression, operator), [value]


__all__ = [
    "MAX_CURSOR_CHARS",
    "VALID_SORT_KEYS",
    "anchor_is_encodable",
    "cursor_group_tail_where",
    "cursor_next_group_where",
    "cursor_page",
    "decode_track_cursor",
    "encode_track_cursor",
]
