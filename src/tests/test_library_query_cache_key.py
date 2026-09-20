import sys
import unittest

sys.path.insert(0, "app/server")

from library_query_cache_key import MAX_CACHE_KEY_TEXT, MAX_CACHE_KEY_VALUES, build_cache_key, normalize_database_identity, normalize_values


class LibraryQueryCacheKeyTests(unittest.TestCase):
    def test_builds_bounded_key_from_supported_values(self):
        key = build_cache_key("/tmp/db", "tracks", ["x" * MAX_CACHE_KEY_TEXT, 2, 1.5])
        self.assertEqual(key[1], "tracks")
        self.assertEqual(key[2], ("x" * 4096, 2, 1.5))

    def test_rejects_overlong_query_values_instead_of_aliasing_them(self):
        first = "x" * MAX_CACHE_KEY_TEXT + "first"
        second = "x" * MAX_CACHE_KEY_TEXT + "second"
        self.assertIsNone(normalize_values((first,)))
        self.assertIsNone(normalize_values((second,)))
        self.assertIsNone(build_cache_key("/tmp/db", "tracks", (first,)))
        self.assertIsNone(build_cache_key("/tmp/db", "tracks", (second,)))

    def test_rejects_unsupported_values_without_collapsing_them(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("cache keys must not stringify arbitrary values")

        self.assertIsNone(normalize_values([Explosive()]))
        self.assertIsNone(build_cache_key("/tmp/db", "tracks", [Explosive()]))

    def test_distinguishes_missing_values_from_an_explicit_empty_sequence(self):
        self.assertIsNone(normalize_values(None))
        self.assertIsNone(normalize_values(1))
        self.assertEqual(normalize_values(()), ())
        self.assertIsNone(build_cache_key("/tmp/db", "tracks", None))
        self.assertIsNone(build_cache_key("/tmp/db", "tracks", 1))
        self.assertIsNotNone(build_cache_key("/tmp/db", "tracks", ()))

    def test_rejects_extreme_numeric_key_values(self):
        self.assertIsNone(normalize_values([10 ** 10000]))
        self.assertIsNone(normalize_values([10 ** 13]))
        self.assertIsNone(normalize_values([float("1e13")]))
        self.assertEqual(normalize_values([10 ** 12]), (10 ** 12,))

    def test_rejects_values_beyond_the_cache_key_limit(self):
        first = tuple(range(MAX_CACHE_KEY_VALUES)) + (100,)
        second = tuple(range(MAX_CACHE_KEY_VALUES)) + (200,)
        self.assertIsNone(normalize_values(first))
        self.assertIsNone(normalize_values(second))
        self.assertIsNone(build_cache_key("/tmp/db", "tracks", first))

    def test_rejects_overlong_identity_components_instead_of_truncating(self):
        oversized = "x" * (MAX_CACHE_KEY_TEXT + 1)
        self.assertIsNone(build_cache_key(oversized, "tracks", ()))
        self.assertIsNone(build_cache_key("/tmp/db", oversized, ()))

    def test_database_identity_partitions_replaceable_database_entries(self):
        first = build_cache_key("/tmp/db", "tracks", ("page",), (1, 2, 3, 4))
        second = build_cache_key("/tmp/db", "tracks", ("page",), (1, 2, 4, 4))
        self.assertNotEqual(first, second)
        self.assertEqual(normalize_database_identity((1, 2, 3, 4)), (1, 2, 3, 4))
        self.assertIsNone(normalize_database_identity((1, object())))

    def test_identity_key_cannot_collide_with_a_flat_query_value_prefix(self):
        identity_key = build_cache_key("/tmp/db", "tracks", (), (1, 2, 3, 4))
        non_identity_key = build_cache_key(
            "/tmp/db", "tracks", ("database_identity", 1, 2, 3, 4)
        )
        self.assertNotEqual(identity_key, non_identity_key)


if __name__ == "__main__":
    unittest.main()
