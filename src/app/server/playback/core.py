from __future__ import annotations

from threading import Condition, RLock
from typing import Any, Dict, Iterable, Mapping, Optional
import math
import random
import uuid

from .models import PlaybackCommand, PlaybackState, TrackRef
from .plugins import BrowserOutput, OutputRegistry
from metadata_track_id_policy import normalize_track_id

MAX_QUEUE_TRACKS = 50000
MAX_SESSION_COUNTER = 2**31 - 1
MAX_COMMAND_TICKET = 128
MAX_EXTERNAL_URI = 8192
MAX_EXTERNAL_TEXT = 1024
MAX_EXTERNAL_ERROR = 2048
MAX_EXTERNAL_TRANSPORT = 64


def _bounded_track_refs(tracks):
    result = []
    try:
        iterator = iter(tracks)
    except Exception:
        return result
    while len(result) < MAX_QUEUE_TRACKS:
        try:
            track = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        try:
            projected = TrackRef.from_mapping(track)
        except Exception:
            continue
        if projected.track_id:
            result.append(projected)
    return result


def _append_bounded_track(queue, track):
    if len(queue) >= MAX_QUEUE_TRACKS:
        queue.pop(0)
    queue.append(track)


def _safe_payload_get(payload, key, default=None):
    if not isinstance(payload, Mapping):
        return default
    try:
        return payload.get(key, default)
    except Exception:
        return default


