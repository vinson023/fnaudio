"""One fact, one predicate: the native-DSD capability truth table (R126 / TODO L176).

Before this round the same question -- can this renderer take a source DSD
stream? -- had three answers depending on where you asked.  Discovery wrote a
flat ``device["supports_dsd"]`` that reported ``False`` for "we never got an
answer", ``media_server.soap_push()`` read the nested probe record and treated a
*failed* probe as a refusal, and ``profiles.device_supports_native_dsd()`` read
the flat field again.  Every case below pins the unified three-state behaviour
and, where the three shapes disagreed, says out loud which side won.
"""

import io
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, "app/server")

from dlna import media_server
from dlna.control_point import device_protocol_info, device_supports_dsd
from dlna.profiles import (
    DSD_CAPABILITY_SUPPORTED,
    DSD_CAPABILITY_UNKNOWN,
    DSD_CAPABILITY_UNSUPPORTED,
    device_supports_native_dsd,
    dsd_capability_state,
)
from dlna.media_server import soap_push
from playback_targets_presentation import build_targets


DSD_ITEM = {"id": "dsd-1", "path": "/music/test.dff", "is_dsd": True, "mime": "audio/x-dff", "duration": 1}
PCM_ITEM = {"id": "pcm-1", "path": "/music/test.flac", "mime": "audio/flac", "duration": 1}


class Handler:
    server = type("Server", (), {"config": {}})()


def _push(device, item=DSD_ITEM):
    # The gate runs before any transport call, but a device without a control
    # URL exits even earlier, so every row has to look like a real renderer.
    device = dict(device)
    device.setdefault("control_url", "http://renderer/control")
    with mock.patch.object(media_server, "soap_request") as request:
        result = soap_push(device, item, Handler(), lambda value: value, lambda _h: "http://host", lambda *_: "")
    return result, request


# (shape, device record, expected state, expected push decision, expected display)
TRUTH_TABLE = [
    (
        "空设备：什么都没探测过",
        {},
        DSD_CAPABILITY_UNKNOWN,
        True,
        False,
    ),
    (
        "扁平字段确认不支持",
        {"supports_dsd": False},
        DSD_CAPABILITY_UNSUPPORTED,
        False,
        False,
    ),
    (
        "扁平字段确认支持",
        {"supports_dsd": True},
        DSD_CAPABILITY_SUPPORTED,
        True,
        True,
    ),
    (
        "扁平字段是非布尔文本",
        {"supports_dsd": "true"},
        DSD_CAPABILITY_UNSUPPORTED,
        False,
        False,
    ),
    (
        "探测记录确认不支持（Volumio 形状）",
        {"capabilities": {"protocol_info": {"source": [], "sink": [], "mime_types": [], "supports_dsd": False}}},
        DSD_CAPABILITY_UNSUPPORTED,
        False,
        False,
    ),
    (
        "探测记录确认支持",
        {"capabilities": {"protocol_info": {"source": [], "sink": [], "mime_types": ["audio/x-dsf"], "supports_dsd": True}}},
        DSD_CAPABILITY_SUPPORTED,
        True,
        True,
    ),
    (
        "探测记录里根本没有这个键",
        {"capabilities": {"protocol_info": {"source": [], "sink": [], "mime_types": []}}},
        DSD_CAPABILITY_UNKNOWN,
        True,
        False,
    ),
    (
        "整个 capabilities 不是字典",
        {"capabilities": "broken"},
        DSD_CAPABILITY_UNKNOWN,
        True,
        False,
    ),
]


