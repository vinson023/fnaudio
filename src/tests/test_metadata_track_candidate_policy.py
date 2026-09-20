import unittest

from metadata_track_candidate_policy import project_track_candidate_fields


class MetadataTrackCandidatePolicyTests(unittest.TestCase):
    def test_projects_only_bounded_text_and_falls_back_album_artist(self):
        result = project_track_candidate_fields(
            "  Song\x00 ", 123, " Album ", None, "2024-01-02", " Pop ",
            "03/10", "https://example.test/cover.jpg", "provider-id", "qq",
        )
        self.assertEqual(result["title"], "Song")
        self.assertEqual(result["artist"], "")
        self.assertEqual(result["album"], "Album")
        self.assertEqual(result["album_artist"], "")
        self.assertEqual(result["track_no"], 3)
        self.assertEqual(result["source"], "qq")

    def test_rejects_arbitrary_objects_without_stringifying(self):
        class Broken:
            def __str__(self):
                raise AssertionError("must not stringify")

        result = project_track_candidate_fields(Broken(), Broken(), Broken(), Broken(), Broken(), Broken(), Broken(), Broken(), Broken(), Broken())
        self.assertEqual(result["title"], "")
        self.assertEqual(result["artist"], "")
        self.assertEqual(result["image_url"], "")
        self.assertEqual(result["track_no"], 0)

    def test_normalizes_protocol_relative_artwork_urls(self):
        result = project_track_candidate_fields("Song", "Artist", image_url="//img.example/cover.jpg")
        self.assertEqual(result["image_url"], "https://img.example/cover.jpg")


if __name__ == "__main__":
    unittest.main()
