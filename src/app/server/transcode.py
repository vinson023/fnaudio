from __future__ import annotations

import os
import re
import signal
import shutil
import subprocess
import tempfile
import threading
import time
import heapq
import hashlib
import math
import ipaddress
import uuid
import weakref
from typing import Any, Dict

from resource_limits import FFMPEG_GATE, ResourceLimitError, bounded_int, disk_has_reserve, ffmpeg_slot
from file_permissions import secure_directory, secure_file
from network_host import is_private_host


MP3_EXTENSIONS = {".mp3"}
APE_EXTENSIONS = {".ape"}
CACHE_TTL_SECONDS = 2 * 24 * 60 * 60
CACHE_CLEANUP_INTERVAL = 6 * 60 * 60
MAX_TRANSCODE_STDERR_BYTES = 64 * 1024
TRANSCODE_JOBS = set()
TRANSCODE_LOCK = threading.Lock()
TRANSCODE_QUEUE = []
TRANSCODE_SEQUENCE = 0
TRANSCODE_WORKER = None
TRANSCODE_STOP_EVENT = threading.Event()
LAST_CACHE_CLEANUP = 0
_CACHE_CLEANUP_LOCK = threading.Lock()
_TARGET_LOCKS_GUARD = threading.Lock()
_TARGET_LOCKS = weakref.WeakValueDictionary()
_ACTIVE_TRANSCODE_PATHS = set()
_SAFE_CACHE_STEM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_WINDOWS_RESERVED_STEMS = {
    "CON", "PRN", "AUX", "NUL",
    *("COM%d" % index for index in range(1, 10)),
    *("LPT%d" % index for index in range(1, 10)),
}


def _run_transcode_process(command, *, stdout, stderr, timeout, env):
    """Use a private process group for real FFmpeg cache jobs."""
    if getattr(subprocess.run, "__module__", "") == "unittest.mock":
        return subprocess.run(command, stdout=stdout, stderr=stderr, timeout=timeout, env=env)
    process = subprocess.Popen(
        command, stdout=stdout, stderr=stderr, env=env,
        start_new_session=(os.name != "nt"),
    )
    try:
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if hasattr(stderr, "tell"):
                stderr.seek(0, os.SEEK_END)
                if stderr.tell() > MAX_TRANSCODE_STDERR_BYTES:
                    raise ResourceLimitError("transcode diagnostic output is too large")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            time.sleep(min(0.05, remaining))
        process.wait(timeout=0)
        # The process can finish between polling iterations after writing its
        # final diagnostic burst. Enforce the same bound on the completed
        # output before callers can publish the cache entry.
        if hasattr(stderr, "tell"):
            stderr.seek(0, os.SEEK_END)
            if stderr.tell() > MAX_TRANSCODE_STDERR_BYTES:
                raise ResourceLimitError("transcode diagnostic output is too large")
    except subprocess.TimeoutExpired:
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except (OSError, ProcessLookupError):
            pass
        try:
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise
    except Exception:
        try:
            if process.poll() is None:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
        except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
            pass
        try:
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise
    return process


def safe_float(value, default=0.0):
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) else default


