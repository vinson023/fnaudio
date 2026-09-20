import sys
import unittest

sys.path.insert(0, "app/server")
from api_token_policy import MAX_TOKEN_CHARS, trim_api_token


class ApiTokenPolicyTests(unittest.TestCase):
    def test_priority_and_bearer(self):
        self.assertEqual(trim_api_token({"X-Fnaudio-Trim-Token": " abc ", "Authorization": "Bearer xyz"}), "abc")
        self.assertEqual(trim_api_token({"Authorization": "Bearer  xyz  "}), "xyz")

    def test_invalid_and_broken_inputs_are_safe(self):
        self.assertEqual(trim_api_token({"X-Fnaudio-Trim-Token": 42, "Authorization": " ok "}), "ok")
        class Broken(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken")
        self.assertEqual(trim_api_token(Broken()), "")
        self.assertEqual(trim_api_token(object()), "")

        class HeaderLike:
            def get(self, key, default=None):
                return {"Authorization": "Bearer header-like"}.get(key, default)

        self.assertEqual(trim_api_token(HeaderLike()), "header-like")

    def test_length_is_bounded(self):
        self.assertEqual(trim_api_token({"Authorization": "x" * (MAX_TOKEN_CHARS + 100)}), "")

    def test_rejects_control_and_internal_whitespace(self):
        self.assertEqual(trim_api_token({"Authorization": "token\nforged"}), "")
        self.assertEqual(trim_api_token({"Authorization": "token\tforged"}), "")


if __name__ == "__main__":
    unittest.main()
