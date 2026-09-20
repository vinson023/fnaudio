import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "unwired"))

from playback_session_contract import (CommandTicket, KeepAliveLease,
                                       PlaybackParticipant,
                                       PlaybackSessionSnapshot, MAX_COUNTER)


class PlaybackSessionContractTests(unittest.TestCase):
    def test_snapshot_is_bounded_and_serializable(self):
        participant = PlaybackParticipant(" p ", -2, -4, 1, "ctx")
        snapshot = PlaybackSessionSnapshot(-1, participant, " song ", 1, -5, "")
        value = snapshot.as_dict()
        self.assertEqual(value["revision"], 0)
        self.assertEqual(value["participant"]["id"], "p")
        self.assertEqual(value["position_ms"], 0)
        self.assertEqual(value["target_id"], "local")


    def test_command_ticket_rejects_stale_generation(self):
        participant = PlaybackParticipant("p", generation=2, engine_epoch=3)
        self.assertTrue(CommandTicket(participant_id="p", generation=2, engine_epoch=3).matches(participant))
        self.assertFalse(CommandTicket(participant_id="p", generation=1, engine_epoch=3).matches(participant))


    def test_keep_alive_lease_is_bounded_and_expires(self):
        lease = KeepAliveLease.issue("p", 999999)
        self.assertGreater(lease.expires_at, 0)
        self.assertTrue(lease.active(now=lease.expires_at - 0.1))
        self.assertFalse(lease.active(now=lease.expires_at + 0.1))

    def test_untrusted_counters_are_bounded_without_exceptions(self):
        participant = PlaybackParticipant("p", 2**99, object(), False, "ctx").bounded()
        self.assertEqual(participant.generation, MAX_COUNTER)
        self.assertEqual(participant.engine_epoch, 0)
        snapshot = PlaybackSessionSnapshot(object(), participant, "song", True, 2**99, "local").bounded()
        self.assertEqual(snapshot.revision, 0)
        self.assertEqual(snapshot.position_ms, MAX_COUNTER)

    def test_ticket_id_is_required_after_normalization(self):
        participant = PlaybackParticipant("p", 1, 2)
        self.assertFalse(CommandTicket(ticket_id=" ", participant_id="p", generation=1, engine_epoch=2).matches(participant))

    def test_keep_alive_lease_rejects_malformed_duration_and_clock(self):
        lease = KeepAliveLease.issue("p", object())
        self.assertTrue(lease.active(now=object()))
        self.assertIsInstance(lease.active(now=float("inf")), bool)

    def test_keep_alive_lease_bounds_nan_duration(self):
        lease = KeepAliveLease.issue("p", float("nan"))
        self.assertGreater(lease.expires_at, 0)
