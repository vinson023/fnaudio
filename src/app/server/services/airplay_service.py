from __future__ import annotations

import os
import shutil
import shlex
import threading
from typing import Any, Dict, Iterable

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
                command = handle.read().replace(b"\x00", b" ").decode("utf-8", "ignore").lower()
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
            str(config.get("shairport_sync_path") or ""),
            *[os.path.join(root, "bin", "shairport-sync") for root in roots if root],
            "/usr/local/bin/shairport-sync",
            "/usr/bin/shairport-sync",
            "shairport-sync",
        ]
    )
    nqptp = _first_binary(
        [
            str(config.get("nqptp_path") or ""),
            *[os.path.join(root, "bin", "nqptp") for root in roots if root],
            "/usr/local/bin/nqptp",
            "/usr/bin/nqptp",
            "nqptp",
        ]
    )
    receiver_available = bool(shairport)
    return {
        "available": receiver_available,
        "configured": bool(config.get("airplay_enabled")) and receiver_available,
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
        configured = self.config.get("airplay_command")
        if configured:
            parts = shlex.split(str(configured))
            if parts:
                return parts
        # Explicit ALSA device keeps ownership deterministic.  shairport-sync
        # can still use its own defaults when no device is configured.
        command = [binary]
        device = str(self.config.get("airplay_alsa_device") or "").strip()
        if device:
            command += ["-a", device]
        return command

    def start(self) -> Dict[str, Any]:
        with self._lock:
            probe = self._probe()
            if not probe.get("available"):
                return {"ok": False, "running": False, "message": probe.get("message") or "AirPlay receiver unavailable", "probe": probe}
            lease = AUDIO_OUTPUT_LEASE.acquire("airplay", str(self.config.get("airplay_alsa_device") or ""))
            if not lease.get("ok"):
                return {"ok": False, "running": False, "message": lease.get("message") or "audio output is busy", "probe": probe, "lease": lease}
            if not self._registered:
                self.supervisor.register("airplay", self._command(probe["binaries"]["shairport_sync"]), log_path=str(self.config.get("airplay_log") or "") or None, max_restarts=8, restart_window=120.0, restart_backoff=1.5)
                self._registered = True
            result = self.supervisor.start("airplay")
            if not result.get("running"):
                AUDIO_OUTPUT_LEASE.release("airplay")
            return {"ok": bool(result.get("running")), **result, "probe": probe, "lease": AUDIO_OUTPUT_LEASE.snapshot()}

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            result = self.supervisor.stop("airplay") if self._registered else {"ok": True, "running": False}
            AUDIO_OUTPUT_LEASE.release("airplay")
            return {**result, "lease": AUDIO_OUTPUT_LEASE.snapshot()}

    def status(self) -> Dict[str, Any]:
        probe = self._probe()
        process = self.supervisor.status("airplay") if self._registered else {"available": False, "running": False}
        return {"probe": probe, "process": process, "lease": AUDIO_OUTPUT_LEASE.snapshot(), "configured": bool(self.config.get("airplay_enabled"))}

    def shutdown(self):
        self.stop()
        self.supervisor.shutdown()


__all__ = ["airplay_probe", "AirplayService"]
