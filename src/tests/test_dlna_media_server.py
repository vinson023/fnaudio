import os
import sys
import tempfile
import unittest

sys.path.insert(0, "app/server")

from dlna.media_server import soap_push, upnp_media_url, upnp_resource_mime, upnp_resource_size
from dlna.profiles import protocol_info, should_direct_push


class DlnaMediaServerTests(unittest.TestCase):
    def test_ape_renderer_resource_is_advertised_as_lossless_flac(self):
        item = {"id": "ape", "path": "/music/album.ape", "mime": "audio/ape"}

        self.assertEqual(upnp_resource_mime(item), "audio/flac")
    def test_dsd_push_advertises_the_original_dsf_resource(self):
        item = {"id": "dsd-1", "title": "DSD Track", "path": "/music/test.dsf", "is_dsd": True, "mime": "audio/x-dsf"}
        url = upnp_media_url(object(), item, lambda value: value, lambda handler: "http://nas:5666")

        self.assertTrue(url.endswith("/DSD%20Track.dsf"))
        self.assertEqual(upnp_resource_mime(item), "audio/x-dsf")

    def test_dsd_resource_size_uses_the_source_file(self):
        with tempfile.TemporaryDirectory() as root:
            item = {"id": "dsd-1", "path": os.path.join(root, "source.dsf"), "is_dsd": True}
            with open(item["path"], "wb") as handle:
                handle.write(b"source-dsd")

            size = upnp_resource_size(item, {}, lambda current, config, mode: (_ for _ in ()).throw(AssertionError("DSD must not transcode")))

            self.assertEqual(size, len(b"source-dsd"))

    def test_dff_push_keeps_source_mime_even_when_renderer_does_not_advertise_dsd(self):
        item = {"id": "dsd-2", "path": "/music/test.dff", "is_dsd": True, "mime": "audio/x-dff"}
        device = {"supports_dsd": False}

        self.assertEqual(upnp_resource_mime(item), "audio/x-dff")

    def test_dsd_push_is_rejected_when_renderer_explicitly_lacks_dsd_sink(self):
        item = {"id": "dff-1", "path": "/music/test.dff", "is_dsd": True, "mime": "audio/x-dff", "duration": 1}
        device = {
            "control_url": "http://renderer/control",
            "capabilities": {
                "protocol_info": {"supports_dsd": False},
                "actions": ["SetAVTransportURI", "Play"],
            },
        }
        class Handler:
            server = type("Server", (), {"config": {}})()

        result = soap_push(device, item, Handler(), lambda value: value, lambda _h: "http://host", lambda *_: "")
        self.assertEqual(result[0], False)
        self.assertIn("不支持源码 DSD", result[1])
        self.assertEqual(protocol_info(item, device), "http-get:*:audio/x-dff:*")
        self.assertTrue(should_direct_push(item, device))


if __name__ == "__main__":
    unittest.main()
