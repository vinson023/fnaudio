from __future__ import annotations

import base64
import ctypes
import errno
import hashlib
import heapq
import json
import math
import os
import random
import re
import shutil
import sqlite3
import subprocess
import struct
import threading
import time
import tempfile
from contextlib import contextmanager
from typing import Any, Dict

from transcode import find_ffmpeg
from resource_limits import bounded_int
from file_permissions import atomic_write_json, secure_directory, secure_directory_on_drift, secure_file, secure_sqlite_files
from config import DEFAULT_PORT
from library_connection_pool import LibraryConnectionPool
from library_query_cache import LibraryQueryCache
from library_query_cache_key import MAX_CACHE_KEY_VALUES
from library_cache_failure_policy import increment_failure, project_failures
from library_query_spec import LIBRARY_ITEM_ID_LIMIT, first_param, normalize_library_item_id, normalize_library_item_sequence, parse_library_folder_query, parse_library_group_query, parse_library_page_query, parse_library_root_search
from library_pagination import counted_page_rows, paged_rows_with_total
from library_track_filter_policy import build_track_filters
from library_item_hydration import hydrate_items_by_ids
from library_group_presentation import project_folder_rows, project_group_rows
from library_item_lookup import lookup_memory_item, lookup_sqlite_item
from library_item_location import resolve_item_location
from library_root_summary import decode_root_summary
from library_root_query_policy import configured_root_filter
from library_root_presentation import project_root_rows
from library_paths import (
    apply_library_paths,
    canonical_library_path,
    display_library_path,
    is_allowed_library_path,
    library_root_label,
    library_root_labels,
    merge_library_paths,
    MAX_LIBRARY_PATH_TEXT,
    normalize_library_paths,
    relative_folder_for_path,
)
from library_cache_payload import project_legacy_cache
from scan_control import ScanCancelled, ScanDeadline, ScanTimedOut, check_scan_deadline as _check_scan_deadline
from scan_reuse_policy import can_reuse_cached_item
from library_index_handover import find_reuse_items as find_legacy_reuse_items
from scan_error_policy import append_scan_error, scan_error_text, snapshot_scan_errors
from metadata_text import artist_title_from_filename, clean_tag, cue_time_seconds, cue_value, display_name, normalize_probe_tags, parse_track_number


def _bounded_wait_timeout(value, default):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(0.0, number) if math.isfinite(number) else default
from native_audio_info import read_native_audio_info
from probe_metadata import normalize_probe_payload
from cue_parser import parse_cue_structure
from cue_reader import read_cue_lines as _read_cue_lines
from id3_parser import decode_id3_text, id3_frame_size
from library_status_presentation import status_message
from library_rows import MAX_ITEM_JSON_BYTES, decode_item_row, decode_item_rows
from library_write import (
    NULLABLE_LABEL_COLUMNS,
    collapse_missing_labels,
    iter_track_persistence_batches,
    normalize_scan_items,
    prepare_track_persistence,
    root_index_summary,
    scan_text,
)
from library_count_policy import (
    GROUP_COUNT_KEYS,
    browse_page_total,
    group_count_key,
    project_saved_count,
    saved_count_key,
)
from library_refresh_policy import cancel_refresh, enqueue_refresh, take_refresh
from library_search_policy import track_search_condition
from library_search_index_policy import cache_token, search_index_status, uses_fts
from library_group_policy import group_match_condition as build_group_match_condition
from library_memory_query import memory_field
from library_memory_page import build_memory_library_page
from library_random_sample import MAX_RANDOM_ROWID_CANDIDATES, random_rowid_candidates
from library_cursor_policy import cursor_group_tail_where, cursor_next_group_where, cursor_page, decode_track_cursor
from library_browse_cursor_policy import (
    browse_cursor_group_tail_where,
    browse_cursor_next_group_where,
    browse_cursor_page,
    decode_browse_cursor,
    encode_browse_cursor,
)
from library_page_result_policy import decode_track_cursor_page_rows as _decode_track_cursor_page_rows
from library_page_result_policy import track_page_result as _track_page_result
from library_page_result_policy import track_page_select as _track_page_select
from library_metadata_presentation import library_metadata
from library_scan_presentation import build_audio_item
from library_scan_results import build_previous_item_index, digest_signature_parts, finalize_scan_results, partition_previous_items, sort_scan_items
from library_scan_file_policy import classify_filename
from summary_values import strict_bool
from library_browse_rows import materialize_browse_rows
from cue_item_presentation import build_cue_item
from cue_numeric_policy import cue_segment_end
from scan_numeric_policy import safe_counter, safe_float, safe_int
from metadata_tag_resolution import resolve_metadata_tags
from vorbis_reader import read_vorbis_comments as _read_vorbis_comments
from cover_readers import read_ape_cover, read_flac_cover
from cover_dispatch import cover_kind
from id3_container import id3_payload, id3_tag, read_id3, read_id3_cover, read_id3v1
from sidecar_cover import read_sidecar_cover
from ffmpeg_cover import MAX_COVER_FILE_BYTES, extract_cover as _extract_ffmpeg_cover
from probe_runner import read_audio_info as _read_audio_info
from probe_runner import read_probe_metadata as _read_probe_metadata

SUPPORTED = {
    ".flac": "audio/flac", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac",
    ".ogg": "audio/ogg", ".opus": "audio/ogg", ".wav": "audio/wav", ".aiff": "audio/aiff",
    ".aif": "audio/aiff", ".wma": "audio/x-ms-wma", ".ape": "audio/ape", ".dsf": "audio/x-dsf", ".dff": "audio/x-dff", ".cue": "application/x-cue",
}
METADATA_VERSION = 16
MAX_PROBE_OUTPUT_BYTES = 2 * 1024 * 1024
UNCLASSIFIED = "未分类"
GROUP_LABEL_VERSION = "3"
MAX_LIBRARY_SIGNATURE_PARTS = 200_000
MAX_LIBRARY_SIGNATURE_BYTES = 8 * 1024 * 1024
SEARCH_INDEX_VERSION = "1"
MUSIC_CACHE = {"stamp": 0, "items": []}
FS_CACHE = {"signature": ""}
# SQLite is deliberately kept as the source of truth.  This small process
# cache only avoids repeating identical count + page queries while a user is
# clicking between views or more than one client is open.  It is invalidated
# synchronously after every index write, so it cannot outlive a scan or a
# metadata update.
LIBRARY_QUERY_CACHE_TTL_SECONDS = 20.0
LIBRARY_QUERY_CACHE_LIMIT = 160
LIBRARY_QUERY_CACHE = LibraryQueryCache(LIBRARY_QUERY_CACHE_TTL_SECONDS, LIBRARY_QUERY_CACHE_LIMIT)
# Status polling only needs the persisted count/signature summary. Keep this
# tiny cache separate from dynamic scan state so frequent clients do not
# reopen SQLite for identical summaries, while writes invalidate it eagerly.
LIBRARY_SUMMARY_CACHE_TTL_SECONDS = 2.0
LIBRARY_SUMMARY_CACHE_LIMIT = 32
LIBRARY_SUMMARY_CACHE = {}
LIBRARY_SUMMARY_CACHE_LOCK = threading.RLock()
# A burst of status polls can otherwise all miss the tiny TTL cache before
# the first SQLite summary has been stored.  Keep only active leaders here;
# followers wait for the leader's cache write and never retain a per-client
# lock after the request has finished.
LIBRARY_SUMMARY_INFLIGHT_LIMIT = 32
LIBRARY_SUMMARY_INFLIGHT = {}
# Cache restore/write failures are intentionally counted instead of being
# silently swallowed.  The counters are operational metadata only; paths and
# exception text are never exposed through the public status payload.
LIBRARY_CACHE_FAILURES = {"load": 0, "save": 0}
LIBRARY_CACHE_FAILURES_LOCK = threading.Lock()
# Map the stable cache path to the filesystem identity of the SQLite main
# file.  A path-only set is unsafe when a cleanup tool deletes and recreates
# the index while fnAudio is still running.
LIBRARY_SCHEMA_READY = {}
LIBRARY_SCHEMA_READY_LOCK = threading.RLock()
LIBRARY_SCHEMA_READY_LIMIT = 32
LIBRARY_SEARCH_INDEX_MODE = {}
LIBRARY_SEARCH_INDEX_LOCK = threading.RLock()
LIBRARY_SEARCH_INDEX_MODE_LIMIT = 32
LIBRARY_CHANGE_MONITOR = None
SCAN_STATE = {
    "running": False,
    "queued": False,
    "queued_force": False,
    "worker_active": False,
    "result": "idle",
    "cancelled": False,
    "timed_out": False,
    "deadline": 0,
    "last_error": "",
    "last_scan": 0,
    "current": "",
    "phase": "",
    "scanned": 0,
    "found": 0,
    "errors": [],
}
SCAN_LOCK = threading.Lock()
SCAN_REQUEST_LOCK = threading.Lock()
SCAN_CANCEL_EVENT = threading.Event()
SCAN_WORKER_THREAD = None
SCAN_REFRESH_GENERATION = 0
LIBRARY_WATCH_STOP_EVENT = threading.Event()
LIBRARY_WATCH_THREAD = None
LIBRARY_WATCH_CURRENT_STOP_EVENT = None
LIBRARY_WATCH_LOCK = threading.RLock()
LIBRARY_JSON_CACHE_LIMIT = 5000
# The legacy JSON cache is only a compatibility fallback; SQLite is the
# authoritative index.  Keep its recovery path bounded as well so a damaged
# or unexpectedly large cache cannot be materialized wholesale.
LIBRARY_JSON_CACHE_MAX_BYTES = 32 * 1024 * 1024
LIBRARY_WRITE_BATCH_SIZE = 500
MAX_LIBRARY_INOTIFY_WATCHES = 4096


def _bounded_database_state_put(entries, database, value, limit):
    """Update a per-database process map without retaining retired roots."""
    entries.pop(database, None)
    while len(entries) >= limit:
        entries.pop(next(iter(entries)), None)
    entries[database] = value


class LibraryChangeMonitor:
    """Use Linux inotify to avoid polling every audio file when nothing changed."""

    IN_ATTRIB = 0x00000004
    IN_CLOSE_WRITE = 0x00000008
    IN_MOVED_FROM = 0x00000040
    IN_MOVED_TO = 0x00000080
    IN_CREATE = 0x00000100
    IN_DELETE = 0x00000200
    IN_DELETE_SELF = 0x00000400
    IN_MOVE_SELF = 0x00000800
    IN_Q_OVERFLOW = 0x00004000
    IN_IGNORED = 0x00008000
    IN_ISDIR = 0x40000000
    WATCH_MASK = (
        IN_ATTRIB | IN_CLOSE_WRITE | IN_MOVED_FROM | IN_MOVED_TO |
        IN_CREATE | IN_DELETE | IN_DELETE_SELF | IN_MOVE_SELF
    )
    EVENT_HEADER = struct.Struct("iIII")

    def __init__(self, roots):
        self.roots = tuple(os.path.abspath(os.path.expanduser(root)) for root in roots)
        self.available = False
        self._dirty = True
        self._overflowed = False
        self._generation = 0
        self._fd = -1
        self._libc = None
        self._watches = {}
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        with self._lifecycle_lock:
            if os.name != "posix" or not self.roots:
                return False
            existing = self._thread
            if existing is not None and existing.is_alive():
                return bool(self.available)
            # Event instances are one-shot. A monitor can be restarted after a
            # configuration reload, so a previous stop must not poison the new
            # watcher thread.
            self._stop.clear()
            try:
                libc = ctypes.CDLL(None, use_errno=True)
                libc.inotify_init1.argtypes = [ctypes.c_int]
                libc.inotify_init1.restype = ctypes.c_int
                libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
                libc.inotify_add_watch.restype = ctypes.c_int
                flags = int(getattr(os, "O_NONBLOCK", 0)) | int(getattr(os, "O_CLOEXEC", 0))
                fd = libc.inotify_init1(flags)
                if fd < 0:
                    raise OSError(ctypes.get_errno(), "inotify_init1 failed")
                self._libc = libc
                self._fd = fd
                for root in self.roots:
                    if os.path.isdir(root):
                        self._add_tree(root)
                if not self._watches:
                    raise OSError("no readable library directories could be watched")
                self.available = True
                thread = threading.Thread(target=self._run, name="fnaudio-library-inotify", daemon=True)
                # Publish before starting so a concurrent caller cannot create
                # a second inotify fd in the narrow Thread.start() window.
                self._thread = thread
                thread.start()
                return True
            except (AttributeError, OSError, RuntimeError):
                self.stop()
                return False

    def stop(self):
        with self._lifecycle_lock:
            self._stop.set()
            thread = self._thread
            self._thread = None
            fd = self._fd
            self._fd = -1
            self.available = False
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
            with self._lock:
                self._watches.clear()
            if thread is not None and thread is not threading.current_thread():
                try:
                    thread.join(timeout=1.0)
                except RuntimeError:
                    # A failed Thread.start() leaves the pre-registered
                    # lifecycle handle unstarted; there is nothing to join.
                    pass

    def needs_scan(self):
        with self._lock:
            return not self.available or self._dirty or self._overflowed

    def generation(self):
        with self._lock:
            return self._generation

    def mark_clean(self, generation):
        with self._lock:
            if self.available and self._generation == generation:
                self._dirty = False
                self._overflowed = False
                return True
            return False

    def status(self):
        with self._lock:
            return {
                "mode": "inotify" if self.available else "polling",
                "watched_directories": len(self._watches),
                "dirty": bool(self._dirty),
                "overflowed": bool(self._overflowed),
            }

    def _watch_path(self, path):
        if self._fd < 0 or self._libc is None:
            return
        with self._lock:
            if len(self._watches) >= MAX_LIBRARY_INOTIFY_WATCHES:
                raise OSError(errno.ENOSPC, "library inotify watch limit reached", path)
        wd = self._libc.inotify_add_watch(self._fd, os.fsencode(path), self.WATCH_MASK)
        if wd < 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), path)
        with self._lock:
            self._watches[wd] = path

    def _add_tree(self, root):
        for base, directories, _ in os.walk(root):
            self._watch_path(base)
            directories[:] = [name for name in directories if not os.path.islink(os.path.join(base, name))]

    def _mark_dirty(self, overflowed=False):
        with self._lock:
            self._generation += 1
            self._dirty = True
            self._overflowed = self._overflowed or overflowed

    def _handle_events(self, payload):
        offset = 0
        while offset + self.EVENT_HEADER.size <= len(payload):
            wd, mask, _, name_length = self.EVENT_HEADER.unpack_from(payload, offset)
            offset += self.EVENT_HEADER.size
            raw_name = payload[offset:offset + name_length]
            offset += name_length
            name = os.fsdecode(raw_name.split(b"\0", 1)[0]) if raw_name else ""
            if mask & self.IN_Q_OVERFLOW:
                self._mark_dirty(True)
                continue
            with self._lock:
                base = self._watches.get(wd, "")
                if mask & self.IN_IGNORED:
                    self._watches.pop(wd, None)
            if mask & self.IN_IGNORED:
                continue
            path = os.path.join(base, name) if base and name else base
            if mask & self.IN_ISDIR:
                self._mark_dirty()
                if mask & (self.IN_CREATE | self.IN_MOVED_TO) and path:
                    try:
                        self._add_tree(path)
                    except OSError:
                        self._mark_dirty(True)
                        # A directory tree beyond the local watch ceiling is
                        # no longer fully observable. Fall back to the
                        # periodic signature check instead of clearing this
                        # dirty bit after one scan and silently missing later
                        # changes below the unwatchable subtree.
                        with self._lock:
                            self.available = False
                continue
            if not name or os.path.splitext(name)[1].lower() in SUPPORTED:
                self._mark_dirty()

    def _run(self):
        # Keep this worker on the fd generation it was started with.  Reading
        # the mutable instance field here can otherwise make a fast stop/start
        # cycle consume events from the replacement monitor.
        fd = self._fd
        while not self._stop.wait(0.25):
            if self._fd != fd or self._stop.is_set():
                return
            try:
                payload = os.read(fd, 256 * 1024)
            except BlockingIOError:
                continue
            except OSError:
                if not self._stop.is_set():
                    self._mark_dirty(True)
                    self.available = False
                return
            if payload:
                self._handle_events(payload)


def check_scan_deadline(deadline=None):
    return _check_scan_deadline(deadline, SCAN_CANCEL_EVENT)


def record_scan_error(path, message):
    SCAN_STATE["errors"] = append_scan_error(SCAN_STATE.setdefault("errors", []), path, message)


def read_m4a_cover(path, config=None):
    cover = read_mp4_covr_cover(path)
    if cover[1]:
        return cover
    return _extract_ffmpeg_cover(path, config, find_ffmpeg, subprocess.run)

def read_wav_cover(path, config=None):
    """Extract an embedded WAV artwork stream when the muxer stores one."""
    mime, body = read_id3_cover(path)
    if body:
        return mime, body
    # WAV artwork is not standardized across muxers. FFmpeg understands the
    # common ID3-in-RIFF representation, so use the same bounded extraction
    # path as M4A when the native RIFF scanner has no result.
    return _extract_ffmpeg_cover(path, config, find_ffmpeg, subprocess.run)

