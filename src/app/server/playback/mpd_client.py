from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
import urllib.parse
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 56660


class MpdError(RuntimeError):
    pass


def mpd_binary() -> str:
    return shutil.which("mpd") or ""


def mpc_binary() -> str:
    return shutil.which("mpc") or ""


def quote_arg(value: Any) -> str:
    text = str(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + text + '"'


def parse_pairs(lines: Iterable[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    repeated: Dict[str, List[str]] = {}
    for line in lines:
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        if key in result:
            repeated.setdefault(key, [str(result[key])]).append(value)
            result[key] = repeated[key]
        else:
            result[key] = value
    return result


def local_file_uri(path: str) -> str:
    path = os.path.abspath(os.path.expanduser(path or ""))
    return "file://" + urllib.parse.quote(path)


class MpdConnection:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 2.0):
        self.host = host or DEFAULT_HOST
        self.port = int(port or DEFAULT_PORT)
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self.file = None

    def __enter__(self) -> "MpdConnection":
        self.sock = socket.create_connection((self.host, self.port), self.timeout)
        self.file = self.sock.makefile("rwb", buffering=0)
        greeting = self._readline()
        if not greeting.startswith("OK MPD"):
            raise MpdError("invalid MPD greeting: %s" % greeting)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self.file:
                self.file.close()
        finally:
            if self.sock:
                self.sock.close()

    def _readline(self) -> str:
        if not self.file:
            raise MpdError("MPD connection is not open")
        raw = self.file.readline()
        if not raw:
            raise MpdError("MPD connection closed")
        return raw.decode("utf-8", "replace").rstrip("\n")

    def command(self, command: str, *args: Any) -> List[str]:
        if not self.file:
            raise MpdError("MPD connection is not open")
        line = " ".join([command] + [quote_arg(arg) for arg in args]) + "\n"
        self.file.write(line.encode("utf-8"))
        lines: List[str] = []
        while True:
            response = self._readline()
            if response == "OK":
                return lines
            if response.startswith("ACK "):
                raise MpdError(response)
            lines.append(response)

    def pairs(self, command: str, *args: Any) -> Dict[str, Any]:
        return parse_pairs(self.command(command, *args))

    def idle(self, *subsystems: str) -> List[str]:
        """Block until MPD reports a change in one of the requested subsystems."""
        if not self.file or not self.sock:
            raise MpdError("MPD connection is not open")
        selected = [str(value).strip() for value in subsystems if str(value).strip()]
        line = "idle%s\n" % ((" " + " ".join(selected)) if selected else "")
        self.file.write(line.encode("utf-8"))
        lines: List[str] = []
        while True:
            response = self._readline()
            if response == "OK":
                return lines
            if response.startswith("ACK "):
                raise MpdError(response)
            lines.append(response)


def mpd_request(command: str, *args: Any, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> List[str]:
    with MpdConnection(host, port) as mpd:
        return mpd.command(command, *args)


def mpd_pairs(command: str, *args: Any, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    with MpdConnection(host, port) as mpd:
        return mpd.pairs(command, *args)


def mpd_idle(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    subsystems: Iterable[str] = ("player", "mixer", "playlist", "database", "update"),
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Wait for an MPD idle event and return the affected subsystems."""
    connection = MpdConnection(host, port, timeout=timeout or 3600.0)
    with connection:
        changed = connection.idle(*subsystems)
    return {"available": True, "changed": changed}


def mpd_status(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    payload = mpd_pairs("status", host=host, port=port)
    song = {}
    try:
        song = mpd_pairs("currentsong", host=host, port=port)
    except Exception:
        song = {}
    elapsed = safe_float(payload.get("elapsed"))
    duration = safe_float(payload.get("duration") or song.get("duration"))
    return {
        "available": True,
        "state": str(payload.get("state") or "stop").upper(),
        "raw": payload,
        "song": song,
        "position": {
            "rel_seconds": elapsed,
            "duration_seconds": duration,
        },
        "transport": {
            "state": "PLAYING" if payload.get("state") == "play" else ("PAUSED" if payload.get("state") == "pause" else "STOPPED")
        },
    }


def mpd_update_and_wait(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 8.0) -> Dict[str, Any]:
    with MpdConnection(host, port) as mpd:
        mpd.command("update")
    deadline = time.monotonic() + max(0.2, float(timeout))
    while time.monotonic() < deadline:
        status = mpd_pairs("status", host=host, port=port)
        if not str(status.get("updating_db") or "").strip():
            return {"ok": True, "updated": True}
        time.sleep(0.2)
    return {"ok": True, "updated": False, "message": "MPD database update is still running"}


def mpd_probe(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    binary = mpd_binary()
    mpc = mpc_binary()
    try:
        version = ""
        if binary:
            try:
                version = subprocess.check_output([binary, "--version"], stderr=subprocess.STDOUT, timeout=2).decode("utf-8", "replace").splitlines()[0]
            except Exception:
                version = ""
        status = mpd_status(host, port)
        return {
            "available": True,
            "running": True,
            "host": host,
            "port": port,
            "binary": binary,
            "mpc": mpc,
            "version": version,
            "status": status,
            "message": "",
        }
    except Exception as exc:
        return {
            "available": bool(binary),
            "running": False,
            "host": host,
            "port": port,
            "binary": binary,
            "mpc": mpc,
            "version": "",
            "status": {},
            "message": str(exc) if binary else "MPD is not installed",
        }


def mpd_load_file(path: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, start: float = 0.0) -> Dict[str, Any]:
    uri = local_file_uri(path)
    return mpd_load_uri(uri, host=host, port=port, start=start)


def mpd_load_uri(uri: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, start: float = 0.0) -> Dict[str, Any]:
    with MpdConnection(host, port) as mpd:
        mpd.command("stop")
        mpd.command("clear")
        add_result = mpd.command("addid", uri)
        song_id = ""
        for line in add_result:
            if line.startswith("Id: "):
                song_id = line.split(": ", 1)[1]
                break
        if song_id:
            mpd.command("playid", song_id)
        else:
            mpd.command("play", 0)
        if start and safe_float(start) > 0:
            if song_id:
                mpd.command("seekid", song_id, max(0, safe_float(start)))
            else:
                mpd.command("seek", 0, max(0, safe_float(start)))
    return {"ok": True, "uri": uri, "song_id": song_id, "start": safe_float(start)}


def mpd_control(action: str, position: Optional[float] = None, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    action = str(action or "").lower()
    with MpdConnection(host, port) as mpd:
        if action in ("play", "resume"):
            mpd.command("play")
        elif action == "pause":
            mpd.command("pause", 1)
        elif action == "stop":
            mpd.command("stop")
        elif action == "next":
            mpd.command("next")
        elif action == "previous":
            mpd.command("previous")
        elif action == "seek":
            mpd.command("seekcur", max(0, safe_float(position)))
        elif action == "volume":
            mpd.command("setvol", max(0, min(100, int(safe_float(position)))))
        else:
            raise MpdError("unsupported MPD action: %s" % action)
    return {"ok": True, "action": action}


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
