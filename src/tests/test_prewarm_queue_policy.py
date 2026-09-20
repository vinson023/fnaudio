import unittest

from prewarm_queue_policy import bounded_unique_items


class PrewarmQueuePolicyTests(unittest.TestCase):
    def test_bounded_unique_items_preserves_order_and_reports_drops(self):
        result, dropped = bounded_unique_items(["a", "b", "a", "c", "d"], 3, lambda value: value)
        self.assertEqual(result, ["a", "b", "c"])
        self.assertEqual(dropped, 2)

    def test_empty_and_zero_limit_are_safe(self):
        self.assertEqual(bounded_unique_items([], 4, str), ([], 0))
        self.assertEqual(bounded_unique_items(["a"], 0, str), ([], 1))

    def test_generator_input_is_not_materialized_before_deduplication(self):
        result, dropped = bounded_unique_items((str(index) for index in range(5)), 2, str)
        self.assertEqual(result, ["0", "1"])
        self.assertEqual(dropped, 3)

    def test_dropped_tail_does_not_continue_growing_deduplication_state(self):
        calls = []
        result, dropped = bounded_unique_items(range(1000), 2, lambda value: calls.append(value) or value)
        self.assertEqual(result, [0, 1])
        self.assertEqual(dropped, 998)
        self.assertEqual(calls, [0, 1])

    def test_sized_large_input_stops_iterating_once_queue_is_full(self):
        class SizedIterable:
            def __init__(self):
                self.yielded = 0

            def __len__(self):
                return 1000

            def __iter__(self):
                for value in range(1000):
                    self.yielded += 1
                    yield value

        source = SizedIterable()
        result, dropped = bounded_unique_items(source, 2, lambda value: value)
        self.assertEqual(result, [0, 1])
        self.assertEqual(dropped, 998)
        self.assertEqual(source.yielded, 2)


if __name__ == "__main__":
    unittest.main()
