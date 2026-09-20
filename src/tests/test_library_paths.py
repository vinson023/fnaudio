import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

from library_paths import (
    MAX_LIBRARY_PATHS,
    MAX_LIBRARY_PATH_TEXT,
    apply_library_paths,
    bounded_library_path_text,
    canonical_library_path,
    library_root_labels,
    merge_library_paths,
    normalize_library_paths,
    relative_folder_for_path,
)


class LibraryPathTests(unittest.TestCase):
    def test_bounded_library_path_text_is_shared_by_writers(self):
        self.assertEqual(bounded_library_path_text(" /music/a "), "/music/a")
        self.assertEqual(bounded_library_path_text("x" * (MAX_LIBRARY_PATH_TEXT + 1)), "")
        self.assertEqual(bounded_library_path_text(object()), "")

    def test_allowed_path_rejects_non_text_and_empty_values_before_path_access(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("allowed path checks must not stringify arbitrary objects")

        from library_paths import is_allowed_library_path

        self.assertFalse(is_allowed_library_path(Explosive()))
        self.assertFalse(is_allowed_library_path(""))

    def test_normalization_merges_legacy_and_structured_paths_without_duplicates(self):
        with tempfile.TemporaryDirectory() as root:
            first = os.path.join(root, "first")
            second = os.path.join(root, "second")
            config = {"library_paths": [first], "library_path": "%s\n%s" % (os.path.join(first, "."), second)}
            self.assertEqual(normalize_library_paths(config), [canonical_library_path(first), canonical_library_path(second)])

    def test_library_path_inputs_are_bounded(self):
        roots = [f"/vol1/music-{index}" for index in range(MAX_LIBRARY_PATHS + 10)]
        self.assertEqual(len(normalize_library_paths({"library_paths": roots})), MAX_LIBRARY_PATHS)
        self.assertEqual(len(merge_library_paths(roots, roots)), MAX_LIBRARY_PATHS)

    def test_empty_and_duplicate_entries_do_not_hide_later_valid_roots(self):
        roots = ["", "/vol1/music"] * 40 + ["/vol2/music"]
        normalized = normalize_library_paths({"library_paths": roots})
        self.assertIn(canonical_library_path("/vol2/music"), normalized)

    def test_path_normalization_skips_objects_that_cannot_be_safely_textified(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("path values must not stringify arbitrary objects")

        self.assertEqual(normalize_library_paths({"library_paths": [Explosive(), "/vol1/music"]}), [canonical_library_path("/vol1/music")])
        self.assertEqual(merge_library_paths([Explosive()], ["/vol1/music"]), [canonical_library_path("/vol1/music")])

    def test_canonical_path_rejects_untrusted_objects_without_stringifying(self):
        class Explosive:
            def __bool__(self):
                raise AssertionError("canonical path must not evaluate arbitrary truthiness")

            def __str__(self):
                raise AssertionError("canonical path must not stringify arbitrary objects")

        self.assertEqual(canonical_library_path(Explosive()), canonical_library_path("."))

    def test_normalization_rejects_non_mapping_config(self):
        self.assertEqual(normalize_library_paths(None), [canonical_library_path(".")])

    def test_apply_rejects_non_mapping_config(self):
        apply_library_paths(None, ["/vol1/music"])

    def test_path_text_is_bounded(self):
        self.assertEqual(normalize_library_paths({"library_paths": ["/vol1/" + "x" * 5000]}), [canonical_library_path(".")])
        self.assertEqual(normalize_library_paths({"library_path": "/vol1/" + "x" * 5000}), [canonical_library_path(".")])

    def test_apply_library_paths_bounds_and_filters_input(self):
        oversized = "/vol1/" + "x" * (MAX_LIBRARY_PATH_TEXT + 1)
        paths = ["/vol1/music"] * 3 + [None, oversized] + [f"/vol1/music-{index}" for index in range(MAX_LIBRARY_PATHS + 5)]
        config = {}
        apply_library_paths(config, paths)
        self.assertLessEqual(len(config["library_paths"]), MAX_LIBRARY_PATHS)
        self.assertTrue(all(isinstance(path, str) and path for path in config["library_paths"]))
        self.assertNotIn(None, config["library_paths"])
        self.assertNotIn(oversized, config["library_paths"])

    def test_merge_apply_and_labels_keep_root_identity(self):
        with tempfile.TemporaryDirectory() as root:
            first = os.path.join(root, "a", "music")
            second = os.path.join(root, "b", "music")
            merged = merge_library_paths([first], [second, first])
            config = {}
            apply_library_paths(config, merged)
            self.assertEqual(normalize_library_paths(config), merged)
            self.assertEqual(set(library_root_labels(config).values()), {"a/music", "b/music"})

    def test_relative_folder_is_portable_and_never_escapes_on_invalid_roots(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(relative_folder_for_path(os.path.join(root, "album", "track.flac"), root), "album")
            self.assertEqual(relative_folder_for_path("", ""), "")


if __name__ == "__main__":
    unittest.main()
