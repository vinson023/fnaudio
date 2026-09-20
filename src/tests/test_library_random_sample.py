import sys
import unittest

sys.path.insert(0, "app/server")

from library_random_sample import MAX_RANDOM_ROWID_CANDIDATES, random_rowid_candidates


class LibraryRandomSampleTests(unittest.TestCase):
    def test_candidates_are_bounded_deduplicated_and_one_based(self):
        values = random_rowid_candidates(10, 10000, lambda _start, _stop: 1)
        self.assertEqual(values, [1])

    def test_candidate_generation_keeps_a_hard_upper_bound(self):
        values = random_rowid_candidates(100000, MAX_RANDOM_ROWID_CANDIDATES + 100, lambda start, _stop: start)
        self.assertEqual(len(values), 1)
        self.assertLessEqual(len(values), MAX_RANDOM_ROWID_CANDIDATES)

    def test_candidates_reject_invalid_inputs_and_broken_random_source(self):
        self.assertEqual(random_rowid_candidates(0, 10, lambda _start, _stop: 1), [])
        self.assertEqual(random_rowid_candidates(10, 0, lambda _start, _stop: 1), [])
        self.assertEqual(random_rowid_candidates(10, 2, lambda _start, _stop: (_ for _ in ()).throw(RuntimeError())), [])


if __name__ == "__main__":
    unittest.main()
