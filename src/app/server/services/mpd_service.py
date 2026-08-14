from __future__ import annotations

import math
import os
import posixpath
import re
import shutil
import signal
import socket
import struct
import subprocess
import threading
import time
import urllib.parse
import wave
from typing import Any, Dict, List, Mapping, Optional

from playback.mpd_client import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    mpd_binary,
    mpd_idle,
    mpd_load_uri,
    mpd_play_queue_item,
    mpd_probe,
    mpd_replace_queue,
    mpd_set_playback_modes,
    mpd_status,
    mpd_update_and_wait,
)
from playback.mpd_errors import (
    classify_mpd_log_errors,
    empty_mpd_error_summary,
    legacy_decoder_error_summary,
)
from playback.alsa_output import alsa_devices, find_ffmpeg, probe_alsa_hw_params
from transcode import transcode_to_audio
from .process_supervisor import ProcessSupervisor
from .audio_output_lease import AUDIO_OUTPUT_LEASE
from .dac_profiles import dac_quirk_profile
from file_permissions import atomic_write_text, secure_directory, secure_file


def device_presence_transition(state: Optional[Dict[str, Any]], present: bool, threshold: int = 2):
    """Debounce USB DAC enumeration changes.

    USB audio devices briefly disappear while the kernel tears down and
    recreates the ALSA card.  A single missing sample must therefore not stop
    MPD, and a single present sample must not immediately start recovery.
    Returns ``(new_state, event)`` where event is ``disconnected``,
    ``reconnected`` or ``""``.
    """
    current = dict(state or {})
    threshold = max(1, int(threshold or 1))
    missing = int(current.get("missing_samples") or 0)
    present_samples = int(current.get("present_samples") or 0)
    was_missing = bool(current.get("missing"))
    if present:
        missing = 0
        present_samples += 1
        event = "reconnected" if was_missing and present_samples >= threshold else ""
        if event:
            was_missing = False
    else:
        present_samples = 0
        missing += 1
        event = "disconnected" if not was_missing and missing >= threshold else ""
        if event:
            was_missing = True
    current.update(
        {
            "missing_samples": missing,
            "present_samples": present_samples,
            "missing": was_missing,
        }
    )
    return current, event


