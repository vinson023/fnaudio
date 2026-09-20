import sys
import unittest

sys.path.insert(0, "app/server")

from library_item_hydration import MAX_HYDRATION_ITEMS, hydrate_items_by_ids


class _FakeConnection:
    def __init__(self, rows_by_id):
        self.rows_by_id = rows_by_id
        self.calls = []

    def execute(self, statement, values):
        self.calls.append((statement, tuple(values)))
        return [self.rows_by_id[value] for value in values if value in self.rows_by_id]


class LibraryItemHydrationTests(unittest.TestCase):
    def test_batches_queries_and_restores_the_first_requested_order(self):
        conn = _FakeConnection({
            "one": {"id": "one"}, "two": {"id": "two"}, "three": {"id": "three"},
        })
        items = hydrate_items_by_ids(conn, ["three", "missing", "one", "two"], list, 2)
        self.assertEqual([item["id"] for item in items], ["three", "one", "two"])
        self.assertEqual([values for _statement, values in conn.calls], [("three", "missing"), ("one", "two")])
        self.assertTrue(all("WHERE id IN" in statement for statement, _values in conn.calls))

    def test_rejects_invalid_adapter_inputs_without_invoking_the_connection(self):
        conn = _FakeConnection({"one": {"id": "one"}})
        self.assertEqual(hydrate_items_by_ids(conn, "one", list, 2), [])
        self.assertEqual(hydrate_items_by_ids(conn, ["one"], list, True), [])
        self.assertEqual(conn.calls, [])

    def test_restore_hydration_has_a_total_item_budget(self):
        conn = _FakeConnection({"one": {"id": "one"}, "two": {"id": "two"}})
        items = hydrate_items_by_ids(conn, ["one", "two", "three"], list, 1, max_items=2)
        self.assertEqual([item["id"] for item in items], ["one", "two"])
        self.assertEqual([values for _statement, values in conn.calls], [("one",), ("two",)])
        self.assertEqual(hydrate_items_by_ids(conn, ["one"], list, 1, max_items=True), [{"id": "one"}])
        self.assertGreater(MAX_HYDRATION_ITEMS, 1000)

    def test_duplicate_queue_ids_are_fetched_once_but_output_order_is_preserved(self):
        conn = _FakeConnection({"one": {"id": "one"}, "two": {"id": "two"}})
        items = hydrate_items_by_ids(conn, ["one", "one", "two", "one"], list, 2)
        self.assertEqual([item["id"] for item in items], ["one", "one", "two", "one"])
        self.assertEqual([values for _statement, values in conn.calls], [("one", "two")])


if __name__ == "__main__":
    unittest.main()
