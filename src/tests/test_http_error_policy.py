import sys
import unittest

sys.path.insert(0, "app/server")

from http_error_policy import MAX_ERROR_TEXT_CHARS, project_error_text


class HttpErrorPolicyTests(unittest.TestCase):
    def test_bounds_text_and_rejects_arbitrary_objects(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify")

        message, explain = project_error_text("x" * 5000, Explosive())
        self.assertEqual(len(message), MAX_ERROR_TEXT_CHARS)
        self.assertIsNone(explain)

    def test_invalid_limit_uses_default(self):
        message, explain = project_error_text("abc", "def", 0)
        self.assertEqual((message, explain), ("abc", "def"))


if __name__ == "__main__":
    unittest.main()