def read_mp4_covr_cover(path):
    """Read JPEG/PNG artwork from the MP4/M4A ilst/covr atom."""
    containers = {b"moov", b"udta", b"meta", b"ilst", b"covr"}
    max_depth = 32
    oversized_covr = False

    def image_from_bytes(data):
        if data.startswith(b"\xff\xd8\xff"):
            end = data.find(b"\xff\xd9", 3)
            return "image/jpeg", data[:end + 2] if end >= 0 else data
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            end = data.find(b"IEND")
            return "image/png", data[:end + 8] if end >= 0 else data
        if data.startswith((b"GIF87a", b"GIF89a")):
            end = data.rfind(b"\x3b")
            return "image/gif", data[:end + 1] if end >= 0 else data
        return None, None

    def scan_covr_payload(fh, start, limit):
        fh.seek(start)
        data = fh.read(max(0, min(limit - start, 8 * 1024 * 1024)))
        covr_at = data.find(b"covr")
        if covr_at < 0:
            return None, None
        window = data[covr_at:covr_at + 4 * 1024 * 1024]
        markers = [
            (b"\xff\xd8\xff", None),
            (b"\x89PNG\r\n\x1a\n", None),
            (b"GIF87a", None),
            (b"GIF89a", None),
        ]
        positions = [pos for marker, _ in markers for pos in [window.find(marker)] if pos >= 0]
        if not positions:
            return None, None
        image_start = min(positions)
        image = window[image_start:]
        mime, body = image_from_bytes(image)
        return mime, body

    try:
        with open(path, "rb") as fh:
            end = os.fstat(fh.fileno()).st_size

            def walk(start, limit, depth=0):
                nonlocal oversized_covr
                if depth > max_depth:
                    return None, None
                position = start
                while position + 8 <= limit:
                    fh.seek(position)
                    header = fh.read(8)
                    if len(header) < 8:
                        break
                    size = int.from_bytes(header[:4], "big")
                    kind = header[4:8]
                    header_size = 8
                    if size == 1:
                        size = int.from_bytes(fh.read(8), "big")
                        header_size = 16
                    elif size == 0:
                        size = limit - position
                    if size < header_size or position + size > limit:
                        break
                    payload = position + header_size
                    payload_end = position + size
                    if kind == b"data" and payload + 16 <= payload_end:
                        if payload_end - payload - 8 > MAX_COVER_FILE_BYTES:
                            oversized_covr = True
                            return None, None
                        fh.seek(payload + 8)
                        body = fh.read(MAX_COVER_FILE_BYTES + 1)
                        mime, image = image_from_bytes(body)
                        if image:
                            return mime, image
                    elif kind in containers:
                        child_start = payload + 4 if kind == b"meta" else payload
                        result = walk(child_start, payload_end, depth + 1)
                        if result[1]:
                            return result
                    position += size
                return None, None

            result = walk(0, end)
            if result[1]:
                return result
            if oversized_covr:
                return None, None
            return scan_covr_payload(fh, 0, end)
    except (OSError, ValueError):
        return None, None

def read_cover(path, config=None):
    kind = cover_kind(path)
    if kind == "id3":
        return read_id3_cover(path)
    if kind == "ape":
        return read_ape_cover(path)
    if kind == "wav":
        return read_wav_cover(path, config)
    if kind == "flac":
        return read_flac_cover(path)
    if kind == "mp4":
        return read_m4a_cover(path, config)
    return None, None

def read_cover_for_item(item, config=None):
    mime, body = read_cover(item["path"], config)
    if body:
        return mime, body
    return read_sidecar_cover(item.get("cue_path"), item.get("path"))

def read_vorbis_comments(path):
    return _read_vorbis_comments(path)

def read_probe_metadata(path, config=None):
    return _read_probe_metadata(
        path,
        config,
        ffprobe_resolver=find_ffprobe,
        native_reader=read_native_audio_info,
        payload_normalizer=normalize_probe_payload,
    )


def read_probe_tags(path, config=None):
    tags, _ = read_probe_metadata(path, config)
    return tags

def read_metadata(path, root, config=None, probe_tags=None):
    # ffprobe already provides the canonical values for most files. Avoid a
    # second full-file ID3/Vorbis scan when all fields needed by the library
    # are present; retain the native fallback for partial or probe-less tags.
    tags = resolve_metadata_tags(
        path,
        probe_tags,
        lambda value: read_probe_tags(value, config or {}),
        read_id3,
        read_vorbis_comments,
    )
    folder = relative_folder_for_path(path, root)
    root_label = library_root_label(root, config or {})
    return library_metadata(path, tags, folder, root_label, UNCLASSIFIED)

def read_cue_lines(cue_path):
    return _read_cue_lines(cue_path)

def parse_cue_tracks(cue_path, root, config=None, deadline=None):
    if not _path_under(cue_path, root):
        return []
    text = read_cue_lines(cue_path)
    if not text:
        return []
    # The CUE file can disappear between the bounded read above and track
    # construction (for example while a library is being reorganized). Read
    # its identity once and let the whole CUE skip cleanly if it is gone.
    try:
        cue_stat = os.stat(cue_path)
    except OSError:
        return []
    parsed = parse_cue_structure(text, os.path.splitext(os.path.basename(cue_path))[0])
    album = parsed["album"]
    album_artist = parsed["album_artist"]
    tracks = parsed["tracks"]
    items = []
    cue_dir = os.path.dirname(cue_path)
    for track in tracks:
        check_scan_deadline(deadline)
        audio_path = os.path.abspath(os.path.join(cue_dir, track.get("file") or ""))
        ext = os.path.splitext(audio_path)[1].lower()
        if (
            ext not in SUPPORTED
            or ext == ".cue"
            or not os.path.isfile(audio_path)
            or not _path_under(audio_path, root)
        ):
            continue
        try:
            stat = os.stat(audio_path)
        except OSError:
            continue
        item_id = hashlib.sha1((cue_path + ":" + str(track.get("track_no"))).encode("utf-8", "ignore")).hexdigest()[:16]
        probe_tags, audio_info = read_probe_metadata(audio_path, config or {})
        metadata = read_metadata(audio_path, root, config or {}, probe_tags)
        metadata.update({"title": track.get("title") or metadata.get("title"), "artist": track.get("artist") or album_artist or metadata.get("artist"), "album": album or metadata.get("album")})
        metadata["track_no"] = safe_int(track.get("track_no"))
        metadata["metadata_source"] = {"title": "cue", "artist": "cue", "album": "cue"}
        metadata["folder"] = relative_folder_for_path(cue_path, root)
        cue_start = safe_float(track.get("start"))
        # The parser answers the boundary in three states and only a final track may
        # borrow the duration of its source file: a positive value is the next track
        # on that file, 0.0 is the end of the file, and None means the boundary is
        # unknown.  Folding those together used to store a full-file cue_end for a
        # sheet that says nothing about where the segment stops.
        cue_end = cue_segment_end(track.get("end"), safe_float(audio_info.get("duration")))
        items.append(build_cue_item(
            item_id, metadata, ext, SUPPORTED[ext], ext in (".dsf", ".dff"),
            stat.st_size, audio_info, audio_path, cue_path, True, cue_start,
            cue_end, time.time(), cue_stat.st_mtime,
            cue_stat.st_mtime_ns, METADATA_VERSION,
        ))
    return items

def scan_library(root, previous_items=None, config=None, deadline=None, found_offset=0, sink=None):
    # A caller that passes a sink keeps the tracks this root has already read
    # even when the walk is cut short by the deadline, so an interrupted scan
    # is able to publish what it found instead of returning nothing at all.
    items = [] if sink is None else sink
    signature_parts = []
    scan_started = time.time()
    previous = build_previous_item_index(previous_items)
    root = canonical_library_path(root)
    if not is_allowed_library_path(root) or not os.path.isdir(root):
        return items, ""
    cue_audio_paths = set()
    SCAN_STATE["phase"] = "扫描 CUE"
    for base, directories, files in os.walk(root):
        directories[:] = [name for name in directories if name != "fnaudio-transcode"]
        check_scan_deadline(deadline)
        SCAN_STATE["current"] = base
        for filename in files:
            check_scan_deadline(deadline)
            if classify_filename(filename, SUPPORTED) != "cue":
                continue
            full = os.path.join(base, filename)
            if not _path_under(full, root):
                record_scan_error(full, "CUE path escapes the configured library root")
                continue
            cue_items = parse_cue_tracks(full, root, config or {}, deadline)
            items.extend(cue_items)
            cue_audio_paths.update(os.path.abspath(item.get("path", "")) for item in cue_items if item.get("path"))
            SCAN_STATE["found"] = found_offset + len(items)
            try:
                stat = os.stat(full)
                signature_parts.append("%s:%s:%s" % (full, stat.st_mtime_ns, stat.st_size))
            except OSError:
                record_scan_error(full, "无法读取 CUE 文件状态")
                pass
            for item in cue_items:
                audio_path = item.get("path")
                if not audio_path:
                    continue
                try:
                    stat = os.stat(audio_path)
                    signature_parts.append("%s:%s:%s" % (audio_path, stat.st_mtime_ns, stat.st_size))
                except OSError:
                    record_scan_error(audio_path, "无法读取 CUE 音频文件状态")
                    pass
        SCAN_STATE["phase"] = "扫描音频文件"
        for filename in files:
            check_scan_deadline(deadline)
            SCAN_STATE["scanned"] += 1
            classification = classify_filename(filename, SUPPORTED)
            if classification != "audio":
                continue
            ext = os.path.splitext(filename)[1].lower()
            full = os.path.join(base, filename)
            if ext == ".cue":
                continue
            if not _path_under(full, root):
                record_scan_error(full, "audio path escapes the configured library root")
                continue
            if os.path.abspath(full) in cue_audio_paths:
                continue
            try:
                stat = os.stat(full)
            except OSError:
                record_scan_error(full, "无法读取文件状态")
                continue
            signature_parts.append("%s:%s:%s" % (full, stat.st_mtime_ns, stat.st_size))
            cached = previous.get(full)
            if can_reuse_cached_item(cached, stat.st_size, stat.st_mtime_ns, METADATA_VERSION):
                items.append(cached)
                SCAN_STATE["found"] = found_offset + len(items)
                continue
            item_id = hashlib.sha1(full.encode("utf-8", "ignore")).hexdigest()[:16]
            probe_tags, audio_info = read_probe_metadata(full, config or {})
            metadata = read_metadata(full, root, config, probe_tags)
            items.append(build_audio_item(
                item_id, metadata, ext, SUPPORTED[ext], ext in (".dsf", ".dff"),
                stat.st_size, audio_info, full, scan_started, stat,
                metadata_version=METADATA_VERSION,
            ))
            SCAN_STATE["found"] = found_offset + len(items)
        if len(items) and len(items) % 500 == 0:
            time.sleep(0.01)
    check_scan_deadline(deadline)
    items = sort_scan_items(items)
    signature_parts.append("metadata_version:%s" % METADATA_VERSION)
    signature = digest_signature_parts(signature_parts)
    return items, signature

def scan_libraries(config, previous_items=None, deadline=None, sink=None):
    shared = sink is not None
    all_items = sink if shared else []
    signatures = []
    roots = normalize_library_paths(config)
    previous_by_root = partition_previous_items(previous_items, roots, _path_under)
    for index, root in enumerate(roots):
        check_scan_deadline(deadline)
        # With a shared accumulator the scanner writes straight into it, so the
        # offset it reports is the total and the per-root result is already in
        # place; extending again would duplicate every track.
        items, signature = scan_library(
            root,
            previous_by_root[index],
            config,
            deadline,
            0 if shared else len(all_items),
            all_items if shared else None,
        )
        if not shared:
            all_items.extend(items)
        if signature:
            signatures.append("%s:%s" % (root, signature))
    return finalize_scan_results(all_items, signatures)


def library_signature_for_config(config, deadline=None):
    """Build the filesystem signature without parsing audio metadata."""
    signatures = []
    for root in normalize_library_paths(config):
        check_scan_deadline(deadline)
        signature = library_signature(root, deadline)
        if signature:
            signatures.append("%s:%s" % (root, signature))
    return digest_signature_parts(signatures)


def _scan_state_value(key, default=None):
    """Read a scan-state field without trusting a mutable runtime mapping."""
    try:
        return SCAN_STATE.get(key, default) if isinstance(SCAN_STATE, dict) else default
    except Exception:
        return default


def _scan_state_bool(key):
    try:
        return strict_bool(_scan_state_value(key, False))
    except Exception:
        return False


def _record_library_cache_failure(kind):
    if kind not in ("load", "save"):
        return
    try:
        with LIBRARY_CACHE_FAILURES_LOCK:
            updated = increment_failure(LIBRARY_CACHE_FAILURES, kind)
            LIBRARY_CACHE_FAILURES.update(updated)
    except Exception:
        return


def library_cache_failure_status():
    try:
        with LIBRARY_CACHE_FAILURES_LOCK:
            return project_failures(LIBRARY_CACHE_FAILURES)
    except Exception:
        return {"load": 0, "save": 0}


def library_status(config):
    roots = normalize_library_paths(config)
    root = roots[0] if roots else canonical_library_path(".")
    db_summary = library_summary_from_sqlite(config)
    count = safe_counter(db_summary.get("count", len(MUSIC_CACHE["items"])))
    dsd_count = safe_counter(db_summary.get("dsd_count", sum(1 for item in MUSIC_CACHE["items"] if item.get("is_dsd"))))
    status = {
        "library_path": root,
        "library_paths": roots,
        "server_port": bounded_int(config, "server_port", DEFAULT_PORT, 1024, 65535),
        "allowed": is_allowed_library_path(root),
        "exists": os.path.exists(root),
        "is_dir": os.path.isdir(root),
        "readable": os.access(root, os.R_OK),
        "count": count,
        "dsd_count": dsd_count,
        "scanning": _scan_state_bool("running"),
        "queued": _scan_state_bool("queued"),
        "result": str(_scan_state_value("result") or "idle")[:32],
        "cancelled": _scan_state_bool("cancelled"),
        "timed_out": _scan_state_bool("timed_out"),
        "deadline": safe_int(_scan_state_value("deadline", 0)),
        "last_error": scan_error_text(_scan_state_value("last_error", "")),
        "last_scan": safe_float(_scan_state_value("last_scan", 0), 0.0),
        "current": scan_error_text(_scan_state_value("current", "")),
        "phase": scan_error_text(_scan_state_value("phase", "")),
        "scanned": safe_counter(_scan_state_value("scanned", 0)),
        "found": safe_counter(_scan_state_value("found", 0)),
        "errors": snapshot_scan_errors(_scan_state_value("errors")),
        "cache_failures": library_cache_failure_status(),
        "storage": library_storage_status(config),
        "change_detection": (
            LIBRARY_CHANGE_MONITOR.status()
            if LIBRARY_CHANGE_MONITOR is not None
            else {"mode": "polling", "watched_directories": 0, "dirty": True, "overflowed": False}
        ),
        "search_index": library_search_index_status(config),
        "supported_formats": sorted(x[1:].upper() for x in SUPPORTED),
    }
    status["message"] = status_message(status)
    return status

def browsable_roots():
    if os.name == "nt":
        return []
    roots = []
    for name in sorted(os.listdir("/")):
        path = "/" + name
        if re.match(r"^/vol\d+$", path) or path in ("/mnt", "/share", "/volume"):
            if os.path.isdir(path):
                roots.append(path)
    return roots

def list_music_directories(path):
    if not isinstance(path, str) or not path.strip():
        return browsable_roots()
    root = os.path.abspath(os.path.expanduser(path.strip()))
    if not root:
        return browsable_roots()
    if not is_allowed_library_path(root) or not os.path.isdir(root):
        return []
    max_directories = 512
    try:
        with os.scandir(root) as entries:
            # Keep directory browsing bounded without changing the existing
            # alphabetical presentation. nsmallest retains only the page
            # prefix instead of materializing every NAS child directory.
            dirs = heapq.nsmallest(
                max_directories,
                (entry.path for entry in entries if entry.is_dir(follow_symlinks=False)),
                key=lambda value: value.lower(),
            )
    except OSError:
        return []
    return dirs

