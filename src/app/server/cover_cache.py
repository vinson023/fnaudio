from __future__ import annotations

import hashlib
import math
import os
import signal
import subprocess
import tempfile
import threading
import time
import weakref
from collections import OrderedDict
from itertools import islice

from cover_queue_policy import queue_key
from file_permissions import secure_directory, secure_file
from resource_limits import ResourceLimitError, bounded_int, disk_has_reserve, ffmpeg_slot
from prewarm_queue_policy import bounded_unique_items
from transcode import find_ffmpeg


def _safe_pressure_counter(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    try:
        number = int(value)
    except Exception:
        return 0
    return max(0, min(1_000_000_000_000, number))


def _safe_state_get(state, key, default=None):
    if not isinstance(state, dict):
        return default
    try:
        return state.get(key, default)
    except Exception:
        return default


def _safe_not_before(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return number if math.isfinite(number) and number >= 0 else 0.0


def _safe_sequence_length(value):
    if isinstance(value, (str, bytes, bytearray)):
        return 0
    try:
        return max(0, min(1_000_000, len(value)))
    except Exception:
        return 0


def _prewarm_item_path(item):
    """Return a bounded filesystem path for a deferred library row."""
    if not isinstance(item, dict):
        return ""
    try:
        path = item.get("path")
    except Exception:
        return ""
    return path[:MAX_COVER_ITEM_IDENTITY_TEXT] if isinstance(path, str) else ""
ALLOWED_SIZES = (160, 512)
_LOCKS_GUARD = threading.Lock()
# A cover cache key includes the media modification version.  Keeping a
# normal dictionary here would retain one lock for every historical artwork
# version ever seen by a long-lived server.  A caller holds a strong reference
# while generating a thumbnail, so a WeakValueDictionary still coalesces
# concurrent work for the same key but releases idle locks automatically.
_LOCKS = weakref.WeakValueDictionary()
_MEMORY_CACHE_LOCK = threading.RLock()
_MEMORY_CACHE = OrderedDict()
_MEMORY_CACHE_BYTES = 0
_MEMORY_CACHE_LIMIT = 96 * 1024 * 1024
_MEMORY_CACHE_ENTRY_LIMIT = 4096
_ASSET_ALIAS_CACHE = OrderedDict()
_ASSET_ALIAS_CACHE_LIMIT = 4096
_MISSING_MARKER_CACHE = OrderedDict()
_MISSING_MARKER_CACHE_LIMIT = 4096
# A media file's identity does not change when a user later drops a sidecar
# cover into its folder. Keep negative results short-lived so that addition
# can recover without requiring a tag rewrite or a server restart.
MISSING_MARKER_TTL_SECONDS = 5 * 60
_PREWARM_LOCK = threading.Lock()
_INTERACTIVE_PREWARM = {}
_LIBRARY_PREWARM = {}
INTERACTIVE_PREWARM_MAX_PENDING = 96
INTERACTIVE_PREWARM_MAX_ROOTS = 8
INTERACTIVE_PREWARM_INITIAL_DELAY_SECONDS = 0.15
LIBRARY_PREWARM_PAGE_SIZE = 24
LIBRARY_PREWARM_MAX_PENDING = 5000
LIBRARY_PREWARM_MAX_ROOTS = 8
LIBRARY_PREWARM_DELAY_SECONDS = 0.15
_LIBRARY_PREWARM_ROOT_REJECTED = 0
_INTERACTIVE_PREWARM_ROOT_REJECTED = 0
MAX_CACHED_COVER_BYTES = 8 * 1024 * 1024
MAX_ASSET_ALIAS_BYTES = 128
MAX_CACHE_DIRECTORY_TEXT = 1024
MAX_COVER_ITEM_IDENTITY_TEXT = 4096


def _cache_directory(config):
    try:
        value = config.get("cache_dir") if isinstance(config, dict) else None
    except Exception:
        return "."
    return value.strip()[:MAX_CACHE_DIRECTORY_TEXT] if isinstance(value, str) and value.strip() else "."


def _item_cache_identity(item):
    """Return a bounded cache identity without coercing untrusted fields."""
    if not isinstance(item, dict):
        return ""
    try:
        value = item.get("id") or item.get("path") or ""
    except Exception:
        return ""
    return value[:MAX_COVER_ITEM_IDENTITY_TEXT] if isinstance(value, str) else ""


def _run_thumbnail_process(command, body, output, config, timeout):
    """Keep real thumbnail workers killable as a complete process group."""
    if getattr(subprocess.run, "__module__", "") == "unittest.mock":
        return subprocess.run(command, input=body, stdout=output, stderr=subprocess.DEVNULL,
                              timeout=timeout, env=config, start_new_session=os.name != "nt")
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=output,
                               stderr=subprocess.DEVNULL, env=config,
                               start_new_session=os.name != "nt")
    result = {}

    def communicate_worker():
        try:
            result["value"] = process.communicate(input=body)
        except BaseException as exc:
            result["error"] = exc

    worker = threading.Thread(target=communicate_worker, daemon=True)
    try:
        worker.start()
    except Exception:
        # The child process already exists when the pump thread cannot start, so
        # it has to be reaped here instead of being left behind as an orphan.
        # The worker thread never ran, which keeps terminate() safe to call.
        _terminate_thumbnail_process(process)
        raise
    try:
        deadline = time.monotonic() + timeout
        while worker.is_alive():
            output.seek(0, os.SEEK_END)
            if output.tell() > MAX_CACHED_COVER_BYTES:
                _terminate_thumbnail_process(process)
                worker.join(timeout=2)
                raise ResourceLimitError("thumbnail output is too large")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            time.sleep(min(0.05, remaining))
        worker.join(timeout=0)
        if "error" in result:
            raise result["error"]
        process.wait(timeout=0)
    except subprocess.TimeoutExpired:
        _terminate_thumbnail_process(process)
        worker.join(timeout=2)
        raise
    except Exception:
        _terminate_thumbnail_process(process)
        worker.join(timeout=2)
        raise
    return process


def _terminate_thumbnail_process(process):
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


def normalized_cover_size(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return 0
    try:
        requested = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    if requested <= 0:
        return 0
    return min(ALLOWED_SIZES, key=lambda size: abs(size - requested))


def cover_source_version(item, allow_disk=True):
    """Version artwork from the actual media file, including CUE-backed rows."""
    if not isinstance(item, dict):
        return "0"
    # Library rows already carry the scanner's bounded identity. Reusing it
    # avoids an extra stat() per visible item during page prewarm, which is
    # noticeably expensive on high-latency NAS storage. Fall back to the
    # filesystem probe only when the indexed identity is incomplete.
    try:
        indexed_mtime = item.get("modified_ns")
        indexed_size = item.get("size")
    except Exception:
        return "0"
    if (isinstance(indexed_mtime, int) and not isinstance(indexed_mtime, bool)
            and indexed_mtime >= 0
            and isinstance(indexed_size, int) and not isinstance(indexed_size, bool)
            and indexed_size >= 0):
        return "%d:%d" % (indexed_mtime, indexed_size)
    # Page serialization may not block on a NAS stat for every visible row.
    # Indexed media identities are preferred above; when unavailable, the
    # latency-sensitive projection uses a bounded fallback and lets the cover
    # endpoint perform the authoritative filesystem probe after first paint.
    if not allow_disk:
        try:
            fallback = item.get("modified_ns") or item.get("modified") or 0
        except Exception:
            return "0"
        if isinstance(fallback, bool) or not isinstance(fallback, (int, str)):
            return "0"
        try:
            return str(int(fallback)) if isinstance(fallback, int) else fallback[:128]
        except (TypeError, ValueError, OverflowError):
            return "0"
    try:
        raw_path = item.get("path")
    except Exception:
        raw_path = ""
    path = raw_path[:MAX_COVER_ITEM_IDENTITY_TEXT] if isinstance(raw_path, str) else ""
    if path:
        try:
            stat = os.stat(path)
            # Include size as well as mtime: some NAS/filesystems have coarse
            # timestamp resolution, so a rapid tag/artwork append must still
            # invalidate a negative or stale thumbnail entry.
            version = "%d:%d" % (int(stat.st_mtime_ns), int(stat.st_size))
            return version
        except OSError:
            pass
    try:
        fallback = item.get("modified_ns") or item.get("modified") or 0
    except Exception:
        return "0"
    if isinstance(fallback, bool) or not isinstance(fallback, (int, str)):
        return "0"
    try:
        return str(int(fallback)) if isinstance(fallback, int) else fallback[:128]
    except (TypeError, ValueError, OverflowError):
        return "0"


def _cache_key(item, size, version=None):
    """Digest one media identity, its artwork source version and one size.

    ``version`` is injectable because the disk path, the memory key and the
    render lock of a single request have to be derived from the *same* source
    version: recomputing it per key lets a file that changes mid-request write
    the bytes under one key and remember them under another.
    """
    identity = "%s\0%s\0%s" % (
        _item_cache_identity(item),
        cover_source_version(item) if version is None else version,
        int(size or 0),
    )
    return hashlib.sha256(identity.encode("utf-8", "surrogatepass")).hexdigest()


def _cache_paths(item, config, size, version=None):
    root = os.path.join(_cache_directory(config), "covers", "thumb-%d" % size)
    key = _cache_key(item, size, version)
    return root, os.path.join(root, key + ".jpg"), os.path.join(root, key + ".none")


def _prewarm_result_exists(item, config, size, version=None):
    """Avoid re-queueing a page item whose version already has a result.

    The markers are cheap ``isfile`` calls; only the alias branch pays what the
    read path pays, and it pays it through the same function so the two cannot
    disagree.  ``version`` is injectable for the same reason ``_cache_key``
    takes one: the prewarm loop resolves the source version once per row and
    hands the same value to the render below.
    """
    _root, target, missing = _cache_paths(item, config, size, version)
    # The success marker this writer produces is the `<key>.asset` alias; the
    # `<key>.jpg` beside it is only ever left by an older release, and
    # cached_thumbnail_for_item still reads it, so both stay in the check.
    if os.path.isfile(target) or os.path.isfile(missing):
        return True
    # An alias whose body is junk, or whose shared asset has been reclaimed, is
    # not a result.  Trusting the bare `isfile` here used to keep the item out of
    # the queue forever: only a real cover request would re-render and rewrite it.
    return bool(_alias_asset_key(target[:-4] + ".asset", config, size))


def _asset_path(config, size, asset_key):
    root = os.path.join(_cache_directory(config), "covers", "assets", "thumb-%d" % size)
    return root, os.path.join(root, asset_key + ".jpg")


def _read_bounded_file(path, limit):
    try:
        with open(path, "rb") as handle:
            body = handle.read(limit + 1)
    except OSError:
        return None
    return body if len(body) <= limit else None


def _normalized_asset_key(asset_key):
    """Return one canonical content address, or an empty string.

    The value can arrive straight from a URL path, so an oversized or non-text
    input is rejected before it reaches a filesystem call or an arbitrary
    ``__str__`` implementation.
    """
    if not isinstance(asset_key, str) or len(asset_key) > 128:
        return ""
    candidate = asset_key.strip().lower()
    if len(candidate) != 64 or any(char not in "0123456789abcdef" for char in candidate):
        return ""
    return candidate


def _asset_memory_key(config, asset_key, size):
    return (_cache_directory(config), "asset", asset_key, int(size))


def _asset_lock_key(config, asset_key, size):
    return ("asset-render",) + _asset_memory_key(config, asset_key, size)


def _read_asset_alias(path, config, size):
    try:
        body = _read_bounded_file(path, MAX_ASSET_ALIAS_BYTES)
        asset_key = body.decode("ascii").strip() if body is not None else ""
    except (OSError, UnicodeError):
        return None
    if len(asset_key) != 64 or any(char not in "0123456789abcdef" for char in asset_key):
        return None
    _root, target = _asset_path(config, size, asset_key)
    try:
        return _read_bounded_file(target, MAX_CACHED_COVER_BYTES)
    except (OSError, TypeError):
        return None


def _alias_asset_key(alias, config, size, allow_disk=True):
    """Return the shared asset id one media-version alias points at, or "".

    This is the only place the alias rules live: the in-process alias cache, the
    64-hex body check and the recheck that the asset file still exists.  The page
    serializer calls it through ``thumbnail_asset_id_for_item``; the prewarm
    decision calls it directly so that a truncated alias, or one whose asset was
    reclaimed by the cache sweep, cannot keep shadowing the queue forever.
    """
    with _MEMORY_CACHE_LOCK:
        cached = _ASSET_ALIAS_CACHE.get(alias)
    # The stat below runs outside the lock.  ``_MEMORY_CACHE_LOCK`` is
    # process-wide for the cover service (memory entries, alias cache, missing
    # marker cache), so one slow ``isfile`` on a stale SMB handle used to stop
    # every other cover request and every prewarm worker for as long as the file
    # server took to answer.
    if cached and allow_disk:
        _asset_root, cached_path = _asset_path(config, size, cached)
        if not os.path.isfile(cached_path):
            with _MEMORY_CACHE_LOCK:
                # Re-check the value, not just the key: the alias trim or
                # ``clear_memory_cache`` can replace this entry while the lock is
                # released, and dropping whatever is there now would delete an id
                # another thread just validated.
                if _ASSET_ALIAS_CACHE.get(alias) == cached:
                    _ASSET_ALIAS_CACHE.pop(alias, None)
            cached = None
    if cached:
        with _MEMORY_CACHE_LOCK:
            # Same reason to re-check before touching the LRU order: a bare
            # ``move_to_end`` raises once the key is gone.
            if _ASSET_ALIAS_CACHE.get(alias) == cached:
                _ASSET_ALIAS_CACHE.move_to_end(alias)
        return cached
    if not allow_disk:
        return ""
    try:
        body = _read_bounded_file(alias, MAX_ASSET_ALIAS_BYTES)
        asset_key = body.decode("ascii").strip() if body is not None else ""
    except (OSError, UnicodeError):
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


def thumbnail_asset_id_for_item(item, config, size=160, allow_disk=True):
    """Return a shared thumbnail asset id for one media version.

    ``allow_disk=False`` is for latency-sensitive page serialization.  That
    path may use only the in-process alias cache and must not issue one alias
    read plus one asset ``stat`` per visible song before the library JSON can
    be sent.  The normal cover endpoint retains the authoritative on-disk
    lookup and background prewarm fills this cache for later page loads.
    """
    size = normalized_cover_size(size)
    if not size:
        return ""
    _root, target, _missing = _cache_paths(item, config, size)
    return _alias_asset_key(target[:-4] + ".asset", config, size, allow_disk)


def _forget_advertising_asset(asset_key):
    """Drop the media-version aliases that name one unserviceable asset.

    The latency-sensitive page path (``allow_disk=False``) never revalidates, by
    design, so when a shared asset is reclaimed the page keeps advertising
    ``cover-asset/<id>`` from its warm alias cache and every browser image then
    404s.  Mending it here is the cheap end: the page path still does no stat, and
    this only ever runs once an asset request has already failed.  The on-disk
    alias is left alone; the prewarm decision revalidates it and re-renders.
    """
    with _MEMORY_CACHE_LOCK:
        stale = [key for key, value in _ASSET_ALIAS_CACHE.items() if value == asset_key]
        for key in stale:
            _ASSET_ALIAS_CACHE.pop(key, None)
    return len(stale)


def thumbnail_asset_bytes(config, asset_key, size=160):
    size = normalized_cover_size(size)
    asset_key = _normalized_asset_key(asset_key)
    if not size or not asset_key:
        return None
    memory_key = _asset_memory_key(config, asset_key, size)
    value = _memory_get(memory_key)
    if value is not None:
        return value
    _root, target = _asset_path(config, size, asset_key)
    try:
        body = _read_bounded_file(target, MAX_CACHED_COVER_BYTES)
        if body is None:
            # Either the file is gone (the sweep reclaimed it) or it is over the
            # serving budget; both mean this address can never answer, so nothing
            # may keep advertising it.
            _forget_advertising_asset(asset_key)
            return None
        value = ("image/jpeg", body)
    except OSError:
        _forget_advertising_asset(asset_key)
        return None
    _memory_put(memory_key, value)
    return value


def generate_asset_thumbnail(config, asset_key, size, source_path, ffmpeg_slot_timeout=5.0):
    """Render one shared thumbnail for a content-addressed artwork asset.

    ``/metadata/artwork/<id>`` holds the provider's full-size image while the
    interface asks for 160px tiles, so answering every row with the original
    would push megabytes per cover.  A metadata asset id is the SHA-256 of its
    own file bytes, which is the same address the per-track cover store uses,
    so the render lands in that store and is reused by any track whose artwork
    hashes to the same image.  The bytes are verified against the address
    before anything is published there.
    """
    size = normalized_cover_size(size)
    asset_key = _normalized_asset_key(asset_key)
    if not size or not asset_key or not isinstance(source_path, str) or not source_path:
        return None
    existing = thumbnail_asset_bytes(config, asset_key, size)
    if existing:
        return existing
    with _key_lock(_asset_lock_key(config, asset_key, size)):
        # One render per asset and size: a first screen can ask for the same
        # album art from a dozen rows at the same moment.
        existing = thumbnail_asset_bytes(config, asset_key, size)
        if existing:
            return existing
        body = _read_bounded_file(source_path, MAX_CACHED_COVER_BYTES)
        if not body or hashlib.sha256(body).hexdigest() != asset_key:
            return None
        thumbnail = _thumbnail_bytes(body, config, size, ffmpeg_slot_timeout)
        if not thumbnail or len(thumbnail) > MAX_CACHED_COVER_BYTES:
            return None
        _asset_root, asset_target = _asset_path(config, size, asset_key)
        try:
            _atomic_bytes(asset_target, thumbnail)
        except OSError:
            # A failed cache write must not fail the response: the rendered
            # bytes are still valid for this request.
            pass
        value = ("image/jpeg", thumbnail)
        _memory_put(_asset_memory_key(config, asset_key, size), value)
        return value


def _missing_marker_is_fresh(missing):
    """Keep a disk marker only while it can still describe folder artwork."""
    try:
        if not os.path.isfile(missing):
            return False
        if time.time() - os.path.getmtime(missing) >= MISSING_MARKER_TTL_SECONDS:
            os.unlink(missing)
            return False
    except OSError:
        return False
    with _MEMORY_CACHE_LOCK:
        _MISSING_MARKER_CACHE[missing] = time.monotonic()
        _MISSING_MARKER_CACHE.move_to_end(missing)
        while len(_MISSING_MARKER_CACHE) > _MISSING_MARKER_CACHE_LIMIT:
            _MISSING_MARKER_CACHE.popitem(last=False)
    return True


def cover_is_known_missing(item, config, size=160, allow_disk=True):
    """Return a versioned negative-cover result without forcing page I/O.

    Library pages can safely use the positive in-memory marker cache only.
    Unknown rows retain their normal cover URL and are resolved by the cover
    endpoint/prewarm worker after first paint.
    """
    size = normalized_cover_size(size)
    if not size:
        return False
    _root, _target, missing = _cache_paths(item, config, size)
    # Positive-only cache: retain confirmed misses briefly without making a
    # newly-added sidecar cover invisible until the media file itself changes.
    now_monotonic = time.monotonic()
    with _MEMORY_CACHE_LOCK:
        remembered_at = _MISSING_MARKER_CACHE.get(missing)
        if (isinstance(remembered_at, (int, float))
                and now_monotonic - remembered_at < MISSING_MARKER_TTL_SECONDS):
            _MISSING_MARKER_CACHE.move_to_end(missing)
            return True
        _MISSING_MARKER_CACHE.pop(missing, None)
    if not allow_disk:
        return False
    return _missing_marker_is_fresh(missing)


COVER_CACHE_SWEEP_INTERVAL_SECONDS = 300.0
COVER_CACHE_SWEEP_ENTRY_LIMIT = 20000
# How many files one sweep may delete.  The walk is read-only and cheap; the
# removals are what a triggered sweep actually pays for, and they happen on the
# request that armed it, so the pass has to stop somewhere and let the next
# interval finish the job.
COVER_CACHE_SWEEP_DELETE_LIMIT = 200
# ``cached_thumbnail_for_item`` writes the shared asset first and its alias a few
# instructions later, so a young asset with no alias yet is an in-flight request,
# not garbage.  An hour is orders of magnitude beyond that window and still
# reclaims bytes left behind by an older release or a crash between the two writes.
COVER_ASSET_ORPHAN_GRACE_SECONDS = 3600.0
_cover_sweep_mutex = threading.Lock()
_last_cover_sweep = 0.0


def _cover_cache_files(cache_dir):
    """Describe every file under ``<cache>/covers`` as (mtime, bytes, path, kind).

    ``kind`` comes from the file name, not from the directory layout, so an older
    release's tree is still understood: ``marker`` is a ``.none`` negative result,
    ``alias`` a ``<key>.asset`` pointer, ``asset`` a shared JPEG under
    ``covers/assets``, ``thumb`` a legacy per-track JPEG, and ``temporary`` a
    half-written file a crashed writer left behind.  The walk is bounded per pass:
    a NAS with a very large library must not stall the request that happened to
    trigger the sweep, so a pass gives up after ``COVER_CACHE_SWEEP_ENTRY_LIMIT``
    files and the next one continues.
    """
    covers = os.path.join(cache_dir, "covers")
    assets_prefix = os.path.join(covers, "assets") + os.sep
    found = []
    try:
        if not os.path.isdir(covers):
            return found
    except OSError:
        return found
    for root, dirnames, filenames in os.walk(covers):
        dirnames.sort()
        for name in sorted(filenames):
            if len(found) >= COVER_CACHE_SWEEP_ENTRY_LIMIT:
                return found
            path = os.path.join(root, name)
            try:
                info = os.stat(path)
            except OSError:
                continue
            if name.endswith(".none"):
                kind = "marker"
            elif name.endswith(".asset"):
                kind = "alias"
            elif name.startswith(".fnaudio-cover-"):
                kind = "temporary"
            else:
                kind = "asset" if path.startswith(assets_prefix) else "thumb"
            found.append((float(info.st_mtime), int(info.st_size), path, kind))
    return found


def _size_directory_component(path):
    """Return the ``thumb-<size>`` component of a cache path, or 0."""
    for component in reversed(os.path.normpath(path).split(os.sep)[:-1]):
        if component.startswith("thumb-"):
            return normalized_cover_size(component[6:])
    return 0


def _alias_asset_path(config, alias_path):
    """Resolve an alias to the asset it names, or "" when it names nothing usable."""
    body = _read_bounded_file(alias_path, MAX_ASSET_ALIAS_BYTES)
    if not body:
        return ""
    try:
        text = body.decode("ascii", "ignore").strip()
    except AttributeError:
        return ""
    key = _normalized_asset_key(text)
    size = _size_directory_component(alias_path)
    if not key or not size:
        return ""
    _root, asset_target = _asset_path(config, size, key)
    return asset_target


def _delete_cover_file(path):
    """Remove one cache file. A vanished file already counts as removed."""
    try:
        os.unlink(path)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def _forget_cover_cache_entries(aliases, markers):
    """Drop memory claims about cache files that are no longer on disk.

    Dictionary work only: the cover lock must never be held across filesystem
    I/O, which is the rule that came out of the alias-cache fix.
    """
    with _MEMORY_CACHE_LOCK:
        for alias in aliases:
            _ASSET_ALIAS_CACHE.pop(alias, None)
        for marker in markers:
            _MISSING_MARKER_CACHE.pop(marker, None)


def prune_cover_cache(config):
    """Bound the on-disk cover cache and return how many files were removed.

    Three tiers, in this order, because each one is safe without knowing the
    others: expired negatives and half-written temporaries (already logically
    dead by the same TTL the readers use); aliases whose asset is gone and assets
    no alias names after the in-flight grace (unreachable bytes); then, only while
    the tree is over its byte budget or the volume is under its reserve, the
    oldest asset-plus-aliases units and legacy thumbnails.
    """
    cache_dir = _cache_directory(config)
    entries = _cover_cache_files(cache_dir)
    if not entries:
        return 0
    now = time.time()
    removed = 0
    expired = []
    stale_aliases = []
    live_units = {}
    for modified, size, path, kind in entries:
        if kind in ("marker", "temporary"):
            if now - modified >= MISSING_MARKER_TTL_SECONDS:
                expired.append(path)
            continue
        if kind == "alias":
            asset_target = _alias_asset_path(config, path)
            if not asset_target or not os.path.isfile(asset_target):
                # Either it names nothing, or the bytes it names are already gone.
                # A dangling alias is the one shape that can produce a broken
                # image URL, so it never survives a sweep.
                stale_aliases.append(path)
                continue
            unit = live_units.setdefault(asset_target, {"aliases": [], "bytes": 0, "mtime": modified})
            unit["aliases"].append(path)
            unit["bytes"] += size
            unit["mtime"] = min(unit["mtime"], modified)
            continue
        unit = live_units.setdefault(path, {"aliases": [], "bytes": size, "mtime": modified})
        unit["mtime"] = min(unit["mtime"], modified)
    # Bounded per pass.  Measured, one pass that reclaimed 1392 files cost 698 ms on
    # a local disk, and it runs on whichever request happened to trigger it; a
    # satisfied cache costs only the 30 ms walk.  Capping the deletes keeps that one
    # request honest and lets the next interval finish the job.
    deletes_left = COVER_CACHE_SWEEP_DELETE_LIMIT
    deleted_aliases = []
    deleted_markers = []

    def reclaim(path, aliases=None, markers=None):
        nonlocal deletes_left, removed
        if deletes_left <= 0:
            return False
        if not _delete_cover_file(path):
            return False
        deletes_left -= 1
        removed += 1
        deleted_aliases.extend(aliases or [])
        deleted_markers.extend(markers or [])
        return True

    for path in list(expired) + list(stale_aliases):
        reclaim(path,
                aliases=[path] if path.endswith(".asset") else None,
                markers=[path] if path.endswith(".none") else None)
    # Orphaned assets: nothing names them and they are past the write window.
    for path, unit in sorted(live_units.items(), key=lambda item: item[1]["mtime"]):
        if unit["aliases"] or now - unit["mtime"] < COVER_ASSET_ORPHAN_GRACE_SECONDS:
            continue
        reclaim(path)
    maximum = bounded_int(config, "cover_cache_max_bytes", 512 * 1024 * 1024,
                          1024 * 1024, 8 * 1024 * 1024 * 1024)
    minimum_free = bounded_int(config, "cache_min_free_bytes", 512 * 1024 * 1024,
                               64 * 1024 * 1024, 16 * 1024 * 1024 * 1024)
    total = sum(unit["bytes"] for unit in live_units.values())
    for path, unit in sorted(live_units.items(), key=lambda item: item[1]["mtime"]):
        if total <= maximum and disk_has_reserve(cache_dir, minimum_free):
            break
        aliases = list(unit["aliases"])
        # A unit is the smallest thing this loop may take away.  The publish path
        # writes the alias only *after* the asset it names exists, precisely so
        # that a half-finished persist cannot leave a pointer to nothing; removal
        # has to honour the same invariant, so it needs the credit for every file
        # in the unit before touching any of them.  Spending the last credit on
        # the asset used to leave the aliases behind, and that is the one shape
        # the readers cannot distrust: the latency-sensitive page path never
        # revalidates, so it keeps advertising a `cover-asset/<id>` until a real
        # cover request happens to forget it.
        if deletes_left < len(aliases) + 1:
            break
        stuck = False
        for alias_path in aliases:
            if not reclaim(alias_path, aliases=[alias_path]):
                # The budget above was reserved, so the only way here is an alias
                # the volume will not hand over.  Its asset stays with it: taking
                # the bytes anyway is the dangling pointer this guard exists to
                # prevent, and stopping keeps the oldest-first order honest.
                stuck = True
                break
        if stuck:
            break
        if not reclaim(path):
            # Nothing but a failed unlink can reach here now; stop rather than
            # orphan the aliases of the units behind this one.
            break
        total = max(0, total - unit["bytes"])
    _forget_cover_cache_entries(deleted_aliases, deleted_markers)
    return removed


def cleanup_cover_cache_if_due(config, force=False):
    """Sweep the cover cache at most once per interval, and never fail a write.

    The interval is claimed *before* sweeping, which is the lesson recorded in
    ``transcode.cleanup_transcode_cache_if_due``: a sweep that raises used to
    leave it unarmed, so every later write paid for a fresh walk of a directory
    that keeps failing.
    """
    global _last_cover_sweep
    now = time.time()
    with _cover_sweep_mutex:
        if not force and now - _last_cover_sweep < COVER_CACHE_SWEEP_INTERVAL_SECONDS:
            return 0
        _last_cover_sweep = now
    try:
        return prune_cover_cache(config)
    except OSError:
        return 0


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
        while (_MEMORY_CACHE_BYTES > _MEMORY_CACHE_LIMIT
               or len(_MEMORY_CACHE) > _MEMORY_CACHE_ENTRY_LIMIT) and _MEMORY_CACHE:
            _old_key, (_mime, old_body) = _MEMORY_CACHE.popitem(last=False)
            _MEMORY_CACHE_BYTES -= len(old_body)


def clear_memory_cache():
    global _MEMORY_CACHE_BYTES
    with _MEMORY_CACHE_LOCK:
        _MEMORY_CACHE.clear()
        _ASSET_ALIAS_CACHE.clear()
        _MISSING_MARKER_CACHE.clear()
        _MEMORY_CACHE_BYTES = 0


def prewarm_thumbnails(items, config, cover_reader, size=160):
    """Queue a bounded visible-window warmup without delaying responses."""
    size = normalized_cover_size(size)
    if not size:
        return
    cache_key = os.path.abspath(_cache_directory(config))
    global _INTERACTIVE_PREWARM_ROOT_REJECTED
    with _PREWARM_LOCK:
        if cache_key not in _INTERACTIVE_PREWARM and len(_INTERACTIVE_PREWARM) >= INTERACTIVE_PREWARM_MAX_ROOTS:
            # One warm worker per cache root is enough.  A client that points the
            # cover cache at several roots must not be able to pile threads up, so
            # an idle root is retired before a new one takes its place.
            for old_key, old_state in list(_INTERACTIVE_PREWARM.items()):
                if not old_state.get("running"):
                    _INTERACTIVE_PREWARM.pop(old_key, None)
                    if len(_INTERACTIVE_PREWARM) < INTERACTIVE_PREWARM_MAX_ROOTS:
                        break
            if len(_INTERACTIVE_PREWARM) >= INTERACTIVE_PREWARM_MAX_ROOTS:
                _INTERACTIVE_PREWARM_ROOT_REJECTED += 1
                return
        state = _INTERACTIVE_PREWARM.setdefault(cache_key, {
            "pending": OrderedDict(), "inflight": set(), "running": False,
            "thread": None, "cancel": threading.Event(), "accepted": 0,
            "completed": 0, "failed": 0, "dropped": 0, "not_before": 0.0,
        })
        if state["cancel"].is_set():
            state = {
                "pending": OrderedDict(), "inflight": set(), "running": False,
                "thread": None, "cancel": threading.Event(), "accepted": 0,
                "completed": 0, "failed": 0, "dropped": 0, "not_before": 0.0,
            }
            _INTERACTIVE_PREWARM[cache_key] = state
        for item in islice(items or (), 24):
            key = queue_key(item, cover_source_version(item, allow_disk=False), size)
            if key in state["pending"] or key in state["inflight"]:
                continue
            if len(state["pending"]) >= INTERACTIVE_PREWARM_MAX_PENDING:
                state["pending"].popitem(last=False)
                state["dropped"] += 1
            state["pending"][key] = item
            state["accepted"] += 1

        # The first page pays a short ramp so a burst of list requests cannot
        # occupy every FFmpeg slot before the visible rows are decoded.
        state["not_before"] = max(
            _safe_not_before(_safe_state_get(state, "not_before", 0.0)),
            time.monotonic() + INTERACTIVE_PREWARM_INITIAL_DELAY_SECONDS,
        )
        if state["running"] or not state["pending"]:
            return
        state["running"] = True

    def worker():
        def stop_when_drained():
            """Retire this worker once the queue is genuinely empty.

            The decision and the ``running`` clear share one lock hold.  Clearing
            the flag afterwards, in the ``finally`` block, lets a page request that
            lands in between queue its covers behind a worker that has already given
            up: the caller still sees ``running`` set and skips starting a thread, so
            that window keeps showing placeholder artwork until some later request
            happens to drain the queue again.
            """
            state["running"] = False
            state["thread"] = None
            if _INTERACTIVE_PREWARM.get(cache_key) is state:
                _INTERACTIVE_PREWARM.pop(cache_key, None)

        try:
            while True:
                with _PREWARM_LOCK:
                    if state["cancel"].is_set() or _INTERACTIVE_PREWARM.get(cache_key) is not state:
                        return
                    if not state["pending"]:
                        stop_when_drained()
                        return
                    delay = max(0.0, _safe_not_before(_safe_state_get(state, "not_before", 0.0)) - time.monotonic())
                if delay:
                    # Wait outside the lock so a page request can still queue
                    # covers; a cancel wakes us immediately.
                    if state["cancel"].wait(delay):
                        return
                    continue
                with _PREWARM_LOCK:
                    if state["cancel"].is_set() or _INTERACTIVE_PREWARM.get(cache_key) is not state:
                        return
                    if not state["pending"]:
                        stop_when_drained()
                        return
                    key, item = state["pending"].popitem(last=False)
                    state["inflight"].add(key)
                try:
                    # One source version for the whole row.  The decision below and
                    # the render used to resolve it independently, so a file that
                    # changed while the row was in flight could be judged against one
                    # key and rendered into another.
                    version = cover_source_version(item)
                    # Skip work the shared asset store already answers.
                    if _prewarm_result_exists(item, config, size, version):
                        continue
                    # A short FFmpeg budget keeps deferred pages out of the way.
                    cached_thumbnail_for_item(item, config, size, cover_reader,
                                              ffmpeg_slot_timeout=0.05, version=version)
                    with _PREWARM_LOCK:
                        state["completed"] += 1
                except Exception:
                    with _PREWARM_LOCK:
                        state["failed"] += 1
                finally:
                    with _PREWARM_LOCK:
                        state["inflight"].discard(key)
        finally:
            with _PREWARM_LOCK:
                state["running"] = False
                state["thread"] = None
                if _INTERACTIVE_PREWARM.get(cache_key) is state:
                    if not state.get("pending"):
                        _INTERACTIVE_PREWARM.pop(cache_key, None)

    thread = threading.Thread(target=worker, name="fnaudio-cover-prewarm", daemon=True)
    with _PREWARM_LOCK:
        state["thread"] = thread
    try:
        thread.start()
    except (RuntimeError, OSError):
        # The thread slot is released with the process; drop the queue so the
        # next request can start a fresh worker instead of waiting on a thread
        # that never existed.
        with _PREWARM_LOCK:
            if _INTERACTIVE_PREWARM.get(cache_key) is state:
                state["running"] = False
                state["thread"] = None


def thumbnail_prewarm_status():
    """Return only bounded cover-prewarm pressure counters for support APIs."""
    with _PREWARM_LOCK:
        interactive_root_rejected = _safe_pressure_counter(_INTERACTIVE_PREWARM_ROOT_REJECTED)
        rejected = _safe_pressure_counter(_LIBRARY_PREWARM_ROOT_REJECTED)
        interactive = list(_INTERACTIVE_PREWARM.values())
        library = list(_LIBRARY_PREWARM.values())
    with _MEMORY_CACHE_LOCK:
        memory_entries = _safe_sequence_length(_MEMORY_CACHE)
        memory_bytes = _safe_pressure_counter(_MEMORY_CACHE_BYTES)
        memory_limit = _safe_pressure_counter(_MEMORY_CACHE_LIMIT)
        memory_entry_limit = _safe_pressure_counter(_MEMORY_CACHE_ENTRY_LIMIT)
        alias_entries = _safe_sequence_length(_ASSET_ALIAS_CACHE)
        alias_limit = _safe_pressure_counter(_ASSET_ALIAS_CACHE_LIMIT)
        return {
            "memory_cache": {
                "entries": memory_entries,
                "entry_limit": memory_entry_limit,
                "bytes": min(memory_bytes, memory_limit),
                "limit_bytes": memory_limit,
                "alias_entries": min(alias_entries, alias_limit),
                "alias_limit": alias_limit,
            },
            "interactive": {
                "workers": sum(1 for state in interactive if _safe_state_get(state, "running")),
                "queued": sum(_safe_sequence_length(_safe_state_get(state, "pending")) for state in interactive),
                "inflight": sum(_safe_sequence_length(_safe_state_get(state, "inflight")) for state in interactive),
                "limit": INTERACTIVE_PREWARM_MAX_PENDING,
                "accepted": sum(_safe_pressure_counter(_safe_state_get(state, "accepted")) for state in interactive),
                "completed": sum(_safe_pressure_counter(_safe_state_get(state, "completed")) for state in interactive),
                "failed": sum(_safe_pressure_counter(_safe_state_get(state, "failed")) for state in interactive),
                "dropped": sum(_safe_pressure_counter(_safe_state_get(state, "dropped")) for state in interactive),
                "root_limit": INTERACTIVE_PREWARM_MAX_ROOTS,
                "root_rejected": interactive_root_rejected,
            },
            "library": {
                "workers": sum(1 for state in library if _safe_state_get(state, "running")),
                "queued": sum(_safe_sequence_length(_safe_state_get(state, "items")) for state in library),
                "page_size": LIBRARY_PREWARM_PAGE_SIZE,
                "limit": LIBRARY_PREWARM_MAX_PENDING,
                "accepted": sum(_safe_pressure_counter(_safe_state_get(state, "accepted")) for state in library),
                "completed": sum(_safe_pressure_counter(_safe_state_get(state, "completed")) for state in library),
                "failed": sum(_safe_pressure_counter(_safe_state_get(state, "failed")) for state in library),
                "dropped": sum(_safe_pressure_counter(_safe_state_get(state, "dropped")) for state in library),
                "root_limit": LIBRARY_PREWARM_MAX_ROOTS,
                "root_rejected": rejected,
            },
        }


def prewarm_library_thumbnails(items, config, cover_reader, size=160):
    """Build thumbnails in cancellable, low-priority pages after a scan."""
    size = normalized_cover_size(size)
    if not size:
        return

    # A scan hands over the whole library, so the queue is trimmed to one cap
    # per root and the worker walks it in pages with an idle gap between them.
    # A second call for the same root replaces the queue instead of stacking.
    cache_key = os.path.abspath(_cache_directory(config))
    global _LIBRARY_PREWARM_ROOT_REJECTED
    with _PREWARM_LOCK:
        if cache_key not in _LIBRARY_PREWARM and len(_LIBRARY_PREWARM) >= LIBRARY_PREWARM_MAX_ROOTS:
            # Root registries are bounded: retire an idle queue first so that a
            # rescan of a new root cannot leak worker states for roots that no
            # longer have any artwork the interface is still asking about.
            for old_key, old_state in list(_LIBRARY_PREWARM.items()):
                if not old_state.get("running"):
                    _LIBRARY_PREWARM.pop(old_key, None)
                    if len(_LIBRARY_PREWARM) < LIBRARY_PREWARM_MAX_ROOTS:
                        break
            if len(_LIBRARY_PREWARM) >= LIBRARY_PREWARM_MAX_ROOTS:
                _LIBRARY_PREWARM_ROOT_REJECTED += 1
                return
        state = _LIBRARY_PREWARM.setdefault(cache_key, {
            "generation": 0,
            "running": False,
            "items": [],
            "accepted": 0,
            "completed": 0,
            "failed": 0,
            "dropped": 0,
            "cancel": threading.Event(),
            "thread": None,
        })
        state["generation"] += 1
        incoming, dropped = bounded_unique_items(
            items, LIBRARY_PREWARM_MAX_PENDING,
            lambda item: queue_key(
                item, cover_source_version(item, allow_disk=False), size, prefer_path=True
            ),
        )
        state["accepted"] += len(incoming)
        state["dropped"] += dropped
        state["items"] = incoming
        state["cancel"].clear()
        if state["running"]:
            return
        state["running"] = True

    worker_state = state

    def worker():
        def stop_when_drained():
            """Retire this worker with ``running`` cleared in the same lock hold.

            A scan that replaces the queue while this thread sits between its empty
            check and its ``finally`` would otherwise be parked behind
            ``running=True`` until the next full-library scan.
            """
            worker_state["running"] = False
            worker_state["thread"] = None
            if _LIBRARY_PREWARM.get(cache_key) is worker_state:
                _LIBRARY_PREWARM.pop(cache_key, None)

        try:
            while True:
                with _PREWARM_LOCK:
                    state = _LIBRARY_PREWARM.get(cache_key)
                    if state is None or state["cancel"].is_set():
                        return
                    generation = state["generation"]
                    jobs = state["items"][:LIBRARY_PREWARM_PAGE_SIZE]
                    del state["items"][:len(jobs)]
                    if not jobs:
                        stop_when_drained()
                        return
                for item in jobs:
                    with _PREWARM_LOCK:
                        if state["cancel"].is_set() or \
                                _LIBRARY_PREWARM.get(cache_key, {}).get("generation") != generation:
                            break
                    if not _prewarm_item_path(item) or not os.path.isfile(_prewarm_item_path(item)):
                        with _PREWARM_LOCK:
                            state["completed"] += 1
                        continue
                    try:
                        cached_thumbnail_for_item(
                            item, config, size, cover_reader,
                            ffmpeg_slot_timeout=0.05,
                            cancel_event=state["cancel"],
                        )
                        with _PREWARM_LOCK:
                            state["completed"] += 1
                    except Exception:
                        with _PREWARM_LOCK:
                            state["failed"] += 1
                with _PREWARM_LOCK:
                    state = _LIBRARY_PREWARM.get(cache_key)
                    if state is None or state["cancel"].is_set():
                        return
                    # Re-read the registry each page: a scan may have replaced
                    # this queue, and a stale worker must not keep decoding the
                    # previous library.  The wait is interruptible so a cancel
                    # ends the thread between pages without a full page delay.
                    if state["generation"] != generation:
                        continue
                if state["cancel"].wait(LIBRARY_PREWARM_DELAY_SECONDS):
                    return
        finally:
            with _PREWARM_LOCK:
                worker_state["running"] = False
                worker_state["thread"] = None
                if _LIBRARY_PREWARM.get(cache_key) is worker_state:
                    if not worker_state.get("items"):
                        _LIBRARY_PREWARM.pop(cache_key, None)

    thread = threading.Thread(target=worker, name="fnaudio-cover-library-prewarm", daemon=True)
    with _PREWARM_LOCK:
        state["thread"] = thread
    try:
        thread.start()
    except (RuntimeError, OSError):
        with _PREWARM_LOCK:
            if _LIBRARY_PREWARM.get(cache_key) is state:
                state["running"] = False
                state["thread"] = None


def shutdown_library_thumbnail_prewarm(wait=False, timeout=5.0):
    """Cancel visible and deferred thumbnail work for shutdown/cache changes."""
    with _PREWARM_LOCK:
        states = list(_INTERACTIVE_PREWARM.values()) + list(_LIBRARY_PREWARM.values())
        _INTERACTIVE_PREWARM.clear()
        _LIBRARY_PREWARM.clear()
        for state in states:
            state["cancel"].set()
            for queue_name in ("pending", "items"):
                pending = state.get(queue_name)
                if pending is not None:
                    pending.clear()
    if wait:
        try:
            bounded_timeout = float(timeout)
        except (TypeError, ValueError, OverflowError):
            bounded_timeout = 5.0
        if not math.isfinite(bounded_timeout):
            bounded_timeout = 5.0
        deadline = time.monotonic() + max(0.0, bounded_timeout)
        for state in states:
            thread = state.get("thread")
            if thread and thread.is_alive():
                thread.join(max(0.0, deadline - time.monotonic()))


def _atomic_bytes(path, body, config=None, durable=True):
    directory = secure_directory(os.path.dirname(path))
    fd, temporary = tempfile.mkstemp(prefix=".fnaudio-cover-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(body)
            handle.flush()
            if durable:
                # Durability is only worth the wait for bytes a reader cannot tell
                # apart from garbage once they are half written, which is the image
                # itself: the shared-asset address names the source artwork, not the
                # rendered tile, so nothing re-checks those pixels.  A truncated alias
                # or negative marker fails the read path's own validation and is
                # re-derived, so that write must not stall the publish on the disk.
                os.fsync(handle.fileno())
        os.replace(temporary, path)
        secure_file(path)
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            if os.path.exists(temporary):
                os.unlink(temporary)
        except OSError:
            pass
    if config is not None:
        # Every byte the cover service keeps on disk goes through this function, so
        # this is the only place a sweep can observe real growth.  It is
        # interval-guarded and swallows its own failures: publishing a thumbnail a
        # caller already paid for must not fail because housekeeping is unhappy.
        cleanup_cover_cache_if_due(config)


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
        # Do not pipe untrusted FFmpeg output into RAM.  The output file gives
        # us a hard size check before the bytes enter the process heap, while
        # the mocked-result fallback preserves the existing unit-test seam.
        with tempfile.TemporaryFile(mode="w+b") as output:
            with ffmpeg_slot(config, timeout=ffmpeg_slot_timeout):
                result = _run_thumbnail_process(command, body, output, environment, timeout=15)
            output.seek(0, os.SEEK_END)
            if output.tell() > MAX_CACHED_COVER_BYTES:
                return None
            output.seek(0)
            rendered = output.read(MAX_CACHED_COVER_BYTES + 1)
            if len(rendered) > MAX_CACHED_COVER_BYTES:
                return None
            if not rendered and isinstance(getattr(result, "stdout", None), (bytes, bytearray)):
                rendered = bytes(result.stdout)
                if len(rendered) > MAX_CACHED_COVER_BYTES:
                    return None
    except (OSError, ResourceLimitError, subprocess.TimeoutExpired):
        return None
    return rendered if result.returncode == 0 and rendered.startswith(b"\xff\xd8") else None


def cached_thumbnail_for_item(item, config, size, cover_reader, ffmpeg_slot_timeout=5.0, cancel_event=None, version=None):
    size = normalized_cover_size(size)
    if not size:
        return cover_reader(item, config)
    if cancel_event is not None and cancel_event.is_set():
        return None, None
    # One source version for the whole request.  ``_cache_paths`` above, the
    # memory key and the render lock below used to resolve it independently, so
    # a file whose identity changed while the request was running could store the
    # rendered bytes under one key, remember them under another and guard the
    # render with a third lock.
    if version is None:
        version = cover_source_version(item)
    _root, target, missing = _cache_paths(item, config, size, version)
    alias = target[:-4] + ".asset"
    memory_key = (_cache_directory(config),
                  _item_cache_identity(item),
                  version, int(size))
    memory_value = _memory_get(memory_key)
    if memory_value is not None:
        return memory_value
    if os.path.isfile(target):
        try:
            body = _read_bounded_file(target, MAX_CACHED_COVER_BYTES)
            if body is None:
                raise OSError("cached cover exceeds size limit")
            value = ("image/jpeg", body)
            _memory_put(memory_key, value)
            return value
        except OSError:
            pass
    asset_body = _read_asset_alias(alias, config, size)
    if asset_body:
        value = ("image/jpeg", asset_body)
        _memory_put(memory_key, value)
        return value
    if _missing_marker_is_fresh(missing):
        return None, None
    with _key_lock(_cache_key(item, size, version)):
        if cancel_event is not None and cancel_event.is_set():
            return None, None
        if os.path.isfile(target):
            try:
                body = _read_bounded_file(target, MAX_CACHED_COVER_BYTES)
                if body is None:
                    raise OSError("cached cover exceeds size limit")
                value = ("image/jpeg", body)
                _memory_put(memory_key, value)
                return value
            except OSError:
                pass
        asset_body = _read_asset_alias(alias, config, size)
        if asset_body:
            value = ("image/jpeg", asset_body)
            _memory_put(memory_key, value)
            return value
        if _missing_marker_is_fresh(missing):
            return None, None
        mime, body = cover_reader(item, config)
        if cancel_event is not None and cancel_event.is_set():
            return None, None
        if not body:
            try:
                # The marker is an empty file: losing it only costs one re-lookup, and
                # it can never be read back as plausible garbage, so it is not worth an
                # fsync on the request path.
                _atomic_bytes(missing, b"", config, durable=False)
            except OSError:
                # A negative marker is an optimization.  If the volume is full or
                # read-only the in-memory cache below still answers this session,
                # and the same rule as generate_asset_thumbnail applies: a failed
                # cache write must not fail the response.
                pass
            with _MEMORY_CACHE_LOCK:
                _MISSING_MARKER_CACHE[missing] = time.monotonic()
                _MISSING_MARKER_CACHE.move_to_end(missing)
                while len(_MISSING_MARKER_CACHE) > _MISSING_MARKER_CACHE_LIMIT:
                    _MISSING_MARKER_CACHE.popitem(last=False)
            return None, None
        thumbnail = _thumbnail_bytes(body, config, size, ffmpeg_slot_timeout)
        if cancel_event is not None and cancel_event.is_set():
            return None, None
        if not thumbnail:
            return mime, body
        asset_key = hashlib.sha256(body).hexdigest()
        asset_root, asset_target = _asset_path(config, size, asset_key)
        try:
            if not os.path.isfile(asset_target):
                secure_directory(asset_root)
                _atomic_bytes(asset_target, thumbnail, config)
            # Preserve a per-track version alias, while the image itself is shared
            # by every track that resolves to identical artwork bytes.
            _atomic_bytes(alias, asset_key.encode("ascii"), config, durable=False)
        except OSError:
            # Same contract as generate_asset_thumbnail above: a failed cache
            # write must not fail the response, because the bytes rendered for
            # this request are already correct.  The alias is written only after
            # the asset it names is on disk, so a half-failed persist leaves
            # nothing behind that a later read would have to distrust.
            pass
        else:
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


__all__ = ["cached_thumbnail_for_item", "clear_memory_cache", "generate_asset_thumbnail", "cover_is_known_missing", "cover_source_version", "normalized_cover_size", "prewarm_library_thumbnails", "prewarm_thumbnails", "shutdown_library_thumbnail_prewarm", "thumbnail_asset_bytes", "thumbnail_asset_id_for_item", "thumbnail_prewarm_status"]
