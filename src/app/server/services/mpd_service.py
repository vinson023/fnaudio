from __future__ import annotations

import glob
import math
import os
import posixpath
import re
import shutil
import signal
import socket
import struct
import subprocess
import tempfile
from contextlib import contextmanager
from process_output import check_output_bounded
from summary_values import nonnegative_int
import threading
import time
import urllib.parse
import wave
from typing import Any, Dict, List, Mapping, Optional

from playback.mpd_client import (
    DEFAULT_HOST,
    MpdConnection,
    MpdError,
    DEFAULT_PORT,
    mpd_binary,
    mpd_control,
    mpd_idle,
    mpd_library_state,
    mpd_load_uri,
    mpd_play_queue_item,
    mpd_is_stale_song_id_error,
    mpd_probe,
    mpd_replace_queue,
    mpd_set_playback_modes,
    mpd_status,
    mpd_update_and_wait,
    mpd_update_hint,
)
from playback.mpd_errors import (
    classify_mpd_log_errors,
    empty_mpd_error_summary,
    legacy_decoder_error_summary,
)
from playback.alsa_output import alsa_devices, find_ffmpeg, probe_alsa_hw_params
from transcode import transcode_to_audio
from .process_supervisor import ProcessSupervisor

MAX_MPD_PROC_CMDLINE_BYTES = 4096
MAX_MPD_PID_FILE_BYTES = 256
# Reading the greeting is what proves the holder of the port really is an MPD, so
# it has to stay far cheaper than the reap it replaces: a stalled stranger must not
# put a full connect timeout in front of a transport command.
MAX_MPD_HANDSHAKE_TIMEOUT_SECONDS = 0.35
MAX_MPD_LOG_TAIL_BYTES = 8192
MAX_OUTPUT_CAPS_COLD_SHARE_SECONDS = 5.0
MAX_MPD_QUEUE_ENTRIES = 50000
# MPD indexes a whole library in the background.  Measured on the fnOS host, a
# pathless ``update`` of the 62,684-song library committed 580 seconds after it
# was issued (``stats.songs`` went 23,483 -> 63,550 in one step), so the worker
# is bounded well above that while still not holding a thread forever.
MPD_INDEX_CATCHUP_POLL_SECONDS = 2.0
MPD_INDEX_CATCHUP_TIMEOUT_SECONDS = 1800.0
from .audio_output_lease import AUDIO_OUTPUT_LEASE
from .dac_profiles import dac_quirk_profile
from file_permissions import atomic_write_text, secure_directory, secure_file


def _safe_index_count(value: Any) -> int:
    """Convert an MPD song counter without ever losing the index job.

    The catch-up worker clears its single-flight flag before it reports
    counters, and each counter conversion is guarded here, so a malformed or
    unexpectedly raising status value degrades to 0 instead of stranding every
    later catch-up behind a job that has already finished.
    """
    try:
        return nonnegative_int(value)
    except Exception:
        return 0


def _config_text(value: Any, fallback: str = "", maximum: int = 4096) -> str:
    """Accept only bounded text from the mutable runtime configuration."""
    if not isinstance(value, str) or len(value) > maximum:
        return fallback
    return value