def library_signature(root, deadline=None):
    parts = []
    total_signature_bytes = 0
    metadata_part = "metadata_version:%s" % METADATA_VERSION

    def append_signature_part(value):
        nonlocal total_signature_bytes
        if len(parts) >= max(0, MAX_LIBRARY_SIGNATURE_PARTS - 1) or not isinstance(value, str):
            return
        bounded = value[:4096]
        remaining = MAX_LIBRARY_SIGNATURE_BYTES - len(metadata_part) - total_signature_bytes
        if remaining <= 0:
            return
        bounded = bounded[:remaining]
        if not bounded:
            return
        parts.append(bounded)
        total_signature_bytes += len(bounded)

    root = os.path.abspath(os.path.expanduser(root))
    if not is_allowed_library_path(root) or not os.path.isdir(root):
        return ""
    for base, directories, files in os.walk(root):
        directories[:] = [name for name in directories if name != "fnaudio-transcode"]
        check_scan_deadline(deadline)
        for filename in files:
            check_scan_deadline(deadline)
            classification = classify_filename(filename, SUPPORTED)
            if classification == "ignore":
                continue
            ext = os.path.splitext(filename)[1].lower()
            full = os.path.join(base, filename)
            if not _path_under(full, root):
                continue
            try:
                stat = os.stat(full)
            except OSError:
                continue
            append_signature_part("%s:%s:%s" % (full, stat.st_mtime_ns, stat.st_size))
    if MAX_LIBRARY_SIGNATURE_PARTS > 0 and MAX_LIBRARY_SIGNATURE_BYTES >= len(metadata_part):
        parts.append(metadata_part)
    return digest_signature_parts(parts)

def legacy_reuse_items_for_scan(config):
    """Reuse the index an earlier install root left behind, if it matches.

    Changing the install type relocates the configuration directory from
    ``/vol<N>/@appconf/<app>`` to ``/usr/local/apps/@appconf/<app>`` without
    moving the library index inside it.  The active cache then looks empty,
    and a library of tens of thousands of files is re-probed track by track:
    the scan cannot finish inside ``scan_timeout_seconds``, so it publishes
    nothing and the interface shows no music at all.  The handover reader is
    read-only, verifies the root and metadata version it was written for, and
    refuses an index with a live write-ahead journal, so the old volume stays
    untouched and a stale or foreign index is never ingested.
    """
    try:
        items, source = find_legacy_reuse_items(
            config.get("cache_dir") if isinstance(config, dict) else "",
            library_path=display_library_path(config),
            metadata_version=METADATA_VERSION,
            list_root=os.listdir,
            active_db_path=library_db_path(config),
        )
    except Exception:
        return []
    if items:
        print("fnAudio reused legacy library index: %s (%s tracks)"
              % (source, len(items)), flush=True)
    return items


def publish_partial_library_index(config, items):
    """Publish an interrupted scan so the library is never left empty.

    A scan that reaches the deadline or is cancelled still knows every track
    it has already read.  Keeping that work is the difference between a large
    library showing its first pages immediately and showing nothing until a
    scan that cannot finish finally gives up.

    The stored signature is deliberately empty.  It marks the index as
    partial, and because the startup fast path only short-circuits behind a
    non-empty signature, every later refresh keeps working toward a complete
    scan; the in-memory filesystem signature is left alone for the same
    reason.
    """
    if not items:
        return False
    try:
        snapshot = list(items)
    except (TypeError, ValueError):
        return False
    if not snapshot:
        return False
    try:
        saved = save_library_cache(config, snapshot, "")
    except Exception:
        return False
    if not saved:
        return False
    MUSIC_CACHE["items"] = snapshot
    MUSIC_CACHE["stamp"] = time.time()
    print("fnAudio published partial library index: %s tracks" % len(snapshot), flush=True)
    return True


def refresh_library_if_changed(config, force=False, change_monitor=None, _refresh_generation=None):
    # Requested scans wait behind the change monitor instead of disappearing
    # when both notice the same filesystem update at nearly the same time.
    SCAN_LOCK.acquire()
    cancelled_before_start = False
    with SCAN_REQUEST_LOCK:
        if (
            _refresh_generation is not None
            and _refresh_generation != SCAN_REFRESH_GENERATION
        ):
            SCAN_STATE["running"] = False
            SCAN_STATE["result"] = "cancelled"
            SCAN_STATE["cancelled"] = True
            SCAN_STATE["timed_out"] = False
            SCAN_STATE["deadline"] = 0
            SCAN_STATE["current"] = ""
            SCAN_STATE["phase"] = ""
            SCAN_STATE["last_error"] = "扫描已取消"
            cancelled_before_start = True
        else:
            # Clear only while the request state is reserved. Otherwise a
            # cancel between `running=True` and clear() can be lost and start
            # a scan while shutdown is waiting for this worker to exit.
            SCAN_CANCEL_EVENT.clear()
            SCAN_STATE["running"] = True
            SCAN_STATE["result"] = "running"
            SCAN_STATE["cancelled"] = False
            SCAN_STATE["timed_out"] = False
    partial_scan_items = []
    if cancelled_before_start:
        SCAN_LOCK.release()
        return
    try:
        # SCAN_LOCK is already held at this point, so every statement that can
        # still fail before the scan begins belongs inside the guarded block:
        # one escaped exception would leave the lock held and block every later
        # refresh request for the lifetime of the process.
        timeout = bounded_int(config, "scan_timeout_seconds", 3600, 60, 86400)
        deadline = ScanDeadline(timeout, SCAN_STATE)
        SCAN_STATE["deadline"] = int(time.time()) + timeout
        SCAN_STATE["last_error"] = ""
        SCAN_STATE["current"] = ""
        SCAN_STATE["phase"] = "准备扫描"
        SCAN_STATE["scanned"] = 0
        SCAN_STATE["found"] = 0
        SCAN_STATE["errors"] = []
        monitor = change_monitor if change_monitor is not None else LIBRARY_CHANGE_MONITOR
        monitor_generation = monitor.generation() if monitor is not None and monitor.available else None
        previous_signature = FS_CACHE["signature"]
        database_exists = os.path.isfile(library_db_path(config))
        if previous_signature and not force:
            if database_exists and monitor_generation is not None and not monitor.needs_scan():
                SCAN_STATE["last_scan"] = time.time()
                return
            # The startup integrity pass and inotify-triggered refresh only
            # read filesystem metadata. Audio tags are parsed after a change.
            quick_signature = library_signature_for_config(config, deadline)
            if quick_signature == previous_signature and database_exists:
                if monitor_generation is not None:
                    monitor.mark_clean(monitor_generation)
                SCAN_STATE["last_scan"] = time.time()
                return
        SCAN_STATE["phase"] = "读取旧索引"
        previous_items = MUSIC_CACHE["items"]
        if not previous_items:
            cached = load_items_from_sqlite(config)
            previous_items = (cached or {}).get("items", [])
        if not previous_items:
            previous_items = legacy_reuse_items_for_scan(config)
        SCAN_STATE["phase"] = "扫描音乐目录"
        items, signature = scan_libraries(config, previous_items, deadline, partial_scan_items)
        check_scan_deadline(deadline)
        if signature != FS_CACHE["signature"] or not os.path.isfile(library_db_path(config)):
            SCAN_STATE["phase"] = "保存音乐库索引"
            if not save_library_cache(config, items, signature):
                raise OSError("library index persistence failed")
        MUSIC_CACHE["items"] = items
        MUSIC_CACHE["stamp"] = time.time()
        FS_CACHE["signature"] = signature
        if monitor_generation is not None:
            monitor.mark_clean(monitor_generation)
        SCAN_STATE["last_scan"] = time.time()
        SCAN_STATE["result"] = "completed"
    except ScanTimedOut as exc:
        SCAN_STATE["timed_out"] = True
        error_text = scan_error_text(exc.args[0] if exc.args else "扫描超时") or "扫描超时"
        SCAN_STATE["last_error"] = error_text
        SCAN_STATE["result"] = "timed_out"
        print("fnAudio library scan timed out: %s" % error_text, flush=True)
        try:
            publish_partial_library_index(config, partial_scan_items)
        except Exception as exc:
            print("fnAudio partial library index failed: %s" % exc.__class__.__name__, flush=True)
    except ScanCancelled as exc:
        SCAN_STATE["cancelled"] = True
        error_text = scan_error_text(exc.args[0] if exc.args else "扫描已取消") or "扫描已取消"
        SCAN_STATE["last_error"] = error_text
        SCAN_STATE["result"] = "cancelled"
        print("fnAudio library scan cancelled: %s" % error_text, flush=True)
        try:
            publish_partial_library_index(config, partial_scan_items)
        except Exception as exc:
            print("fnAudio partial library index failed: %s" % exc.__class__.__name__, flush=True)
    except Exception as exc:
        error_text = scan_error_text(exc.args[0] if exc.args else "扫描失败") or "扫描失败"
        SCAN_STATE["last_error"] = error_text
        SCAN_STATE["result"] = "error"
        print("fnAudio library scan failed: %s" % error_text, flush=True)
    finally:
        if SCAN_STATE.get("result") == "running":
            SCAN_STATE["result"] = "completed"
        SCAN_STATE["running"] = False
        SCAN_STATE["current"] = ""
        SCAN_STATE["phase"] = ""
        SCAN_STATE["deadline"] = 0
        SCAN_LOCK.release()

def _run_library_refresh_queue(config):
    global SCAN_WORKER_THREAD
    worker = threading.current_thread()
    try:
        while True:
            with SCAN_REQUEST_LOCK:
                force, queued, queued_force = take_refresh(
                    SCAN_STATE.get("queued"), SCAN_STATE.get("queued_force")
                )
                if force is None:
                    if SCAN_WORKER_THREAD is worker:
                        SCAN_STATE["worker_active"] = False
                        SCAN_WORKER_THREAD = None
                    return
                SCAN_STATE["queued"] = queued
                SCAN_STATE["queued_force"] = queued_force
                refresh_generation = SCAN_REFRESH_GENERATION
            refresh_library_if_changed(config, force, _refresh_generation=refresh_generation)
    finally:
        with SCAN_REQUEST_LOCK:
            # An old worker can finish after cancellation and a replacement
            # worker has already been published. Never clear the replacement's
            # active latch or thread handle from the stale worker.
            if SCAN_WORKER_THREAD is worker:
                SCAN_STATE["worker_active"] = False
                SCAN_WORKER_THREAD = None


def request_library_refresh(config, force=False):
    global SCAN_WORKER_THREAD
    with SCAN_REQUEST_LOCK:
        accepted, start_worker, queued, queued_force, worker_active = enqueue_refresh(
            SCAN_STATE.get("queued"),
            SCAN_STATE.get("queued_force"),
            SCAN_STATE.get("worker_active"),
            force,
        )
        SCAN_STATE["queued"] = queued
        SCAN_STATE["queued_force"] = queued_force
        SCAN_STATE["worker_active"] = worker_active
        if not start_worker:
            return accepted
        thread = threading.Thread(target=_run_library_refresh_queue, args=(config,), daemon=True)
        try:
            SCAN_WORKER_THREAD = thread
            thread.start()
        except Exception:
            if SCAN_WORKER_THREAD is thread:
                SCAN_WORKER_THREAD = None
            SCAN_STATE["queued"] = False
            SCAN_STATE["queued_force"] = False
            SCAN_STATE["worker_active"] = False
            raise
    return True


def cancel_library_refresh():
    global SCAN_REFRESH_GENERATION
    with SCAN_REQUEST_LOCK:
        accepted, queued, queued_force, signal_running = cancel_refresh(
            SCAN_STATE.get("running"),
            SCAN_STATE.get("queued"),
            SCAN_STATE.get("worker_active"),
        )
        SCAN_STATE["queued"] = queued
        SCAN_STATE["queued_force"] = queued_force
        if accepted:
            SCAN_REFRESH_GENERATION += 1
        if signal_running:
            SCAN_CANCEL_EVENT.set()
        return accepted


def shutdown_library_refresh(wait=True, timeout=5.0):
    """Cancel any scan worker and wait for it before process shutdown."""
    cancel_library_refresh()
    with SCAN_REQUEST_LOCK:
        thread = SCAN_WORKER_THREAD
    if wait and thread is not None and thread is not threading.current_thread():
        thread.join(_bounded_wait_timeout(timeout, 5.0))

def library_items(config, refresh=False):
    if refresh:
        request_library_refresh(config, True)
    return MUSIC_CACHE["items"]


def _track_search_condition(search, alias="", use_fts=False, rowid_column=None):
    return track_search_condition(search, alias, use_fts, rowid_column)


def _search_index_mode(config):
    database = os.path.abspath(library_db_path(config))
    with LIBRARY_SEARCH_INDEX_LOCK:
        return LIBRARY_SEARCH_INDEX_MODE.get(database, "like")


def library_search_index_status(config):
    mode = _search_index_mode(config)
    return search_index_status(mode)


def _search_uses_fts(config, search):
    return uses_fts(_search_index_mode(config), search)


def _search_cache_token(config, search):
    return cache_token(_search_index_mode(config), search) if search else ""


def _search_plan(config, search):
    """Read the current search mode once for both SQL and cache identity."""
    if not search:
        return False, ""
    mode = _search_index_mode(config)
    return uses_fts(mode, search), cache_token(mode, search)


def group_match_condition(column, value):
    """Match a visible group label while preserving SQLite's ordinary indexes.

    Group tables expose both literal ``未分类`` tags and blank/null tags under
    the same label.  The older COALESCE expression was convenient but made
    every normal artist/album/genre page non-sargable.  Keep the exceptional
    label explicit and let ordinary values use a direct indexed equality.
    """
    return build_group_match_condition(column, value)


def _saved_library_meta_count(conn, key):
    safe_key = key if isinstance(key, str) else ""
    try:
        row = conn.execute("SELECT value FROM library_meta WHERE key = ?", (safe_key,)).fetchone()
    except Exception:
        return None
    return project_saved_count(row)


def _save_library_meta_count(conn, key, value):
    """Persist one derived count without trusting the caller or the handle.

    A browse read borrows a pooled handle it did not open, so a repair write is
    best effort: failing to persist is never a reason to fail a page that is
    already carrying the authoritative count.
    """
    if not isinstance(key, str) or not key:
        return False
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return False
    try:
        conn.execute(
            "INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)",
            (key, str(value)),
        )
    except Exception:
        return False
    return True


def _refresh_group_counts(conn):
    """Store each group table's row count for the pages that read it whole.

    The value is derived from the table on the write side rather than patched
    per mutation, so it cannot drift by construction: every site that can add
    or drop a group label ends up here.  A browse page still re-checks the
    stored number against its own look-ahead row and overwrites it from the
    authoritative count, which is what heals an index edited outside a scan.
    """
    for table, key in GROUP_COUNT_KEYS:
        count = conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
        _save_library_meta_count(conn, key, int(count))


def _cursor_page_rows(conn, where, args, page_query, cursor, limit):
    """Read the rows after a cursor with two index seeks instead of a counted OFFSET.

    The first statement walks the tail of the key group the cursor sits in and the
    second one continues with the groups that follow it, so neither has to visit
    the rows it would throw away. The shape this replaced counted the group prefix
    and then let OFFSET walk it again: on a 100000-track library a page inside a
    20000-row format group at a 19000-row depth cost 3.31ms (1.88ms of it in the
    count) against 1.27ms here, and 1.28ms against 8.64ms once the offset itself
    is deep.

    Both statements stay single comparisons on the ordering prefix, which is the
    only form SQLite seeks; the predicates are widened into an OR nowhere. At most
    ``limit + 1`` rows come back so the caller keeps its look-ahead row, and both
    queries are bounded by the same limit, so no unbounded result is materialised.
    """
    select = _track_page_select(page_query)
    budget = limit + 1
    rows = []
    for condition, condition_args in (
        cursor_group_tail_where(page_query, cursor),
        cursor_next_group_where(page_query, cursor),
    ):
        if not condition or budget <= 0:
            break
        statement = "%s FROM tracks WHERE %s ORDER BY %s LIMIT ?" % (
            select,
            " AND ".join(list(where) + [condition]),
            page_query.sql_order_by,
        )
        # No exception guard: this runs on the same connection, with the same
        # filter arguments, as the total count beside it, and a swallowed failure
        # here would answer with a short page instead of failing the request.
        found = conn.execute(statement, list(args) + list(condition_args) + [budget]).fetchall()
        rows.extend(found)
        budget -= len(found)
    return rows


def _browse_cursor_rows(conn, prefix, joiner, order_by, base_args, cursor, kind, sort_dir, name_expression, tie_expression, limit):
    """Read the browse rows after a cursor with two index seeks instead of an OR.

    The first statement walks the tail of the key group the cursor sits in and
    the second one continues with the groups that follow it, so neither has to
    visit a row it would throw away.  The OR predicate this replaces was one
    condition, but SQLite cannot seek on it: a 100000-album continuation cost
    1.90/3.31/6.95/11.90ms at depths 0/12000/50000/99000 against 1.8-2.4ms for
    either statement here.  Both share one ``limit + 1`` budget so the caller
    keeps its look-ahead row, and neither materialises more than a page.
    """
    budget = limit + 1
    rows = []
    for condition, condition_args in (
        browse_cursor_group_tail_where(cursor, kind, sort_dir, name_expression, tie_expression),
        browse_cursor_next_group_where(cursor, kind, sort_dir, name_expression),
    ):
        if not condition or budget <= 0:
            break
        # No exception guard: this runs on the same connection, with the same
        # filter arguments, as the total beside it, and a swallowed failure here
        # would answer with a short page instead of failing the request.
        found = conn.execute(
            prefix + joiner + condition + " ORDER BY " + order_by + " LIMIT ?",
            list(base_args) + list(condition_args) + [budget],
        ).fetchall()
        rows.extend(found)
        budget -= len(found)
    return rows