class MpdService:
    """Owns an app-private MPD instance when an MPD binary is available."""

    def __init__(
        self,
        config: Dict[str, Any],
        app_root: Optional[str] = None,
        app_config_path: Optional[str] = None,
    ):
        self.config = config
        self.app_config_path = os.path.abspath(app_config_path) if app_config_path else ""
        self.app_root = app_root or os.environ.get("TRIM_APPDEST") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.host = DEFAULT_HOST
        self.port = self._select_port(int(config.get("mpd_port") or DEFAULT_PORT))
        self.config["mpd_port"] = self.port
        self.binary = self._find_binary()
        self.lib_dir = os.path.join(self.app_root, "target", "lib")
        self.data_root = self._data_root()
        self.music_root = os.path.join(self.data_root, "music")
        self.config_path = os.path.join(self.data_root, "mpd.conf")
        self.log_path = os.path.join(self.data_root, "mpd.log")
        self.supervisor = ProcessSupervisor()
        self._configured = False
        self._idle_stop = threading.Event()
        self._idle_thread: Optional[threading.Thread] = None
        self._idle_lock = threading.Lock()
        self._idle_state: Dict[str, Any] = {"last_event": 0.0, "changed": [], "error": ""}
        self._status_lock = threading.Lock()
        self._status_cache: Dict[str, Any] = {}
        # ALSA enumeration and hw_params probing are comparatively expensive
        # (and can briefly contend with MPD for the PCM).  Keep this state
        # separate from the high-frequency transport status cache.
        self._output_caps_lock = threading.Lock()
        self._output_caps_cache: Dict[str, Any] = {}
        self._output_caps_cache_at = 0.0
        self._output_caps_refreshing = False
        self._output_caps_ttl = 4.0
        self._binary_version_cache: Optional[str] = None
        self._status_listener = None
        self._last_transport = ""
        self._suppress_stop_until = 0.0
        self._queue_lock = threading.RLock()
        self._queue_fingerprint = ()
        self._queue_song_ids: Dict[str, str] = {}
        self._queue_song_tracks: Dict[str, str] = {}
        self._queue_entries: List[Dict[str, Any]] = []
        self._queue_current_track_id = ""
        self._last_position = 0.0
        self._queue_repeat = "off"
        self._queue_shuffle = False
        self._recovery_lock = threading.Lock()
        self._device_monitor_stop = threading.Event()
        self._device_monitor_thread: Optional[threading.Thread] = None
        self._selected_device_missing = False
        self._device_presence = {"missing_samples": 0, "present_samples": 0, "missing": False}
        self._device_presence_threshold = max(1, int(config.get("mpd_device_presence_samples") or 2))
        self._last_underrun_restart = 0.0
        self._underrun_state: Dict[str, Any] = {
            "count": 0,
            "last_detected": 0.0,
            "last_message": "",
            "last_restart": 0.0,
            "restart_suppressed": 0,
        }
        self._playback_error_state: Dict[str, Any] = {
            "count": 0,
            "last_detected": 0.0,
            "last_category": "",
            "last_domain": "",
            "last_message": "",
            "by_category": {},
        }
        self._last_log_size = 0
        self._fault_lock = threading.Lock()
        self._fault_state: Dict[str, Any] = {
            "state": "IDLE",
            "consecutive_failures": 0,
            "last_transition": time.time(),
            "last_error": "",
            "recovery_count": 0,
            "status_latency_ms": 0.0,
            "status_samples": 0,
        }

    def _persist_app_config(self) -> bool:
        if not self.app_config_path:
            return False
        try:
            from config import save_config

            return bool(save_config(self.app_config_path, self.config))
        except Exception:
            return False

    def set_status_listener(self, callback) -> None:
        """Receive every normalized MPD idle snapshot.

        The callback keeps the historical ``(previous, current, probe)``
        signature. It now also runs for mixer/playlist/output events where
        transport did not change, making MPD the authoritative state source.
        """
        self._status_listener = callback

    def suppress_stop_transition(self, seconds: float = 2.0) -> None:
        """Mark an upcoming STOPPED event as command-driven, not track end."""
        self._suppress_stop_until = max(self._suppress_stop_until, time.monotonic() + max(0.1, seconds))

    def _find_binary(self) -> str:
        candidates = [
            os.path.join(self.app_root, "bin", "mpd"),
            os.path.join(self.app_root, "target", "bin", "mpd"),
            mpd_binary(),
        ]
        for path in candidates:
            if not path:
                continue
            found = path if os.path.isfile(path) else shutil.which(path)
            if not found:
                continue
            try:
                os.chmod(found, os.stat(found).st_mode | 0o755)
            except OSError:
                pass
            return found
        return ""

    def _select_port(self, requested: int) -> int:
        requested = max(1024, min(65535, int(requested or DEFAULT_PORT)))
        if _tcp_port_available(self.host, requested):
            return requested
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((self.host, 0))
            return int(sock.getsockname()[1])

    def _data_root(self) -> str:
        configured = str(self.config.get("mpd_data_dir") or "").strip()
        if configured:
            return os.path.abspath(os.path.expanduser(configured))
        return os.path.join(self.app_root, "share", "mpd")

    def _library_paths(self) -> List[str]:
        paths = self.config.get("library_paths")
        if isinstance(paths, list):
            values = [str(x).strip() for x in paths if str(x).strip()]
        else:
            values = []
        if not values and self.config.get("library_path"):
            values = [x.strip() for x in str(self.config.get("library_path")).replace(";", "\n").splitlines() if x.strip()]
        return values or ["/"]

    def uri_for_path(self, path: str) -> str:
        full = os.path.abspath(os.path.expanduser(path or ""))
        roots = self._library_paths()
        for index, root in enumerate(roots):
            root_path = os.path.abspath(os.path.expanduser(root))
            try:
                if os.path.commonpath([full, root_path]) != root_path:
                    continue
            except ValueError:
                continue
            rel = os.path.relpath(full, root_path)
            if rel and rel != ".":
                if len(roots) > 1:
                    return "%s/%s" % (self._root_alias(root_path, index), rel.replace(os.sep, "/"))
                return rel.replace(os.sep, "/")
        return "file://" + urllib.parse.quote(full)

    def _mpd_transcode_config(self, source_path: str) -> Dict[str, Any]:
        """Keep MPD playback transcodes inside a configured music root.

        MPD accepts database-relative files reliably, while its optional URI
        input plugins are not bundled consistently by fnOS.  A cache outside
        ``music_directory`` therefore cannot be used as an MPD queue entry.
        """
        source = str(source_path or "")
        # NAS library paths are POSIX even when the release tests run on
        # Windows. Keep the comparison and cache location POSIX in that case.
        path_module = posixpath if source.startswith("/") else os.path
        full = path_module.abspath(path_module.expanduser(source))
        for root in self._library_paths():
            root_text = str(root or "")
            root_module = posixpath if root_text.startswith("/") else os.path
            root_path = root_module.abspath(root_module.expanduser(root_text))
            if root_module is not path_module:
                continue
            try:
                if path_module.commonpath([full, root_path]) == root_path:
                    return {**self.config, "cache_dir": path_module.join(root_path, "fnaudio-transcode")}
            except ValueError:
                continue
        return dict(self.config)

    def refresh_database(self) -> Dict[str, Any]:
        from playback.mpd_client import mpd_request

        try:
            mpd_request("update", host=self.host, port=self.port)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def sync_playback_queue(
        self,
        queue,
        current_track_id: str,
        resolver=None,
        current_item: Optional[Dict[str, Any]] = None,
        start: float = 0.0,
        repeat: str = "off",
        shuffle: bool = False,
        play: bool = True,
    ) -> Dict[str, Any]:
        """Mirror the logical fnAudio queue into MPD's native queue.

        CUE virtual tracks intentionally stay in single-item mode because MPD
        cannot independently enforce each virtual segment's end boundary.
        APE-backed CUE tracks are materialized as lossless FLAC segments so
        the MPD build does not need a Monkey's Audio decoder.
        """
        entries: List[Dict[str, Any]] = []
        has_cue = False
        current_cue_ape = False
        generated_mpd_media = False
        for track in list(queue or []):
            track_id = str(getattr(track, "track_id", "") or "")
            item = dict(getattr(track, "item", {}) or {})
            if callable(resolver):
                try:
                    resolved = resolver(track_id)
                    if isinstance(resolved, dict):
                        item = resolved
                except Exception:
                    pass
            if track_id == str(current_track_id or "") and current_item:
                item = dict(current_item)
            path = str(item.get("path") or "")
            if not track_id or not path:
                continue
            # MPD builds on fnOS do not consistently ship the Monkey's Audio
            # decoder. Decode ordinary APE files once to FLAC. A CUE-backed
            # APE is instead decoded as its requested lossless FLAC segment.
            if path.lower().endswith(".ape"):
                path, _mime = transcode_to_audio(
                    item, self._mpd_transcode_config(path), "cue_flac" if item.get("cue_track") else "ape_flac"
                )
                generated_mpd_media = True
                current_cue_ape = current_cue_ape or (
                    track_id == str(current_track_id or "") and bool(item.get("cue_track"))
                )
            has_cue = bool(has_cue or item.get("cue_track"))
            entries.append(
                {
                    "track_id": track_id,
                    "uri": self.uri_for_path(path),
                    "cue_track": bool(item.get("cue_track")),
                }
            )
        if has_cue:
            entries = [entry for entry in entries if entry["track_id"] == str(current_track_id or "")]
        if not entries:
            raise RuntimeError("MPD queue has no playable local files")
        if generated_mpd_media:
            # The generated FLAC lives in a regular directory below a music
            # root. Refresh before addid so MPD can resolve its relative URI.
            mpd_update_and_wait(host=self.host, port=self.port)
        fingerprint = tuple((entry["track_id"], entry["uri"]) for entry in entries)
        with self._queue_lock:
            reusable = fingerprint == self._queue_fingerprint and bool(self._queue_song_ids)
            selected_song_id = self._queue_song_ids.get(str(current_track_id or "")) if reusable else ""
            if selected_song_id and play:
                result = mpd_play_queue_item(
                    selected_song_id,
                    start=0.0 if current_cue_ape else start,
                    repeat=repeat,
                    shuffle=shuffle,
                    host=self.host,
                    port=self.port,
                )
                self._queue_current_track_id = str(current_track_id or "")
                self._last_position = max(0.0, float(start or 0))
                self._queue_repeat = str(repeat or "off")
                self._queue_shuffle = bool(shuffle)
                return {**result, "queue_reused": True, "queue_count": len(entries), "cue_transcoded": current_cue_ape}
            result = mpd_replace_queue(
                entries,
                current_track_id=current_track_id,
                start=0.0 if current_cue_ape else start,
                repeat=repeat,
                shuffle=shuffle,
                play=play,
                host=self.host,
                port=self.port,
            )
            self._queue_fingerprint = fingerprint
            self._queue_song_ids = dict(result.get("song_ids") or {})
            self._queue_song_tracks = {song_id: track_id for track_id, song_id in self._queue_song_ids.items()}
            self._queue_entries = list(entries)
            self._queue_current_track_id = str(current_track_id or entries[0]["track_id"])
            self._last_position = max(0.0, float(start or 0))
            self._queue_repeat = str(repeat or "off")
            self._queue_shuffle = bool(shuffle)
            return {**result, "queue_reused": False, "queue_count": len(entries), "cue_single_mode": has_cue, "cue_transcoded": current_cue_ape}

    def track_id_for_status(self, probe: Optional[Dict[str, Any]] = None) -> str:
        status = dict((probe or {}).get("status") or {})
        song = dict(status.get("song") or {})
        song_id = str(song.get("Id") or song.get("id") or "")
        with self._queue_lock:
            return str(self._queue_song_tracks.get(song_id) or "")

    def update_playback_modes(self, repeat: str, shuffle: bool) -> Dict[str, Any]:
        with self._queue_lock:
            self._queue_repeat = str(repeat or "off")
            self._queue_shuffle = bool(shuffle)
        return mpd_set_playback_modes(repeat, shuffle, host=self.host, port=self.port)

    def preload_status(self, track_id: str) -> Dict[str, Any]:
        with self._queue_lock:
            song_id = self._queue_song_ids.get(str(track_id or ""), "")
            return {
                "ok": bool(song_id),
                "supported": True,
                "preloaded": bool(song_id),
                "song_id": song_id,
                "queue_count": len(self._queue_entries),
            }

    def recover_playback(self) -> Dict[str, Any]:
        self._recover_playback_after_restart()
        return {"ok": True, "supported": True, "status": self.status()}

    def prepare_track_output(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Negotiate source format without implicit DAC conversion."""
        selected = self._selected_alsa_output()
        if not selected or selected.get("alsa_id") == "default":
            if bool((item or {}).get("is_dsd")):
                return {"ok": False, "message": "未找到可验证的 USB DAC，已阻止 DSD 转 PCM"}
            return {"ok": True, "dsd": False}
        descriptor_caps = dict(selected.get("caps") or {})
        quirk = dac_quirk_profile(selected, self.config.get("dac_profiles") or [])
        source_rate = int(float((item or {}).get("sample_rate") or 0))
        descriptor_rates = set(descriptor_caps.get("pcm_rates") or [])
        # Do not stop an active MPD instance merely to probe a PCM rate. The
        # USB descriptor is stable and sufficient to reject unsupported
        # sources such as 384 kHz while another track is playing.
        if not bool((item or {}).get("is_dsd")) and source_rate and descriptor_rates and source_rate not in descriptor_rates:
            return {
                "ok": False,
                "message": "DAC 不支持源采样率 %s Hz，已阻止隐式重采样" % source_rate,
                "source_rate": source_rate,
                "supported_rates": sorted(descriptor_rates),
                "hw_params": {},
                "caps": descriptor_caps,
            }
        # DSD must be validated against the live ALSA endpoint.  Force a
        # refresh here because a previous playback poll may have cached a
        # transient EBUSY result while MPD was still releasing the device.
        hw = probe_alsa_hw_params(selected, force=bool((item or {}).get("is_dsd")))
        pcm_rates = set(hw.get("pcm_rates") or descriptor_rates)
        if hw.get("busy") and not hw.get("verified"):
            if not bool((item or {}).get("is_dsd")):
                return {"ok": True, "dsd": False, "hw_params": hw, "probe_deferred": True}
            return {
                "ok": False,
                "message": "DAC 当前正在播放，暂时无法验证 Native DSD/DoP，已保持当前播放",
                "hw_params": hw,
                "caps": descriptor_caps,
            }
        if not bool((item or {}).get("is_dsd")) and source_rate and pcm_rates and source_rate not in pcm_rates:
            return {
                "ok": False,
                "message": "DAC 不支持源采样率 %s Hz，已阻止隐式重采样" % source_rate,
                "source_rate": source_rate,
                "supported_rates": sorted(pcm_rates),
                "hw_params": hw,
                "caps": descriptor_caps,
            }
        native = bool(hw.get("verified") and hw.get("native_dsd") and not quirk.get("disable_native_dsd"))
        dsd_text = " ".join(str(value) for value in descriptor_caps.get("dsd_rates") or []).lower()
        dop = bool("dop" in dsd_text and ({176400, 352800} & pcm_rates))
        if not bool((item or {}).get("is_dsd")):
            return {"ok": True, "dsd": False, "hw_params": hw}
        if not native and not dop:
            return {
                "ok": False,
                "message": "当前 DAC 未通过 Native DSD/DoP 验证，已阻止转码为 PCM",
                "hw_params": hw,
                "caps": descriptor_caps,
            }
        wanted_dop = bool((not native and dop) or (quirk.get("force_dop") and dop))
        if bool(self.config.get("mpd_dop")) != wanted_dop:
            self.config["mpd_dop"] = wanted_dop
            self._configured = False
            self._persist_app_config()
        return {
            "ok": True,
            "dsd": True,
            "mode": "dop" if wanted_dop else "native",
            "native_dsd_verified": native,
            "hw_params": hw,
        }

    def ensure_config(self) -> Dict[str, Any]:
        if not self.binary:
            return {"ok": False, "available": False, "message": "MPD is not installed"}
        secure_directory(self.data_root)
        roots = self._library_paths()
        music_directory = self._prepare_music_directory(roots)
        playlist_directory = os.path.join(self.data_root, "playlists")
        secure_directory(playlist_directory)
        output_device = self._selected_alsa_output()
        output_name = output_device.get("name") or "fnAudio MPD"
        output_alsa_id = output_device.get("stable_alsa_id") or output_device.get("alsa_id") or "default"
        mixer = self.mixer_policy(output_device)
        mixer_type = mixer["mode"]
        dop = "yes" if bool(self.config.get("mpd_dop")) else "no"
        quirk = dac_quirk_profile(output_device, self.config.get("dac_profiles") or [])
        keepalive_mode = str(self.config.get("dac_keepalive_mode") or quirk.get("keepalive_mode") or "off").lower()
        if keepalive_mode not in ("off", "pcm_only"):
            keepalive_mode = "off"
        quirk["keepalive_mode"] = keepalive_mode
        output_lines = [
                'music_directory "%s"' % _mpd_quote(music_directory),
                'playlist_directory "%s"' % _mpd_quote(playlist_directory),
                'db_file "%s"' % _mpd_quote(os.path.join(self.data_root, "database")),
                'state_file "%s"' % _mpd_quote(os.path.join(self.data_root, "state")),
                'sticker_file "%s"' % _mpd_quote(os.path.join(self.data_root, "sticker.sql")),
                'pid_file "%s"' % _mpd_quote(os.path.join(self.data_root, "mpd.pid")),
                'log_file "%s"' % _mpd_quote(self.log_path),
                'bind_to_address "%s"' % self.host,
                'port "%s"' % self.port,
                'auto_update "no"',
                'connection_timeout "5"',
                'audio_buffer_size "%s"' % _mpd_quote(quirk.get("audio_buffer_size") or "8M"),
                'follow_outside_symlinks "yes"',
                'follow_inside_symlinks "yes"',
                'filesystem_charset "UTF-8"',
                "",
                'audio_output {',
                '    type "alsa"',
                '    name "%s"' % _mpd_quote("fnAudio MPD - " + output_name),
                '    device "%s"' % _mpd_quote(output_alsa_id),
                '    mixer_type "%s"' % mixer_type,
        ]
        if mixer_type == "hardware":
            output_lines.extend(
                [
                    '    mixer_device "%s"' % _mpd_quote(mixer["device"]),
                    '    mixer_control "%s"' % _mpd_quote(mixer["control"]),
                ]
            )
        output_lines.extend(
            [
                '    dop "%s"' % dop,
                # Keep the DAC path bit-perfect.  MPD otherwise silently
                # resamples unsupported source rates (for example 384 kHz
                # into a 352.8 kHz-only USB DAC).
                '    auto_resample "no"',
                '    auto_format "no"',
                '    auto_channels "no"',
                "}",
                "",
            ]
        )
        config = "\n".join(output_lines)
        config_changed = not os.path.isfile(self.config_path) or _read_text(self.config_path) != config
        if config_changed:
            atomic_write_text(self.config_path, config)
        secure_file(self.config_path)
        self._configured = True
        return {
            "ok": True,
            "available": True,
            "binary": self.binary,
            "config_path": self.config_path,
            "data_root": self.data_root,
            "music_directory": music_directory,
            "output_device": output_device,
            "mixer_type": mixer_type,
            "mixer": mixer,
            "dsd_mode": "dop" if dop == "yes" else "native",
            "dac_profile": quirk,
            "keepalive_mode": keepalive_mode,
            "mpd_nice": int(self.config.get("mpd_nice") or 0),
            "config_changed": config_changed,
            "host": self.host,
            "port": self.port,
        }

    def start(self) -> Dict[str, Any]:
        setup = self.ensure_config()
        if not setup.get("ok"):
            return setup
        lease = AUDIO_OUTPUT_LEASE.acquire("mpd", str((setup.get("output_device") or {}).get("stable_id") or ""))
        if not lease.get("ok"):
            return {**setup, "ok": False, "running": False, "message": lease.get("message")}
        if not self.supervisor.status("mpd").get("running"):
            self._cleanup_stale_instances()
        self.supervisor.register(
            "mpd",
            [self.binary, "--no-daemon", self.config_path],
            cwd=self.data_root,
            env=self._runtime_env(),
            log_path=self.log_path,
            restart=True,
            max_restarts=4,
            restart_window=90.0,
            on_restart=self._schedule_playback_recovery,
            nice=int(self.config.get("mpd_nice") or 0),
        )
        running_status = self.supervisor.status("mpd")
        scheduling_changed = int(running_status.get("nice") or 0) != int(self.config.get("mpd_nice") or 0)
        if (setup.get("config_changed") or scheduling_changed) and running_status.get("running"):
            result = self.supervisor.restart("mpd")
        else:
            result = self.supervisor.start("mpd")
        if not result.get("ok"):
            AUDIO_OUTPUT_LEASE.release("mpd")
            return {**setup, **result}
        ready = self._wait_ready()
        if not ready.get("running"):
            self.supervisor.stop("mpd")
            AUDIO_OUTPUT_LEASE.release("mpd")
            return {
                **setup,
                "ok": False,
                "running": False,
                "pid": result.get("pid", 0),
                "message": ready.get("message") or "MPD did not become ready",
            }
        self._start_idle_listener()
        self._start_device_monitor()
        startup_delay = int(((setup.get("dac_profile") or {}).get("startup_delay_ms") or 0))
        if startup_delay > 0 and (setup.get("config_changed") or result.get("pid")):
            time.sleep(startup_delay / 1000.0)
        self.refresh_status()
        return {**setup, **result, **ready}

    def stop(self) -> Dict[str, Any]:
        self._idle_stop.set()
        if self._idle_thread and self._idle_thread.is_alive():
            self._idle_thread.join(timeout=1.0)
        result = self.supervisor.stop("mpd")
        AUDIO_OUTPUT_LEASE.release("mpd")
        # A previous app crash may have orphaned an MPD process which is no
        # longer owned by this in-memory supervisor instance.
        self._cleanup_stale_instances()
        return result

    def restart(self) -> Dict[str, Any]:
        setup = self.ensure_config()
        if not setup.get("ok"):
            return setup
        lease = AUDIO_OUTPUT_LEASE.acquire("mpd", str((setup.get("output_device") or {}).get("stable_id") or ""))
        if not lease.get("ok"):
            return {**setup, "ok": False, "running": False, "message": lease.get("message")}
        if not self.supervisor.status("mpd").get("running"):
            self._cleanup_stale_instances()
        self.supervisor.register(
            "mpd",
            [self.binary, "--no-daemon", self.config_path],
            cwd=self.data_root,
            env=self._runtime_env(),
            log_path=self.log_path,
            restart=True,
            max_restarts=4,
            restart_window=90.0,
            on_restart=self._schedule_playback_recovery,
            nice=int(self.config.get("mpd_nice") or 0),
        )
        result = self.supervisor.restart("mpd")
        if not result.get("ok"):
            AUDIO_OUTPUT_LEASE.release("mpd")
            return {**setup, **result}
        ready = self._wait_ready()
        if not ready.get("running"):
            self.supervisor.stop("mpd")
            AUDIO_OUTPUT_LEASE.release("mpd")
            return {
                **setup,
                "ok": False,
                "running": False,
                "pid": result.get("pid", 0),
                "message": ready.get("message") or "MPD did not become ready",
            }
        self._start_idle_listener()
        self.refresh_status()
        return {**setup, **result, **ready}

    def status(self, light: bool = False) -> Dict[str, Any]:
        if not self.binary:
            return {
                "available": False,
                "running": False,
                "binary": "",
                "host": self.host,
                "port": self.port,
                "message": "MPD is not installed",
            }
        probe = self._cached_probe()
        supervisor = self.supervisor.status("mpd")
        result = {
            **probe,
            "available": True,
            "binary": self.binary,
            "version": self._binary_version(),
            "config_path": self.config_path,
            "data_root": self.data_root,
            "supervisor": supervisor,
            "idle": self.idle_status(),
            "output_capabilities": self.output_capabilities(),
            "selected_output": self._selected_alsa_output(),
        }
        result["playback_errors"] = empty_mpd_error_summary()
        result["decoder_errors"] = legacy_decoder_error_summary(result["playback_errors"])
        if not light:
            recent_log = _tail_text(self.log_path, 4000)
            result["recent_log"] = recent_log
            result["playback_errors"] = classify_mpd_log_errors(recent_log)
            result["decoder_errors"] = legacy_decoder_error_summary(result["playback_errors"])
        return result

    def refresh_status(self) -> Dict[str, Any]:
        started_at = time.perf_counter()
        try:
            status = mpd_status(self.host, self.port)
            probe = {
                "available": True,
                "running": True,
                "host": self.host,
                "port": self.port,
                "binary": self.binary,
                "status": status,
                "message": "",
                "cached_at": time.time(),
            }
        except Exception as exc:
            probe = {
                "available": True,
                "running": False,
                "host": self.host,
                "port": self.port,
                "binary": self.binary,
                "status": {},
                "message": str(exc),
                "cached_at": time.time(),
            }
        with self._status_lock:
            self._status_cache = probe
        self._record_status_latency((time.perf_counter() - started_at) * 1000.0)
        return self._project_cached_probe(probe)

    def _record_status_latency(self, elapsed_ms: float) -> None:
        with self._fault_lock:
            samples = int(self._fault_state.get("status_samples") or 0) + 1
            previous = float(self._fault_state.get("status_latency_ms") or 0.0)
            self._fault_state["status_samples"] = samples
            self._fault_state["status_latency_ms"] = previous + (elapsed_ms - previous) / samples

    def _observe_fault(self, transport: str = "", error: str = "", suppressed: bool = False) -> None:
        """Track transport faults without treating every STOP as a failure.

        STOP events generated by an explicit user command are passed with
        ``suppressed=True``. Unexpected stops require two observations before
        entering DEGRADED, which prevents a single USB/ALSA scheduling blip
        from immediately rebuilding the native queue.
        """
        transport = str(transport or "").upper()
        with self._fault_lock:
            current = str(self._fault_state.get("state") or "IDLE")
            next_state = current
            failures = int(self._fault_state.get("consecutive_failures") or 0)
            if error:
                failures += 1
                next_state = "SUSPECT" if failures < 2 else "DEGRADED"
            elif transport == "PLAYING":
                failures = 0
                next_state = "PLAYING"
            elif transport == "PAUSED":
                next_state = "PAUSED"
            elif transport == "STOPPED":
                if suppressed:
                    failures = 0
                    next_state = "IDLE"
                elif current in ("PLAYING", "PAUSED", "RECOVERING", "SUSPECT"):
                    failures += 1
                    next_state = "SUSPECT" if failures < 2 else "DEGRADED"
                else:
                    next_state = "IDLE"
            if next_state != current:
                self._fault_state["last_transition"] = time.time()
            self._fault_state["state"] = next_state
            self._fault_state["consecutive_failures"] = failures
            if error:
                self._fault_state["last_error"] = str(error)

    def _mark_recovering(self) -> None:
        with self._fault_lock:
            self._fault_state["state"] = "RECOVERING"
            self._fault_state["last_transition"] = time.time()

    def _mark_recovered(self, transport: str = "") -> None:
        with self._fault_lock:
            self._fault_state["recovery_count"] = int(self._fault_state.get("recovery_count") or 0) + 1
            self._fault_state["consecutive_failures"] = 0
            self._fault_state["state"] = str(transport or "PLAYING").upper() if transport else "PLAYING"
            self._fault_state["last_error"] = ""
            self._fault_state["last_transition"] = time.time()

    def fault_status(self) -> Dict[str, Any]:
        with self._fault_lock:
            return dict(self._fault_state)

    def _cached_probe(self) -> Dict[str, Any]:
        with self._status_lock:
            cached = dict(self._status_cache)
        if not cached or time.time() - float(cached.get("cached_at") or 0) > 2.0:
            return self.refresh_status()
        return self._project_cached_probe(cached)

    def _project_cached_probe(self, probe: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(probe)
        status = dict(result.get("status") or {})
        position = dict(status.get("position") or {})
        transport = dict(status.get("transport") or {})
        if transport.get("state") == "PLAYING":
            elapsed = max(0.0, time.time() - float(result.get("cached_at") or time.time()))
            base = _safe_float(position.get("rel_seconds"))
            duration = _safe_float(position.get("duration_seconds"))
            position["rel_seconds"] = min(duration, base + elapsed) if duration > 0 else base + elapsed
            status["position"] = position
        result["status"] = status
        return result

    def invalidate_output_capabilities(self) -> None:
        """Drop the cached ALSA descriptor after a device/config change."""
        with self._output_caps_lock:
            self._output_caps_cache = {}
            self._output_caps_cache_at = 0.0

    def output_capabilities(self, force: bool = False) -> Dict[str, Any]:
        """Return DAC capabilities without making every status poll scan ALSA.

        A stale value is intentionally served while one background refresh is
        running.  This keeps the playback-status request responsive even when
        a USB DAC is busy or the kernel's ALSA enumeration is slow.
        """
        now = time.time()
        with self._output_caps_lock:
            cached = dict(self._output_caps_cache)
            age = now - self._output_caps_cache_at if self._output_caps_cache_at else float("inf")
            refreshing = self._output_caps_refreshing
            if cached and not force and age <= self._output_caps_ttl:
                return cached
            if cached and not force:
                if not refreshing:
                    self._output_caps_refreshing = True
                    threading.Thread(target=self._refresh_output_capabilities, name="fnaudio-alsa-caps", daemon=True).start()
                return cached
            if refreshing and cached:
                return cached
            self._output_caps_refreshing = True
        try:
            result = self._build_output_capabilities()
            with self._output_caps_lock:
                self._output_caps_cache = dict(result)
                self._output_caps_cache_at = time.time()
            return result
        finally:
            with self._output_caps_lock:
                self._output_caps_refreshing = False

    def _refresh_output_capabilities(self) -> None:
        try:
            result = self._build_output_capabilities()
            with self._output_caps_lock:
                self._output_caps_cache = dict(result)
                self._output_caps_cache_at = time.time()
        finally:
            with self._output_caps_lock:
                self._output_caps_refreshing = False

    def _build_output_capabilities(self) -> Dict[str, Any]:
        devices = []
        detected_devices = alsa_devices()
        selected = self._selected_alsa_output()
        selected_stable_id = str(selected.get("stable_id") or "")
        selected_runtime_id = str(selected.get("alsa_id") or "")
        selected_caps = {}
        selected_hw = {}
        for device in detected_devices:
            caps = dict(device.get("caps") or {})
            is_selected = bool(
                (selected_stable_id and device.get("stable_id") == selected_stable_id)
                or (selected_runtime_id and device.get("alsa_id") == selected_runtime_id)
            )
            hw_params = probe_alsa_hw_params(device) if is_selected else {}
            if is_selected:
                selected_caps = caps
                selected_hw = hw_params
            devices.append(
                {
                    "id": device.get("id", ""),
                    "alsa_id": device.get("alsa_id", ""),
                    "stable_id": device.get("stable_id", ""),
                    "stable_alsa_id": device.get("stable_alsa_id", ""),
                    "name": device.get("name", ""),
                    "raw_name": device.get("raw_name", ""),
                    "is_usb": bool(device.get("is_usb")),
                    "selected": is_selected,
                    "caps": caps,
                    "hw_params": hw_params,
                    "mixer": self._mixer_for_device(device),
                }
            )
        verified = bool(selected_hw.get("verified"))
        rates = selected_hw.get("pcm_rates") if verified else selected_caps.get("pcm_rates") or []
        max_bits = int(selected_hw.get("pcm_max_bits") or selected_caps.get("pcm_max_bits") or 0)
        dsd_text = " ".join(str(x) for x in selected_caps.get("dsd_rates") or []).lower()
        dsd_native = bool(selected_hw.get("native_dsd")) if verified else False
        dsd_advertised = bool(selected_caps.get("dsd"))
        dop = bool("dop" in dsd_text and (176400 in rates or 352800 in rates))
        selected_device = next((device for device in devices if device.get("selected")), None)
        selected_mixer = dict((selected_device or {}).get("mixer") or {})
        mixer_policy = self.mixer_policy(selected, selected_mixer)
        return {
            "backend": "alsa",
            "device": selected.get("stable_alsa_id") or selected.get("alsa_id") or "default",
            "selected_output": selected,
            "pcm_rates": sorted(set(rates)),
            "pcm_max_rate": max(rates) if rates else 0,
            "pcm_max_bits": max_bits,
            "dsd_native": dsd_native,
            "dsd_advertised": dsd_advertised,
            "dop": dop,
            "dsd_mode": "dop" if bool(self.config.get("mpd_dop")) else "native",
            "keepalive_mode": str(self.config.get("dac_keepalive_mode") or "off"),
            "keepalive_active": False,
            "mpd_nice": int(self.config.get("mpd_nice") or 0),
            "native_dsd_verified": bool(verified and selected_hw.get("native_dsd")),
            "hw_params": selected_hw,
            "bitperfect": bool(mixer_policy.get("bitperfect")),
            "hardware_volume": bool(selected_mixer.get("available")),
            "alsa_mixer": bool(selected_mixer.get("available")),
            "mixers": [selected_mixer] if selected_mixer.get("available") else [],
            "volume_control": mixer_policy,
            "devices": devices,
        }

    def idle_status(self) -> Dict[str, Any]:
        with self._idle_lock:
            result = dict(self._idle_state)
        result["underrun"] = dict(self._underrun_state)
        result["playback_errors"] = dict(self._playback_error_state)
        result["fault"] = self.fault_status()
        return result

    def _start_idle_listener(self) -> None:
        if self._idle_thread and self._idle_thread.is_alive():
            return
        self._idle_stop.clear()
        self._idle_thread = threading.Thread(target=self._idle_loop, name="fnaudio-mpd-idle", daemon=True)
        self._idle_thread.start()

    def _idle_loop(self) -> None:
        while not self._idle_stop.is_set():
            try:
                result = mpd_idle(self.host, self.port)
                refreshed = self.refresh_status()
                with self._idle_lock:
                    self._idle_state.update(
                        {
                            "last_event": time.time(),
                            "changed": list(result.get("changed") or []),
                            "error": "",
                            "transport": normalized_transport(refreshed),
                        }
                    )
                transport = normalized_transport(refreshed)
                previous = self._last_transport
                self._last_transport = transport
                status_payload = dict(refreshed.get("status") or {})
                position_payload = dict(status_payload.get("position") or {})
                backend_track_id = self.track_id_for_status(refreshed)
                with self._queue_lock:
                    if backend_track_id:
                        self._queue_current_track_id = backend_track_id
                    self._last_position = max(0.0, _safe_float(position_payload.get("rel_seconds")))
                suppressed_stop = transport == "STOPPED" and time.monotonic() <= self._suppress_stop_until
                if suppressed_stop:
                    self._suppress_stop_until = 0.0
                natural_end = bool(
                    transport == "STOPPED"
                    and previous == "PLAYING"
                    and _safe_float(position_payload.get("duration_seconds")) > 0
                    and _safe_float(position_payload.get("rel_seconds"))
                    >= _safe_float(position_payload.get("duration_seconds")) - 0.5
                )
                self._observe_fault(transport, suppressed=(suppressed_stop or natural_end))
                if self._status_listener and transport and not suppressed_stop:
                    try:
                        self._status_listener(previous, transport, refreshed)
                    except Exception:
                        pass
            except Exception as exc:
                self._observe_fault(error=str(exc))
                with self._idle_lock:
                    self._idle_state["error"] = str(exc)
                self._idle_stop.wait(1.0)

    def _schedule_playback_recovery(self, _name: str, _result: Dict[str, Any]) -> None:
        # A process crash briefly looks like a normal MPD STOPPED event. Keep
        # the transport listener from advancing the logical queue while the
        # supervisor brings MPD back and restores the saved song/position.
        self.suppress_stop_transition(15.0)
        self._mark_recovering()
        threading.Thread(target=self._recover_playback_after_restart, name="fnaudio-mpd-recovery", daemon=True).start()

    def _recover_playback_after_restart(self) -> None:
        if not self._recovery_lock.acquire(False):
            return
        try:
            ready = self._wait_ready(8.0)
            if not ready.get("running"):
                return
            with self._queue_lock:
                entries = list(self._queue_entries)
                current_track_id = self._queue_current_track_id
                position = self._last_position
                repeat = self._queue_repeat
                shuffle = self._queue_shuffle
            if not entries or not current_track_id:
                return
            result = mpd_replace_queue(
                entries,
                current_track_id=current_track_id,
                start=max(0.0, position - 0.35),
                repeat=repeat,
                shuffle=shuffle,
                host=self.host,
                port=self.port,
            )
            with self._queue_lock:
                self._queue_song_ids = dict(result.get("song_ids") or {})
                self._queue_song_tracks = {song_id: track_id for track_id, song_id in self._queue_song_ids.items()}
            probe = self.refresh_status()
            transport = normalized_transport(probe)
            if not transport:
                transport = "PLAYING" if entries else "STOPPED"
            with self._idle_lock:
                self._idle_state.update(
                    {
                        "last_event": time.time(),
                        "changed": ["recovery", "player"],
                        "error": "",
                        "transport": transport,
                    }
                )
            self._last_transport = transport
            self._observe_fault(transport, suppressed=(transport == "STOPPED"))
            self._mark_recovered(transport)
            # MPD may be PLAYING immediately after the queue is rebuilt but
            # emit no new idle event.  Publish the recovered snapshot now so
            # PlaybackCore, WebView and MediaSession do not retain STOPPED.
            if self._status_listener:
                try:
                    self._status_listener("RECOVERING", transport, probe)
                except Exception:
                    pass
        except Exception as exc:
            self._observe_fault(error="MPD playback recovery failed: %s" % exc)
            with self._idle_lock:
                self._idle_state["error"] = "MPD playback recovery failed: %s" % exc
        finally:
            self._recovery_lock.release()

    def _wait_ready(self, timeout: float = 5.0) -> Dict[str, Any]:
        deadline = time.monotonic() + max(0.2, float(timeout))
        last = "MPD is not accepting connections"
        while time.monotonic() < deadline:
            supervisor = self.supervisor.status("mpd")
            if not supervisor.get("running"):
                return {
                    "running": False,
                    "message": supervisor.get("last_error") or "MPD exited before becoming ready",
                }
            probe = mpd_probe(self.host, self.port)
            if probe.get("running"):
                return {"running": True, "status": probe.get("status") or {}}
            last = probe.get("message") or last
            time.sleep(0.15)
        return {"running": False, "message": last}

    def shutdown(self) -> None:
        self._device_monitor_stop.set()
        if self._device_monitor_thread and self._device_monitor_thread.is_alive():
            self._device_monitor_thread.join(timeout=1.0)
        self._idle_stop.set()
        if self._idle_thread and self._idle_thread.is_alive():
            self._idle_thread.join(timeout=1.0)
        self.supervisor.shutdown()
        self._cleanup_stale_instances()

    def _start_device_monitor(self) -> None:
        if self._device_monitor_thread and self._device_monitor_thread.is_alive():
            return
        self._device_monitor_stop.clear()
        self._device_monitor_thread = threading.Thread(
            target=self._device_monitor_loop,
            name="fnaudio-usb-dac-monitor",
            daemon=True,
        )
        self._device_monitor_thread.start()

    def _device_monitor_loop(self) -> None:
        while not self._device_monitor_stop.wait(2.0):
            stable_id = str(self.config.get("mpd_output_stable_id") or "")
            if stable_id:
                selected = self._find_output_device(stable_id)
                self._device_presence, transition = device_presence_transition(
                    self._device_presence,
                    bool(selected),
                    self._device_presence_threshold,
                )
                if transition == "disconnected" and self.supervisor.status("mpd").get("running"):
                    self._selected_device_missing = True
                    self.suppress_stop_transition(5.0)
                    self.supervisor.stop("mpd")
                    AUDIO_OUTPUT_LEASE.release("mpd")
                    with self._idle_lock:
                        self._idle_state["error"] = "selected USB DAC disconnected"
                elif transition == "reconnected" and self._selected_device_missing:
                    self._selected_device_missing = False
                    self.config["mpd_output_alsa_id"] = selected.get("alsa_id") or ""
                    self._configured = False
                    started = self.start()
                    if started.get("running"):
                        self._schedule_playback_recovery("mpd", started)
            self._watch_for_playback_errors()

    def _watch_for_playback_errors(self) -> None:
        if not os.path.isfile(self.log_path) or not self._queue_entries:
            return
        try:
            size = os.path.getsize(self.log_path)
            if size < self._last_log_size:
                self._last_log_size = 0
            if size == self._last_log_size:
                return
            with open(self.log_path, "rb") as handle:
                handle.seek(max(self._last_log_size, size - 8192))
                chunk = handle.read().decode("utf-8", "ignore").lower()
            self._last_log_size = size
        except OSError:
            return
        summary = classify_mpd_log_errors(chunk)
        if not summary.get("count"):
            return
        latest = (summary.get("items") or [{}])[-1]
        counts = dict(self._playback_error_state.get("by_category") or {})
        for category, count in (summary.get("by_category") or {}).items():
            counts[category] = int(counts.get(category) or 0) + int(count or 0)
        self._playback_error_state.update(
            {
                "count": int(self._playback_error_state.get("count") or 0) + int(summary.get("occurrences") or 0),
                "last_detected": time.time(),
                "last_category": str(latest.get("category") or ""),
                "last_domain": str(latest.get("domain") or ""),
                "last_message": str(latest.get("message") or ""),
                "by_category": counts,
            }
        )
        output_items = [item for item in summary.get("items") or [] if item.get("domain") == "output"]
        if not output_items:
            return
        output_error = output_items[-1]
        category = str(output_error.get("category") or "")
        marker = str(output_error.get("message") or category)
        now = time.monotonic()
        if int((summary.get("by_category") or {}).get("buffer_underrun") or 0):
            self._underrun_state.update(
                {
                    "count": int(self._underrun_state.get("count") or 0)
                    + int(summary["by_category"]["buffer_underrun"]),
                    "last_detected": time.time(),
                    "last_message": marker,
                }
            )
        self._observe_fault(error=marker)
        if category in ("output_device_missing", "output_format_unsupported"):
            return
        if now - self._last_underrun_restart < 30.0:
            self._underrun_state["restart_suppressed"] = int(self._underrun_state.get("restart_suppressed") or 0) + 1
            return
        self._last_underrun_restart = now
        result = self.restart()
        if result.get("running"):
            self._underrun_state["last_restart"] = time.time()
            self._schedule_playback_recovery("mpd", result)

    def _watch_for_underrun(self) -> None:
        self._watch_for_playback_errors()

    def _runtime_env(self) -> Dict[str, str]:
        paths = []
        if os.path.isdir(self.lib_dir):
            paths.append(self.lib_dir)
        existing = os.environ.get("LD_LIBRARY_PATH", "")
        if existing:
            paths.append(existing)
        return {"LD_LIBRARY_PATH": os.pathsep.join(paths)} if paths else {}

    def _binary_version(self) -> str:
        if not self.binary:
            return ""
        if self._binary_version_cache is not None:
            return self._binary_version_cache
        try:
            env = {**os.environ, **self._runtime_env()}
            value = subprocess.check_output([self.binary, "--version"], stderr=subprocess.STDOUT, env=env, timeout=3).decode("utf-8", "replace").splitlines()[0]
        except Exception:
            value = ""
        self._binary_version_cache = value
        return value

    def _cleanup_stale_instances(self) -> None:
        if os.name == "nt":
            return
        stale_pids = set()
        pid_file = os.path.join(self.data_root, "mpd.pid")
        if os.path.isfile(pid_file):
            try:
                with open(pid_file, "r", encoding="utf-8", errors="ignore") as fh:
                    pid = int(str(fh.read()).strip().splitlines()[0])
                if pid > 1 and self._pid_matches_mpd(pid):
                    stale_pids.add(pid)
            except Exception:
                pass
        stale_pids.update(self._scan_matching_pids())
        for pid in sorted(stale_pids):
            self._terminate_pid(pid)

    def _scan_matching_pids(self) -> List[int]:
        if os.name == "nt":
            return []
        matches = []
        proc_root = "/proc"
        if not os.path.isdir(proc_root):
            return matches
        for entry in os.listdir(proc_root):
            if not entry.isdigit():
                continue
            pid = int(entry)
            if pid <= 1:
                continue
            if self._pid_matches_mpd(pid):
                matches.append(pid)
        return matches

    def _pid_matches_mpd(self, pid: int) -> bool:
        if pid <= 1:
            return False
        cmdline = f"/proc/{pid}/cmdline"
        try:
            with open(cmdline, "rb") as fh:
                raw = fh.read().replace(b"\x00", b" ").decode("utf-8", "ignore")
        except Exception:
            return False
        if not raw:
            return False
        text = raw.lower()
        return "mpd" in text and (self.config_path.lower() in text or self.data_root.lower() in text)

    def _terminate_pid(self, pid: int) -> None:
        if pid <= 1:
            return
        try:
            if hasattr(os, "killpg"):
                try:
                    os.killpg(pid, signal.SIGTERM)
                except Exception:
                    os.kill(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception:
            return
        deadline = time.time() + 2.5
        while time.time() < deadline:
            if not self._pid_alive(pid):
                return
            time.sleep(0.1)
        try:
            if hasattr(os, "killpg"):
                try:
                    os.killpg(pid, signal.SIGKILL)
                except Exception:
                    os.kill(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except Exception:
            pass

    def _pid_alive(self, pid: int) -> bool:
        if pid <= 1:
            return False
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _prepare_music_directory(self, roots: List[str]) -> str:
        if len(roots) <= 1:
            return roots[0] if roots else "/"
        os.makedirs(self.music_root, exist_ok=True)
        wanted = set()
        for index, root in enumerate(roots):
            root_path = os.path.abspath(os.path.expanduser(root))
            alias = self._root_alias(root_path, index)
            wanted.add(alias)
            link_path = os.path.join(self.music_root, alias)
            try:
                if os.path.lexists(link_path):
                    current = os.path.realpath(link_path)
                    if os.path.islink(link_path) and os.path.abspath(current) == root_path:
                        continue
                    if os.path.isdir(link_path) and not os.path.islink(link_path):
                        continue
                    os.unlink(link_path)
                os.symlink(root_path, link_path, target_is_directory=True)
            except OSError:
                pass
        for name in os.listdir(self.music_root):
            if name not in wanted:
                stale = os.path.join(self.music_root, name)
                try:
                    if os.path.islink(stale):
                        os.unlink(stale)
                except OSError:
                    pass
        return self.music_root

    def _root_alias(self, root_path: str, index: int) -> str:
        base = os.path.basename(os.path.normpath(root_path)) or "music"
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in base).strip("._")
        return "%02d_%s" % (index + 1, safe or "music")

    def _preferred_alsa_output(self) -> Dict[str, Any]:
        devices = alsa_devices()
        if not devices:
            return {"alsa_id": "default", "name": "default", "reason": "fallback"}

        def score(device: Dict[str, Any]) -> tuple:
            text = ("%s %s" % (device.get("name", ""), device.get("alsa_id", ""))).lower()
            usb = 1 if device.get("is_usb") or "usb" in text else 0
            analog = 1 if "analog" in text or "alc" in text else 0
            hdmi_penalty = 1 if "hdmi" in text else 0
            return (usb, analog, -hdmi_penalty, text)

        selected = sorted(devices, key=score, reverse=True)[0]
        return {
            "id": selected.get("id", ""),
            "alsa_id": selected.get("alsa_id") or "default",
            "stable_id": selected.get("stable_id", ""),
            "stable_alsa_id": selected.get("stable_alsa_id") or selected.get("alsa_id") or "default",
            "name": selected.get("name") or selected.get("alsa_id") or "default",
            "is_usb": bool(selected.get("is_usb")),
            "usb_vendor_id": selected.get("usb_vendor_id", ""),
            "usb_product_id": selected.get("usb_product_id", ""),
            "usb_serial": selected.get("usb_serial", ""),
            "caps": selected.get("caps") or {},
            "reason": "usb_first_then_analog_then_hdmi",
        }

    def _find_output_device(self, identifier: str, devices=None) -> Optional[Dict[str, Any]]:
        identifier = urllib.parse.unquote(str(identifier or "").strip())
        if identifier.startswith("mpd:") or identifier.startswith("dac:"):
            identifier = identifier.split(":", 1)[1]
        for device in devices if devices is not None else alsa_devices():
            candidates = {
                str(device.get("id") or ""),
                str(device.get("alsa_id") or ""),
                str(device.get("stable_id") or ""),
                str(device.get("stable_alsa_id") or ""),
            }
            candidates.update(value.split(":", 1)[1] for value in list(candidates) if value.startswith("dac:"))
            if identifier in candidates:
                return device
        return None

    def select_output(self, alsa_id: str) -> Dict[str, Any]:
        alsa_id = urllib.parse.unquote(str(alsa_id or "").strip())
        devices = alsa_devices()
        selected = self._find_output_device(alsa_id, devices)
        if not selected:
            return {"ok": False, "message": "没有找到这个 MPD 输出设备", "alsa_id": alsa_id}
        previous = str(self.config.get("mpd_output_alsa_id") or "")
        previous_stable = str(self.config.get("mpd_output_stable_id") or "")
        wanted_runtime = str(selected.get("alsa_id") or "")
        wanted_stable = str(selected.get("stable_id") or "")
        changed = previous != wanted_runtime or previous_stable != wanted_stable
        if not changed:
            return {"ok": True, "selected_output": self._public_output(selected), "changed": False}
        self.invalidate_output_capabilities()
        was_running = bool(self.supervisor.status("mpd").get("running"))
        previous_dop = bool(self.config.get("mpd_dop"))
        if was_running:
            self.suppress_stop_transition(5.0)
            self.stop()
        self.config["mpd_output_alsa_id"] = wanted_runtime
        self.config["mpd_output_stable_id"] = wanted_stable
        self._configured = False
        verification = probe_alsa_hw_params(selected, force=True)
        if not verification.get("available"):
            self.config.update({"mpd_output_alsa_id": previous, "mpd_output_stable_id": previous_stable, "mpd_dop": previous_dop})
            self._configured = False
            self.invalidate_output_capabilities()
            rollback = self.start() if was_running else {"running": False}
            return {"ok": False, "message": "ALSA 输出验证失败，已恢复原输出", "verification": verification, "rollback": rollback}
        activated = self.start() if was_running else self.ensure_config()
        if not activated.get("ok") or (was_running and not activated.get("running")):
            self.config.update({"mpd_output_alsa_id": previous, "mpd_output_stable_id": previous_stable, "mpd_dop": previous_dop})
            self._configured = False
            rollback = self.start() if was_running else self.ensure_config()
            return {"ok": False, "message": "新输出启动失败，已回滚原输出", "activation": activated, "rollback": rollback}
        self._persist_app_config()
        self.invalidate_output_capabilities()
        return {"ok": True, "selected_output": self._public_output(selected), "changed": True, "verification": verification, "activation": activated}

    def test_output(self, alsa_id: str, duration: float = 1.2) -> Dict[str, Any]:
        alsa_id = str(alsa_id or "").strip()
        devices = alsa_devices()
        device = self._find_output_device(alsa_id, devices)
        if not device:
            return {"ok": False, "message": "没有找到这个本机输出设备", "alsa_id": alsa_id, "devices": devices}
        alsa_id = str(device.get("alsa_id") or "")
        mixer = self._mixer_for_device(device)
        diagnostics = {
            "device": self._public_output(device),
            "mixer": mixer,
            "caps": device.get("caps") or {},
            "attempts": [],
        }
        previous_selection = {
            "mpd_output_alsa_id": str(self.config.get("mpd_output_alsa_id") or ""),
            "mpd_output_stable_id": str(self.config.get("mpd_output_stable_id") or ""),
            "mpd_dop": bool(self.config.get("mpd_dop")),
        }
        was_running = bool(self.supervisor.status("mpd").get("running"))
        # The bundled ffmpeg on fnOS may not include the ALSA muxer. Route the
        # test tone through MPD so the test exercises the same output path as
        # normal playback.
        try:
            previous = str(self.config.get("mpd_output_alsa_id") or "")
            self.config["mpd_output_alsa_id"] = alsa_id
            self.config["mpd_output_stable_id"] = str(device.get("stable_id") or "")
            self._configured = False
            started = self.start()
            if not started.get("running"):
                return {"ok": False, "message": started.get("message") or "MPD 未能启动", **diagnostics}
            test_root = self._library_paths()[0] if self._library_paths() else self.data_root
            test_path = os.path.join(test_root, ".fnaudio-output-test.wav")
            _write_test_wav(test_path, duration)
            loaded = mpd_load_uri(self.uri_for_path(test_path), host=self.host, port=self.port)
            diagnostics["attempts"].append({"target": alsa_id, "method": "mpd-wav", "mpd": loaded})
            time.sleep(max(0.4, min(2.0, float(duration or 1.2))))
            if previous != alsa_id:
                self.config["mpd_output_alsa_id"] = previous
                self._configured = False
                self.restart()
            try:
                os.unlink(test_path)
            except OSError:
                pass
            return {"ok": True, "message": "测试音已通过 MPD 发送到 %s" % (device.get("name") or alsa_id), "used_target": alsa_id, **diagnostics}
        except Exception as exc:
            return {"ok": False, "message": "MPD 测试音播放失败：%s" % exc, **diagnostics}

        finally:
            selection_changed = any(self.config.get(key) != value for key, value in previous_selection.items())
            self.config.update(previous_selection)
            if selection_changed:
                self._configured = False
                if was_running:
                    self.restart()

    def _selected_alsa_output(self) -> Dict[str, Any]:
        stable_wanted = str(self.config.get("mpd_output_stable_id") or "").strip()
        wanted = str(self.config.get("mpd_output_alsa_id") or "").strip()
        devices = alsa_devices()
        if stable_wanted:
            selected = self._find_output_device(stable_wanted, devices)
            if selected:
                runtime_id = selected.get("alsa_id") or ""
                if self.config.get("mpd_output_alsa_id") != runtime_id:
                    self.config["mpd_output_alsa_id"] = runtime_id
                    self._persist_app_config()
                return self._public_output(selected, "stable-selected")
        if wanted:
            selected = self._find_output_device(wanted, devices)
            if selected:
                self.config["mpd_output_stable_id"] = selected.get("stable_id") or ""
                self.config["mpd_output_alsa_id"] = selected.get("alsa_id") or ""
                self._persist_app_config()
                return self._public_output(selected, "legacy-migrated")
        selected = self._preferred_alsa_output()
        if selected and selected.get("alsa_id") != "default":
            self.config["mpd_output_stable_id"] = selected.get("stable_id") or ""
            self.config["mpd_output_alsa_id"] = selected.get("alsa_id") or ""
            self._persist_app_config()
        return selected

    def _public_output(self, selected: Dict[str, Any], reason: str = "selected") -> Dict[str, Any]:
        return {
            "id": selected.get("id", ""),
            "alsa_id": selected.get("alsa_id") or "default",
            "stable_id": selected.get("stable_id", ""),
            "stable_alsa_id": selected.get("stable_alsa_id") or selected.get("alsa_id") or "default",
            "name": selected.get("name") or selected.get("alsa_id") or "default",
            "raw_name": selected.get("raw_name", ""),
            "is_usb": bool(selected.get("is_usb")),
            "usb_vendor_id": selected.get("usb_vendor_id", ""),
            "usb_product_id": selected.get("usb_product_id", ""),
            "usb_serial": selected.get("usb_serial", ""),
            "caps": selected.get("caps") or {},
            "reason": reason,
        }

    def _mixer_for_device(self, device: Dict[str, Any]) -> Dict[str, Any]:
        amixer = shutil.which("amixer")
        if not amixer:
            return {"available": False, "controls": [], "message": "amixer is not installed"}
        card = str(device.get("alsa_id") or "").replace("hw:", "").split(",", 1)[0].strip()
        command = [amixer]
        if card:
            command += ["-c", card]
        command += ["scontents"]
        try:
            output = subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=2).decode("utf-8", "ignore")
        except Exception as exc:
            return {"available": False, "controls": [], "message": str(exc)}
        controls = []
        blocks = re.split(r"(?=^Simple mixer control )", output, flags=re.MULTILINE)
        for block in blocks:
            match = re.match(r"Simple mixer control '([^']+)'", block)
            if not match:
                continue
            if re.search(r"(?im)^\s*Capabilities:.*\bpvolume\b", block) or re.search(r"(?im)^\s*(?:Mono|Front Left|Front Right):\s+Playback\s+\d+", block):
                controls.append(match.group(1).strip())
        preferred = self._preferred_mixer_control(controls, str(self.config.get("mpd_mixer_control") or ""))
        return {
            "available": bool(controls),
            "controls": controls,
            "preferred_control": preferred,
            "card": card,
            "message": "" if controls else "no ALSA playback-volume control",
        }

    @staticmethod
    def _preferred_mixer_control(controls, configured=""):
        configured = str(configured or "").strip()
        by_lower = {str(control).casefold(): str(control) for control in controls or []}
        if configured and configured.casefold() in by_lower:
            return by_lower[configured.casefold()]
        for name in ("PCM", "Master", "Digital", "Speaker", "Headphone"):
            if name.casefold() in by_lower:
                return by_lower[name.casefold()]
        return str((controls or [""])[0])

    @staticmethod
    def _mixer_device(device: Dict[str, Any]) -> str:
        value = str(device.get("stable_alsa_id") or device.get("alsa_id") or "default")
        if not value.startswith("hw:"):
            return value
        body = value[3:]
        if body.startswith("CARD="):
            body = ",".join(part for part in body.split(",") if not part.startswith("DEV="))
        else:
            body = body.split(",", 1)[0]
        return "hw:" + body

    def mixer_policy(self, device: Optional[Dict[str, Any]] = None, mixer_probe: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        requested = str(self.config.get("mpd_mixer_type") or "none").strip().lower()
        if requested not in ("none", "software", "hardware"):
            requested = "none"
        if requested == "none":
            return {
                "requested_mode": requested,
                "mode": "none",
                "available": False,
                "bitperfect": True,
                "control": "",
                "device": "",
                "controls": [],
                "fallback": False,
                "message": "固定输出电平；fnAudio 不修改数字音量",
            }
        if requested == "software":
            return {
                "requested_mode": requested,
                "mode": "software",
                "available": True,
                "bitperfect": False,
                "control": "software",
                "device": "",
                "controls": [],
                "fallback": False,
                "message": "MPD 软件音量会改变音频样本，不属于 bit-perfect 输出",
            }
        device = device or self._selected_alsa_output()
        probe = dict(mixer_probe) if mixer_probe is not None else self._mixer_for_device(device)
        controls = [str(control) for control in probe.get("controls") or []]
        control = self._preferred_mixer_control(controls, str(self.config.get("mpd_mixer_control") or ""))
        if not probe.get("available") or not control:
            return {
                "requested_mode": requested,
                "mode": "none",
                "available": False,
                "bitperfect": True,
                "control": "",
                "device": "",
                "controls": controls,
                "fallback": True,
                "message": str(probe.get("message") or "所选设备没有可用的 ALSA Playback Volume 控件；已回退固定音量"),
            }
        return {
            "requested_mode": requested,
            "mode": "hardware",
            "available": True,
            "bitperfect": True,
            "control": control,
            "device": self._mixer_device(device),
            "controls": controls,
            "fallback": False,
            "message": "使用所选 DAC 的 ALSA 硬件音量控件",
        }


def _mpd_quote(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _tail_text(path: str, limit: int = 4000) -> str:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - max(1, int(limit))))
            return fh.read().decode("utf-8", "replace")
    except OSError:
        return ""


def classify_decoder_errors(log_text: str, limit: int = 20) -> Dict[str, Any]:
    return legacy_decoder_error_summary(classify_mpd_log_errors(log_text, limit))


def normalized_transport(probe: Mapping[str, Any]) -> str:
    """Resolve transport from normalized MPD status, then raw MPD state.

    During process recovery the idle listener can observe the old STOPPED
    event before the rebuilt queue has emitted a new one.  Raw MPD state is
    authoritative in that gap and prevents stale STOPPED publication.
    """
    status = probe.get("status") if isinstance(probe, Mapping) else {}
    status = status if isinstance(status, Mapping) else {}
    transport = status.get("transport")
    transport = transport.get("state") if isinstance(transport, Mapping) else transport
    normalized = str(transport or "").upper()
    if normalized in ("PLAYING", "PAUSED", "STOPPED"):
        return normalized
    raw = status.get("raw") if isinstance(status.get("raw"), Mapping) else {}
    return {
        "play": "PLAYING",
        "pause": "PAUSED",
        "stop": "STOPPED",
    }.get(str(raw.get("state") or "").lower(), "")


def _tcp_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, int(port)))
            return True
        except OSError:
            return False


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _write_test_wav(path: str, duration: float = 1.2) -> None:
    sample_rate = 44100
    frames = int(sample_rate * max(0.3, min(5.0, float(duration or 1.2))))
    with wave.open(path, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for index in range(frames):
            value = int(5000 * math.sin(2 * math.pi * 880 * index / sample_rate))
            wav.writeframes(struct.pack("<hh", value, value))
