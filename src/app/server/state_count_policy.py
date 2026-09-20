"""Pure policy for persisted per-playlist row counts in the state database.

``playlists.track_count`` holds how many ``playlist_tracks`` rows a playlist
owns.  Every writer that changes those rows sets the number in the same
statement batch, so a save no longer has to re-derive it by scanning the child
table.  This module decides when such a number may be believed; the SQL stays
in ``state_store``.
"""

from __future__ import annotations

MAX_PERSISTED_COUNT = 2_147_483_647

# The state_meta marker saying that playlist_tracks was last found to hold no
# row without a parent.  Only the cleanup that proves it may write it.
CHILD_INTEGRITY_VERIFIED = "1"


def normalize_count(value):
    """Return a trustworthy row count, or None when the stored value is not one.

    SQLite hands back whatever was written, so a damaged row can carry text, a
    float, a bool or a negative number.  Booleans are rejected because they
    subclass int and would otherwise read a stored ``True`` as a single row.
    A missing column -- every playlist row in a database created before this
    count existed -- reads back as None and means "unknown", never "empty".
    """
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    if count < 0 or count > MAX_PERSISTED_COUNT:
        return None
    return count


def child_integrity_is_recorded(row):
    """Read the child-row marker without trusting the row that carries it."""
    if not row:
        return False
    try:
        value = row["value"]
    except Exception:
        return False
    return value == CHILD_INTEGRITY_VERIFIED


def children_are_within_budget(counts, per_playlist_cap, total_cap):
    """Decide whether a playlist trim could possibly delete a single row.

    ``counts`` are the persisted row counts of the playlists being kept, in
    retention order.  The answer is ``True`` only when every one of them is a
    usable number and their running total stays inside both caps, because that
    running total *is* the trimming budget: a playlist is shortened exactly when
    its own count exceeds ``min(per_playlist_cap, remaining)``.

    Skipping the child table is the whole point of the question, so the
    predicate must never answer ``True`` about a number it cannot vouch for --
    one unknown count sends the caller back to SQLite for an authoritative
    re-count.  Answering ``True`` for a count that was recorded too high is
    still safe: the rows the caller believes in are then a superset of the rows
    on disk, and a superset that fits both caps cannot need trimming.
    """
    for cap in (per_playlist_cap, total_cap):
        if isinstance(cap, bool) or not isinstance(cap, int) or cap < 0:
            return False
    total = 0
    for value in counts:
        count = normalize_count(value)
        if count is None or count > per_playlist_cap:
            return False
        total += count
        if total > total_cap:
            return False
    return True


__all__ = [
    "CHILD_INTEGRITY_VERIFIED",
    "MAX_PERSISTED_COUNT",
    "child_integrity_is_recorded",
    "children_are_within_budget",
    "normalize_count",
]
