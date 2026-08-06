from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time


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
    def from_mapping(cls, value: Dict[str, Any]) -> "TrackRef":
        return cls(
            track_id=str(value.get("id") or value.get("track_id") or ""),
            title=str(value.get("title") or ""),
            duration=float(value.get("duration") or 0),
            format=str(value.get("format") or ""),
            is_dsd=bool(value.get("is_dsd")),
            item=dict(value),
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
    updated_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
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
            "updated_at": self.updated_at,
        }
