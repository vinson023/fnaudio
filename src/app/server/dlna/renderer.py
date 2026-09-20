from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock, Thread
from typing import Any, Callable, Dict
import math
import time
from .next_queue import MAX_NEXT_QUEUE_ENTRIES, bounded_next_queue
from .backend_schedule import BackendOperation, schedule_latest, take_latest
from .renderer_presentation import metadata_fields, normalize_renderer_media

MAX_RENDERER_SEEK_SECONDS = 24 * 60 * 60


def _backend_result(result: Any) -> Dict[str, Any]:
    """Expose backend control results with a stable success contract."""
    source = result if isinstance(result, dict) else {}
    projected = dict(source)
    projected["ok"] = source.get("ok") is True
    return projected


def _safe_position(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 0.0
    if isinstance(value, str) and len(value) > 64:
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return max(0.0, number) if math.isfinite(number) else 0.0


@dataclass
class DlnaRendererState:
    uri: str = ""
    metadata: str = ""
    title: str = ""
    artist: str = ""
    art_url: str = ""
    next_uri: str = ""
    next_metadata: str = ""
    next_queue: list[Dict[str, str]] = field(default_factory=list)
    next_queue_dropped: int = 0
    transport: str = "STOPPED"
    position: float = 0.0
    duration: float = 0.0
    volume: int = 100
    muted: bool = False
    last_error: str = ""
    updated_at: float = field(default_factory=time.time)


class DlnaRenderer:
    """DLNA MediaRenderer transport facade.

    The class owns the UPnP-facing state only. Playback is delegated through
    injected callbacks, so incoming DLNA control never becomes a second local
    player implementation.
    """

    def __init__(
        self,
        load_uri: Callable[[str, float], Dict[str, Any]],
        control: Callable[[str, float | None], Dict[str, Any]],
        status: Callable[[], Dict[str, Any]],
        on_state_change: Callable[[Dict[str, Any]], None] | None = None,
    ):
        self._load_uri = load_uri
        self._control = control
        self._status = status
        self._on_state_change = on_state_change
        self._listeners: list[Callable[[Dict[str, Any]], None]] = []
        self._lock = RLock()
        # Transport commands are coalesced through the worker below, while
        # volume calls retain their synchronous response contract. Serialize
        # the actual backend I/O so those two paths cannot enter MPD together.
        self._backend_io_lock = RLock()
        self._load_generation = 0
        self._loading_uri = ""
        # UPnP controllers can issue bursts of Play/Pause/Seek calls.  Keep
        # at most one backend thread and coalesce the pending operation to
        # the newest generation instead of creating unbounded threads blocked
        # behind a backend lock.
        self._backend_worker_active = False
        self._backend_pending: BackendOperation | None = None
        self._backend_coalesced = 0
        # MPD status can briefly remain STOPPED after accepting an HTTP source.
        # Do not let that stale value erase a new AVTransport session before
        # the backend has ever reported it active.
        self._backend_active_observed = False
        self.state = DlnaRendererState()

    def set_uri(self, uri: str, metadata: str = "") -> None:
        safe_uri, safe_metadata = normalize_renderer_media(uri, metadata)
        with self._lock:
            self.state.uri = safe_uri
            self.state.metadata = safe_metadata
            self.state.title, self.state.artist, self.state.art_url = metadata_fields(safe_metadata, safe_uri)
            self.state.transport = "STOPPED"
            self.state.position = 0.0
            self.state.duration = 0.0
            self.state.last_error = ""
            self._load_generation += 1
            self._loading_uri = ""
            self._backend_active_observed = False
            self.state.updated_at = time.time()
        self._notify()

    def set_next_uri(self, uri: str, metadata: str = "") -> None:
        with self._lock:
            # Do not retain arbitrary controller input or an unbounded chain
            # of preloaded URIs. The policy preserves FIFO and empty-URI clear
            # semantics used by normal AVTransport clients.
            safe_uri = uri if isinstance(uri, str) else ""
            safe_metadata = metadata if isinstance(metadata, str) else ""
            queue, accepted = bounded_next_queue(self.state.next_queue, safe_uri, safe_metadata)
            self.state.next_queue = queue
            if not accepted:
                self.state.next_queue_dropped = min(1_000_000_000, self.state.next_queue_dropped + 1)
            self._sync_next_fields()
            self.state.updated_at = time.time()
        self._notify()

    def add_state_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._listeners.append(callback)

    def play(self) -> Dict[str, Any]:
        """Acknowledge Play before a remote stream is opened by MPD.

        Several controllers, including Synology Media Server, close their SOAP
        request quickly when the renderer blocks while MPD resolves an HTTP
        source. UPnP transport commands must remain responsive, so loading is
        performed in a worker and the final transport state is published once
        MPD accepts or rejects the URI.
        """
        with self._lock:
            if not self.state.uri:
                return {"ok": False, "message": "no transport URI"}
            if self._loading_uri == self.state.uri:
                return {"ok": True, "queued": True}
            uri = self.state.uri
            position = self.state.position
            self._load_generation += 1
            generation = self._load_generation
            self._loading_uri = uri
            self.state.transport = "TRANSITIONING"
            self.state.last_error = ""
            self.state.updated_at = time.time()
        self._notify()
        self._schedule_backend("load", generation, uri=uri, load_position=position)
        return {"ok": True, "queued": True}

    def _load_in_background(self, generation: int, uri: str, position: float) -> None:
        # Serializing MPD work keeps an older source load from racing a later
        # Stop or Next command.
        with self._lock:
            if generation != self._load_generation or uri != self.state.uri:
                return
        try:
            with self._backend_io_lock:
                result = _backend_result(self._load_uri(uri, position))
        except Exception as exc:
            result = {"ok": False, "message": str(exc)}
        with self._lock:
            stale = generation != self._load_generation or uri != self.state.uri
        if stale:
            # The latest action is coalesced in the single backend worker and
            # becomes the only final command after this obsolete load exits.
            return
        with self._lock:
            self._loading_uri = ""
            if result.get("ok") is not True:
                self.state.transport = "STOPPED"
                self.state.last_error = str(result.get("message") or "unable to load source")
            else:
                self.state.transport = "PLAYING"
                self.state.last_error = ""
            self.state.updated_at = time.time()
        self._notify()

    def command(self, action: str, position: float | None = None) -> Dict[str, Any]:
        if not isinstance(action, str):
            return {"ok": False, "message": "invalid action"}
        action = action.strip().lower()
        if action not in {"play", "pause", "stop", "next", "previous", "seek"}:
            return {"ok": False, "message": "unsupported action"}
        if action == "seek" and position is None:
            return {"ok": False, "message": "invalid seek position"}
        if action == "seek":
            try:
                position = float(position)
            except (TypeError, ValueError, OverflowError):
                return {"ok": False, "message": "invalid seek position"}
            if not math.isfinite(position) or position < 0 or position > MAX_RENDERER_SEEK_SECONDS:
                return {"ok": False, "message": "invalid seek position"}
        if action == "play":
            # play() publishes state first and then notifies and schedules the
            # load outside its own lock window. Reaching it through the command
            # lock below would run every listener, including Playback Core,
            # while the renderer lock is held.
            return self.play()
        next_entry = None
        with self._lock:
            if action == "next" and self.state.next_queue:
                next_entry = self.state.next_queue.pop(0)
                self._sync_next_fields()
                self.state.updated_at = time.time()
        if next_entry is not None:
            # Do not invoke notifications or backend admission while the
            # command lock is held. A listener may perform another control
            # request, and a slow listener must not block unrelated commands.
            self._notify()
            self.set_uri(next_entry["uri"], next_entry["metadata"])
            return self.play()
        with self._lock:
            self._load_generation += 1
            generation = self._load_generation
            self._loading_uri = ""
            if action == "pause":
                self.state.transport = "PAUSED_PLAYBACK"
            elif action == "stop":
                self.state.transport = "STOPPED"
                self.state.position = 0.0
            elif action == "seek" and position is not None:
                self.state.position = max(0.0, position)
            self.state.updated_at = time.time()
        self._notify()
        self._schedule_backend("control", generation, action=action, control_position=position)
        return {"ok": True, "queued": True}

    def _control_in_background(self, generation: int, action: str, position: float | None) -> None:
        with self._lock:
            if generation != self._load_generation:
                return
        try:
            with self._backend_io_lock:
                result = _backend_result(self._control(action, position))
        except Exception as exc:
            result = {"ok": False, "message": str(exc)}
        if result.get("ok") is not True:
            with self._lock:
                if generation == self._load_generation:
                    self.state.last_error = str(result.get("message") or "playback control failed")
                    self.state.updated_at = time.time()
            self._notify()

    def _schedule_backend(
        self,
        kind: str,
        generation: int,
        uri: str = "",
        load_position: float = 0.0,
        action: str = "",
        control_position: float | None = None,
    ) -> None:
        """Queue only the latest backend command under the worker-state lock."""
        operation = BackendOperation(kind, generation, uri, load_position, action, control_position)
        with self._lock:
            # State is published before backend admission so UPnP controllers
            # get a prompt response. A notification callback can interleave a
            # newer command in that gap; never let the delayed older operation
            # replace the newer pending backend work.
            if generation != self._load_generation:
                return
            self._backend_worker_active, self._backend_pending, self._backend_coalesced, start_worker = schedule_latest(
                self._backend_worker_active, self._backend_pending, self._backend_coalesced, operation
            )
            if start_worker:
                try:
                    Thread(target=self._run_backend_worker, name="fnaudio-dlna-renderer-backend", daemon=True).start()
                except Exception:
                    # The operation remains pending so the next controller
                    # command can retry it, but the failed start must release
                    # the single-worker latch or future commands would queue
                    # behind a worker that never existed.
                    self._backend_worker_active = False
                    raise

    def _run_backend_worker(self) -> None:
        while True:
            with self._lock:
                operation = take_latest(self._backend_pending)
                self._backend_pending = None
                if operation is None:
                    self._backend_worker_active = False
                    return
            if operation.kind == "load":
                self._load_in_background(operation.generation, operation.uri, operation.load_position)
            else:
                self._control_in_background(operation.generation, operation.action, operation.control_position)

    def set_volume(self, volume: int) -> Dict[str, Any]:
        if isinstance(volume, bool):
            return {"ok": False, "message": "invalid volume"}
        try:
            numeric_volume = float(volume)
        except (TypeError, ValueError, OverflowError):
            return {"ok": False, "message": "invalid volume"}
        if not math.isfinite(numeric_volume) or not numeric_volume.is_integer():
            return {"ok": False, "message": "invalid volume"}
        volume = max(0, min(100, int(numeric_volume)))
        with self._lock:
            muted = self.state.muted
        if muted:
            with self._lock:
                self.state.volume = volume
                self.state.updated_at = time.time()
            self._notify()
            return {"ok": True, "deferred": True}
        try:
            with self._backend_io_lock:
                result = _backend_result(self._control("volume", float(volume)))
        except Exception as exc:
            return {"ok": False, "message": str(exc) or "volume control failed"}
        if result.get("ok") is True:
            with self._lock:
                self.state.volume = volume
                self.state.updated_at = time.time()
            self._notify()
        return result

    def set_mute(self, muted: bool) -> Dict[str, Any]:
        if not isinstance(muted, bool):
            return {"ok": False, "message": "invalid mute"}
        with self._lock:
            if self.state.muted == muted:
                return {"ok": True}
            target_volume = 0 if muted else self.state.volume
        try:
            with self._backend_io_lock:
                result = _backend_result(self._control("volume", float(target_volume)))
        except Exception as exc:
            return {"ok": False, "message": str(exc) or "mute control failed"}
        if result.get("ok") is True:
            with self._lock:
                self.state.muted = muted
                self.state.updated_at = time.time()
            self._notify()
        return result

    def snapshot(self) -> Dict[str, Any]:
        notify = False
        with self._lock:
            result = self._project_state_locked()
            status_generation = self._load_generation
        try:
            backend = self._status() or {}
            transport = backend.get("transport") or {}
            position = backend.get("position") or {}
            raw = backend.get("raw") or {}
            backend_error = str(raw.get("error") or "").strip()
            backend_transport = str(transport.get("state") or "").upper()
            # Preserve the UPnP session while MPD has not yet confirmed a
            # start. Once MPD reports PLAYING/PAUSED, its later STOPPED state
            # is authoritative, including natural end-of-track.
            with self._lock:
                if status_generation != self._load_generation:
                    # The backend read raced a newer URI/control command.
                    # Never project the old MPD snapshot onto the new session.
                    return self._project_state_locked()
                if backend_transport in ("PLAYING", "PAUSED_PLAYBACK", "PAUSED"):
                    self._backend_active_observed = True
                    result["transport"] = backend_transport
                    result["position"] = _safe_position(position.get("rel_seconds"))
                    result["duration"] = _safe_position(position.get("duration_seconds"))
                elif backend_transport == "STOPPED" and (
                    result["transport"] == "STOPPED" or self._backend_active_observed
                ):
                    self._backend_active_observed = False
                    result["transport"] = "STOPPED"
                    result["position"] = 0.0
                    result["duration"] = _safe_position(position.get("duration_seconds"))
                if backend_error and result["transport"] != "STOPPED":
                    # MPD accepts a play command before ALSA/network output
                    # can fail. Surface that asynchronous failure to both the
                    # DLNA controller and Playback Core instead of leaving a
                    # permanently optimistic PLAYING state.
                    self.state.transport = "STOPPED"
                    self.state.position = 0.0
                    self.state.last_error = backend_error
                    self.state.updated_at = time.time()
                    self._backend_active_observed = False
                    result.update({
                        "transport": "STOPPED",
                        "position": 0.0,
                        "last_error": backend_error,
                        "updated_at": self.state.updated_at,
                    })
                    notify = True
            if raw.get("volume") is not None:
                volume = float(raw["volume"])
                if math.isfinite(volume):
                    result["volume"] = max(0, min(100, int(volume)))
        except Exception:
            pass
        if notify:
            self._notify()
        return result

    def _state_copy_locked(self) -> Dict[str, Any]:
        """Copy renderer state. The caller must hold the lock.

        ``next_queue`` is popped in place by command("next"), so anything that
        leaves the lock window (a status projection, or a state dict handed to
        a listener) must get its own list and entries or it can change
        underneath the reader.
        """
        result = dict(self.state.__dict__)
        result["next_queue"] = [dict(entry) for entry in self.state.next_queue]
        return result

    def _project_state_locked(self) -> Dict[str, Any]:
        result = self._state_copy_locked()
        result["next_queue_limit"] = MAX_NEXT_QUEUE_ENTRIES
        result["backend_worker_active"] = self._backend_worker_active
        result["backend_pending"] = self._backend_pending is not None
        result["backend_coalesced"] = self._backend_coalesced
        return result

    def _notify(self) -> None:
        with self._lock:
            state = self._state_copy_locked()
            listeners = list(self._listeners)
        callbacks = ([self._on_state_change] if self._on_state_change else []) + listeners
        for callback in callbacks:
            try:
                callback(state)
            except Exception:
                pass

    def _sync_next_fields(self) -> None:
        """Keep the UPnP-facing NextURI fields aligned with the queue head."""
        if self.state.next_queue:
            entry = self.state.next_queue[0]
            self.state.next_uri = entry["uri"]
            self.state.next_metadata = entry["metadata"]
        else:
            self.state.next_uri = ""
            self.state.next_metadata = ""
