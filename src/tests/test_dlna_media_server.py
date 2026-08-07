import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

from dlna.media_server import upnp_media_url, upnp_resource_mime, upnp_resource_size


class DlnaMediaServerTests(unittest.TestCase):
    def test_dsd_push_advertises_the_transcoded_wav_resource(self):
        item = {"id": "dsd-1", "title": "DSD Track", "path": "/music/test.dsf", "is_dsd": True, "mime": "audio/x-dsf"}
        url = upnp_media_url(object(), item, lambda value: value, lambda handler: "http://nas:5666")

        self.assertTrue(url.endswith("/DSD%20Track.wav?transcode=dsd_wav"))
        self.assertEqual(upnp_resource_mime(item), "audio/wav")

    def test_dsd_resource_size_uses_the_pcm_cache_file(self):
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "converted.wav")
            with open(target, "wb") as handle:
                handle.write(b"pcm-data")
            item = {"id": "dsd-1", "path": os.path.join(root, "source.dsf"), "is_dsd": True}

            size = upnp_resource_size(item, {}, lambda current, config, mode: (target, "audio/wav"))

            self.assertEqual(size, len(b"pcm-data"))


if __name__ == "__main__":
    unittest.main()
