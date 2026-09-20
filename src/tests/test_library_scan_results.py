import sys
import unittest

sys.path.insert(0, "app/server")
from library_scan_results import _MAX_PATH_LENGTH, _MAX_PREVIOUS_ITEMS, _MAX_ROOTS, _MAX_SIGNATURE_TOTAL_LENGTH, _MAX_SORT_ITEMS, build_previous_item_index, digest_signature_parts, finalize_scan_results, partition_previous_items, sort_scan_items


class LibraryScanResultsTests(unittest.TestCase):
    def test_sort_scan_items_handles_missing_fields_without_mutating_input(self):
        items = [{"id": "b"}, {"id": "a", "artist": "A"}]
        result = sort_scan_items(items)
        self.assertEqual([item["id"] for item in result], ["b", "a"])
        self.assertEqual(items[0]["id"], "b")

    def test_sort_scan_items_bounds_untrusted_iterables(self):
        consumed = []
        def source():
            for index in range(_MAX_SORT_ITEMS + 100):
                consumed.append(index)
                yield {"id": str(index)}
        result = sort_scan_items(source())
        self.assertEqual(len(result), _MAX_SORT_ITEMS)
        self.assertEqual(len(consumed), _MAX_SORT_ITEMS)

    def test_signature_digest_is_deterministic_and_bounded(self):
        self.assertEqual(
            digest_signature_parts(["b", "a" * 5000]),
            digest_signature_parts(["a" * 4096, "b"]),
        )

    def test_previous_item_index_isolates_malformed_entries(self):
        class BrokenAfterOne:
            def __iter__(self):
                yield {"path": "/music/ok.flac", "id": "ok"}
                yield None
                raise RuntimeError("broken")

        self.assertEqual(
            build_previous_item_index(BrokenAfterOne()),
            {"/music/ok.flac": {"path": "/music/ok.flac", "id": "ok"}},
        )

    def test_previous_item_index_skips_broken_path_access(self):
        class Broken(dict):
            def get(self, key, default=None):
                if key == "path":
                    raise RuntimeError("broken")
                return super().get(key, default)

        self.assertEqual(build_previous_item_index([Broken(id="bad"), {"path": "/music/ok.flac"}]), {"/music/ok.flac": {"path": "/music/ok.flac"}})

    def test_previous_item_index_bounds_input(self):
        consumed = []
        def source():
            for index in range(_MAX_PREVIOUS_ITEMS + 10):
                consumed.append(index)
                yield {"path": f"/music/{index}"}
        result = build_previous_item_index(source())
        self.assertEqual(len(result), _MAX_PREVIOUS_ITEMS)
        self.assertEqual(len(consumed), _MAX_PREVIOUS_ITEMS)

    def test_previous_indexes_skip_oversized_paths(self):
        oversized = {"path": "/music/" + "x" * _MAX_PATH_LENGTH}
        self.assertEqual(build_previous_item_index([oversized]), {})
        buckets = partition_previous_items([oversized], ["/music"], lambda *_: True)
        self.assertEqual(buckets, [[]])

    def test_deduplicates_and_sorts_without_filesystem(self):
        items = [
            {"id": "b", "artist": "Z", "album": "A", "title": "Two"},
            {"id": "a", "artist": "a", "album": "B", "title": "One"},
            {"id": "b", "artist": "Z", "album": "A", "title": "Duplicate"},
        ]
        result, digest = finalize_scan_results(items, ["/root:z", "", 3, "/root:a"])
        self.assertEqual([item["id"] for item in result], ["a", "b"])
        self.assertEqual(len(digest), 40)

    def test_sort_uses_id_as_stable_tiebreaker(self):
        items, _ = finalize_scan_results([
            {"id": "z", "artist": "A", "album": "B", "title": "C"},
            {"id": "a", "artist": "A", "album": "B", "title": "C"},
        ], [])
        self.assertEqual([item["id"] for item in items], ["a", "z"])

    def test_malformed_items_and_signatures_are_ignored(self):
        result, digest = finalize_scan_results([None, {"id": "x"}, {"id": "x"}, {"id": []}], [None, object()])
        self.assertEqual([item["id"] for item in result], ["x"])
        self.assertEqual(len(digest), 40)

    def test_broken_iterables_do_not_abort_finalization(self):
        class Broken:
            def __iter__(self):
                raise RuntimeError("broken")

        result, digest = finalize_scan_results(Broken(), Broken())
        self.assertEqual(result, [])
        self.assertEqual(len(digest), 40)

    def test_signature_iterator_failure_does_not_abort_finalization(self):
        class BrokenAfterOne:
            def __iter__(self):
                yield "/root:ok"
                raise RuntimeError("broken")

        result, digest = finalize_scan_results([{"id": "x"}], BrokenAfterOne())
        self.assertEqual([item["id"] for item in result], ["x"])
        self.assertEqual(len(digest), 40)

    def test_signature_text_is_bounded_before_digest(self):
        result, truncated_digest = finalize_scan_results([{"id": "x"}], ["a" * 5000])
        _, bounded_digest = finalize_scan_results([{"id": "x"}], ["a" * 4096])
        self.assertEqual([item["id"] for item in result], ["x"])
        self.assertEqual(truncated_digest, bounded_digest)

    def test_signature_total_text_has_a_global_bound(self):
        oversized = ["x" * 4096] * ((_MAX_SIGNATURE_TOTAL_LENGTH // 4096) + 100)
        self.assertEqual(digest_signature_parts(oversized), digest_signature_parts(oversized[:_MAX_SIGNATURE_TOTAL_LENGTH // 4096]))

    def test_item_iterator_failure_keeps_items_read_before_failure(self):
        class BrokenAfterOne:
            def __iter__(self):
                yield {"id": "ok"}
                raise RuntimeError("broken")

        result, _ = finalize_scan_results(BrokenAfterOne(), [])
        self.assertEqual([item["id"] for item in result], ["ok"])

    def test_previous_items_are_partitioned_by_root(self):
        items = [
            {"id": "a", "path": "/music/a/song.flac"},
            {"id": "b", "path": "/other/b/song.flac"},
            {"id": "bad", "path": object()},
        ]
        under = lambda path, root: path == root or path.startswith(root + "/")
        buckets = partition_previous_items(items, ["/music", "/other"], under)
        self.assertEqual([[item["id"] for item in bucket] for bucket in buckets], [["a"], ["b"]])

    def test_partition_reuses_root_match_for_duplicate_paths(self):
        calls = []
        items = [{"id": "a", "path": "/music/song.flac"}, {"id": "b", "path": "/music/song.flac"}]
        def under(path, root):
            calls.append((path, root))
            return True
        buckets = partition_previous_items(items, ["/music"], under)
        self.assertEqual([item["id"] for item in buckets[0]], ["a", "b"])
        self.assertEqual(calls, [("/music/song.flac", "/music")])

    def test_partition_isolates_broken_root_container(self):
        class Broken:
            def __iter__(self):
                raise RuntimeError("broken")

        self.assertEqual(partition_previous_items([{"id": "x", "path": "/music/x"}], Broken(), lambda *_: True), [])

    def test_partition_isolates_broken_item_container(self):
        class Broken:
            def __iter__(self):
                raise RuntimeError("broken")

        self.assertEqual(partition_previous_items(Broken(), ["/music"], lambda *_: True), [[]])

    def test_sort_isolates_broken_mapping_access(self):
        class Broken(dict):
            def get(self, key, default=None):
                if key == "artist":
                    raise RuntimeError("broken")
                return super().get(key, default)

        result, _ = finalize_scan_results([
            Broken(id="b", album="A", title="C"),
            {"id": "a", "artist": "A", "album": "A", "title": "C"},
        ], [])
        self.assertEqual([item["id"] for item in result], ["b", "a"])

    def test_deduplication_skips_broken_id_access(self):
        class Broken(dict):
            def get(self, key, default=None):
                if key == "id":
                    raise RuntimeError("broken")
                return super().get(key, default)

        result, _ = finalize_scan_results([
            Broken(artist="A"),
            {"id": "ok", "artist": "B"},
        ], [])
        self.assertEqual([item["id"] for item in result], ["ok"])

    def test_partition_skips_broken_path_access(self):
        class Broken(dict):
            def get(self, key, default=None):
                if key == "path":
                    raise RuntimeError("broken")
                return super().get(key, default)

        buckets = partition_previous_items([
            Broken(id="bad"),
            {"id": "ok", "path": "/music/song.flac"},
        ], ["/music"], lambda path, root: path == root or path.startswith(root + "/"))
        self.assertEqual([[item["id"] for item in bucket] for bucket in buckets], [["ok"]])

    def test_partition_keeps_items_before_iterator_failure(self):
        class BrokenAfterOne:
            def __iter__(self):
                yield {"id": "ok", "path": "/music/song.flac"}
                raise RuntimeError("broken")

        buckets = partition_previous_items(
            BrokenAfterOne(), ["/music"],
            lambda path, root: path == root or path.startswith(root + "/"),
        )
        self.assertEqual([[item["id"] for item in bucket] for bucket in buckets], [["ok"]])

    def test_partition_bounds_input(self):
        consumed = []
        def source():
            for index in range(_MAX_PREVIOUS_ITEMS + 10):
                consumed.append(index)
                yield {"path": f"/music/{index}", "id": str(index)}
        buckets = partition_previous_items(source(), ["/music"], lambda path, root: path.startswith(root + "/"))
        self.assertEqual(len(buckets[0]), _MAX_PREVIOUS_ITEMS)
        self.assertEqual(len(consumed), _MAX_PREVIOUS_ITEMS)

    def test_partition_bounds_root_iterable(self):
        consumed = []
        def roots():
            for index in range(_MAX_ROOTS + 10):
                consumed.append(index)
                yield f"/music/{index}"
        buckets = partition_previous_items([], roots(), lambda *_: True)
        self.assertEqual(len(buckets), _MAX_ROOTS)
        self.assertEqual(len(consumed), _MAX_ROOTS)

    def test_partition_skips_invalid_root_values(self):
        roots = [object(), "", "x" * (_MAX_PATH_LENGTH + 1), "/music"]
        buckets = partition_previous_items([], roots, lambda *_: True)
        self.assertEqual(len(buckets), 1)

    def test_deduplication_skips_ids_with_broken_hash(self):
        class BrokenHash:
            def __hash__(self):
                raise RuntimeError("broken")

        result, _ = finalize_scan_results([
            {"id": BrokenHash()},
            {"id": "ok"},
        ], [])
        self.assertEqual([item["id"] for item in result], ["ok"])

    def test_sort_key_bounds_large_text(self):
        result, _ = finalize_scan_results([
            {"id": "b", "artist": "a" * 5000},
            {"id": "a", "artist": "a" * 4096},
        ], [])
        self.assertEqual([item["id"] for item in result], ["a", "b"])

    def test_deduplication_skips_oversized_text_id(self):
        result, _ = finalize_scan_results([
            {"id": "x" * 4097},
            {"id": "ok"},
        ], [])
        self.assertEqual([item["id"] for item in result], ["ok"])

    def test_finalization_bounds_unique_results(self):
        result, _ = finalize_scan_results(({"id": str(index)} for index in range(_MAX_SORT_ITEMS + 100)), [])
        self.assertEqual(len(result), _MAX_SORT_ITEMS)


if __name__ == "__main__":
    unittest.main()
