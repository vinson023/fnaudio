from __future__ import annotations

from typing import Any, Dict, Optional

from .models import PlaybackCommand, PlaybackState, TrackRef
from .mpd_client import (
    MpdError,
    mpd_control,
    mpd_load_file,
    mpd_load_uri,
    mpd_probe,
    mpd_status,
    mpd_update_and_wait,
)
from .plugins import OutputPlugin


class MpdOutput(OutputPlugin):
    plugin_id = "mpd"
    display_name = "MPD 本机播放"
    target_kind = "mpd"

    def __init__(self, service=None):
        self.service = service

    def configure(self, service) -> None:
        self.service = service

    def start_service(self) -> Dict[str, Any]:
        if self.service:
            return self.service.start()
        return mpd_probe()

    def stop_service(self) -> Dict[str, Any]:
        if self.service:
            return self.service.stop()
        return {"ok": True, "running": False}

    def _connection(self) -> Dict[str, Any]:
        if self.service:
            return {"host": self.service.host, "port": self.service.port}
        return {}

    def _select_target_output(self, state: PlaybackState) -> Dict[str, Any]:
        if not self.service or not hasattr(self.service, "select_output"):
            return {"ok": True}
        target_id = str(getattr(state, "target_id", "") or "")
        if not target_id.startswith("mpd:"):
            return {"ok": True}
        alsa_id = target_id[4:]
        if not alsa_id or alsa_id == "local":
            return {"ok": True}
        return self.service.select_output(alsa_id)

    def capabilities(self) -> Dict[str, Any]:
        return {
            "seek": True,
            "pause": True,
            "stop": True,
            "volume": True,
            "next_previous": True,
            "native_dsd": True,
            "server_transcode": False,
            "optional_backend": True,
        }

    def open(self, track: TrackRef, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        item = (context or {}).get("item") or track.item
        path = str(item.get("path") or "")
        if not path:
            return {"ok": False, "message": "曲目没有本地文件路径", "target_id": state.target_id}
        try:
            selected = self._select_target_output(state)
            if selected.get("ok") is False:
                return {"ok": False, "message": selected.get("message") or "MPD 输出设备不可用", "target_id": state.target_id}
            started = self.start_service()
            if started.get("available") is False or (started.get("ok") is False and not started.get("running")):
                return {"ok": False, "message": started.get("message") or "MPD 不可用", "target_id": state.target_id}
            output_ready = self._output_ready()
            if not output_ready.get("ok"):
                return {"ok": False, "message": output_ready.get("message") or "没有检测到本机音频输出设备", "target_id": state.target_id}
            cue_start = float(item.get("cue_start") or 0) if item.get("cue_track") else 0.0
            if self.service and hasattr(self.service, "suppress_stop_transition"):
                self.service.suppress_stop_transition()
            if self.service and hasattr(self.service, "uri_for_path"):
                result = self._load_uri_with_retry(self.service.uri_for_path(path), cue_start)
            else:
                result = mpd_load_file(path, start=cue_start, **self._connection())
            if self.service and hasattr(self.service, "refresh_status"):
                self.service.refresh_status()
            return {
                **result,
                "message": "",
                "target_id": state.target_id,
                "track_id": track.track_id,
                "cue_segment": bool(item.get("cue_track")),
            }
        except Exception as exc:
            return {"ok": False, "message": "MPD 播放失败：%s" % exc, "target_id": state.target_id}

    def command(self, command: PlaybackCommand, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            selected = self._select_target_output(state)
            if selected.get("ok") is False:
                return {"ok": False, "message": selected.get("message") or "MPD 输出设备不可用", "target_id": state.target_id}
            started = self.start_service()
            if started.get("available") is False or (started.get("ok") is False and not started.get("running")):
                return {"ok": False, "message": started.get("message") or "MPD 不可用", "target_id": state.target_id}
            if command.action == "stop" and self.service and hasattr(self.service, "suppress_stop_transition"):
                self.service.suppress_stop_transition()
            result = mpd_control(command.action, command.position, **self._connection())
            if self.service and hasattr(self.service, "refresh_status"):
                self.service.refresh_status()
            return {**result, "message": "", "target_id": state.target_id}
        except Exception as exc:
            return {"ok": False, "message": "MPD 控制失败：%s" % exc, "target_id": state.target_id}

    def close(self, state: PlaybackState) -> None:
        try:
            mpd_control("stop", **self._connection())
        except Exception:
            pass

    def snapshot(self, state: PlaybackState) -> Dict[str, Any]:
        result = super().snapshot(state)
        try:
            result["mpd"] = self.status()
        except Exception as exc:
            result["mpd"] = {"available": False, "message": str(exc)}
        return result

    def status(self) -> Dict[str, Any]:
        if self.service:
            return self.service.status()
        return mpd_probe()

    def _output_ready(self) -> Dict[str, Any]:
        if not self.service or not hasattr(self.service, "output_capabilities"):
            return {"ok": True}
        caps = self.service.output_capabilities()
        devices = caps.get("devices") or []
        if devices:
            return {"ok": True}
        return {
            "ok": False,
            "message": "MPD 已启动，但没有检测到真实 ALSA 声卡或 USB DAC，无法本机播放",
            "capabilities": caps,
        }

    def _load_uri_with_retry(self, uri: str, cue_start: float) -> Dict[str, Any]:
        try:
            return mpd_load_uri(uri, start=cue_start, **self._connection())
        except MpdError as exc:
            message = str(exc)
            if "No such song" not in message and "directory or file not found" not in message.lower():
                raise
            update = mpd_update_and_wait(**self._connection())
            try:
                result = mpd_load_uri(uri, start=cue_start, **self._connection())
                return {**result, "mpd_update": update}
            except Exception as retry_exc:
                raise MpdError("%s；已触发 MPD 音乐库更新后重试仍失败：%s；uri=%s" % (message, retry_exc, uri)) from retry_exc


def mpd_output_status(output: Optional[MpdOutput] = None) -> Dict[str, Any]:
    return (output or MpdOutput()).status()
