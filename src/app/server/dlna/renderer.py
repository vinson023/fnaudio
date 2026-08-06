from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock, Thread
from typing import Any, Callable, Dict
import time
from xml.etree import ElementTree as ET


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
        self._backend_lock = RLock()
        self._load_generation = 0
        self._loading_uri = ""
        # MPD status can briefly remain STOPPED after accepting an HTTP source.
        # Do not let that stale value erase a new AVTransport session before
        # the backend has ever reported it active.
        self._backend_active_observed = False
        self.state = DlnaRendererState()

    def set_uri(self, uri: str, metadata: str = "") -> None:
        with self._lock:
            self.state.uri = str(uri or "")
            self.state.metadata = str(metadata or "")
            self.state.title, self.state.artist, self.state.art_url = self._metadata_fields(metadata, uri)
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
            uri = str(uri or "")
            metadata = str(metadata or "")
            if not uri:
                self.state.next_queue = []
            else:
                self.state.next_queue.append({"uri": uri, "metadata": metadata})
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
        Thread(
            target=self._load_in_background,
            args=(generation, uri, position),
            name="fnaudio-dlna-renderer-load",
            daemon=True,
        ).start()
        return {"ok": True, "queued": True}

    def _load_in_background(self, generation: int, uri: str, position: float) -> None:
        # Serializing MPD work keeps an older source load from racing a later
        # Stop or Next command.
        with self._backend_lock:
            with self._lock:
                if generation != self._load_generation or uri != self.state.uri:
                    return
            try:
                result = self._load_uri(uri, position) or {}
            except Exception as exc:
                result = {"ok": False, "message": str(exc)}
            with self._lock:
                stale = generation != self._load_generation or uri != self.state.uri
            if stale:
                # The following Stop/Pause/Play worker is queued behind this
                # load by _backend_lock and becomes the single final action.
                return
            with self._lock:
                self._loading_uri = ""
                if result.get("ok") is False:
                    self.state.transport = "STOPPED"
                    self.state.last_error = str(result.get("message") or "unable to load source")
                else:
                    self.state.transport = "PLAYING"
                    self.state.last_error = ""
                self.state.updated_at = time.time()
        self._notify()

    def command(self, action: str, position: float | None = None) -> Dict[str, Any]:
        action = str(action or "").lower()
        with self._lock:
            if action == "play":
                return self.play()
            if action == "next" and self.state.next_queue:
                entry = self.state.next_queue.pop(0)
                self._sync_next_fields()
                uri = entry["uri"]
                metadata = entry["metadata"]
                self.set_uri(uri, metadata)
                return self.play()
            self._load_generation += 1
            generation = self._load_generation
            self._loading_uri = ""
            if action == "pause":
                self.state.transport = "PAUSED_PLAYBACK"
            elif action == "stop":
                self.state.transport = "STOPPED"
                self.state.position = 0.0
            elif action == "seek" and position is not None:
                self.state.position = max(0.0, float(position))
            self.state.updated_at = time.time()
        self._notify()
        Thread(
            target=self._control_in_background,
            args=(generation, action, position),
            name="fnaudio-dlna-renderer-control",
            daemon=True,
        ).start()
        return {"ok": True, "queued": True}

    def _control_in_background(self, generation: int, action: str, position: float | None) -> None:
        with self._backend_lock:
            with self._lock:
                if generation != self._load_generation:
                    return
            try:
                result = self._control(action, position) or {}
            except Exception as exc:
                result = {"ok": False, "message": str(exc)}
            if result.get("ok") is False:
                with self._lock:
                    if generation == self._load_generation:
                        self.state.last_error = str(result.get("message") or "playback control failed")
                        self.state.updated_at = time.time()
                self._notify()

    def set_volume(self, volume: int) -> Dict[str, Any]:
        volume = max(0, min(100, int(volume)))
        result = self._control("volume", float(volume))
        if result.get("ok") is not False:
            with self._lock:
                self.state.volume = volume
                self.state.updated_at = time.time()
            self._notify()
        return result

    def set_mute(self, muted: bool) -> None:
        with self._lock:
            self.state.muted = bool(muted)
            self.state.updated_at = time.time()
        self._notify()

    def snapshot(self) -> Dict[str, Any]:
        notify = False
        with self._lock:
            result = dict(self.state.__dict__)
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
                if backend_transport in ("PLAYING", "PAUSED_PLAYBACK", "PAUSED"):
                    self._backend_active_observed = True
                    result["transport"] = backend_transport
                    result["position"] = float(position.get("rel_seconds") or 0)
                    result["duration"] = float(position.get("duration_seconds") or 0)
                elif backend_transport == "STOPPED" and (
                    result["transport"] == "STOPPED" or self._backend_active_observed
                ):
                    self._backend_active_observed = False
                    result["transport"] = "STOPPED"
                    result["position"] = 0.0
                    result["duration"] = float(position.get("duration_seconds") or 0)
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
                result["volume"] = max(0, min(100, int(float(raw["volume"]))))
        except Exception:
            pass
        if notify:
            self._notify()
        return result

    def _notify(self) -> None:
        with self._lock:
            state = dict(self.state.__dict__)
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

    @staticmethod
    def _metadata_fields(metadata: str, uri: str) -> tuple[str, str, str]:
        title = ""
        artist = ""
        art_url = ""
        try:
            root = ET.fromstring(str(metadata or ""))
            for node in root.iter():
                tag = str(node.tag).split("}")[-1]
                if tag == "title" and not title:
                    title = str(node.text or "").strip()
                elif tag in ("creator", "artist") and not artist:
                    artist = str(node.text or "").strip()
                elif tag == "albumArtURI" and not art_url:
                    art_url = str(node.text or "").strip()
        except Exception:
            pass
        fallback = str(uri or "").rsplit("/", 1)[-1].split("?", 1)[0] or "DLNA input"
        return title or fallback, artist, art_url
