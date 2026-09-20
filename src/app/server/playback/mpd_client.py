from __future__ import annotations

import math
import os
import shutil
import socket
import subprocess
from process_output import check_output_bounded
import time
import urllib.parse
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 56660
MAX_MPD_LINE_BYTES = 256 * 1024
MAX_MPD_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_MPD_COMMAND_BYTES = 16 * 1024 * 1024


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


def _add_response_bytes(total: int, line: str) -> int:
    total += len(line.encode("utf-8", "replace")) + 1
    if total > MAX_MPD_RESPONSE_BYTES:
        raise MpdError("MPD response is too large")
    return total


class MpdConnection:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 2.0):
        self.host = host or DEFAULT_HOST
        self.port = int(port or DEFAULT_PORT)
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self.file = None

    def __enter__(self) -> "MpdConnection":
        try:
            self.sock = socket.create_connection((self.host, self.port), self.timeout)
            self.file = self.sock.makefile("rwb", buffering=0)
            greeting = self._readline()
            if not greeting.startswith("OK MPD"):
                raise MpdError("invalid MPD greeting: %s" % greeting)
            return self
        except Exception:
            # __exit__ is not invoked when __enter__ itself fails.
            self.__exit__(None, None, None)
            raise

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
        # MPD responses are line-oriented but the peer controls line length.
        # Bound the read before decoding so a malformed daemon cannot grow a
        # Python bytes object without limit.
        raw = self.file.readline(MAX_MPD_LINE_BYTES + 1)
        if not raw:
            raise MpdError("MPD connection closed")
        if len(raw) > MAX_MPD_LINE_BYTES or not raw.endswith(b"\n"):
            raise MpdError("MPD response line is too large or unterminated")
        return raw.decode("utf-8", "replace").rstrip("\n")

    def command(self, command: str, *args: Any) -> List[str]:
        if not self.file:
            raise MpdError("MPD connection is not open")
        self.file.write(self._command_line(command, args))
        lines: List[str] = []
        response_bytes = 0
        while True:
            response = self._readline()
            response_bytes = _add_response_bytes(response_bytes, response)
            if response == "OK":
                return lines
            if response.startswith("ACK "):
                raise MpdError(response)
            lines.append(response)

    @staticmethod
    def _command_line(command: str, args: Iterable[Any] = ()) -> bytes:
        return (" ".join([str(command)] + [quote_arg(arg) for arg in args]) + "\n").encode("utf-8")

    def command_list_ok(self, commands: Iterable[tuple[str, Iterable[Any]]]) -> List[List[str]]:
        """Run commands in one MPD round trip and retain each response block.

        Large logical queues used to issue one ``addid`` round trip per song.
        On a 2,000-song queue that delays DAC output switching noticeably even
        though MPD and fnAudio share localhost. ``command_list_ok`` is part of
        the standard MPD protocol and preserves every generated song id.
        """
        if not self.file:
            raise MpdError("MPD connection is not open")
        payload = bytearray(b"command_list_ok_begin\n")
        for command, args in commands:
            line = self._command_line(command, args)
            if len(payload) + len(line) + len(b"command_list_end\n") > MAX_MPD_COMMAND_BYTES:
                raise MpdError("MPD command list is too large")
            payload.extend(line)
        payload.extend(b"command_list_end\n")
        self.file.write(bytes(payload))
        results: List[List[str]] = []
        current: List[str] = []
        response_bytes = 0
        while True:
            response = self._readline()
            response_bytes = _add_response_bytes(response_bytes, response)
            if response == "OK":
                return results
            if response.startswith("ACK "):
                raise MpdError(response)
            if response == "list_OK":
                results.append(current)
                current = []
            else:
                current.append(response)

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
        response_bytes = 0
        while True:
            response = self._readline()
            response_bytes = _add_response_bytes(response_bytes, response)
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
    audio_format = str(payload.get("audio") or song.get("Format") or "")
    audio_parts = audio_format.split(":") if audio_format else []
    dsd_output = bool(audio_parts and audio_parts[0].lower().startswith("dsd"))
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
        "stream": {
            "format": audio_format,
            "sample_rate": 0 if dsd_output else safe_int(audio_parts[0]) if audio_parts else 0,
            "bit_depth": 0 if dsd_output else safe_int(audio_parts[1]) if len(audio_parts) > 1 else 0,
            "channels": safe_int(audio_parts[-1]) if len(audio_parts) > 1 else 0,
            "dsd": dsd_output,
            "bitperfect_candidate": dsd_output or bool(audio_format),
        },
    }


