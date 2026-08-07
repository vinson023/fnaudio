import sys
import unittest

sys.path.insert(0, "app/server")

from playback.core import PlaybackCore
from playback.models import PlaybackCommand, TrackRef
from playback.plugins import BrowserOutput, OutputPlugin, OutputRegistry


class FailingOutput(OutputPlugin):
    plugin_id = "failing"
    target_kind = "failing"

    def open(self, track, state, context=None):
        return {"ok": False, "message": "output rejected track"}

    def command(self, command, state, context=None):
        return {"ok": False, "message": "output rejected command"}

    def close(self, state):
        return None

    def capabilities(self):
        return {}


class PlaybackCoreStateTests(unittest.TestCase):
    def test_failed_load_does_not_publish_optimistic_playing_state(self):
        core = PlaybackCore(OutputRegistry([BrowserOutput(), FailingOutput()]))
        core.set_target("failing", "failing")
        track = TrackRef.from_mapping({"id": "track-1", "title": "Track 1", "duration": 12})

        result = core.dispatch(PlaybackCommand("load", track=track, context={"item": track.item}))

        self.assertFalse(result["state"]["playing"])
        self.assertEqual(result["state"]["error"], "output rejected track")


if __name__ == "__main__":
    unittest.main()
