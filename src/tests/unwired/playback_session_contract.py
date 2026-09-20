"""Bounded, transport-neutral playback session contract.

This is fnAudio's equivalent of the host/participant protocol used by the
official client.  It deliberately contains no Android, Flutter or Pigeon
types so browser, Android and remote renderers can share the same semantics.
"""

from dataclasses import dataclass, field
from math import isfinite
from time import time
from uuid import uuid4

MAX_ID = 128
MAX_LEASE_SECONDS = 24 * 60 * 60
MAX_COUNTER = 2**31 - 1


def _lease_seconds(value, default=30):
    """Normalize untrusted keep-alive durations without raising."""
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not isfinite(number):
        return default
    return min(MAX_LEASE_SECONDS, max(1, int(number)))


def _clock(value):
    """Normalize optional clock values used by recovery checks."""
    if value is None:
        return time()
    if isinstance(value, bool):
        return time()
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return time()
    return number if isfinite(number) else time()


def _text(value, limit=MAX_ID):
    return value.strip()[:limit] if isinstance(value, str) else ""


def _counter(value):
    """Normalize untrusted session counters without allowing exceptions."""
    if isinstance(value, bool):
        return 0
    try:
        return max(0, min(int(value), MAX_COUNTER))
    except (TypeError, ValueError, OverflowError):
        return 0


@dataclass(frozen=True)
class PlaybackParticipant:
    participant_id: str
    generation: int = 0
    engine_epoch: int = 0
    supports_background: bool = False
    media_context_id: str = ""

    def bounded(self):
        return PlaybackParticipant(
            _text(self.participant_id),
            _counter(self.generation),
            _counter(self.engine_epoch),
            bool(self.supports_background),
            _text(self.media_context_id),
        )


@dataclass(frozen=True)
class PlaybackSessionSnapshot:
    revision: int
    participant: PlaybackParticipant
    current_id: str = ""
    playing: bool = False
    position_ms: int = 0
    target_id: str = "local"

    def bounded(self):
        p = self.participant.bounded()
        return PlaybackSessionSnapshot(
            _counter(self.revision), p, _text(self.current_id), bool(self.playing),
            _counter(self.position_ms), _text(self.target_id) or "local",
        )

    def as_dict(self):
        value = self.bounded()
        return {
            "revision": value.revision,
            "participant": {
                "id": value.participant.participant_id,
                "generation": value.participant.generation,
                "engine_epoch": value.participant.engine_epoch,
                "supports_background": value.participant.supports_background,
                "media_context_id": value.participant.media_context_id,
            },
            "current_id": value.current_id,
            "playing": value.playing,
            "position_ms": value.position_ms,
            "target_id": value.target_id,
        }


@dataclass(frozen=True)
class KeepAliveLease:
    lease_id: str
    participant_id: str
    expires_at: float

    @classmethod
    def issue(cls, participant_id, seconds=30):
        seconds = _lease_seconds(seconds)
        return cls(uuid4().hex, _text(participant_id), time() + seconds)

    def active(self, now=None):
        expires_at = _clock(self.expires_at)
        return bool(self.lease_id and self.participant_id and _clock(now) < expires_at)


@dataclass(frozen=True)
class CommandTicket:
    ticket_id: str = field(default_factory=lambda: uuid4().hex)
    participant_id: str = ""
    generation: int = 0
    engine_epoch: int = 0

    def matches(self, participant: PlaybackParticipant):
        p = participant.bounded()
        return bool(_text(self.ticket_id)) and _text(self.participant_id) == p.participant_id and _counter(self.generation) == p.generation and _counter(self.engine_epoch) == p.engine_epoch


__all__ = ["MAX_COUNTER", "PlaybackParticipant", "PlaybackSessionSnapshot", "KeepAliveLease", "CommandTicket"]