def query_library_page(config, params):
    if not os.path.isfile(library_db_path(config)):
        return _query_memory_library_page(config, params)
    page_query = parse_library_page_query(params)
    limit, offset = page_query.limit, page_query.offset
    cursor = cursor_page(decode_track_cursor(page_query.cursor), page_query)
    if cursor:
        # A cursor is already a keyset position. Applying a caller-supplied
        # offset after it would silently skip additional rows.
        offset = 0
    view, group, album = page_query.view, page_query.group, page_query.album
    folder, root, search = page_query.folder, page_query.root, page_query.search
    sort_dir, order, order_by = page_query.sql_sort_dir, page_query.sql_order, page_query.sql_order_by
    use_fts, search_cache_token = _search_plan(config, search)
    cache_values = (
        page_query.view, page_query.group, page_query.album, page_query.folder,
        page_query.root, page_query.search, page_query.sort_key,
        page_query.sql_sort_dir, page_query.limit, offset, page_query.cursor,
    ) + ((search_cache_token,) if search_cache_token else ())
    # A random page's explicit refresh means "draw another sample".  The
    # browser response cache and the scan refresh queue remain independent,
    # but the server-side page cache must not turn that request into the same
    # sample again.
    random_refresh = view == "random100" and first_param(params, "refresh", "") == "1"
    cache_epoch = _library_cache_epoch(config)
    cached = None if random_refresh else cache_epoch.get("tracks", cache_values)
    if cached is not None:
        return cached
    where = []
    args = []
    if view == "dsd":
        where.append("is_dsd = 1")
    elif view == "recent":
        if search:
            condition, condition_args = _track_search_condition(search, use_fts=use_fts)
            where.append(condition)
            args.extend(condition_args)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        with library_db_connect(config) as conn:
            count = _saved_library_meta_count(conn, "track_count") if not where_sql else None
            page_sql = "%s FROM tracks%s ORDER BY %s LIMIT ? OFFSET ?" % (_track_page_select(page_query), where_sql, order_by)
            if count is None:
                window_sql = "%s FROM tracks%s ORDER BY %s LIMIT ? OFFSET ?" % (_track_page_select(page_query, True), where_sql, order_by)
                if cursor:
                    count = conn.execute("SELECT COUNT(*) FROM tracks" + where_sql, args).fetchone()[0]
                    rows = _cursor_page_rows(conn, where, args, page_query, cursor, limit)
                else:
                    rows, count = paged_rows_with_total(conn, window_sql, args + [limit + 1, offset], "SELECT COUNT(*) FROM tracks" + where_sql, args, page_sql, args + [limit + 1, offset])
            else:
                rows = (
                    _cursor_page_rows(conn, where, args, page_query, cursor, limit)
                    if cursor
                    else conn.execute(page_sql, args + [limit + 1, offset])
                )
            if count == 0 and MUSIC_CACHE["items"] and not cursor:
                return _query_memory_library_page(config, params)
            if cursor:
                items, anchor, has_more = _decode_track_cursor_page_rows(rows, limit)
            else:
                # One row past the limit is read here as well: a page whose last served
                # row carries a key no predicate can express continues from the row after
                # it instead. has_more still comes from the total count, as it always did
                # on this path, so the page keeps the same completeness answer.
                items, anchor, _look_ahead_more = _decode_track_cursor_page_rows(rows, limit)
                has_more = None
        return cache_epoch.put(
            "tracks",
            cache_values,
            _track_page_result(items, count, limit, offset, page_query, anchor, has_more),
        )
    elif view == "random100":
        sample_limit = min(100, limit)
        if search:
            condition, condition_args = _track_search_condition(search, use_fts=use_fts)
            where.append(condition)
            args.extend(condition_args)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        with library_db_connect(config) as conn:
            count = _saved_library_meta_count(conn, "track_count") if not where_sql else None
            if count is None:
                count = conn.execute("SELECT COUNT(*) FROM tracks" + where_sql, args).fetchone()[0]
            if count == 0 and MUSIC_CACHE["items"]:
                return _query_memory_library_page(config, params)
            # `ORDER BY RANDOM()` scans and sorts every row, which is
            # disproportionately expensive for the unfiltered 100-track view
            # on a large collection. SQLite rowids are dense after normal
            # index writes; probe a bounded set of random rowids, retry around
            # occasional deletion gaps, then keep the existing display sort.
            # Filtered random pages retain SQLite's exact random query because
            # rowid guesses would distort sparse search result sets.
            if not where_sql:
                maximum_rowid = conn.execute("SELECT COALESCE(MAX(rowid),0) FROM tracks").fetchone()[0]
                selected_rowids = set()
                attempts = 0
                while len(selected_rowids) < sample_limit and attempts < 4:
                    needed = sample_limit - len(selected_rowids)
                    candidates = random_rowid_candidates(
                        maximum_rowid,
                        min(MAX_RANDOM_ROWID_CANDIDATES, max(needed * 2, 64)),
                        random.randrange,
                    )
                    candidates = [value for value in candidates if value not in selected_rowids]
                    if not candidates:
                        break
                    placeholders = ",".join("?" for _ in candidates)
                    selected_rowids.update(
                        row["rowid"] for row in conn.execute(
                            "SELECT rowid FROM tracks WHERE rowid IN (%s)" % placeholders,
                            candidates,
                        )
                    )
                    attempts += 1
                if len(selected_rowids) >= sample_limit:
                    # The probe set is deliberately larger than the visible
                    # sample to tolerate sparse rowid gaps.  Sorting before
                    # truncating would make every response favor older,
                    # lower rowids, defeating the random view's contract.
                    selected = random.sample(tuple(selected_rowids), sample_limit)
                    placeholders = ",".join("?" for _ in selected)
                    rows = conn.execute(
                        "SELECT item_json FROM tracks WHERE rowid IN (%s) ORDER BY %s" % (placeholders, order_by),
                        selected,
                    )
                else:
                    rows = conn.execute(
                        "SELECT item_json FROM (SELECT item_json,title,artist,album,format,added_ns,track_no,id FROM tracks ORDER BY RANDOM() LIMIT ?) ORDER BY %s" % order_by,
                        [sample_limit],
                    )
            else:
                rows = conn.execute(
                        "SELECT item_json FROM (SELECT item_json,title,artist,album,format,added_ns,track_no,id FROM tracks%s ORDER BY RANDOM() LIMIT ?) ORDER BY %s" % (where_sql, order_by),
                    args + [sample_limit],
                )
            items = decode_item_rows(rows)
        return cache_epoch.put("tracks", cache_values, {"items": items, "count": min(count, sample_limit), "limit": sample_limit, "offset": 0, "paged": True})
    where, args = build_track_filters(
        page_query,
        search_condition=_track_search_condition,
        group_condition=group_match_condition,
        use_fts=use_fts,
    )
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    with library_db_connect(config) as conn:
        # The unfiltered library view is the hottest pagination path.  Scans
        # already commit an exact track count alongside the index metadata,
        # so avoid rescanning a large ``tracks`` table for every page.  Older
        # indexes (or manually edited caches) simply fall back to the
        # authoritative COUNT query and are repaired on the next scan.
        count = None
        count_key = saved_count_key(view, search, where_sql)
        if count_key:
            count = _saved_library_meta_count(conn, count_key)
        page_sql = "%s FROM tracks%s ORDER BY %s LIMIT ? OFFSET ?" % (_track_page_select(page_query), where_sql, order_by)
        if count is None:
            window_sql = "%s FROM tracks%s ORDER BY %s LIMIT ? OFFSET ?" % (_track_page_select(page_query, True), where_sql, order_by)
            if cursor:
                count = conn.execute("SELECT COUNT(*) FROM tracks" + where_sql, args).fetchone()[0]
                rows = _cursor_page_rows(conn, where, args, page_query, cursor, limit)
            else:
                rows, count = paged_rows_with_total(conn, window_sql, args + [limit + 1, offset], "SELECT COUNT(*) FROM tracks" + where_sql, args, page_sql, args + [limit + 1, offset])
        else:
            rows = (
                _cursor_page_rows(conn, where, args, page_query, cursor, limit)
                if cursor
                else conn.execute(page_sql, args + [limit + 1, offset])
            )
        if count == 0 and MUSIC_CACHE["items"] and not cursor:
            return _query_memory_library_page(config, params)
        if cursor:
            items, anchor, has_more = _decode_track_cursor_page_rows(rows, limit)
        else:
            # One row past the limit is read here as well: a page whose last served
            # row carries a key no predicate can express continues from the row after
            # it instead. has_more still comes from the total count, as it always did
            # on this path, so the page keeps the same completeness answer.
            items, anchor, _look_ahead_more = _decode_track_cursor_page_rows(rows, limit)
            has_more = None
    return cache_epoch.put("tracks", cache_values, _track_page_result(items, count, limit, offset, page_query, anchor, has_more))


def _query_memory_library_page(config, params):
    items = library_items(config)
    page_query = parse_library_page_query(params)
    roots = normalize_library_paths(config)
    return build_memory_library_page(
        items, page_query, roots, UNCLASSIFIED, _path_under, safe_int,
        shuffle=random.shuffle, randrange=random.randrange,
    )

def query_library_groups(config, view, search="", limit=None, offset=0, sort_dir="asc", artist="", composer="", cursor=""):
    browse_query = parse_library_group_query(view, search, limit, offset, sort_dir, artist, composer, cursor)
    view, search, page = browse_query.view, browse_query.search, browse_query.page
    direction, artist, composer, cursor = browse_query.sql_sort_dir, browse_query.artist, browse_query.composer, decode_browse_cursor(browse_query.cursor)
    if browse_cursor_page(cursor, "group", browse_query.sql_sort_dir.lower()):
        offset = 0
        page = type(page)(page.limit, 0) if page is not None else None
    table_map = {"albums": "albums", "artists": "artists", "composers": "composers", "genres": "genres"}
    table = table_map.get(view)
    if not table or not os.path.isfile(library_db_path(config)):
        return {"groups": [], "count": 0, "limit": 0, "offset": 0, "paged": True} if limit is not None else []
    use_fts, search_cache_token = _search_plan(config, search)
    cache_values = (view, search, page.limit, page.offset, direction, artist, composer, browse_query.cursor) if page else ()
    if page and search_cache_token:
        cache_values += (search_cache_token,)
    cache_epoch = _library_cache_epoch(config) if page else None
    if page:
        cached = cache_epoch.get("groups", cache_values)
        if cached is not None:
            return cached
    if view == "albums" and (artist or composer):
        owner_column = "composer" if composer else "artist"
        owner = composer or artist
        owner_condition, owner_args = group_match_condition("t." + owner_column, owner)
        search_condition, search_args = _track_search_condition(
            search, use_fts=use_fts, rowid_column="track_rowid"
        )
        matched_where = (" WHERE " + search_condition) if search_condition else ""
        cte = (
            "WITH scoped AS ("
            "SELECT t.rowid AS track_rowid, t.*, COALESCE(NULLIF(t.album, ''), ?) AS group_name FROM tracks t "
            "WHERE %s"
            "), matched AS (SELECT DISTINCT group_name FROM scoped%s) "
            % (owner_condition, matched_where)
        )
        cte_args = [UNCLASSIFIED] + owner_args + search_args
        artist_expr = "COALESCE(NULLIF(MIN(NULLIF(s.album_artist, '')), ''), NULLIF(MIN(NULLIF(s.artist, '')), ''), ?)"
        grouped_sql = (
            "SELECT s.group_name AS name, %s AS artist, COUNT(*) AS track_count, MIN(s.id) AS cover_track_id "
            "FROM scoped s JOIN matched m ON m.group_name = s.group_name GROUP BY s.group_name"
            % artist_expr
        )
        with library_db_connect(config) as conn:
            if page is None:
                rows = conn.execute(
                    cte + grouped_sql + " ORDER BY name COLLATE NOCASE " + direction + ", name ASC",
                    cte_args + [UNCLASSIFIED],
                )
                return materialize_browse_rows(rows)
            # The normal paged path used to run the same scoped/matched CTE
            # twice: once to count and once to render a page.  Let SQLite
            # attach the grouped total to each returned row instead.  An
            # out-of-range page has no row from which to read the window
            # value, so only that exceptional path retains the count query.
            window_sql = (
                cte + "SELECT name,artist,track_count,cover_track_id,COUNT(*) OVER() AS total_count "
                "FROM (" + grouped_sql + ") grouped ORDER BY name COLLATE NOCASE " + direction + ", name ASC LIMIT ? OFFSET ?"
            )
            count_sql = cte + "SELECT COUNT(*) FROM matched"
            page_sql = cte + grouped_sql + " ORDER BY name COLLATE NOCASE " + direction + ", name ASC LIMIT ? OFFSET ?"
            cursor_condition, _cursor_args = browse_cursor_next_group_where(cursor, "group", browse_query.sql_sort_dir.lower(), "name COLLATE NOCASE")
            if cursor_condition:
                rows = _browse_cursor_rows(
                    conn,
                    cte + "SELECT * FROM (" + grouped_sql + ") grouped",
                    " WHERE ",
                    "name COLLATE NOCASE " + direction + ", name ASC",
                    cte_args + [UNCLASSIFIED],
                    cursor, "group", browse_query.sql_sort_dir.lower(), "name COLLATE NOCASE", "name", page.limit,
                )
                count = conn.execute(count_sql, cte_args).fetchone()[0]
            else:
                rows, count = paged_rows_with_total(
                    conn,
                    window_sql,
                    cte_args + [UNCLASSIFIED, page.limit, page.offset],
                    count_sql,
                    cte_args,
                    page_sql,
                    cte_args + [UNCLASSIFIED, page.limit, page.offset],
                )
            groups = project_group_rows(rows, page.limit + 1 if cursor_condition else page.limit)
            has_more = bool(cursor_condition and len(groups) > page.limit)
            if has_more:
                groups = groups[:page.limit]
            result = {"groups": groups, "count": count, "limit": page.limit, "offset": page.offset, "paged": True}
            if groups:
                token = encode_browse_cursor("group", browse_query.sql_sort_dir.lower(), groups[-1].get("name", ""))
                if token:
                    result["next_cursor"] = token
                    result["has_more"] = has_more if cursor_condition else len(groups) == page.limit and page.offset + len(groups) < count
            return cache_epoch.put("groups", cache_values, result)
    search_condition, search_args = _track_search_condition(search, "t", use_fts=use_fts)
    group_column = {"albums": "album", "artists": "artist", "composers": "composer", "genres": "genre"}[view]
    if search_condition:
        matched_sql = (
            "WITH matched AS (SELECT DISTINCT COALESCE(NULLIF(t.%s, ''), ?) AS name FROM tracks t WHERE %s) "
            % (group_column, search_condition)
        )
        select_sql = "SELECT g.* FROM %s g JOIN matched m ON m.name = g.name" % table
        args = [UNCLASSIFIED] + search_args
    else:
        matched_sql = ""
        select_sql = "SELECT * FROM %s" % table
        args = []
    with library_db_connect(config) as conn:
        if page is None:
            return materialize_browse_rows(conn.execute(
                matched_sql + select_sql + " ORDER BY name COLLATE NOCASE " + direction + ", name ASC",
                args,
            ))
        count_sql = matched_sql + ("SELECT COUNT(*) FROM matched" if search_condition else "SELECT COUNT(*) FROM %s" % table)
        cursor_condition, _cursor_args = browse_cursor_next_group_where(cursor, "group", browse_query.sql_sort_dir.lower(), "name COLLATE NOCASE")
        page_sql = matched_sql + "SELECT * FROM (" + select_sql + ") grouped ORDER BY name COLLATE NOCASE " + direction + ", name ASC LIMIT ? OFFSET ?"
        window_sql = (
            matched_sql
            + "SELECT grouped.*, COUNT(*) OVER() AS total_count FROM (" + select_sql + ") grouped"
            + " ORDER BY name COLLATE NOCASE " + direction + ", name ASC LIMIT ? OFFSET ?"
        )
        if cursor_condition:
            rows = _browse_cursor_rows(
                conn,
                matched_sql + "SELECT * FROM (" + select_sql + ") grouped",
                " WHERE ",
                "name COLLATE NOCASE " + direction + ", name ASC",
                args,
                cursor, "group", browse_query.sql_sort_dir.lower(), "name COLLATE NOCASE", "name", page.limit,
            )
            count = conn.execute(count_sql, args).fetchone()[0]
        elif search_condition:
            rows, count = paged_rows_with_total(
                conn, window_sql, args + [page.limit, page.offset], count_sql, args,
                page_sql, args + [page.limit, page.offset],
            )
        else:
            # An unfiltered browse page reads a whole group table, so its total is
            # a plain count over the primary key.  A window total stays correct
            # here, but COUNT(*) OVER() has to sort every group before it can
            # emit the first row, which turns a page the ordering indexes serve
            # in bounded time back into a scan of the entire collection.  Scans
            # persist that plain count, and reading one row past the limit keeps
            # it honest.  An index written before the key existed pays the
            # two-statement shape below once and then stores what it learned, so
            # the scan stops being the only way the key can appear.
            count_key = group_count_key(table, search)
            saved = _saved_library_meta_count(conn, count_key)
            if saved is None:
                rows, count = counted_page_rows(
                    conn, page_sql, args + [page.limit, page.offset], count_sql, args,
                )
                _save_library_meta_count(conn, count_key, count)
            else:
                rows = conn.execute(
                    page_sql, args + [page.limit + 1, page.offset]
                ).fetchall()
                count, refuted = browse_page_total(
                    saved, page.offset, len(rows), page.limit
                )
                if refuted:
                    count = conn.execute(count_sql, args).fetchone()[0]
                if count != saved:
                    _save_library_meta_count(conn, count_key, count)
        groups = project_group_rows(rows, page.limit + 1 if cursor_condition else page.limit)
        has_more = bool(cursor_condition and len(groups) > page.limit)
        if has_more:
            groups = groups[:page.limit]
        result = {"groups": groups, "count": count, "limit": page.limit, "offset": page.offset, "paged": True}
        if groups:
            token = encode_browse_cursor("group", browse_query.sql_sort_dir.lower(), groups[-1].get("name", ""))
            if token:
                result["next_cursor"] = token
                result["has_more"] = has_more if cursor_condition else len(groups) == page.limit and page.offset + len(groups) < count
        return cache_epoch.put("groups", cache_values, result)