def _safe_nonnegative_float(value, default=0.0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if number >= 0 and number != float("inf") and number != float("-inf") else default


def _safe_optional_bool(value):
    return value if isinstance(value, bool) else None


def _bounded_text(value, limit):
    return value[:limit] if isinstance(value, str) else ""


def _plugin_result_accepted(result):
    """Keep legacy missing-ok responses while rejecting malformed results."""
    if not isinstance(result, dict):
        return False
    return "ok" not in result or result["ok"] is True


def _plugin_result_error(result):
    if not isinstance(result, dict):
        return "output returned an invalid response"
    message = result.get("message") or result.get("error") or ""
    return message if isinstance(message, str) else "output rejected the command"


class PlaybackCore:
    """Target-independent queue and session state machine."""

    def __init__(self, registry: Optional[OutputRegistry] = None):
        self.registry = registry or OutputRegistry([BrowserOutput()])
        self.state = PlaybackState(session_id=uuid.uuid4().hex)
        self._lock = RLock()
        self._changed = Condition(self._lock)

    def set_target(self, target_id: str, target_kind: str) -> PlaybackState:
        with self._lock:
            if self.state.target_id == target_id and self.state.target_kind == target_kind:
                return self.state
            self._plugin().close(self.state)
            self.state.target_id = target_id or "browser"
            self.state.target_kind = target_kind or "browser"
            self.state.playing = False
            self.state.transport = "STOPPED"
            self.state.position = 0.0
            self.state.error = ""
            self._touch()
            return self.state

    def set_session_identity(self, generation=0, engine_epoch=0, command_ticket="") -> PlaybackState:
        """Bind the latest client identity to the authoritative core state."""
        with self._lock:
            def counter(value):
                if isinstance(value, bool):
                    return 0
                try:
                    return max(0, min(int(value), MAX_SESSION_COUNTER))
                except (TypeError, ValueError, OverflowError):
                    return 0

            ticket = command_ticket.strip()[:MAX_COMMAND_TICKET] if isinstance(command_ticket, str) else ""
            next_generation = counter(generation)
            next_epoch = counter(engine_epoch)
            if (
                self.state.generation == next_generation
                and self.state.engine_epoch == next_epoch
                and self.state.command_ticket == ticket
            ):
                return self.state
            self.state.generation = next_generation
            self.state.engine_epoch = next_epoch
            self.state.command_ticket = ticket
            self._touch()
            return self.state

    def sync_output_status(
        self,
        target_kind: str,
        transport: str,
        position: Optional[float] = None,
        duration: Optional[float] = None,
        error: str = "",
    ) -> PlaybackState:
        """Merge an asynchronous backend snapshot into the global state.

        Output backends such as MPD and UPnP can change independently of the
        HTTP command that started them. Updates from a stale/non-selected
        backend are ignored so a late event cannot overwrite the active
        playback target.
        """
        with self._lock:
            if target_kind and self.state.target_kind != target_kind:
                return self.state
            normalized = str(transport or "UNKNOWN").upper()
            playing = self.state.playing
            if normalized == "PLAYING":
                playing = True
            elif normalized in ("PAUSED", "PAUSED_PLAYBACK", "STOPPED", "NO_MEDIA_PRESENT", "ERROR"):
                playing = False
            next_position = self.state.position
            if position is not None:
                next_position = _safe_position(position)
            next_duration = self.state.duration
            if duration is not None:
                next_duration = _safe_position(duration)
            next_error = str(error or "")
            if (
                self.state.transport == normalized
                and self.state.playing == playing
                and self.state.position == next_position
                and self.state.duration == next_duration
                and self.state.error == next_error
            ):
                return self.state
            self.state.transport = normalized
            self.state.playing = playing
            self.state.position = next_position
            self.state.duration = next_duration
            self.state.error = next_error
            self._touch()
            return self.state

    def select_current(self, track_id: str) -> PlaybackState:
        """Adopt a queue item selected autonomously by an output backend."""
        with self._lock:
            index = self._index_for(normalize_track_id(track_id))
            if index < 0:
                return self.state
            self.state.current_index = index
            self.state.current_track_id = self.state.queue[index].track_id
            self.state.position = 0.0
            self._sync_duration()
            self._touch()
            return self.state

    def set_queue(
        self,
        tracks: Iterable[Mapping[str, Any]],
        current: Optional[str] = None,
        repeat: Optional[str] = None,
        shuffle: Optional[bool] = None,
    ) -> PlaybackState:
        with self._lock:
            self.state.queue = _bounded_track_refs(tracks)
            current_id = normalize_track_id(current)
            self.state.current_track_id = current_id or (self.state.queue[0].track_id if self.state.queue else "")
            self.state.current_index = self._index_for(self.state.current_track_id)
            if repeat is not None:
                self.state.repeat = repeat if repeat in ("off", "all", "one") else "off"
            shuffle_value = _safe_optional_bool(shuffle)
            if shuffle_value is not None:
                self.state.shuffle = shuffle_value
            self._sync_duration()
            self._touch()
            return self.state

    def dispatch(self, command: PlaybackCommand) -> Dict[str, Any]:
        with self._lock:
            previous = {
                "queue": list(self.state.queue),
                "current_track_id": self.state.current_track_id,
                "current_index": self.state.current_index,
                "position": self.state.position,
                "duration": self.state.duration,
                "repeat": self.state.repeat,
                "shuffle": self.state.shuffle,
                "playing": self.state.playing,
                "transport": self.state.transport,
            }
            if command.action == "load" and command.track:
                # A library click can arrive before the frontend has mirrored
                # its queue. Keep the selected item in the authoritative
                # queue so MPD cannot accidentally replay a stale song id.
                if self._index_for(command.track.track_id) < 0:
                    _append_bounded_track(self.state.queue, command.track)
                self.state.current_track_id = command.track.track_id
                self.state.current_index = self._index_for(command.track.track_id)
                self.state.position = _safe_position(command.position)
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
                            projected = TrackRef.from_mapping(resolved)
                            # A resolver enriches a queue item; it must not
                            # replace its identity or create an unaddressable
                            # track when a library row disappeared meanwhile.
                            if projected.track_id == track.track_id:
                                track = projected
                    except Exception:
                        # Keep the queue state usable when an item was deleted during playback.
                        pass
                self.state.position = 0.0
                self.state.duration = track.duration
                result = self._plugin().open(track, self.state, command.context)
            elif command.action == "repeat":
                requested = (command.context or {}).get("repeat_value")
                # Keep direct API and legacy clients aligned with Volumio's
                # three repeat states: off -> queue -> current track -> off.
                if requested in ("off", "all", "one"):
                    self.state.repeat = requested
                else:
                    self.state.repeat = {"off": "all", "all": "one", "one": "off"}.get(
                        self.state.repeat,
                        "off",
                    )
                if self.state.target_kind == "mpd":
                    result = self._plugin().command(command, self.state, command.context)
                else:
                    result = {"repeat": self.state.repeat}
            elif command.action == "shuffle":
                requested = (command.context or {}).get("shuffle_value")
                self.state.shuffle = bool(requested) if isinstance(requested, bool) else not self.state.shuffle
                if self.state.target_kind == "mpd":
                    result = self._plugin().command(command, self.state, command.context)
                else:
                    result = {"shuffle": self.state.shuffle}
            else:
                result = self._plugin().command(command, self.state, command.context)
            succeeded = _plugin_result_accepted(result)
            if succeeded:
                self._apply_command(command)
            else:
                self.state.queue = previous["queue"]
                self.state.current_track_id = previous["current_track_id"]
                self.state.current_index = previous["current_index"]
                self.state.position = previous["position"]
                self.state.duration = previous["duration"]
                self.state.repeat = previous["repeat"]
                self.state.shuffle = previous["shuffle"]
                self.state.playing = previous["playing"]
                self.state.transport = previous["transport"]
                self.state.error = _plugin_result_error(result)
            self._touch()
            return {"ok": succeeded, "result": result, "state": self.state.to_dict()}

    def sync_frontend(self, payload: Mapping[str, Any]) -> PlaybackState:
        """Temporarily mirrors the 0.1.2 browser state during migration."""
        with self._lock:
            queue = _safe_payload_get(payload, "queue")
            if isinstance(queue, list) and queue and isinstance(queue[0], Mapping):
                self.state.queue = _bounded_track_refs(queue)
            current = _safe_payload_get(payload, "current")
            if isinstance(current, Mapping):
                current_id = normalize_track_id(_safe_payload_get(current, "id"))
                if current_id:
                    self.state.current_track_id = current_id
                self.state.duration = _safe_nonnegative_float(_safe_payload_get(current, "duration"))
            else:
                current_id = normalize_track_id(current)
                if current_id:
                    self.state.current_track_id = current_id
            if isinstance(payload, Mapping) and "repeat" in payload:
                repeat = _safe_payload_get(payload, "repeat")
                repeat = repeat if isinstance(repeat, str) else "off"
                self.state.repeat = repeat if repeat in ("off", "all", "one") else "off"
            if isinstance(payload, Mapping) and "shuffle" in payload:
                shuffle_value = _safe_optional_bool(_safe_payload_get(payload, "shuffle"))
                if shuffle_value is not None:
                    self.state.shuffle = shuffle_value
            self.state.current_index = self._index_for(self.state.current_track_id)
            if isinstance(payload, Mapping) and "playing" in payload:
                playing_value = _safe_optional_bool(_safe_payload_get(payload, "playing"))
                if playing_value is not None:
                    self.state.playing = playing_value
            self._sync_duration()
            self._touch()
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
            external_id = normalize_track_id(source_id) or "input"
            track_id = "external:%s" % external_id
            safe_title = _bounded_text(title, MAX_EXTERNAL_TEXT)
            safe_uri = _bounded_text(uri, MAX_EXTERNAL_URI)
            normalized_transport = _bounded_text(transport, MAX_EXTERNAL_TRANSPORT).upper() or "STOPPED"
            safe_duration = _safe_position(duration)
            self.state.queue = [TrackRef(track_id=track_id, title=safe_title, duration=safe_duration, item={"id": track_id, "title": safe_title, "uri": safe_uri, "external": True})] if safe_uri else []
            self.state.current_track_id = track_id if safe_uri else ""
            self.state.current_index = 0 if safe_uri else -1
            self.state.position = _safe_position(position)
            self.state.duration = safe_duration
            self.state.transport = normalized_transport
            self.state.playing = normalized_transport == "PLAYING"
            self.state.error = _bounded_text(error, MAX_EXTERNAL_ERROR)
            self._touch()
            return self.state

    def _current_item_locked(self) -> Dict[str, Any]:
        """Return the queue mapping for the current track without any I/O.

        Queue entries keep the library mapping they were built from, so CUE
        offsets are available at the point where a position is projected or a
        seek is dispatched.  ``current_index`` is maintained by every queue and
        transport mutation, so the O(1) hit is the normal case; the linear scan
        is only a guard against a stale index.
        """
        queue = self.state.queue
        track_id = self.state.current_track_id
        if not queue or not track_id:
            return {}
        index = self.state.current_index
        if isinstance(index, int) and 0 <= index < len(queue) and queue[index].track_id == track_id:
            item = queue[index].item
        else:
            position = self._index_for(track_id)
            item = queue[position].item if position >= 0 else {}
        return item if isinstance(item, dict) else {}

    def current_item(self) -> Dict[str, Any]:
        with self._lock:
            return self._current_item_locked()

    def snapshot_with_item(self):
        """Return ``(snapshot, current_item)`` while holding one lock.

        SSE projects the position through the CUE metadata of the current track.
        Reading the snapshot and the item separately could pair a new position
        with the offset of the previous track, so both come from the same critical
        section.
        """
        with self._lock:
            result = self.state.to_dict()
            result["output"] = self._plugin().snapshot(self.state)
            return result, self._current_item_locked()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            result = self.state.to_dict()
            result["output"] = self._plugin().snapshot(self.state)
            return result

    def wait_for_version(self, version: int, timeout: float = 15.0) -> int:
        """Block an event consumer until the authoritative state changes."""
        with self._changed:
            if self.state.state_version == int(version):
                try:
                    bounded_timeout = float(timeout)
                except (TypeError, ValueError, OverflowError):
                    bounded_timeout = 15.0
                if not math.isfinite(bounded_timeout):
                    bounded_timeout = 15.0
                self._changed.wait(max(0.0, bounded_timeout))
            return self.state.state_version

    def _touch(self) -> None:
        self.state.touch()
        self._changed.notify_all()

    def _plugin(self):
        plugin_id = self.state.target_id if self.registry.has(self.state.target_id) else self.state.target_kind
        return self.registry.get(plugin_id)

    def _apply_command(self, command: PlaybackCommand) -> None:
        if command.action in ("play", "resume", "load", "next", "previous"):
            self.state.playing = True
            self.state.transport = "PLAYING"
        elif command.action in ("pause", "stop"):
            self.state.playing = False
            self.state.transport = "PAUSED" if command.action == "pause" else "STOPPED"
        if command.action == "stop":
            self.state.position = 0.0
        elif command.action == "seek" and command.position is not None:
            self.state.position = _safe_position(command.position)

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


def _safe_position(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return max(0.0, number) if math.isfinite(number) else 0.0
