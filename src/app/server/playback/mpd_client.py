from __future__ import annotations

import math
import os
import re
import shutil
import socket
import subprocess
from process_output import check_output_bounded
import time
import urllib.parse
from typing import Any, Callable, Dict, Iterable, List, Optional


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 56660
MAX_MPD_LINE_BYTES = 256 * 1024
MAX_MPD_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_MPD_COMMAND_BYTES = 16 * 1024 * 1024


class MpdError(RuntimeError):
    pass


class MpdQueueEntryError(MpdError):
    """An ``addid`` refusal that also names the queue entry MPD blamed.

    ``mpd_replace_queue`` mirrors the whole logical queue in one command list,
    so the un-indexed file can be any entry and MPD reports which one through
    the ACK command index.  Losing that index is what made every queue retry
    refresh the folder of the track the user pressed instead.
    """

    def __init__(self, message: str, uri: str = ""):
        super().__init__(message)
        self.uri = str(uri or "")


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
    """Return the ``file://`` form MPD itself answers for.

    MPD 0.23 resolves ``addid`` against its own database and does *not*
    percent-decode a ``file://`` uri first, so an encoded path is looked up
    verbatim and every fnOS library name (spaces, CJK) used to fail with
    ``No such song``.  The raw absolute path is what MPD accepts.
    """
    path = os.path.abspath(os.path.expanduser(path or ""))
    return "file://" + path


def mpd_update_hint(uri: str) -> str:
    """Return the single folder MPD has to rescan for one queue entry uri.

    ``addid`` only knows songs MPD already indexed, so a file that just
    appeared (a CUE/APE transcode, a fresh album) stays invisible until its
    folder is scanned.  Asking for that one folder keeps the queue usable
    while a tens-of-thousands-file library is still being indexed; a uri that
    is not a database-relative path has no narrower scope and returns "".
    """
    text = str(uri or "")
    if text.startswith("file://") or "/" not in text:
        return ""
    return text.rsplit("/", 1)[0]


def mpd_update_job_id(reply: Any) -> str:
    """Return the id of the update job an ``update`` reply queued, or "".

    MPD runs a database update as a background job and answers the command
    with ``updating_db: <id>``.  That id is the only handle a caller has to
    tell "this scan finished" apart from "this scan had not started yet";
    without it a wait on ``status`` is a guess.
    """
    try:
        lines = [str(line) for line in (reply or [])]
    except TypeError:
        return ""
    return str(parse_pairs(lines).get("updating_db") or "").strip()


def mpd_job_number(value: Any) -> int:
    """Return MPD's update job id as a number, or 0 when it is not one.

    Measured on the fnOS host with the MPD 0.23.5 shipped in this package: the
    id in ``updating_db`` is MPD's own monotonically increasing queue number.
    Comparing it as text makes "an older scan is still running" look like "a
    different scan is running", and that is what let a two-second poll report a
    ten-minute convergence as finished.
    """
    try:
        return max(0, int(str(value).strip()))
    except Exception:
        return 0


