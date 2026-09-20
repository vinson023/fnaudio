import sys
import unittest
import sqlite3

sys.path.insert(0, "app/server")

from metadata_query_policy import MAX_QUERY_TEXT, entity_search_query, local_track_candidate, track_search_query


class MetadataQueryPolicyTests(unittest.TestCase):
    def test_track_query_accepts_sqlite_row_mapping(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT 'Song' AS title, 'Artist' AS artist, 'Album' AS album, '/music/Artist - Song.flac' AS path"
        ).fetchone()
        self.assertEqual(track_search_query(row), "Song Artist Album")
        connection.close()
    def test_omits_unknown_artist_placeholder(self):
        self.assertEqual(track_search_query({"title": "Song", "artist": "未知歌手"}), "Song")

    def test_keeps_real_title_and_artist(self):
        self.assertEqual(track_search_query({"title": "Song", "artist": "Artist"}), "Song Artist")

    def test_adds_known_album_as_a_disambiguation_hint(self):
        self.assertEqual(
            track_search_query({"title": "Song", "artist": "Artist", "album": "Album"}),
            "Song Artist Album",
        )

    def test_bounds_and_rejects_untrusted_values(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify")

        self.assertEqual(track_search_query({"title": "x" * (MAX_QUERY_TEXT + 20), "artist": Explosive()}), "x" * MAX_QUERY_TEXT)

    def test_uses_bounded_filename_when_title_is_missing(self):
        self.assertEqual(
            track_search_query({"title": "Unknown song", "artist": "Unknown artist", "path": r"E:\\Music\\Artist - Title.flac"}),
            "Title Artist",
        )

    def test_filename_fallback_does_not_replace_real_title(self):
        self.assertEqual(
            track_search_query({"title": "Real title", "path": "/music/other.flac"}),
            "Real title",
        )

    def test_missing_artist_uses_filename_artist_when_title_matches(self):
        self.assertEqual(
            track_search_query({"title": "Title", "artist": "Unknown artist", "path": r"E:\\Music\\Artist - Title.flac"}),
            "Title Artist",
        )

    def test_filename_artist_title_without_spaces_is_supported(self):
        self.assertEqual(
            track_search_query({"title": "Title", "artist": "Unknown artist", "path": r"E:\\Music\\Artist-Title.flac"}),
            "Title Artist",
        )

    def test_entity_query_omits_placeholders_and_bounds_text(self):
        self.assertEqual(entity_search_query("专辑", "未知艺术家"), "专辑")
        self.assertEqual(entity_search_query("x" * (MAX_QUERY_TEXT + 20)), "x" * MAX_QUERY_TEXT)

    def test_local_candidate_keeps_tagged_identity_during_provider_pending(self):
        candidate = local_track_candidate({
            "title": "晴天", "artist": "周杰伦", "album": "叶惠美",
            "album_artist": "周杰伦", "date": "2003", "track_no": "4",
            "path": "/music/晴天.flac",
        })
        self.assertEqual(candidate["source"], "local")
        self.assertEqual(candidate["title"], "晴天")
        self.assertEqual(candidate["album"], "叶惠美")
        self.assertEqual(candidate["track_no"], 4)
        self.assertEqual(candidate["confidence"], 1.0)

    def test_local_candidate_does_not_stringify_untrusted_fields(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify")

        self.assertIsNone(local_track_candidate({"title": Explosive(), "artist": ""}))


if __name__ == "__main__":
    unittest.main()