def query_library_folders(config, parent="", root="", sort_dir="asc", limit=None, offset=0, search="", cursor=""):
    browse_query = parse_library_folder_query(parent, root, sort_dir, limit, offset, search, cursor)
    parent, root, search, page, direction, cursor = browse_query.parent, browse_query.root, browse_query.search, browse_query.page, browse_query.sql_sort_dir, decode_browse_cursor(browse_query.cursor)
    if browse_cursor_page(cursor, "folder", browse_query.sql_sort_dir.lower()):
        page = type(page)(page.limit, 0) if page is not None else None
    if not os.path.isfile(library_db_path(config)):
        return {"folders": [], "count": 0, "limit": 0, "offset": 0, "paged": True} if limit is not None else []
    use_fts, search_cache_token = _search_plan(config, search)
    cache_values = (parent, root, direction, page.limit, page.offset, search, browse_query.cursor) if page else ()
    if page and search_cache_token:
        cache_values += (search_cache_token,)
    cache_epoch = _library_cache_epoch(config) if page else None
    if page:
        cached = cache_epoch.get("folders", cache_values)
        if cached is not None:
            return cached
    if root:
        conditions = ["f.root = ?", "f.parent = ?"]
        args = [root, parent]
    else:
        conditions = ["f.parent = ?"]
        args = [parent]
    search_condition, search_args = _track_search_condition(search, "t", use_fts=use_fts)
    matched_cte = ""
    if search_condition:
        # A folder matches a search when one of its own tracks, or one of a
        # descendant folder, matches.  Asking that per folder row against
        # `tracks` costs a pass over every track in the library root for each
        # sibling, because SQLite binds only `root` when it seeks the folder
        # index: one page measured 2.2 s at 4000 top-level folders and 64.6 s at
        # 16000.  Folding the matching tracks into a folder set once and walking
        # that set up the parent chain answers the same listing in 16 ms and
        # 70 ms, and it drops the path LIKE test, which also treated `_` and `%`
        # inside a folder name as wildcards and pulled in unrelated siblings.
        # Walking the parent chain only reaches an ancestor while that
        # ancestor has a folders row, so this rests on an invariant: every
        # folder that still holds a track has its row. Incremental writes
        # keep it by rebuilding the whole top-level tree of every added,
        # removed, or moved track. The closure test named
        # test_incremental_folder_refresh_keeps_the_track_folder_closure_complete
        # asserts that shape after moves, removals, and brand new chains.
        matched_cte = (
            "WITH RECURSIVE matched_folder_paths(root, path) AS ("
            "SELECT DISTINCT t.root, t.folder FROM tracks t"
            " WHERE COALESCE(t.folder, '') <> '' AND %s"
            " UNION"
            " SELECT f2.root, f2.parent FROM folders f2 JOIN matched_folder_paths m"
            " ON f2.root = m.root AND f2.path = m.path"
            " WHERE COALESCE(f2.parent, '') <> '') " % search_condition
        )
        conditions.append(
            "EXISTS (SELECT 1 FROM matched_folder_paths m"
            " WHERE m.root = f.root AND m.path = f.path)"
        )
    where = " WHERE " + " AND ".join(conditions)
    if matched_cte:
        # The search term binds inside the CTE, which precedes every statement
        # below, so its arguments have to go in front of the folder filters.
        args = list(search_args) + list(args)
    with library_db_connect(config) as conn:
        if page is None:
            return materialize_browse_rows(conn.execute(
                matched_cte + "SELECT f.* FROM folders f%s ORDER BY f.name COLLATE NOCASE %s" % (where, direction), args,
            ))
        count_sql = matched_cte + "SELECT COUNT(*) FROM folders f%s" % where
        cursor_condition, _cursor_args = browse_cursor_next_group_where(cursor, "folder", browse_query.sql_sort_dir.lower(), "f.name COLLATE NOCASE")
        order = "f.name COLLATE NOCASE %s, f.path ASC" % direction
        page_sql = matched_cte + "SELECT f.* FROM folders f%s ORDER BY %s LIMIT ? OFFSET ?" % (where, order)
        window_sql = matched_cte + "SELECT f.*, COUNT(*) OVER() AS total_count FROM folders f%s ORDER BY %s LIMIT ? OFFSET ?" % (where, order)
        if cursor_condition:
            rows = _browse_cursor_rows(
                conn,
                matched_cte + "SELECT f.* FROM folders f" + where,
                " AND ",
                order,
                args,
                cursor, "folder", browse_query.sql_sort_dir.lower(), "f.name COLLATE NOCASE", "f.path", page.limit,
            )
            count = conn.execute(count_sql, args).fetchone()[0]
        elif search_condition:
            # A search page has to test every sibling anyway, so carrying the
            # total inside the page stays cheaper than a second statement.
            rows, count = paged_rows_with_total(
                conn, window_sql, args + [page.limit, page.offset], count_sql, args,
                page_sql, args + [page.limit, page.offset],
            )
        else:
            # An unfiltered directory page is bounded by one parent and the
            # NOCASE ordering indexes can seek straight to its first row.  A
            # window total would walk back through every sibling that the index
            # just skipped, so the count rides its own covering-index statement.
            rows, count = counted_page_rows(
                conn, page_sql, args + [page.limit, page.offset], count_sql, args,
            )
        folders = project_folder_rows(rows, page.limit + 1 if cursor_condition else page.limit)
        has_more = bool(cursor_condition and len(folders) > page.limit)
        if has_more:
            folders = folders[:page.limit]
        result = {"folders": folders, "count": count, "limit": page.limit, "offset": page.offset, "paged": True}
        if folders:
            token = encode_browse_cursor("folder", browse_query.sql_sort_dir.lower(), folders[-1].get("name", ""), folders[-1].get("path", ""))
            if token:
                result["next_cursor"] = token
                result["has_more"] = has_more if cursor_condition else len(folders) == page.limit and page.offset + len(folders) < count
        return cache_epoch.put("folders", cache_values, result)

