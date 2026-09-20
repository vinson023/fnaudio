import importlib.util
from pathlib import Path
import unittest


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tools" / "ui_e2e_fixture.py"
SPEC = importlib.util.spec_from_file_location("ui_e2e_fixture", FIXTURE_PATH)
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class UiE2eFixtureTests(unittest.TestCase):
    def test_query_integers_reject_invalid_and_bound_valid_values(self):
        self.assertEqual(fixture.bounded_query_int("12", 0, 0, 500), 12)
        self.assertEqual(fixture.bounded_query_int("999", 0, 0, 500), 500)
        self.assertEqual(fixture.bounded_query_int("-1", 7, 0, 500), 7)
        self.assertEqual(fixture.bounded_query_int("1.5", 7, 0, 500), 7)
        self.assertEqual(fixture.bounded_query_int("１２", 7, 0, 500), 7)

    def test_request_body_length_rejects_unsafe_values_before_reading(self):
        self.assertEqual(fixture.request_body_length(None), 0)
        self.assertEqual(fixture.request_body_length("12"), 12)
        self.assertIsNone(fixture.request_body_length("-1"))
        self.assertIsNone(fixture.request_body_length("1.5"))
        self.assertIsNone(fixture.request_body_length(str(fixture.MAX_REQUEST_BODY_BYTES + 1)))


if __name__ == "__main__":
    unittest.main()
