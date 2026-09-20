import sys
import unittest

sys.path.insert(0, "app/server")

from probe_metadata import MAX_PROBE_STREAMS, MAX_PROBE_TAGS, normalize_probe_payload


class ProbeMetadataTests(unittest.TestCase):
    def test_format_and_stream_tags_share_the_existing_precedence(self):
        tags, info = normalize_probe_payload({
            "format": {"duration": "12.5", "tags": {"title": "Format title", "artist": "Artist"}},
            "streams": [{"sample_rate": "96000", "bits_per_sample": 24, "tags": {"title": "Stream title", "tracknumber": "02/09"}}],
        })
        self.assertEqual(tags["title"], "Stream title")
        self.assertEqual(tags["track_no"], 2)
        self.assertEqual(info["sample_rate"], 96000)
        self.assertEqual(info["bit_depth"], 24)
        self.assertEqual(info["duration"], 12.5)

    def test_empty_probe_payload_is_bounded(self):
        self.assertEqual(normalize_probe_payload({}), ({}, {"sample_rate": 0, "bit_depth": 0, "bit_rate": 0, "duration": 0.0}))

    def test_malformed_payload_does_not_coerce_objects(self):
        class Explosive:
            def __int__(self):
                raise AssertionError("probe values must not be coerced")
            def __float__(self):
                raise AssertionError("probe values must not be coerced")
            def __str__(self):
                raise AssertionError("probe keys must not be stringified")

        self.assertEqual(normalize_probe_payload(Explosive())[1]["duration"], 0.0)
        tags, info = normalize_probe_payload({"format": {"duration": Explosive(), "tags": {Explosive(): "x"}}, "streams": [Explosive()]})
        self.assertEqual(tags, {})
        self.assertEqual(info["sample_rate"], 0)

    def test_probe_streams_are_bounded(self):
        streams = [{"sample_rate": str(index)} for index in range(MAX_PROBE_STREAMS + 20)]
        _tags, info = normalize_probe_payload({"streams": streams})
        self.assertEqual(info["sample_rate"], 0)

    def test_probe_tags_are_bounded(self):
        tags = {"title": "Title"}
        tags.update({"x%d" % index: "value" for index in range(MAX_PROBE_TAGS + 20)})
        normalized, _info = normalize_probe_payload({"format": {"tags": tags}})
        self.assertEqual(normalized["title"], "Title")


if __name__ == "__main__":
    unittest.main()
