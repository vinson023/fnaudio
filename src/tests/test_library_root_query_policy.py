import sys
import unittest

sys.path.insert(0, "app/server")

from library_root_query_policy import MAX_CONFIGURED_ROOTS, configured_root_filter


class LibraryRootQueryPolicyTests(unittest.TestCase):
    def test_filter_is_bounded_deduplicated_and_parameterized(self):
        predicate, values = configured_root_filter(["/a", "/a", "/b"])
        self.assertEqual(predicate, "root IN (?,?)")
        self.assertEqual(values, ["/a", "/b"])

    def test_empty_or_broken_input_cannot_widen_query(self):
        self.assertEqual(configured_root_filter([]), ("1 = 0", []))

        class Broken:
            def __iter__(self):
                raise RuntimeError("broken")

        self.assertEqual(configured_root_filter(Broken()), ("1 = 0", []))

    def test_generator_is_stopped_at_configured_root_limit(self):
        seen = []

        def roots():
            for index in range(MAX_CONFIGURED_ROOTS + 20):
                seen.append(index)
                yield "/root-%s" % index

        predicate, values = configured_root_filter(roots())
        self.assertEqual(len(values), MAX_CONFIGURED_ROOTS)
        self.assertEqual(len(seen), MAX_CONFIGURED_ROOTS)
        self.assertEqual(predicate.count("?"), MAX_CONFIGURED_ROOTS)


if __name__ == "__main__":
    unittest.main()
