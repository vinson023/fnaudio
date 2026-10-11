import sys
import unittest

sys.path.insert(0, "app/server")

import sqlite3

from library_cache_failure_policy import (
    MAX_FAILURE_DETAIL_CHARS,
    describe_failure,
    increment_failure,
    project_failures,
)


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


class DescribeFailureTests(unittest.TestCase):
    """Ninety-eight identical "persistence failed" lines had no cause in them."""

    def test_the_exception_class_and_message_survive(self):
        self.assertEqual(
            describe_failure(sqlite3.OperationalError("database is locked")),
            "sqlite3.OperationalError: database is locked",
        )

    def test_sqlite_module_is_named_so_operational_error_is_not_ambiguous(self):
        self.assertTrue(describe_failure(sqlite3.Error("table is locked")).startswith("sqlite3."))

    def test_absolute_paths_are_collapsed(self):
        detail = describe_failure(OSError(13, "attempt to open /vol2/1000/music/a.flac"))
        self.assertIn("<path>", detail)
        self.assertNotIn("/vol2", detail)

    def test_windows_paths_are_collapsed_too(self):
        detail = describe_failure(OSError("cannot write C:\\Users\\x\\library.sqlite3"))
        self.assertNotIn("C:", detail)
        self.assertIn("<path>", detail)

    def test_prose_slashes_are_not_mangled(self):
        self.assertEqual(describe_failure(RuntimeError("disk I/O error")), "RuntimeError: disk I/O error")

    def test_the_detail_is_a_single_bounded_line(self):
        detail = describe_failure(ValueError("line one\nline two\t\t/vol1/a/b " + "z" * 500))
        self.assertLessEqual(len(detail), MAX_FAILURE_DETAIL_CHARS)
        self.assertNotIn("\n", detail)
        self.assertNotIn("\t", detail)

    def test_garbage_input_never_raises(self):
        for value in (None, 123, [], {}, "", "plain text"):
            with self.subTest(value=value):
                described = describe_failure(value)
                self.assertIsInstance(described, str)
        self.assertEqual(describe_failure(None), "")
        self.assertEqual(describe_failure(123), "")
        self.assertEqual(describe_failure(""), "")
        self.assertEqual(describe_failure("plain text"), "plain text")


if __name__ == "__main__":
    unittest.main()
