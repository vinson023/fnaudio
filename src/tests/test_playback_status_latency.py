import contextlib
import inspect
import os
import sys
import tempfile
import unittest
from unittest import mock
from unittest.mock import patch

sys.path.insert(0, "app/server")

from playback import alsa_output
from playback.models import PlaybackState
from playback.mpd_output import MpdOutput
from services import mpd_service as mpd_module
from services.mpd_service import MpdService


CARDS = """ 0 [UD301           ]: USB-Audio - TEAC UD-301
                      TEAC Corporation TEAC UD-301 at usb-0000:00:14.0-2, high speed
 1 [PCH            ]: HDA-Intel - HDA Intel PCH
                      HDA Intel PCH at 0x6002120000 irq 187
"""

PCM = """00-00: USB Audio : USB Audio : playback 1
01-00: ALC897 Analog : ALC897 Analog : playback 1 : capture 1
01-03: HDMI 0 : HDMI 0 : playback 1
"""

# A real HDA codec dump runs to hundreds of lines and the kernel builds it by
# issuing one verb per codec node, so the header is all this fixture needs: the
# assertion is about whether the file was opened at all.
CODEC_DUMP = "Codec: Realtek ALC897\nAddress 0\nAFG Function Id: 0x1\n"


def _write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class _Tree:
    """A fake /proc/asound plus /sys/class/sound with one USB and one HDA card."""

    def __init__(self, tmp):
        self.proc = os.path.join(tmp, "proc")
        self.sys = os.path.join(tmp, "sys")
        usb_device = os.path.join(tmp, "usb_device")
        os.makedirs(self.proc)
        os.makedirs(self.sys)
        os.makedirs(usb_device)
        for name, value in {
            "idVendor": "0644",
            "idProduct": "804a",
            "serial": "UD301-SERIAL",
            "product": "TEAC UD-301",
        }.items():
            _write(os.path.join(usb_device, name), value)
        _write(os.path.join(self.proc, "cards"), CARDS)
        _write(os.path.join(self.proc, "pcm"), PCM)
        for card in ("card0", "card1"):
            os.makedirs(os.path.join(self.proc, card))
        _write(os.path.join(self.proc, "card0", "id"), "UD301")
        _write(os.path.join(self.proc, "card0", "stream0"), "TEAC UD-301 at usb-0000:00:14.0-2")
        _write(os.path.join(self.proc, "card1", "id"), "PCH")
        _write(os.path.join(self.proc, "card1", "codec#0"), CODEC_DUMP)
        os.makedirs(os.path.join(self.sys, "card0"))
        os.makedirs(os.path.join(self.sys, "card1"))
        os.symlink(usb_device, os.path.join(self.sys, "card0", "device"), target_is_directory=True)
        os.makedirs(os.path.join(self.sys, "card1", "device"))


