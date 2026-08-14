from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import threading
import time
from collections import OrderedDict

from file_permissions import secure_directory, secure_file
from resource_limits import ResourceLimitError, ffmpeg_slot
from transcode import find_ffmpeg

ALLOWED_SIZES = (160, 512)
_LOCKS_GUARD = threading.Lock()
_LOCKS = {}
_MEMORY_CACHE_LOCK = threading.RLock()
_MEMORY_CACHE = OrderedDict()
_MEMORY_CACHE_BYTES = 0
_MEMORY_CACHE_LIMIT = 96 * 1024 * 1024
_ASSET_ALIAS_CACHE = OrderedDict()
_ASSET_ALIAS_CACHE_LIMIT = 4096
_PREWARM_LOCK = threading.Lock()
_PREWARM_PENDING = set()
_LIBRARY_PREWARM = {}
LIBRARY_PREWARM_PAGE_SIZE = 24
LIBRARY_PREWARM_DELAY_SECONDS = 0.15


def normalized_cover_size(value):
    try:
        requested = int(value or 0)
    except (TypeError, ValueError):
        return 0
    if requested <= 0:
        return 0
    return min(ALLOWED_SIZES, key=lambda size: abs(size - requested))


def cover_source_version(item):
    """Version artwork from the actual media file, including CUE-backed rows."""
    item = item or {}
    path = str(item.get("path") or "")
    if path:
        try:
            return int(os.stat(path).st_mtime_ns)
        except OSError:
            pass
    return int(item.get("modified_ns") or item.get("modified") or 0)


def _cache_key(item, size):
    identity = "%s\0%s\0%s" % (
        str((item or {}).get("id") or (item or {}).get("path") or ""),
        cover_source_version(item),
        int(size or 0),
    )
    return hashlib.sha256(identity.encode("utf-8", "surrogatepass")).hexdigest()


def _cache_paths(item, config, size):
    root = os.path.join(str(config.get("cache_dir") or "."), "covers", "thumb-%d" % size)
    key = _cache_key(item, size)
    return root, os.path.join(root, key + ".jpg"), os.path.join(root, key + ".none")


def _asset_path(config, size, asset_key):
    root = os.path.join(str(config.get("cache_dir") or "."), "covers", "assets", "thumb-%d" % size)
    return root, os.path.join(root, asset_key + ".jpg")


