"""Park a library snapshot that lost the write race, and replay it later.

A full walk of a real collection takes minutes.  Until now the scan thread also
made durability a hard precondition of availability: one
``sqlite3.OperationalError: database is locked`` from a concurrent metadata
writer threw the finished scan away, ``MUSIC_CACHE`` stayed empty, and the very
next watcher tick started the same multi-minute walk again.  On a device with
62,684 tracks that loop is what produced a permanent ``scanning=true``, an
empty library, and every click waiting behind a rescan.

This module holds the retry bookkeeping only.  It never opens SQLite, so
"is this worth waiting for, and when" stays testable without a database.
"""

from __future__ import annotations

# The driver only ever says one of these two things when another writer owns the
# database.  A permission error, a full disk or a corrupt file says something
# else, and none of those get better by waiting.
TRANSIENT_LOCK_MARKERS = ("database is locked", "database table is locked", "busy")

DEFAULT_RETRY_LIMIT = 4
DEFAULT_RETRY_BASE_SECONDS = 60.0
DEFAULT_RETRY_MAX_SECONDS = 300.0


def is_transient_lock(detail):
    """Return True when waiting for the other writer can plausibly help."""
    if detail is None:
        return False
    text = str(detail).lower()
    return any(marker in text for marker in TRANSIENT_LOCK_MARKERS)


class PersistRetrySlot:
    """One parked snapshot with a bounded, tick-aligned retry budget.

    ``stage`` is idempotent for the same signature so a replay that fails again
    cannot hand itself a fresh budget forever; ``note_failure`` is the only
    place the budget shrinks.
    """

    def __init__(self, limit=DEFAULT_RETRY_LIMIT, base_delay=DEFAULT_RETRY_BASE_SECONDS,
                 max_delay=DEFAULT_RETRY_MAX_SECONDS):
        self.limit = int(limit)
        self.base_delay = float(base_delay)
        self.max_delay = float(max_delay)
        self.items = None
        self.signature = ""
        self.attempts = 0
        self.due_at = 0.0
        self.staged_at = 0.0
        self.gave_up = False

    def pending(self):
        return isinstance(self.items, list) and bool(self.items)

    def stage(self, items, signature, now):
        """Park a snapshot.  Empty snapshots and unknown signatures are refused.

        The scan path passes the filesystem signature it just computed, so an
        empty one means a partial publish, and replaying partial rows later
        would regress an index a newer scan already wrote.  An empty item list
        has the same problem in the other direction.
        """
        text = str(signature or "")
        if not text or not isinstance(items, list) or not items:
            return False
        same = self.pending() and self.signature == text
        self.items = items
        self.signature = text
        if not same:
            self.attempts = 0
            self.gave_up = False
            self.staged_at = float(now)
            self.due_at = float(now) + self.base_delay
        return True

    def due(self, now):
        return self.pending() and float(now) >= self.due_at

    def snapshot(self):
        return (self.items, self.signature) if self.pending() else None

    def _delay(self):
        return min(self.max_delay, self.base_delay * (2 ** self.attempts))

    def note_success(self, now):
        self.clear()

    def note_failure(self, now):
        if not self.pending():
            return False
        self.attempts += 1
        if self.attempts >= self.limit:
            self.clear(gave_up=True)
            return False
        self.due_at = float(now) + self._delay()
        return True

    def clear(self, gave_up=False):
        self.items = None
        self.signature = ""
        self.attempts = 0
        self.due_at = 0.0
        self.staged_at = 0.0
        self.gave_up = bool(gave_up)

    def status(self, now):
        return {
            "pending": self.pending(),
            "attempts": int(self.attempts),
            "limit": int(self.limit),
            "next_in": max(0, int(round(self.due_at - float(now)))) if self.pending() else 0,
            "gave_up": bool(self.gave_up),
        }


__all__ = [
    "DEFAULT_RETRY_BASE_SECONDS",
    "DEFAULT_RETRY_LIMIT",
    "DEFAULT_RETRY_MAX_SECONDS",
    "PersistRetrySlot",
    "TRANSIENT_LOCK_MARKERS",
    "is_transient_lock",
]