class AlsaEnumerationCostTests(unittest.TestCase):
    """``alsa_devices()`` sits on the playback-status path, so it must stay cheap.

    Measured on the fnOS host (TEAC UD-301 attached, 62,684-song library) a
    single enumeration cost 362-558 ms, and cProfile put 1.856 s of its
    1.870 s inside ``_read_card_codecs``: six of the seven codec dumps read
    belonged to the on-board HDA lines that the result discards anyway because
    they are not USB devices.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tree = _Tree(self._tmp.name)
        self._env = patch.dict(
            os.environ,
            {
                "FNAUDIO_ASOUND_ROOT": self.tree.proc,
                "FNAUDIO_SYS_SOUND_ROOT": self.tree.sys,
            },
        )
        self._env.start()
        self.addCleanup(self._env.stop)
        self.read_cards = []
        original = alsa_output._read_card_codecs

        def spy(card):
            self.read_cards.append(str(card))
            return original(card)

        self._spy = patch.object(alsa_output, "_read_card_codecs", side_effect=spy)
        self._spy.start()
        self.addCleanup(self._spy.stop)

    def test_only_the_usb_card_ever_reaches_the_codec_dump(self):
        alsa_output.alsa_devices()
        self.assertEqual(self.read_cards, ["0"], self.read_cards)

    def test_the_usb_device_keeps_its_stable_identity(self):
        devices = alsa_output.alsa_devices()
        self.assertEqual([device["alsa_id"] for device in devices], ["hw:0,0"])
        self.assertTrue(devices[0]["is_usb"])
        self.assertEqual(devices[0]["name"], "TEAC UD-301")
        self.assertEqual(devices[0]["stable_id"], "usb:0644:804a:ud301-serial:dev0")
        self.assertEqual(devices[0]["id"], "dac:usb:0644:804a:ud301-serial:dev0")

    def test_a_usb_card_whose_pcm_line_does_not_spell_usb_still_survives(self):
        """The gate must ask exactly the question the code below it asks.

        A card is only identifiable as USB from ``cardN/stream*`` or its sysfs
        device path when the pcm line itself is generic, and both of those are
        keyed on the plain card digit; if the gate forwarded the zero-padded
        token from ``/proc/asound/pcm`` it would read paths that never exist,
        answer "not USB", and drop the owner's DAC from the target list.
        """
        _write(
            os.path.join(self.tree.proc, "cards"),
            " 0 [UD301           ]: Custom - TEAC UD-301\n",
        )
        _write(os.path.join(self.tree.proc, "pcm"), "00-00: Audio : Audio : playback 1\n")
        _write(os.path.join(self.tree.proc, "card0", "stream0"), "TEAC UD-301\n")

        devices = alsa_output.alsa_devices()

        self.assertEqual([device["alsa_id"] for device in devices], ["hw:0,0"], devices)
        self.assertTrue(devices[0]["is_usb"], devices[0])

    def _detached_tree(self):
        """Drop the sysfs fallback so only proc-file text can identify the card."""
        path = os.path.join(self.tree.sys, "card0", "device")
        os.remove(path)
        os.makedirs(path)
        return path

    def test_usbness_carried_only_by_the_stream_file_survives(self):
        """``cardN/stream*`` is one of the gate's inputs, not only the pcm line.

        On a host whose ``cardN/device`` link is not visible to the app, the
        stream description is the only place the card says USB, and the code
        below the gate learns it from the name that file produces.
        """
        self._detached_tree()
        _write(
            os.path.join(self.tree.proc, "cards"),
            " 0 [GEN0            ]: Generic - Generic Card\n",
        )
        _write(
            os.path.join(self.tree.proc, "pcm"),
            "00-00: Audio Playback : Audio Playback : playback 1\n",
        )
        _write(os.path.join(self.tree.proc, "card0", "stream0"), "TEAC USB\n")

        devices = alsa_output.alsa_devices()

        self.assertEqual([device["alsa_id"] for device in devices], ["hw:0,0"], devices)
        self.assertTrue(devices[0]["is_usb"], devices[0])

    def test_usbness_carried_only_by_the_card_name_survives(self):
        """The ``/proc/asound/cards`` name is visible without naming codecs."""
        self._detached_tree()
        _write(
            os.path.join(self.tree.proc, "cards"),
            " 0 [GEN0            ]: Generic - Generic USB DAC\n",
        )
        _write(os.path.join(self.tree.proc, "pcm"), "00-00: Audio : Audio : playback 1\n")
        for name in os.listdir(os.path.join(self.tree.proc, "card0")):
            if name.startswith("stream"):
                os.remove(os.path.join(self.tree.proc, "card0", name))

        devices = alsa_output.alsa_devices()

        self.assertEqual([device["alsa_id"] for device in devices], ["hw:0,0"], devices)
        self.assertTrue(devices[0]["is_usb"], devices[0])

    def test_is_usb_card_answers_from_text_before_touching_sysfs(self):
        """The gate stays cheap only because the text test comes first.

        ``_is_usb_card`` now runs for every enumeration line, so it must not
        need a sysfs node to recognise the wording the kernel writes into
        ``/proc/asound``.
        """
        self.assertTrue(alsa_output._is_usb_card("9", "09-00: USB Audio : USB Audio"))

    def test_a_skipped_line_could_never_have_been_a_returned_device(self):
        """Naming the HDA line would only add devices the ``is_usb`` filter drops.

        ``alsa_devices()`` filters on ``is_usb`` on both branches, so the gate
        cannot remove anything from the published list; this pins that the lines
        it skips really are the ones that would have been dropped a few
        statements later.
        """
        for line in PCM.splitlines():
            card = str(int(line.split("-")[0]))
            if card == "0":
                continue
            self.assertFalse(
                alsa_output._is_usb_card(
                    card,
                    line,
                    alsa_output._read_card_usb_name(card),
                    "HDA-Intel",
                    "PCH",
                ),
                line,
            )


class MpdOutputSnapshotCostTests(unittest.TestCase):
    """A core snapshot must not pay for log reads: callers hold the core lock."""

    class _Service:
        def __init__(self):
            self.calls = []

        def output_capabilities(self):
            return {}

        def status(self, light=False):
            self.calls.append(bool(light))
            return {"available": True, "running": True, "light": bool(light)}

    def setUp(self):
        self.service = self._Service()
        self.output = MpdOutput(service=self.service)

    def test_snapshot_requests_the_light_status(self):
        result = self.output.snapshot(PlaybackState())
        self.assertEqual(self.service.calls, [True], self.service.calls)
        self.assertTrue(result["mpd"]["light"])

    def test_status_still_defaults_to_the_full_probe_for_explicit_callers(self):
        self.output.status()
        self.assertEqual(self.service.calls, [False], self.service.calls)


class PlaybackStatusRouteWiringTests(unittest.TestCase):
    """Wiring pin for ``/api/playback/status``, which no unit test can reach.

    The route documents that ALSA capability probing and recent-log collection
    must never run in the request thread, yet it snapshotted the core twice per
    poll - once for the CUE check and again for the response - so every poll paid
    two extra full MPD statuses while holding the playback core lock, and four
    concurrent polls each waited 4.4-5.8 s. A source guard is the only way to
    see the duplicate come back.
    """

    def setUp(self):
        with open("app/server/server.py", encoding="utf-8") as source_file:
            source = source_file.read()
        start = source.index("def playback_status(payload_or_query):")
        end = source.index("device = find_upnp_device(target_id)", start)
        self.route = source[start:end]

    def test_the_mpd_branch_snapshots_the_core_once_per_state_change(self):
        # Every other branch of the route snapshots once for its own response;
        # only the two assignments below belong to the MPD branch, and the
        # second one is allowed to exist only inside the CUE auto-advance.
        self.assertEqual(
            self.route.count("core_snapshot = PLAYBACK_CORE.snapshot()"),
            2,
            self.route,
        )
        first = self.route.index("core_snapshot = PLAYBACK_CORE.snapshot()")
        second = self.route.index("core_snapshot = PLAYBACK_CORE.snapshot()", first + 1)
        self.assertLess(first, self.route.index("current_item = find_library_item("), self.route)
        self.assertGreater(second, self.route.index("CUE_AUTO_ADVANCE.update("), self.route)

    def test_the_response_is_built_from_the_reused_snapshot(self):
        self.assertIn("            status,\n            core_snapshot,", self.route)
        self.assertNotIn("            status,\n            PLAYBACK_CORE.snapshot(),", self.route)



MPD_HOST = "127.0.0.1"
MPD_PORT = 56660


def build_mpd_service():
    """Build the MPD service without discovery, without a data directory, without
    ever letting __init__ pick a real port."""
    with mock.patch.object(MpdService, "_select_port", return_value=MPD_PORT), mock.patch.object(
        MpdService, "_find_binary", return_value="/usr/bin/mpd"
    ):
        return MpdService({"library_paths": ["/vol2/1000/music"], "mpd_port": MPD_PORT})


def warm_setup(**overrides):
    setup = {
        "ok": True,
        "available": True,
        "config_path": "/tmp/mpd.conf",
        "output_device": {"stable_id": "dev0"},
        "dac_profile": {"startup_delay_ms": 1200},
        "host": MPD_HOST,
        "port": MPD_PORT,
        "mpd_nice": 0,
        "config_changed": False,
    }
    setup.update(overrides)
    return setup


class MpdWarmStartTests(unittest.TestCase):
    """F3: a transport command must not replay the cold MPD start sequence.

    Before this round every ``start()`` registered the child, waited for the ready
    handshake (which spawns ``mpd --version``), converged the index and refreshed
    status, even when the supervised MPD was already up and answering on its port.
    Combined with F1 that cost ~380 ms per control on top of the reap; the owner
    felt it as the USB DAC answering "half a beat late" on play, pause and track
    change.  Warm means "already exactly what start() would produce": the config we
    would write is unchanged on disk, our own child holds the port and speaks MPD,
    and the supervisor priority matches the configured nice.
    """

    def setUp(self):
        self.service = build_mpd_service()

    def run_start(self, setup, port_held=True, supervisor_status=None):
        status = supervisor_status or {"running": True, "pid": 4242, "nice": 0}
        service = self.service
        mocks = {}
        with contextlib.ExitStack() as stack:

            def enter(target, name, **kwargs):
                mocks[name] = stack.enter_context(mock.patch.object(target, name, **kwargs))

            enter(service, "_ensure_bindable_port")
            enter(service, "ensure_config", return_value=setup)
            enter(mpd_module.AUDIO_OUTPUT_LEASE, "acquire", return_value={"ok": True})
            enter(mpd_module.AUDIO_OUTPUT_LEASE, "release")
            enter(service, "_port_held_by_our_mpd", return_value=port_held)
            enter(service, "_managed_mpd_pid", return_value=int(status.get("pid") or 0))
            enter(service.supervisor, "status", return_value=status)
            enter(service.supervisor, "register")
            enter(service.supervisor, "start", return_value={"ok": True, "pid": 9999})
            enter(service.supervisor, "restart", return_value={"ok": True, "pid": 9999})
            enter(service, "_wait_ready", return_value={"running": True})
            enter(service, "_start_idle_listener")
            enter(service, "_start_device_monitor")
            enter(service, "_maybe_converge_mpd_index")
            enter(service, "refresh_status")
            enter(service, "_cleanup_stale_instances")
            mocks["result"] = service._start_locked()
        return mocks["result"], mocks

    def test_a_warm_mpd_skips_the_entire_cold_sequence(self):
        result, mocks = self.run_start(warm_setup())
        self.assertTrue(result["warm_start"], result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["running"])
        self.assertEqual(result["pid"], 4242, result)
        mocks["register"].assert_not_called()
        mocks["start"].assert_not_called()
        mocks["restart"].assert_not_called()
        mocks["_wait_ready"].assert_not_called()
        mocks["_maybe_converge_mpd_index"].assert_not_called()
        mocks["refresh_status"].assert_not_called()
        mocks["_cleanup_stale_instances"].assert_not_called()

    def test_a_warm_start_still_admits_the_companion_workers_and_the_lease(self):
        result, mocks = self.run_start(warm_setup())
        mocks["acquire"].assert_called_once_with("mpd", "dev0")
        mocks["_start_idle_listener"].assert_called_once_with()
        mocks["_start_device_monitor"].assert_called_once_with()
        mocks["release"].assert_not_called()
        self.assertTrue(result["warm_start"])

    def test_a_changed_configuration_falls_through_to_the_cold_sequence(self):
        result, mocks = self.run_start(warm_setup(config_changed=True))
        self.assertNotIn("warm_start", result)
        mocks["register"].assert_called_once()
        mocks["_wait_ready"].assert_called_once_with()
        mocks["_maybe_converge_mpd_index"].assert_called_once()
        mocks["refresh_status"].assert_called_once_with()
        # config_changed plus a running child is a restart, not a bare start.
        mocks["restart"].assert_called_once_with("mpd")
        mocks["start"].assert_not_called()

    def test_a_priority_that_does_not_match_the_config_falls_through(self):
        result, mocks = self.run_start(warm_setup(), supervisor_status={"running": True, "pid": 4242, "nice": 5})
        self.assertNotIn("warm_start", result)
        mocks["register"].assert_called_once()
        mocks["restart"].assert_called_once_with("mpd")

    def test_an_up_but_unanswered_port_is_never_treated_as_warm(self):
        result, mocks = self.run_start(warm_setup(), port_held=False)
        self.assertNotIn("warm_start", result)
        mocks["register"].assert_called_once()
        mocks["_wait_ready"].assert_called_once_with()

    def test_the_warm_response_keeps_every_field_the_cold_response_returns(self):
        setup = warm_setup()
        result, _mocks = self.run_start(setup)
        for key in ("available", "ok", "running", "host", "port", "output_device", "mpd_nice"):
            self.assertIn(key, result, result)
        self.assertEqual(result["host"], MPD_HOST)
        self.assertEqual(result["port"], MPD_PORT)
        self.assertEqual(result["output_device"], setup["output_device"])
        self.assertEqual(result["dac_profile"], setup["dac_profile"])

    def test_a_companion_worker_failure_rolls_the_lease_back_on_the_warm_path(self):
        service = self.service
        with contextlib.ExitStack() as stack:
            for target, name, kwargs in (
                (service, "_ensure_bindable_port", {}),
                (service, "ensure_config", {"return_value": warm_setup()}),
                (mpd_module.AUDIO_OUTPUT_LEASE, "acquire", {"return_value": {"ok": True}}),
                (mpd_module.AUDIO_OUTPUT_LEASE, "release", {}),
                (service, "_port_held_by_our_mpd", {"return_value": True}),
                (service.supervisor, "status", {"return_value": {"running": True, "pid": 4242, "nice": 0}}),
                (service, "_start_idle_listener", {}),
                (service, "_start_device_monitor", {"side_effect": RuntimeError("monitor refused")}),
            ):
                stack.enter_context(mock.patch.object(target, name, **kwargs))
            release = mock.patch.object(mpd_module.AUDIO_OUTPUT_LEASE, "release")
            released = stack.enter_context(release)
            with self.assertRaises(RuntimeError):
                service._start_locked()
        released.assert_called_once_with("mpd")

    def test_the_warm_guard_sits_between_the_lease_and_the_registration(self):
        body = inspect.getsource(MpdService._start_locked)
        acquire = body.find('AUDIO_OUTPUT_LEASE.acquire("mpd"')
        guard = body.find("self._mpd_is_warm(setup)")
        register = body.find("self.supervisor.register(")
        self.assertGreaterEqual(acquire, 0, body)
        self.assertGreaterEqual(guard, 0, "_start_locked has to consult the warm guard")
        self.assertGreaterEqual(register, 0, body)
        self.assertLess(acquire, guard, "DAC arbitration stays in front of the warm return")
        self.assertLess(guard, register, "a warm child must be recognised before it is re-registered")

    def test_the_warm_guard_requires_all_three_conditions(self):
        body = inspect.getsource(MpdService._mpd_is_warm)
        self.assertIn('setup.get("config_changed")', body)
        self.assertIn("self._port_held_by_our_mpd()", body)
        self.assertIn('self.supervisor.status("mpd")', body)
        self.assertLess(body.index('setup.get("config_changed")'), body.index("self._port_held_by_our_mpd()"))

if __name__ == "__main__":
    unittest.main()