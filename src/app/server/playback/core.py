from __future__ import annotations

from threading import RLock
from typing import Any, Dict, Iterable, Mapping, Optional
import random
import uuid

from .models import PlaybackCommand, PlaybackState, TrackRef
from .plugins import BrowserOutput, OutputRegistry


class PlaybackCore:
    """Target-independent queue and session state machine."""

    def __init__(self, registry: Optional[OutputRegistry] = None):
        self.registry = registry or OutputRegistry([BrowserOutput()])
        self.state = PlaybackState(session_id=uuid.uuid4().hex)
        self._lock = RLock()

    def set_target(self, target_id: str, target_kind: str) -> PlaybackState:
        with self._lock:
            if self.state.target_id == target_id and self.state.target_kind == target_kind:
                return self.state
            self._plugin().close(self.state)
            self.state.target_id = target_id or "browser"
            self.state.target_kind = target_kind or "browser"
            self.state.playing = False
            self.state.position = 0.0
            self.state.error = ""
            self.state.touch()
            return self.state

    def set_queue(
        self,
        tracks: Iterable[Mapping[str, Any]],
        current: Optional[str] = None,
        repeat: Optional[str] = None,
        shuffle: Optional[bool] = None,
    ) -> PlaybackState:
        with self._lock:
            self.state.queue = [TrackRef.from_mapping(track) for track in tracks]
            self.state.current_track_id = current or (
                self.state.queue[0].track_id if self.state.queue else ""
            )
            self.state.current_index = self._index_for(self.state.current_track_id)
            if repeat is not None:
                self.state.repeat = repeat if repeat in ("off", "all", "one") else "off"
            if shuffle is not None:
                self.state.shuffle = bool(shuffle)
            self._sync_duration()
            self.state.touch()
            return self.state

    def dispatch(self, command: PlaybackCommand) -> Dict[str, Any]:
        with self._lock:
            if command.action == "load" and command.track:
                self.state.current_track_id = command.track.track_id
                self.state.current_index = self._index_for(command.track.track_id)
                self.state.position = 0.0
                self.state.duration = command.track.duration
                result = self._plugin().open(command.track, self.state, command.context)
            elif command.action in ("next", "previous"):
                track = self.next_track() if command.action == "next" else self.previous_track()
                if not track:
                    return {"ok": False, "result": {"error": "no track"}, "state": self.state.to_dict()}
                resolver = (command.context or {}).get("resolve_track")
                if callable(resolver):
                    try:
                        resolved = resolver(track.track_id)
                        if isinstance(resolved, Mapping):
                            track = TrackRef.from_mapping(resolved)
                    except Exception:
                        # Keep the queue state usable when an item was deleted during playback.
                        pass
                self.state.position = 0.0
                self.state.duration = track.duration
                result = self._plugin().open(track, self.state, command.context)
            elif command.action == "repeat":
                self.state.repeat = "off" if self.state.repeat == "all" else "all"
                result = {"repeat": self.state.repeat}
            elif command.action == "shuffle":
                self.state.shuffle = not self.state.shuffle
                result = {"shuffle": self.state.shuffle}
            else:
                result = self._plugin().command(command, self.state, command.context)
            succeeded = not (isinstance(result, dict) and result.get("ok") is False)
            if succeeded:
                self._apply_command(command)
            else:
                self.state.playing = False
                self.state.error = str(result.get("message") or result.get("error") or "")
            self.state.touch()
            return {"ok": True, "result": result, "state": self.state.to_dict()}

    def sync_frontend(self, payload: Mapping[str, Any]) -> PlaybackState:
        """Temporarily mirrors the 0.1.2 browser state during migration."""
        with self._lock:
            queue = payload.get("queue")
            if isinstance(queue, list) and queue and isinstance(queue[0], Mapping):
                self.state.queue = [TrackRef.from_mapping(item) for item in queue]
            current = payload.get("current")
            if isinstance(current, Mapping):
                self.state.current_track_id = str(current.get("id") or "")
                self.state.duration = float(current.get("duration") or 0)
            elif current:
                self.state.current_track_id = str(current)
            if "repeat" in payload:
                repeat = str(payload.get("repeat") or "off")
                self.state.repeat = repeat if repeat in ("off", "all", "one") else "off"
            if "shuffle" in payload:
                self.state.shuffle = bool(payload.get("shuffle"))
            self.state.current_index = self._index_for(self.state.current_track_id)
            if "playing" in payload:
                self.state.playing = bool(payload.get("playing"))
            self._sync_duration()
            self.state.touch()
            return self.state

    def sync_external_session(
        self,
        source_id: str,
        title: str,
        uri: str,
        transport: str,
        position: float = 0.0,
        duration: float = 0.0,
        target_id: str = "mpd",
        error: str = "",
    ) -> PlaybackState:
        """Mirror an incoming renderer session without making it a UI queue.

        DLNA control points provide a network URI instead of a fnAudio library
        item. Keeping it as a one-item external session preserves the single
        playback state machine while leaving AVTransport parsing outside it.
        """
        with self._lock:
            # Unit and recovery modes can run the core before optional MPD is
            # registered. Keep the session observable instead of making a
            # status request fail because an output plugin is absent.
            selected_target = target_id if self.registry.has(target_id) else self.state.target_id
            selected_kind = "mpd" if self.registry.has(selected_target) else self.state.target_kind
            self.set_target(selected_target, selected_kind)
            track_id = "external:%s" % str(source_id or "input")
            self.state.queue = [TrackRef(track_id=track_id, title=title, duration=max(0.0, float(duration or 0)), item={"id": track_id, "title": title, "uri": uri, "external": True})] if uri else []
            self.state.current_track_id = track_id if uri else ""
            self.state.current_index = 0 if uri else -1
            self.state.position = max(0.0, float(position or 0))
            self.state.duration = max(0.0, float(duration or 0))
            self.state.playing = str(transport or "").upper() == "PLAYING"
            self.state.error = str(error or "")
            self.state.touch()
            return self.state

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            result = self.state.to_dict()
            result["output"] = self._plugin().snapshot(self.state)
            return result

    def _plugin(self):
        plugin_id = self.state.target_id if self.registry.has(self.state.target_id) else self.state.target_kind
        return self.registry.get(plugin_id)

    def _apply_command(self, command: PlaybackCommand) -> None:
        if command.action in ("play", "resume", "load", "next", "previous"):
            self.state.playing = True
        elif command.action in ("pause", "stop"):
            self.state.playing = False
        if command.action == "stop":
            self.state.position = 0.0
        elif command.action == "seek" and command.position is not None:
            self.state.position = max(0.0, float(command.position))

    def _sync_duration(self) -> None:
        current = next(
            (track for track in self.state.queue if track.track_id == self.state.current_track_id),
            None,
        )
        if current:
            self.state.duration = current.duration

    def _index_for(self, track_id: str) -> int:
        return next((idx for idx, track in enumerate(self.state.queue) if track.track_id == track_id), -1)

    def next_track(self) -> Optional[TrackRef]:
        if not self.state.queue:
            return None
        if self.state.repeat == "one" and self.state.current_index >= 0:
            return self.state.queue[self.state.current_index]
        if self.state.shuffle and len(self.state.queue) > 1:
            choices = [idx for idx in range(len(self.state.queue)) if idx != self.state.current_index]
            self.state.current_index = random.choice(choices)
        elif self.state.current_index < len(self.state.queue) - 1:
            self.state.current_index += 1
        elif self.state.repeat == "all":
            self.state.current_index = 0
        else:
            return None
        self.state.current_track_id = self.state.queue[self.state.current_index].track_id
        return self.state.queue[self.state.current_index]

    def previous_track(self) -> Optional[TrackRef]:
        if not self.state.queue:
            return None
        if self.state.current_index > 0:
            self.state.current_index -= 1
        elif self.state.repeat == "all":
            self.state.current_index = len(self.state.queue) - 1
        else:
            return None
        self.state.current_track_id = self.state.queue[self.state.current_index].track_id
        return self.state.queue[self.state.current_index]