def _config_int(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    """Accept only bounded integral settings from mutable runtime config."""
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and len(value) <= 16 and re.fullmatch(r"[+-]?\d+", value.strip()):
        try:
            number = int(value, 10)
        except (TypeError, ValueError, OverflowError):
            return fallback
    else:
        return fallback
    return min(maximum, max(minimum, number))


def device_presence_transition(state: Optional[Dict[str, Any]], present: bool, threshold: int = 2):
    """Debounce USB DAC enumeration changes.

    USB audio devices briefly disappear while the kernel tears down and
    recreates the ALSA card.  A single missing sample must therefore not stop
    MPD, and a single present sample must not immediately start recovery.
    Returns ``(new_state, event)`` where event is ``disconnected``,
    ``reconnected`` or ``""``.
    """
    current = dict(state or {})
    threshold = _config_int(threshold, 2, 1, 1000)
    missing = _config_int(current.get("missing_samples"), 0, 0, 10**6)
    present_samples = _config_int(current.get("present_samples"), 0, 0, 10**6)
    # Persisted state must use strict booleans.  Truthiness would interpret
    # a damaged value such as "false" as a real disconnect.
    was_missing = current.get("missing") if isinstance(current.get("missing"), bool) else False
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


# fnOS rewrites the whole ``@appcenter/<app>`` payload on every install-local
# upgrade (measured 2026-10-10: the MPD ``database`` was found truncated to
# 8,499 bytes minutes after a reinstall, which costs a ~30 minute cold scan).
# The per-app configuration directory is the only place with a longer lifetime,
# so from now on the MPD index lives beside the config file when there is one.
DURABLE_CONFIG_MARKER = "@appconf"
LEGACY_DATA_ROOT_PARTS = ("share", "mpd")
RECLAIMED_INDEX_FILES = ("database", "state", "sticker.sql")

# A loopback MPD client can be handed MPD's own listening port as its source
# port, and that self-connection keeps the port claimed after MPD dies
# (measured 2026-10-10: the app process held ``127.0.0.1:56660`` and MPD failed
# every start with ``Failed to bind ... Address already in use``).  ``bind(0)``
# picks numbers from the same kernel range, so a fallback port must live
# outside it or the next restart walks into the same trap.
EPHEMERAL_RANGE_PATH = "/proc/sys/net/ipv4/ip_local_port_range"
DEFAULT_EPHEMERAL_RANGE = (32768, 60999)
MAX_FALLBACK_PORT_CANDIDATES = 4096


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
        self.lib_dir = os.path.join(self.app_root, "target", "lib")
        # The data paths are resolved before the port is chosen: an MPD still
        # running from the old payload-rooted directory keeps the configured MPD
        # port, and without reaping it first this instance would drift onto a
        # random port and never reclaim the index it is about to need.
        self.data_root = self._data_root()
        self.music_root = os.path.join(self.data_root, "music")
        self.config_path = os.path.join(self.data_root, "mpd.conf")
        self.log_path = os.path.join(self.data_root, "mpd.log")
        self.reclaimed_index_from = ""
        self.port = self._select_port(_config_int(config.get("mpd_port"), DEFAULT_PORT, 1024, 65535))
        self.config["mpd_port"] = self.port
        self.binary = self._find_binary()
        self.supervisor = ProcessSupervisor()
        self._configured = False
        # Process setup, companion-worker admission and shutdown form one
        # lifecycle transaction. Command/queue locks intentionally stay
        # separate so ordinary transport requests are not serialized here.
        self._lifecycle_lock = threading.RLock()
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
        self._output_caps_builders = 0
        # Set while no capability scan is running, so a caller that arrives
        # during a cold scan can wait for the shared result.
        self._output_caps_idle = threading.Event()
        self._output_caps_idle.set()
        self._output_caps_ttl = 4.0
        self._binary_version_cache: Optional[str] = None
        self._status_listener = None
        self._last_transport = ""
        self._suppress_stop_until = 0.0
        self._queue_lock = threading.RLock()
        # MPD exposes one process-wide queue. Queue replacement, transport
        # controls and Renderer loads must therefore be serialized even when
        # they originate from different HTTP/idle/recovery threads.
        self._command_lock = threading.RLock()
        # fnAudio owns the logical library index, but MPD can only play songs
        # its *own* database resolved, and ``auto_update "no"`` means MPD never
        # refreshes itself.  This is the state of that convergence job.
        self._index_lock = threading.Lock()
        self._index_stop = threading.Event()
        self._index_thread: Optional[threading.Thread] = None
        self._index_state: Dict[str, Any] = {
            "running": False,
            "reason": "",
            "scope": "",
            "job": "",
            "indexed_before": 0,
            "indexed_after": 0,
            "started_at": 0.0,
            "finished_at": 0.0,
            "updated": False,
            "timed_out": False,
            "error": "",
            "requests": 0,
        }

        # `select_output` and `test_output` rewrite the ALSA selection around
        # MPD restarts. They must not interleave with each other, and a reader
        # must never persist the temporary value.
        self._output_selection_lock = threading.RLock()
        self._output_selection_transition = False
        self._recovery_active = threading.Event()
        self._service_stop = threading.Event()
        self._recovery_thread: Optional[threading.Thread] = None
        self._recovery_thread_lock = threading.Lock()
        # A service instance can stop and start again before an old recovery
        # thread has unwound. Bind recovery work to this monotonically growing
        # lifecycle marker so that thread cannot rebuild a newer MPD queue.
        self._recovery_generation = 0
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
        self._device_presence_threshold = _config_int(config.get("mpd_device_presence_samples"), 2, 1, 5)
        self._last_underrun_restart = float("-inf")
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
        # Guards the underrun/playback-error dictionaries that the device
        # monitor rewrites while every status poll copies them.
        self._error_state_lock = threading.Lock()
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

    @contextmanager
    def _exclusive_output_selection(self):
        """Own the ALSA selection while it is temporarily rewritten."""
        with self._output_selection_lock:
            outer = self._output_selection_transition
            self._output_selection_transition = True
            try:
                yield
            finally:
                self._output_selection_transition = outer

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
        # The only holder we are allowed to displace is an MPD from the previous
        # payload-rooted layout; anything else is a stranger and gets a fallback port.
        if self._reap_legacy_instances() and _tcp_port_available(self.host, requested):
            return requested
        return self._select_fallback_port()

    def _select_fallback_port(self) -> int:
        """Take a free port outside the kernel ephemeral range for MPD.

        Staying inside that range is what let our own client re-claim the
        number, so a moved MPD gets a port the kernel will never hand to an
        outbound connect.  If every candidate is somehow taken we keep the old
        random behaviour rather than refusing to start at all.
        """
        for port in _candidate_fallback_ports():
            if _tcp_port_available(self.host, port):
                return port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((self.host, 0))
            return int(sock.getsockname()[1])

    def _managed_mpd_pid(self) -> int:
        """Return the pid of the MPD this process supervises, else 0.

        ``ProcessSupervisor.status`` reports ``unknown process`` before the first
        ``register`` and ``pid`` 0 once the child exited; both must read here as
        "nothing of ours is running" rather than raise on a transport path.
        """
        try:
            status = self.supervisor.status("mpd")
            if not status.get("running"):
                return 0
            return int(status.get("pid") or 0)
        except Exception:
            return 0

    def _port_held_by_our_mpd(self) -> bool:
        """Tell our own running MPD apart from a stranger on the MPD port.

        A bind probe cannot: a healthy MPD always fails ``bind`` on the number it
        is listening on.  Measured on the owner's host on 2026-10-10, reading that
        failure as "stolen port" made every transport action SIGTERM our own child,
        wait for it and start a new MPD -- seven controls, seven different MPD pids,
        1,247 ms mean inside this method alone, and the "half a beat late" the owner
        felt on the USB DAC.  So both halves must agree: the supervisor owns a live
        child, and MPD protocol answers on the port.  A child of ours that is up but
        never bound, and any foreign holder while we have no child, keep the
        original displacement behaviour untouched.
        """
        if self._managed_mpd_pid() <= 0:
            return False
        return _mpd_handshake_ok(self.host, self.port)

    def _ensure_bindable_port(self) -> None:
        """Move MPD off a stolen port before ``mpd.conf`` is written.

        ``_select_port`` only runs once, when the service object is built, so a
        port taken afterwards used to keep ``start()`` failing for the whole
        lifetime of the app process.  Before anything is displaced the service asks
        whether the holder is its own running MPD -- holding the port is what a
        healthy MPD does, and this method runs on every transport command.  A
        legacy payload-rooted MPD is still the first thing we try to displace; only
        a stranger on the number makes MPD move, and the new port is written back
        into the config every client reads, so the two sides cannot drift.
        """
        if _tcp_port_available(self.host, self.port):
            return
        if self._port_held_by_our_mpd():
            # Normal steady state, not theft: the port belongs to the MPD this very
            # service supervises.  Displacing it here restarted MPD -- and repaid the
            # index, the output lease and the startup handshake -- on every
            # play/pause/next/previous/stop/seek/volume.
            return
        if self._reap_legacy_instances() and _tcp_port_available(self.host, self.port):
            return
        self.port = self._select_fallback_port()
        self.config["mpd_port"] = self.port

    def _data_root(self) -> str:
        configured = _config_text(self.config.get("mpd_data_dir"), maximum=1024).strip()
        if configured:
            return os.path.abspath(os.path.expanduser(configured))
        durable = self._durable_app_dir()
        if durable:
            return os.path.join(durable, "mpd")
        return os.path.join(self.app_root, *LEGACY_DATA_ROOT_PARTS)

    def _durable_app_dir(self) -> str:
        """Return the app-configuration directory that outlives a reinstall, or "".

        Production launches pass ``--config /usr/local/apps/<marker>/<app>/config.json``
        where the marker segment is ``DURABLE_CONFIG_MARKER`` (read from ``/proc`` on the
        test host); a relative ``config.json``
        used by development runs carries no such marker and keeps the payload
        directory, so no test or checkout layout changes shape.
        """
        if not self.app_config_path:
            return ""
        parent = os.path.dirname(os.path.abspath(self.app_config_path))
        segments = [part.lower() for part in parent.replace("\\", "/").split("/")]
        if DURABLE_CONFIG_MARKER not in segments:
            return ""
        return parent

    def _legacy_data_root(self) -> str:
        """The payload-rooted data directory, but only once the index moved away."""
        legacy = os.path.abspath(os.path.join(self.app_root, *LEGACY_DATA_ROOT_PARTS))
        if legacy == self.data_root:
            return ""
        return legacy

    def _legacy_data_roots(self) -> List[str]:
        """Return every pre-durable MPD directory this install may have left behind."""
        roots = []
        payload = self._legacy_data_root()
        if payload:
            roots.append(payload)
        durable = self._durable_app_dir()
        if not durable:
            return roots
        app_name = os.path.basename(os.path.dirname(durable))
        for pattern in (
            os.path.join(os.path.sep, "*", DURABLE_CONFIG_MARKER, app_name, "mpd"),
            os.path.join(os.path.sep, "*", "*", DURABLE_CONFIG_MARKER, app_name, "mpd"),
        ):
            for candidate in glob.glob(pattern):
                candidate = os.path.abspath(candidate)
                if candidate != os.path.abspath(self.data_root) and candidate not in roots:
                    roots.append(candidate)
        return roots

    def _reap_legacy_instances(self) -> bool:
        """Stop an MPD that is still holding resources from the legacy directory."""
        # No platform guard here: ``_scan_matching_pids`` is already a no-op without
        # /proc, and the pid file only exists where the legacy layout ever ran.
        legacy_roots = self._legacy_data_roots()
        if not legacy_roots:
            return False
        owned = self._managed_mpd_pid()
        targets = set(self._scan_matching_pids())
        for legacy in legacy_roots:
            pid_file = os.path.join(legacy, "mpd.pid")
            if os.path.isfile(pid_file):
                try:
                    with open(pid_file, "r", encoding="utf-8", errors="ignore") as fh:
                        pid_text = fh.read(MAX_MPD_PID_FILE_BYTES + 1)[:MAX_MPD_PID_FILE_BYTES]
                        pid = int(pid_text.strip().splitlines()[0])
                    if pid > 1 and self._pid_matches_mpd(pid):
                        targets.add(pid)
                except Exception:
                    pass
        # Depth defence: ``_pid_matches_mpd`` recognises the command line we
        # launched ourselves, so the child this process supervises must never be a
        # reap target, whichever caller reaches this method.
        targets.discard(owned)
        if not targets:
            return False
        for pid in sorted(targets):
            self._terminate_pid(pid)
        return True

    def _reclaim_legacy_index(self) -> str:
        """Copy the MPD index into the durable directory before an upgrade deletes it.

        A stale index is cheap - MPD's own ``update`` repairs it incrementally. An
        empty index is not: every track MPD has not resolved yet is refused, and
        the user is told to wait for a scan that takes about half an hour.
        """
        target = os.path.join(self.data_root, "database")
        if os.path.exists(target):
            return ""
        legacy = next(
            (root for root in self._legacy_data_roots() if os.path.isfile(os.path.join(root, "database"))),
            "",
        )
        if not legacy:
            return ""
        source = os.path.join(legacy, "database")
        staged = target + ".reclaim"
        try:
            shutil.copyfile(source, staged)
            secure_file(staged)
            os.replace(staged, target)
        except Exception:
            try:
                os.remove(staged)
            except Exception:
                pass
            return ""
        for name in RECLAIMED_INDEX_FILES:
            if name == "database":
                continue
            side_source = os.path.join(legacy, name)
            side_target = os.path.join(self.data_root, name)
            if os.path.isfile(side_source) and not os.path.exists(side_target):
                try:
                    shutil.copyfile(side_source, side_target)
                except Exception:
                    pass
        return legacy

    def _library_paths(self) -> List[str]:
        paths = self.config.get("library_paths")
        if isinstance(paths, list):
            values = [_config_text(x, maximum=4096).strip() for x in paths]
            values = [value for value in values if value]
        else:
            values = []
        if not values and self.config.get("library_path"):
            values = [x.strip() for x in _config_text(self.config.get("library_path"), maximum=4096).replace(";", "\n").splitlines() if x.strip()]
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
        # MPD 0.23 resolves a file:// uri without percent-decoding it and
        # refuses anything outside music_directory, so the raw path is the
        # only form that can ever produce a useful answer here.
        return "file://" + full

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

    def index_status(self) -> Dict[str, Any]:
        """Return the last MPD index convergence job for the status endpoint."""
        with self._index_lock:
            return dict(self._index_state)

    def _stop_index_catchup(self) -> None:
        self._index_stop.set()
        thread = self._index_thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def request_index_catchup(self, reason: str = "", path: str = "") -> Dict[str, Any]:
        """Queue one bounded MPD database update and track it in the background.

        ``No such song`` for a song fnAudio just served from its own index means
        MPD's database is behind, and on a 60,000-file library only a full
        ``update`` converges it.  A refresh request cannot block on that scan,
        so it runs here and leaves counters behind for the status endpoint and
        the failure toast.  One job at a time: a second full scan queued behind
        the first only adds disk thrash while the DAC stays silent.
        """
        scope = str(path or "").strip()
        text_reason = str(reason or "")[:64]
        if not self.supervisor.status("mpd").get("running"):
            with self._index_lock:
                return {"accepted": False, "reason": "mpd-not-running", "state": dict(self._index_state)}
        with self._index_lock:
            # The state flag, not thread liveness, is the single-flight guard: a
            # finished Thread object stays referenced, and a request arriving
            # between "flag set" and "thread started" must still see the job as
            # taken, or one play failure would queue two full library scans.
            if self._index_state.get("running"):
                return {"accepted": False, "reason": "already-running", "state": dict(self._index_state)}
            self._index_state.update(
                {
                    "running": True,
                    "reason": text_reason,
                    "scope": scope or "all",
                    "job": "",
                    "indexed_before": 0,
                    "indexed_after": 0,
                    "started_at": time.time(),
                    "finished_at": 0.0,
                    "updated": False,
                    "timed_out": False,
                    "error": "",
                    "requests": min(nonnegative_int(self._index_state.get("requests")) + 1, 10 ** 9),
                }
            )
            snapshot = dict(self._index_state)
        self._index_stop.clear()
        try:
            thread = threading.Thread(
                target=self._index_loop,
                args=(text_reason, scope),
                name="fnaudio-mpd-index",
                daemon=True,
            )
            self._index_thread = thread
            thread.start()
        except Exception as exc:
            with self._index_lock:
                self._index_thread = None
                self._index_state.update(
                    {"running": False, "error": str(exc), "timed_out": True, "finished_at": time.time()}
                )
                snapshot = dict(self._index_state)
            return {"accepted": False, "reason": "thread-start-failed", "state": snapshot}
        return {"accepted": True, "reason": text_reason, "state": snapshot}

    def _maybe_converge_mpd_index(self, reason: str = "mpd-start") -> Dict[str, Any]:
        """Ask MPD for a full scan when its database came up empty.

        An empty database that is not being updated means MPD never indexed
        this music directory, so every ``addid`` would be refused.  A database
        that already has songs is left alone: re-scanning the whole library on
        each DAC switch would thrash the disk for no proven gain, and a real
        lag is detected where it hurts (a refused ``addid``).

        ``updating_db`` is MPD's own liveness flag, and it is not enough on its
        side of the race: measured on the fnOS host a queued job is absent from
        ``status`` until it starts, so this worker's own flag is checked first.
        """
        with self._index_lock:
            if self._index_state.get("running"):
                return {"accepted": False, "reason": "already-running", "state": dict(self._index_state)}
        state = mpd_library_state(self.host, self.port)
        if not state.get("available") or state.get("indexed") or state.get("updating"):
            return {"accepted": False, "reason": "index-not-empty", "state": state}
        return self.request_index_catchup(reason=reason)

    def _index_loop(self, reason: str, scope: str) -> None:
        """Track one MPD database update so its progress is observable."""
        def on_progress(state: Dict[str, Any]) -> None:
            with self._index_lock:
                self._index_state["indexed_after"] = nonnegative_int(state.get("indexed"))
                self._index_state["job"] = str(state.get("job") or "")

        try:
            result = mpd_update_and_wait(
                host=self.host,
                port=self.port,
                timeout=MPD_INDEX_CATCHUP_TIMEOUT_SECONDS,
                path=scope,
                poll=MPD_INDEX_CATCHUP_POLL_SECONDS,
                on_progress=on_progress,
            )
        except Exception as exc:
            result = {
                "ok": False,
                "updated": False,
                "timed_out": True,
                "scope": scope or "all",
                "job": "",
                "indexed_before": 0,
                "indexed_after": 0,
                "message": str(exc),
            }
        # The flag is what makes the next request wait for this one, so it is
        # released in its own locked write, before any counter is formatted:
        # building the report must not be able to strand every later catch-up
        # behind a job that is already gone.
        with self._index_lock:
            self._index_state.update({"running": False, "finished_at": time.time()})
        terminal = {
            "scope": str(result.get("scope") or scope or "all"),
            "job": str(result.get("job") or ""),
            "indexed_before": _safe_index_count(result.get("indexed_before")),
            "indexed_after": _safe_index_count(result.get("indexed_after")),
            "updated": bool(result.get("updated")),
            "timed_out": bool(result.get("timed_out")),
            "error": "" if result.get("ok") else str(result.get("message") or ""),
        }
        with self._index_lock:
            self._index_state.update(terminal)

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
        generated_track_ids = set()
        try:
            queue_iterator = iter(queue)
        except Exception:
            queue_iterator = iter(())
        for _ in range(MAX_MPD_QUEUE_ENTRIES):
            try:
                track = next(queue_iterator)
            except StopIteration:
                break
            except Exception:
                break
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
                generated_track_ids.add(track_id)
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
            hint = ""
            verify = ""
            for entry in entries:
                if entry["track_id"] in generated_track_ids:
                    hint = mpd_update_hint(entry["uri"])
                    verify = str(entry["uri"] or "")
                    break
            # The generated FLAC sits in a folder MPD may never have mounted, and
            # a folder-targeted ``update`` is a silent no-op for exactly those
            # folders, so the wait is settled by the uri it is about to ``addid``.
            mpd_update_and_wait(
                host=self.host, port=self.port, path=hint, verify_uri=verify
            )
        fingerprint = tuple((entry["track_id"], entry["uri"]) for entry in entries)
        self._wait_for_recovery_window()
        with self._command_lock, self._queue_lock:
            reusable = fingerprint == self._queue_fingerprint and bool(self._queue_song_ids)
            selected_song_id = self._queue_song_ids.get(str(current_track_id or "")) if reusable else ""
            if selected_song_id and play:
                try:
                    result = mpd_play_queue_item(
                        selected_song_id,
                        start=0.0 if current_cue_ape else start,
                        repeat=repeat,
                        shuffle=shuffle,
                        host=self.host,
                        port=self.port,
                    )
                except MpdError as exc:
                    if not mpd_is_stale_song_id_error(exc):
                        raise
                    # MPD no longer holds that playlist entry: its own
                    # ``update`` removes songs that left the database, and a
                    # restart clears the queue outright.  The logical queue is
                    # still the one fnAudio owns, so the ids are simply stale -
                    # forget them and fall through to a full replace.  Letting
                    # this reach MpdOutput instead made it look like the song
                    # was missing from MPD and end in a "wait for the index"
                    # refusal for a file MPD can play.
                    self._queue_fingerprint = ()
                    self._queue_song_ids = {}
                    self._queue_song_tracks = {}
                    self._queue_current_track_id = ""
                else:
                    self._queue_current_track_id = str(current_track_id or "")
                    self._last_position = _safe_float(start)
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
            self._last_position = _safe_float(start)
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
        self._wait_for_recovery_window()
        with self._command_lock:
            with self._queue_lock:
                self._queue_repeat = str(repeat or "off")
                self._queue_shuffle = bool(shuffle)
            return mpd_set_playback_modes(repeat, shuffle, host=self.host, port=self.port)

    def control(self, action: str, position: Optional[float] = None) -> Dict[str, Any]:
        self._wait_for_recovery_window()
        with self._command_lock:
            return mpd_control(action, position, host=self.host, port=self.port)

    def load_uri(self, uri: str, start: float = 0.0) -> Dict[str, Any]:
        self._wait_for_recovery_window()
        with self._command_lock:
            return mpd_load_uri(uri, host=self.host, port=self.port, start=start)

    def _wait_for_recovery_window(self, timeout: float = 10.0) -> bool:
        """Wait until restart recovery has rebuilt MPD's process-local queue."""
        deadline = time.monotonic() + _safe_float(timeout)
        while self._recovery_active.is_set() and time.monotonic() < deadline:
            time.sleep(0.025)
        return not self._recovery_active.is_set()

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
        """Negotiate source format while keeping DSD conversion strict.

        PCM is allowed to use MPD's bounded software resampler when the USB
        descriptor does not advertise the source rate. Refusing ordinary PCM
        files here made every incompatible track fail before MPD could play it,
        and the UI consequently showed a blocking alert on every attempt.
        DSD remains strict because an implicit DSD-to-PCM conversion would
        change the user's selected output mode.
        """
        selected = self._selected_alsa_output()
        if not selected or selected.get("alsa_id") == "default":
            if bool((item or {}).get("is_dsd")):
                return {"ok": False, "message": "未找到可验证的 USB DAC，已阻止 DSD 转 PCM"}
            return {"ok": True, "dsd": False}
        descriptor_caps = dict(selected.get("caps") or {})
        quirk = dac_quirk_profile(selected, self.config.get("dac_profiles") or [])
        source_rate = int(_safe_float((item or {}).get("sample_rate")))
        descriptor_rates = set(descriptor_caps.get("pcm_rates") or [])
        # Do not stop an active MPD instance merely to probe a PCM rate. The
        # USB descriptor is stable and sufficient to reject unsupported
        # sources such as 384 kHz while another track is playing.
        if not bool((item or {}).get("is_dsd")) and source_rate and descriptor_rates and source_rate not in descriptor_rates:
            return {
                "ok": True,
                "resample_required": True,
                "resample_to": min(descriptor_rates, key=lambda rate: (abs(rate - source_rate), rate)),
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
                "ok": True,
                "resample_required": True,
                "resample_to": min(pcm_rates, key=lambda rate: (abs(rate - source_rate), rate)),
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
        self.reclaimed_index_from = self._reclaim_legacy_index()
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
        keepalive_mode = _config_text(self.config.get("dac_keepalive_mode")).lower() or _config_text(quirk.get("keepalive_mode"), "off").lower()
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
                # Ordinary PCM may need software conversion when its source
                # rate is outside the DAC descriptor. DSD is still gated above
                # and is never silently converted through this option.
                '    auto_resample "yes"',
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
            "reclaimed_index_from": self.reclaimed_index_from,
            "music_directory": music_directory,
            "output_device": output_device,
            "mixer_type": mixer_type,
            "mixer": mixer,
            "dsd_mode": "dop" if dop == "yes" else "native",
            "dac_profile": quirk,
            "keepalive_mode": keepalive_mode,
            "mpd_nice": _config_int(self.config.get("mpd_nice"), 0, -5, 10),
            "config_changed": config_changed,
            "host": self.host,
            "port": self.port,
        }

    def start(self) -> Dict[str, Any]:
        with self._lifecycle_lock:
            return self._start_locked()

    def _mpd_is_warm(self, setup: Dict[str, Any]) -> bool:
        """Whether MPD is already in exactly the state ``start()`` would produce.

        Three things have to hold together, which is why this is not one check: the
        configuration we would write is already on disk unchanged, our own supervised
        child is alive and answers MPD protocol on its port, and the priority the
        supervisor holds matches the config.  A DAC switch, a settings change, a dead
        child, or a child that never bound, all fall through to the cold sequence,
        which is also what restarts MPD when the output changes.
        """
        if setup.get("config_changed"):
            return False
        if not self._port_held_by_our_mpd():
            return False
        running_status = self.supervisor.status("mpd")
        wanted = _config_int(self.config.get("mpd_nice"), 0, -5, 10)
        return _config_int(running_status.get("nice"), 0, -5, 10) == wanted

    def _start_locked(self) -> Dict[str, Any]:
        self._ensure_bindable_port()
        self._recovery_generation += 1
        self._recovery_active.clear()
        self._service_stop.clear()
        setup = self.ensure_config()
        if not setup.get("ok"):
            return setup
        lease = AUDIO_OUTPUT_LEASE.acquire("mpd", str((setup.get("output_device") or {}).get("stable_id") or ""))
        if not lease.get("ok"):
            return {**setup, "ok": False, "running": False, "message": lease.get("message")}
        if self._mpd_is_warm(setup):
            # The child we supervise already answers on the port, the configuration
            # it was started with is still what we would write, and its scheduling
            # priority matches.  That is precisely the state the rest of this method
            # exists to produce, so replaying it -- process registration, the ready
            # handshake with its ``mpd --version`` subprocess, the index convergence
            # and a full status probe -- only puts another ~380 ms in front of the
            # transport command the user just pressed.  The companion workers stay
            # admitted here, because a warm start is still the only place a listener
            # that died since the cold start gets restarted.
            try:
                self._start_idle_listener()
                self._start_device_monitor()
            except Exception:
                AUDIO_OUTPUT_LEASE.release("mpd")
                raise
            return {**setup, "ok": True, "running": True, "pid": self._managed_mpd_pid(), "warm_start": True}
        if not self.supervisor.status("mpd").get("running"):
            self._cleanup_stale_instances()
        try:
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
                on_exhaust=self._release_audio_output,
                nice=_config_int(self.config.get("mpd_nice"), 0, -5, 10),
            )
            running_status = self.supervisor.status("mpd")
            scheduling_changed = _config_int(running_status.get("nice"), 0, -5, 10) != _config_int(
                self.config.get("mpd_nice"), 0, -5, 10
            )
            if (setup.get("config_changed") or scheduling_changed) and running_status.get("running"):
                result = self.supervisor.restart("mpd")
            else:
                result = self.supervisor.start("mpd")
        except Exception:
            try:
                self.supervisor.stop("mpd")
            finally:
                AUDIO_OUTPUT_LEASE.release("mpd")
            raise
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
        try:
            self._start_idle_listener()
            self._start_device_monitor()
            startup_delay = _config_int(
                ((setup.get("dac_profile") or {}).get("startup_delay_ms")),
                0,
                0,
                60000,
            )
            if startup_delay > 0 and (setup.get("config_changed") or result.get("pid")):
                time.sleep(startup_delay / 1000.0)
            self._maybe_converge_mpd_index("mpd-start")
            self.refresh_status()
        except Exception:
            # MPD is already running at this point. Roll back the whole
            # runtime if a companion worker cannot be admitted, otherwise a
            # failed start leaves a live daemon and a held output lease.
            self.shutdown()
            raise
        return {**setup, **result, **ready}

    def stop(self) -> Dict[str, Any]:
        with self._lifecycle_lock:
            return self._stop_locked()

    def _stop_locked(self) -> Dict[str, Any]:
        self._recovery_generation += 1
        self._recovery_active.clear()
        # An explicit stop is a terminal state for the current runtime. The
        # DAC monitor must not interpret a later hotplug event as permission
        # to start MPD again.
        self._service_stop.set()
        self._device_monitor_stop.set()
        if self._device_monitor_thread and self._device_monitor_thread.is_alive():
            self._device_monitor_thread.join(timeout=1.0)
        self._idle_stop.set()
        if self._idle_thread and self._idle_thread.is_alive():
            self._idle_thread.join(timeout=1.0)
        self._stop_index_catchup()
        result = self.supervisor.stop("mpd")
        AUDIO_OUTPUT_LEASE.release("mpd")
        # A previous app crash may have orphaned an MPD process which is no
        # longer owned by this in-memory supervisor instance.
        self._cleanup_stale_instances()
        return result

    def restart(self) -> Dict[str, Any]:
        with self._lifecycle_lock:
            return self._restart_locked()

    def _restart_locked(self) -> Dict[str, Any]:
        self._recovery_generation += 1
        self._recovery_active.clear()
        self._service_stop.clear()
        setup = self.ensure_config()
        if not setup.get("ok"):
            return setup
        lease = AUDIO_OUTPUT_LEASE.acquire("mpd", str((setup.get("output_device") or {}).get("stable_id") or ""))
        if not lease.get("ok"):
            return {**setup, "ok": False, "running": False, "message": lease.get("message")}
        if not self.supervisor.status("mpd").get("running"):
            self._cleanup_stale_instances()
        try:
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
                on_exhaust=self._release_audio_output,
                nice=_config_int(self.config.get("mpd_nice"), 0, -5, 10),
            )
            result = self.supervisor.restart("mpd")
        except Exception:
            try:
                self.supervisor.stop("mpd")
            finally:
                AUDIO_OUTPUT_LEASE.release("mpd")
            raise
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
        try:
            self._start_idle_listener()
            self._maybe_converge_mpd_index("mpd-restart")
            self.refresh_status()
        except Exception:
            self.shutdown()
            raise
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
            "reclaimed_index_from": self.reclaimed_index_from,
            "supervisor": supervisor,
            "idle": self.idle_status(),
            "index_catchup": self.index_status(),
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
                "cached_monotonic": time.monotonic(),
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
                "cached_monotonic": time.monotonic(),
            }
        with self._status_lock:
            self._status_cache = probe
        self._record_status_latency((time.perf_counter() - started_at) * 1000.0)
        return self._project_cached_probe(probe)

    def _record_status_latency(self, elapsed_ms: float) -> None:
        with self._fault_lock:
            samples = _safe_counter(self._fault_state.get("status_samples")) + 1
            previous = _safe_float(self._fault_state.get("status_latency_ms"))
            elapsed_ms = _safe_float(elapsed_ms)
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
            failures = _safe_counter(self._fault_state.get("consecutive_failures"))
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
            self._fault_state["recovery_count"] = _safe_counter(self._fault_state.get("recovery_count")) + 1
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
        if not cached or self._probe_age_seconds(cached) > 2.0:
            return self.refresh_status()
        return self._project_cached_probe(cached)

    @staticmethod
    def _probe_age_seconds(probe: Mapping[str, Any]) -> float:
        cached_monotonic = _safe_float(probe.get("cached_monotonic"))
        if cached_monotonic > 0.0:
            return max(0.0, time.monotonic() - cached_monotonic)
        # Compatibility for probes assembled by older callers that only carry
        # the diagnostic wall-clock timestamp.
        cached_at = _safe_float(probe.get("cached_at"))
        return max(0.0, time.time() - cached_at) if cached_at > 0.0 else float("inf")

    def _project_cached_probe(self, probe: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(probe)
        status = dict(result.get("status") or {})
        position = dict(status.get("position") or {})
        transport = dict(status.get("transport") or {})
        if transport.get("state") == "PLAYING":
            cached_monotonic = _safe_float(result.get("cached_monotonic"))
            if cached_monotonic > 0.0:
                elapsed = max(0.0, time.monotonic() - cached_monotonic)
            else:
                cached_at = _safe_float(result.get("cached_at")) or time.time()
                elapsed = max(0.0, time.time() - cached_at)
            base = _safe_float(position.get("rel_seconds"))
            duration = _safe_float(position.get("duration_seconds"))
            position["rel_seconds"] = min(duration, base + elapsed) if duration > 0 else base + elapsed
            status["position"] = position
        result["status"] = status
        self._update_recovery_checkpoint(result)
        return result

    def _update_recovery_checkpoint(self, probe: Mapping[str, Any], backend_track_id: str = "") -> None:
        """Keep a live song/position checkpoint for an unexpected MPD restart.

        MPD idle events do not fire as playback time advances. Status polling
        must therefore refresh the checkpoint too. Once recovery starts, the
        newly spawned MPD may briefly report position zero before fnAudio has
        rebuilt its queue; that transient state must not erase the checkpoint.
        """
        transport = normalized_transport(probe)
        if transport not in ("PLAYING", "PAUSED"):
            return
        with self._fault_lock:
            if str(self._fault_state.get("state") or "").upper() == "RECOVERING":
                return
        status = dict((probe or {}).get("status") or {})
        position = dict(status.get("position") or {})
        resolved_track_id = str(backend_track_id or self.track_id_for_status(dict(probe or {})) or "")
        with self._queue_lock:
            if resolved_track_id:
                self._queue_current_track_id = resolved_track_id
            self._last_position = max(0.0, _safe_float(position.get("rel_seconds")))

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
        now = time.monotonic()
        wait_for_builder = False
        owns_build = False
        with self._output_caps_lock:
            cached = dict(self._output_caps_cache)
            age = now - self._output_caps_cache_at if self._output_caps_cache_at else float("inf")
            building = self._output_caps_builders > 0
            if cached and not force:
                if age > self._output_caps_ttl and not building:
                    self._begin_output_caps_build_locked()
                    try:
                        threading.Thread(
                            target=self._refresh_output_capabilities,
                            name="fnaudio-alsa-caps",
                            daemon=True,
                        ).start()
                    except Exception:
                        # A temporary thread-admission failure must not leave
                        # the refresh latch set forever; otherwise every
                        # later status poll serves stale capabilities forever.
                        self._end_output_caps_build_locked()
                return cached
            if building and not force:
                wait_for_builder = True
            else:
                self._begin_output_caps_build_locked()
                owns_build = True
        if wait_for_builder:
            # The cache is cold and a scan is already running, so share that
            # result instead of stacking a second scan behind it. A cold build
            # spawns one `amixer` process per card and probes hw_params, which
            # every concurrent first-screen status poll used to pay for alone.
            self._output_caps_idle.wait(timeout=MAX_OUTPUT_CAPS_COLD_SHARE_SECONDS)
            with self._output_caps_lock:
                result = dict(self._output_caps_cache)
                if not result:
                    # The in-flight scan is wedged or found nothing usable. An
                    # empty descriptor would make mpd_output report "no sound
                    # card" and drop native DSD, so build it here instead.
                    self._begin_output_caps_build_locked()
                    owns_build = True
            if result:
                return result
        try:
            return self._publish_output_capabilities(self._build_output_capabilities())
        finally:
            if owns_build:
                with self._output_caps_lock:
                    self._end_output_caps_build_locked()

    def _begin_output_caps_build_locked(self) -> None:
        self._output_caps_builders += 1
        self._output_caps_idle.clear()

    def _end_output_caps_build_locked(self) -> None:
        self._output_caps_builders = max(0, self._output_caps_builders - 1)
        if self._output_caps_builders == 0:
            self._output_caps_idle.set()

    def _publish_output_capabilities(self, result: Dict[str, Any]) -> Dict[str, Any]:
        with self._output_caps_lock:
            self._output_caps_cache = dict(result)
            self._output_caps_cache_at = time.monotonic()
        return result

    def _refresh_output_capabilities(self) -> None:
        try:
            self._publish_output_capabilities(self._build_output_capabilities())
        finally:
            with self._output_caps_lock:
                self._end_output_caps_build_locked()

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
        max_bits = int(_safe_float(selected_hw.get("pcm_max_bits") or selected_caps.get("pcm_max_bits")))
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
            "keepalive_mode": _config_text(self.config.get("dac_keepalive_mode"), "off"),
            "keepalive_active": False,
            "mpd_nice": _config_int(self.config.get("mpd_nice"), 0, -5, 10),
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
        # The device monitor rewrites both dictionaries from its own thread.
        # Copying them unlocked can hand the status endpoint a torn snapshot
        # (a fresh count paired with the previous category breakdown).
        with self._error_state_lock:
            result["underrun"] = dict(self._underrun_state)
            result["playback_errors"] = dict(self._playback_error_state)
        result["fault"] = self.fault_status()
        return result

    def _start_idle_listener(self) -> None:
        old_thread = self._idle_thread
        if old_thread and old_thread.is_alive():
            if not self._idle_stop.is_set():
                return
            old_thread.join(timeout=1.0)
            if old_thread.is_alive():
                raise RuntimeError("MPD idle listener is still stopping")
            if self._idle_thread is old_thread:
                self._idle_thread = None
        self._idle_stop.clear()
        try:
            thread = threading.Thread(target=self._idle_loop, name="fnaudio-mpd-idle", daemon=True)
            self._idle_thread = thread
            thread.start()
        except Exception:
            if "thread" in locals() and self._idle_thread is thread:
                self._idle_thread = None
            self._idle_stop.set()
            raise

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
                self._update_recovery_checkpoint(refreshed, backend_track_id)
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
        if self._service_stop.is_set():
            return
        self.suppress_stop_transition(15.0)
        self._mark_recovering()
        self._recovery_active.set()
        generation = self._recovery_generation
        try:
            with self._recovery_thread_lock:
                if self._recovery_thread and self._recovery_thread.is_alive():
                    return
                thread = threading.Thread(
                    target=self._recover_playback_after_restart,
                    args=(generation,),
                    name="fnaudio-mpd-recovery",
                    daemon=True,
                )
                self._recovery_thread = thread
                # Registration and start must be one atomic transition. A
                # concurrent supervisor callback otherwise sees a non-live
                # gap and can overwrite this tracked recovery thread.
                thread.start()
        except Exception as exc:
            with self._recovery_thread_lock:
                if "thread" in locals() and self._recovery_thread is thread:
                    self._recovery_thread = None
                elif "thread" not in locals():
                    self._recovery_thread = None
            self._recovery_active.clear()
            self._observe_fault(error="MPD playback recovery could not start: %s" % exc)
            with self._idle_lock:
                self._idle_state["error"] = "MPD playback recovery could not start: %s" % exc
            raise

    def _recover_playback_after_restart(self, generation: Optional[int] = None) -> None:
        if generation is None:
            generation = self._recovery_generation
        if generation != self._recovery_generation:
            return
        if not self._recovery_lock.acquire(False):
            return
        self._recovery_active.set()
        try:
            if generation != self._recovery_generation or self._service_stop.is_set():
                return
            with self._command_lock:
                if generation != self._recovery_generation or self._service_stop.is_set():
                    return
                ready = self._wait_ready(8.0)
                if generation != self._recovery_generation or self._service_stop.is_set():
                    return
                if not ready.get("running"):
                    self._observe_fault(error=ready.get("message") or "MPD recovery timed out")
                    return
                with self._queue_lock:
                    entries = list(self._queue_entries)
                    current_track_id = self._queue_current_track_id
                    position = self._last_position
                    repeat = self._queue_repeat
                    shuffle = self._queue_shuffle
                if generation != self._recovery_generation or self._service_stop.is_set():
                    return
                if not entries or not current_track_id:
                    self._mark_recovered("STOPPED")
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
            if generation != self._recovery_generation or self._service_stop.is_set():
                return
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
            with self._recovery_thread_lock:
                owns_tracked_thread = self._recovery_thread is threading.current_thread()
                if owns_tracked_thread:
                    self._recovery_thread = None
                if generation == self._recovery_generation and (
                    owns_tracked_thread or self._recovery_thread is None
                ):
                    self._recovery_active.clear()

    def _wait_ready(self, timeout: float = 5.0) -> Dict[str, Any]:
        deadline = time.monotonic() + max(0.2, _safe_float(timeout))
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
        with self._lifecycle_lock:
            self._shutdown_locked()

    def _shutdown_locked(self) -> None:
        self._service_stop.set()
        with self._recovery_thread_lock:
            recovery_thread = self._recovery_thread
        self._device_monitor_stop.set()
        if self._device_monitor_thread and self._device_monitor_thread.is_alive():
            self._device_monitor_thread.join(timeout=1.0)
        self._idle_stop.set()
        if self._idle_thread and self._idle_thread.is_alive():
            self._idle_thread.join(timeout=1.0)
        self._stop_index_catchup()
        if recovery_thread and recovery_thread.is_alive() and recovery_thread is not threading.current_thread():
            recovery_thread.join(timeout=1.0)
        self.supervisor.shutdown()
        AUDIO_OUTPUT_LEASE.release("mpd")
        self._cleanup_stale_instances()

    def _release_audio_output(self, _name: str = "", _status: Dict[str, Any] | None = None) -> None:
        AUDIO_OUTPUT_LEASE.release("mpd")

    def _start_device_monitor(self) -> None:
        old_thread = self._device_monitor_thread
        if old_thread and old_thread.is_alive():
            if not self._device_monitor_stop.is_set():
                return
            old_thread.join(timeout=1.0)
            if old_thread.is_alive():
                raise RuntimeError("MPD device monitor is still stopping")
            if self._device_monitor_thread is old_thread:
                self._device_monitor_thread = None
        self._device_monitor_stop.clear()
        try:
            thread = threading.Thread(
                target=self._device_monitor_loop,
                name="fnaudio-usb-dac-monitor",
                daemon=True,
            )
            self._device_monitor_thread = thread
            thread.start()
        except Exception:
            if "thread" in locals() and self._device_monitor_thread is thread:
                self._device_monitor_thread = None
            self._device_monitor_stop.set()
            raise

    def _device_monitor_loop(self) -> None:
        while not self._device_monitor_stop.wait(2.0):
            if self._service_stop.is_set():
                return
            # One failed tick must not retire the monitor: it is the only thread
            # that notices an unplugged USB DAC and the only reader of MPD's log
            # for output/decoder errors. Work is retried on the next tick and the
            # failure stays observable through fault_status().
            try:
                stable_id = _config_text(self.config.get("mpd_output_stable_id"))
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
                        # The stop flag and the restart decision must be checked
                        # under the same lifecycle lock. Otherwise stop() can set
                        # the flag after this check but before start() acquires
                        # the lock; start() would then clear the flag and revive
                        # MPD after an explicit user stop.
                        with self._lifecycle_lock:
                            if self._service_stop.is_set():
                                return
                            self._selected_device_missing = False
                            self.config["mpd_output_alsa_id"] = selected.get("alsa_id") or ""
                            self._configured = False
                            started = self._start_locked()
                        if started.get("running"):
                            self._schedule_playback_recovery("mpd", started)
                self._watch_for_playback_errors()
            except Exception as exc:
                self._observe_fault(error=str(exc))

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
                handle.seek(max(self._last_log_size, size - MAX_MPD_LOG_TAIL_BYTES))
                chunk = handle.read(MAX_MPD_LOG_TAIL_BYTES + 1)[:MAX_MPD_LOG_TAIL_BYTES].decode("utf-8", "ignore").lower()
            self._last_log_size = size
        except OSError:
            return
        summary = classify_mpd_log_errors(chunk)
        if not summary.get("count"):
            return
        latest = (summary.get("items") or [{}])[-1]
        with self._error_state_lock:
            counts = dict(self._playback_error_state.get("by_category") or {})
            for category, count in (summary.get("by_category") or {}).items():
                counts[category] = _safe_counter(counts.get(category)) + _safe_counter(count)
            self._playback_error_state.update(
                {
                    "count": _safe_counter(self._playback_error_state.get("count"))
                    + _safe_counter(summary.get("occurrences")),
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
        underruns = _safe_counter((summary.get("by_category") or {}).get("buffer_underrun"))
        if underruns:
            with self._error_state_lock:
                self._underrun_state.update(
                    {
                        "count": _safe_counter(self._underrun_state.get("count")) + underruns,
                        "last_detected": time.time(),
                        "last_message": marker,
                    }
                )
        self._observe_fault(error=marker)
        if category in ("output_device_missing", "output_format_unsupported"):
            return
        if now - self._last_underrun_restart < 30.0:
            with self._error_state_lock:
                self._underrun_state["restart_suppressed"] = _safe_counter(
                    self._underrun_state.get("restart_suppressed")
                ) + 1
            return
        self._last_underrun_restart = now
        result = self.restart()
        if result.get("running"):
            with self._error_state_lock:
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
            value = check_output_bounded([self.binary, "--version"], max_bytes=16 * 1024, timeout=3, env=env).decode("utf-8", "replace").splitlines()[0]
        except Exception:
            value = ""
        self._binary_version_cache = value
        return value

    def _cleanup_stale_instances(self) -> None:
        if os.name == "nt":
            return
        stale_pids = set()
        for root in [self.data_root, *self._legacy_data_roots()]:
            pid_file = os.path.join(root, "mpd.pid")
            if os.path.isfile(pid_file):
                try:
                    with open(pid_file, "r", encoding="utf-8", errors="ignore") as fh:
                        pid_text = fh.read(MAX_MPD_PID_FILE_BYTES + 1)[:MAX_MPD_PID_FILE_BYTES]
                        pid = int(pid_text.strip().splitlines()[0])
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
                raw = fh.read(MAX_MPD_PROC_CMDLINE_BYTES + 1)
                raw = raw[:MAX_MPD_PROC_CMDLINE_BYTES].replace(b"\x00", b" ").decode("utf-8", "ignore")
        except Exception:
            return False
        if not raw:
            return False
        text = raw.lower()
        if "mpd" not in text:
            return False
        needles = [self.config_path.lower(), self.data_root.lower()]
        needles.extend(root.lower() for root in self._legacy_data_roots())
        return any(needle and needle in text for needle in needles)

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
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline:
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
        # This directory is app-owned state, not a user library root.  Never
        # follow a replacement symlink here: alias creation and stale-link
        # cleanup would otherwise operate on an arbitrary external directory.
        if os.path.lexists(self.music_root) and (
                os.path.islink(self.music_root) or not os.path.isdir(self.music_root)):
            raise OSError("MPD music alias directory is not a regular directory")
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
            if name not in wanted and re.fullmatch(r"\d{2}_[A-Za-z0-9_.-]+", name):
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
        if not isinstance(alsa_id, str) or len(alsa_id) > 512:
            return {"ok": False, "message": "输出设备标识无效", "alsa_id": ""}
        alsa_id = urllib.parse.unquote(alsa_id.strip())
        devices = alsa_devices()
        selected = self._find_output_device(alsa_id, devices)
        if not selected:
            return {"ok": False, "message": "没有找到这个 MPD 输出设备", "alsa_id": alsa_id}
        previous = _config_text(self.config.get("mpd_output_alsa_id"), maximum=512)
        previous_stable = _config_text(self.config.get("mpd_output_stable_id"), maximum=512)
        wanted_runtime = str(selected.get("alsa_id") or "")
        wanted_stable = str(selected.get("stable_id") or "")
        changed = previous != wanted_runtime or previous_stable != wanted_stable
        if not changed:
            return {"ok": True, "selected_output": self._public_output(selected), "changed": False}
        with self._exclusive_output_selection():
            self.invalidate_output_capabilities()
            was_running = bool(self.supervisor.status("mpd").get("running"))
            previous_dop = bool(self.config.get("mpd_dop"))
            if was_running:
                self.suppress_stop_transition(5.0)
                self.stop()
            # One update: a poll that resolves the selection must never see a
            # half-written pair, or it rewrites the runtime id from the old card.
            self.config.update({
                "mpd_output_alsa_id": wanted_runtime,
                "mpd_output_stable_id": wanted_stable,
            })
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
        if not isinstance(alsa_id, str) or len(alsa_id) > 512:
            return {"ok": False, "message": "输出设备标识无效", "alsa_id": "", "devices": []}
        alsa_id = alsa_id.strip()
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
        with self._exclusive_output_selection():
            previous_selection = {
                "mpd_output_alsa_id": _config_text(self.config.get("mpd_output_alsa_id"), maximum=512),
                "mpd_output_stable_id": _config_text(self.config.get("mpd_output_stable_id"), maximum=512),
                "mpd_dop": bool(self.config.get("mpd_dop")),
            }
            was_running = bool(self.supervisor.status("mpd").get("running"))
            # The bundled ffmpeg on fnOS may not include the ALSA muxer. Route the
            # test tone through MPD so the test exercises the same output path as
            # normal playback.
            fd = -1
            test_path = ""
            started_for_test = False
            try:
                previous = _config_text(self.config.get("mpd_output_alsa_id"), maximum=512)
                # One update: a poll that resolves the selection must never see a
                # half-written pair, or it rewrites the runtime id from the old card.
                self.config.update({
                    "mpd_output_alsa_id": alsa_id,
                    "mpd_output_stable_id": str(device.get("stable_id") or ""),
                })
                self._configured = False
                started = self.start()
                started_for_test = not was_running and bool(started.get("running"))
                if not started.get("running"):
                    return {"ok": False, "message": started.get("message") or "MPD 未能启动", **diagnostics}
                test_root = self._library_paths()[0] if self._library_paths() else self.data_root
                fd, test_path = tempfile.mkstemp(prefix=".fnaudio-output-test-", suffix=".wav", dir=test_root)
                os.close(fd)
                fd = -1
                _write_test_wav(test_path, duration)
                loaded = mpd_load_uri(self.uri_for_path(test_path), host=self.host, port=self.port)
                diagnostics["attempts"].append({"target": alsa_id, "method": "mpd-wav", "mpd": loaded})
                time.sleep(max(0.4, min(2.0, _safe_float(duration) or 1.2)))
                if previous != alsa_id and was_running:
                    # Restore the whole selection. Leaving the tested device's
                    # stable id behind would make the next read resolve straight
                    # back to the tested device and persist it again.
                    self.config.update(previous_selection)
                    self._configured = False
                    self.restart()
                return {"ok": True, "message": "测试音已通过 MPD 发送到 %s" % (device.get("name") or alsa_id), "used_target": alsa_id, **diagnostics}
            except Exception as exc:
                return {"ok": False, "message": "MPD 测试音播放失败：%s" % exc, **diagnostics}

            finally:
                if fd >= 0:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                if test_path:
                    try:
                        os.unlink(test_path)
                    except OSError:
                        pass
                selection_changed = any(self.config.get(key) != value for key, value in previous_selection.items())
                self.config.update(previous_selection)
                if selection_changed:
                    self._configured = False
                    # Whatever a concurrent poll wrote to disk while the test tone
                    # was playing, the caller's own selection must be what survives.
                    self._persist_app_config()
                if was_running and selection_changed:
                    self.restart()
                elif started_for_test:
                    # Output testing may start MPD temporarily. Restore the
                    # caller's original stopped state after the test finishes.
                    self.stop()

    def _selected_alsa_output(self) -> Dict[str, Any]:
        stable_wanted = _config_text(self.config.get("mpd_output_stable_id"), maximum=512).strip()
        wanted = _config_text(self.config.get("mpd_output_alsa_id"), maximum=512).strip()
        devices = alsa_devices()
        if stable_wanted:
            selected = self._find_output_device(stable_wanted, devices)
            if selected:
                runtime_id = selected.get("alsa_id") or ""
                if self.config.get("mpd_output_alsa_id") != runtime_id:
                    self.config["mpd_output_alsa_id"] = runtime_id
                    self._persist_output_selection()
                return self._public_output(selected, "stable-selected")
        if wanted:
            selected = self._find_output_device(wanted, devices)
            if selected:
                # One update: a poll that resolves the selection must never see a
                # half-written pair, or it rewrites the runtime id from the old card.
                self.config.update({
                    "mpd_output_alsa_id": selected.get("alsa_id") or "",
                    "mpd_output_stable_id": selected.get("stable_id") or "",
                })
                self._persist_output_selection()
                return self._public_output(selected, "legacy-migrated")
        selected = self._preferred_alsa_output()
        if selected and selected.get("alsa_id") != "default":
            # One update: a poll that resolves the selection must never see a
            # half-written pair, or it rewrites the runtime id from the old card.
            self.config.update({
                "mpd_output_alsa_id": selected.get("alsa_id") or "",
                "mpd_output_stable_id": selected.get("stable_id") or "",
            })
            self._persist_output_selection()
        return selected

    def _persist_output_selection(self) -> None:
        """Persist a resolved selection, but never while one is being changed.

        `select_output` and `test_output` rewrite the ALSA selection triple
        around MPD restarts, and every status poll resolves it through this
        class. Letting that read path persist a temporary value would keep a
        device that failed verification - or one that was only being tested -
        selected after the next service start.
        """
        if self._output_selection_transition:
            return
        self._persist_app_config()

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
            output = check_output_bounded(command, max_bytes=256 * 1024, timeout=2).decode("utf-8", "ignore")
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
        preferred = self._preferred_mixer_control(controls, _config_text(self.config.get("mpd_mixer_control"), maximum=128))
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
        requested = _config_text(self.config.get("mpd_mixer_type"), "none", 32).strip().lower()
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
        control = self._preferred_mixer_control(controls, _config_text(self.config.get("mpd_mixer_control"), maximum=128))
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
    max_bytes = 1024 * 1024
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read(max_bytes + 1)[:max_bytes]
    except OSError:
        return ""


def _tail_text(path: str, limit: int = 4000) -> str:
    # The normalisation has to happen outside the `except OSError` below: that
    # handler covers the file work, and `int(limit)` used to raise straight through
    # it for a non-numeric bound, turning a diagnostics read into a 500.
    limit = max(1, min(MAX_MPD_LOG_TAIL_BYTES, nonnegative_int(limit, 4000,
                                                                maximum=MAX_MPD_LOG_TAIL_BYTES)))
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - limit))
            return fh.read(limit + 1)[:limit].decode("utf-8", "replace")
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


def _mpd_handshake_ok(host: str, port: int) -> bool:
    """Return True when an MPD protocol server greets us on ``host:port``.

    Only the greeting is read.  ``mpd_probe`` would add an ``mpd --version``
    subprocess to the transport path this exists to shorten, and a bare port scan
    would confuse MPD with any other listener.  The connect goes through the same
    source-port guard every other client uses, so asking the port cannot be what
    steals it.
    """
    try:
        with MpdConnection(host, port, MAX_MPD_HANDSHAKE_TIMEOUT_SECONDS):
            return True
    except Exception:
        return False


def _ephemeral_port_range() -> tuple:
    """Read the kernel ephemeral range, or fall back to the Linux default.

    A missing or malformed ``/proc`` file (Windows development runs, a stripped
    container) must not decide the fallback port, so anything that fails
    validation returns the documented default instead of raising.
    """
    try:
        with open(EPHEMERAL_RANGE_PATH, "r", encoding="utf-8") as handle:
            parts = handle.read().split()
        low, high = int(parts[0]), int(parts[1])
    except (OSError, ValueError, IndexError):
        return DEFAULT_EPHEMERAL_RANGE
    if not 1024 <= low <= high <= 65535:
        return DEFAULT_EPHEMERAL_RANGE
    return low, high


def _candidate_fallback_ports() -> List[int]:
    """Ports outside the ephemeral range, the block above the range first.

    Each block is capped on its own so a crowded upper block can still reach
    the lower one.  Probing a candidate costs one socket bind, so the cap also
    bounds the worst case work on the recovery path.
    """
    low, high = _ephemeral_port_range()
    upper = list(range(high + 1, 65536))[:MAX_FALLBACK_PORT_CANDIDATES]
    lower = list(range(1024, low))[:MAX_FALLBACK_PORT_CANDIDATES]
    return upper + lower


def _safe_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 0.0
    if isinstance(value, str) and len(value) > 64:
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return max(0.0, number) if math.isfinite(number) else 0.0


def _safe_counter(value: Any, maximum: int = 10**12) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 0
    if isinstance(value, str) and len(value) > 64:
        return 0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    if not math.isfinite(number) or number < 0:
        return 0
    return min(int(number), maximum)


def _write_test_wav(path: str, duration: float = 1.2) -> None:
    sample_rate = 44100
    frames = int(sample_rate * max(0.3, min(5.0, _safe_float(duration) or 1.2)))
    with wave.open(path, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for index in range(frames):
            value = int(5000 * math.sin(2 * math.pi * 880 * index / sample_rate))
            wav.writeframes(struct.pack("<hh", value, value))
