from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import threading
import time
import heapq
from typing import Any, Dict


MP3_EXTENSIONS = {".mp3"}
CACHE_TTL_SECONDS = 2 * 24 * 60 * 60
CACHE_CLEANUP_INTERVAL = 6 * 60 * 60
TRANSCODE_JOBS = set()
TRANSCODE_LOCK = threading.Lock()
TRANSCODE_QUEUE = []
TRANSCODE_SEQUENCE = 0
TRANSCODE_WORKER = None
LAST_CACHE_CLEANUP = 0
PRIVATE_HOSTS = {"localhost", "127.0.0.1", "::1"}


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_private_host(value):
    host = (value or "").split(",", 1)[0].strip().split(":", 1)[0].lower()
    if not host:
        return False
    if host in PRIVATE_HOSTS or host.endswith(".local") or host.endswith(".lan"):
        return True
    try:
        ip = socket.gethostbyname(host)
        parts = [int(x) for x in ip.split(".")]
        return (
            parts[0] == 10
            or parts[0] == 127
            or (parts[0] == 172 and 16 <= parts[1] <= 31)
            or (parts[0] == 192 and parts[1] == 168)
            or (parts[0] == 169 and parts[1] == 254)
        )
    except (OSError, ValueError):
        return False


def playback_profile(handler):
    host = handler.headers.get("X-Forwarded-Host") or handler.headers.get("Host", "")
    remote = handler.headers.get("X-Forwarded-For") or handler.headers.get("X-Real-IP") or handler.client_address[0]
    remote_first = (remote or "").split(",", 1)[0].strip()
    if remote_first and not is_private_host(remote_first):
        return "wan"
    if remote_first and is_private_host(remote_first) and remote_first not in ("127.0.0.1", "::1"):
        return "lan"
    if host:
        return "lan" if is_private_host(host) else "wan"
    return "lan" if is_private_host(remote_first) else "wan"


def public_access(handler):
    return {
        "profile": playback_profile(handler),
        "client_ip": (handler.headers.get("X-Forwarded-For") or handler.headers.get("X-Real-IP") or handler.client_address[0]).split(",", 1)[0].strip(),
        "host": handler.headers.get("X-Forwarded-Host") or handler.headers.get("Host", ""),
        "proto": handler.headers.get("X-Forwarded-Proto") or "http",
    }


def media_mode(item, query, handler):
    requested = (query.get("transcode") or query.get("delivery") or ["auto"])[0]
    profile = (query.get("profile") or ["auto"])[0]
    ext = os.path.splitext(item["path"])[1].lower()
    if requested in ("original", "upnp"):
        return "original"
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
        try:
            os.chmod(candidate, os.stat(candidate).st_mode | 0o755)
        except OSError:
            pass
        return candidate
    return ""


def transcode_to_audio(item, config, mode="mp3"):
    if mode == "original":
        return item["path"], item["mime"]
    ffmpeg = find_ffmpeg(config)
    if not ffmpeg:
        raise RuntimeError("系统中未找到可用的 ffmpeg")
    cache_dir = config.get("cache_dir") or os.path.join(os.path.dirname(item["path"]), ".fnaudio-cache")
    os.makedirs(cache_dir, exist_ok=True)
    if mode == "dsd_wav":
        target = os.path.join(cache_dir, item["id"] + ".dsd-96k-24bit.wav")
        mime = "audio/wav"
        temp = target + ".tmp.wav"
        command = [ffmpeg, "-threads", "0", "-y", "-i", item["path"], "-vn", "-map", "0:a:0", "-ar", "96000", "-codec:a", "pcm_s24le"]
    elif mode == "cue_flac":
        target = os.path.join(cache_dir, item["id"] + ".cue-segment.flac")
        mime = "audio/flac"
        temp = target + ".tmp.flac"
        command = [ffmpeg, "-threads", "0", "-y", "-ss", str(max(0, safe_float(item.get("cue_start")))), "-i", item["path"]]
        duration = safe_float(item.get("duration"))
        if duration > 0:
            command += ["-t", str(duration)]
        command += ["-vn", "-map", "0:a:0", "-codec:a", "flac"]
    else:
        target = os.path.join(cache_dir, item["id"] + ".mp3")
        mime = "audio/mpeg"
        temp = target + ".tmp.mp3"
        command = [ffmpeg, "-threads", "0", "-y", "-i", item["path"], "-vn", "-map", "0:a:0", "-codec:a", "libmp3lame", "-q:a", "2"]
    source_mtime = os.path.getmtime(item["path"])
    if item.get("cue_path") and os.path.isfile(item.get("cue_path")):
        source_mtime = max(source_mtime, os.path.getmtime(item["cue_path"]))
    if not os.path.isfile(target) or os.path.getmtime(target) < source_mtime:
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
        result = subprocess.run(command + [temp], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=900, env=env)
        if result.returncode != 0:
            try:
                os.remove(temp)
            except OSError:
                pass
            detail = result.stderr.decode("utf-8", "ignore")[-300:]
            raise RuntimeError("音频转码失败: " + detail)
        os.replace(temp, target)
    return target, mime