def mpd_uri_indexed(uri: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    """Ask MPD whether its own database can resolve one file uri.

    Playback only needs this one fact, and it is the same lookup ``addid``
    performs, so it is the completion evidence this module accepts.  The
    counters are not: measured on the fnOS host, ``stats.songs`` stayed at
    23,483 for the whole of a full-library update and jumped to 63,550 only when
    the scan committed 580 seconds later, so a counter read cannot tell "still
    building" from "built and this song is really gone".
    """
    text = str(uri or "")
    if "://" in text or "/" not in text:
        return False
    parent = mpd_update_hint(text)
    name = text.rsplit("/", 1)[-1]
    if not parent or not name:
        return False
    try:
        with MpdConnection(host, port) as mpd:
            lines = mpd.command("listall", parent)
    except Exception:
        return False
    for line in lines:
        value = str(line)
        if not value.startswith("file:"):
            continue
        listed = value.split(":", 1)[1].strip()
        if listed == text or listed.rsplit("/", 1)[-1] == name:
            return True
    return False


MPD_ACK_LINE = re.compile(r"ACK \[(\d+)@(\d+)\] \{([^}]*)\}")


def mpd_addid_failure_uri(entries, message: str) -> str:
    """Return the queue uri an MPD command-list ``ACK`` blames, or "".

    Measured against MPD 0.23.5 on the fnOS host: with ``clear`` sent first,
    an un-indexed entry at queue position 0 answers ``ACK [50@1] {addid}`` and
    the position-1 entry answers ``ACK [50@2] {addid}``; a standalone ``addid``
    answers ``ACK [50@0]``.  So command-list positions start at 1 and only an
    ``addid`` names a queue entry; anything else leaves the caller its usual
    fallback instead of a guessed folder.
    """
    match = MPD_ACK_LINE.search(str(message or ""))
    if not match or match.group(3) != "addid":
        return ""
    position = int(match.group(2)) - 1
    listed = list(entries or [])
    if position < 0 or position >= len(listed):
        return ""
    return str(listed[position].get("uri") or "")


def mpd_library_state(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """Report how far MPD's own song database has come.

    ``No such song`` means "MPD cannot resolve the uri", never "fnAudio has no
    such track", so the caller needs the index counters to tell a cold
    database apart from a missing or out-of-root file.
    """
    state: Dict[str, Any] = {"available": False, "indexed": 0, "updating": False, "job": ""}
    try:
        with MpdConnection(host, port) as mpd:
            status = parse_pairs(mpd.command("status"))
            stats = parse_pairs(mpd.command("stats"))
    except Exception:
        return state
    state["available"] = True
    state["indexed"] = safe_int(stats.get("songs"))
    state["job"] = str(status.get("updating_db") or "").strip()
    state["updating"] = bool(state["job"])
    return state


def mpd_library_state_message(state: Dict[str, Any], pending: bool = False) -> str:
    """Render ``mpd_library_state`` as one actionable sentence.

    ``pending`` means fnAudio has already asked MPD to index the whole library.
    Without it a database that is merely *behind* has to be reported as
    "index finished, so the file must be gone": ``auto_update "no"`` keeps MPD
    from re-scanning by itself, and measured on the fnOS host its own song
    count sat far below the fnAudio index, so an un-indexed song really was
    still on disk.  The middle sentence is what makes that retryable.
    """
    state = state if isinstance(state, dict) else {}
    if not state.get("available"):
        return "MPD 索引状态不可读取，请确认 MPD 已启动"
    indexed = safe_int(state.get("indexed"))
    if state.get("updating"):
        if pending:
            return (
                "MPD 索引仍在建立中，当前已收录 %d 首，fnAudio 已请求 MPD 收录整个曲库，"
                "本机实测全库收录约需十分钟，请等待收录完成后重试播放" % indexed
            )
        return "MPD 索引仍在建立中，当前已收录 %d 首，请等待扫描完成后再播放" % indexed
    if pending:
        return (
                "MPD 索引落后于 fnAudio 曲库，当前已收录 %d 首，fnAudio 已请求 MPD 收录整个曲库，"
                "本机实测全库收录约需十分钟，请等待收录完成后重试播放" % indexed
            )
    return "MPD 索引已完成，当前收录 %d 首，请确认文件仍存在且位于曲库根目录内" % indexed


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


def mpd_update_and_wait(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 8.0,
    path: str = "",
    poll: float = 0.2,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    verify_uri: str = "",
) -> Dict[str, Any]:
    """Ask MPD to index ``path`` (or everything) and wait for proof it worked.

    ``path`` is a music-directory-relative file or folder.  Passing it is the
    difference between one folder and a full re-scan of a 75,769-file library.

    Three facts measured against MPD 0.23.5 on the fnOS host shape this wait:

    * ``update <directory>`` is a *silent no-op* for a directory MPD has never
      mounted.  Issued against the album that produced ``ACK [50@1] {addid} No
      such song`` it replied ``updating_db: 5``, and over the next 90 seconds
      ``stats.songs`` stayed at 23,483 and ``listall`` kept answering ``No such
      directory``.  ``rescan`` behaved the same way.  Only a pathless ``update``
      mounts new directories, and on this library it took 580 seconds to commit.
    * ``updating_db`` is a monotonically increasing job number, so comparing it
      as text is wrong.  Queued job 7 while status still reports the older job 4
      means "our scan has not started yet"; the previous version read that as
      "our scan finished", which is what turned a ten-minute convergence into a
      two-second success and made the retry re-issue the same failing ``addid``.
    * ``stats.songs`` moves only when a scan commits, so it can confirm that a
      scan finished but can never say that a given song is available.

    ``verify_uri`` is therefore the evidence playback actually needs: when the
    caller names the song it wants, that song resolving in MPD's own database is
    the only thing that settles the wait.  Without it the job numbers decide, and
    a job that finished while the song still resolves to nothing is reported as
    ``absent`` so the caller escalates to a full scan instead of pretending.
    """
    scope = str(path or "").strip()
    target = str(verify_uri or "").strip()
    before = mpd_library_state(host, port)
    indexed_before = safe_int(before.get("indexed"))
    with MpdConnection(host, port) as mpd:
        reply = mpd.command("update", scope) if scope else mpd.command("update")
    job = mpd_update_job_id(reply)
    job_num = mpd_job_number(job)
    deadline = time.monotonic() + max(0.2, safe_float(timeout))
    step = max(0.05, safe_float(poll))
    ours_ran = False
    unconfirmed = 0
    settled = False
    resolved = False
    absent = False
    state: Dict[str, Any] = before
    if job_num:
        # Give MPD one poll interval before the first look.  A job that is
        # queued but not started is absent from ``status`` as well, and reading
        # "nothing is running" at that moment is exactly the false success this
        # wait used to report.
        time.sleep(step)
    while time.monotonic() < deadline:
        state = mpd_library_state(host, port)
        if on_progress is not None:
            try:
                on_progress(state)
            except Exception:
                pass
        if not state.get("available"):
            break
        if target and mpd_uri_indexed(target, host, port):
            resolved = True
            settled = True
            break
        running = mpd_job_number(state.get("job"))
        indexed_now = safe_int(state.get("indexed"))
        if running:
            if job_num and running > job_num:
                # MPD has moved past the job we queued, so ours is done.
                settled = True
                break
            if running == job_num or not job_num:
                ours_ran = True
            # An older job (running < job_num) still owns MPD and ours has not
            # started, which is a reason to keep waiting, not to report success.
            time.sleep(step)
            continue
        if indexed_now != indexed_before:
            settled = True
            break
        if ours_ran:
            settled = True
            break
        # No job is running and nothing moved: not evidence yet that our own
        # scan finished.  Two idle polls, then a job MPD did acknowledge counts
        # as merged into the scan that was already running.
        unconfirmed += 1
        if unconfirmed >= 2:
            settled = bool(job_num)
            break
        time.sleep(step)
    if settled and target and not resolved:
        # The refresh is over and the song still resolves to nothing, so more
        # waiting cannot help: only mounting the directory can, and that needs
        # the whole library.
        settled = False
        absent = True
    result: Dict[str, Any] = {
        "ok": True,
        "updated": settled,
        "scope": scope or "all",
        "timed_out": not settled and not absent,
        "job": job,
        "resolved": resolved,
        "absent": absent,
        "indexed_before": indexed_before,
        "indexed_after": safe_int(state.get("indexed")),
    }
    if absent:
        result["message"] = "MPD finished the folder but still cannot resolve this song"
    elif not settled:
        result["message"] = "MPD database update is still running"
    return result


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
        try:
            responses = mpd.command_list_ok(commands)
        except MpdError as exc:
            failing_uri = mpd_addid_failure_uri(normalized, str(exc))
            if not failing_uri:
                raise
            raise MpdQueueEntryError(str(exc), failing_uri) from exc
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
