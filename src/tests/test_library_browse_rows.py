import unittest

import sys
sys.path.insert(0, "app/server")

from library_browse_rows import MAX_UNPAGED_BROWSE_ROWS, materialize_browse_rows


class LibraryBrowseRowsTests(unittest.TestCase):
    def test_materialization_has_a_fixed_legacy_response_bound(self):
        rows = ({"id": index} for index in range(MAX_UNPAGED_BROWSE_ROWS + 10))
        result = materialize_browse_rows(rows)
        self.assertEqual(len(result), MAX_UNPAGED_BROWSE_ROWS)
        self.assertEqual(result[0]["id"], 0)
        self.assertEqual(result[-1]["id"], MAX_UNPAGED_BROWSE_ROWS - 1)

    def test_materialization_keeps_rows_before_iterator_or_mapping_failure(self):
        class BrokenRows:
            def __iter__(self):
                yield {"id": "kept"}
                raise RuntimeError("cursor unavailable")

        class BrokenMapping:
            def keys(self):
                raise RuntimeError("mapping unavailable")

        self.assertEqual(materialize_browse_rows(BrokenRows()), [{"id": "kept"}])
        self.assertEqual(materialize_browse_rows([BrokenMapping()]), [])

    def test_materialization_rejects_untrusted_limits(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("row limit must not coerce custom objects")

        self.assertEqual(materialize_browse_rows([{"id": 1}], Explosive()), [{"id": 1}])
        self.assertEqual(materialize_browse_rows([{"id": 1}], 0), [])


if __name__ == "__main__":
    unittest.main()
