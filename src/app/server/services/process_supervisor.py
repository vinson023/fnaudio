from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from collections import deque
from typing import Callable, Dict, List, Optional

from file_permissions import secure_directory, secure_file
from process_error_policy import process_error_text

MAX_RESTART_HISTORY = 100000
STATUS_RESTART_HISTORY = 32
MAX_SERVICE_LOG_BYTES = 1024 * 1024
SERVICE_LOG_TRIM_THRESHOLD_BYTES = MAX_SERVICE_LOG_BYTES + (256 * 1024)


def _strict_bool(value, default=False):
    return value if isinstance(value, bool) else default


def _reap_exited_process(process):
    """Collect an exited child before dropping the only Popen handle."""
    if not process:
        return
    try:
        if process.poll() is not None:
            process.wait(timeout=0)
    except (OSError, subprocess.TimeoutExpired, AttributeError):
        pass


def _terminate_process(process):
    if not process or process.poll() is not None:
        _reap_exited_process(process)
        return
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=3)
        return
    except Exception:
        pass
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except Exception:
        pass
    try:
        process.wait(timeout=2)
    except Exception:
        pass


def _bounded_restart_history(values, limit):
    """Return the newest ``limit`` finite restart stamps, oldest first.

    The history is append-ordered, so a bound taken from the front keeps the
    oldest entries and discards exactly the evidence the restart cap and the
    status projection depend on: the window filter then sees nothing recent,
    ``max_restarts`` is never reached, and an unavailable dependency restarts
    forever.
    """
    result = deque()
    seen = set()
    if isinstance(values, (str, bytes, dict)):
        return []
    try:
        iterator = iter(values or ())
        keep = min(MAX_RESTART_HISTORY, max(0, int(limit)))
    except Exception:
        return []
    if keep <= 0:
        return []
    # The scan stays bounded by MAX_RESTART_HISTORY, which is also the largest
    # keep any caller can ask for, so eviction keeps this linear.
    for _ in range(MAX_RESTART_HISTORY):
        try:
            value = next(iterator)
            stamp = float(value)
        except StopIteration:
            break
        except (TypeError, ValueError, OverflowError):
            continue
        if stamp != stamp or stamp in seen:
            continue
        result.append(stamp)
        seen.add(stamp)
        while len(result) > keep:
            seen.discard(result.popleft())
    return list(result)


def _trim_service_log(path):
    """Keep daemon logs useful without letting a noisy child exhaust storage."""
    if not isinstance(path, str) or not path:
        return
    try:
        if os.path.getsize(path) <= SERVICE_LOG_TRIM_THRESHOLD_BYTES:
            return
        with open(path, "r+b") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            if size <= MAX_SERVICE_LOG_BYTES:
                return
            handle.seek(-MAX_SERVICE_LOG_BYTES, os.SEEK_END)
            tail = handle.read(MAX_SERVICE_LOG_BYTES)
            handle.seek(0)
            handle.write(tail)
            handle.truncate()
        secure_file(path)
    except OSError:
        # A log is diagnostic-only. A transient permission or replacement race
        # must not stop lifecycle monitoring for the service itself.
        return


