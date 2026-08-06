from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from typing import Dict, List, Optional


class ProcessSupervisor:
    """Small process lifecycle manager for app-private daemons."""

    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self._lock = threading.RLock()
        self._entries: Dict[str, Dict] = {}
        self._thread: Optional[threading.Thread] = None
        self._stopping = False

    def register(
        self,
        name: str,
        command: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        log_path: Optional[str] = None,
        restart: bool = True,
    ) -> None:
        with self._lock:
            previous = self._entries.get(name) or {}
            process = previous.get("process")
            running = bool(process and process.poll() is None)
            self._entries[name] = {
                "name": name,
                "command": list(command),
                "cwd": cwd,
                "env": dict(env or {}),
                "log_path": log_path,
                "restart": bool(restart),
                "desired": bool(previous.get("desired")) if previous else False,
                "process": process if running else None,
                "last_error": previous.get("last_error") or "",
                "last_start": previous.get("last_start") or 0.0,
                "restart_after": previous.get("restart_after") or 0.0,
            }
            self._ensure_monitor()

    def _ensure_monitor(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stopping = False
        self._thread = threading.Thread(target=self._monitor, name="fnaudio-process-supervisor", daemon=True)
        self._thread.start()

    def start(self, name: str) -> Dict:
        with self._lock:
            entry = self._entries.get(name)
            if not entry:
                return {"ok": False, "message": "unknown process: %s" % name}
            entry["desired"] = True
            result = self._start_locked(entry)
            self._ensure_monitor()
            return result

    def stop(self, name: str) -> Dict:
        with self._lock:
            entry = self._entries.get(name)
            if not entry:
                return {"ok": False, "message": "unknown process: %s" % name}
            entry["desired"] = False
            process = entry.get("process")
            entry["process"] = None
            if process and process.poll() is None:
                try:
                    if os.name != "nt":
                        os.killpg(process.pid, signal.SIGTERM)
                    else:
                        process.terminate()
                    process.wait(timeout=3)
                except Exception:
                    try:
                        if os.name != "nt":
                            os.killpg(process.pid, signal.SIGKILL)
                        else:
                            process.kill()
                    except Exception:
                        pass
            return {"ok": True, "running": False}

    def restart(self, name: str) -> Dict:
        self.stop(name)
        return self.start(name)

    def status(self, name: str) -> Dict:
        with self._lock:
            entry = self._entries.get(name)
            if not entry:
                return {"available": False, "running": False, "message": "unknown process: %s" % name}
            process = entry.get("process")
            running = bool(process and process.poll() is None)
            return {
                "available": True,
                "running": running,
                "desired": bool(entry.get("desired")),
                "pid": process.pid if running else 0,
                "command": list(entry.get("command") or []),
                "last_error": entry.get("last_error") or "",
                "last_start": entry.get("last_start") or 0,
            }

    def shutdown(self) -> None:
        with self._lock:
            self._stopping = True
            names = list(self._entries)
        for name in names:
            self.stop(name)

    def _start_locked(self, entry: Dict) -> Dict:
        process = entry.get("process")
        if process and process.poll() is None:
            return {"ok": True, "running": True, "pid": process.pid}
        command = entry["command"]
        if not command or not os.path.isfile(command[0]) and not _command_exists(command[0]):
            entry["last_error"] = "executable not found: %s" % (command[0] if command else "")
            return {"ok": False, "running": False, "message": entry["last_error"]}
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL
        log_path = entry.get("log_path")
        log_handle = None
        try:
            if log_path:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                log_handle = open(log_path, "ab", buffering=0)
                stdout = log_handle
                stderr = log_handle
            process = subprocess.Popen(
                command,
                cwd=entry.get("cwd") or None,
                env={**os.environ, **entry.get("env", {})},
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
            entry["process"] = process
            entry["last_error"] = ""
            entry["last_start"] = time.time()
            return {"ok": True, "running": True, "pid": process.pid}
        except Exception as exc:
            entry["last_error"] = str(exc)
            return {"ok": False, "running": False, "message": str(exc)}
        finally:
            if log_handle:
                log_handle.close()

    def _monitor(self) -> None:
        while not self._stopping:
            time.sleep(self.poll_interval)
            with self._lock:
                for entry in self._entries.values():
                    process = entry.get("process")
                    if process and process.poll() is not None:
                        entry["process"] = None
                        if entry.get("desired") and entry.get("restart"):
                            entry["restart_after"] = time.time() + 2
                    if (
                        entry.get("desired")
                        and entry.get("restart")
                        and not entry.get("process")
                        and time.time() >= float(entry.get("restart_after") or 0)
                    ):
                        self._start_locked(entry)


def _command_exists(command: str) -> bool:
    if os.path.sep in command:
        return False
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory, command)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return True
    return False
