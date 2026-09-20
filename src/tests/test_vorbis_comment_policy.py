import sys
import unittest

sys.path.insert(0, "app/server")

from vorbis_comment_policy import MAX_VORBIS_TAGS, parse_vorbis_comments


class VorbisCommentPolicyTests(unittest.TestCase):
    def test_extracts_only_supported_normalized_fields(self):
        tags = parse_vorbis_comments(b"TITLE= Song \nARTIST=Artist\nTRACKNUMBER=03/12\nIGNORED=value")
        self.assertEqual(tags, {"title": "Song", "artist": "Artist", "track_no": 3})

    def test_rejects_non_binary_and_bounds_match_count(self):
        self.assertEqual(parse_vorbis_comments("TITLE=bad"), {})
        payload = b"\n".join(b"TITLE=value%d" % index for index in range(MAX_VORBIS_TAGS + 8))
        self.assertEqual(parse_vorbis_comments(payload)["title"], "value127")


if __name__ == "__main__":
    unittest.main()