def mpd_update_and_wait(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 8.0) -> Dict[str, Any]:
    with MpdConnection(host, port) as mpd:
        mpd.command("update")
    deadline = time.monotonic() + max(0.2, safe_float(timeout))
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
                version = check_output_bounded([binary, "--version"], max_bytes=16 * 1024, timeout=2).decode("utf-8", "replace").splitlines()[0]
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


def mpd_replace_queue(
    entries: Iterable[Dict[str, Any]],
    current_track_id: str = "",
    start: float = 0.0,
    repeat: str = "off",
    shuffle: bool = False,
    play: bool = True,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> Dict[str, Any]:
    """Atomically replace MPD's execution queue and start the selected item.

    fnAudio remains the owner of the logical queue, while MPD receives a
    mirrored execution queue so it can keep ALSA open and perform gapless
    transitions. The returned song id mapping is retained by MpdService and
    used to reconcile autonomous MPD track changes back into PlaybackCore.
    """
    normalized = [
        {
            "track_id": str(entry.get("track_id") or ""),
            "uri": str(entry.get("uri") or ""),
        }
        for entry in entries
        if str(entry.get("track_id") or "") and str(entry.get("uri") or "")
    ]
    if not normalized:
        raise MpdError("MPD queue is empty")
    selected_track_id = str(current_track_id or normalized[0]["track_id"])
    song_ids: Dict[str, str] = {}
    with MpdConnection(host, port) as mpd:
        commands = [("clear", ())]
        commands.extend(("addid", (entry["uri"],)) for entry in normalized)
        commands.extend([
            ("random", (1 if shuffle else 0,)),
            ("repeat", (1 if str(repeat or "off").lower() in ("all", "one") else 0,)),
            ("single", (1 if str(repeat or "off").lower() == "one" else 0,)),
            ("consume", (0,)),
        ])
        responses = mpd.command_list_ok(commands)
        add_responses = responses[1:1 + len(normalized)]
        if len(add_responses) != len(normalized):
            raise MpdError("MPD did not acknowledge the complete queue")
        for entry, response in zip(normalized, add_responses):
            song_id = next(
                (line.split(": ", 1)[1] for line in response if line.startswith("Id: ")),
                "",
            )
            if not song_id:
                raise MpdError("MPD did not return a song id for %s" % entry["uri"])
            song_ids[entry["track_id"]] = song_id
        selected_song_id = song_ids.get(selected_track_id) or next(iter(song_ids.values()))
        if play:
            mpd.command("playid", selected_song_id)
        if play and safe_float(start) > 0:
            mpd.command("seekid", selected_song_id, max(0, safe_float(start)))
    return {
        "ok": True,
        "song_ids": song_ids,
        "current_track_id": selected_track_id,
        "current_song_id": song_ids.get(selected_track_id, ""),
        "count": len(song_ids),
        "start": safe_float(start),
        "playing": bool(play),
    }


def mpd_play_queue_item(
    song_id: str,
    start: float = 0.0,
    repeat: str = "off",
    shuffle: bool = False,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> Dict[str, Any]:
    if not str(song_id or ""):
        raise MpdError("MPD song id is required")
    with MpdConnection(host, port) as mpd:
        _set_playback_modes(mpd, repeat, shuffle)
        mpd.command("playid", song_id)
        if safe_float(start) > 0:
            mpd.command("seekid", song_id, max(0, safe_float(start)))
    return {"ok": True, "song_id": str(song_id), "start": safe_float(start)}


def mpd_set_playback_modes(
    repeat: str = "off",
    shuffle: bool = False,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> Dict[str, Any]:
    shuffle = shuffle if isinstance(shuffle, bool) else False
    with MpdConnection(host, port) as mpd:
        _set_playback_modes(mpd, repeat, shuffle)
    return {"ok": True, "repeat": repeat, "shuffle": bool(shuffle)}


def _set_playback_modes(mpd: MpdConnection, repeat: str, shuffle: bool) -> None:
    shuffle = shuffle if isinstance(shuffle, bool) else False
    repeat_mode = str(repeat or "off").lower()
    mpd.command("random", 1 if shuffle else 0)
    mpd.command("repeat", 1 if repeat_mode in ("all", "one") else 0)
    mpd.command("single", 1 if repeat_mode == "one" else 0)
    mpd.command("consume", 0)


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
    if isinstance(value, bool):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0