def transcode_cache_target(item, config, mode="mp3"):
    cache_dir = config.get("cache_dir") or os.path.join(os.path.dirname(item["path"]), ".fnaudio-cache")
    if mode == "dsd_wav":
        return os.path.join(cache_dir, item["id"] + ".dsd-96k-24bit.wav"), "audio/wav"
    if mode == "cue_flac":
        return os.path.join(cache_dir, item["id"] + ".cue-segment.flac"), "audio/flac"
    return os.path.join(cache_dir, item["id"] + ".mp3"), "audio/mpeg"


def transcode_cache_ready(item, config, mode="mp3"):
    target, mime = transcode_cache_target(item, config, mode)
    return target, mime, os.path.isfile(target) and os.path.getmtime(target) >= os.path.getmtime(item["path"])


def _transcode_cache_worker():
    global TRANSCODE_WORKER
    while True:
        with TRANSCODE_LOCK:
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


def warm_transcode_cache(item, config, mode="mp3", priority=100):
    """Queue cache work so the currently selected track can run before opportunistic warms."""
    global TRANSCODE_SEQUENCE, TRANSCODE_WORKER
    _, _, ready = transcode_cache_ready(item, config, mode)
    if ready:
        return False
    job_key = "%s:%s" % (mode, item["id"])
    with TRANSCODE_LOCK:
        if job_key in TRANSCODE_JOBS:
            return False
        TRANSCODE_JOBS.add(job_key)
        TRANSCODE_SEQUENCE += 1
        heapq.heappush(
            TRANSCODE_QUEUE,
            (int(priority), TRANSCODE_SEQUENCE, job_key, dict(item), dict(config), mode),
        )
        if TRANSCODE_WORKER is None or not TRANSCODE_WORKER.is_alive():
            TRANSCODE_WORKER = threading.Thread(target=_transcode_cache_worker, daemon=True)
            TRANSCODE_WORKER.start()
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
    for name in os.listdir(cache_dir):
        lower_name = name.lower()
        is_transcode = lower_name.endswith((".mp3", ".dsd-96k-24bit.wav", ".cue-segment.flac"))
        is_transcode_temp = ".tmp." in lower_name and lower_name.endswith((".mp3", ".wav", ".flac"))
        if not is_transcode and not is_transcode_temp:
            continue
        path = os.path.join(cache_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            if now - os.path.getmtime(path) <= max_age_seconds:
                continue
            os.remove(path)
            removed += 1
        except OSError:
            pass
    return removed


def cleanup_transcode_cache_if_due(config, force=False):
    global LAST_CACHE_CLEANUP
    now = time.time()
    if force or now - LAST_CACHE_CLEANUP >= CACHE_CLEANUP_INTERVAL:
        prune_transcode_cache(config)
        LAST_CACHE_CLEANUP = now


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
    "warm_transcode_cache",
]