class ProcessSupervisor:
    """Small process lifecycle manager for app-private daemons."""

    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = _safe_float(poll_interval, 2.0, minimum=0.01, maximum=60.0)
        self._lock = threading.RLock()
        self._entries: Dict[str, Dict] = {}
        self._thread: Optional[threading.Thread] = None
        self._monitor_generation = 0
        self._stopping = False
        self._wake_event = threading.Event()
        # Serializes the final lifecycle check with callback invocation. The
        # monitor must not start a callback after shutdown has marked itself
        # stopped, even if the event was collected just before shutdown.
        # Re-entrant because lifecycle callbacks are application code and may
        # legitimately request supervisor shutdown from the monitor thread.
        self._callback_gate = threading.RLock()

    def register(
        self,
        name: str,
        command: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        log_path: Optional[str] = None,
        restart: bool = True,
        max_restarts: int = 5,
        restart_window: float = 60.0,
        restart_backoff: float = 2.0,
        on_restart: Optional[Callable[[str, Dict], None]] = None,
        on_exhaust: Optional[Callable[[str, Dict], None]] = None,
        nice: int = 0,
    ) -> None:
        safe_command = _normalise_command(command)
        safe_max_restarts = _safe_int(max_restarts, 5, minimum=1, maximum=100000)
        safe_restart_window = _safe_float(restart_window, 60.0, minimum=5.0, maximum=86400.0)
        safe_restart_backoff = _safe_float(restart_backoff, 2.0, minimum=0.01, maximum=30.0)
        safe_nice = _safe_int(nice, 0, minimum=-20, maximum=19)
        with self._lock:
            previous = self._entries.get(name) or {}
            process = previous.get("process")
            running = bool(process and process.poll() is None)
            launch_changed = (
                running and (
                    safe_command != previous.get("command") or
                    cwd != previous.get("cwd") or
                    dict(env or {}) != previous.get("env", {}) or
                    log_path != previous.get("log_path") or
                    safe_nice != _safe_int(previous.get("nice"), 0, minimum=-20, maximum=19)
                )
            )
            if launch_changed:
                # Re-registering a service is also used by configuration
                # reloads. Never report the old process as the new command.
                _terminate_process(process)
                process = None
                running = False
            if process and not running:
                _reap_exited_process(process)
            self._entries[name] = {
                "name": name,
                "command": safe_command,
                "cwd": cwd,
                "env": dict(env or {}),
                "log_path": log_path,
                # Configuration values must not use Python truthiness here:
                # a persisted string such as "false" would otherwise enable
                # automatic restarts.
                "restart": _strict_bool(restart),
                "max_restarts": safe_max_restarts,
                "restart_window": safe_restart_window,
                "restart_backoff": safe_restart_backoff,
                "restart_times": _bounded_restart_history(previous.get("restart_times"), safe_max_restarts),
                "restart_times_monotonic": _bounded_restart_history(previous.get("restart_times_monotonic"), safe_max_restarts),
                "restart_count": _safe_int(
                    previous.get("restart_count"), 0, minimum=0, maximum=MAX_RESTART_HISTORY,
                ),
                "restart_exhausted": _strict_bool(previous.get("restart_exhausted")),
                "on_restart": on_restart or previous.get("on_restart"),
                "on_exhaust": on_exhaust or previous.get("on_exhaust"),
                "nice": safe_nice,
                "desired": _strict_bool(previous.get("desired")) if previous else False,
                "process": process if running else None,
                "last_error": process_error_text(previous.get("last_error"), default=""),
                "last_start": previous.get("last_start") or 0.0,
                "restart_after": previous.get("restart_after") or 0.0,
                "restart_after_monotonic": previous.get("restart_after_monotonic") or 0.0,
            }
            self._ensure_monitor()

    def _ensure_monitor(self) -> None:
        if self._thread and self._thread.is_alive() and not self._stopping:
            return
        self._stopping = False
        self._wake_event.clear()
        self._monitor_generation += 1
        generation = self._monitor_generation
        try:
            thread = threading.Thread(target=self._monitor, args=(generation,), name="fnaudio-process-supervisor", daemon=True)
            self._thread = thread
            thread.start()
        except Exception:
            if "thread" in locals() and self._thread is thread:
                self._thread = None
            self._stopping = False
            raise

    def start(self, name: str) -> Dict:
        with self._lock:
            entry = self._entries.get(name)
            if not entry:
                return {"ok": False, "message": "unknown process: %s" % name}
            entry["desired"] = True
            entry["restart_exhausted"] = False
            entry["restart_times"] = []
            entry["restart_times_monotonic"] = []
            entry["restart_after"] = 0.0
            entry["restart_after_monotonic"] = 0.0
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
            _terminate_process(process)
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
            restart_count = _safe_int(entry.get("restart_count"), 0, minimum=0, maximum=MAX_RESTART_HISTORY)
            restart_window = _safe_float(entry.get("restart_window"), 60.0, minimum=5.0, maximum=86400.0)
            restart_after = _safe_float(entry.get("restart_after"), 0.0, minimum=0.0, maximum=10**12)
            return {
                "available": True,
                "running": running,
                "desired": _strict_bool(entry.get("desired")),
                "pid": process.pid if running else 0,
                "command": list(entry.get("command") or []),
                "nice": _safe_int(entry.get("nice"), 0, minimum=-20, maximum=19),
                "last_error": process_error_text(entry.get("last_error"), default=""),
                "last_start": entry.get("last_start") or 0,
                "restart_count": restart_count,
                "restart_exhausted": _strict_bool(entry.get("restart_exhausted")),
                "restart_window": restart_window,
                "restart_after": restart_after,
                "recent_restart_times": _bounded_restart_history(
                    entry.get("restart_times"), STATUS_RESTART_HISTORY
                ),
            }

    def shutdown(self) -> None:
        with self._callback_gate:
            with self._lock:
                self._stopping = True
                self._monitor_generation += 1
                self._wake_event.set()
                names = list(self._entries)
        for name in names:
            self.stop(name)
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(1.0, self.poll_interval + 1.0))
        with self._lock:
            if self._thread is thread and (thread is None or not thread.is_alive()):
                self._thread = None

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
                secure_directory(os.path.dirname(log_path))
                log_handle = open(log_path, "ab", buffering=0)
                secure_file(log_path)
                stdout = log_handle
                stderr = log_handle
            preexec_fn = None
            if os.name != "nt":
                delta = _safe_int(entry.get("nice"), 0, minimum=-20, maximum=19)
                def _prepare_child(value=delta):
                    os.umask(0o077)
                    try:
                        if value:
                            os.nice(value)
                    except (OSError, ValueError):
                        pass
                preexec_fn = _prepare_child
            process = subprocess.Popen(
                command,
                cwd=entry.get("cwd") or None,
                env={**os.environ, **entry.get("env", {})},
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                preexec_fn=preexec_fn,
            )
            entry["process"] = process
            entry["last_error"] = ""
            entry["last_start"] = time.time()
            entry["restart_after"] = 0.0
            entry["restart_after_monotonic"] = 0.0
            return {"ok": True, "running": True, "pid": process.pid}
        except Exception as exc:
            message = process_error_text(exc)
            entry["last_error"] = message
            return {"ok": False, "running": False, "message": message}
        finally:
            if log_handle:
                log_handle.close()

    def _monitor(self, generation=None) -> None:
        while True:
            self._wake_event.wait(self.poll_interval)
            self._wake_event.clear()
            callback_events = []
            with self._lock:
                if self._stopping or generation != self._monitor_generation:
                    return
                log_paths = [entry.get("log_path") for entry in self._entries.values()]
            # A trim rewrites up to 1 MiB per service log. Do it outside the
            # supervisor lock: status(), start() and stop() all need it, so one
            # slow rewrite would otherwise stall every status poll.
            for log_path in log_paths:
                _trim_service_log(log_path)
            with self._lock:
                if self._stopping or generation != self._monitor_generation:
                    return
                for entry in self._entries.values():
                    process = entry.get("process")
                    if process and process.poll() is not None:
                        _reap_exited_process(process)
                        entry["process"] = None
                        if entry.get("desired") and entry.get("restart"):
                            now = time.time()
                            now_monotonic = time.monotonic()
                            window = _safe_float(
                                entry.get("restart_window"), 60.0, minimum=5.0, maximum=86400.0,
                            )
                            recent = [
                                stamp for stamp in _bounded_restart_history(
                                    entry.get("restart_times"), MAX_RESTART_HISTORY,
                                )
                                if now - stamp <= window
                            ]
                            recent_monotonic = [
                                stamp for stamp in _bounded_restart_history(
                                    entry.get("restart_times_monotonic"), MAX_RESTART_HISTORY,
                                )
                                if now_monotonic - stamp <= window
                            ]
                            max_restarts = _safe_int(
                                entry.get("max_restarts"), 5, minimum=1, maximum=100000,
                            )
                            if len(recent_monotonic) >= max_restarts:
                                entry["restart_times"] = recent
                                entry["restart_times_monotonic"] = recent_monotonic
                                entry["restart_exhausted"] = True
                                entry["desired"] = False
                                entry["last_error"] = "restart limit reached"
                                callback = entry.get("on_exhaust")
                                if callback:
                                    name = entry.get("name") or ""
                                    callback_events.append((
                                        callback,
                                        name,
                                        self.status(name),
                                        "restart limit reached; exhaustion callback failed: %s",
                                    ))
                            else:
                                recent.append(now)
                                recent_monotonic.append(now_monotonic)
                                entry["restart_times"] = recent
                                entry["restart_times_monotonic"] = recent_monotonic
                                entry["restart_count"] = min(
                                    MAX_RESTART_HISTORY,
                                    _safe_int(
                                        entry.get("restart_count"), 0,
                                        minimum=0, maximum=MAX_RESTART_HISTORY,
                                    ) + 1,
                                )
                                restart_backoff = _safe_float(
                                    entry.get("restart_backoff"), 2.0, minimum=0.01, maximum=30.0,
                                )
                                delay = min(30.0, restart_backoff ** min(len(recent), 5))
                                entry["restart_after"] = now + delay
                                entry["restart_after_monotonic"] = now_monotonic + delay
                    if (
                        entry.get("desired")
                        and entry.get("restart")
                        and not entry.get("process")
                        and time.monotonic() >= _safe_float(
                            entry.get("restart_after_monotonic"), 0.0, minimum=0.0, maximum=10**12,
                        )
                    ):
                        result = self._start_locked(entry)
                        callback = entry.get("on_restart")
                        if callback and result.get("ok"):
                            callback_events.append((
                                callback,
                                entry.get("name") or "",
                                dict(result),
                                "restart callback failed: %s",
                            ))
                        elif not result.get("ok"):
                            # A missing binary or a transient fork failure has
                            # no child process to trigger the exit branch above.
                            # Treat it as a failed restart nevertheless: merely
                            # backing off without recording the attempt lets an
                            # unavailable dependency retry forever and bypass
                            # the configured restart cap.
                            now = time.time()
                            now_monotonic = time.monotonic()
                            window = _safe_float(
                                entry.get("restart_window"), 60.0, minimum=5.0, maximum=86400.0,
                            )
                            recent = [
                                stamp for stamp in _bounded_restart_history(
                                    entry.get("restart_times"), MAX_RESTART_HISTORY,
                                )
                                if now - stamp <= window
                            ]
                            recent_monotonic = [
                                stamp for stamp in _bounded_restart_history(
                                    entry.get("restart_times_monotonic"), MAX_RESTART_HISTORY,
                                )
                                if now_monotonic - stamp <= window
                            ]
                            max_restarts = _safe_int(
                                entry.get("max_restarts"), 5, minimum=1, maximum=100000,
                            )
                            if len(recent_monotonic) >= max_restarts:
                                entry["restart_times"] = recent
                                entry["restart_times_monotonic"] = recent_monotonic
                                entry["restart_exhausted"] = True
                                entry["desired"] = False
                                entry["last_error"] = "restart limit reached"
                                callback = entry.get("on_exhaust")
                                if callback:
                                    name = entry.get("name") or ""
                                    callback_events.append((
                                        callback,
                                        name,
                                        self.status(name),
                                        "restart limit reached; exhaustion callback failed: %s",
                                    ))
                                continue
                            recent.append(now)
                            recent_monotonic.append(now_monotonic)
                            entry["restart_times"] = recent
                            entry["restart_times_monotonic"] = recent_monotonic
                            entry["restart_count"] = min(
                                MAX_RESTART_HISTORY,
                                _safe_int(
                                    entry.get("restart_count"), 0,
                                    minimum=0, maximum=MAX_RESTART_HISTORY,
                                ) + 1,
                            )
                            restart_backoff = _safe_float(
                                entry.get("restart_backoff"), 2.0, minimum=0.01, maximum=30.0,
                            )
                            delay = min(
                                30.0,
                                restart_backoff ** min(max(1, len(recent)), 5),
                            )
                            entry["restart_after"] = time.time() + delay
                            entry["restart_after_monotonic"] = time.monotonic() + delay
            self._dispatch_callback_events(generation, callback_events)

    def _dispatch_callback_events(self, generation, callback_events) -> None:
        """Run lifecycle callbacks only while their monitor generation is live."""
        for callback, name, payload, error_template in callback_events:
            with self._callback_gate:
                with self._lock:
                    # Callback collection happens under the supervisor lock,
                    # but execution is intentionally outside it. Shutdown or
                    # a newer monitor generation can therefore occur in that
                    # gap; stale lifecycle callbacks must not resurrect a
                    # service after the supervisor has been stopped.
                    if self._stopping or generation != self._monitor_generation:
                        continue
                try:
                    callback(name, payload)
                except Exception as exc:
                    with self._lock:
                        entry = self._entries.get(name)
                        if entry is not None:
                            entry["last_error"] = process_error_text(
                                error_template % process_error_text(exc)
                            )


def _command_exists(command: str) -> bool:
    if os.path.sep in command:
        return False
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory, command)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return True
    return False


def _safe_float(value, default: float, minimum: float, maximum: float) -> float:
    """Convert finite numeric configuration without invoking arbitrary objects."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not (minimum <= result <= maximum):
        return default
    return result


def _safe_int(value, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return min(maximum, max(minimum, value))


def _normalise_command(command) -> List[str]:
    if not isinstance(command, (list, tuple)):
        return []
    if not command or any(not isinstance(part, str) or not part or len(part) > 4096 for part in command):
        return []
    if len(command) > 128:
        return []
    return list(command)
