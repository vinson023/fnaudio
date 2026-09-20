import sys
import unittest

sys.path.insert(0, "app/server")

from library_cache_failure_policy import increment_failure, project_failures


class LibraryCacheFailurePolicyTests(unittest.TestCase):
    def test_increment_failure_keeps_only_known_bounded_counters(self):
        self.assertEqual(increment_failure({"load": 2, "save": 3, "private": "/secret"}, "load"), {"load": 3, "save": 3})
        self.assertEqual(increment_failure({"load": 2}, "unknown"), {"load": 2, "save": 0})

    def test_projection_rejects_untrusted_values_without_coercion(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("must not coerce")
        self.assertEqual(project_failures({"load": Explosive(), "save": True}), {"load": 0, "save": 0})

    def test_increment_saturates(self):
        self.assertEqual(increment_failure({"load": 2_147_483_647, "save": 0}, "load")["load"], 2_147_483_647)

    def test_broken_mapping_access_isolated(self):
        class BrokenDict(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken")
        self.assertEqual(project_failures(BrokenDict()), {"load": 0, "save": 0})
        self.assertEqual(increment_failure(BrokenDict(), "load"), {"load": 1, "save": 0})


if __name__ == "__main__":
    unittest.main()