class NativeDsdTruthTableTests(unittest.TestCase):
    def test_every_shape_maps_to_one_state_one_gate_and_one_display(self):
        for label, device, state, push_allowed, display in TRUTH_TABLE:
            with self.subTest(shape=label):
                self.assertEqual(dsd_capability_state(device), state)
                self.assertEqual(device_supports_native_dsd(device), display)
                result, request = _push(device)
                if push_allowed:
                    self.assertTrue(result[0], result[1])
                    self.assertTrue(request.called)
                else:
                    self.assertFalse(result[0])
                    self.assertIn("不支持源码 DSD", result[1])
                    self.assertFalse(request.called)

    def test_non_dsd_sources_never_reach_the_gate(self):
        refusal = {"capabilities": {"protocol_info": {"supports_dsd": False}}}
        result, request = _push(refusal, PCM_ITEM)
        self.assertTrue(result[0], result[1])
        self.assertTrue(request.called)

    def test_a_failed_probe_is_silence_and_not_a_refusal(self):
        # This is the contradiction the entry was about: the comment promised
        # "empty/unknown stays permissive" while the code blocked on it, because
        # a failed ConnectionManager request wrote supports_dsd = False.
        shell = device_protocol_info("")
        self.assertNotIn("supports_dsd", shell)
        self.assertEqual(dsd_capability_state(shell), DSD_CAPABILITY_UNKNOWN)
        device = {"capabilities": {"protocol_info": shell}}
        result, request = _push(device)
        self.assertTrue(result[0], result[1])
        self.assertTrue(request.called)

    def test_a_raising_probe_also_reports_silence(self):
        with mock.patch("dlna.control_point.soap_request", side_effect=OSError("unreachable")):
            shell = device_protocol_info("http://renderer.test/connection")
            self.assertEqual(shell, {"source": [], "sink": [], "mime_types": []})
            self.assertEqual(dsd_capability_state(shell), DSD_CAPABILITY_UNKNOWN)
            self.assertFalse(device_supports_dsd("http://renderer.test/connection"))
        result, request = _push({"capabilities": {"protocol_info": shell}})
        self.assertTrue(result[0], result[1])
        self.assertTrue(request.called)

    def test_a_refusal_claimed_as_none_is_still_a_refusal(self):
        # A present key is a claim, so ``None`` cannot be laundered into silence:
        # narrowing this to unknown would re-open the bit-perfect hole for
        # renderers whose probe wrote a null.
        for device in ({"supports_dsd": None}, {"capabilities": {"protocol_info": {"supports_dsd": None}}}):
            with self.subTest(device=repr(device)):
                self.assertEqual(dsd_capability_state(device), DSD_CAPABILITY_UNSUPPORTED)
                self.assertFalse(device_supports_native_dsd(device))
                result, request = _push(device)
                self.assertFalse(result[0])
                self.assertFalse(request.called)

    def test_the_probe_record_outranks_the_derived_display_field(self):
        # The flat field is only a cache of the probe, so a stale or hand-written
        # True must not outvote a recorded refusal, and the display must follow
        # the same answer the push gate gives.
        device = {
            "supports_dsd": True,
            "capabilities": {"protocol_info": {"source": [], "sink": [], "mime_types": [], "supports_dsd": False}},
        }
        self.assertEqual(dsd_capability_state(device), DSD_CAPABILITY_UNSUPPORTED)
        self.assertFalse(device_supports_native_dsd(device))
        result, request = _push(device)
        self.assertFalse(result[0])
        self.assertIn("不支持源码 DSD", result[1])
        self.assertFalse(request.called)

    def test_the_push_gate_and_the_target_list_share_one_predicate(self):
        for label, device, _, push_allowed, display in TRUTH_TABLE:
            with self.subTest(shape=label):
                targets, _, _ = build_targets(
                    {"available": False, "output_capabilities": {}},
                    {"target_id": "local"},
                    [dict(device, id="renderer", name="Renderer", online=True)],
                    {},
                    {},
                    {},
                )
                self.assertEqual(targets[-1]["capabilities"]["native_dsd"], display)
                result, _ = _push(device)
                self.assertEqual(bool(result[0]), push_allowed)

    def test_garbage_inputs_cannot_be_read_as_support(self):
        for value in (None, "", 0, 1, [], object(), {"capabilities": {"protocol_info": "broken"}}):
            with self.subTest(value=repr(value)):
                self.assertEqual(dsd_capability_state(value), DSD_CAPABILITY_UNKNOWN)
                self.assertFalse(device_supports_native_dsd(value))


class SharedPredicateWiringTests(unittest.TestCase):
    """The unification must not be re-split by a later reader of the flat field."""

    # Resolved from this file so the assertions survive either runner CWD: the
    # offline gate discovers from src/, a focused run may start inside src/tests/.
    ROOT = pathlib.Path(__file__).resolve().parents[1] / "app" / "server"

    def _lines(self, relative):
        path = self.ROOT.joinpath(*relative)
        with io.open(str(path), encoding="utf-8") as handle:
            return handle.read().split("\n")

    def test_only_the_predicate_reads_the_capability_key(self):
        for relative in (("dlna", "media_server.py"), ("playback_targets_presentation.py",)):
            path = "/".join(relative)
            with self.subTest(module=path):
                for number, line in enumerate(self._lines(relative), 1):
                    self.assertNotIn("supports_dsd", line, "%s:%d" % (path, number))

    def test_control_point_only_writes_the_field_never_reads_it_back(self):
        allowed = {
            # the single probe record that observes the capability
            '"supports_dsd": bool(dsd_mimes.intersection(mime_types)),',
            # the derived display cache, produced by the shared predicate
            'device["supports_dsd"] = device_supports_native_dsd(device)',
            # the legacy name, which now delegates to that predicate
            "def device_supports_dsd(control):",
        }
        for number, line in enumerate(self._lines(("dlna", "control_point.py")), 1):
            if "supports_dsd" not in line:
                continue
            stripped = line.strip()
            with self.subTest(line=number):
                self.assertTrue(
                    stripped in allowed or stripped.startswith("#"),
                    "unexpected capability access at control_point.py:%d -> %s" % (number, stripped),
                )

    def test_the_predicate_is_the_only_reader_in_the_package(self):
        predicate = "\n".join(self._lines(("dlna", "profiles.py")))
        self.assertEqual(predicate.count('record.get("supports_dsd")'), 1)
        self.assertEqual(predicate.count('"supports_dsd" in record'), 1)

    def test_the_bool_view_delegates_instead_of_coercing_on_its_own(self):
        body = "\n".join(self._lines(("dlna", "profiles.py")))
        start = body.index("def device_supports_native_dsd(")
        end = body.index("def mime_for_item(", start)
        section = body[start:end]
        self.assertIn("dsd_capability_state(device) == DSD_CAPABILITY_SUPPORTED", section)
        self.assertNotIn("isinstance(value, bool)", section)

    def test_the_probe_shells_stop_reporting_a_refusal_they_never_observed(self):
        body = "\n".join(self._lines(("dlna", "control_point.py")))
        self.assertEqual(body.count('"supports_dsd": bool(dsd_mimes.intersection(mime_types))'), 1)
        self.assertEqual(body.count('"supports_dsd": False'), 0)
        self.assertNotIn('device["supports_dsd"] = False', body)


if __name__ == "__main__":
    unittest.main()
