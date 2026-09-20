import os
import sys
import tempfile
import unittest
import urllib.parse
import xml.etree.ElementTree as ET
from unittest import mock

sys.path.insert(0, "app/server")

from dlna.media_server import renderer_track_metadata, soap_push, upnp_media_url, upnp_resource_mime, upnp_resource_size
from dlna.profiles import protocol_info, should_direct_push


class DlnaMediaServerTests(unittest.TestCase):
    def test_ape_renderer_resource_is_advertised_as_lossless_flac(self):
        item = {"id": "ape", "path": "/music/album.ape", "mime": "audio/ape"}

        self.assertEqual(upnp_resource_mime(item), "audio/flac")

    def test_ape_resource_size_uses_the_lossless_compatibility_bytes(self):
        # The advertised size has to describe the FLAC bytes that /upnp/media
        # actually serves for an APE source, not the untouched container.
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, "album.ape")
            compatible = os.path.join(root, "album.ape-source.flac")
            with open(source, "wb") as handle:
                handle.write(b"ape-source")
            with open(compatible, "wb") as handle:
                handle.write(b"flac-compatible-resource")
            item = {"id": "ape", "path": source, "mime": "audio/ape"}
            transcode = mock.Mock(return_value=(compatible, "audio/flac"))

            size = upnp_resource_size(item, {}, transcode)

            self.assertEqual(size, len(b"flac-compatible-resource"))
            self.assertEqual(upnp_resource_mime(item), "audio/flac")
            transcode.assert_called_with(item, {}, "ape_flac")

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

    def test_dsd_push_rejects_string_false_capability(self):
        item = {"id": "dff-2", "path": "/music/test.dff", "is_dsd": True, "mime": "audio/x-dff", "duration": 1}
        device = {"control_url": "http://renderer/control", "capabilities": {"protocol_info": {"supports_dsd": "false"}}}
        Handler = type("Handler", (), {"server": type("Server", (), {"config": {}})()})
        result = soap_push(device, item, Handler(), lambda value: value, lambda _h: "http://host", lambda *_: "")
        self.assertFalse(result[0])

    def test_renderer_push_metadata_exposes_public_album_art(self):
        calls = []
        item = {
            "id": "track / 1",
            "title": "Track",
            "artist": "Artist",
            "album": "Album",
            "path": "/music/track.flac",
            "mime": "audio/flac",
            "duration": 180,
        }
        device = {
            "control_url": "http://renderer/control",
            "capabilities": {"actions": ["SetAVTransportURI", "Play"]},
        }

        class Handler:
            server = type("Server", (), {"config": {}})()

        def capture(_control, _service, action, args):
            calls.append((action, args))
            return b""

        with mock.patch("dlna.media_server.soap_request", side_effect=capture):
            result = soap_push(
                device,
                item,
                Handler(),
                lambda value: value,
                lambda _handler: "http://nas:5666",
                lambda *_args: "",
            )

        self.assertTrue(result[0])
        set_uri = next(args for action, args in calls if action == "SetAVTransportURI")
        self.assertIn("xmlns:dlna", set_uri)
        self.assertIn("upnp:albumArtURI", set_uri)
        self.assertNotIn("profileID", set_uri)
        # Progression belongs to the renderer monitor, so a push must never
        # preload another track with SetNextAVTransportURI.
        self.assertEqual(
            [action for action, _args in calls],
            ["Stop", "SetAVTransportURI", "Play"],
        )
        self.assertIn("http://nas:5666/upnp/cover/track%20%2F%201?size=160", set_uri)

    def test_renderer_metadata_matches_upmpdcli_compatible_didl_shape(self):
        metadata = renderer_track_metadata(
            {
                "title": "Track & One",
                "artist": "Artist",
                "album": "Album",
                "duration": 180,
            },
            "http://nas/media?a=1&b=2",
            "http://nas/cover?a=1&b=2",
            "http-get:*:audio/flac:*",
            1234,
        )

        self.assertTrue(metadata.startswith('<?xml version="1.0" encoding="utf-8"?>'))
        root = ET.fromstring(metadata)
        item = next(iter(root))
        self.assertEqual(item.attrib["searchable"], "0")
        self.assertEqual(
            [child.tag.rsplit("}", 1)[-1] for child in item],
            ["title", "class", "album", "res", "creator", "artist", "albumArtURI"],
        )
        resource = item[3]
        self.assertEqual(resource.attrib["protocolInfo"], "http-get:*:audio/flac:*")
        self.assertEqual(resource.attrib["duration"], "0:03:00")
        self.assertEqual(resource.attrib["size"], "1234")
        self.assertEqual(resource.text, "http://nas/media?a=1&b=2")
        self.assertEqual(item[-1].text, "http://nas/cover?a=1&b=2")

    def test_renderer_metadata_rejects_non_text_and_bounds_xml_fields(self):
        metadata = renderer_track_metadata(
            {"title": object(), "artist": "A\x00" + "B" * 5000, "album": object()},
            "http://nas/media",
            "http://nas/cover",
            "http-get:*:audio/flac:*",
        )
        root = ET.fromstring(metadata)
        item = next(iter(root))
        values = {child.tag.rsplit("}", 1)[-1]: child.text or "" for child in item}
        self.assertTrue(values["title"].endswith(" - "))
        self.assertEqual(values["album"], "")
        self.assertLessEqual(len(values["artist"]), 1024)
        self.assertNotIn("\x00", metadata)

    def test_renderer_metadata_ignores_nonfinite_duration_and_invalid_size(self):
        metadata = renderer_track_metadata(
            {"title": "Track", "duration": float("inf")},
            "http://nas/media",
            "http://nas/cover",
            "http-get:*:audio/flac:*",
            float("nan"),
        )
        root = ET.fromstring(metadata)
        resource = next(node for node in next(iter(root)) if node.tag.rsplit("}", 1)[-1] == "res")
        self.assertNotIn("duration", resource.attrib)
        self.assertNotIn("size", resource.attrib)


    def test_media_url_encodes_the_id_segment_so_the_route_can_read_it_back(self):
        item = {"id": "track / 1", "title": "Mix", "path": "/music/mix.flac"}

        url = upnp_media_url(object(), item, lambda value: value, lambda _h: "http://nas:5666")

        self.assertIn("/upnp/media/track%20%2F%201/", url)
        segment = urllib.parse.urlparse(url).path.split("/upnp/media/", 1)[1].split("/", 1)[0]
        self.assertEqual(urllib.parse.unquote(segment), item["id"])

    def test_media_descriptors_survive_queue_rows_without_a_source_path(self):
        # Queue and legacy payloads are not guaranteed to carry scanner fields.
        # A missing source must degrade to an unusable resource, never raise
        # inside the push path.
        item = {"id": 12, "title": "No path"}

        self.assertEqual(
            upnp_media_url(object(), item, lambda value: value, lambda _h: "http://nas"),
            "http://nas/upnp/media//",
        )
        self.assertEqual(upnp_resource_mime(item), "application/octet-stream")
        self.assertEqual(
            upnp_resource_size(item, {}, lambda *_args: (_ for _ in ()).throw(AssertionError("must not transcode"))),
            0,
        )


if __name__ == "__main__":
    unittest.main()