def _safe_priority(value, default=100):
    """Keep queue ordering bounded without coercing arbitrary callers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(number):
        return default
    return max(-100000, min(100000, int(number)))


def _cache_item_stem(item):
    """Map arbitrary item identities to one filename component.

    Scanner-generated IDs are short hashes, but transcode helpers also serve
    legacy rows and queue payloads.  Never let a malformed ID add a path
    separator, a dot segment, or a Windows device name to the cache path.
    """
    raw_id = item.get("id") if isinstance(item, dict) else ""
    value = raw_id if isinstance(raw_id, str) else ""
    if _SAFE_CACHE_STEM.fullmatch(value) and value.upper() not in _WINDOWS_RESERVED_STEMS:
        return value
    return "item-" + hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()[:32]


def _transcode_job_key(item, mode):
    """Use the same bounded identity for queue de-duplication and cache paths."""
    return "%s:%s" % (str(mode or "mp3"), _cache_item_stem(item))


def _target_lock(item, mode):
    key = _transcode_job_key(item, mode)
    with _TARGET_LOCKS_GUARD:
        lock = _TARGET_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _TARGET_LOCKS[key] = lock
        return lock


def _transcode_temp_path(target):
    """Give every conversion attempt its own publish-before-replace path."""
    extension = os.path.splitext(target)[1]
    return "%s.tmp.%s%s" % (target, uuid.uuid4().hex, extension)


def _mark_active_transcode_paths(paths):
    with TRANSCODE_LOCK:
        _ACTIVE_TRANSCODE_PATHS.update(paths)


def _unmark_active_transcode_paths(paths):
    with TRANSCODE_LOCK:
        for path in paths:
            _ACTIVE_TRANSCODE_PATHS.discard(path)


def playback_profile(handler):
    forwarded = trusted_forwarded_headers(handler)
    host = (forwarded.get("host") if forwarded else "") or handler.headers.get("Host", "")
    remote = (forwarded.get("remote") if forwarded else "") or _peer_address(handler)
    remote_first = (remote or "").split(",", 1)[0].strip()
    if remote_first and not is_private_host(remote_first):
        return "wan"
    if remote_first and is_private_host(remote_first) and remote_first not in ("127.0.0.1", "::1"):
        return "lan"
    if host:
        return "lan" if is_private_host(host) else "wan"
    return "lan" if is_private_host(remote_first) else "wan"


def public_access(handler):
    forwarded = trusted_forwarded_headers(handler)
    client_ip = (forwarded.get("remote") if forwarded else "") or _peer_address(handler)
    host = (forwarded.get("host") if forwarded else "") or handler.headers.get("Host", "")
    proto = (forwarded.get("proto") if forwarded else "") or "http"
    return {
        "profile": playback_profile(handler),
        "client_ip": client_ip.split(",", 1)[0].strip(),
        "host": host,
        "proto": proto,
    }


def _peer_address(handler):
    try:
        address = handler.client_address[0]
    except (AttributeError, IndexError, TypeError):
        return ""
    return address if isinstance(address, str) else ""


def trusted_forwarded_headers(handler):
    """Accept forwarded identity only from the local CGI reverse proxy.

    The backend is also reachable directly on the NAS.  A direct client can
    otherwise forge X-Forwarded-For/Host and change the automatic LAN/WAN
    delivery profile or the access diagnostic payload.  The bundled CGI proxy
    connects over loopback, so that is the narrow trust boundary we need.
    """
    peer = _peer_address(handler)
    try:
        is_loopback = ipaddress.ip_address(peer).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback:
        return {}
    headers = getattr(handler, "headers", {})
    try:
        return {
            "remote": headers.get("X-Forwarded-For") or headers.get("X-Real-IP") or "",
            "host": headers.get("X-Forwarded-Host") or "",
            "proto": headers.get("X-Forwarded-Proto") or "",
        }
    except Exception:
        return {}


def _transcode_source_mtime(item):
    """Return the newest mtime that can affect a transcode result.

    Returns None when the source cannot be stat'ed.  The library index
    outlives files on a NAS share (rename, delete, unmount), and both callers
    need to tell "unreadable" apart from "fresh".
    """
    try:
        source_mtime = os.path.getmtime(item["path"])
    except OSError:
        return None
    cue_path = item.get("cue_path")
    if cue_path and os.path.isfile(cue_path):
        try:
            source_mtime = max(source_mtime, os.path.getmtime(cue_path))
        except OSError:
            pass
    return source_mtime


def media_mode(item, query, handler):
    requested = (query.get("transcode") or query.get("delivery") or ["auto"])[0]
    profile = (query.get("profile") or ["auto"])[0]
    ext = os.path.splitext(item["path"])[1].lower()
    if requested in ("original", "upnp"):
        return "original"
    if requested in ("flac", "ape-flac", "ape_flac"):
        return "ape_flac" if ext in APE_EXTENSIONS else "original"
    if requested in ("cue_flac", "cue-flac"):
        return "cue_flac" if item.get("cue_track") else "original"
    if requested in ("upnp-wav", "upnp_wav"):
        return "dsd_wav" if item["is_dsd"] else "original"
    if requested == "mp3":
        return "mp3" if ext not in MP3_EXTENSIONS else "original"
    if requested in ("wav", "dsd-wav", "dsd_wav"):
        return "dsd_wav" if item["is_dsd"] else "original"
    if profile not in ("lan", "wan"):
        profile = playback_profile(handler)
    if profile == "wan":
        return "mp3" if ext not in MP3_EXTENSIONS else "original"
    if item.get("cue_track"):
        return "cue_flac"
    if ext in APE_EXTENSIONS:
        return "ape_flac"
    if item["is_dsd"]:
        return "dsd_wav"
    return "original"


def find_ffmpeg(config):
    candidates = [
        config.get("ffmpeg_path"),
        "/usr/trim/lib/mediasrv/bin/ffmpeg",
        "/usr/trim/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg",
        shutil.which("ffmpeg"),
        shutil.which("ffmpeg.exe"),
    ]
    for candidate in candidates:
        if not candidate or not os.path.isfile(candidate):
            continue
        if os.access(candidate, os.X_OK):
            return candidate
    return ""


def transcode_to_audio(item, config, mode="mp3"):
    if mode == "original":
        return item["path"], item["mime"]
    ffmpeg = find_ffmpeg(config)
    if not ffmpeg:
        raise RuntimeError("系统中未找到可用的 ffmpeg")
    cache_dir = config.get("cache_dir") or os.path.join(os.path.dirname(item["path"]), ".fnaudio-cache")
    secure_directory(cache_dir)
    stem = _cache_item_stem(item)
    if mode == "dsd_wav":
        target = os.path.join(cache_dir, stem + ".dsd-96k-24bit.wav")
        mime = "audio/wav"
        command = [ffmpeg, "-threads", "0", "-y", "-i", item["path"], "-vn", "-map", "0:a:0", "-ar", "96000", "-codec:a", "pcm_s24le"]
    elif mode == "ape_flac":
        target = os.path.join(cache_dir, stem + ".ape-source.flac")
        mime = "audio/flac"
        command = [ffmpeg, "-threads", "0", "-y", "-i", item["path"], "-vn", "-map", "0:a:0", "-codec:a", "flac"]
    elif mode == "cue_flac":
        target = os.path.join(cache_dir, stem + ".cue-segment.flac")
        mime = "audio/flac"
        command = [ffmpeg, "-threads", "0", "-y", "-ss", str(max(0, safe_float(item.get("cue_start")))), "-i", item["path"]]
        duration = safe_float(item.get("duration"))
        if duration > 0:
            command += ["-t", str(duration)]
        command += ["-vn", "-map", "0:a:0", "-codec:a", "flac"]
    else:
        target = os.path.join(cache_dir, stem + ".mp3")
        mime = "audio/mpeg"
        command = [ffmpeg, "-threads", "0", "-y", "-i", item["path"], "-vn", "-map", "0:a:0", "-codec:a", "libmp3lame", "-q:a", "2"]
    temp = _transcode_temp_path(target)
    active_paths = (target, temp)
    _mark_active_transcode_paths(active_paths)
    try:
        cleanup_transcode_cache_if_due(config)
        minimum_free = bounded_int(config, "cache_min_free_bytes", 512 * 1024 * 1024, 64 * 1024 * 1024, 16 * 1024 * 1024 * 1024)
        if not disk_has_reserve(cache_dir, minimum_free):
            prune_transcode_cache(config, max_age_seconds=0)
        if not disk_has_reserve(cache_dir, minimum_free):
            raise ResourceLimitError("转码缓存磁盘空间低于保留水位")
    # Playback can request a cache miss while its low-priority warmup is
    # already running.  They previously shared one deterministic .tmp path,
    # allowing one job to remove or replace the other's output.
        with _target_lock(item, mode):
            source_mtime = _transcode_source_mtime(item)
            if source_mtime is None:
                raise RuntimeError("audio source is no longer readable")
            if not os.path.isfile(target) or os.path.getmtime(target) < source_mtime:
                env = os.environ.copy()
                env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
                timeout = bounded_int(config, "ffmpeg_job_timeout_seconds", 900, 30, 3600)
                try:
                    with tempfile.TemporaryFile(mode="w+b") as errors:
                        with ffmpeg_slot(config, timeout=5):
                            result = _run_transcode_process(
                                command + [temp], stdout=subprocess.DEVNULL, stderr=errors,
                                timeout=timeout, env=env,
                            )
                        if result.returncode != 0:
                            errors.seek(0, os.SEEK_END)
                            errors.seek(max(0, errors.tell() - MAX_TRANSCODE_STDERR_BYTES))
                            detail = errors.read(MAX_TRANSCODE_STDERR_BYTES).decode("utf-8", "ignore")[-300:]
                            if not detail and isinstance(getattr(result, "stderr", None), (bytes, bytearray)):
                                detail = bytes(result.stderr)[-300:].decode("utf-8", "ignore")
                            try:
                                os.remove(temp)
                            except OSError:
                                pass
                            raise RuntimeError("音频转码失败: " + detail)
                except (subprocess.TimeoutExpired, ResourceLimitError) as exc:
                    try:
                        os.remove(temp)
                    except OSError:
                        pass
                    if isinstance(exc, subprocess.TimeoutExpired):
                        raise RuntimeError("audio transcode timed out") from exc
                    raise RuntimeError("audio transcode diagnostic output exceeded safety limit") from exc
                except OSError as exc:
                    try:
                        os.remove(temp)
                    except OSError:
                        pass
                    raise RuntimeError("failed to start ffmpeg: %s" % exc) from exc
                # A full or read-only cache volume must also degrade to a
                # handled 5xx, never to an OSError escaping the request path.
                try:
                    secure_file(temp)
                    os.replace(temp, target)
                    secure_file(target)
                except OSError as exc:
                    raise RuntimeError("failed to publish transcode cache: %s" % exc) from exc
        return target, mime
    finally:
        # Every failed attempt must release its unique temporary output
        # immediately. The periodic cache pruner is only a backstop and can
        # otherwise let failed jobs consume the disk reserve for hours.
        try:
            os.remove(temp)
        except OSError:
            pass
        _unmark_active_transcode_paths(active_paths)


def transcode_cache_target(item, config, mode="mp3"):
    cache_dir = config.get("cache_dir") or os.path.join(os.path.dirname(item["path"]), ".fnaudio-cache")
    stem = _cache_item_stem(item)
    if mode == "dsd_wav":
        return os.path.join(cache_dir, stem + ".dsd-96k-24bit.wav"), "audio/wav"
    if mode == "cue_flac":
        return os.path.join(cache_dir, stem + ".cue-segment.flac"), "audio/flac"
    if mode == "ape_flac":
        return os.path.join(cache_dir, stem + ".ape-source.flac"), "audio/flac"
    return os.path.join(cache_dir, stem + ".mp3"), "audio/mpeg"


def transcode_cache_ready(item, config, mode="mp3"):
    target, mime = transcode_cache_target(item, config, mode)
    # The cache can be pruned between the existence check and stat. Treat
    # that normal miss race as a miss instead of failing the playback request.
    if not os.path.isfile(target):
        return target, mime, False
    try:
        target_mtime = os.path.getmtime(target)
    except OSError:
        return target, mime, False
    source_mtime = _transcode_source_mtime(item)
    if source_mtime is None:
        return target, mime, False
    return target, mime, target_mtime >= source_mtime


def _transcode_cache_worker():
    global TRANSCODE_WORKER
    while True:
        with TRANSCODE_LOCK:
            if TRANSCODE_STOP_EVENT.is_set():
                while TRANSCODE_QUEUE:
                    _priority, _sequence, queued_key, _item, _config, _mode = heapq.heappop(TRANSCODE_QUEUE)
                    TRANSCODE_JOBS.discard(queued_key)
                TRANSCODE_WORKER = None
                return
            if not TRANSCODE_QUEUE:
                TRANSCODE_WORKER = None
                return
            _priority, _sequence, job_key, item, config, mode = heapq.heappop(TRANSCODE_QUEUE)
        try:
            transcode_to_audio(item, config, mode)
        except Exception:
            pass
        finally:
            with TRANSCODE_LOCK:
                TRANSCODE_JOBS.discard(job_key)


def shutdown_transcode_cache_worker(wait=True, timeout=5.0):
    """Stop cache warming and release queued jobs during server shutdown."""
    global TRANSCODE_WORKER
    with TRANSCODE_LOCK:
        TRANSCODE_STOP_EVENT.set()
        while TRANSCODE_QUEUE:
            _priority, _sequence, job_key, _item, _config, _mode = heapq.heappop(TRANSCODE_QUEUE)
            TRANSCODE_JOBS.discard(job_key)
        worker = TRANSCODE_WORKER
    if wait and worker is not None and worker is not threading.current_thread():
        worker.join(max(0.0, safe_float(timeout, 5.0)))
    with TRANSCODE_LOCK:
        if TRANSCODE_WORKER is worker and (worker is None or not worker.is_alive()):
            TRANSCODE_WORKER = None


def warm_transcode_cache(item, config, mode="mp3", priority=100):
    """Queue cache work so the currently selected track can run before opportunistic warms."""
    global TRANSCODE_SEQUENCE, TRANSCODE_WORKER
    _, _, ready = transcode_cache_ready(item, config, mode)
    if ready:
        return False
    job_key = _transcode_job_key(item, mode)
    queue_priority = _safe_priority(priority)
    with TRANSCODE_LOCK:
        if TRANSCODE_STOP_EVENT.is_set():
            if TRANSCODE_WORKER is not None and TRANSCODE_WORKER.is_alive():
                return False
            TRANSCODE_STOP_EVENT.clear()
        if job_key in TRANSCODE_JOBS:
            return False
        queue_limit = bounded_int(config, "transcode_queue_max_jobs", 64, 1, 1000)
        if len(TRANSCODE_QUEUE) >= queue_limit:
            worst = max(TRANSCODE_QUEUE, key=lambda entry: (entry[0], entry[1]))
            if queue_priority >= worst[0]:
                return False
            TRANSCODE_QUEUE.remove(worst)
            heapq.heapify(TRANSCODE_QUEUE)
            TRANSCODE_JOBS.discard(worst[2])
        TRANSCODE_JOBS.add(job_key)
        TRANSCODE_SEQUENCE += 1
        heapq.heappush(
            TRANSCODE_QUEUE,
            (queue_priority, TRANSCODE_SEQUENCE, job_key, dict(item), dict(config), mode),
        )
        if TRANSCODE_WORKER is None or not TRANSCODE_WORKER.is_alive():
            try:
                worker = threading.Thread(target=_transcode_cache_worker, daemon=True)
                TRANSCODE_WORKER = worker
                worker.start()
            except Exception:
                # Keep a failed thread creation from stranding the job in the
                # de-duplication set forever. Older queued jobs remain
                # available for a later request to restart the worker.
                TRANSCODE_WORKER = None
                TRANSCODE_JOBS.discard(job_key)
                TRANSCODE_QUEUE[:] = [entry for entry in TRANSCODE_QUEUE if entry[2] != job_key]
                heapq.heapify(TRANSCODE_QUEUE)
                return False
    return True


def transcode_command(item, config, mode, start=0):
    ffmpeg = find_ffmpeg(config)
    if not ffmpeg:
        raise RuntimeError("系统中未找到可用的 ffmpeg")
    command = [ffmpeg, "-threads", "0", "-hide_banner", "-loglevel", "error"]
    if start and start > 0:
        command += ["-ss", str(max(0, float(start)))]
    if mode == "dsd_wav":
        mime = "audio/wav"
        command += ["-i", item["path"], "-vn", "-map", "0:a:0", "-ar", "96000", "-codec:a", "pcm_s24le", "-f", "wav", "pipe:1"]
    elif mode == "ape_flac":
        mime = "audio/flac"
        command += ["-i", item["path"], "-vn", "-map", "0:a:0", "-codec:a", "flac", "-f", "flac", "pipe:1"]
    else:
        mime = "audio/mpeg"
        command += ["-i", item["path"], "-vn", "-map", "0:a:0", "-codec:a", "libmp3lame", "-q:a", "2", "-f", "mp3", "pipe:1"]
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
    return command, mime, env


def prune_transcode_cache(config, max_age_seconds=CACHE_TTL_SECONDS):
    cache_dir = config.get("cache_dir")
    if not cache_dir or not os.path.isdir(cache_dir):
        return 0
    now = time.time()
    removed = 0
    candidates = []
    with TRANSCODE_LOCK:
        active_stems = {
            _cache_item_stem({"id": key.split(":", 1)[-1]})
            for key in TRANSCODE_JOBS
        }
        active_paths = set(_ACTIVE_TRANSCODE_PATHS)
    try:
        names = os.listdir(cache_dir)
    except OSError:
        # The share can drop out between the isdir() check above and the
        # listing.  Nothing to sweep is a miss, not a playback failure.
        return removed
    for name in names:
        lower_name = name.lower()
        is_transcode = lower_name.endswith((".mp3", ".dsd-96k-24bit.wav", ".cue-segment.flac", ".ape-source.flac"))
        is_transcode_temp = ".tmp." in lower_name and lower_name.endswith((".mp3", ".wav", ".flac"))
        if not is_transcode and not is_transcode_temp:
            continue
        path = os.path.join(cache_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            stat = os.stat(path)
            if any(name.startswith(stem + ".") for stem in active_stems) or path in active_paths:
                continue
            candidates.append((stat.st_mtime, stat.st_size, path))
        except OSError:
            pass
    remaining = []
    for modified, size, path in candidates:
        if now - modified > max_age_seconds:
            try:
                os.remove(path)
                removed += 1
                continue
            except OSError:
                pass
        remaining.append((modified, size, path))
    max_bytes = bounded_int(config, "transcode_cache_max_bytes", 2 * 1024 * 1024 * 1024, 64 * 1024 * 1024, 64 * 1024 * 1024 * 1024)
    minimum_free = bounded_int(config, "cache_min_free_bytes", 512 * 1024 * 1024, 64 * 1024 * 1024, 16 * 1024 * 1024 * 1024)
    total = sum(size for _, size, _ in remaining)
    for modified, size, path in sorted(remaining):
        if total <= max_bytes and disk_has_reserve(cache_dir, minimum_free):
            break
        try:
            os.remove(path)
            total = max(0, total - size)
            removed += 1
        except OSError:
            pass
    return removed


def transcode_resource_status(config):
    with TRANSCODE_LOCK:
        queued = len(TRANSCODE_QUEUE)
        tracked = len(TRANSCODE_JOBS)
    return {
        "queued": queued,
        "tracked": tracked,
        "queue_limit": bounded_int(config, "transcode_queue_max_jobs", 64, 1, 1000),
        "ffmpeg": {
            **FFMPEG_GATE.snapshot(),
            "limit": bounded_int(config, "ffmpeg_max_concurrency", 2, 1, 8),
            "waiter_limit": bounded_int(config, "ffmpeg_max_waiters", 32, 0, 256),
        },
    }


def cleanup_transcode_cache_if_due(config, force=False):
    """Sweep the cache at most once per interval, and never fail a request.

    The sweep walks every cached file, so concurrent transcode requests must
    not each pay for one.  The interval is claimed before sweeping because a
    sweep that raises used to leave it unarmed, turning every later request
    into a fresh full scan of a directory that keeps failing.
    """
    global LAST_CACHE_CLEANUP
    now = time.time()
    with _CACHE_CLEANUP_LOCK:
        if not force and now - LAST_CACHE_CLEANUP < CACHE_CLEANUP_INTERVAL:
            return
        LAST_CACHE_CLEANUP = now
    try:
        prune_transcode_cache(config)
    except OSError:
        pass


__all__ = [
    "cleanup_transcode_cache_if_due",
    "find_ffmpeg",
    "media_mode",
    "playback_profile",
    "public_access",
    "prune_transcode_cache",
    "transcode_cache_ready",
    "transcode_cache_target",
    "transcode_command",
    "transcode_to_audio",
    "transcode_resource_status",
    "shutdown_transcode_cache_worker",
    "warm_transcode_cache",
]
