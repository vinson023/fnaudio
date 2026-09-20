from __future__ import annotations

from typing import Any, Dict, Optional
import math

from .models import PlaybackCommand, PlaybackState, TrackRef
from .mpd_client import (
    MpdError,
    mpd_control,
    mpd_load_file,
    mpd_load_uri,
    mpd_probe,
    mpd_set_playback_modes,
    mpd_status,
    mpd_update_and_wait,
)
from playback_cue_position import project_cue_seek
from .mpd_errors import classify_mpd_exception, mpd_error
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

    @staticmethod
    def _failure(message: str, target_id: str, category: str = "") -> Dict[str, Any]:
        error = mpd_error(category, message) if category else classify_mpd_exception(message)
        return {
            "ok": False,
            "message": message,
            "error_category": error["category"],
            "error": error,
            "target_id": target_id,
        }

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
        output = {}
        if self.service and hasattr(self.service, "output_capabilities"):
            try:
                output = self.service.output_capabilities()
            except Exception:
                output = {}
        volume_control = output.get("volume_control") or {}
        def flag(value):
            return value if isinstance(value, bool) else False
        return {
            "seek": True,
            "pause": True,
            "stop": True,
            "volume": flag(volume_control.get("available")),
            "next_previous": True,
            "native_dsd": flag(output.get("dsd_native")),
            "native_dsd_verified": flag(output.get("native_dsd_verified")),
            "dop": flag(output.get("dop")),
            "dsd_mode": output.get("dsd_mode") or "native",
            "bitperfect": flag(output.get("bitperfect")),
            "server_transcode": False,
            "optional_backend": True,
            "volume_control": volume_control,
        }

    def preload_next(self, track: TrackRef, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.service and hasattr(self.service, "preload_status"):
            return self.service.preload_status(track.track_id)
        return {"ok": False, "supported": False}

    def recover(self, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.service and hasattr(self.service, "recover_playback"):
            return self.service.recover_playback()
        return {"ok": False, "supported": False}

    def open(self, track: TrackRef, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        item = (context or {}).get("item") or track.item
        path = str(item.get("path") or "")
        if not path:
            return self._failure("曲目没有本地文件路径", state.target_id, "source_missing")
        try:
            selected = self._select_target_output(state)
            if selected.get("ok") is False:
                return self._failure(selected.get("message") or "MPD 输出设备不可用", state.target_id, "output_device_missing")
            if self.service and hasattr(self.service, "prepare_track_output"):
                negotiated = self.service.prepare_track_output(item)
                if negotiated.get("ok") is False:
                    failure = self._failure(
                        negotiated.get("message") or "MPD 输出格式不受支持",
                        state.target_id,
                        "output_format_unsupported",
                    )
                    return {**negotiated, **failure}
            started = self.start_service()
            if started.get("available") is False or (started.get("ok") is False and not started.get("running")):
                return self._failure(started.get("message") or "MPD 不可用", state.target_id, "backend_unavailable")
            output_ready = self._output_ready()
            if not output_ready.get("ok"):
                return self._failure(
                    output_ready.get("message") or "没有检测到本机音频输出设备",
                    state.target_id,
                    "output_device_missing",
                )
            try:
                requested_position = float((context or {}).get("position") or 0.0)
                cue_offset = float(item.get("cue_start") or 0) if item.get("cue_track") else 0.0
                if not math.isfinite(requested_position) or not math.isfinite(cue_offset):
                    raise ValueError("non-finite playback position")
                requested_position = max(0.0, requested_position)
                cue_start = max(0.0, cue_offset) + requested_position
            except (TypeError, ValueError, OverflowError):
                requested_position = 0.0
                cue_start = 0.0
            if self.service and hasattr(self.service, "suppress_stop_transition"):
                self.service.suppress_stop_transition()
            if self.service and hasattr(self.service, "sync_playback_queue"):
                resolver = (context or {}).get("resolve_track")
                try:
                    result = self.service.sync_playback_queue(
                        state.queue,
                        state.current_track_id,
                        resolver=resolver,
                        current_item=item,
                        start=cue_start,
                        repeat=state.repeat,
                        shuffle=state.shuffle,
                    )
                except MpdError as exc:
                    # fnAudio can finish scanning before MPD notices a new
                    # file. Keep the native queue path consistent with the
                    # single-track fallback: refresh MPD once, then retry.
                    if not self._is_missing_mpd_library_entry(exc):
                        raise
                    update = mpd_update_and_wait(**self._connection())
                    result = self.service.sync_playback_queue(
                        state.queue,
                        state.current_track_id,
                        resolver=resolver,
                        current_item=item,
                        start=cue_start,
                        repeat=state.repeat,
                        shuffle=state.shuffle,
                    )
                    result = {**result, "mpd_update": update}
            elif self.service and hasattr(self.service, "uri_for_path"):
                result = self._load_uri_with_retry(self.service.uri_for_path(path), cue_start)
            else:
                result = mpd_load_file(path, start=cue_start, **self._connection())
            if self.service and hasattr(self.service, "refresh_status"):
                self.service.refresh_status()
            return {
                **result,
                "target_id": state.target_id,
                "track_id": track.track_id,
                "cue_segment": bool(item.get("cue_track")),
            }
        except Exception as exc:
            return self._failure("MPD 播放失败：%s" % exc, state.target_id)

    @staticmethod
    def _current_cue_item(state: PlaybackState, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolve the item a seek applies to, preferring the request payload.

        A control request carries the library mapping it is acting on.  When a
        client omits it, the queue reference for the current track already holds
        the same mapping, so the offset needs no filesystem or database lookup.
        """
        item = (context or {}).get("item")
        if isinstance(item, dict) and item:
            return item
        queue = state.queue or []
        track_id = state.current_track_id
        if not queue or not track_id:
            return {}
        index = state.current_index
        if isinstance(index, int) and 0 <= index < len(queue) and queue[index].track_id == track_id:
            candidate = queue[index].item
        else:
            candidate = next((track.item for track in queue if track.track_id == track_id), {})
        return candidate if isinstance(candidate, dict) else {}

    def command(self, command: PlaybackCommand, state: PlaybackState, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            selected = self._select_target_output(state)
            if selected.get("ok") is False:
                return self._failure(selected.get("message") or "MPD 输出设备不可用", state.target_id, "output_device_missing")
            if command.action == "volume" and self.service and hasattr(self.service, "mixer_policy"):
                mixer = self.service.mixer_policy()
                if not mixer.get("available"):
                    return self._failure(mixer.get("message") or "当前输出未启用音量控制", state.target_id, "mixer_unavailable")
            started = self.start_service()
            if started.get("available") is False or (started.get("ok") is False and not started.get("running")):
                return self._failure(started.get("message") or "MPD 不可用", state.target_id, "backend_unavailable")
            if command.action in ("repeat", "shuffle"):
                result = self.service.update_playback_modes(state.repeat, state.shuffle) if self.service else mpd_set_playback_modes(state.repeat, state.shuffle, **self._connection())
                return {**result, "target_id": state.target_id}
            if command.action == "stop" and self.service and hasattr(self.service, "suppress_stop_transition"):
                self.service.suppress_stop_transition()
            # The client reports and requests seconds inside the CUE segment.
            # MPD is driven in source-file seconds for a native CUE track, so the
            # seek is folded back through the inverse of the status projection.
            requested_position = (
                project_cue_seek(command.position, self._current_cue_item(state, context))
                if command.action == "seek"
                else command.position
            )
            result = self.service.control(command.action, requested_position) if self.service else mpd_control(command.action, requested_position, **self._connection())
            if self.service and hasattr(self.service, "refresh_status"):
                self.service.refresh_status()
            return {**result, "target_id": state.target_id}
        except Exception as exc:
            return self._failure("MPD 控制失败：%s" % exc, state.target_id)

    def close(self, state: PlaybackState) -> None:
        try:
            if self.service:
                self.service.control("stop")
            else:
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

    def status(self, light: bool = False) -> Dict[str, Any]:
        if self.service:
            return self.service.status(light=light)
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
            if not self._is_missing_mpd_library_entry(exc):
                raise
            update = mpd_update_and_wait(**self._connection())
            try:
                result = mpd_load_uri(uri, start=cue_start, **self._connection())
                return {**result, "mpd_update": update}
            except Exception as retry_exc:
                raise MpdError("%s；已触发 MPD 音乐库更新后重试仍失败：%s；uri=%s" % (message, retry_exc, uri)) from retry_exc


    @staticmethod
    def _is_missing_mpd_library_entry(exc: Exception) -> bool:
        message = str(exc).lower()
        return "no such song" in message or "directory or file not found" in message


def mpd_output_status(output: Optional[MpdOutput] = None) -> Dict[str, Any]:
    return (output or MpdOutput()).status()
