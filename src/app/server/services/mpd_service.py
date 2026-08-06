from __future__ import annotations

import math
import os
import shutil
import signal
import socket
import struct
import subprocess
import threading
import time
import urllib.parse
import wave
from typing import Any, Dict, List, Optional

from playback.mpd_client import DEFAULT_HOST, DEFAULT_PORT, mpd_binary, mpd_idle, mpd_load_uri, mpd_probe, mpd_status
from playback.alsa_output import alsa_devices, find_ffmpeg
from .process_supervisor import ProcessSupervisor


class MpdService:
    """Owns an app-private MPD instance when an MPD binary is available."""

    def __init__(self, config: Dict[str, Any], app_root: Optional[str] = None):
        self.config = config
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

    def refresh_database(self) -> Dict[str, Any]:
        from playback.mpd_client import mpd_request

        try:
            mpd_request("update", host=self.host, port=self.port)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def ensure_config(self) -> Dict[str, Any]:
        if not self.binary:
            return {"ok": False, "available": False, "message": "MPD is not installed"}
        os.makedirs(self.data_root, exist_ok=True)
        roots = self._library_paths()
        music_directory = self._prepare_music_directory(roots)
        playlist_directory = os.path.join(self.data_root, "playlists")
        os.makedirs(playlist_directory, exist_ok=True)
        output_device = self._selected_alsa_output()
        output_name = output_device.get("name") or "fnAudio MPD"
        output_alsa_id = output_device.get("alsa_id") or "default"
        config = "\n".join(
            [
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
                'follow_outside_symlinks "yes"',
                'follow_inside_symlinks "yes"',
                'filesystem_charset "UTF-8"',
                "",
                'audio_output {',
                '    type "alsa"',
                '    name "%s"' % _mpd_quote("fnAudio MPD - " + output_name),
                '    device "%s"' % _mpd_quote(output_alsa_id),
                '    mixer_type "software"',
                "}",
                "",
            ]
        )
        config_changed = not os.path.isfile(self.config_path) or _read_text(self.config_path) != config
        if config_changed:
            temp_path = self.config_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(config)
            os.replace(temp_path, self.config_path)
        self._configured = True
        return {
            "ok": True,
            "available": True,
            "binary": self.binary,
            "config_path": self.config_path,
            "data_root": self.data_root,
            "music_directory": music_directory,
            "output_device": output_device,
            "config_changed": config_changed,
            "host": self.host,
            "port": self.port,
        }

    def start(self) -> Dict[str, Any]:
        setup = self.ensure_config()
        if not setup.get("ok"):
            return setup
        if not self.supervisor.status("mpd").get("running"):
            self._cleanup_stale_instances()
        self.supervisor.register(
            "mpd",
            [self.binary, "--no-daemon", self.config_path],
            cwd=self.data_root,
            env=self._runtime_env(),
            log_path=self.log_path,
            restart=True,
        )
        if setup.get("config_changed") and self.supervisor.status("mpd").get("running"):
            result = self.supervisor.restart("mpd")
        else:
            result = self.supervisor.start("mpd")
        if not result.get("ok"):
            return {**setup, **result}
        ready = self._wait_ready()
        if not ready.get("running"):
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

    def stop(self) -> Dict[str, Any]:
        self._idle_stop.set()
        if self._idle_thread and self._idle_thread.is_alive():
            self._idle_thread.join(timeout=1.0)
        result = self.supervisor.stop("mpd")
        # A previous app crash may have orphaned an MPD process which is no
        # longer owned by this in-memory supervisor instance.
        self._cleanup_stale_instances()
        return result

    def restart(self) -> Dict[str, Any]:
        setup = self.ensure_config()
        if not setup.get("ok"):
            return setup
        if not self.supervisor.status("mpd").get("running"):
            self._cleanup_stale_instances()
        self.supervisor.register(
            "mpd",
            [self.binary, "--no-daemon", self.config_path],
            cwd=self.data_root,
            env=self._runtime_env(),
            log_path=self.log_path,
            restart=True,
        )
        result = self.supervisor.restart("mpd")
        if not result.get("ok"):
            return {**setup, **result}
        ready = self._wait_ready()
        if not ready.get("running"):
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

    def status(self) -> Dict[str, Any]:
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
        return {
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
            "recent_log": _tail_text(self.log_path, 4000),
        }

    def refresh_status(self) -> Dict[str, Any]:
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
        return self._project_cached_probe(probe)

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

    def output_capabilities(self) -> Dict[str, Any]:
        devices = []
        rates = set()
        max_bits = 0
        dsd_native = False
        dop = False
        for device in alsa_devices():
            caps = dict(device.get("caps") or {})
            for rate in caps.get("pcm_rates") or []:
                try:
                    rates.add(int(rate))
                except (TypeError, ValueError):
                    pass
            try:
                max_bits = max(max_bits, int(caps.get("pcm_max_bits") or 0))
            except (TypeError, ValueError):
                pass
            dsd_native = bool(dsd_native or caps.get("dsd"))
            dsd_text = " ".join(str(x) for x in caps.get("dsd_rates") or []).lower()
            dop = bool(dop or "dop" in dsd_text)
            devices.append(
                {
                    "id": device.get("id", ""),
                    "alsa_id": device.get("alsa_id", ""),
                    "name": device.get("name", ""),
                    "raw_name": device.get("raw_name", ""),
                    "is_usb": bool(device.get("is_usb")),
                    "caps": caps,
                    "mixer": self._mixer_for_device(device),
                }
            )
        mixers = [device["mixer"] for device in devices if device.get("mixer", {}).get("available")]
        return {
            "backend": "alsa",
            "device": "default",
            "pcm_rates": sorted(rates),
            "pcm_max_rate": max(rates) if rates else 0,
            "pcm_max_bits": max_bits,
            "dsd_native": dsd_native,
            "dop": dop,
            "hardware_volume": bool(mixers),
            "alsa_mixer": bool(mixers),
            "mixers": mixers,
            "devices": devices,
        }

    def idle_status(self) -> Dict[str, Any]:
        with self._idle_lock:
            return dict(self._idle_state)

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
                            "transport": ((refreshed.get("status") or {}).get("transport") or {}).get("state", ""),
                        }
                    )
            except Exception as exc:
                with self._idle_lock:
                    self._idle_state["error"] = str(exc)
                self._idle_stop.wait(1.0)

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
        self._idle_stop.set()
        if self._idle_thread and self._idle_thread.is_alive():
            self._idle_thread.join(timeout=1.0)
        self.supervisor.shutdown()
        self._cleanup_stale_instances()

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
        try:
            env = {**os.environ, **self._runtime_env()}
            return subprocess.check_output([self.binary, "--version"], stderr=subprocess.STDOUT, env=env, timeout=3).decode("utf-8", "replace").splitlines()[0]
        except Exception:
            return ""

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
            "name": selected.get("name") or selected.get("alsa_id") or "default",
            "is_usb": bool(selected.get("is_usb")),
            "caps": selected.get("caps") or {},
            "reason": "usb_first_then_analog_then_hdmi",
        }

    def select_output(self, alsa_id: str) -> Dict[str, Any]:
        alsa_id = str(alsa_id or "").strip()
        if alsa_id.startswith("dac:"):
            alsa_id = alsa_id[4:]
        devices = alsa_devices()
        selected = next((device for device in devices if device.get("alsa_id") == alsa_id), None)
        if not selected:
            return {"ok": False, "message": "娌℃湁鎵惧埌杩欎釜 MPD 杈撳嚭璁惧", "alsa_id": alsa_id}
        previous = str(self.config.get("mpd_output_alsa_id") or "")
        self.config["mpd_output_alsa_id"] = alsa_id
        if previous != alsa_id:
            self._configured = False
        return {"ok": True, "selected_output": self._public_output(selected), "changed": previous != alsa_id}

    def test_output(self, alsa_id: str, duration: float = 1.2) -> Dict[str, Any]:
        alsa_id = str(alsa_id or "").strip()
        if alsa_id.startswith("mpd:"):
            alsa_id = alsa_id[4:]
        if alsa_id.startswith("dac:"):
            alsa_id = alsa_id[4:]
        devices = alsa_devices()
        device = next((item for item in devices if item.get("alsa_id") == alsa_id), None)
        if not device:
            return {"ok": False, "message": "娌℃湁鎵惧埌杩欎釜鏈満杈撳嚭璁惧", "alsa_id": alsa_id, "devices": devices}
        mixer = self._mixer_for_device(device)
        diagnostics = {
            "device": self._public_output(device),
            "mixer": mixer,
            "caps": device.get("caps") or {},
            "attempts": [],
        }
        # The bundled ffmpeg on fnOS may not include the ALSA muxer. Route the
        # test tone through MPD so the test exercises the same output path as
        # normal playback.
        try:
            previous = str(self.config.get("mpd_output_alsa_id") or "")
            self.config["mpd_output_alsa_id"] = alsa_id
            self._configured = False
            started = self.start()
            if not started.get("running"):
                return {"ok": False, "message": started.get("message") or "MPD 鏈兘鍚姩", **diagnostics}
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
            return {"ok": True, "message": "娴嬭瘯闊冲凡閫氳繃 MPD 鍙戦€佸埌 %s" % (device.get("name") or alsa_id), "used_target": alsa_id, **diagnostics}
        except Exception as exc:
            return {"ok": False, "message": "MPD 娴嬭瘯闊虫挱鏀惧け璐ワ細%s" % exc, **diagnostics}

    def _selected_alsa_output(self) -> Dict[str, Any]:
        wanted = str(self.config.get("mpd_output_alsa_id") or "").strip()
        if wanted.startswith("dac:"):
            wanted = wanted[4:]
        devices = alsa_devices()
        if wanted:
            selected = next((device for device in devices if device.get("alsa_id") == wanted), None)
            if selected:
                return self._public_output(selected, "selected")
        return self._preferred_alsa_output()

    def _public_output(self, selected: Dict[str, Any], reason: str = "selected") -> Dict[str, Any]:
        return {
            "id": selected.get("id", ""),
            "alsa_id": selected.get("alsa_id") or "default",
            "name": selected.get("name") or selected.get("alsa_id") or "default",
            "raw_name": selected.get("raw_name", ""),
            "is_usb": bool(selected.get("is_usb")),
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
        command += ["scontrols"]
        try:
            output = subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=2).decode("utf-8", "ignore")
        except Exception as exc:
            return {"available": False, "controls": [], "message": str(exc)}
        controls = []
        for line in output.splitlines():
            marker = "Simple mixer control "
            if marker in line:
                controls.append(line.split(marker, 1)[1].strip().strip("'"))
        return {"available": bool(controls), "controls": controls}


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
