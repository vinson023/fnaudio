from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time

from metadata_track_id_policy import normalize_track_id


MAX_TRACK_TEXT = 512


def _mapping_value(value: Any, key: str, default=None):
    if not isinstance(value, Mapping):
        return default
    try:
        return value.get(key, default)
    except Exception:
        return default


def _track_text(value: Any, limit: int = MAX_TRACK_TEXT) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _track_duration(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    try:
        duration = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return duration if math.isfinite(duration) and duration >= 0 else 0.0


def _track_item(value: Any) -> Dict[str, Any]:
    """Copy a mapping only when it can be safely materialized."""
    if not isinstance(value, Mapping):
        return {}
    try:
        return dict(value)
    except Exception:
        return {}


@dataclass(frozen=True)
class TrackRef:
    """Small track identity shared by the core and output plugins."""

    track_id: str
    title: str = ""
    duration: float = 0.0
    format: str = ""
    is_dsd: bool = False
    item: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TrackRef":
        track_id = normalize_track_id(_mapping_value(value, "id"))
        if not track_id:
            track_id = normalize_track_id(_mapping_value(value, "track_id"))
        return cls(
            track_id=track_id,
            title=_track_text(_mapping_value(value, "title")),
            duration=_track_duration(_mapping_value(value, "duration")),
            format=_track_text(_mapping_value(value, "format")),
            is_dsd=_mapping_value(value, "is_dsd") is True,
            item=_track_item(value),
        )


@dataclass(frozen=True)
class PlaybackCommand:
    action: str
    position: Optional[float] = None
    track: Optional[TrackRef] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlaybackState:
    session_id: str = ""
    # Client session identity is carried by every authoritative snapshot.
    # Keeping it in the core prevents SSE, polling and command responses from
    # disagreeing about which host/player instance produced the state.
    generation: int = 0
    engine_epoch: int = 0
    command_ticket: str = ""
    target_id: str = "browser"
    target_kind: str = "browser"
    queue: List[TrackRef] = field(default_factory=list)
    current_track_id: str = ""
    current_index: int = -1
    repeat: str = "off"
    shuffle: bool = False
    playing: bool = False
    position: float = 0.0
    duration: float = 0.0
    error: str = ""
    transport: str = "STOPPED"
    state_version: int = 0
    updated_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.state_version += 1
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "generation": self.generation,
            "engine_epoch": self.engine_epoch,
            "command_ticket": self.command_ticket,
            "target_id": self.target_id,
            "target_kind": self.target_kind,
            "queue": [track.track_id for track in self.queue],
            "current": self.current_track_id or None,
            "current_index": self.current_index,
            "repeat": self.repeat,
            "shuffle": self.shuffle,
            "playing": self.playing,
            "position": self.position,
            "duration": self.duration,
            "error": self.error,
            "transport": self.transport,
            "state_version": self.state_version,
            "updated_at": self.updated_at,
        }
