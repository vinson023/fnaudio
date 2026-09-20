import unittest

import sys

sys.path.insert(0, "app/server")

from metadata_tag_resolution import resolve_metadata_tags


class MetadataTagResolutionTests(unittest.TestCase):
    def test_complete_probe_skips_native_reader(self):
        calls = []
        complete = {"title": "T", "artist": "A", "album": "B", "composer": "C", "genre": "G", "track_no": 1}
        result = resolve_metadata_tags("song.mp3", complete, lambda _: calls.append("probe"), lambda _: calls.append("id3"), lambda _: calls.append("vorbis"))
        self.assertEqual(result, complete)
        self.assertEqual(calls, [])

    def test_partial_probe_uses_id3_for_id3_containers(self):
        calls = []
        probe = {"title": "T"}
        result = resolve_metadata_tags("song.dsf", probe, lambda _: calls.append("probe"), lambda _: (calls.append("id3"), {"artist": "A"})[1], lambda _: calls.append("vorbis"))
        self.assertEqual(result, {"title": "T", "artist": "A"})
        self.assertEqual(calls, ["id3"])

    def test_empty_probe_reads_probe_then_vorbis_fallback(self):
        calls = []
        result = resolve_metadata_tags("song.flac", {}, lambda _: (calls.append("probe"), {"title": "T"})[1], lambda _: calls.append("id3"), lambda _: (calls.append("vorbis"), {"album": "B"})[1])
        self.assertEqual(result, {"title": "T", "album": "B"})
        self.assertEqual(calls, ["probe", "vorbis"])

    def test_broken_local_reader_keeps_probe_tags(self):
        result = resolve_metadata_tags("song.flac", {"title": "T"}, lambda _: {}, lambda _: {}, lambda _: (_ for _ in ()).throw(RuntimeError("broken")))
        self.assertEqual(result, {"title": "T"})

    def test_broken_probe_reader_falls_back_to_local_reader(self):
        result = resolve_metadata_tags("song.mp3", {}, lambda _: (_ for _ in ()).throw(RuntimeError("broken")), lambda _: {"artist": "A"}, lambda _: {})
        self.assertEqual(result, {"artist": "A"})


if __name__ == "__main__":
    unittest.main()
