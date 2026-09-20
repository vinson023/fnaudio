import sys
import threading
import time
import unittest

sys.path.insert(0, "app/server")

from library_connection_pool import (
    DEFAULT_MAX_IDLE_PER_DATABASE,
    DEFAULT_MAX_IDLE_TOTAL,
    LibraryConnectionPool,
)


class FakeConnection:
    """Stand-in that records closure and refuses to be handed to two readers."""

    def __init__(self, name):
        self.name = name
        self.closed = False
        self._guard = threading.Lock()
        self._in_use = False

    def close(self):
        self.closed = True

    def claim(self):
        with self._guard:
            if self._in_use:
                return False
            self._in_use = True
            return True

    def discharge(self):
        with self._guard:
            self._in_use = False


class ExplodingConnection(FakeConnection):
    def close(self):
        raise OSError("handle already detached")


class LibraryConnectionPoolTests(unittest.TestCase):
    def test_borrow_uses_last_in_first_out(self):
        pool = LibraryConnectionPool()
        first, second = FakeConnection("first"), FakeConnection("second")
        self.assertTrue(pool.release("db", "identity", first))
        self.assertTrue(pool.release("db", "identity", second))
        self.assertIs(pool.borrow("db", "identity"), second)
        self.assertIs(pool.borrow("db", "identity"), first)
        self.assertIsNone(pool.borrow("db", "identity"))
        snapshot = pool.snapshot()
        self.assertEqual(snapshot["reuses"], 2)
        self.assertEqual(snapshot["idle"], 0)
        self.assertEqual(snapshot["databases"], 0)

    def test_a_replaced_database_purges_stale_handles_with_the_reuse(self):
        pool = LibraryConnectionPool()
        stale, current = FakeConnection("stale"), FakeConnection("current")
        pool.release("db", (1, 1), stale)
        pool.release("db", (2, 2), current)
        self.assertIs(pool.borrow("db", (2, 2)), current)
        self.assertTrue(stale.closed)
        self.assertFalse(current.closed)
        self.assertEqual(pool.snapshot()["closures"], 1)

    def test_missing_identity_closes_every_stored_handle(self):
        pool = LibraryConnectionPool()
        handles = [FakeConnection("h%d" % index) for index in range(3)]
        for handle in handles:
            self.assertTrue(pool.release("db", (9, 9), handle))
        # The index file cannot be identified (a user cleared it while the
        # service was running), so no idle handle may be trusted.
        self.assertIsNone(pool.borrow("db", None))
        self.assertTrue(all(handle.closed for handle in handles))
        snapshot = pool.snapshot()
        self.assertEqual(snapshot["idle"], 0)
        self.assertEqual(snapshot["databases"], 0)
        self.assertEqual(snapshot["closures"], 3)

    def test_a_borrow_purges_stale_handles_and_spares_another_database(self):
        pool = LibraryConnectionPool()
        library, other = FakeConnection("library"), FakeConnection("other")
        pool.release("db-a", (1, 1), library)
        pool.release("db-b", (1, 1), other)
        self.assertIsNone(pool.borrow("db-a", (2, 2)))
        self.assertTrue(library.closed)
        self.assertFalse(other.closed)
        self.assertIs(pool.borrow("db-b", (1, 1)), other)

    def test_per_database_idle_bound(self):
        pool = LibraryConnectionPool(max_idle_per_database=2, max_idle_total=8)
        handles = [FakeConnection("h%d" % index) for index in range(6)]
        accepted = []
        for handle in handles:
            # The documented contract: a rejected handle stays the caller's to
            # close, which is how an over-limit borrow ends up closed at once.
            if not pool.release("db", (1, 1), handle):
                handle.close()
            accepted.append(handle.closed)
        self.assertEqual(accepted, [False, False, True, True, True, True])
        self.assertEqual(pool.snapshot()["idle"], 2)
        self.assertEqual(pool.borrow("db", (1, 1)), handles[1])
        self.assertEqual(pool.borrow("db", (1, 1)), handles[0])

    def test_total_idle_bound_spans_databases(self):
        pool = LibraryConnectionPool(max_idle_per_database=1, max_idle_total=3)
        accepted = [
            pool.release("db%d" % index, (1, 1), FakeConnection("db%d" % index))
            for index in range(8)
        ]
        self.assertEqual(accepted, [True, True, True] + [False] * 5)
        snapshot = pool.snapshot()
        self.assertEqual(snapshot["idle"], 3)
        self.assertEqual(snapshot["databases"], 3)

    def test_limits_keep_the_total_at_least_as_high_as_one_database(self):
        snapshot = LibraryConnectionPool(max_idle_per_database=8, max_idle_total=1).snapshot()
        self.assertEqual(snapshot["max_idle_per_database"], 8)
        self.assertEqual(snapshot["max_idle_total"], 8)

    def test_shipped_defaults_stay_inside_the_worker_ceiling(self):
        self.assertLessEqual(DEFAULT_MAX_IDLE_PER_DATABASE, 4)
        self.assertLessEqual(DEFAULT_MAX_IDLE_TOTAL, 8)

    def test_a_handle_is_never_handed_to_two_readers(self):
        pool = LibraryConnectionPool()
        handles = [FakeConnection("h%d" % index) for index in range(4)]
        for handle in handles:
            pool.release("db", (1, 1), handle)
        violations = []
        started = threading.Barrier(6)

        def worker():
            started.wait()
            for _ in range(50):
                connection = pool.borrow("db", (1, 1))
                if connection is None:
                    continue
                if not connection.claim():
                    violations.append(connection.name)
                connection.discharge()
                pool.release("db", (1, 1), connection)

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(violations, [])
        self.assertEqual(pool.snapshot()["idle"], 4)

    def test_borrow_never_blocks_and_counts_what_it_could_not_serve(self):
        pool = LibraryConnectionPool()
        created = []
        lock = threading.Lock()
        started = threading.Barrier(6)
        shared = []

        def worker():
            started.wait()
            for _ in range(20):
                connection = pool.borrow("db", (1, 1))
                if connection is None:
                    connection = FakeConnection("created")
                    with lock:
                        created.append(connection)
                    pool.note_created()
                elif not connection.claim():
                    with lock:
                        shared.append(connection.name)
                else:
                    connection.discharge()
                time.sleep(0)
                pool.release("db", (1, 1), connection)

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(any(thread.is_alive() for thread in threads), "a borrow waited for a slot")
        self.assertEqual(shared, [])
        snapshot = pool.snapshot()
        self.assertLessEqual(snapshot["idle"], DEFAULT_MAX_IDLE_TOTAL)
        self.assertEqual(snapshot["creations"], len(created))
        self.assertEqual(snapshot["reuses"] + snapshot["creations"], 120)

    def test_close_failure_does_not_strand_the_pool(self):
        pool = LibraryConnectionPool()
        pool.release("db", (1, 1), ExplodingConnection("broken"))
        # The replaced index forces the pool to close the broken handle, which
        # raises. That must not swallow the usable handle or wedge the database.
        replacement = FakeConnection("next")
        pool.release("db", (2, 2), replacement)
        self.assertIs(pool.borrow("db", (2, 2)), replacement)
        snapshot = pool.snapshot()
        self.assertEqual(snapshot["idle"], 0)
        self.assertEqual(snapshot["closures"], 1)
        self.assertTrue(pool.release("db", (2, 2), replacement))

    def test_drop_targets_one_database_or_all_of_them(self):
        pool = LibraryConnectionPool()
        handles = {}
        for database in ("db-a", "db-b"):
            handle = FakeConnection(database)
            handles[database] = handle
            pool.release(database, (1, 1), handle)
        self.assertEqual(pool.drop("db-a"), 1)
        self.assertTrue(handles["db-a"].closed)
        self.assertFalse(handles["db-b"].closed)
        self.assertEqual(pool.snapshot()["databases"], 1)
        self.assertEqual(pool.drop(), 1)
        self.assertTrue(handles["db-b"].closed)
        self.assertEqual(pool.snapshot()["idle"], 0)

    def test_a_handle_returned_after_the_shutdown_drain_is_closed_not_pooled(self):
        # The shutdown drain has to survive a reader that is still in flight: an HTTP
        # handler finishes its query after `close_library_connections()` ran, offers the
        # handle back, and must not be able to leave `library.sqlite3` open again. Three
        # separate promises, so a mutant that keeps any one of them fails on its own.
        pool = LibraryConnectionPool()
        idle_before = FakeConnection("idle-before-shutdown")
        pool.release("db", (1, 1), idle_before)
        self.assertEqual(pool.stop_accepting(), 1)
        idle_closed = pool.snapshot()["closures"]
        self.assertTrue(idle_before.closed, "the drain did not close what it already held")
        # A late reader gets no handle: the drain closed everything idle, and `release()`
        # below is the only door back in.
        self.assertIsNone(pool.borrow("db", (1, 1)))
        # ...and the handle it opened for itself is refused on the way out. `release()`
        # returning False is the caller's contract to close it, which is what
        # `library_db_connect`'s epilogue does; the pool never closes a handle the caller
        # may still be holding.
        late = FakeConnection("late-handler")
        self.assertFalse(pool.release("db", (1, 1), late))
        self.assertEqual(pool.snapshot()["idle"], 0)
        # The refusal is a closure as far as diagnostics go: a handle that leaves the
        # runtime and is never seen again must show up in the counter that explains the
        # hit rate, or the numbers on the health page stop adding up.
        self.assertEqual(pool.snapshot()["closures"], idle_closed + 1)
        late.close()
        self.assertTrue(late.closed)

    def test_the_ordinary_drain_keeps_pooling_available(self):
        # The distinction the shutdown drain adds has to be one-directional: `drop()` runs
        # between scans, where readers keep coming, so it must not stop acceptance.
        pool = LibraryConnectionPool()
        handle = FakeConnection("first")
        pool.release("db", (1, 1), handle)
        self.assertEqual(pool.drop(), 1)
        replacement = FakeConnection("second")
        self.assertTrue(pool.release("db", (1, 1), replacement))
        self.assertIs(pool.borrow("db", (1, 1)), replacement)

    def test_stop_accepting_reports_only_the_handles_it_closed(self):
        pool = LibraryConnectionPool()
        for index in range(3):
            pool.release("db-%d" % index, (index, index), FakeConnection("h%d" % index))
        self.assertEqual(pool.stop_accepting("db-1"), 1)
        self.assertEqual(pool.snapshot()["databases"], 2)
        self.assertEqual(pool.stop_accepting(), 2)
        self.assertEqual(pool.stop_accepting(), 0, "a second drain double-counted closures")


    def test_an_unidentifiable_database_never_stores_an_idle_handle(self):
        pool = LibraryConnectionPool()
        handle = FakeConnection("handle")
        self.assertFalse(pool.release("db", None, handle))
        self.assertEqual(handle.closed, False)
        snapshot = pool.snapshot()
        self.assertEqual(snapshot["idle"], 0)
        # A rejection must not leave an empty bucket behind, or a long-lived
        # process would accumulate one entry per unreachable cache directory.
        self.assertEqual(snapshot["databases"], 0)


if __name__ == "__main__":
    unittest.main()
