import sys
import unittest

sys.path.insert(0, "app/server")

from library_root_presentation import MAX_ROOT_PRESENTATION, project_root_rows


class LibraryRootPresentationTests(unittest.TestCase):
    def test_projects_bounded_safe_rows_and_ignores_bad_summary_values(self):
        rows = project_root_rows(
            ["/music/a", "/music/b", object()],
            {"/music/a": {"track_count": "bad", "cover_track_id": object()}, "/music/b": {"track_count": 3}},
        )
        self.assertEqual([row["track_count"] for row in rows], [0, 3])
        self.assertEqual(rows[0]["cover_track_id"], "")
        self.assertEqual(rows[0]["name"], "a")

    def test_search_filter_and_iterator_failures_are_safe(self):
        class Broken:
            def __iter__(self):
                raise RuntimeError("broken")

        self.assertEqual(project_root_rows(Broken(), {}, set()), [])
        rows = project_root_rows(["/a", "/b"], {}, {"/b"})
        self.assertEqual([row["root"] for row in rows], ["/b"])

    def test_root_count_is_bounded(self):
        roots = ("/root-%s" % index for index in range(MAX_ROOT_PRESENTATION + 10))
        self.assertEqual(len(project_root_rows(roots, {})), MAX_ROOT_PRESENTATION)


if __name__ == "__main__":
    unittest.main()
