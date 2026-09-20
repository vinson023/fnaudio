from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Iterable, Optional

from .models import PlaybackCommand, PlaybackState, TrackRef


class OutputPlugin(ABC):
    """Backend output contract. Plugins never own the global queue."""

    plugin_id = "output"
    display_name = "Output"
    target_kind = "unknown"

    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def open(self, track: TrackRef, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def command(self, command: PlaybackCommand, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def close(self, state: PlaybackState) -> None:
        raise NotImplementedError

    def snapshot(self, state: PlaybackState) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "target_kind": self.target_kind,
            "capabilities": self.capabilities(),
            "playing": state.playing,
            "position": state.position,
            "duration": state.duration,
            "transport": state.transport,
            "owns_audio_device": self.owns_audio_device(state),
        }

    def status(self, state: Optional[PlaybackState] = None) -> Dict[str, Any]:
        """Return normalized backend status when the output can provide it.

        Older callback outputs intentionally inherit this conservative state
        projection. Concrete asynchronous outputs can override it without
        forcing every plugin to implement a second status API immediately.
        """
        if state is None:
            return {"transport": {"state": "UNKNOWN"}}
        return {
            "transport": {"state": state.transport},
            "position": {
                "rel_seconds": state.position,
                "duration_seconds": state.duration,
            },
            "error": state.error,
        }

    def supports_action(self, action: str) -> bool:
        action = str(action or "").lower()
        capabilities = self.capabilities()
        mapping = {
            "seek": "seek",
            "pause": "pause",
            "stop": "stop",
            "next": "next_previous",
            "previous": "next_previous",
            "volume": "volume",
        }
        capability = mapping.get(action)
        if not capability:
            return True
        value = capabilities.get(capability)
        return value if isinstance(value, bool) else False

    def owns_audio_device(self, state: Optional[PlaybackState] = None) -> bool:
        return self.target_kind in ("alsa", "mpd")

    def preload_next(self, track: TrackRef, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"ok": False, "supported": False}

    def recover(self, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"ok": False, "supported": False}


class OutputRegistry:
    def __init__(self, plugins: Optional[Iterable[OutputPlugin]] = None):
        self._plugins: Dict[str, OutputPlugin] = {}
        for plugin in plugins or ():
            self.register(plugin)

    def register(self, plugin: OutputPlugin) -> None:
        if not plugin.plugin_id:
            raise ValueError("output plugin_id is required")
        self._plugins[plugin.plugin_id] = plugin

    def get(self, plugin_id: str) -> OutputPlugin:
        try:
            return self._plugins[plugin_id]
        except KeyError as exc:
            raise KeyError("unknown output plugin: %s" % plugin_id) from exc

    def has(self, plugin_id: str) -> bool:
        return plugin_id in self._plugins

    def describe(self) -> list[Dict[str, Any]]:
        return [
            {
                "id": plugin.plugin_id,
                "name": plugin.display_name,
                "target_kind": plugin.target_kind,
                "capabilities": plugin.capabilities(),
            }
            for plugin in self._plugins.values()
        ]


class BrowserOutput(OutputPlugin):
    plugin_id = "browser"
    display_name = "浏览器播放"
    target_kind = "browser"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "seek": True,
            "pause": True,
            "volume": True,
            "native_dsd": False,
            "server_transcode": True,
        }

    def open(self, track: TrackRef, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"track_id": track.track_id, "mode": "browser"}

    def command(self, command: PlaybackCommand, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"action": command.action, "position": command.position}

    def close(self, state: PlaybackState) -> None:
        return None


class CallbackOutput(OutputPlugin):
    """Adapter for legacy output functions during the playback migration."""

    plugin_id = "callback"
    display_name = "Callback Output"
    target_kind = "callback"

    def __init__(
        self,
        plugin_id: str,
        display_name: str,
        target_kind: str,
        capabilities: Dict[str, Any],
        on_open: Optional[Callable[[TrackRef, PlaybackState, Dict[str, Any]], Dict[str, Any]]] = None,
        on_command: Optional[Callable[[PlaybackCommand, PlaybackState, Dict[str, Any]], Dict[str, Any]]] = None,
        on_close: Optional[Callable[[PlaybackState], None]] = None,
    ):
        self.plugin_id = plugin_id
        self.display_name = display_name
        self.target_kind = target_kind
        self._capabilities = dict(capabilities)
        self._on_open = on_open
        self._on_command = on_command
        self._on_close = on_close

    def capabilities(self) -> Dict[str, Any]:
        return dict(self._capabilities)

    def open(self, track: TrackRef, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self._on_open:
            return self._on_open(track, state, context or {})
        return {"track_id": track.track_id, "mode": self.target_kind, "deferred": True}

    def command(self, command: PlaybackCommand, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self._on_command:
            return self._on_command(command, state, context or {})
        return {"action": command.action, "deferred": True}

    def close(self, state: PlaybackState) -> None:
        if self._on_close:
            self._on_close(state)


class DlnaPushOutput(CallbackOutput):
    def __init__(self, **callbacks):
        super().__init__(
            plugin_id="dlna_push",
            display_name="UPnP/DLNA 推送",
            target_kind="dlna_push",
            capabilities={
                "seek": True,
                "pause": True,
                "stop": True,
                "next_previous": True,
                "native_dsd": True,
                "server_transcode": False,
            },
            **callbacks,
        )


class AlsaOutput(CallbackOutput):
    def __init__(self, **callbacks):
        super().__init__(
            plugin_id="alsa",
            display_name="本机 ALSA/DAC 输出",
            target_kind="alsa",
            capabilities={
                "seek": True,
                "pause": True,
                "stop": True,
                "volume": False,
                "native_dsd": False,
                "server_transcode": True,
            },
            **callbacks,
        )