def _read_asset_alias(path, config, size):
    try:
        with open(path, "rt", encoding="ascii") as handle:
            asset_key = handle.read().strip()
    except OSError:
        return None
    if len(asset_key) != 64 or any(char not in "0123456789abcdef" for char in asset_key):
        return None
    _root, target = _asset_path(config, size, asset_key)
    try:
        with open(target, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def thumbnail_asset_id_for_item(item, config, size=160):
    size = normalized_cover_size(size)
    if not size:
        return ""
    _root, target, _missing = _cache_paths(item, config, size)
    alias = target[:-4] + ".asset"
    with _MEMORY_CACHE_LOCK:
        cached = _ASSET_ALIAS_CACHE.get(alias)
        if cached:
            _asset_root, cached_path = _asset_path(config, size, cached)
            if os.path.isfile(cached_path):
                _ASSET_ALIAS_CACHE.move_to_end(alias)
                return cached
            _ASSET_ALIAS_CACHE.pop(alias, None)
    try:
        with open(alias, "rt", encoding="ascii") as handle:
            asset_key = handle.read().strip()
    except OSError:
        return ""
    if len(asset_key) != 64 or any(char not in "0123456789abcdef" for char in asset_key):
        return ""
    _asset_root, asset_path = _asset_path(config, size, asset_key)
    if not os.path.isfile(asset_path):
        return ""
    with _MEMORY_CACHE_LOCK:
        _ASSET_ALIAS_CACHE[alias] = asset_key
        _ASSET_ALIAS_CACHE.move_to_end(alias)
        while len(_ASSET_ALIAS_CACHE) > _ASSET_ALIAS_CACHE_LIMIT:
            _ASSET_ALIAS_CACHE.popitem(last=False)
    return asset_key


def thumbnail_asset_bytes(config, asset_key, size=160):
    size = normalized_cover_size(size)
    asset_key = str(asset_key or "").strip().lower()
    if not size or len(asset_key) != 64 or any(char not in "0123456789abcdef" for char in asset_key):
        return None
    memory_key = (str(config.get("cache_dir") or "."), "asset", asset_key, int(size))
    value = _memory_get(memory_key)
    if value is not None:
        return value
    _root, target = _asset_path(config, size, asset_key)
    try:
        with open(target, "rb") as handle:
            value = ("image/jpeg", handle.read())
    except OSError:
        return None
    _memory_put(memory_key, value)
    return value


def cover_is_known_missing(item, config, size=160):
    size = normalized_cover_size(size)
    if not size:
        return False
    _root, _target, missing = _cache_paths(item, config, size)
    return os.path.isfile(missing)


def _key_lock(key):
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def _memory_get(key):
    with _MEMORY_CACHE_LOCK:
        value = _MEMORY_CACHE.get(key)
        if value is None:
            return None
        _MEMORY_CACHE.move_to_end(key)
        return value


def _memory_put(key, value):
    global _MEMORY_CACHE_BYTES
    if not value:
        return
    with _MEMORY_CACHE_LOCK:
        previous = _MEMORY_CACHE.pop(key, None)
        if previous is not None:
            _MEMORY_CACHE_BYTES -= len(previous[1])
        _MEMORY_CACHE[key] = value
        _MEMORY_CACHE_BYTES += len(value[1])
        while _MEMORY_CACHE_BYTES > _MEMORY_CACHE_LIMIT and _MEMORY_CACHE:
            _old_key, (_mime, old_body) = _MEMORY_CACHE.popitem(last=False)
            _MEMORY_CACHE_BYTES -= len(old_body)


def clear_memory_cache():
    global _MEMORY_CACHE_BYTES
    with _MEMORY_CACHE_LOCK:
        _MEMORY_CACHE.clear()
        _ASSET_ALIAS_CACHE.clear()
        _MEMORY_CACHE_BYTES = 0


def prewarm_thumbnails(items, config, cover_reader, size=160):
    """Warm a small visible window without delaying the library response."""
    size = normalized_cover_size(size)
    if not size:
        return
    jobs = []
    with _PREWARM_LOCK:
        for item in list(items or [])[:24]:
            key = (str((item or {}).get("id") or (item or {}).get("path") or ""),
                   cover_source_version(item), int(size))
            if key in _PREWARM_PENDING:
                continue
            _PREWARM_PENDING.add(key)
            jobs.append((key, item))
    if not jobs:
        return

    def worker():
        try:
            for key, item in jobs:
                try:
                    cached_thumbnail_for_item(item, config, size, cover_reader)
                finally:
                    with _PREWARM_LOCK:
                        _PREWARM_PENDING.discard(key)
        finally:
            for key, _item in jobs:
                with _PREWARM_LOCK:
                    _PREWARM_PENDING.discard(key)

    threading.Thread(target=worker, name="fnaudio-cover-prewarm", daemon=True).start()


def prewarm_library_thumbnails(items, config, cover_reader, size=160):
    """Build thumbnails in cancellable, low-priority pages after a scan."""
    size = normalized_cover_size(size)
    if not size:
        return
    cache_key = str(config.get("cache_dir") or ".")
    with _PREWARM_LOCK:
        state = _LIBRARY_PREWARM.setdefault(cache_key, {
            "generation": 0,
            "running": False,
            "items": [],
            "cancel": threading.Event(),
            "thread": None,
        })
        state["generation"] += 1
        state["items"] = list(items or [])
        state["cancel"].clear()
        if state["running"]:
            return
        state["running"] = True

    def worker():
        while True:
            with _PREWARM_LOCK:
                state = _LIBRARY_PREWARM.get(cache_key)
                if state is None or state["cancel"].is_set():
                    return
                generation = state["generation"]
                jobs = state["items"][:LIBRARY_PREWARM_PAGE_SIZE]
                del state["items"][:len(jobs)]
            if not jobs:
                with _PREWARM_LOCK:
                    if _LIBRARY_PREWARM.get(cache_key) is state:
                        state["running"] = False
                        _LIBRARY_PREWARM.pop(cache_key, None)
                return
            for item in jobs:
                with _PREWARM_LOCK:
                    if (state["cancel"].is_set()
                            or _LIBRARY_PREWARM.get(cache_key, {}).get("generation") != generation):
                        break
                # Do not create a negative cover cache for a file that was
                # deleted between the scan and this deferred worker.
                if not os.path.isfile(str((item or {}).get("path") or "")):
                    continue
                try:
                    cached_thumbnail_for_item(
                        item,
                        config,
                        size,
                        cover_reader,
                        ffmpeg_slot_timeout=0.05,
                        cancel_event=state["cancel"],
                    )
                except Exception:
                    # A corrupt tag must not stop warming the rest of the library.
                    pass
            with _PREWARM_LOCK:
                state = _LIBRARY_PREWARM.get(cache_key)
                if state is None or state["cancel"].is_set():
                    return
                if state["generation"] != generation:
                    continue
            # Keep cache work behind interactive playback, transcode and
            # metadata tasks even when a large library has no cache yet.
            if state["cancel"].wait(LIBRARY_PREWARM_DELAY_SECONDS):
                return

    thread = threading.Thread(target=worker, name="fnaudio-cover-library-prewarm", daemon=True)
    with _PREWARM_LOCK:
        state["thread"] = thread
    thread.start()


def shutdown_library_thumbnail_prewarm(wait=False, timeout=5.0):
    """Cancel deferred thumbnail work, for shutdown and cache-root changes."""
    with _PREWARM_LOCK:
        states = list(_LIBRARY_PREWARM.values())
        _LIBRARY_PREWARM.clear()
        for state in states:
            state["cancel"].set()
    if wait:
        deadline = time.monotonic() + max(0.0, float(timeout))
        for state in states:
            thread = state.get("thread")
            if thread and thread.is_alive():
                thread.join(max(0.0, deadline - time.monotonic()))


def _atomic_bytes(path, body):
    directory = secure_directory(os.path.dirname(path))
    fd, temporary = tempfile.mkstemp(prefix=".fnaudio-cover-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        secure_file(path)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            if os.path.exists(temporary):
                os.unlink(temporary)
        except OSError:
            pass


def _thumbnail_bytes(body, config, size, ffmpeg_slot_timeout=5.0):
    ffmpeg = find_ffmpeg(config)
    if not ffmpeg:
        return None
    command = [
        ffmpeg, "-v", "error", "-i", "pipe:0",
        "-vf", "scale=%d:%d:force_original_aspect_ratio=decrease" % (size, size),
        "-frames:v", "1", "-c:v", "mjpeg", "-q:v", "5", "-f", "image2pipe", "pipe:1",
    ]
    environment = os.environ.copy()
    if "/usr/trim/lib/mediasrv/bin" in ffmpeg:
        environment["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + environment.get("LD_LIBRARY_PATH", "")
    try:
        with ffmpeg_slot(config, timeout=ffmpeg_slot_timeout):
            result = subprocess.run(command, input=body, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    timeout=15, env=environment)
    except (OSError, ResourceLimitError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 and result.stdout.startswith(b"\xff\xd8") else None


def cached_thumbnail_for_item(item, config, size, cover_reader, ffmpeg_slot_timeout=5.0, cancel_event=None):
    size = normalized_cover_size(size)
    if not size:
        return cover_reader(item, config)
    if cancel_event is not None and cancel_event.is_set():
        return None, None
    root, target, missing = _cache_paths(item, config, size)
    alias = target[:-4] + ".asset"
    memory_key = (str(config.get("cache_dir") or "."),
                  str((item or {}).get("id") or (item or {}).get("path") or ""),
                  cover_source_version(item), int(size))
    memory_value = _memory_get(memory_key)
    if memory_value is not None:
        return memory_value
    if os.path.isfile(target):
        try:
            with open(target, "rb") as handle:
                value = ("image/jpeg", handle.read())
                _memory_put(memory_key, value)
                return value
        except OSError:
            pass
    asset_body = _read_asset_alias(alias, config, size)
    if asset_body:
        value = ("image/jpeg", asset_body)
        _memory_put(memory_key, value)
        return value
    if os.path.isfile(missing):
        return None, None
    with _key_lock(_cache_key(item, size)):
        if cancel_event is not None and cancel_event.is_set():
            return None, None
        if os.path.isfile(target):
            try:
                with open(target, "rb") as handle:
                    value = ("image/jpeg", handle.read())
                    _memory_put(memory_key, value)
                    return value
            except OSError:
                pass
        asset_body = _read_asset_alias(alias, config, size)
        if asset_body:
            value = ("image/jpeg", asset_body)
            _memory_put(memory_key, value)
            return value
        if os.path.isfile(missing):
            return None, None
        mime, body = cover_reader(item, config)
        if cancel_event is not None and cancel_event.is_set():
            return None, None
        secure_directory(root)
        if not body:
            _atomic_bytes(missing, b"")
            return None, None
        thumbnail = _thumbnail_bytes(body, config, size, ffmpeg_slot_timeout)
        if cancel_event is not None and cancel_event.is_set():
            return None, None
        if not thumbnail:
            return mime, body
        asset_key = hashlib.sha256(body).hexdigest()
        asset_root, asset_target = _asset_path(config, size, asset_key)
        if not os.path.isfile(asset_target):
            secure_directory(asset_root)
            _atomic_bytes(asset_target, thumbnail)
        # Preserve a per-track version alias, while the image itself is shared
        # by every track that resolves to identical artwork bytes.
        _atomic_bytes(alias, asset_key.encode("ascii"))
        with _MEMORY_CACHE_LOCK:
            _ASSET_ALIAS_CACHE[alias] = asset_key
            _ASSET_ALIAS_CACHE.move_to_end(alias)
            while len(_ASSET_ALIAS_CACHE) > _ASSET_ALIAS_CACHE_LIMIT:
                _ASSET_ALIAS_CACHE.popitem(last=False)
        try:
            if os.path.exists(missing):
                os.unlink(missing)
        except OSError:
            pass
        value = ("image/jpeg", thumbnail)
        _memory_put(memory_key, value)
        return value


__all__ = ["cached_thumbnail_for_item", "clear_memory_cache", "cover_is_known_missing", "cover_source_version", "normalized_cover_size", "prewarm_library_thumbnails", "prewarm_thumbnails", "shutdown_library_thumbnail_prewarm", "thumbnail_asset_bytes", "thumbnail_asset_id_for_item"]
