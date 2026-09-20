"""Pure policy for choosing persisted versus live library counts."""

from __future__ import annotations

MAX_SAVED_COUNT = 2_147_483_647


def saved_count_key(view, search, where_sql):
    """Return the library_meta key safe for an unfiltered hot-path query."""
    if not isinstance(view, str):
        return None
    view = view.strip().lower()
    if not isinstance(search, str) or not isinstance(where_sql, str):
        return None
    if view == "dsd":
        return "dsd_count" if not search else None
    has_filter = bool(search.strip()) or bool(where_sql.strip())
    if has_filter:
        return None
    if view in ("all", "recent", "random100"):
        return "track_count"
    return None


def project_saved_count(row):
    """Read a persisted count row without trusting SQLite or mapping values."""
    if not row:
        return None
    try:
        raw = row["value"]
        if isinstance(raw, bool) or not isinstance(raw, (str, int)):
            return None
        value = int(raw)
        return value if 0 <= value <= MAX_SAVED_COUNT else None
    except Exception:
        return None


GROUP_COUNT_KEYS = (
    ("albums", "group_count_albums"),
    ("artists", "group_count_artists"),
    ("composers", "group_count_composers"),
    ("genres", "group_count_genres"),
)


def group_count_key(table, search):
    """Return the library_meta key holding a group table's row count.

    Only a browse page that reads a whole group table may use a persisted total,
    so a search -- or any other narrowing -- has to keep counting live.  The
    caller normalises its own search text, but this policy is what stops a
    future caller from relying on that, so any text at all is refused here
    rather than stripped and trusted.
    """
    if not isinstance(table, str) or not isinstance(search, str):
        return None
    if search:
        return None
    for name, key in GROUP_COUNT_KEYS:
        if table == name:
            return key
    return None


def browse_page_total(saved, offset, row_count, limit):
    """Decide a browse total from the persisted count plus the look-ahead row.

    The page reads ``limit + 1`` rows, so a short page proves the walk reached
    the end of the table: the rows seen *are* the exact total, which repairs a
    count that drifted high. A full look-ahead row only proves the table is
    bigger than the page, so it can refute a persisted count that sits *below*
    the rows already read -- the dangerous direction, because a small count
    makes ``has_more`` claim the list ended and truncates it -- and that answer
    has to come from the authoritative count. Returns ``(count, refuted)``; a
    refuted count means the caller must read the real one.
    """
    for value in (saved, offset, row_count, limit):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None, True
    if saved > MAX_SAVED_COUNT or row_count == 0 or row_count > limit + 1:
        return None, True
    if row_count <= limit:
        return offset + row_count, False
    if saved < offset + row_count:
        return None, True
    return saved, False
