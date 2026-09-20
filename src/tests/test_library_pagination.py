import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "server"))

from library_pagination import MAX_PAGE_ROWS, counted_page_rows, paged_rows_with_total


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Connection:
    def __init__(self, responses, fail_window=False):
        self.responses = responses
        self.fail_window = fail_window
        self.statements = []

    def execute(self, statement, args=()):
        self.statements.append((statement, tuple(args)))
        if self.fail_window and statement == "window":
            import sqlite3
            raise sqlite3.OperationalError("window functions unavailable")
        return _Cursor(self.responses.get(statement, []))


class LibraryPaginationTests(unittest.TestCase):
    def test_window_and_fallback_rows_are_bounded(self):
        class Cursor:
            def __iter__(self):
                return self
            def __next__(self):
                return {"item_json": "{}", "total_count": 1}

        class Conn:
            def execute(self, sql, args):
                return Cursor()

        rows, total = paged_rows_with_total(Conn(), "window", [], "count", [], "page", [])
        self.assertEqual(len(rows), MAX_PAGE_ROWS)
        self.assertEqual(total, 1)

    def test_window_row_carries_total_without_count_fallback(self):
        conn = _Connection({"window": [{"id": "two", "total_count": 3}]})
        rows, count = paged_rows_with_total(conn, "window", [1], "count", [], "page", [1])
        self.assertEqual(rows[0]["id"], "two")
        self.assertEqual(count, 3)
        self.assertEqual([statement for statement, _ in conn.statements], ["window"])

    def test_empty_window_page_and_old_sqlite_use_precise_fallback(self):
        empty = _Connection({"window": [], "count": [(4,)]})
        rows, count = paged_rows_with_total(empty, "window", [], "count", [], "page", [])
        self.assertEqual(rows, [])
        self.assertEqual(count, 4)
        self.assertEqual([statement for statement, _ in empty.statements], ["window", "count"])

        legacy = _Connection({"count": [(2,)], "page": [{"id": "one"}]}, fail_window=True)
        rows, count = paged_rows_with_total(legacy, "window", [], "count", [], "page", [])
        self.assertEqual(rows, [{"id": "one"}])
        self.assertEqual(count, 2)
        self.assertEqual([statement for statement, _ in legacy.statements], ["window", "count", "page"])

    def test_malformed_window_total_uses_bounded_count_fallback(self):
        malformed = _Connection({"window": [{"id": "one", "total_count": True}], "count": [(5,)]})
        rows, count = paged_rows_with_total(malformed, "window", [], "count", [], "page", [])
        self.assertEqual(rows[0]["id"], "one")
        self.assertEqual(count, 5)
        self.assertEqual([statement for statement, _ in malformed.statements], ["window", "count"])

    def test_legacy_sqlite_malformed_count_falls_back_to_zero(self):
        legacy = _Connection({"count": [(True,)], "page": [{"id": "one"}]}, fail_window=True)
        rows, count = paged_rows_with_total(legacy, "window", [], "count", [], "page", [])
        self.assertEqual(rows, [{"id": "one"}])
        self.assertEqual(count, 0)

    def test_non_iterable_window_cursor_uses_count_and_page_fallback(self):
        class BrokenConnection(_Connection):
            def execute(self, statement, args=()):
                self.statements.append((statement, tuple(args)))
                if statement == "window":
                    return object()
                return _Cursor(self.responses.get(statement, []))

        conn = BrokenConnection({"count": [(2,)], "page": [{"id": "one"}]})
        rows, count = paged_rows_with_total(conn, "window", [], "count", [], "page", [])
        self.assertEqual(rows, [{"id": "one"}])
        self.assertEqual(count, 2)

    def test_runtime_error_during_window_iteration_uses_fallback(self):
        class BrokenCursor:
            def __iter__(self):
                raise RuntimeError("cursor failed")

        class BrokenConnection(_Connection):
            def execute(self, statement, args=()):
                self.statements.append((statement, tuple(args)))
                if statement == "window":
                    return BrokenCursor()
                return _Cursor(self.responses.get(statement, []))

        conn = BrokenConnection({"count": [(3,)], "page": [{"id": "one"}]})
        rows, count = paged_rows_with_total(conn, "window", [], "count", [], "page", [])
        self.assertEqual(rows, [{"id": "one"}])
        self.assertEqual(count, 3)

    def test_page_sqlite_error_returns_empty_page_with_count(self):
        class BrokenPageConnection(_Connection):
            def execute(self, statement, args=()):
                self.statements.append((statement, tuple(args)))
                if statement == "window":
                    raise __import__("sqlite3").OperationalError("no window")
                if statement == "page":
                    raise __import__("sqlite3").OperationalError("page failed")
                return _Cursor(self.responses.get(statement, []))

        conn = BrokenPageConnection({"count": [(4,)]})
        rows, count = paged_rows_with_total(conn, "window", [], "count", [], "page", [])
        self.assertEqual(rows, [])
        self.assertEqual(count, 4)

    def test_counted_page_rows_reads_the_page_then_the_total(self):
        conn = _Connection({"page": [{"id": "one"}], "count": [(7,)]})
        rows, count = counted_page_rows(conn, "page", [1], "count", [])
        self.assertEqual(rows, [{"id": "one"}])
        self.assertEqual(count, 7)
        self.assertEqual([statement for statement, _ in conn.statements], ["page", "count"])

    def test_counted_page_rows_isolates_a_failed_page_and_a_failed_total(self):
        class BrokenConnection(_Connection):
            def __init__(self, responses, fail):
                _Connection.__init__(self, responses)
                self.fail = fail

            def execute(self, statement, args=()):
                self.statements.append((statement, tuple(args)))
                if statement == self.fail:
                    raise __import__("sqlite3").OperationalError("statement failed")
                return _Cursor(self.responses.get(statement, []))

        broken_page = BrokenConnection({"count": [(3,)]}, "page")
        rows, count = counted_page_rows(broken_page, "page", [], "count", [])
        self.assertEqual(rows, [])
        self.assertEqual(count, 3)
        broken_count = BrokenConnection({"page": [{"id": "one"}]}, "count")
        rows, count = counted_page_rows(broken_count, "page", [], "count", [])
        self.assertEqual(rows, [{"id": "one"}])
        self.assertEqual(count, 0)

    def test_counted_page_rows_only_isolates_database_failures(self):
        # Swallowing every Exception would hide a programming error behind an
        # empty page, so the guard has to stay as narrow as the window path.
        class BrokenConnection(_Connection):
            def execute(self, statement, args=()):
                self.statements.append((statement, tuple(args)))
                if statement == "page":
                    raise ZeroDivisionError("bug in the caller")
                return _Cursor(self.responses.get(statement, []))

        with self.assertRaises(ZeroDivisionError):
            counted_page_rows(BrokenConnection({"count": [(1,)]}), "page", [], "count", [])

    def test_counted_page_rows_still_bounds_a_runaway_page_cursor(self):
        class Cursor:
            def __init__(self):
                self.emitted = 0

            def __iter__(self):
                return self

            def __next__(self):
                # Three times the ceiling: enough to fail an unbounded read
                # without hanging the suite when the guard disappears.
                if self.emitted >= MAX_PAGE_ROWS * 3:
                    raise StopIteration
                self.emitted += 1
                return {"id": "one"}

        class UnboundedConnection:
            def execute(self, statement, args=()):
                return Cursor()

        rows, count = counted_page_rows(UnboundedConnection(), "page", [], "count", [])
        self.assertEqual(len(rows), MAX_PAGE_ROWS)
        self.assertEqual(count, 0)

    def test_runtime_error_reading_count_returns_zero(self):
        class BrokenCountCursor:
            def fetchone(self):
                raise RuntimeError("count failed")

            def __iter__(self):
                return iter(())

        class BrokenCountConnection(_Connection):
            def execute(self, statement, args=()):
                self.statements.append((statement, tuple(args)))
                if statement == "window":
                    raise __import__("sqlite3").OperationalError("no window")
                if statement == "count":
                    return BrokenCountCursor()
                return _Cursor(self.responses.get(statement, []))

        conn = BrokenCountConnection({"page": []})
        rows, count = paged_rows_with_total(conn, "window", [], "count", [], "page", [])
        self.assertEqual(rows, [])
        self.assertEqual(count, 0)

    def test_missing_cursor_methods_are_isolated(self):
        class MissingCursorConnection(_Connection):
            def execute(self, statement, args=()):
                self.statements.append((statement, tuple(args)))
                if statement == "window":
                    return object()
                if statement == "count":
                    return object()
                return object()

        conn = MissingCursorConnection({})
        rows, count = paged_rows_with_total(conn, "window", [], "count", [], "page", [])
        self.assertEqual(rows, [])
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