def query_library_root_folders(config, search=""):
    roots = normalize_library_paths(config)
    search = parse_library_root_search(search)
    use_fts, search_cache_token = _search_plan(config, search)
    # The same SQLite database can be viewed through different configured
    # roots. Keep that configuration identity in the bounded cache key so a
    # root switch cannot reuse a response projected for the previous roots.
    roots_cache_token = hashlib.sha256(
        json.dumps(roots, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    cache_values = (search, roots_cache_token)
    if search_cache_token:
        cache_values += (search_cache_token,)
    cache_epoch = _library_cache_epoch(config)
    cached = cache_epoch.get("roots", cache_values) if os.path.isfile(library_db_path(config)) else None
    if cached is not None:
        return cached
    if not os.path.isfile(library_db_path(config)):
        return [{"path": root, "root": root, "parent": "", "name": os.path.basename(root.rstrip("/\\")) or root, "track_count": 0, "cover_track_id": ""} for root in roots]
    with library_db_connect(config) as conn:
        search_condition, search_args = _track_search_condition(search, use_fts=use_fts)
        matched_roots = None
        if search_condition:
            if not roots:
                matched_roots = set()
            else:
                root_filter, root_args = configured_root_filter(roots)
                matched_roots = {
                    row["root"] or ""
                    for row in conn.execute(
                        "SELECT DISTINCT root FROM tracks WHERE " + root_filter + " AND " + search_condition,
                        root_args + search_args,
                    )
                }
            # A no-match search cannot produce root rows, so avoid decoding
            # the persisted summary (or falling back to aggregation) first.
            if not matched_roots:
                return cache_epoch.put("roots", cache_values, [])
        meta_row = conn.execute("SELECT value FROM library_meta WHERE key = 'root_summary'").fetchone()
        rows = decode_root_summary(meta_row["value"] if meta_row else None, roots)
        if rows is None:
            # Restrict the fallback aggregation to configured roots.  A stale
            # database may retain rows for removed libraries; grouping those
            # rows adds an avoidable full-table pass on every root view.
            root_filter, root_args = configured_root_filter(roots)
            if root_args:
                rows = {
                    row["root"] or "": row
                    for row in conn.execute(
                        "SELECT root, COUNT(*) AS track_count, MIN(id) AS cover_track_id "
                        "FROM tracks WHERE " + root_filter + " GROUP BY root",
                        root_args,
                    )
                }
            else:
                rows = {}
    result = project_root_rows(roots, rows, matched_roots)
    return cache_epoch.put("roots", cache_values, result)


def query_library_items_by_ids(config, ids):
    values = normalize_library_item_sequence(ids)
    if not values or not os.path.isfile(library_db_path(config)):
        return []
    # Favorites, playlists and playback restoration all use this ordered
    # hydration path.  It is read-only and already bounded by the transport
    # normalizer, so let the same short-lived SQLite page cache coalesce
    # repeated requests during a render/recovery burst.  The cache returns a
    # defensive copy and every index write invalidates this database namespace.
    # Cache keys intentionally retain only a small fixed number of values.
    # Playback restoration may legally hydrate far more IDs, so caching such
    # a request would alias queues that share an initial prefix. Bypass this
    # short-lived page cache for long ordered sequences rather than returning
    # a different queue's rows from a truncated key.
    cacheable = len(values) <= MAX_CACHE_KEY_VALUES
    cache_values = tuple(values) if cacheable else ()
    cache_epoch = _library_cache_epoch(config) if cacheable else None
    if cacheable:
        cached = cache_epoch.get("items_by_id", cache_values)
        if cached is not None:
            return cached
    with library_db_connect(config) as conn:
        result = hydrate_items_by_ids(conn, values, decode_item_rows, LIBRARY_ITEM_ID_LIMIT)
    return cache_epoch.put("items_by_id", cache_values, result) if cacheable else result

def query_library_item_by_id(config, item_id):
    value = normalize_library_item_id(item_id)
    if not value:
        return None
    if os.path.isfile(library_db_path(config)):
        with library_db_connect(config) as conn:
            item = lookup_sqlite_item(conn, value, decode_item_row)
            if item is not None:
                return item
    return lookup_memory_item(MUSIC_CACHE["items"], value)

def query_library_item_location(config, item_id):
    item = query_library_item_by_id(config, item_id)
    return resolve_item_location(item, item_id, normalize_library_paths(config), _path_under, MAX_LIBRARY_PATH_TEXT)

def library_cache_path(config):
    cache_dir = config.get("cache_dir", ".") if isinstance(config, dict) else "."
    return os.path.join(cache_dir if isinstance(cache_dir, str) and cache_dir else ".", "library.json")

def library_db_path(config):
    cache_dir = config.get("cache_dir", ".") if isinstance(config, dict) else "."
    return os.path.join(cache_dir if isinstance(cache_dir, str) and cache_dir else ".", "library.sqlite3")


def library_storage_status(config):
    """Return bounded SQLite storage pressure without exposing cache paths."""
    db_path = library_db_path(config)
    if not isinstance(db_path, str) or not db_path or len(db_path) > MAX_LIBRARY_PATH_TEXT:
        return {"database_bytes": 0, "wal_bytes": 0, "shm_bytes": 0, "total_bytes": 0}
    sizes = {}
    for name, path in (("database_bytes", db_path), ("wal_bytes", db_path + "-wal"), ("shm_bytes", db_path + "-shm")):
        try:
            sizes[name] = safe_counter(os.stat(path).st_size)
        except OSError:
            sizes[name] = 0
    sizes["total_bytes"] = safe_counter(sum(sizes.values()))
    return sizes


class LibraryCacheEpoch:
    """Pin one database fingerprint and one read instant for a whole query.

    The page adapters used to fingerprint the database file separately for the
    read and the write, so an index commit that landed between them moved the
    cache key forward: a page built from pre-commit rows became addressable by
    post-commit readers and stayed wrong for the full TTL.  Capturing the
    fingerprint and the read instant once, before the query runs, keeps the key
    stable and lets LibraryQueryCache.put fence the page against the moment the
    database was actually read.
    """

    __slots__ = ("database", "identity", "read_at")

    def __init__(self, config):
        # Keep normalization in LibraryQueryCache.  Materializing an arbitrary
        # iterable here would defeat its bounded key reader and could turn a
        # malformed/future caller into an unbounded allocation.
        self.database = os.path.abspath(library_db_path(config))
        self.identity = _library_database_cache_identity(self.database)
        self.read_at = time.monotonic()

    def get(self, namespace, values):
        return LIBRARY_QUERY_CACHE.get(self.database, namespace, values, self.identity)

    def put(self, namespace, values, result):
        return LIBRARY_QUERY_CACHE.put(
            self.database,
            namespace,
            values,
            result,
            database_identity=self.identity,
            read_at=self.read_at,
        )


def _library_cache_epoch(config):
    return LibraryCacheEpoch(config)


def invalidate_library_query_cache(config):
    LIBRARY_QUERY_CACHE.invalidate_database(library_db_path(config))
    database = os.path.abspath(library_db_path(config))
    with LIBRARY_SUMMARY_CACHE_LOCK:
        LIBRARY_SUMMARY_CACHE.pop(database, None)


def library_query_cache_status():
    return LIBRARY_QUERY_CACHE.snapshot()


LIBRARY_CONNECTION_POOL = LibraryConnectionPool()
LIBRARY_CONNECTION_POOL_CONFIG_KEY = "library_connection_pool"


def _library_connection_pool_enabled(config):
    """Pool read handles only when the runtime opted in; tests keep one per query."""
    return bool(config.get(LIBRARY_CONNECTION_POOL_CONFIG_KEY)) if isinstance(config, dict) else False


def library_connection_pool_config_key():
    """The one public spelling of the switch's configuration key.

    The runtime settings pane has to name this key inside a request payload, but the
    key and its default stay owned by this module.  The startup path once seeded its
    own copy of the value, which `save_config` then dropped from disk; the guard test
    for that bug keeps the name out of the server module, and this accessor is how the
    pane reaches the switch without reviving the bug or loosening the guard.
    """
    return LIBRARY_CONNECTION_POOL_CONFIG_KEY


def library_connection_pool_status():
    return LIBRARY_CONNECTION_POOL.snapshot()


def close_library_connections(config=None):
    """Drain idle library handles so the cache directory can be removed."""
    database = None
    if config is not None:
        database = os.path.abspath(library_db_path(config))
    return LIBRARY_CONNECTION_POOL.drop(database)


def apply_library_connection_pool_config(config):
    """Make the running configuration's pool setting true for idle handles.

    The reader path decides per query whether to borrow, so switching the pool off
    only stops *new* pooling: handles already parked in it would keep the index file
    open while the configuration claims pooling is disabled, which is the exact
    inconsistency that made the switch unsafe to expose. The drain is the re-poolable
    `close_library_connections()`, never the one-way `stop_library_connections()`:
    switching back on has to work without a restart. A config this function cannot
    read a database path from must not leave any handle behind either.
    """
    if _library_connection_pool_enabled(config):
        return 0
    return close_library_connections(config if isinstance(config, dict) else None)


def stop_library_connections(config=None):
    """Drain idle handles *and* stop pooling them: the shutdown-only drain.

    Called once, from `server.shutdown_runtime()`. A reader that is still in flight when
    the runtime winds down (an HTTP handler is the only one left that can reach the index)
    then closes its own handle instead of parking it in the pool, so the drain cannot be
    undone from behind. `close_library_connections()` stays the re-poolable variant for
    the between-scan uses.
    """
    database = None
    if config is not None:
        database = os.path.abspath(library_db_path(config))
    return LIBRARY_CONNECTION_POOL.stop_accepting(database)


def _forget_library_schema(config):
    database = os.path.abspath(library_db_path(config))
    # Any handle opened against a database whose schema state was just dropped
    # may sit in the pool with a stale read snapshot, so forget those handles
    # before the next writer recreates the tables.
    LIBRARY_CONNECTION_POOL.drop(database)
    with LIBRARY_SCHEMA_READY_LOCK:
        LIBRARY_SCHEMA_READY.pop(database, None)
    with LIBRARY_SEARCH_INDEX_LOCK:
        LIBRARY_SEARCH_INDEX_MODE.pop(database, None)


def _library_database_identity(path):
    try:
        stat = os.stat(path)
        return (int(stat.st_dev), int(stat.st_ino))
    except OSError:
        return None


def _library_database_cache_identity(path):
    """Return a main-db/WAL fingerprint so cached pages track committed data."""
    try:
        database_stat = os.stat(path)
    except OSError:
        return None
    try:
        wal_stat = os.stat(path + "-wal")
    except OSError:
        wal_stat = None

    def stat_values(stat):
        if stat is None:
            return (0, 0, 0, 0)
        return (int(stat.st_dev), int(stat.st_ino), int(stat.st_mtime_ns), int(stat.st_size))

    # SQLite WAL commits may not update the main database's mtime or size
    # until checkpointing.  Keep the optional WAL file in the identity so an
    # external writer cannot leave cached pages stale until their TTL expires.
    return stat_values(database_stat) + stat_values(wal_stat)


def _ensure_library_schema_once(config, conn):
    """Run migrations once per live database, not once per HTTP request."""
    database = os.path.abspath(library_db_path(config))
    with LIBRARY_SCHEMA_READY_LOCK:
        identity = _library_database_identity(database)
        if identity is not None and LIBRARY_SCHEMA_READY.get(database) == identity:
            return
        ensure_library_schema(conn)
        _configure_library_search_index(conn, database)
        # sqlite3.connect creates the main file before this code runs.  Keep
        # a conservative fallback for unusual filesystems which cannot expose
        # inode information, rather than allowing migrations to be skipped.
        identity = _library_database_identity(database)
        if identity is not None:
            _bounded_database_state_put(
                LIBRARY_SCHEMA_READY, database, identity, LIBRARY_SCHEMA_READY_LIMIT
            )
        else:
            LIBRARY_SCHEMA_READY.pop(database, None)


def _configure_library_search_index(conn, database):
    """Create an optional FTS5 trigram index without requiring it at runtime."""
    try:
        version = conn.execute("SELECT value FROM library_meta WHERE key = 'search_index_version'").fetchone()
        if not version or str(version["value"] or "") != SEARCH_INDEX_VERSION:
            conn.execute("DROP TABLE IF EXISTS tracks_search")
            conn.execute(
                "CREATE VIRTUAL TABLE tracks_search USING fts5("
                "title,artist,album,album_artist,composer,genre,folder,path,format,"
                "content='tracks', content_rowid='rowid', tokenize='trigram'"
                ")"
            )
            conn.execute("INSERT INTO tracks_search(tracks_search) VALUES ('rebuild')")
            conn.execute(
                "INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)",
                ("search_index_version", SEARCH_INDEX_VERSION),
            )
        mode = "fts5-trigram"
    except sqlite3.OperationalError:
        # Older fnOS builds may ship SQLite without FTS5/trigram. Queries
        # deliberately continue using the original case-insensitive LIKE path.
        mode = "like"
    with LIBRARY_SEARCH_INDEX_LOCK:
        _bounded_database_state_put(
            LIBRARY_SEARCH_INDEX_MODE, database, mode, LIBRARY_SEARCH_INDEX_MODE_LIMIT
        )


def _rebuild_library_search_index(conn, config):
    if _search_index_mode(config) != "fts5-trigram":
        return
    try:
        conn.execute("INSERT INTO tracks_search(tracks_search) VALUES ('rebuild')")
    except sqlite3.OperationalError:
        with LIBRARY_SEARCH_INDEX_LOCK:
            _bounded_database_state_put(
                LIBRARY_SEARCH_INDEX_MODE,
                os.path.abspath(library_db_path(config)),
                "like",
                LIBRARY_SEARCH_INDEX_MODE_LIMIT,
            )

def _prepare_library_connection(config, conn, db_path):
    """Apply the per-connection setup that a borrowed handle already carries."""
    secure_sqlite_files(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA journal_mode=WAL")
    secure_sqlite_files(db_path)
    conn.execute("PRAGMA synchronous=NORMAL")
    _ensure_library_schema_once(config, conn)


@contextmanager
def library_db_connect(config):
    """Yield a library index handle, reusing an idle one when pooling is on.

    Opening the WAL index costs more than the first-screen page query itself, so
    a borrowed handle skips the pragma and schema prologue: those are properties
    of the connection, not of the request. A reused handle only ever returns
    after its own transaction committed, so it cannot carry a stale WAL snapshot
    into the next reader.
    """
    # Every read still hardens the cache directory; only the probe gets cheaper. The
    # drift path is one lstat where the full pass is six syscalls, and it falls back
    # to secure_directory when the directory is missing or is not a directory, so a
    # cache_dir created by an older build or removed underneath us behaves as before.
    secure_directory_on_drift(config["cache_dir"])
    db_path = library_db_path(config)
    pooled = _library_connection_pool_enabled(config)
    database = os.path.abspath(db_path)
    identity = _library_database_identity(db_path) if pooled else None
    conn = LIBRARY_CONNECTION_POOL.borrow(database, identity) if pooled else None
    if conn is None:
        # A driver failure here propagates without the epilogue below, exactly as
        # it did before pooling existed: there is no handle to roll back or close.
        if pooled:
            conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
            # Counted after the driver actually returned a handle, so the hit
            # rate in diagnostics cannot be inflated by a failed open.
            LIBRARY_CONNECTION_POOL.note_created()
        else:
            conn = sqlite3.connect(db_path, timeout=15)
        fresh = True
    else:
        fresh = False
    failed = False
    try:
        if fresh:
            _prepare_library_connection(config, conn, db_path)
        else:
            # Permission refresh stays on every path: a borrowed handle proves the
            # pragmas, not that another process left the index files private.
            secure_sqlite_files(db_path)
        yield conn
        conn.commit()
    except BaseException:
        failed = True
        try:
            conn.rollback()
        except Exception:
            # Preserve the original transaction failure. Rollback is
            # best-effort because a broken or already-closed connection may
            # reject cleanup as well.
            pass
        raise
    finally:
        keep = (
            pooled
            and not failed
            # A patched-out test double must never reach another test through
            # the pool, so only real driver connections are eligible.
            and isinstance(conn, sqlite3.Connection)
        )
        if keep:
            stored = identity
            if stored is None:
                stored = _library_database_identity(db_path)
            keep = LIBRARY_CONNECTION_POOL.release(database, stored, conn)
        close_error = None
        if not keep:
            try:
                conn.close()
            except Exception as exc:
                # On the failure path the rolled-back write is the real error, so
                # a cleanup fault must not hide it. Otherwise close() still
                # matters and is re-raised after the permission refresh below.
                close_error = None if failed else exc
        try:
            secure_sqlite_files(db_path)
        except Exception:
            pass
        if close_error is not None:
            raise close_error

def ensure_library_schema(conn):
    # Older builds could leave stale folders indexes behind after replacing the
    # folders table. Remove those orphans before SQLite parses CREATE INDEX.
    folder_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'folders'"
    ).fetchone()
    if folder_table is None:
        orphan_indexes = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'index' AND name LIKE 'idx_folders%'"
        ).fetchall()
        if orphan_indexes:
            # DROP INDEX asks SQLite to resolve the missing table first and
            # can fail on databases produced by the old migration. Removing
            # only this stale sqlite_master row lets the schema be rebuilt.
            conn.execute("PRAGMA writable_schema = ON")
            conn.execute(
                "DELETE FROM sqlite_master "
                "WHERE type = 'index' AND name LIKE 'idx_folders%'"
            )
            conn.execute("PRAGMA writable_schema = OFF")
            conn.execute("PRAGMA integrity_check")
    _migrate_legacy_tracks_columns(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS library_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tracks (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            root TEXT,
            folder TEXT,
            title TEXT,
            artist TEXT,
            album TEXT,
            track_no INTEGER NOT NULL DEFAULT 0,
            album_artist TEXT,
            composer TEXT,
            genre TEXT,
            format TEXT,
            mime TEXT,
            is_dsd INTEGER NOT NULL DEFAULT 0,
            duration REAL NOT NULL DEFAULT 0,
            size INTEGER NOT NULL DEFAULT 0,
            sample_rate INTEGER NOT NULL DEFAULT 0,
            bit_depth INTEGER NOT NULL DEFAULT 0,
            bitrate INTEGER NOT NULL DEFAULT 0,
            added INTEGER NOT NULL DEFAULT 0,
            added_ns INTEGER NOT NULL DEFAULT 0,
            modified INTEGER NOT NULL DEFAULT 0,
            modified_ns INTEGER NOT NULL DEFAULT 0,
            cue_path TEXT,
            cue_track INTEGER NOT NULL DEFAULT 0,
            cue_start REAL NOT NULL DEFAULT 0,
            cue_end REAL NOT NULL DEFAULT 0,
            metadata_version INTEGER NOT NULL DEFAULT 0,
            item_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tracks_path ON tracks(path);
        CREATE INDEX IF NOT EXISTS idx_tracks_folder ON tracks(folder);
        CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album);
        CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
        CREATE INDEX IF NOT EXISTS idx_tracks_composer ON tracks(composer);
        CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks(genre);
        CREATE INDEX IF NOT EXISTS idx_tracks_added_title_id_asc ON tracks(added_ns ASC, title COLLATE NOCASE ASC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_tracks_added_title_id_desc ON tracks(added_ns DESC, title COLLATE NOCASE ASC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_tracks_root ON tracks(root);
        CREATE INDEX IF NOT EXISTS idx_tracks_root_folder ON tracks(root, folder);
        CREATE INDEX IF NOT EXISTS idx_tracks_root_folder_track_no ON tracks(root, folder, track_no);
        CREATE INDEX IF NOT EXISTS idx_tracks_is_dsd ON tracks(is_dsd);
        CREATE INDEX IF NOT EXISTS idx_tracks_title_nocase ON tracks(title COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_tracks_title_nocase_id_asc ON tracks(title COLLATE NOCASE ASC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_tracks_title_nocase_id_desc ON tracks(title COLLATE NOCASE DESC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_tracks_artist_nocase ON tracks(artist COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_tracks_artist_nocase_title_id_asc ON tracks(artist COLLATE NOCASE ASC, title COLLATE NOCASE ASC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_tracks_artist_nocase_title_id_desc ON tracks(artist COLLATE NOCASE DESC, title COLLATE NOCASE ASC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_tracks_album_nocase ON tracks(album COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_tracks_album_nocase_title_id_asc ON tracks(album COLLATE NOCASE ASC, title COLLATE NOCASE ASC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_tracks_album_nocase_title_id_desc ON tracks(album COLLATE NOCASE DESC, title COLLATE NOCASE ASC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_tracks_format_nocase_title_id_asc ON tracks(format COLLATE NOCASE ASC, title COLLATE NOCASE ASC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_tracks_format_nocase_title_id_desc ON tracks(format COLLATE NOCASE DESC, title COLLATE NOCASE ASC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_tracks_track_no_title_id_asc ON tracks((CASE WHEN track_no <= 0 THEN 2147483647 ELSE track_no END) ASC, title COLLATE NOCASE ASC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_tracks_track_no_title_id_desc ON tracks((CASE WHEN track_no <= 0 THEN 2147483647 ELSE track_no END) DESC, title COLLATE NOCASE ASC, id ASC);
        CREATE INDEX IF NOT EXISTS idx_tracks_folder_nocase ON tracks(folder COLLATE NOCASE);
        CREATE TABLE IF NOT EXISTS albums (
            name TEXT PRIMARY KEY,
            artist TEXT,
            track_count INTEGER NOT NULL DEFAULT 0,
            cover_track_id TEXT
        );
        CREATE TABLE IF NOT EXISTS artists (
            name TEXT PRIMARY KEY,
            track_count INTEGER NOT NULL DEFAULT 0,
            cover_track_id TEXT
        );
        CREATE TABLE IF NOT EXISTS composers (
            name TEXT PRIMARY KEY,
            track_count INTEGER NOT NULL DEFAULT 0,
            cover_track_id TEXT
        );
        CREATE TABLE IF NOT EXISTS genres (
            name TEXT PRIMARY KEY,
            track_count INTEGER NOT NULL DEFAULT 0,
            cover_track_id TEXT
        );
        CREATE TABLE IF NOT EXISTS folders (
            path TEXT PRIMARY KEY,
            root TEXT,
            parent TEXT,
            name TEXT,
            track_count INTEGER NOT NULL DEFAULT 0,
            cover_track_id TEXT
        );
        -- Browse pages order the group tables by `name COLLATE NOCASE <dir>, name ASC`.
        -- The TEXT primary key only gives a binary-collate order, so without these
        -- per-direction indexes SQLite sorts every group for each page.
        CREATE INDEX IF NOT EXISTS idx_albums_name_nocase_asc ON albums(name COLLATE NOCASE ASC, name ASC);
        CREATE INDEX IF NOT EXISTS idx_albums_name_nocase_desc ON albums(name COLLATE NOCASE DESC, name ASC);
        CREATE INDEX IF NOT EXISTS idx_artists_name_nocase_asc ON artists(name COLLATE NOCASE ASC, name ASC);
        CREATE INDEX IF NOT EXISTS idx_artists_name_nocase_desc ON artists(name COLLATE NOCASE DESC, name ASC);
        CREATE INDEX IF NOT EXISTS idx_composers_name_nocase_asc ON composers(name COLLATE NOCASE ASC, name ASC);
        CREATE INDEX IF NOT EXISTS idx_composers_name_nocase_desc ON composers(name COLLATE NOCASE DESC, name ASC);
        CREATE INDEX IF NOT EXISTS idx_genres_name_nocase_asc ON genres(name COLLATE NOCASE ASC, name ASC);
        CREATE INDEX IF NOT EXISTS idx_genres_name_nocase_desc ON genres(name COLLATE NOCASE DESC, name ASC);
        CREATE TABLE IF NOT EXISTS covers (
            track_id TEXT PRIMARY KEY,
            source TEXT,
            folder_path TEXT,
            updated_at INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS cue_tracks (
            track_id TEXT PRIMARY KEY,
            cue_path TEXT NOT NULL,
            audio_path TEXT NOT NULL,
            track_no INTEGER NOT NULL DEFAULT 0,
            start REAL NOT NULL DEFAULT 0,
            end REAL NOT NULL DEFAULT 0
        );
        """
    )
    # New databases used to retain the legacy `folders(path)` primary key
    # because this migration was defined but never invoked. The composite key
    # is required when distinct music roots contain the same folder names.
    _migrate_tracks_columns(conn)
    # The original one-column index cannot satisfy the visible-page title/ID
    # tie-breaker and leaves SQLite to build a temporary sort. The composite
    # indexes created above cover its ordered-read use while keeping recent
    # pages bounded, so remove the redundant legacy index from upgraded DBs.
    conn.execute("DROP INDEX IF EXISTS idx_tracks_added")
    conn.execute("DROP INDEX IF EXISTS idx_tracks_format_nocase")
    conn.execute("DROP INDEX IF EXISTS idx_tracks_track_no")


def _migrate_legacy_tracks_columns(conn):
    """Bring databases created by older fnAudio builds up to the current schema.

    SQLite only applies columns from CREATE TABLE when a table is new.  Older
    installs therefore need explicit ADD COLUMN migrations before an index can
    refer to a column introduced by a later release.
    """
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'tracks'"
    ).fetchone()
    if not exists:
        return
    existing = {
        str(row[1]).lower()
        for row in conn.execute("PRAGMA table_info(tracks)")
    }
    additions = [
        ("root", "TEXT"),
        ("folder", "TEXT"),
        ("title", "TEXT"),
        ("artist", "TEXT"),
        ("album", "TEXT"),
        ("track_no", "INTEGER NOT NULL DEFAULT 0"),
        ("album_artist", "TEXT"),
        ("composer", "TEXT"),
        ("genre", "TEXT"),
        ("format", "TEXT"),
        ("mime", "TEXT"),
        ("is_dsd", "INTEGER NOT NULL DEFAULT 0"),
        ("duration", "REAL NOT NULL DEFAULT 0"),
        ("size", "INTEGER NOT NULL DEFAULT 0"),
        ("sample_rate", "INTEGER NOT NULL DEFAULT 0"),
        ("bit_depth", "INTEGER NOT NULL DEFAULT 0"),
        ("bitrate", "INTEGER NOT NULL DEFAULT 0"),
        ("added", "INTEGER NOT NULL DEFAULT 0"),
        ("added_ns", "INTEGER NOT NULL DEFAULT 0"),
        ("modified", "INTEGER NOT NULL DEFAULT 0"),
        ("modified_ns", "INTEGER NOT NULL DEFAULT 0"),
        ("cue_path", "TEXT"),
        ("cue_track", "INTEGER NOT NULL DEFAULT 0"),
        ("cue_start", "REAL NOT NULL DEFAULT 0"),
        ("cue_end", "REAL NOT NULL DEFAULT 0"),
        ("metadata_version", "INTEGER NOT NULL DEFAULT 0"),
        ("item_json", "TEXT NOT NULL DEFAULT '{}'"),
    ]
    for name, definition in additions:
        if name not in existing:
            conn.execute("ALTER TABLE tracks ADD COLUMN %s %s" % (name, definition))
    return


def _migrate_tracks_columns(conn):
    track_columns = {row["name"] for row in conn.execute("PRAGMA table_info(tracks)")}
    if "track_no" not in track_columns:
        conn.execute("ALTER TABLE tracks ADD COLUMN track_no INTEGER NOT NULL DEFAULT 0")
    folder_columns = [dict(row) for row in conn.execute("PRAGMA table_info(folders)")]
    pk_columns = [row["name"] for row in folder_columns if row.get("pk")]
    if pk_columns == ["path"]:
        conn.execute("DROP TABLE IF EXISTS folders")
        conn.execute(
            """
            CREATE TABLE folders (
                path TEXT NOT NULL,
                root TEXT NOT NULL DEFAULT '',
                parent TEXT,
                name TEXT,
                track_count INTEGER NOT NULL DEFAULT 0,
                cover_track_id TEXT,
                PRIMARY KEY (root, path)
            )
            """
        )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_folders_root_parent ON folders(root, parent)")
    # Browsing one directory lists it as `name COLLATE NOCASE <dir>, path`.  The
    # plain sibling indexes can seek the directory but still leave SQLite to sort
    # every child for a page that shows a hundred of them, so a flat collection
    # with thousands of top-level folders pays tens of milliseconds per folder
    # page.  These per-direction expression indexes let the page stop at its own
    # limit; the binary-collate three-column index never matched the query order
    # once they exist, so it goes.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_folders_root_parent_name_nocase_asc "
        "ON folders(root, parent, name COLLATE NOCASE ASC, path ASC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_folders_root_parent_name_nocase_desc "
        "ON folders(root, parent, name COLLATE NOCASE DESC, path ASC)"
    )
    # `/api/library/folders` can arrive with no `root` filter: the UI only sets the parameter when
    # a root has actually been chosen (app.js:5745), and the player adapter passes whatever it
    # holds straight through (server.py:3154).  A `parent`-only predicate cannot use
    # `idx_folders_root_parent` at all, because that index leads with `root`, so the listing
    # scanned every folder row and sorted the whole thing in a temporary B-tree.  Measured here at
    # 20000 folders: 1.00 ms per page scanned versus 0.05 ms for the root-scoped page, and the
    # item's own numbers were 5.52/14.40 ms at 20000/50000 rows.  One index per browse direction
    # lets the page seek its own parent and stop at its own limit, mirroring the pair the
    # root-scoped path already has.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_folders_parent_name_nocase_asc "
        "ON folders(parent, name COLLATE NOCASE ASC, path ASC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_folders_parent_name_nocase_desc "
        "ON folders(parent, name COLLATE NOCASE DESC, path ASC)"
    )
    conn.execute("DROP INDEX IF EXISTS idx_folders_root_parent_name")
    group_version = conn.execute(
        "SELECT value FROM library_meta WHERE key = 'group_label_version'"
    ).fetchone()
    if not group_version or str(group_version["value"]) != GROUP_LABEL_VERSION:
        conn.execute("DELETE FROM albums")
        conn.execute("DELETE FROM artists")
        conn.execute("DELETE FROM composers")
        conn.execute("DELETE FROM genres")
        if conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]:
            _rebuild_group_table(conn, "albums", "album", "album_artist")
            _rebuild_simple_group(conn, "artists", "artist")
            _rebuild_simple_group(conn, "composers", "composer")
            _rebuild_simple_group(conn, "genres", "genre")
        _refresh_group_counts(conn)
        conn.execute(
            "INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)",
            ("group_label_version", GROUP_LABEL_VERSION),
        )

@contextmanager
def library_db_writer(config):
    """Open an exclusive write handle. Never pooled: a scan must start clean.

    A scan recreates tables and holds a long transaction. Sharing such a handle
    would expose half-written index rows to the reader that borrows it next, so
    every write path keeps the original open-and-close-per-request sequence.
    """
    secure_directory(config["cache_dir"])
    db_path = library_db_path(config)
    conn = sqlite3.connect(db_path, timeout=15)
    failed = False
    try:
        _prepare_library_connection(config, conn, db_path)
        yield conn
        conn.commit()
    except BaseException:
        failed = True
        try:
            conn.rollback()
        except Exception:
            # Preserve the original transaction failure. Rollback is
            # best-effort because a broken or already-closed connection may
            # reject cleanup as well.
            pass
        raise
    finally:
        close_error = None
        try:
            conn.close()
        except Exception as exc:
            close_error = None if failed else exc
        try:
            secure_sqlite_files(db_path)
        except Exception:
            pass
        if close_error is not None:
            raise close_error


NULL_LABEL_COLLAPSE_KEY = "null_label_collapse"


def _collapse_null_labels(conn):
    """Converge one legacy index, once, so no label column holds SQL NULL.

    ``prepare_track_persistence`` no longer writes NULL into a label column, which
    keeps new rows clean; this repairs the rows that predate that rule.  An
    unchanged row is not rewritten by the upsert - it is skipped by the
    ``WHERE tracks.item_json <> excluded.item_json`` guard at the end of the
    statement - so a legacy NULL outlives every later scan on its own.

    The repair is deliberately a migration and not a periodic sweep.  A sweep that
    ran on every save would silently undo any future write path that reintroduced
    NULL, which is exactly the regression the writer-side guard exists to make
    visible; it would also turn a stable cost into one paid per track per scan.
    With the marker stored, an injected NULL survives the next save, and
    ``test_the_null_label_collapse_is_a_one_time_migration_not_a_sweep`` pins that.

    Only the columns are rewritten.  A legacy ``item_json`` still carrying ``null``
    heals by itself: once the scanner reports the same track without the ``None``,
    the two JSON spellings differ, the upsert guard stops skipping the row, and the
    columns and the payload are rewritten together.
    """
    try:
        marked = conn.execute(
            "SELECT value FROM library_meta WHERE key = ?", (NULL_LABEL_COLLAPSE_KEY,)
        ).fetchone()
    except Exception:
        # A library_meta table this old cannot hold the marker either; the collapse
        # still runs, and re-running it is harmless, so nothing is lost.
        marked = None
    if marked is not None:
        return 0
    clauses = " OR ".join("%s IS NULL" % column for column in NULLABLE_LABEL_COLUMNS)
    affected = conn.execute("SELECT COUNT(*) FROM tracks WHERE %s" % clauses).fetchone()[0]
    for column in NULLABLE_LABEL_COLUMNS:
        conn.execute("UPDATE tracks SET %s = '' WHERE %s IS NULL" % (column, column))
    conn.execute(
        "INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)",
        (NULL_LABEL_COLLAPSE_KEY, str(int(affected))),
    )
    return affected


def save_items_to_sqlite(config, items, signature):
    # A scan is also the recovery path after a user clears a broken index.
    # Force migrations here so a recreated database is never mistaken for the
    # old one merely because it has the same cache path.
    _forget_library_schema(config)
    with library_db_writer(config) as conn:
        roots = normalize_library_paths(config)
        normalized_items = normalize_scan_items(
            items,
            roots,
            is_under=_path_under,
            relative_folder=relative_folder_for_path,
            root_label=lambda root: library_root_label(root, config),
        )

        conn.execute("CREATE TEMP TABLE IF NOT EXISTS current_track_ids (id TEXT PRIMARY KEY)")
        conn.execute("DELETE FROM current_track_ids")
        conn.executemany("INSERT OR IGNORE INTO current_track_ids(id) VALUES (?)", [(scan_text(item.get("id")),) for item in normalized_items if isinstance(item.get("id"), str) and item.get("id")])

        # Keep the old and new folder locations in a small temporary table.  A
        # changed track only invalidates its top-level folder subtree; the
        # remaining folder index can stay untouched.
        conn.execute("""
            CREATE TEMP TABLE IF NOT EXISTS current_track_meta (
                id TEXT PRIMARY KEY, root TEXT NOT NULL, folder TEXT NOT NULL,
                album TEXT NOT NULL, album_artist TEXT NOT NULL,
                artist TEXT NOT NULL, composer TEXT NOT NULL, genre TEXT NOT NULL
            )
        """)
        meta_columns = {row["name"] for row in conn.execute("PRAGMA temp.table_info(current_track_meta)")}
        for name in ("album", "album_artist", "artist", "composer", "genre"):
            if name not in meta_columns:
                conn.execute("ALTER TABLE current_track_meta ADD COLUMN %s TEXT NOT NULL DEFAULT ''" % name)
        conn.execute("DELETE FROM current_track_meta")
        conn.executemany(
            """INSERT OR REPLACE INTO current_track_meta(
                id,root,folder,album,album_artist,artist,composer,genre
            ) VALUES (?,?,?,?,?,?,?,?)""",
            [(scan_text(item.get("id")), scan_text(item.get("_index_root")), scan_text(item.get("folder")),
              scan_text(item.get("album")), scan_text(item.get("album_artist")),
              scan_text(item.get("artist")), scan_text(item.get("composer")), scan_text(item.get("genre")))
             for item in normalized_items if isinstance(item.get("id"), str) and item.get("id")],
        )
        conn.execute("CREATE TEMP TABLE IF NOT EXISTS affected_folder_roots (root TEXT NOT NULL, folder TEXT NOT NULL, PRIMARY KEY(root, folder))")
        conn.execute("DELETE FROM affected_folder_roots")
        conn.execute("""
            INSERT OR IGNORE INTO affected_folder_roots(root, folder)
            SELECT old.root, old.folder
            FROM tracks old
            LEFT JOIN current_track_meta current ON current.id = old.id
            WHERE current.id IS NULL
              AND COALESCE(old.folder, '') <> ''
        """)
        conn.execute("""
            INSERT OR IGNORE INTO affected_folder_roots(root, folder)
            SELECT old.root, old.folder
            FROM tracks old
            JOIN current_track_meta current ON current.id = old.id
            WHERE COALESCE(old.root, '') <> COALESCE(current.root, '')
               OR COALESCE(old.folder, '') <> COALESCE(current.folder, '')
        """)
        conn.execute("""
            INSERT OR IGNORE INTO affected_folder_roots(root, folder)
            SELECT current.root, current.folder
            FROM current_track_meta current
            LEFT JOIN tracks old ON old.id = current.id
            WHERE COALESCE(current.folder, '') <> ''
              AND (old.id IS NULL
               OR COALESCE(old.root, '') <> COALESCE(current.root, '')
               OR COALESCE(old.folder, '') <> COALESCE(current.folder, ''))
        """)
        # Capture old group labels before the upsert replaces the old row.
        _refresh_group_tables_for_changes(conn)
        conn.execute("DELETE FROM tracks WHERE id NOT IN (SELECT id FROM current_track_ids)")
        conn.execute("DELETE FROM covers WHERE track_id NOT IN (SELECT id FROM current_track_ids)")
        conn.execute("DELETE FROM cue_tracks WHERE track_id NOT IN (SELECT id FROM current_track_ids)")
        track_upsert_sql = """
            INSERT INTO tracks (
                id,path,root,folder,title,artist,album,track_no,album_artist,composer,genre,format,mime,is_dsd,
                duration,size,sample_rate,bit_depth,bitrate,added,added_ns,modified,modified_ns,
                cue_path,cue_track,cue_start,cue_end,metadata_version,item_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                path=excluded.path, root=excluded.root, folder=excluded.folder, title=excluded.title,
                artist=excluded.artist, album=excluded.album, track_no=excluded.track_no,
                album_artist=excluded.album_artist, composer=excluded.composer, genre=excluded.genre,
                format=excluded.format, mime=excluded.mime, is_dsd=excluded.is_dsd, duration=excluded.duration,
                size=excluded.size, sample_rate=excluded.sample_rate, bit_depth=excluded.bit_depth,
                bitrate=excluded.bitrate, added=excluded.added, added_ns=excluded.added_ns,
                modified=excluded.modified, modified_ns=excluded.modified_ns, cue_path=excluded.cue_path,
                cue_track=excluded.cue_track, cue_start=excluded.cue_start, cue_end=excluded.cue_end,
                metadata_version=excluded.metadata_version, item_json=excluded.item_json
            WHERE tracks.item_json <> excluded.item_json
        """
        prepared_batches = iter_track_persistence_batches(
            normalized_items,
            LIBRARY_WRITE_BATCH_SIZE,
            prepare=lambda item: prepare_track_persistence(
                item, safe_int=safe_int, safe_float=safe_float,
                dumps=lambda value: json.dumps(value, ensure_ascii=False),
            ),
        )
        updated_at = int(time.time())
        for batch in prepared_batches:
            conn.executemany(track_upsert_sql, [row for row, _cue, _path, _item in batch])
            cue_rows = [cue_row for _row, cue_row, _path, _item in batch if cue_row]
            if cue_rows:
                conn.executemany(
                    "INSERT OR REPLACE INTO cue_tracks (track_id,cue_path,audio_path,track_no,start,end) VALUES (?,?,?,?,?,?)",
                    cue_rows,
                )
            conn.executemany(
                "INSERT OR REPLACE INTO covers (track_id,source,folder_path,updated_at) VALUES (?,?,?,?)",
                [(scan_text(canonical_item.get("id")), "indexed", os.path.dirname(path), updated_at)
                 for _row, _cue_row, path, canonical_item in batch],
            )
        # A stable track ID can change from a CUE segment back into an ordinary
        # file.  The old per-row write only added CUE rows, which left the
        # obsolete segment index live until the entire track vanished.
        conn.execute("""
            DELETE FROM cue_tracks
            WHERE track_id IN (SELECT id FROM current_track_ids)
              AND NOT EXISTS (
                  SELECT 1 FROM tracks
                  WHERE tracks.id = cue_tracks.track_id
                    AND COALESCE(tracks.cue_path, '') <> ''
              )
        """)
        # Runs after the upserts so a rewritten row is not counted as legacy, and
        # before the collected change set is turned into the group tables, the folder
        # index, and the search index.  None of that tail can observe the order: both
        # spellings fold into UNCLASSIFIED through ``COALESCE(NULLIF(artist, ''), ?)``,
        # folders never read a label, and an external-content FTS5 row indexes NULL and
        # "" as the same empty text.  So moving this call below them is a mutation this
        # suite cannot catch (R125 V17) - the ordering is defensive, and the consumer
        # the collapse exists for is the read path in ``query_library_page``.
        _collapse_null_labels(conn)
        _refresh_group_tables_for_changes(conn, collect=False)
        _rebuild_folders_for_changes(conn)
        conn.execute("INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)", ("library_path", display_library_path(config)))
        conn.execute("INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)", ("signature", signature))
        conn.execute("INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)", ("metadata_version", str(METADATA_VERSION)))
        conn.execute("INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)", ("track_count", str(len(normalized_items))))
        conn.execute(
            "INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)",
            ("dsd_count", str(sum(1 for item in normalized_items if item.get("is_dsd"))),),
        )
        _refresh_group_counts(conn)
        conn.execute(
            "INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)",
            ("root_summary", json.dumps(root_index_summary(normalized_items, roots), ensure_ascii=False, separators=(",", ":"))),
        )
        conn.execute("INSERT OR REPLACE INTO library_meta (key,value) VALUES (?,?)", ("saved_at", str(int(time.time()))))
        _rebuild_library_search_index(conn, config)
    invalidate_library_query_cache(config)

def load_items_from_sqlite(config):
    if not os.path.isfile(library_db_path(config)):
        return None
    with library_db_connect(config) as conn:
        meta = {row["key"]: row["value"] for row in conn.execute("SELECT key,value FROM library_meta")}
        if meta.get("library_path") != display_library_path(config):
            return None
        if str(meta.get("metadata_version") or "") != str(METADATA_VERSION):
            return None
        items = decode_item_rows(conn.execute("SELECT item_json FROM tracks ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE, title COLLATE NOCASE"))
        return {"items": items, "signature": meta.get("signature", "")}

def library_summary_from_sqlite(config):
    db_path = library_db_path(config)
    if not os.path.isfile(db_path):
        return {}
    database = os.path.abspath(db_path)
    fingerprint = _library_database_cache_identity(db_path)
    if fingerprint is None:
        return {}
    def cached_summary():
        now = time.monotonic()
        with LIBRARY_SUMMARY_CACHE_LOCK:
            cached = LIBRARY_SUMMARY_CACHE.get(database)
            if (cached and len(cached) >= 3 and cached[2] == fingerprint
                    and now - cached[0] < LIBRARY_SUMMARY_CACHE_TTL_SECONDS):
                return dict(cached[1])
        return None

    cached = cached_summary()
    if cached is not None:
        return cached

    leader = False
    completion = None
    with LIBRARY_SUMMARY_CACHE_LOCK:
        # Recheck after acquiring the coordination lock: another request may
        # have completed between the optimistic cache lookup and this point.
        cached = LIBRARY_SUMMARY_CACHE.get(database)
        now = time.monotonic()
        if (cached and len(cached) >= 3 and cached[2] == fingerprint
                and now - cached[0] < LIBRARY_SUMMARY_CACHE_TTL_SECONDS):
            return dict(cached[1])
        completion = LIBRARY_SUMMARY_INFLIGHT.get(database)
        if completion is None and len(LIBRARY_SUMMARY_INFLIGHT) < LIBRARY_SUMMARY_INFLIGHT_LIMIT:
            completion = threading.Event()
            LIBRARY_SUMMARY_INFLIGHT[database] = completion
            leader = True

    if not leader and completion is not None:
        # Do not let a stuck filesystem/SQLite operation hold status callers
        # forever. A timed-out follower safely falls back to its own bounded
        # read, while normal bursts reuse the leader's cache entry below.
        completion.wait(2.0)
        cached = cached_summary()
        if cached is not None:
            return cached
    try:
        with library_db_connect(config) as conn:
            meta = {row["key"]: row["value"] for row in conn.execute("SELECT key,value FROM library_meta")}
            if meta.get("library_path") != display_library_path(config):
                return {}
            if str(meta.get("metadata_version") or "") != str(METADATA_VERSION):
                return {}
            count = None
            dsd_count = None
            count = safe_int(meta.get("track_count"), -1)
            dsd_count = safe_int(meta.get("dsd_count"), -1)
            if count < 0 or dsd_count < 0:
                count = None
                dsd_count = None
            else:
                count = safe_counter(count)
                dsd_count = safe_counter(dsd_count)
            if count is None or dsd_count is None:
                row = conn.execute(
                    "SELECT COUNT(*) AS count, SUM(CASE WHEN is_dsd = 1 THEN 1 ELSE 0 END) AS dsd_count FROM tracks"
                ).fetchone()
                count = safe_counter(row["count"] if row else 0)
                dsd_count = safe_counter(row["dsd_count"] if row else 0)
            summary = {
                "count": count,
                "dsd_count": dsd_count,
                "signature": meta.get("signature", ""),
            }
            with LIBRARY_SUMMARY_CACHE_LOCK:
                while len(LIBRARY_SUMMARY_CACHE) >= LIBRARY_SUMMARY_CACHE_LIMIT and database not in LIBRARY_SUMMARY_CACHE:
                    LIBRARY_SUMMARY_CACHE.pop(next(iter(LIBRARY_SUMMARY_CACHE)), None)
                while len(LIBRARY_SUMMARY_CACHE) > LIBRARY_SUMMARY_CACHE_LIMIT:
                    LIBRARY_SUMMARY_CACHE.pop(next(iter(LIBRARY_SUMMARY_CACHE)), None)
                LIBRARY_SUMMARY_CACHE[database] = (time.monotonic(), dict(summary), fingerprint)
            return summary
    except Exception:
        return {}
    finally:
        if leader and completion is not None:
            with LIBRARY_SUMMARY_CACHE_LOCK:
                if LIBRARY_SUMMARY_INFLIGHT.get(database) is completion:
                    LIBRARY_SUMMARY_INFLIGHT.pop(database, None)
                    completion.set()

def _rebuild_group_table(conn, table, column, artist_column):
    conn.execute(
        f"""
        INSERT OR REPLACE INTO {table} (name, artist, track_count, cover_track_id)
        SELECT COALESCE(NULLIF({column}, ''), ?),
               COALESCE(NULLIF(MIN(NULLIF({artist_column}, '')), ''), NULLIF(MIN(NULLIF(artist, '')), ''), ?),
               COUNT(*), MIN(id)
        FROM tracks GROUP BY COALESCE(NULLIF({column}, ''), ?)
        """,
        (UNCLASSIFIED, UNCLASSIFIED, UNCLASSIFIED),
    )

def _rebuild_simple_group(conn, table, column):
    conn.execute(
        f"""
        INSERT OR REPLACE INTO {table} (name, track_count, cover_track_id)
        SELECT COALESCE(NULLIF({column}, ''), ?), COUNT(*), MIN(id)
        FROM tracks GROUP BY COALESCE(NULLIF({column}, ''), ?)
        """,
        (UNCLASSIFIED, UNCLASSIFIED),
    )


def _refresh_group_tables_for_changes(conn, collect=True):
    """Refresh only group labels whose tracks were added, removed, or edited."""
    if collect:
        conn.execute("""
            CREATE TEMP TABLE IF NOT EXISTS affected_group_labels (
                table_name TEXT NOT NULL, name TEXT NOT NULL,
                PRIMARY KEY(table_name, name)
            )
        """)
        conn.execute("DELETE FROM affected_group_labels")
        specs = (
            ("albums", "album", "album_artist", "album", "album_artist"),
            ("artists", "artist", None, "artist", "artist"),
            ("composers", "composer", None, "composer", "composer"),
            ("genres", "genre", None, "genre", "genre"),
        )
        for table, old_column, old_artist, new_column, new_artist in specs:
            old_label = "COALESCE(NULLIF(old.%s, ''), ?)" % old_column
            new_label = "COALESCE(NULLIF(current.%s, ''), ?)" % new_column
            changed = "COALESCE(old.%s, '') <> COALESCE(current.%s, '')" % (old_column, new_column)
            if old_artist:
                changed += " OR COALESCE(old.%s, '') <> COALESCE(current.%s, '')" % (old_artist, new_artist)
            conn.execute(
                """
                INSERT OR IGNORE INTO affected_group_labels(table_name, name)
                SELECT ?, %s
                FROM tracks old LEFT JOIN current_track_meta current ON current.id = old.id
                WHERE current.id IS NULL OR (%s)
                """ % (old_label, changed),
                (table, UNCLASSIFIED),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO affected_group_labels(table_name, name)
                SELECT ?, %s
                FROM current_track_meta current LEFT JOIN tracks old ON old.id = current.id
                WHERE old.id IS NULL OR (%s)
                """ % (new_label, changed),
                (table, UNCLASSIFIED),
            )
    for table, column, artist_column in (
        ("albums", "album", "album_artist"),
        ("artists", "artist", None),
        ("composers", "composer", None),
        ("genres", "genre", None),
    ):
        labels = [row["name"] for row in conn.execute(
            "SELECT name FROM affected_group_labels WHERE table_name = ?", (table,)
        )]
        if not labels:
            continue
        conn.executemany("DELETE FROM %s WHERE name = ?" % table, [(label,) for label in labels])
        for label in labels:
            if artist_column:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO albums(name, artist, track_count, cover_track_id)
                    SELECT ?,
                           COALESCE(NULLIF(MIN(NULLIF(album_artist, '')), ''), NULLIF(MIN(NULLIF(artist, '')), ''), ?),
                           COUNT(*), MIN(id)
                    FROM tracks WHERE COALESCE(NULLIF(album, ''), ?) = ?
                    HAVING COUNT(*) > 0
                    """,
                    (label, UNCLASSIFIED, UNCLASSIFIED, label),
                )
            else:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO %s(name, track_count, cover_track_id)
                    SELECT ?, COUNT(*), MIN(id)
                    FROM tracks WHERE COALESCE(NULLIF(%s, ''), ?) = ?
                    HAVING COUNT(*) > 0
                    """ % (table, column),
                    (label, UNCLASSIFIED, label),
                )

def _rebuild_folders(conn):
    folders = {}
    for row in conn.execute("SELECT id, folder, root FROM tracks WHERE COALESCE(folder, '') <> '' ORDER BY folder COLLATE NOCASE, id"):
        root = row["root"] or ""
        parts = [part for part in (row["folder"] or "").split("/") if part]
        for index in range(1, len(parts) + 1):
            folder = "/".join(parts[:index])
            parent = "/".join(parts[:index - 1])
            key = (root, folder)
            current = folders.setdefault(key, {"root": root, "path": folder, "parent": parent, "name": parts[index - 1], "track_count": 0, "cover_track_id": row["id"]})
            current["track_count"] += 1
            if not current.get("cover_track_id"):
                current["cover_track_id"] = row["id"]
    for row in folders.values():
        conn.execute(
            "INSERT OR REPLACE INTO folders (path, root, parent, name, track_count, cover_track_id) VALUES (?,?,?,?,?,?)",
            (row["path"], row["root"], row["parent"], row["name"], row["track_count"], row["cover_track_id"]),
        )


def _rebuild_folders_for_changes(conn):
    """Refresh only folder trees touched by added, removed, or moved tracks.

    Rebuilding the whole top-level tree of every change is what keeps the
    invariant the recursive folder-search closure relies on: a folder that
    still holds a track can never be missing a row, or a parent row, while
    the tracks table already has it. That shape is asserted by
    test_incremental_folder_refresh_keeps_the_track_folder_closure_complete
    in src/tests/test_library_sqlite.py.
    """
    affected = set()
    for row in conn.execute("SELECT root, folder FROM affected_folder_roots"):
        folder = str(row["folder"] or "").strip("/")
        if folder:
            # Rebuilding the first folder below a library root also refreshes
            # every descendant and keeps all ancestor counts consistent.
            affected.add((str(row["root"] or ""), folder.split("/", 1)[0]))
    for root, top_folder in affected:
        escaped = top_folder.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        prefix = escaped + "/%"
        conn.execute(
            "DELETE FROM folders WHERE root = ? AND (path = ? OR path LIKE ? ESCAPE '\\')",
            (root, top_folder, prefix),
        )
        folders = {}
        for row in conn.execute(
            """
            SELECT id, folder FROM tracks
            WHERE root = ? AND (folder = ? OR folder LIKE ? ESCAPE '\\')
            ORDER BY folder COLLATE NOCASE, id
            """,
            (root, top_folder, prefix),
        ):
            parts = [part for part in (row["folder"] or "").split("/") if part]
            for index in range(1, len(parts) + 1):
                folder = "/".join(parts[:index])
                parent = "/".join(parts[:index - 1])
                key = (root, folder)
                current = folders.setdefault(
                    key,
                    {"root": root, "path": folder, "parent": parent,
                     "name": parts[index - 1], "track_count": 0,
                     "cover_track_id": row["id"]},
                )
                current["track_count"] += 1
        for row in folders.values():
            conn.execute(
                "INSERT OR REPLACE INTO folders (path, root, parent, name, track_count, cover_track_id) VALUES (?,?,?,?,?,?)",
                (row["path"], row["root"], row["parent"], row["name"], row["track_count"], row["cover_track_id"]),
            )

def _path_under(path, root):
    try:
        path = os.path.realpath(os.path.abspath(path))
        root = os.path.realpath(os.path.abspath(root))
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def is_library_item_path(config, path):
    if not isinstance(path, str) or len(path) > MAX_LIBRARY_PATH_TEXT:
        return False
    value = path.strip()
    return bool(value) and any(_path_under(value, root) for root in normalize_library_paths(config))

def load_library_cache(config):
    summary = library_summary_from_sqlite(config)
    if summary:
        MUSIC_CACHE["items"] = []
        MUSIC_CACHE["stamp"] = time.time()
        FS_CACHE["signature"] = summary.get("signature", "")
        return
    try:
        cache_path = library_cache_path(config)
        if os.path.getsize(cache_path) > LIBRARY_JSON_CACHE_MAX_BYTES:
            return
        with open(cache_path, "rb") as fh:
            raw = fh.read(LIBRARY_JSON_CACHE_MAX_BYTES + 1)
        if len(raw) > LIBRARY_JSON_CACHE_MAX_BYTES:
            return
        data = json.loads(raw.decode("utf-8"))
        projected = project_legacy_cache(data, display_library_path(config))
        if projected is None:
            return
        MUSIC_CACHE["items"] = projected["items"]
        MUSIC_CACHE["stamp"] = time.time()
        FS_CACHE["signature"] = projected["signature"]
        save_items_to_sqlite(config, MUSIC_CACHE["items"], FS_CACHE["signature"])
    except (OSError, TypeError, ValueError, UnicodeError):
        _record_library_cache_failure("load")

def save_library_cache(config, items=None, signature=None):
    """Persist a scan snapshot before publishing it to in-memory readers."""
    snapshot_items = MUSIC_CACHE["items"] if items is None else items
    snapshot_signature = FS_CACHE["signature"] if signature is None else signature
    try:
        secure_directory(config["cache_dir"])
        save_items_to_sqlite(config, snapshot_items, snapshot_signature)
    except (OSError, sqlite3.Error):
        _record_library_cache_failure("save")
        return False
    try:
        # SQLite is the authoritative index. Keep the legacy JSON fallback
        # useful for smaller libraries without serializing a large library a
        # second time after every scan.
        cached_items = snapshot_items if len(snapshot_items) <= LIBRARY_JSON_CACHE_LIMIT else []
        payload = {
            "library_path": display_library_path(config),
            "signature": snapshot_signature,
            "items": cached_items,
            "sqlite": True,
        }
        atomic_write_json(library_cache_path(config), payload)
        # Thumbnail work is intentionally deferred until the SQLite index is
        # durable. It runs outside the scan path and therefore never delays
        # library availability after an update.
        from cover_cache import prewarm_library_thumbnails
        prewarm_library_thumbnails(snapshot_items, config, read_cover_for_item)
    except OSError:
        _record_library_cache_failure("save")
    return True

def stop_library_watcher(wait=True, timeout=2.0):
    """Stop the background library watcher and release its inotify handle."""
    global LIBRARY_WATCH_CURRENT_STOP_EVENT
    with LIBRARY_WATCH_LOCK:
        LIBRARY_WATCH_STOP_EVENT.set()
        if LIBRARY_WATCH_CURRENT_STOP_EVENT is not None:
            LIBRARY_WATCH_CURRENT_STOP_EVENT.set()
        thread = LIBRARY_WATCH_THREAD
    if wait and thread is not None and thread is not threading.current_thread():
        thread.join(_bounded_wait_timeout(timeout, 2.0))


def start_library_watcher(config):
    """Start the watcher without publishing a thread that failed to start."""
    global LIBRARY_WATCH_THREAD, LIBRARY_WATCH_CURRENT_STOP_EVENT
    with LIBRARY_WATCH_LOCK:
        existing = LIBRARY_WATCH_THREAD
        if existing is not None and existing.is_alive():
            return existing
        LIBRARY_WATCH_STOP_EVENT.clear()
        stop_event = threading.Event()
        LIBRARY_WATCH_CURRENT_STOP_EVENT = stop_event
        thread = threading.Thread(target=watch_library, args=(config, stop_event), daemon=True)
        # Publish before starting so concurrent configuration reloads see the
        # reservation even while Thread.start() is still in progress.
        LIBRARY_WATCH_THREAD = thread
        try:
            thread.start()
        except Exception:
            if LIBRARY_WATCH_THREAD is thread:
                LIBRARY_WATCH_THREAD = None
            if LIBRARY_WATCH_CURRENT_STOP_EVENT is stop_event:
                LIBRARY_WATCH_CURRENT_STOP_EVENT = None
            LIBRARY_WATCH_STOP_EVENT.set()
            stop_event.set()
            raise
        return thread


def watch_library(config, _stop_event=None):
    global LIBRARY_CHANGE_MONITOR, LIBRARY_WATCH_THREAD, LIBRARY_WATCH_CURRENT_STOP_EVENT
    stop_event = _stop_event if _stop_event is not None else LIBRARY_WATCH_STOP_EVENT
    with LIBRARY_WATCH_LOCK:
        LIBRARY_WATCH_THREAD = threading.current_thread()
    monitor = None
    try:
        while not stop_event.is_set():
            roots = tuple(normalize_library_paths(config))
            if monitor is None or monitor.roots != roots:
                if monitor is not None:
                    monitor.stop()
                monitor = LibraryChangeMonitor(roots)
                monitor.start()
                LIBRARY_CHANGE_MONITOR = monitor
            try:
                refresh_library_if_changed(config, change_monitor=monitor)
                cleanup_transcode_cache_if_due(config)
            except Exception:
                pass
            stop_event.wait(180)
    finally:
        if monitor is not None:
            monitor.stop()
        if LIBRARY_CHANGE_MONITOR is monitor:
            LIBRARY_CHANGE_MONITOR = None
        with LIBRARY_WATCH_LOCK:
            if LIBRARY_WATCH_THREAD is threading.current_thread():
                LIBRARY_WATCH_THREAD = None
            if LIBRARY_WATCH_CURRENT_STOP_EVENT is stop_event:
                LIBRARY_WATCH_CURRENT_STOP_EVENT = None

def find_ffprobe(config):
    configured = config.get("ffprobe_path")
    ffmpeg = find_ffmpeg(config)
    candidates = [
        configured,
        ffmpeg.replace("ffmpeg.exe", "ffprobe.exe") if ffmpeg.endswith("ffmpeg.exe") else "",
        ffmpeg.replace("ffmpeg", "ffprobe") if ffmpeg else "",
        "/usr/trim/lib/mediasrv/bin/ffprobe",
        "/usr/trim/bin/ffprobe",
        "/usr/local/bin/ffprobe",
        "/usr/bin/ffprobe",
        shutil.which("ffprobe"),
        shutil.which("ffprobe.exe"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return ""

def read_audio_info(path, config=None):
    return _read_audio_info(
        path,
        config,
        ffprobe_resolver=find_ffprobe,
        native_reader=read_native_audio_info,
    )
