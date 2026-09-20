import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "app" / "server"))

from playback_session_policy import identity_is_stale, session_identity, ticket_matches


class PlaybackSessionPolicyTests(unittest.TestCase):
    def test_identity_is_bounded(self):
        self.assertEqual(session_identity({"generation": -1, "engine_epoch": 2**99}), {"generation": 0, "engine_epoch": 2**31 - 1})

    def test_ticket_matches_only_same_identity(self):
        identity = session_identity({"generation": 4, "engine_epoch": 9})
        self.assertTrue(ticket_matches({"generation": 4, "engine_epoch": 9}, identity))
        self.assertFalse(ticket_matches({"generation": 3, "engine_epoch": 9}, identity))

    def test_untrusted_values_are_rejected(self):
        self.assertFalse(ticket_matches(None, {"generation": 0, "engine_epoch": 0}))
        self.assertEqual(session_identity(object()), {"generation": 0, "engine_epoch": 0})

    def test_identity_staleness_is_monotonic_and_legacy_zero_is_allowed(self):
        self.assertTrue(identity_is_stale({"generation": 2, "engine_epoch": 1}, {"generation": 3, "engine_epoch": 0}))
        self.assertTrue(identity_is_stale({"generation": 3, "engine_epoch": 1}, {"generation": 3, "engine_epoch": 2}))
        self.assertFalse(identity_is_stale({"generation": 4, "engine_epoch": 0}, {"generation": 3, "engine_epoch": 99}))
        self.assertFalse(identity_is_stale({}, {"generation": 3, "engine_epoch": 2}))
