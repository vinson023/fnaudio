import os
import sys
import unittest

sys.path.insert(0, "app/server")

from metadata_text import MAX_NORMALIZED_TAGS, MAX_TAG_TEXT, artist_title_from_filename, clean_tag, cue_time_seconds, cue_value, display_name, normalize_probe_tags, parse_track_number


class MetadataTextTests(unittest.TestCase):
    def test_tag_and_track_number_normalization(self):
        self.assertEqual(clean_tag("  A\x00  B\n"), "A B")
        self.assertEqual(parse_track_number("03/12"), 3)
        self.assertEqual(parse_track_number(13), 13)
        self.assertEqual(parse_track_number("side A"), 0)

    def test_clean_tag_rejects_objects_and_bounds_text(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("tags must not stringify custom objects")

        self.assertEqual(clean_tag(Explosive()), "")
        self.assertEqual(len(clean_tag("x" * (MAX_TAG_TEXT + 10))), MAX_TAG_TEXT)

    def test_probe_and_cue_helpers_ignore_non_text_inputs(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("metadata helpers must not stringify custom values")

        self.assertEqual(cue_time_seconds(Explosive()), 0.0)
        self.assertEqual(normalize_probe_tags({Explosive(): "ignored", "title": Explosive()}), {})
        self.assertEqual(normalize_probe_tags(Explosive()), {})

    def test_probe_tag_normalization_is_bounded(self):
        class Guarded(dict):
            def items(self):
                for index, pair in enumerate(super().items()):
                    if index >= MAX_NORMALIZED_TAGS + 1:
                        raise AssertionError("tag mapping iterated beyond bound")
                    yield pair

        tags = Guarded({"x%d" % index: "value" for index in range(MAX_NORMALIZED_TAGS + 100)})
        self.assertEqual(normalize_probe_tags(tags), {})

    def test_cue_time_rejects_unbounded_numeric_components(self):
        self.assertEqual(cue_time_seconds("9" * 100 + ":00:00"), 0.0)

    def test_track_number_rejects_huge_numeric_tags(self):
        self.assertEqual(parse_track_number("9" * 100), 0)
        self.assertEqual(parse_track_number("1000000/1000001"), 0)

    def test_filename_and_cue_helpers_keep_legacy_semantics(self):
        self.assertEqual(artist_title_from_filename("/music/02_Artist - Title.flac"), ("Artist", "Title"))
        self.assertEqual(display_name("/music/02_Only_Title.flac"), "Only Title")
        self.assertEqual(cue_value('TITLE " Album  Name "'), "Album Name")
        self.assertAlmostEqual(cue_time_seconds("01:30:37"), 90 + 37 / 75.0)

    def test_filename_helpers_reject_non_text_and_bound_long_names(self):
        self.assertEqual(artist_title_from_filename(object()), ("", ""))
        self.assertEqual(display_name(object()), "未知曲目")
        self.assertLessEqual(len(display_name("/music/" + "x" * (MAX_TAG_TEXT + 100) + ".flac")), MAX_TAG_TEXT)

    def test_probe_aliases_are_normalized_without_ffprobe_or_file_io(self):
        # R591: ``album_artist`` is its own field now.  It used to be folded into
        # ``artist``'s alias list, so the key was never produced and the album
        # grouping's ``COALESCE(album_artist, artist)`` always fell through to a
        # track artist.  ``artist`` still borrows the album artist when the file
        # carries no track artist, which is why the first case has both keys.
        self.assertEqual(
            normalize_probe_tags({"TIT2": "Title", "album_artist": "Artist", "TRCK": "04/10", "ignored": "x"}),
            {"title": "Title", "artist": "Artist", "album_artist": "Artist", "track_no": 4},
        )

    def test_a_compilation_keeps_album_artist_apart_from_the_track_artist(self):
        tags = normalize_probe_tags({
            "artist": "周杰伦", "album_artist": "群星", "album": "合辑",
            "track": "3/12", "disc": "2/2", "date": "2019-08-30", "comment": "hi",
        })
        self.assertEqual(tags["artist"], "周杰伦")
        self.assertEqual(tags["album_artist"], "群星", "the album artist must not be lost")
        self.assertEqual(tags["track_no"], 3)
        self.assertEqual(tags["disc_no"], 2)
        # ``date`` keeps the tag text so a write-back round-trip does not
        # truncate it; ``year`` is the numeric projection the column sorts on.
        self.assertEqual(tags["date"], "2019-08-30")
        self.assertEqual(tags["year"], 2019)
        self.assertEqual(tags["comment"], "hi")

    def test_a_file_tagged_only_with_album_artist_still_names_an_artist(self):
        # The degenerate case the old folding handled by accident: with no
        # ARTIST at all, ``artist`` has to keep showing something.
        self.assertEqual(
            normalize_probe_tags({"ALBUMARTIST": "群星"}),
            {"album_artist": "群星", "artist": "群星"},
        )

    def test_disc_and_year_take_the_shapes_taggers_actually_write(self):
        self.assertEqual(normalize_probe_tags({"disc": "1"})["disc_no"], 1)
        self.assertEqual(normalize_probe_tags({"DISKNUMBER": "03"})["disc_no"], 3)
        self.assertEqual(normalize_probe_tags({"disc": "2/3"})["disc_no"], 2)
        self.assertEqual(normalize_probe_tags({"date": "2020"})["year"], 2020)
        self.assertEqual(normalize_probe_tags({"date": "2020-05-01"})["year"], 2020)
        self.assertEqual(normalize_probe_tags({"TDRC": "2020-05-01T00:00:00"})["year"], 2020)
        self.assertEqual(normalize_probe_tags({"©day": "1999"})["year"], 1999)
        # Not a year, so not stored: the UI shows nothing rather than a guess.
        self.assertNotIn("year", normalize_probe_tags({"date": "not a date"}))
        self.assertNotIn("year", normalize_probe_tags({"date": "99"}))
        self.assertNotIn("disc_no", normalize_probe_tags({"disc": "0"}))

if __name__ == "__main__":
    unittest.main()
