import sys
import unittest

sys.path.insert(0, "app/server")

from library_item_lookup import lookup_memory_item, lookup_sqlite_item


class _Connection:
    def __init__(self, row=None, error=None):
        self.row = row
        self.error = error

    def execute(self, *_args):
        if self.error:
            raise self.error
        return self

    def fetchone(self):
        return self.row


class LibraryItemLookupTests(unittest.TestCase):
    def test_sqlite_lookup_uses_normalized_id_and_decoder(self):
        row = {"item_json": "payload"}
        self.assertEqual(
            lookup_sqlite_item(_Connection(row), "track-1", lambda value: {"id": "track-1"}),
            {"id": "track-1"},
        )

    def test_sqlite_lookup_isolates_connection_and_decoder_failures(self):
        self.assertIsNone(lookup_sqlite_item(_Connection(error=RuntimeError()), "x", dict))
        self.assertIsNone(lookup_sqlite_item(_Connection({}), "x", lambda _row: (_ for _ in ()).throw(ValueError())))

    def test_memory_lookup_preserves_mapping_identity_and_handles_broken_iterators(self):
        item = {"id": "x", "title": "Title"}
        self.assertIs(lookup_memory_item([None, item], "x"), item)

        class Broken:
            def __iter__(self):
                yield {"id": "before"}
                raise RuntimeError("broken")

        self.assertIsNone(lookup_memory_item(Broken(), "missing"))

    def test_memory_lookup_skips_mapping_with_broken_getter(self):
        class BrokenMapping(dict):
            def get(self, _key, _default=None):
                raise RuntimeError("broken getter")

        item = {"id": "valid"}
        self.assertIs(lookup_memory_item([BrokenMapping(), item], "valid"), item)


if __name__ == "__main__":
    unittest.main()
