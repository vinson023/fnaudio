"""Bounded reuse of idle library SQLite connections.

Opening a WAL index costs about 1.1ms on a 100000-track library: SQLite has to
read the header, attach the ``-shm`` region, and rebuild the wal-index after the
previous connection closed. The first-screen page query itself measures 0.1ms,
so opening the database per request costs more than reading from it. This pool
keeps a small, explicitly bounded set of idle handles so a worker can borrow one
instead.

Two rules keep the reuse honest. A borrow never waits: when the pool has nothing
usable the caller opens its own connection, so the pool cannot become a queue in
front of the request admission limit. And every handle carries the identity of
the file it was opened against, so a replaced or deleted index can never be read
through a stale descriptor.

The ceiling is deliberately small. An index costs three files while it is open
(main, ``-wal``, ``-shm``), so eight idle handles hold at most twenty-four extra
descriptors on top of the handles borrowed by in-flight requests, and a WAL
checkpoint is not delayed by an idle handle because its read transaction was
already committed when it came back.
"""

from __future__ import annotations

import threading


DEFAULT_MAX_IDLE_PER_DATABASE = 4
DEFAULT_MAX_IDLE_TOTAL = 8


def _close_quietly(connections):
    """Best-effort close. Housekeeping must not fail an answered request."""
    closed = 0
    for connection in connections:
        try:
            connection.close()
        except Exception:
            pass
        else:
            closed += 1
    return closed


class LibraryConnectionPool:
    """Thread-safe, bounded, LIFO holder of idle connections."""

    __slots__ = (
        "_lock", "_idle", "_limit_per_database", "_limit_total",
        "_reuses", "_creations", "_closures", "_accepting",
    )

    def __init__(self, max_idle_per_database=DEFAULT_MAX_IDLE_PER_DATABASE,
                 max_idle_total=DEFAULT_MAX_IDLE_TOTAL):
        self._lock = threading.Lock()
        self._idle = {}
        self._limit_per_database = max(1, int(max_idle_per_database))
        self._limit_total = max(self._limit_per_database, int(max_idle_total))
        self._reuses = 0
        self._creations = 0
        self._closures = 0
        # Cleared once, by `stop_accepting()`, during runtime shutdown. A pool that
        # stopped accepting still answers readers - it just closes their handles on the
        # way out instead of keeping the index file open for a process that is winding
        # down. `drop()` deliberately does not touch this flag: it is also used between
        # scans, where pooling has to keep working.
        self._accepting = True

    def borrow(self, database, identity):
        """Return an idle handle for ``database``, or ``None`` to open a new one.

        ``identity`` fingerprints the file the caller intends to read. Handles
        stored against any other identity are dropped immediately: they point at
        a database that is no longer there.
        """
        stale = []
        connection = None
        with self._lock:
            # No acceptance check here: `stop_accepting()` emptied the pool and `release()`
            # below is the only door back in, so a closed pool has nothing left to lend.
            entries = self._idle.get(database)
            if entries:
                reusable = []
                for stored_identity, stored in entries:
                    if identity is not None and stored_identity == identity:
                        reusable.append((stored_identity, stored))
                    else:
                        stale.append(stored)
                if reusable:
                    # Newest first, so a handle that just ran a query keeps its
                    # warm page cache instead of rotating to the coldest one.
                    _, connection = reusable.pop()
                    self._reuses += 1
                if reusable:
                    self._idle[database] = reusable
                else:
                    self._idle.pop(database, None)
            if stale:
                self._closures += len(stale)
        if stale:
            _close_quietly(stale)
        return connection

    def release(self, database, identity, connection):
        """Offer a finished handle back. Returns False when the caller must close it."""
        with self._lock:
            if not self._accepting:
                # The single enforcement point for a handle released after the shutdown
                # drain: returning False is the caller's instruction to close it, which is
                # what `library_db_connect`'s epilogue does.
                self._closures += 1
                return False
            entries = self._idle.get(database)
            if (identity is not None
                    and len(entries or ()) < self._limit_per_database
                    and self._total_idle() < self._limit_total):
                if entries is None:
                    entries = self._idle[database] = []
                entries.append((identity, connection))
                return True
            # A handle with no verifiable identity points at a file this process
            # cannot prove is still there, so it must not be stored or reused.
            if entries is not None and not entries:
                self._idle.pop(database, None)
            self._closures += 1
        return False

    def note_created(self):
        """Count a handle the pool could not serve, so status shows the hit rate."""
        with self._lock:
            self._creations += 1

    def stop_accepting(self, database=None):
        """Close idle handles and refuse to pool anything further.

        This is the shutdown drain. `drop()` above only forgets what is idle *now*, so a
        reader still inside a query when the runtime winds down can hand its handle back
        afterwards and leave `library.sqlite3` open again - which is the exact state the
        drain exists to prevent. Closing acceptance is one-way on purpose: it is called
        when no start path remains.
        """
        with self._lock:
            self._accepting = False
            if database is None:
                doomed = [item for entries in self._idle.values() for _, item in entries]
                self._idle.clear()
            else:
                entries = self._idle.pop(database, [])
                doomed = [item for _, item in entries]
            self._closures += len(doomed)
        return _close_quietly(doomed)

    def drop(self, database=None):
        """Forget (and close) idle handles; pooling stays available afterwards."""
        with self._lock:
            if database is None:
                doomed = [item for entries in self._idle.values() for _, item in entries]
                self._idle.clear()
            else:
                entries = self._idle.pop(database, [])
                doomed = [item for _, item in entries]
            self._closures += len(doomed)
        return _close_quietly(doomed)

    def snapshot(self):
        with self._lock:
            return {
                "idle": self._total_idle(),
                "databases": len(self._idle),
                "reuses": self._reuses,
                "creations": self._creations,
                "closures": self._closures,
                "max_idle_per_database": self._limit_per_database,
                "max_idle_total": self._limit_total,
            }

    def _total_idle(self):
        return sum(len(entries) for entries in self._idle.values())


__all__ = [
    "DEFAULT_MAX_IDLE_PER_DATABASE",
    "DEFAULT_MAX_IDLE_TOTAL",
    "LibraryConnectionPool",
]
