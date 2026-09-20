import sys
import unittest

sys.path.insert(0, "app/server")

from library_group_presentation import project_folder_rows, project_group_row, project_group_rows


class LibraryGroupPresentationTests(unittest.TestCase):
    def test_drops_window_metadata_and_unknown_columns(self):
        row = {"name": "Album", "track_count": 2, "total_count": 99, "secret": "x"}
        self.assertEqual(project_group_row(row), {"name": "Album", "track_count": 2})

    def test_bounds_rows_and_isolates_broken_iterators(self):
        class Broken:
            def __iter__(self):
                yield {"name": "A"}
                raise RuntimeError("broken")

        self.assertEqual(project_group_rows(Broken(), 10), [{"name": "A"}])
        self.assertEqual(project_group_rows([{"name": "A"}] * 8, 2), [{"name": "A"}, {"name": "A"}])

    def test_rejects_non_mapping_rows(self):
        self.assertEqual(project_group_rows([None, "bad", {"name": "ok"}], 10), [{"name": "ok"}])

    def test_broken_field_access_does_not_abort_page(self):
        class Broken(dict):
            def __getitem__(self, key):
                if key == "artist":
                    raise RuntimeError("broken field")
                return super().__getitem__(key)

        row = Broken(name="Album", track_count=2, cover_track_id="id")
        self.assertEqual(
            project_group_rows([row], 10),
            [{"name": "Album", "track_count": 2, "cover_track_id": "id"}],
        )

    def test_folder_projection_drops_window_metadata(self):
        row = {"path": "/music", "root": "/", "parent": "", "name": "music", "track_count": 3, "cover_track_id": "t1", "total_count": 10}
        self.assertEqual(project_folder_rows([row], 10), [{"path": "/music", "root": "/", "parent": "", "name": "music", "track_count": 3, "cover_track_id": "t1"}])


if __name__ == "__main__":
    unittest.main()
