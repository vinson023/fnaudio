from __future__ import annotations

import os
import shutil
import shlex
import threading
from typing import Any, Dict, Iterable

MAX_PROC_CMDLINE_BYTES = 4096
MAX_AIRPLAY_COMMAND_BYTES = 4096
MAX_AIRPLAY_PATH_BYTES = 512

from .audio_output_lease import AUDIO_OUTPUT_LEASE
from .process_supervisor import ProcessSupervisor


def _first_binary(candidates: Iterable[str]) -> str:
    for candidate in candidates:
        if not candidate:
            continue
        path = candidate if os.path.isfile(candidate) else shutil.which(candidate)
        if path:
            return os.path.abspath(path)
    return ""


def _config_text(config: Dict[str, Any], key: str, maximum: int) -> str:
    value = config.get(key)
    return value.strip()[:maximum] if isinstance(value, str) else ""


def _process_running(name: str) -> bool:
    proc_root = "/proc"
    if os.name == "nt" or not os.path.isdir(proc_root):
        return False
    wanted = str(name or "").lower()
    try:
        entries = os.listdir(proc_root)
    except OSError:
        return False
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(os.path.join(proc_root, entry, "cmdline"), "rb") as handle:
                command = handle.read(MAX_PROC_CMDLINE_BYTES + 1)
                command = command[:MAX_PROC_CMDLINE_BYTES]
                command = command.replace(b"\x00", b" ").decode("utf-8", "ignore").lower()
        except OSError:
            continue
        if wanted and wanted in command:
            return True
    return False


def airplay_probe(config: Dict[str, Any] | None = None, app_root: str = "") -> Dict[str, Any]:
    """Report real AirPlay receiver prerequisites without claiming support.

    Volumio and moOde supervise shairport-sync (and nqptp for AirPlay 2).
    fnAudio exposes the same dependency boundary first; service ownership and
    metadata integration can be enabled only after the binaries are present.
    """
    config = config or {}
    roots = [app_root, os.environ.get("TRIM_APPDEST", "")]
    shairport = _first_binary(
        [
            _config_text(config, "shairport_sync_path", MAX_AIRPLAY_PATH_BYTES),
            *[os.path.join(root, "bin", "shairport-sync") for root in roots if root],
            "/usr/local/bin/shairport-sync",
            "/usr/bin/shairport-sync",
            "shairport-sync",
        ]
    )
    nqptp = _first_binary(
        [
            _config_text(config, "nqptp_path", MAX_AIRPLAY_PATH_BYTES),
            *[os.path.join(root, "bin", "nqptp") for root in roots if root],
            "/usr/local/bin/nqptp",
            "/usr/bin/nqptp",
            "nqptp",
        ]
    )
    receiver_available = bool(shairport)
    raw_enabled = config.get("airplay_enabled", False) if isinstance(config, dict) else False
    enabled = raw_enabled if isinstance(raw_enabled, bool) else False
    return {
        "available": receiver_available,
        "configured": enabled and receiver_available,
        "running": _process_running("shairport-sync"),
        "airplay1": receiver_available,
        "airplay2": bool(shairport and nqptp),
        "binaries": {"shairport_sync": shairport, "nqptp": nqptp},
        "audio_ownership": "not_configured",
        "metadata": False,
        "message": "" if receiver_available else "shairport-sync is not installed; AirPlay receiver is unavailable",
    }


class AirplayService:
    """Supervise shairport-sync without stealing an active DAC implicitly.

    Volumio/moOde treat AirPlay as an input daemon with explicit output
    ownership.  This small service follows that boundary: it only starts when
    enabled and the receiver binary exists, acquires the shared ALSA lease,
    and releases it on stop or supervisor exhaustion.
    """

    def __init__(self, config: Dict[str, Any], app_root: str = ""):
        self.config = config
        self.app_root = app_root
        self.supervisor = ProcessSupervisor(poll_interval=1.0)
        self._lock = threading.RLock()
        self._registered = False

    def _probe(self) -> Dict[str, Any]:
        return airplay_probe(self.config, self.app_root)

    def _command(self, binary: str):
        configured = _config_text(self.config, "airplay_command", MAX_AIRPLAY_COMMAND_BYTES)
        if configured:
            try:
                parts = shlex.split(configured)
            except ValueError:
                return []
            if parts:
                return parts
        # Explicit ALSA device keeps ownership deterministic.  shairport-sync
        # can still use its own defaults when no device is configured.
        command = [binary]
        device = _config_text(self.config, "airplay_alsa_device", MAX_AIRPLAY_PATH_BYTES)
        if device:
            command += ["-a", device]
        return command

    def _release_audio_output(self, _name: str = "", _status: Dict[str, Any] | None = None) -> None:
        """Return the ALSA lease when the supervised receiver gives up."""
        AUDIO_OUTPUT_LEASE.release("airplay")

    def start(self) -> Dict[str, Any]:
        with self._lock:
            probe = self._probe()
            if not probe.get("available"):
                return {"ok": False, "running": False, "message": probe.get("message") or "AirPlay receiver unavailable", "probe": probe}
            command = self._command(probe["binaries"]["shairport_sync"])
            if not command:
                return {"ok": False, "running": False, "message": "invalid AirPlay command", "probe": probe}
            lease = AUDIO_OUTPUT_LEASE.acquire("airplay", _config_text(self.config, "airplay_alsa_device", MAX_AIRPLAY_PATH_BYTES))
            if not lease.get("ok"):
                return {"ok": False, "running": False, "message": lease.get("message") or "audio output is busy", "probe": probe, "lease": lease}
            if not self._registered:
                self.supervisor.register(
                    "airplay",
                    command,
                    log_path=_config_text(self.config, "airplay_log", MAX_AIRPLAY_PATH_BYTES) or None,
                    max_restarts=8,
                    restart_window=120.0,
                    restart_backoff=1.5,
                    on_exhaust=self._release_audio_output,
                )
                self._registered = True
            result = self.supervisor.start("airplay")
            running = isinstance(result, dict) and result.get("running") is True
            if not running:
                AUDIO_OUTPUT_LEASE.release("airplay")
            projected = dict(result) if isinstance(result, dict) else {}
            projected["running"] = running
            projected["ok"] = running
            return {**projected, "probe": probe, "lease": AUDIO_OUTPUT_LEASE.snapshot()}

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            result = self.supervisor.stop("airplay") if self._registered else {"ok": True, "running": False}
            AUDIO_OUTPUT_LEASE.release("airplay")
            projected = dict(result) if isinstance(result, dict) else {}
            projected["ok"] = isinstance(result, dict) and result.get("ok") is True
            projected["running"] = isinstance(result, dict) and result.get("running") is True
            return {**projected, "lease": AUDIO_OUTPUT_LEASE.snapshot()}

    def status(self) -> Dict[str, Any]:
        probe = self._probe()
        process = self.supervisor.status("airplay") if self._registered else {"available": False, "running": False}
        raw_enabled = self.config.get("airplay_enabled", False) if isinstance(self.config, dict) else False
        enabled = raw_enabled if isinstance(raw_enabled, bool) else False
        return {"probe": probe, "process": process, "lease": AUDIO_OUTPUT_LEASE.snapshot(), "configured": enabled}

    def shutdown(self):
        self.stop()
        self.supervisor.shutdown()


__all__ = ["airplay_probe", "AirplayService"]
