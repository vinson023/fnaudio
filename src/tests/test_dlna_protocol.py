import math
import os
import pathlib
import re
import sys
import tempfile
import threading
import time
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, "app/server")

import dlna.network as dlna_network
import dlna.service as dlna_service
from dlna.renderer import DlnaRenderer
from dlna.next_queue import MAX_NEXT_QUEUE_ENTRIES
from dlna.service import AVTRANSPORT, CONNECTION_MANAGER, CONTENT_DIRECTORY, MAX_DLNA_ARGUMENT_CHARS, MAX_DLNA_SOAP_ARGUMENTS, MAX_EVENT_COUNTER, MAX_EVENT_SUBSCRIPTIONS, SEEK_UNITS, DlnaEventService, DlnaProtocolService, UpnpActionError, _duration, _mute, _next_event_sequence, _seconds, _seek_position, _volume, parse_soap_action
from playback.alsa_output import choose_dac_strategy, enrich_dac_device
from dlna.control_point import configure_local_renderer_identity, device_protocol_info, is_local_renderer, soap_text, upnp_control
from library_browse_rows import MAX_UNPAGED_BROWSE_ROWS
from library_query_spec import MAX_LIBRARY_OFFSET
from unittest import mock


class DlnaProtocolTests(unittest.TestCase):
    def test_transport_time_helpers_reject_nonfinite_and_invalid_components(self):
        self.assertEqual(_duration(float("nan")), "0:00:00")
        self.assertEqual(_duration(float("inf")), "0:00:00")
        self.assertEqual(_seconds("00:99:00"), 0.0)
        self.assertEqual(_seconds("1" * 65 + ":00:00"), 0.0)
        self.assertEqual(_seconds("01:02:03.5"), 3723.5)
        self.assertEqual(_duration(True), "0:00:00")
        self.assertEqual(_next_event_sequence(True), 1)

    def test_malformed_control_point_xml_is_a_safe_empty_value(self):
        self.assertEqual(soap_text(b"<Envelope><broken>", "State"), "")

    def test_seek_position_resolves_units_signs_and_bounds(self):
        cases = (
            (("ABS_TIME", "0:01:30", 60.0, 180.0), 90.0),
            (("REL_TIME", "0:00:45", 60.0, 180.0), 45.0),
            (("REL_TIME", "+0:00:30", 60.0, 180.0), 90.0),
            (("REL_TIME", "-0:00:30", 60.0, 180.0), 30.0),
            (("REL_TIME", "-0:01:00", 60.0, 180.0), 0.0),
            (("REL_TIME", "-0:02:00", 60.0, 180.0), 0.0),
            (("REL_TIME", "+0:10:00", 60.0, 180.0), 180.0),
            (("ABS_TIME", "10:00:00", 60.0, 180.0), 180.0),
            ((None, "0:00:45", 60.0, 180.0), 45.0),
            (("", "0:00:45", 60.0, 180.0), 45.0),
            (("  rel_time  ", "+0:00:01.500", 10.0, 180.0), 11.5),
            (("ABS_TIME", "0:02:00", 60.0, 0.0), 120.0),
            (("ABS_TIME", "0:02:00", 60.0, float("nan")), 120.0),
            (("ABS_TIME", "0:02:00", True, False), 120.0),
            (("REL_TIME", "+0:00:30", True, 180.0), 30.0),
            (("REL_TIME", "+0:00:30", float("inf"), 180.0), 30.0),
        )
        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                self.assertEqual(_seek_position(*arguments), expected)

    def test_seek_position_refuses_what_it_cannot_honour(self):
        for arguments in (
            ("TRACK_NR", "2", 60.0, 180.0),
            ("ABS_COUNT", "1000", 60.0, 180.0),
            ("REL_COUNT", "+1", 60.0, 180.0),
            ("FUTURE_UNIT", "0:00:30", 60.0, 180.0),
            ("ABS_TIME", "+0:00:30", 60.0, 180.0),
            ("ABS_TIME", None, 60.0, 180.0),
            ("ABS_TIME", "", 60.0, 180.0),
            ("ABS_TIME", "999:99:99", 60.0, 180.0),
            ("ABS_TIME", "0:01:30x", 60.0, 180.0),
            ("REL_TIME", "+", 60.0, 180.0),
            (123, "0:00:30", 60.0, 180.0),
            ("ABS_TIME", 45, 60.0, 180.0),
            ("ABS_TIME", ["0:00:45"], 60.0, 180.0),
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    _seek_position(*arguments)
        self.assertEqual(SEEK_UNITS, ("ABS_TIME", "REL_TIME"))

    def test_the_forgiving_numeric_readers_survive_every_unreadable_shape(self):
        # R68 counted this idiom three times inside service.py; measuring the whole
        # package finds six copies, and one of them carried a live gap: `float()` of a
        # magnitude a double cannot hold raises OverflowError instead of producing an
        # infinity, so `_finite(10 ** 400)` escaped as an exception while its two siblings
        # in this module and `renderer._safe_position` all caught it.  The readers keep
        # their differing contracts afterwards; they only share the type gate now.
        huge = 10 ** 400
        for value in (huge, -huge, float("inf"), float("-inf"), float("nan"), True, False,
                      "1e999", "not-a-number", "", None, [], {}, object()):
            with self.subTest(shape=type(value).__name__):
                self.assertIsInstance(dlna_service._finite(value), float)
                self.assertIsInstance(dlna_service._safe_count(value), int)
                self.assertIsInstance(dlna_service._saturating_increment(value), int)
        self.assertEqual(dlna_service._finite(huge), 0.0, "the same answer it gives for inf")
        self.assertEqual(dlna_service._finite(-huge), 0.0)
        self.assertEqual(dlna_service._finite(2.5), 2.5)
        self.assertEqual(dlna_service._finite(7), 7.0)
        self.assertEqual(dlna_service._safe_count(True), 0, "a boolean is not a count")
        self.assertEqual(dlna_service._safe_count("12"), 12)
        self.assertEqual(dlna_service._safe_count(huge), 0, "an unrepresentable count falls back")
        self.assertEqual(dlna_service._saturating_increment(True),
                         dlna_service._saturating_increment(0))
        self.assertEqual(dlna_service._saturating_increment(dlna_service.MAX_EVENT_COUNTER,
                                                           dlna_service.MAX_EVENT_COUNTER),
                         dlna_service.MAX_EVENT_COUNTER, "a doubled counter stays clamped")

    def test_the_descriptor_declares_exactly_the_seek_units_we_accept(self):
        # The SCPD is what a controller builds its fast-forward UI from (and what it
        # may validate before sending), so the advertised values have to be the ones
        # `_seek_position` honours.  They are read from SEEK_UNITS rather than being
        # written out again here, so this fails if the two ever drift apart.
        namespace = "{urn:schemas-upnp-org:service-1-0}"
        descriptor = ET.fromstring(dlna_service.scpd(AVTRANSPORT))
        declared = {
            state.find(namespace + "name").text: [value.text for value in state.iter(namespace + "allowedValue")]
            for state in descriptor.iter(namespace + "stateVariable")
        }
        self.assertEqual(declared["A_ARG_TYPE_SeekMode"], list(SEEK_UNITS))
        # Every other variable stays as loose as the handler: an allowedValueList we do
        # not enforce would be a promise controllers can hold us to.
        self.assertEqual(declared["A_ARG_TYPE_SeekTarget"], [])
        self.assertEqual(declared["TransportState"], [])

    def test_seek_control_carries_the_unit_and_never_rewinds_on_garbage(self):
        load = (
            '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            '<s:Body><u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            "<InstanceID>0</InstanceID><CurrentURI>http://198.51.100.20/test.mp3</CurrentURI>"
            "<CurrentURIMetaData></CurrentURIMetaData></u:SetAVTransportURI></s:Body></s:Envelope>"
        ).encode("utf-8")
        self.service.control("renderer", "avtransport", load)

        def seek_body(unit, target):
            arguments = "<InstanceID>0</InstanceID>"
            if unit is not None:
                arguments += "<Unit>%s</Unit>" % unit
            if target is not None:
                arguments += "<Target>%s</Target>" % target
            return (
                '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
                '<s:Body><u:Seek xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">%s</u:Seek>'
                "</s:Body></s:Envelope>" % arguments
            ).encode("utf-8")

        def status():
            return {"transport": {"state": "PLAYING"}, "position": {"rel_seconds": 60, "duration_seconds": 180}}

        with mock.patch.object(self.renderer, "_status", status), \
             mock.patch.object(self.renderer, "command", return_value={"ok": True, "queued": True}) as command:
            status_value, response = self.service.control("renderer", "avtransport", seek_body("REL_TIME", "+0:00:30"), '"x#Seek"')
            self.assertEqual(status_value, 200)
            self.assertIn(b"<u:SeekResponse", response)
            command.assert_called_once_with("seek", 90.0)

            for unit, target, message in (
                ("TRACK_NR", "2", b"unsupported Seek unit"),
                ("ABS_TIME", None, b"invalid Seek target"),
                ("ABS_TIME", "0:99:00", b"invalid Seek target"),
                ("ABS_TIME", "+0:00:30", b"signed target requires REL_TIME"),
            ):
                with self.subTest(unit=unit, target=target):
                    status_value, response = self.service.control("renderer", "avtransport", seek_body(unit, target), '"x#Seek"')
                    self.assertEqual(status_value, 500)
                    self.assertIn(message, response)
                    self.assertIn(b"s:Client", response)
            command.assert_called_once_with("seek", 90.0)

    @mock.patch("dlna.control_point.soap_request")
    def test_control_point_does_not_report_a_soap_fault_as_success(self, request):
        request.return_value = (
            b'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            b'<s:Body><s:Fault><faultstring>Transition denied</faultstring>'
            b'</s:Fault></s:Body></s:Envelope>'
        )
        ok, message = upnp_control({"control_url": "http://198.51.100.20:1400/control"}, "play")
        self.assertFalse(ok)
        self.assertEqual(message, "Transition denied")

    def test_mute_projection_rejects_non_text_values_without_coercion(self):
        for value in (True, 1, object(), ["true"], "x" * 33):
            with self.assertRaises(ValueError):
                _mute(value)
        self.assertFalse(_mute("FALSE"))
        self.assertTrue(_mute("true"))

    def test_volume_projection_rejects_fractional_values_without_truncation(self):
        for value in ("42.9", "NaN", "Infinity", True, object()):
            with self.assertRaises(ValueError):
                _volume(value)
        self.assertEqual(_volume(" 42 "), 42)
        self.assertEqual(_volume("101"), 100)

    def test_update_id_rejects_boolean_provider_values(self):
        service = DlnaProtocolService(
            lambda: "http://198.51.100.24:18080",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            lambda view, **query: [],
            lambda item: "audio/mpeg",
            system_update_id=lambda: True,
        )
        self.assertEqual(service._update_id(), 0)

    def setUp(self):
        self.loads = []
        self.controls = []
        self.renderer = DlnaRenderer(self._load, self._control, self._status)
        self.service = DlnaProtocolService(
            lambda: "http://198.51.100.24:18080",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            lambda view, **query: [],
            lambda item: item.get("mime", "audio/mpeg"),
            output_capabilities=lambda: {
                "pcm_rates": [44100, 96000, 192000],
                "pcm_max_bits": 24,
                "dsd_native": True,
            },
        )

    def tearDown(self):
        configure_local_renderer_identity()

    def test_discovery_excludes_only_the_exact_local_fnaudio_renderer(self):
        local = "http://198.51.100.24:53199/dlna/renderer/description.xml"
        remote = "http://198.51.100.25:53199/dlna/renderer/description.xml"
        configure_local_renderer_identity(local, "uuid:local-renderer")

        self.assertTrue(is_local_renderer({"location": local}, ["uuid:local-renderer"]))
        self.assertFalse(is_local_renderer(
            {"location": remote, "usn": "uuid:remote-renderer::urn:schemas-upnp-org:device:MediaRenderer:1"},
            ["uuid:remote-renderer"],
        ))

    def test_discovery_identity_projection_rejects_hostile_values(self):
        class Exploding:
            def __str__(self):
                raise AssertionError("discovery identities must not stringify arbitrary values")

        configure_local_renderer_identity(Exploding(), Exploding())
        self.assertFalse(is_local_renderer({"location": Exploding(), "usn": Exploding()}, [Exploding()]))
        self.assertFalse(is_local_renderer(Exploding(), Exploding()))

    def _load(self, uri, position):
        self.loads.append((uri, position))
        return {"ok": True}

    def _control(self, action, position):
        self.controls.append((action, position))
        return {"ok": True}

    @staticmethod
    def _status():
        return {"transport": {"state": "STOPPED"}, "position": {"rel_seconds": 0, "duration_seconds": 0}}

    def test_renderer_description_and_profiles(self):
        description = self.service.description("renderer").decode("utf-8")
        self.assertIn("fnAudio Renderer", description)
        self.assertIn("MediaRenderer:1", description)
        profiles = self.service.protocol_info("renderer")
        self.assertIn("http-get:*:audio/L24;rate=192000;channels=2:*", profiles)
        self.assertIn("http-get:*:audio/x-dsf:*", profiles)

    def test_renderer_description_uses_configured_friendly_name_and_xml_escapes_it(self):
        service = DlnaProtocolService(
            lambda: "http://198.51.100.24:18080",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            lambda view, **query: [],
            lambda item: "audio/mpeg",
            renderer_name='客厅 <DAC> & "主机"',
        )
        root = ET.fromstring(service.description("renderer"))
        friendly_name = root.find("{urn:schemas-upnp-org:device-1-0}device/{urn:schemas-upnp-org:device-1-0}friendlyName")
        self.assertEqual(friendly_name.text, '客厅 <DAC> & "主机"')

    def test_renderer_name_update_reports_only_changes_and_leaves_server_name_alone(self):
        self.assertTrue(self.service.set_renderer_name("客厅播放器"))
        self.assertFalse(self.service.set_renderer_name("客厅播放器"))

        renderer_root = ET.fromstring(self.service.description("renderer"))
        server_root = ET.fromstring(self.service.description("server"))
        renderer_name = renderer_root.find("{urn:schemas-upnp-org:device-1-0}device/{urn:schemas-upnp-org:device-1-0}friendlyName")
        server_name = server_root.find("{urn:schemas-upnp-org:device-1-0}device/{urn:schemas-upnp-org:device-1-0}friendlyName")
        self.assertEqual(renderer_name.text, "客厅播放器")
        self.assertEqual(server_name.text, "fnAudio Music Library")

    def test_renderer_does_not_advertise_a_rate_the_driver_never_reported(self):
        # End to end on purpose. A driver stream file that lists formats but no
        # rates used to be turned into a fabricated single 192 kHz capability by
        # enrich_dac_device(), this service then published it as an LPCM profile
        # a controller may push audio at, and choose_dac_strategy() then planned
        # a resample to that same invented rate. Only the proc root is mocked.
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "card0"))
            with open(os.path.join(root, "card0", "stream0"), "w", encoding="utf-8") as handle:
                handle.write("Playback: #0" + chr(10) + chr(9) + "Formats: S16_LE S24_LE" + chr(10))
            with mock.patch.dict(os.environ, {"FNAUDIO_ASOUND_ROOT": root}):
                device = enrich_dac_device({"name": "Obscure USB DAC", "alsa_id": "hw:0,0"})
        caps = device["caps"]
        self.assertEqual(caps["pcm_rates"], [])
        self.assertEqual(caps["pcm_max_rate"], 0)

        service = DlnaProtocolService(
            lambda: "http://198.51.100.24:18080",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            lambda view, **query: [],
            lambda item: item.get("mime", "audio/mpeg"),
            output_capabilities=lambda: caps,
        )
        profiles = service.protocol_info("renderer")
        self.assertNotIn("audio/L16;rate=", profiles)
        self.assertNotIn("audio/L24;rate=", profiles)
        # Plain PCM stays welcome; only the invented rate claim is gone.
        self.assertIn("http-get:*:audio/wav:*", profiles)
        # And the same caps no longer plan a resample of a native 44.1 kHz file.
        self.assertFalse(choose_dac_strategy({"sample_rate": 44100, "bit_depth": 16}, device)["needs_transcode"])

    def test_event_service_limits_isolate_invalid_configuration(self):
        invalid = DlnaEventService(max_workers=object(), max_pending=True)
        self.assertEqual(invalid._max_workers, 4)
        self.assertEqual(invalid._max_pending, 64)
        bounded = DlnaEventService(max_workers=999, max_pending=-5)
        self.assertEqual(bounded._max_workers, 8)
        self.assertEqual(bounded._max_pending, 1)

    def test_event_pressure_counters_saturate(self):
        service = DlnaEventService()
        service._accepted_notifications = MAX_EVENT_COUNTER
        service._dropped_notifications = MAX_EVENT_COUNTER
        service._peak_notifications = MAX_EVENT_COUNTER
        snapshot = service.snapshot()
        self.assertEqual(snapshot["accepted"], MAX_EVENT_COUNTER)
        self.assertEqual(snapshot["dropped"], MAX_EVENT_COUNTER)
        self.assertEqual(snapshot["peak_pending"], MAX_EVENT_COUNTER)

    def test_event_sequence_wraps_after_safety_ceiling(self):
        self.assertEqual(_next_event_sequence(MAX_EVENT_COUNTER), 0)
        self.assertEqual(_next_event_sequence(MAX_EVENT_COUNTER - 1), MAX_EVENT_COUNTER)

    def test_connection_manager_protocol_info(self):
        status, body = self.service.control(
            "renderer",
            "connection",
            b'<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><u:GetProtocolInfo xmlns:u="urn:schemas-upnp-org:service:ConnectionManager:1"/></s:Body></s:Envelope>',
            '"urn:schemas-upnp-org:service:ConnectionManager:1#GetProtocolInfo"',
        )
        self.assertEqual(status, 200)
        self.assertIn(CONNECTION_MANAGER.encode("utf-8"), body)
        self.assertIn(b"audio/L16;rate=96000", body)

    def test_didl_metadata_is_exposed_to_renderer_state(self):
        metadata = (
            '<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
            '<item><dc:title>Example Track</dc:title><upnp:artist>Example Artist</upnp:artist>'
            '<upnp:albumArtURI>http://example.test/cover.jpg</upnp:albumArtURI></item></DIDL-Lite>'
        )
        self.renderer.set_uri("http://example.test/track.flac", metadata)
        state = self.renderer.snapshot()
        self.assertEqual(state["title"], "Example Track")
        self.assertEqual(state["artist"], "Example Artist")
        self.assertEqual(state["art_url"], "http://example.test/cover.jpg")

    def test_didl_item_rejects_non_text_and_bounds_xml_fields(self):
        item = {"id": object(), "title": object(), "artist": "A\x00" + "B" * 5000, "album": object(), "format": object()}
        xml = (
            '<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" '
            'xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/">'
            + self.service._didl_item(item)
            + "</DIDL-Lite>"
        )
        root = ET.fromstring(xml)
        row = next(iter(root))
        values = {child.tag.rsplit("}", 1)[-1]: child.text or "" for child in row}
        self.assertEqual(values["title"], "Unknown title")
        self.assertEqual(values["album"], "")
        self.assertLessEqual(len(values["artist"]), 1024)
        self.assertNotIn("\x00", xml)

    def test_container_browse_rejects_non_text_and_bounds_group_fields(self):
        service = DlnaProtocolService(
            lambda: "http://198.51.100.24:18080",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            lambda view, **query: [{"name": object()}, {"name": "A\x00" + "B" * 5000}],
            lambda item: item.get("mime", "audio/mpeg"),
        )
        result = service._browse({"ObjectID": "albums", "BrowseFlag": "BrowseDirectChildren", "Filter": "*"})
        root = ET.fromstring(result["Result"])
        rows = list(root)
        self.assertEqual(len(rows), 2)
        self.assertLessEqual(len(rows[1][0].text or ""), 1024)
        self.assertNotIn("\x00", result["Result"])

    def test_browse_arguments_are_bounded_before_filter_and_sort_parsing(self):
        oversized_filter = "dc:title," + "x" * 20000
        result = self.service._browse({
            "ObjectID": "0",
            "BrowseFlag": "BrowseDirectChildren",
            "Filter": oversized_filter,
            "SortCriteria": "+" + "dc:title" + "\x00" * 20000,
        })
        self.assertIn("DIDL-Lite", result["Result"])
        self.assertNotIn("\x00", result["Result"])

    def test_soap_parser_rejects_excessive_argument_count_and_text_before_dispatch(self):
        arguments = "".join("<Arg%s>x</Arg%s>" % (index, index) for index in range(MAX_DLNA_SOAP_ARGUMENTS + 1))
        body = (
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
            '<u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">%s</u:Play>'
            "</s:Body></s:Envelope>" % arguments
        ).encode("utf-8")
        status, response = self.service.control("renderer", "avtransport", body)
        self.assertEqual(status, 500)
        self.assertIn(b"too many SOAP arguments", response)

        oversized = "x" * (MAX_DLNA_ARGUMENT_CHARS + 1)
        body = (
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
            '<u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><Speed>%s</Speed></u:Play>'
            "</s:Body></s:Envelope>" % oversized
        ).encode("utf-8")
        status, response = self.service.control("renderer", "avtransport", body)
        self.assertEqual(status, 500)
        self.assertIn(b"invalid SOAP argument", response)

    def test_soap_parser_reads_the_action_beside_a_header_block(self):
        envelope = (
            "<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" "
            'xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">%s'
            "<s:Body><u:Play><u:InstanceID>0</u:InstanceID><u:Speed>1</u:Speed></u:Play></s:Body>"
            "</s:Envelope>"
        )
        for header in ("<s:Header><SessionID>00000000</SessionID></s:Header>", "<s:Header/>", ""):
            action, arguments = parse_soap_action(envelope % header)
            self.assertEqual(action, "Play")
            self.assertEqual(arguments, {"InstanceID": "0", "Speed": "1"})

    def test_soap_parser_still_accepts_an_unwrapped_action_element(self):
        action, arguments = parse_soap_action(
            b'<u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            b"<u:InstanceID>0</u:InstanceID></u:SetAVTransportURI>"
        )
        self.assertEqual(action, "SetAVTransportURI")
        self.assertEqual(arguments, {"InstanceID": "0"})

    def test_set_uri_control_survives_a_controller_soap_header(self):
        # Synology, Windows Media Player, and many Denon/Sony controllers send
        # a SOAP Header ahead of the Body. If the header wins, the transport
        # action faults and the renderer cannot be driven at all.
        body = (
            '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            "<s:Header><ConnectionID>0</ConnectionID></s:Header>"
            '<s:Body><u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            "<InstanceID>0</InstanceID><CurrentURI>http://198.51.100.20/test.flac</CurrentURI>"
            "<CurrentURIMetaData></CurrentURIMetaData></u:SetAVTransportURI></s:Body></s:Envelope>"
        ).encode("utf-8")

        status, response = self.service.control("renderer", "avtransport", body)

        self.assertEqual(status, 200)
        self.assertIn(b"SetAVTransportURIResponse", response)
        self.assertEqual(self.renderer.snapshot()["uri"], "http://198.51.100.20/test.flac")

    def test_group_browse_does_not_list_every_group_to_validate_one_name(self):
        probes = []

        def library_groups(view, **query):
            raise AssertionError("validating one group must not read the whole group table")

        def library_page(params):
            probes.append(dict(params))
            return {"items": [], "count": 1}

        service = DlnaProtocolService(
            lambda: "http://198.51.100.24:18080",
            self.renderer,
            library_page,
            library_groups,
            lambda item: "audio/mpeg",
        )

        xml = service._metadata_for_object("albums:Kind%20of%20Blue", {"*"})

        self.assertIn("Kind of Blue", xml)
        self.assertEqual(probes[0]["view"], "albums")
        self.assertEqual(probes[0]["group"], "Kind of Blue")
        self.assertEqual(probes[0]["limit"], 1)

    def test_unknown_group_is_rejected_without_listing_every_group(self):
        service = DlnaProtocolService(
            lambda: "http://198.51.100.24:18080",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            lambda view, **query: [{"name": "Kind of Blue"}],
            lambda item: "audio/mpeg",
        )

        with self.assertRaises(UpnpActionError) as caught:
            service._metadata_for_object("albums:Not%20An%20Album", {"*"})

        self.assertEqual(caught.exception.code, 701)

    def test_empty_group_label_is_rejected_before_the_page_probe(self):
        # An empty group reads as "no group filter" to the page query, so it
        # must be refused instead of resolving the whole library under a bogus
        # container id.
        calls = []
        service = DlnaProtocolService(
            lambda: "http://198.51.100.24:18080",
            self.renderer,
            lambda params: calls.append(dict(params)) or {"items": [], "count": 9},
            lambda view, **query: [{"name": "Kind of Blue"}],
            lambda item: "audio/mpeg",
        )

        with self.assertRaises(UpnpActionError) as caught:
            service._metadata_for_object("albums:", {"*"})

        self.assertEqual(caught.exception.code, 701)
        self.assertEqual(calls, [])

    def test_group_browse_reads_only_the_requested_group_page(self):
        reads = []

        def library_groups(view, **query):
            reads.append((view, dict(query)))
            return {"groups": [{"name": "Aqualung"}, {"name": "Kind of Blue"}], "count": 4120, "paged": True}

        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            library_groups,
            lambda item: "audio/mpeg",
        )
        result = service._browse({
            "ObjectID": "artists",
            "BrowseFlag": "BrowseDirectChildren",
            "StartingIndex": "30",
            "RequestedCount": "2",
        })
        self.assertEqual(reads, [("artists", {"limit": 2, "offset": 30, "sort_dir": "asc"})])
        self.assertEqual(result["TotalMatches"], "4120")
        self.assertEqual(result["NumberReturned"], "2")
        self.assertEqual([row[0].text for row in ET.fromstring(result["Result"])], ["Aqualung", "Kind of Blue"])

        service._browse({
            "ObjectID": "artists",
            "BrowseFlag": "BrowseDirectChildren",
            "RequestedCount": "25",
            "SortCriteria": "-dc:title",
        })
        # The direction is part of the read now, so the query that owns the
        # ordering has to receive it.
        self.assertEqual(reads[1], ("artists", {"limit": 25, "offset": 0, "sort_dir": "desc"}))

    def test_group_browse_total_is_not_capped_by_materialization(self):
        # The unbounded read has to materialize the whole group table before it
        # slices the page, and that materialization is capped. Past the cap the
        # container reported a total equal to the cap, so every later group was
        # unreachable for the controller. A bounded read reports the provider's
        # own count and reaches the window behind the cap.
        hidden = MAX_UNPAGED_BROWSE_ROWS + 10
        names = ["artist-%05d" % index for index in range(MAX_UNPAGED_BROWSE_ROWS + 500)]

        def library_groups(view, **query):
            if "limit" not in query:
                return [{"name": name} for name in names]
            start = query["offset"]
            return {
                "groups": [{"name": name} for name in names[start:start + query["limit"]]],
                "count": len(names),
                "paged": True,
            }

        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            library_groups,
            lambda item: "audio/mpeg",
        )
        result = service._browse({
            "ObjectID": "genres",
            "BrowseFlag": "BrowseDirectChildren",
            "StartingIndex": str(hidden),
            "RequestedCount": "3",
        })
        self.assertEqual(result["TotalMatches"], str(len(names)))
        self.assertEqual(result["NumberReturned"], "3")
        self.assertEqual([row[0].text for row in ET.fromstring(result["Result"])], names[hidden:hidden + 3])

    def test_group_browse_from_an_unpaged_provider_stops_at_the_materialization_cap(self):
        # A provider that ignores the page still owns the old shape, cap and all,
        # so this is the behaviour the bounded read exists to replace - and the
        # proof that the cap above really comes from materializing the table.
        rows = [{"name": "artist-%05d" % index} for index in range(MAX_UNPAGED_BROWSE_ROWS + 10)]

        def library_groups(view, **query):
            return rows

        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            library_groups,
            lambda item: "audio/mpeg",
        )
        result = service._browse({"ObjectID": "artists", "BrowseFlag": "BrowseDirectChildren"})
        self.assertEqual(result["TotalMatches"], str(MAX_UNPAGED_BROWSE_ROWS))
        self.assertEqual(result["NumberReturned"], "500")

    def test_group_browse_keeps_the_provider_page_order(self):
        # Sorting a page in Python reorders it against the query that produced
        # it, so the provider order is the one that stays consistent page to
        # page. A casefold sort here would swap these two names.
        def library_groups(view, **query):
            return {"groups": [{"name": "beta"}, {"name": "Alpha"}], "count": 2, "paged": True}

        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            library_groups,
            lambda item: "audio/mpeg",
        )
        result = service._browse({"ObjectID": "albums", "BrowseFlag": "BrowseDirectChildren"})
        self.assertEqual([row[0].text for row in ET.fromstring(result["Result"])], ["beta", "Alpha"])
        self.assertEqual(result["TotalMatches"], "2")
        self.assertEqual(result["NumberReturned"], "2")

    def test_albums_sorted_by_artist_still_read_every_group(self):
        # Listing albums by artist sorts on a column the group query does not
        # order by, so it has to keep reading the whole table. Forwarding the
        # page here would reorder the container against its own SortCriteria.
        reads = []

        def library_groups(view, **query):
            reads.append(dict(query))
            return [
                {"name": "Zeta", "artist": "Adele"},
                {"name": "Alpha", "artist": "Bee Gee"},
            ]

        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            library_groups,
            lambda item: "audio/mpeg",
        )
        result = service._browse({
            "ObjectID": "albums",
            "BrowseFlag": "BrowseDirectChildren",
            "SortCriteria": "+upnp:artist",
        })
        self.assertEqual(reads, [{}])
        self.assertEqual([row[0].text for row in ET.fromstring(result["Result"])], ["Zeta", "Alpha"])
        self.assertEqual(result["TotalMatches"], "2")

    def test_group_browse_past_the_provider_window_stays_unbounded(self):
        # The library clamps a starting index into its own window, so asking the
        # provider for a page beyond that window would answer a different request
        # than the controller made. That read keeps the whole-table path.
        reads = []

        def library_groups(view, **query):
            reads.append(dict(query))
            if "limit" in query:
                return {"groups": [{"name": "Wrong window"}], "count": 9, "paged": True}
            return [{"name": "Only group"}]

        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            library_groups,
            lambda item: "audio/mpeg",
        )
        result = service._browse({
            "ObjectID": "genres",
            "BrowseFlag": "BrowseDirectChildren",
            "StartingIndex": str(MAX_LIBRARY_OFFSET + 1),
            "RequestedCount": "2",
        })
        self.assertEqual(reads, [{}])
        self.assertEqual(result["TotalMatches"], "1")
        self.assertEqual(result["NumberReturned"], "0")
        self.assertNotIn("Wrong window", result["Result"])

    def test_the_provider_page_splitter_only_trusts_a_stated_total(self):
        rows = [{"name": "A"}]
        self.assertEqual(dlna_service._provider_browse_page({"groups": rows, "count": 7}, "groups"), (rows, 7))
        self.assertEqual(dlna_service._provider_browse_page({"groups": rows, "count": "7"}, "groups"), (rows, 7))
        self.assertEqual(dlna_service._provider_browse_page({"groups": [], "count": 0}, "groups"), ([], 0))
        for unusable in (rows, {"groups": rows}, {"groups": rows, "count": -3}, {"groups": rows, "count": True}, {"count": 5}, None):
            self.assertEqual(dlna_service._provider_browse_page(unusable, "groups"), (unusable, None))

    def test_folder_browse_reads_only_the_requested_subfolder_page(self):
        folder_reads = []
        track_reads = []

        def library_folders(parent, root, **query):
            folder_reads.append((parent, root, dict(query)))
            return {
                "folders": [
                    {"name": "Live", "path": "/music/Live"},
                    {"name": "Studio", "path": "/music/Studio"},
                ],
                "count": 8100,
                "paged": True,
            }

        def library_page(params):
            track_reads.append(dict(params))
            return {"items": [{"id": "track-1", "title": "Song"}], "count": 40}

        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            library_page,
            lambda view, **query: [],
            lambda item: "audio/mpeg",
            library_roots=lambda: [{"root": "/music", "name": "Music"}],
            library_folders=library_folders,
        )
        result = service._browse({
            "ObjectID": "folders-root:%2Fmusic",
            "BrowseFlag": "BrowseDirectChildren",
            "StartingIndex": "4",
            "RequestedCount": "2",
        })
        self.assertEqual(folder_reads, [("", "/music", {"limit": 2, "offset": 4, "sort_dir": "asc"})])
        self.assertEqual(len(track_reads), 1)
        self.assertEqual((track_reads[0]["limit"], track_reads[0]["offset"]), (1, 0))
        # The folder rows already fill the window, so the track probe only buys
        # this container its total; a total that stopped at the folder list made
        # controllers stop paging before the first track.
        self.assertNotIn("<item ", result["Result"])
        self.assertEqual(result["NumberReturned"], "2")
        self.assertEqual(result["TotalMatches"], "8140")
        self.assertEqual([row[0].text for row in ET.fromstring(result["Result"])], ["Live", "Studio"])

    def test_folder_browse_starts_tracks_after_the_subfolder_total(self):
        track_reads = []

        def library_folders(parent, root, **query):
            return {"folders": [{"name": "Live", "path": "/music/Live"}], "count": 3, "paged": True}

        def library_page(params):
            track_reads.append(dict(params))
            return {"items": [{"id": "track-9", "title": "Encore"}], "count": 9}

        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            library_page,
            lambda view, **query: [],
            lambda item: "audio/mpeg",
            library_roots=lambda: [{"root": "/music", "name": "Music"}],
            library_folders=library_folders,
        )
        result = service._browse({
            "ObjectID": "folders-root:%2Fmusic",
            "BrowseFlag": "BrowseDirectChildren",
            "StartingIndex": "4",
            "RequestedCount": "2",
        })
        self.assertEqual(len(track_reads), 1)
        self.assertEqual((track_reads[0]["limit"], track_reads[0]["offset"]), (1, 1))
        self.assertIn("<item ", result["Result"])
        self.assertEqual(result["NumberReturned"], "2")
        self.assertEqual(result["TotalMatches"], "12")

    def test_unpaged_folder_provider_keeps_the_whole_table_path(self):
        def library_folders(parent, root, **query):
            return [
                {"name": "b", "path": "/music/b"},
                {"name": "a", "path": "/music/a"},
                {"name": "c", "path": "/music/c"},
            ]

        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            lambda view, **query: [],
            lambda item: "audio/mpeg",
            library_roots=lambda: [{"root": "/music", "name": "Music"}],
            library_folders=library_folders,
        )
        result = service._browse({
            "ObjectID": "folders-root:%2Fmusic",
            "BrowseFlag": "BrowseDirectChildren",
            "RequestedCount": "2",
        })
        self.assertEqual([row[0].text for row in ET.fromstring(result["Result"])], ["a", "b"])
        self.assertEqual(result["TotalMatches"], "3")

    def test_folder_root_browse_has_no_page_api_to_use(self):
        # The root list is one row per configured library and its query has no
        # paging statement, so this container keeps the whole-table read.
        reads = []

        def library_roots(*args, **query):
            reads.append((args, dict(query)))
            return [{"root": "/a", "name": "A"}, {"root": "/b", "name": "B"}]

        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            lambda view, **query: [],
            lambda item: "audio/mpeg",
            library_roots=library_roots,
            library_folders=lambda parent, root, **query: [],
        )
        result = service._browse({"ObjectID": "folders", "BrowseFlag": "BrowseDirectChildren", "RequestedCount": "1"})
        self.assertEqual(reads, [((), {})])
        self.assertEqual(result["TotalMatches"], "2")
        self.assertEqual(result["NumberReturned"], "1")

    def test_folder_metadata_still_scans_its_siblings_unbounded(self):
        # Resolving one folder path reads its sibling list because the metadata
        # lookup has no by-path query yet. Recorded here so the browse paging
        # above is not mistaken for having closed it.
        reads = []

        def library_folders(parent, root, **query):
            reads.append((parent, root, dict(query)))
            return [{"name": "Live", "path": "/music/Live"}]

        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            lambda params: {"items": [], "count": 0},
            lambda view, **query: [],
            lambda item: "audio/mpeg",
            library_roots=lambda: [{"root": "/music", "name": "Music"}],
            library_folders=library_folders,
        )
        xml = service._metadata_for_object("folder:%2Fmusic:%2Fmusic%2FLive", {"*"})
        self.assertIn(">Live</dc:title>", xml)
        self.assertEqual(reads, [("/music", "/music", {})])

    def test_dlna_browse_wiring_forwards_the_page_to_the_library_queries(self):
        source = (pathlib.Path(__file__).resolve().parents[2] / "src" / "app" / "server" / "server.py").read_text(encoding="utf-8")
        wiring = source[source.index("def initialize_dlna_services(server):") : source.index("    DLNA_PROTOCOL = DlnaProtocolService(")]
        groups = wiring[wiring.index("    def groups(") : wiring.index("    def roots():")]
        roots = wiring[wiring.index("    def roots():") : wiring.index("    def folders(")]
        folders = wiring[wiring.index("    def folders(") : wiring.index("    def output_capabilities():")]
        self.assertIn('def groups(view, limit=None, offset=0, sort_dir="asc"):', groups)
        self.assertIn("query_library_groups(server.config, view, limit=limit, offset=offset, sort_dir=sort_dir)", groups)
        self.assertIn('def folders(parent, root, limit=None, offset=0, sort_dir="asc"):', folders)
        self.assertIn("query_library_folders(server.config, parent, root, sort_dir=sort_dir, limit=limit, offset=offset)", folders)
        self.assertNotIn("limit", roots)
        # Each forwarded keyword has to exist on the real query: a name the
        # provider does not accept would make every container fall back to the
        # whole-table read at runtime without failing a single double-based test.
        import inspect
        import library

        for body, provider in ((groups, library.query_library_groups), (folders, library.query_library_folders)):
            keywords = re.findall(r"(\w+)=", body.strip().splitlines()[-1])
            accepted = inspect.signature(provider).parameters
            self.assertEqual(set(keywords), {"limit", "offset", "sort_dir"})
            for keyword in keywords:
                self.assertIn(keyword, accepted)

    def test_event_subscription_limit_reported_is_the_limit_enforced(self):
        events = DlnaEventService(max_workers=1, max_pending=4)
        events._callback_url = lambda value: value
        for index in range(MAX_EVENT_SUBSCRIPTIONS):
            events.subscribe("renderer", "avtransport", "http://198.51.100.20/%d" % index, "", "Second-60")

        self.assertEqual(events.snapshot()["subscription_limit"], MAX_EVENT_SUBSCRIPTIONS)
        self.assertEqual(len(events._subscriptions), MAX_EVENT_SUBSCRIPTIONS)
        with self.assertRaises(ValueError):
            events.subscribe("renderer", "avtransport", "http://198.51.100.20/overflow", "", "Second-60")
        events.shutdown(wait=False)

    def test_mute_and_unmute_are_applied_to_the_backend_volume(self):
        self.renderer.set_volume(63)
        self.controls.clear()

        self.assertTrue(self.renderer.set_mute(True)["ok"])
        self.assertTrue(self.renderer.snapshot()["muted"])
        self.assertEqual(self.controls, [("volume", 0.0)])

        self.controls.clear()
        self.renderer.set_volume(41)
        self.assertEqual(self.controls, [])
        self.assertEqual(self.renderer.snapshot()["volume"], 41)

        self.assertTrue(self.renderer.set_mute(False)["ok"])
        self.assertEqual(self.controls, [("volume", 41.0)])
        self.assertFalse(self.renderer.snapshot()["muted"])

    def test_volume_backend_io_waits_for_an_inflight_transport_operation(self):
        started = threading.Event()
        release = threading.Event()
        controls = []

        def load(uri, position):
            started.set()
            self.assertTrue(release.wait(1))
            return {"ok": True}

        def control(action, position):
            controls.append((action, position))
            return {"ok": True}

        renderer = DlnaRenderer(load, control, self._status)
        renderer.set_uri("http://example.test/blocked.flac")
        renderer.play()
        self.assertTrue(started.wait(1))

        volume_done = threading.Event()

        def set_volume():
            renderer.set_volume(37)
            volume_done.set()

        volume_thread = threading.Thread(target=set_volume)
        volume_thread.start()
        self.assertFalse(volume_done.wait(0.05))
        self.assertEqual(controls, [])
        release.set()
        self.assertTrue(volume_done.wait(1))
        volume_thread.join(1)
        self.assertEqual(controls, [("volume", 37.0)])

    def test_renderer_rejects_non_finite_seek_and_volume_values(self):
        self.assertFalse(self.renderer.command("seek", float("nan"))["ok"])
        self.assertFalse(self.renderer.command("seek", float("inf"))["ok"])
        self.assertFalse(self.renderer.set_volume(float("nan"))["ok"])
        self.assertFalse(self.renderer.set_volume(float("inf"))["ok"])
        self.assertEqual(self.renderer.snapshot()["position"], 0.0)
        self.assertEqual(self.renderer.snapshot()["volume"], 100)

    def test_renderer_rejects_fractional_volume_without_truncation(self):
        result = self.renderer.set_volume(42.9)
        self.assertFalse(result["ok"])
        self.assertEqual(self.renderer.snapshot()["volume"], 100)
        self.assertEqual(self.controls, [])

    def test_renderer_rejects_non_text_action_without_coercion(self):
        class HostileAction:
            def __str__(self):
                raise AssertionError("action must not be coerced")

        result = self.renderer.command(HostileAction())
        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "invalid action")
        self.assertEqual(self.controls, [])

    def test_renderer_rejects_unsupported_actions_without_backend_admission(self):
        result = self.renderer.command("dance")
        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "unsupported action")
        self.assertEqual(self.controls, [])

    def test_renderer_requires_a_seek_position(self):
        result = self.renderer.command("seek")
        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "invalid seek position")
        self.assertEqual(self.controls, [])

    def test_renderer_rejects_seek_positions_beyond_protocol_bound(self):
        result = self.renderer.command("seek", 24 * 60 * 60 + 1)
        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "invalid seek position")
        self.assertEqual(self.controls, [])

    def test_renderer_requires_explicit_backend_success_for_volume_and_mute(self):
        self.renderer._control = lambda _action, _position: {"ok": "false"}
        result = self.renderer.set_volume(42)
        self.assertFalse(result["ok"])
        self.assertEqual(self.renderer.snapshot()["volume"], 100)

        result = self.renderer.set_mute(True)
        self.assertFalse(result["ok"])
        self.assertFalse(self.renderer.snapshot()["muted"])

        self.assertFalse(self.renderer.set_mute("true")["ok"])

    def test_volume_and_mute_backend_exceptions_become_structured_failures(self):
        def broken_control(_action, _position):
            raise OSError("mixer unavailable")

        self.renderer._control = broken_control
        volume = self.renderer.set_volume(42)
        self.assertFalse(volume["ok"])
        self.assertEqual(volume["message"], "mixer unavailable")
        mute = self.renderer.set_mute(True)
        self.assertFalse(mute["ok"])
        self.assertEqual(mute["message"], "mixer unavailable")
        self.assertFalse(self.renderer.snapshot()["muted"])

    def test_rendering_control_rejects_non_finite_volume_and_parses_uppercase_false(self):
        def request(action, argument, value):
            return (
                '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
                '<s:Body><u:%s xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
                '<InstanceID>0</InstanceID><Channel>Master</Channel><%s>%s</%s>'
                '</u:%s></s:Body></s:Envelope>' % (action, argument, value, argument, action)
            ).encode("utf-8")

        for value in ("NaN", "Infinity", "-Infinity"):
            status, response = self.service.control("renderer", "rendering", request("SetVolume", "DesiredVolume", value))
            self.assertEqual(status, 500)
            self.assertIn(b"invalid volume", response)

        self.renderer.set_mute(True)
        status, _ = self.service.control("renderer", "rendering", request("SetMute", "DesiredMute", "FALSE"))
        self.assertEqual(status, 200)
        self.assertFalse(self.renderer.snapshot()["muted"])

    def test_avtransport_set_uri_returns_standard_soap_response(self):
        body = (
            '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            '<s:Body><u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID><CurrentURI>http://198.51.100.20/test.mp3</CurrentURI>'
            '<CurrentURIMetaData></CurrentURIMetaData></u:SetAVTransportURI></s:Body></s:Envelope>'
        ).encode("utf-8")
        status, response = self.service.control("renderer", "avtransport", body, '"%s#SetAVTransportURI"' % AVTRANSPORT)
        self.assertEqual(status, 200)
        self.assertIn(b"SetAVTransportURIResponse", response)
        self.assertEqual(self.renderer.snapshot()["uri"], "http://198.51.100.20/test.mp3")

    def test_utf16_control_body_cannot_smuggle_entity_declarations(self):
        # expat decodes UTF-16 from a BOM or from NUL padding, so a peer that
        # encoded the same DTD in UTF-16 used to walk past the byte-level
        # declaration guard and have the cascade expanded inside the parser.
        parts = ['<!ENTITY e0 "xxxxxxxxxx">']
        for level in range(1, 6):
            parts.append('<!ENTITY e%d "%s">' % (level, ("&e%d;" % (level - 1)) * 3))
        bomb = (
            '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE bomb [%s]>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
            '<u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            "<InstanceID>&e5;</InstanceID></u:SetAVTransportURI></s:Body></s:Envelope>" % "".join(parts)
        )
        for codec in ("utf-16", "utf-16-le", "utf-16-be"):
            with self.subTest(codec=codec):
                status, response = self.service.control("renderer", "avtransport", bomb.encode(codec))
                self.assertEqual(status, 500)
                self.assertIn(b"declarations are not allowed", response)
        self.assertEqual(self.loads, [])
        self.assertEqual(self.renderer.snapshot()["uri"], "")

    def test_utf16_control_body_still_reaches_the_renderer(self):
        # The fix must close the bypass, not ban the encoding: some UPnP peers do
        # send UTF-16 envelopes, and refusing them would break real playback.
        header = '"%s#SetAVTransportURI"' % AVTRANSPORT
        for codec, declared in (("utf-16", "UTF-16"), ("utf-16-le", "UTF-16LE"), ("utf-16-be", "UTF-16BE")):
            with self.subTest(codec=codec):
                uri = "http://198.51.100.20/%s.mp3" % codec
                body = (
                    '<?xml version="1.0" encoding="%s"?>'
                    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
                    '<u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
                    "<InstanceID>0</InstanceID><CurrentURI>%s</CurrentURI>"
                    "<CurrentURIMetaData></CurrentURIMetaData></u:SetAVTransportURI></s:Body></s:Envelope>"
                    % (declared, uri)
                )
                status, response = self.service.control("renderer", "avtransport", body.encode(codec), header)
                self.assertEqual(status, 200)
                self.assertIn(b"SetAVTransportURIResponse", response)
                self.assertEqual(self.renderer.snapshot()["uri"], uri)

    def test_next_uses_the_next_transport_uri(self):
        self.renderer.set_uri("http://example.test/first.flac")
        self.renderer.set_next_uri("http://example.test/second.flac", "")

        result = self.renderer.command("next")

        self.assertTrue(result["ok"])
        self.assertEqual(self.renderer.snapshot()["uri"], "http://example.test/second.flac")
        self.assertEqual(self.renderer.snapshot()["next_uri"], "")
        self.assertTrue(self._wait_for(lambda: self.loads == [("http://example.test/second.flac", 0.0)]))
        self.assertEqual(self.renderer.snapshot()["transport"], "PLAYING")

    def test_next_notifications_do_not_hold_renderer_lock(self):
        entered = threading.Event()
        release = threading.Event()
        changed = threading.Event()
        armed = threading.Event()
        block_next = [True]

        def listener(_state):
            if not armed.is_set() or not block_next[0]:
                return
            block_next[0] = False
            entered.set()
            release.wait(1)

        self.renderer.add_state_listener(listener)
        self.renderer.set_uri("http://example.test/first.flac")
        self.renderer.set_next_uri("http://example.test/second.flac", "")
        entered.clear()
        armed.set()
        worker = threading.Thread(target=lambda: self.renderer.command("next"))
        worker.start()
        self.assertTrue(entered.wait(1))
        setter = threading.Thread(target=lambda: (self.renderer.set_uri("http://example.test/third.flac"), changed.set()))
        setter.start()
        self.assertTrue(changed.wait(1))
        release.set()
        worker.join(timeout=1)
        setter.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertFalse(setter.is_alive())

    def test_play_notifications_do_not_hold_renderer_lock(self):
        # command("play") used to call play() from inside its own lock window,
        # so every listener (eventing plus Playback Core) ran while the
        # renderer lock was held, blocking unrelated commands.
        entered = threading.Event()
        release = threading.Event()
        changed = threading.Event()
        armed = threading.Event()
        block_play = [True]

        def listener(_state):
            if not armed.is_set() or not block_play[0]:
                return
            block_play[0] = False
            entered.set()
            release.wait(1)

        self.renderer.add_state_listener(listener)
        self.renderer.set_uri("http://example.test/first.flac")
        entered.clear()
        armed.set()
        worker = threading.Thread(target=lambda: self.renderer.command("play"))
        worker.start()
        self.assertTrue(entered.wait(1))
        setter = threading.Thread(target=lambda: (self.renderer.set_uri("http://example.test/second.flac"), changed.set()))
        setter.start()
        self.assertTrue(changed.wait(1))
        release.set()
        worker.join(timeout=1)
        setter.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertFalse(setter.is_alive())

    def test_state_listeners_receive_a_copied_next_queue(self):
        # A listener is allowed to keep the state dict it was handed, and
        # command("next") pops the live queue in place, so the delivered copy
        # must not shrink afterwards.
        seen = []
        self.renderer.add_state_listener(lambda state: seen.append(state))
        self.renderer.set_uri("http://example.test/first.flac")
        self.renderer.set_next_uri("http://example.test/second.flac", "")
        self.renderer.set_next_uri("http://example.test/third.flac", "")
        expected = ["http://example.test/second.flac", "http://example.test/third.flac"]
        delivered = seen[-1]
        self.assertEqual([entry["uri"] for entry in delivered["next_queue"]], expected)

        self.renderer.command("next")

        self.assertEqual([entry["uri"] for entry in delivered["next_queue"]], expected)

    def test_snapshot_returns_a_copy_of_the_next_queue(self):
        # command("next") pops the live queue in place, so a projection taken
        # moments earlier (status polling, DLNA state) must not share it.
        self.renderer.set_uri("http://example.test/first.flac")
        for name in ("second", "third"):
            self.renderer.set_next_uri("http://example.test/%s.flac" % name, "")

        state = self.renderer.snapshot()
        self.assertEqual(
            [entry["uri"] for entry in state["next_queue"]],
            ["http://example.test/second.flac", "http://example.test/third.flac"],
        )

        self.renderer.command("next")

        self.assertEqual(len(state["next_queue"]), 2)
        self.assertEqual(state["next_uri"], "http://example.test/second.flac")
        self.assertEqual([entry["uri"] for entry in self.renderer.snapshot()["next_queue"]], ["http://example.test/third.flac"])

    def test_renderer_next_uri_queue_has_a_bounded_fifo_budget(self):
        self.renderer.set_uri("http://example.test/current.flac")
        for index in range(MAX_NEXT_QUEUE_ENTRIES + 1):
            self.renderer.set_next_uri("http://example.test/%s.flac" % index, "")
        state = self.renderer.snapshot()
        self.assertEqual(len(state["next_queue"]), MAX_NEXT_QUEUE_ENTRIES)
        self.assertEqual(state["next_uri"], "http://example.test/0.flac")
        self.assertEqual(state["next_queue_dropped"], 1)
        self.assertEqual(state["next_queue_limit"], MAX_NEXT_QUEUE_ENTRIES)

    def test_renderer_snapshot_does_not_apply_status_from_an_older_session(self):
        started = threading.Event()
        release = threading.Event()

        def slow_status():
            started.set()
            release.wait(1)
            return {
                "transport": {"state": "PLAYING"},
                "position": {"rel_seconds": 12, "duration_seconds": 120},
            }

        renderer = DlnaRenderer(self._load, self._control, slow_status)
        renderer.set_uri("http://example.test/old.flac")
        result = {}
        worker = threading.Thread(target=lambda: result.setdefault("state", renderer.snapshot()))
        worker.start()
        self.assertTrue(started.wait(1))
        renderer.set_uri("http://example.test/new.flac")
        release.set()
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result["state"]["uri"], "http://example.test/new.flac")
        self.assertEqual(result["state"]["transport"], "STOPPED")

    def test_bursty_renderer_controls_coalesce_to_one_backend_thread(self):
        renderer = DlnaRenderer(self._load, self._control, self._status)
        renderer.set_uri("http://example.test/current.flac")
        with mock.patch("dlna.renderer.Thread") as thread:
            renderer.command("pause")
            renderer.command("seek", 12.0)
            renderer.command("stop")
        self.assertEqual(thread.call_count, 1)
        state = renderer.snapshot()
        self.assertTrue(state["backend_worker_active"])
        self.assertTrue(state["backend_pending"])
        self.assertGreaterEqual(state["backend_coalesced"], 2)

    def test_backend_worker_admission_holds_renderer_state_lock(self):
        renderer = DlnaRenderer(self._load, self._control, self._status)
        renderer.set_uri("http://example.test/current.flac")
        original_lock = renderer._lock

        class ObservedLock:
            def __init__(self, lock):
                self.lock = lock
                self.depth = 0

            def __enter__(self):
                self.lock.acquire()
                self.depth += 1
                return self

            def __exit__(self, *args):
                self.depth -= 1
                self.lock.release()

        observed_lock = ObservedLock(original_lock)
        renderer._lock = observed_lock

        def make_thread(**_kwargs):
            self.assertGreater(observed_lock.depth, 0)
            return mock.Mock()

        with mock.patch("dlna.renderer.Thread", side_effect=make_thread):
            renderer.command("pause")

    def test_backend_thread_start_failure_releases_latch_for_retry(self):
        renderer = DlnaRenderer(self._load, self._control, self._status)
        renderer.set_uri("http://example.test/current.flac")
        with mock.patch("dlna.renderer.Thread") as thread:
            thread.return_value.start.side_effect = RuntimeError("no threads")
            with self.assertRaises(RuntimeError):
                renderer.command("pause")
        failed = renderer.snapshot()
        self.assertFalse(failed["backend_worker_active"])
        self.assertTrue(failed["backend_pending"])

        with mock.patch("dlna.renderer.Thread") as retry_thread:
            renderer.command("stop")
        self.assertTrue(retry_thread.called)
        self.assertTrue(renderer.snapshot()["backend_worker_active"])

    def test_stop_after_play_does_not_allow_an_old_load_to_restart(self):
        started = threading.Event()
        release = threading.Event()
        controls = []

        def slow_load(uri, position):
            started.set()
            release.wait(2)
            return {"ok": True}

        def control(action, position):
            controls.append((action, position))
            return {"ok": True}

        renderer = DlnaRenderer(slow_load, control, self._status)
        renderer.set_uri("http://example.test/slow.flac")
        self.assertTrue(renderer.command("play")["ok"])
        self.assertTrue(started.wait(1))

        self.assertTrue(renderer.command("stop")["ok"])
        release.set()

        self.assertTrue(self._wait_for(lambda: ("stop", None) in controls))
        self.assertEqual(renderer.snapshot()["transport"], "STOPPED")
        self.assertEqual(renderer.snapshot()["position"], 0.0)

    def test_delayed_play_admission_cannot_replace_newer_stop(self):
        controls = []
        entered_notify = threading.Event()
        release_notify = threading.Event()

        def control(action, position):
            controls.append((action, position))
            return {"ok": True}

        renderer = DlnaRenderer(self._load, control, self._status)
        renderer.set_uri("http://example.test/current.flac")
        original_notify = renderer._notify
        blocked_once = {"value": False}

        def pause_first_play_notification():
            if not blocked_once["value"]:
                blocked_once["value"] = True
                entered_notify.set()
                release_notify.wait(1)
            original_notify()

        renderer._notify = pause_first_play_notification
        play_thread = threading.Thread(target=renderer.command, args=("play",))
        play_thread.start()
        self.assertTrue(entered_notify.wait(1))

        self.assertTrue(renderer.command("stop")["ok"])
        release_notify.set()
        play_thread.join(timeout=1)

        self.assertFalse(play_thread.is_alive())
        self.assertTrue(self._wait_for(lambda: ("stop", None) in controls))
        self.assertEqual(self.loads, [])
        self.assertEqual(renderer.snapshot()["transport"], "STOPPED")

    def test_pause_then_play_reloads_the_paused_uri(self):
        renderer = DlnaRenderer(self._load, self._control, self._status)
        renderer.set_uri("http://example.test/resume.flac")

        renderer.command("play")
        self.assertTrue(self._wait_for(lambda: len(self.loads) == 1))
        renderer.command("pause")
        self.assertTrue(self._wait_for(lambda: ("pause", None) in self.controls))
        self.assertEqual(renderer.snapshot()["transport"], "PAUSED_PLAYBACK")

        renderer.command("play")
        self.assertTrue(self._wait_for(lambda: len(self.loads) == 2))
        self.assertEqual(renderer.snapshot()["transport"], "PLAYING")

    def test_backend_output_error_stops_the_renderer_session(self):
        renderer = DlnaRenderer(
            self._load,
            self._control,
            lambda: {
                "transport": {"state": "PAUSED"},
                "position": {"rel_seconds": 0, "duration_seconds": 12},
                "raw": {"error": "Failed to open ALSA device"},
            },
        )
        renderer.set_uri("http://example.test/failure.flac")
        renderer.command("play")
        self.assertTrue(self._wait_for(lambda: len(self.loads) == 1))

        state = renderer.snapshot()

        self.assertEqual(state["transport"], "STOPPED")
        self.assertIn("Failed to open ALSA device", state["last_error"])

    @mock.patch("dlna.control_point.soap_request")
    def test_renderer_protocol_info_is_parsed_into_mime_capabilities(self, request):
        request.return_value = (
            b'<Envelope><Source></Source><Sink>'
            b'http-get:*:audio/flac:*,http-get:*:audio/x-dsf:*'
            b'</Sink></Envelope>'
        )

        result = device_protocol_info("http://renderer.test/connection")

        self.assertTrue(result["supports_dsd"])
        self.assertIn("audio/flac", result["mime_types"])
        self.assertIn("audio/x-dsf", result["mime_types"])

    def test_event_subscriptions_are_bounded(self):
        events = self.service.events
        events._callback_url = lambda value: value
        for index in range(64):
            events.subscribe("renderer", "avtransport", "http://198.51.100.20/%s" % index, "", "Second-60")
        with self.assertRaisesRegex(ValueError, "too many"):
            events.subscribe("renderer", "avtransport", "http://198.51.100.20/overflow", "", "Second-60")

    def test_event_admission_reclaims_lapsed_leases(self):
        class DeferredExecutor:
            def __init__(self):
                self.calls = []
            def submit(self, fn, *args):
                self.calls.append((fn, args))
            def shutdown(self, wait=True, cancel_futures=False):
                self.calls.clear()

        class FixedClock:
            def __init__(self, start):
                self.now = start
            def monotonic(self):
                return self.now
            def time(self):
                return time.time()
            def sleep(self, seconds):
                time.sleep(seconds)

        events = DlnaEventService(max_workers=1, max_pending=MAX_EVENT_SUBSCRIPTIONS * 2)
        events._callback_url = lambda value: value
        events._executor = DeferredExecutor()
        clock = FixedClock(1000.0)
        try:
            with mock.patch.object(dlna_service, "time", clock):
                for index in range(MAX_EVENT_SUBSCRIPTIONS):
                    events.subscribe("renderer", "avtransport", "http://198.51.100.20/%s" % index, "", "Second-60")
                events.notify_renderer({"transport": "PLAYING", "volume": 10})
                self.assertEqual(events.snapshot()["pending"], MAX_EVENT_SUBSCRIPTIONS)

                # Every controller walks away without unsubscribing.
                clock.now = 1100.0
                sid, timeout = events.subscribe("renderer", "avtransport", "http://198.51.100.20/fresh", "", "Second-60")
                self.assertTrue(sid.startswith("uuid:"))
                self.assertEqual(timeout, 60)
                self.assertEqual(len(events._subscriptions), 1)
                self.assertEqual(events._pending_notifications, 0)
                # A second admission on the same lapsed table changes nothing.
                events.subscribe("renderer", "rendering", "http://198.51.100.20/fresh-2", "", "Second-60")
                self.assertEqual(len(events._subscriptions), 2)
        finally:
            events.shutdown(wait=False)

    def test_slow_callback_resolution_does_not_block_eventing(self):
        events = DlnaEventService(max_workers=1)
        entered = threading.Event()
        release = threading.Event()
        waits = []

        def slow_callback(value):
            entered.set()
            release.wait(10)
            return value

        events._callback_url = slow_callback

        def observer():
            began = time.monotonic()
            events.notify_renderer({"transport": "PLAYING", "volume": 10})
            waits.append(time.monotonic() - began)

        try:
            subscriber = threading.Thread(target=lambda: events.subscribe("renderer", "avtransport", "http://198.51.100.20/slow", "", "Second-60"))
            subscriber.start()
            self.assertTrue(entered.wait(10), "callback validation never started")
            watching = threading.Thread(target=observer)
            watching.start()
            deadline = time.monotonic() + 0.25
            while not waits and time.monotonic() < deadline:
                time.sleep(0.005)
            release.set()
            subscriber.join(10)
            watching.join(10)
            self.assertTrue(waits, "renderer notification never returned")
            self.assertLess(waits[0], 0.2, "notification waited behind the subscription lock")
            self.assertEqual(len(events._subscriptions), 1)
        finally:
            release.set()
            events.shutdown(wait=False)

    def test_callback_validation_still_resolves_the_host_it_admits(self):
        class ResolverSocket:
            gaierror = OSError
            SOCK_STREAM = 1
            def __init__(self, addresses):
                self.addresses = addresses
                self.seen = []
            def getaddrinfo(self, host, port, type=None):
                self.seen.append((host, port))
                return [(2, 1, 6, "", (address, port)) for address in self.addresses]

        events = DlnaEventService()
        resolver = ResolverSocket(["198.51.100.20"])
        with mock.patch.object(dlna_network, "socket", resolver):
            self.assertEqual(events._callback_url('<http://controller.example:8000/Event>'), "http://controller.example:8000/Event")
        self.assertEqual(resolver.seen, [("controller.example", 8000)])

        resolver = ResolverSocket(["8.8.8.8"])
        with mock.patch.object(dlna_network, "socket", resolver):
            with self.assertRaisesRegex(ValueError, "LAN addresses"):
                events._callback_url('<http://controller.example:8000/Event>')
        self.assertEqual(resolver.seen, [("controller.example", 8000)])

    def test_a_host_that_never_resolves_cannot_take_the_http_pool_with_it(self):
        # `getaddrinfo` has no timeout of its own, and every SUBSCRIBE used to run one on its
        # own HTTP worker: measured, 16 simultaneous subscriptions put 16 of the 32 workers in
        # the resolver at once, so 32 would stop the web UI and /api/health too. The bound is
        # on concurrency, not on the answer, so validation still resolves every host it admits.
        events = DlnaEventService()
        self.addCleanup(events.shutdown, True)
        limit = dlna_service.GENA_VALIDATION_LIMIT
        self.assertLess(limit, 32 // 2, "the bound must leave most of the worker pool free")
        inside = 0
        peak = 0
        guard = threading.Lock()
        release = threading.Event()
        barrier = threading.Barrier(limit * 4)

        def blocked_validation(value):
            nonlocal inside, peak
            with guard:
                inside += 1
                peak = max(peak, inside)
            release.wait(30)
            with guard:
                inside -= 1
            return value

        events._callback_url = blocked_validation
        refusals = []

        def subscriber(index):
            barrier.wait(30)
            try:
                events.subscribe("renderer", "avtransport", "http://198.51.100.20/%d" % index, "", "Second-60")
            except ValueError as exc:
                refusals.append(str(exc))

        threads = [threading.Thread(target=subscriber, args=(index,), name="flood-%d" % index)
                   for index in range(limit * 4)]
        for thread in threads:
            thread.start()
        # The release has to wait until every flood thread is accounted for at the bound:
        # inside the callback, queued behind it, or already refused.  Stopping at "peak
        # reached the limit" let the main thread unblock the holders while the slowest
        # arrivals were still between the barrier and subscribe(), and those arrivals then
        # found a free slot: the admitted total came out above limit + waiters for reasons
        # that have nothing to do with the bound this test exists to hold.
        flood = limit * 4
        deadline = time.monotonic() + 10.0
        accounted = 0
        while time.monotonic() < deadline:
            gate = events._validation_gate.snapshot()
            accounted = gate["active"] + gate["waiting"] + len(refusals)
            if accounted >= flood:
                break
            time.sleep(0.01)
        with guard:
            observed_peak = peak
        self.assertEqual(
            accounted, flood,
            "only %d of %d flood threads reached the bound, so the verdict below is not a"
            " measurement of the bound" % (accounted, flood))
        release.set()
        for thread in threads:
            thread.join(30)
        # Anti-idling: the flood has to have actually stacked up to the bound, or "never more
        # than 4" would be satisfied by nothing having run at all.
        self.assertGreaterEqual(observed_peak, limit, "no validation ever reached the bound")
        self.assertLessEqual(observed_peak, limit, "the resolver bound was exceeded")
        status = events.snapshot()
        self.assertEqual(status["validating"], 0)
        # The bound limits concurrency, not the total: the four that were already queued get
        # their turn once the holders finish, so a flood of 16 can admit at most
        # `limit + waiters` and must refuse the rest while the resolver is dead.
        self.assertGreaterEqual(status["subscriptions"], limit)
        self.assertLessEqual(status["subscriptions"], limit + dlna_service.GENA_VALIDATION_WAITERS)
        self.assertEqual(len(refusals), 16 - status["subscriptions"])
        self.assertTrue(refusals, "the overflow was queued indefinitely instead of refused")

    def test_an_admission_that_cannot_happen_never_costs_a_resolution(self):
        # The cap used to be checked after the resolver answered, so a table that was already
        # full paid one resolution per refused request: measured 20 refused, 20 burned.
        events = DlnaEventService()
        self.addCleanup(events.shutdown, True)
        resolutions = []
        events._callback_url = lambda value: (resolutions.append(value), value)[1]
        for index in range(MAX_EVENT_SUBSCRIPTIONS):
            events.subscribe("renderer", "avtransport", "http://198.51.100.20/lease-%d" % index, "", "Second-3600")
        self.assertEqual(events.snapshot()["subscriptions"], MAX_EVENT_SUBSCRIPTIONS)
        del resolutions[:]
        for index in range(5):
            with self.assertRaises(ValueError) as refused:
                events.subscribe("renderer", "avtransport", "http://198.51.100.20/flood-%d" % index, "", "Second-3600")
        self.assertEqual(resolutions, [], "a refused admission still resolved its callback")
        # The point is a cheaper refusal, not a different refusal: the reason the client sees
        # must stay the one the authoritative check gives, or the two paths drift.
        self.assertEqual(str(refused.exception), "too many event subscriptions")
        # A lapsed lease has to keep working: refusing here would turn the cap into a wedge.
        oldest = next(iter(events._subscriptions))
        events._subscriptions[oldest]["expires"] = time.monotonic() - 1.0
        sid, _ = events.subscribe("renderer", "avtransport", "http://198.51.100.20/reclaimed", "", "Second-60")
        self.assertTrue(sid.startswith("uuid:"))
        self.assertEqual(len(resolutions), 1, "an admissible request must still resolve exactly once")
        # Subscribing after shutdown used to hand out a lease nothing can ever deliver.
        events._shutdown = True
        before = len(resolutions)
        with self.assertRaises(ValueError) as late:
            events.subscribe("renderer", "avtransport", "http://198.51.100.20/late", "", "Second-60")
        self.assertIn("shutting down", str(late.exception))
        self.assertEqual(len(resolutions), before)

    def test_a_saturated_validator_refuses_within_its_own_wait_bound(self):
        # Overflow must cost the caller about `GENA_VALIDATION_WAIT_SECONDS`, not however long
        # the host in front of it takes to time out.
        events = DlnaEventService()
        self.addCleanup(events.shutdown, True)
        limit = dlna_service.GENA_VALIDATION_LIMIT
        # Read the policy before measuring it. A test whose expectation is computed from the
        # same constant the code uses cannot notice the constant being widened, and widening
        # it is exactly how this bound decays back into "no bound".
        self.assertLessEqual(
            dlna_service.GENA_VALIDATION_WAIT_SECONDS, 3.0,
            "a caller must not be parked behind someone else's dead resolver for longer than this")
        self.assertLessEqual(
            dlna_service.GENA_VALIDATION_WAITERS, limit,
            "the queue in front of the bound may not be wider than the bound itself")
        self.assertEqual(events.snapshot()["validation_waiter_limit"], dlna_service.GENA_VALIDATION_WAITERS)
        release = threading.Event()
        self.addCleanup(release.set)
        events._callback_url = lambda value: (release.wait(30), value)[1]
        holders = [threading.Thread(target=events.subscribe,
                                    args=("renderer", "avtransport", "http://198.51.100.20/hold-%d" % index, "", "Second-60"),
                                    name="holder-%d" % index)
                   for index in range(limit)]
        for holder in holders:
            holder.start()
        time.sleep(0.3)
        self.assertEqual(events.snapshot()["validating"], limit, "the holders never filled the bound")
        began = time.perf_counter()
        with self.assertRaises(ValueError) as refused:
            events.subscribe("renderer", "avtransport", "http://198.51.100.20/overflow", "", "Second-60")
        waited = time.perf_counter() - began
        self.assertIn("busy", str(refused.exception))
        self.assertLess(waited, dlna_service.GENA_VALIDATION_WAIT_SECONDS + 1.0)
        self.assertFalse(release.is_set(), "the refusal only happened because validation finished")
        self.assertEqual(events.snapshot()["validation_rejected"], 1)
        release.set()
        for holder in holders:
            holder.join(30)

    def test_the_validator_reports_counts_and_never_names_a_peer(self):
        # R87's rule: state that is added has to be observable, and on this surface only as
        # counters. The callback host is as identifying as a device name.
        events = DlnaEventService()
        self.addCleanup(events.shutdown, True)
        events._callback_url = lambda value: value
        keys = ("validating", "validation_limit", "validation_waiter_limit",
                "validation_waited", "validation_rejected")
        status = events.snapshot()
        self.assertEqual([key for key in keys if key not in status], [])
        self.assertTrue(all(isinstance(status[key], int) for key in keys), status)
        self.assertEqual(status["validation_limit"], dlna_service.GENA_VALIDATION_LIMIT)
        self.assertEqual(status["validation_waiter_limit"], dlna_service.GENA_VALIDATION_WAITERS)
        events.subscribe("renderer", "avtransport", "http://controller.invalid:8000/Event", "", "Second-60")
        status = events.snapshot()
        self.assertEqual(status["validation_rejected"], 0)
        rendered = repr(status)
        for fragment in ("controller.invalid", "198.51.100.20", "http://", "Event"):
            self.assertNotIn(fragment, rendered, fragment)

    def test_event_notifications_are_bounded_before_executor_submission(self):
        class DeferredExecutor:
            def __init__(self):
                self.calls = []

            def submit(self, fn, *args):
                self.calls.append((fn, args))

        events = DlnaEventService(max_workers=2, max_pending=1)
        events._callback_url = lambda value: value
        events._executor = DeferredExecutor()
        events.subscribe("renderer", "avtransport", "http://198.51.100.20/one", "", "Second-60")
        events.subscribe("renderer", "rendering", "http://198.51.100.20/two", "", "Second-60")

        events.notify_renderer({"transport": "PLAYING", "volume": 20})

        status = events.snapshot()
        self.assertEqual(len(events._executor.calls), 1)
        self.assertEqual(status["pending"], 1)
        self.assertEqual(status["pending_limit"], 1)
        self.assertEqual(status["accepted"], 1)
        self.assertEqual(status["dropped"], 1)

    def test_event_sequence_is_reserved_before_concurrent_submission(self):
        class DeferredExecutor:
            def __init__(self):
                self.calls = []
            def submit(self, fn, *args):
                self.calls.append(args)

        events = DlnaEventService(max_workers=2, max_pending=4)
        events._callback_url = lambda value: value
        events._executor = DeferredExecutor()
        sid, _ = events.subscribe("renderer", "avtransport", "http://198.51.100.20/one", "", "Second-60")
        events.notify_renderer({"transport": "PLAYING"})
        events.notify_renderer({"transport": "PAUSED"})
        self.assertEqual(len(events._executor.calls), 1)
        self.assertEqual([delivery[1] for delivery in events._subscriptions[sid]["deliveries"]], [0, 1])
        self.assertEqual(events._subscriptions[sid]["sequence"], 2)

    def test_event_submit_failure_releases_all_mailbox_pressure(self):
        class FailingExecutor:
            def __init__(self):
                self.injected = False

            def submit(self, fn, *args):
                if not self.injected:
                    self.injected = True
                    events.notify_renderer({"transport": "PAUSED"})
                raise RuntimeError("executor unavailable")

        events = DlnaEventService(max_workers=1, max_pending=4)
        events._callback_url = lambda value: value
        events._executor = FailingExecutor()
        sid, _ = events.subscribe("renderer", "avtransport", "http://198.51.100.20/one", "", "Second-60")

        events.notify_renderer({"transport": "PLAYING"})

        self.assertEqual(events.snapshot()["pending"], 0)
        self.assertEqual(events.snapshot()["dropped"], 2)
        self.assertFalse(events._subscriptions[sid]["delivery_scheduled"])
        self.assertEqual(len(events._subscriptions[sid]["deliveries"]), 0)

    def test_event_snapshot_expiry_releases_queued_notification_pressure(self):
        class DeferredExecutor:
            def submit(self, fn, *args):
                pass

        events = DlnaEventService(max_workers=1, max_pending=2)
        events._callback_url = lambda value: value
        events._executor = DeferredExecutor()
        sid, _ = events.subscribe("renderer", "avtransport", "http://198.51.100.20/one", "", "Second-60")
        events.notify_renderer({"transport": "PLAYING"})
        events._subscriptions[sid]["expires"] = 0

        self.assertEqual(events.snapshot()["subscriptions"], 0)
        self.assertEqual(events.snapshot()["pending"], 0)

    def test_expired_subscription_cannot_be_renewed(self):
        events = DlnaEventService(max_workers=1)
        events._callback_url = lambda value: value
        sid, _ = events.subscribe("renderer", "avtransport", "http://198.51.100.20/one", "", "Second-60")
        events._subscriptions[sid]["expires"] = 0
        with self.assertRaisesRegex(ValueError, "unknown subscription"):
            events.subscribe("renderer", "avtransport", "", sid, "Second-60")
        self.assertNotIn(sid, events._subscriptions)
        events.shutdown()

    def test_expired_subscription_drops_queued_delivery_before_send(self):
        class DeferredExecutor:
            def __init__(self):
                self.calls = []
            def submit(self, fn, *args):
                self.calls.append((fn, args))

        events = DlnaEventService(max_workers=1)
        events._callback_url = lambda value: value
        events._executor = DeferredExecutor()
        sid, _ = events.subscribe("renderer", "avtransport", "http://198.51.100.20/one", "", "Second-60")
        events.notify_renderer({"transport": "PLAYING"})
        events._subscriptions[sid]["expires"] = 0
        fn, args = events._executor.calls[0]
        with mock.patch("dlna.service.fetch_lan") as send:
            fn(*args)
        send.assert_not_called()
        self.assertEqual(events.snapshot()["pending"], 0)

    def test_notification_is_not_admitted_after_subscription_expires_during_body_build(self):
        events = DlnaEventService(max_workers=1, max_pending=4)
        self.addCleanup(events.shutdown)
        events._callback_url = lambda value: value
        sid, _ = events.subscribe("renderer", "avtransport", "http://198.51.100.20/one", "", "Second-30")
        with mock.patch.object(events, "_body", side_effect=lambda *_: self._expire_subscription(events, sid)):
            events.notify_renderer({"TransportState": "PLAYING"})
        self.assertNotIn(sid, events._subscriptions)
        self.assertEqual(events.snapshot()["pending"], 0)

    @staticmethod
    def _expire_subscription(events, sid):
        events._subscriptions[sid]["expires"] = 0
        return b"<event/>"

    def test_event_delivery_waits_for_earlier_sequence_of_the_same_subscription(self):
        events = DlnaEventService(max_workers=2, max_pending=4)
        events._callback_url = lambda value: value
        sid, _ = events.subscribe("renderer", "avtransport", "http://198.51.100.20/one", "", "Second-60")
        seen = []
        started = threading.Event()
        release = threading.Event()

        def send(_request, **_kwargs):
            sequence = int(_request.get_header("Seq"))
            if sequence == 0:
                started.set()
                release.wait(1)
            seen.append(sequence)
            return object()

        with mock.patch("dlna.service.fetch_lan", side_effect=send):
            events.notify_renderer({"transport": "PLAYING"})
            self.assertTrue(started.wait(1))
            events.notify_renderer({"transport": "PAUSED"})
            release.set()
            deadline = time.time() + 1
            while len(seen) < 2 and time.time() < deadline:
                time.sleep(0.01)
        events.shutdown()
        self.assertEqual(seen, [0, 1])

    def test_event_delivery_for_one_slow_subscription_does_not_park_every_worker(self):
        events = DlnaEventService(max_workers=2, max_pending=8)
        events._callback_url = lambda value: value
        slow_sid, _ = events.subscribe("renderer", "avtransport", "http://198.51.100.20/slow", "", "Second-60")
        fast_sid, _ = events.subscribe("renderer", "avtransport", "http://198.51.100.21/fast", "", "Second-60")
        slow_started = threading.Event()
        release_slow = threading.Event()
        fast_seen = threading.Event()

        def send(request, **_kwargs):
            sid = request.get_header("Sid")
            if sid == slow_sid:
                slow_started.set()
                release_slow.wait(1)
            elif sid == fast_sid:
                fast_seen.set()
            return object()

        with mock.patch("dlna.service.fetch_lan", side_effect=send):
            events.notify_renderer({"transport": "PLAYING"})
            self.assertTrue(slow_started.wait(1))
            events.notify_renderer({"transport": "PAUSED"})
            events.notify_renderer({"transport": "STOPPED"})
            time.sleep(0.05)
            events.notify_renderer({"transport": "PLAYING"})
            self.assertTrue(fast_seen.wait(0.5))
            release_slow.set()
        events.shutdown()

    def test_a_delivery_in_flight_does_not_hold_the_lock_the_admission_path_needs(self):
        # The event face runs on one lock, and R69 deliberately left it alone pending a
        # contention measurement.  Measured now: a 64-subscription storm spends about 1% of
        # its wall outside the callbacks' own sleeps (3.232 s for 256 deliveries against a
        # 3.200 s parallel lower bound), and a fresh admission during that storm costs
        # 26-42 microseconds, so splitting the lock would buy nothing.  What has to stay
        # true for that conclusion to hold is narrower and worth pinning: the network call
        # is made outside the lock, so one unreachable controller cannot stop another from
        # subscribing.
        events = DlnaEventService(max_workers=1, max_pending=8)
        events._callback_url = lambda value: value
        blocked_sid, _ = events.subscribe("renderer", "avtransport",
                                          "http://198.51.100.20/slow", "", "Second-60")
        entered = threading.Event()
        release = threading.Event()

        def send(request, **_kwargs):
            if request.get_header("Sid") == blocked_sid:
                entered.set()
                release.wait(2)
            return object()

        outcome = []

        def arrive():
            try:
                outcome.append(events.subscribe("renderer", "avtransport",
                                                "http://198.51.100.21/fast", "", "Second-60")[0])
            except Exception as error:
                outcome.append(error)

        with mock.patch("dlna.service.fetch_lan", side_effect=send):
            events.notify_renderer({"transport": "PLAYING"})
            self.assertTrue(entered.wait(1), "the blocked delivery never started")
            arrival = threading.Thread(target=arrive)
            arrival.start()
            arrival.join(1)
            waiting = arrival.is_alive()
            release.set()
            arrival.join(1)
        events.shutdown()
        self.assertFalse(waiting, "the new admission was still waiting while only a callback was "
                                  "blocked, so the lock is being held across the delivery")
        self.assertEqual(len(outcome), 1,
                         "a new admission never returned at all")
        self.assertIsInstance(outcome[0], str,
                              "admission failed instead of returning a SID: %r" % (outcome[0],))

    def test_event_shutdown_rejects_new_notifications_and_closes_executor(self):
        events = DlnaEventService()
        events.shutdown()
        events.notify_renderer({"transport": "PLAYING"})
        self.assertEqual(events.snapshot()["subscriptions"], 0)

    def test_event_shutdown_honors_timeout_while_callback_is_in_flight(self):
        events = DlnaEventService(max_workers=1)
        events._callback_url = lambda value: value
        events.subscribe("renderer", "avtransport", "http://198.51.100.20/one", "", "Second-60")
        started = threading.Event()
        release = threading.Event()

        def send(_request, **_kwargs):
            started.set()
            release.wait(1)
            return object()

        with mock.patch("dlna.service.fetch_lan", side_effect=send):
            events.notify_renderer({"transport": "PLAYING"})
            self.assertTrue(started.wait(1))
            began = time.monotonic()
            events.shutdown(timeout=0.03)
            self.assertLess(time.monotonic() - began, 0.25)
            release.set()
            deadline = time.monotonic() + 1
            while events.snapshot()["workers"] and time.monotonic() < deadline:
                time.sleep(0.01)
        self.assertEqual(events.snapshot()["workers"], 0)

    def test_event_shutdown_replaces_nonfinite_timeout_before_waiting(self):
        events = DlnaEventService()
        lock = threading.RLock()
        ready = mock.Mock()
        events._lock = lock
        events._delivery_ready = ready
        events._active_notifications = 1

        def wait(timeout):
            self.assertTrue(math.isfinite(timeout))
            events._active_notifications = 0

        ready.wait.side_effect = wait
        events.shutdown(timeout=float("nan"))
        ready.wait.assert_called_once()

    def test_event_unsubscribe_releases_queued_notification_pressure(self):
        class DeferredExecutor:
            def __init__(self):
                self.calls = []
            def submit(self, fn, *args):
                self.calls.append((fn, args))

        events = DlnaEventService(max_workers=1, max_pending=2)
        events._callback_url = lambda value: value
        events._executor = DeferredExecutor()
        sid, _ = events.subscribe("renderer", "avtransport", "http://198.51.100.20/one", "", "Second-60")
        events.notify_renderer({"transport": "PLAYING"})
        events.unsubscribe(sid)
        fn, args = events._executor.calls[0]
        fn(*args)
        self.assertEqual(events.snapshot()["pending"], 0)

    def test_content_directory_honors_metadata_filter_sort_and_update_id(self):
        calls = []
        item = {"id": "track-1", "title": "Example", "artist": "Artist", "album": "Album", "format": "FLAC", "mime": "audio/flac", "duration": 12}

        def page(params):
            calls.append(dict(params))
            return {"items": [item], "count": 1}

        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            page,
            lambda view, **query: [],
            lambda value: value.get("mime", "audio/mpeg"),
            library_item=lambda item_id: item if item_id == "track-1" else None,
            system_update_id=lambda: 42,
        )
        children = service._browse({
            "ObjectID": "music",
            "BrowseFlag": "BrowseDirectChildren",
            "Filter": "dc:title,upnp:artist",
            "StartingIndex": "0",
            "RequestedCount": "0",
            "SortCriteria": "-upnp:artist",
        })
        self.assertEqual(children["UpdateID"], "42")
        self.assertEqual(children["NumberReturned"], "1")
        self.assertEqual(calls[0]["sort"], "artist")
        self.assertEqual(calls[0]["dir"], "desc")
        self.assertIn("<upnp:artist>Artist</upnp:artist>", children["Result"])
        self.assertNotIn("<upnp:album>", children["Result"])
        self.assertNotIn("<res ", children["Result"])

        self.assertEqual(service._dispatch("server", CONTENT_DIRECTORY, "GetSearchCapabilities", {})["SearchCaps"], "")

        metadata = service._browse({"ObjectID": "track-1", "BrowseFlag": "BrowseMetadata", "Filter": "*"})
        self.assertEqual(metadata["NumberReturned"], "1")
        self.assertIn("audio/flac", metadata["Result"])
        self.assertIn("urn:schemas-dlna-org:metadata-1-0", metadata["Result"])
        self.assertIn('dlna:profileID="JPEG_TN"', metadata["Result"])
        self.assertEqual(service._dispatch("server", CONTENT_DIRECTORY, "GetSystemUpdateID", {}), {"Id": "42"})

    def test_content_directory_rejects_unknown_objects_and_sort_criteria(self):
        with self.assertRaises(UpnpActionError) as unknown:
            self.service._browse({"ObjectID": "missing", "BrowseFlag": "BrowseDirectChildren"})
        self.assertEqual(unknown.exception.code, 701)
        with self.assertRaises(UpnpActionError) as invalid_sort:
            self.service._browse({"ObjectID": "music", "BrowseFlag": "BrowseDirectChildren", "SortCriteria": "+dc:date"})
        self.assertEqual(invalid_sort.exception.code, 709)

    def test_content_directory_uses_safe_fallback_for_corrupt_page_count(self):
        service = DlnaProtocolService(
            lambda: "http://198.51.100.2:5666",
            self.renderer,
            lambda params: {"items": [{"id": "track-1", "title": "Example"}], "count": object()},
            lambda view, **query: [],
            lambda value: "audio/mpeg",
            library_item=lambda item_id: {"id": "track-1"} if item_id == "track-1" else None,
        )
        result = service._browse({"ObjectID": "music", "BrowseFlag": "BrowseDirectChildren"})
        self.assertEqual(result["TotalMatches"], "1")

    def test_content_directory_browse_metadata_returns_one_root_object(self):
        result = self.service._browse({"ObjectID": "0", "BrowseFlag": "BrowseMetadata", "Filter": "dc:title"})
        self.assertEqual(result["NumberReturned"], "1")
        self.assertEqual(result["TotalMatches"], "1")
        self.assertIn('parentID="-1"', result["Result"])

    @staticmethod
    def _wait_for(predicate, timeout=1.5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.01)
        return bool(predicate())


if __name__ == "__main__":
    unittest.main()
