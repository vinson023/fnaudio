import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

import library


class LibraryQueryAdapterTests(unittest.TestCase):
    def test_cache_epoch_does_not_stringify_namespace_or_materialize_values(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("adapter must not stringify namespace")

        class BoundedIterable:
            def __iter__(self):
                yield "first"
                raise AssertionError("adapter must not consume iterable")

        config = {"cache_dir": os.path.join("/tmp", "fnaudio-cache")}
        seen = []

        def record(database, namespace, values, identity):
            seen.append((database, namespace, values, identity))
            return None

        with mock.patch.object(library, "LIBRARY_QUERY_CACHE") as cache:
            cache.get.side_effect = record
            epoch = library.LibraryCacheEpoch(config)
            epoch.get(Explosive(), BoundedIterable())

        database, namespace, values, identity = seen[0]
        expected = os.path.abspath(os.path.join("/tmp", "fnaudio-cache", "library.sqlite3"))
        self.assertEqual(database, expected)
        self.assertIsInstance(namespace, Explosive)
        self.assertIsInstance(values, BoundedIterable)
        self.assertIs(identity, epoch.identity)

    def test_cache_epoch_pins_one_identity_and_one_read_instant(self):
        config = {"cache_dir": os.path.join("/tmp", "fnaudio-cache")}
        fingerprints = iter([("first",), ("second",)])
        writes = []

        def record_put(database, namespace, values, result, database_identity=None, read_at=None):
            writes.append((namespace, values, database_identity, read_at))
            return result

        def counting_identity(path):
            return next(fingerprints)

        with mock.patch.object(library, "_library_database_cache_identity", side_effect=counting_identity):
            with mock.patch.object(library, "LIBRARY_QUERY_CACHE") as cache:
                cache.get.return_value = None
                cache.put.side_effect = record_put
                epoch = library.LibraryCacheEpoch(config)
                read_at = epoch.read_at
                epoch.get("tracks", ("page",))
                epoch.put("tracks", ("page",), {"items": []})
                epoch.put("folders", ("page",), {"folders": []})

        # A second fingerprint would mean the read and the write disagree on
        # which database generation the page came from.
        self.assertEqual(list(fingerprints), [("second",)])
        self.assertEqual([entry[2] for entry in writes], [("first",), ("first",)])
        self.assertEqual([entry[3] for entry in writes], [read_at, read_at])
        self.assertGreater(read_at, 0.0)


if __name__ == "__main__":
    unittest.main()
