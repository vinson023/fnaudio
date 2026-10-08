"""Read-only discovery of a library index an earlier install left on disk.

fnOS moves an application data root when the install type changes: a
volume-rooted package keeps its configuration under ``/vol<N>/@appconf/<app>``
while a system-partition package puts the same directory under
``/usr/local/apps/@appconf/<app>``.  Neither upgrade carries the scan cache
across, so the first scan after such a move starts from an empty index and
re-probes every track with ffprobe.  For a library in the tens of thousands
that is measured in tens of hours; the scan then reaches
``scan_timeout_seconds`` and publishes nothing, which is what makes the
interface look permanently empty.

This module only ever reads.  It never copies, rewrites, or deletes an index:
a second writer against a database another service root may still hold open
is exactly how the ``database is locked`` scan failures recorded in
CHANGELOG_AI.md were produced.  Every filesystem question is injected so the
policy is testable without a disk, and the SQLite handle is opened read-only
and refuses a database whose write-ahead journal is still non-empty.
"""

from __future__ import annotations

import os
import posixpath
import re
import sqlite3
from contextlib import contextmanager

from library_rows import decode_item_rows

APP_CONFIG_SEGMENT = "@appconf"
CACHE_DIR_BASENAME = "transcode"
INDEX_BASENAME = "library.sqlite3"
WAL_SUFFIX = "-wal"
SYSTEM_APP_ROOT = "/usr/local/apps"
MAX_APP_NAME_LENGTH = 64
MAX_VOLUME_ROOT_DIGITS = 6
MAX_HANDOVER_CANDIDATES = 16
MAX_HANDOVER_ITEMS = 500000

META_SQL = "SELECT key,value FROM library_meta"
TRACKS_SQL = "SELECT item_json FROM tracks LIMIT ?"

_APP_NAME_RE = re.compile("[A-Za-z0-9._-]{1,64}")
_VOLUME_ROOT_PREFIX = "vol"


def is_volume_root_name(name):
    """Accept ``vol`` plus a positive, ASCII, bounded digit run and nothing else."""
    if not isinstance(name, str) or not name.startswith(_VOLUME_ROOT_PREFIX):
        return False
    digits = name[len(_VOLUME_ROOT_PREFIX):]
    if not digits or len(digits) > MAX_VOLUME_ROOT_DIGITS:
        return False
    # ``str.isdigit`` also accepts superscripts and non-ASCII decimal forms,
    # none of which can name a real mount point.
    if not all("0" <= char <= "9" for char in digits):
        return False
    return digits[0] != "0"


def is_valid_app_name(name):
    """Bound the package name so no candidate can smuggle a path separator."""
    if not isinstance(name, str) or len(name) > MAX_APP_NAME_LENGTH:
        return False
    if name in (".", "..") or ".." in name:
        return False
    return _APP_NAME_RE.fullmatch(name) is not None


def _path_parts(value):
    """Split an absolute POSIX path into meaningful segments, or refuse it."""
    if not isinstance(value, str) or not value.startswith("/"):
        return None
    parts = [part for part in value.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        return None
    return parts


def split_cache_dir(cache_dir):
    """Return ``(app_root, app_name)`` for the shipped config directory shape."""
    parts = _path_parts(cache_dir)
    if parts is None or len(parts) < 4:
        return None
    if parts[-1] != CACHE_DIR_BASENAME or parts[-3] != APP_CONFIG_SEGMENT:
        return None
    app_name = parts[-2]
    if not is_valid_app_name(app_name):
        return None
    return "/" + "/".join(parts[:-3]), app_name


def _volume_root_path(entry):
    """Normalise one candidate application root, keeping only ``/<vol<N>>``."""
    if not isinstance(entry, str):
        return None
    if entry.startswith("/"):
        parts = _path_parts(entry)
        if parts is None or len(parts) != 1:
            return None
        name = parts[0]
    else:
        if not entry or "/" in entry or entry in (".", ".."):
            return None
        name = entry
    return "/" + name if is_volume_root_name(name) else None


def candidate_cache_dirs(cache_dir, extra_roots):
    """Probe other install roots for a legacy index; never the active root."""
    split = split_cache_dir(cache_dir)
    if split is None:
        return []
    app_root, app_name = split
    roots = []
    seen = {app_root}
    for entry in extra_roots or ():
        root = _volume_root_path(entry)
        if root is None or root in seen:
            continue
        seen.add(root)
        roots.append(root)
    if SYSTEM_APP_ROOT not in seen and len(roots) < MAX_HANDOVER_CANDIDATES:
        roots.append(SYSTEM_APP_ROOT)
    return [
        posixpath.join(root, APP_CONFIG_SEGMENT, app_name, CACHE_DIR_BASENAME)
        for root in roots[:MAX_HANDOVER_CANDIDATES]
    ]


def index_path_for_cache_dir(cache_dir):
    if not isinstance(cache_dir, str) or not cache_dir:
        return ""
    return posixpath.join(cache_dir, INDEX_BASENAME)


def validate_index_payload(meta, library_path, metadata_version):
    """Refuse an index built for a different library root or tag version."""
    if not isinstance(meta, dict):
        return False
    if not isinstance(library_path, str) or not library_path:
        return False
    if meta.get("library_path") != library_path:
        return False
    return str(meta.get("metadata_version") or "") == str(metadata_version)


def wal_is_pending(db_path, file_exists=None, file_size=None):
    """True when the side journal still holds pages that were never folded in."""
    exists = file_exists or os.path.isfile
    size = file_size or os.path.getsize
    wal_path = db_path + WAL_SUFFIX
    try:
        if not exists(wal_path):
            return False
        return size(wal_path) > 0
    except OSError:
        # A journal that cannot be stat-ed is a journal that may still be live.
        return True


def default_list_root(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


@contextmanager
def read_only_connection(uri):
    """Open a handle that cannot commit a single page into the legacy index."""
    conn = sqlite3.connect(uri, uri=True, timeout=1.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def read_index_items(db_path, *, library_path, metadata_version, connect=None,
                     decode_rows=None, is_link=None, is_file=None, file_size=None):
    """Return the tracks of one legacy index, or an empty list for any doubt."""
    if not isinstance(db_path, str) or not db_path.startswith("/"):
        return []
    link_probe = is_link or os.path.islink
    file_probe = is_file or os.path.isfile
    try:
        if link_probe(db_path):
            return []
        if not file_probe(db_path):
            return []
        if wal_is_pending(db_path, file_exists=file_probe, file_size=file_size):
            return []
    except Exception:
        return []
    opener = connect or read_only_connection
    decoder = decode_rows or decode_item_rows
    limit = MAX_HANDOVER_ITEMS + 1
    try:
        with opener("file:%s?mode=ro" % db_path) as conn:
            meta = {row["key"]: row["value"] for row in conn.execute(META_SQL)}
            if not validate_index_payload(meta, library_path, metadata_version):
                return []
            items = decoder(conn.execute(TRACKS_SQL, (limit,)))
    except Exception:
        return []
    if not isinstance(items, list):
        return []
    if not items or len(items) > MAX_HANDOVER_ITEMS:
        return []
    return items


def _normalise(path):
    if not isinstance(path, str) or not path:
        return ""
    return posixpath.normpath(path)


def find_reuse_items(cache_dir, *, library_path, metadata_version, list_root=None,
                     active_db_path=None, read_items=None):
    """Return ``(items, source_cache_dir)`` for the first reusable legacy index."""
    root_list = list_root or default_list_root
    reader = read_items or read_index_items
    try:
        entries = root_list("/")
    except Exception:
        entries = []
    active = _normalise(active_db_path)
    for candidate in candidate_cache_dirs(cache_dir, entries):
        db_path = index_path_for_cache_dir(candidate)
        if active and _normalise(db_path) == active:
            continue
        try:
            items = reader(db_path, library_path=library_path, metadata_version=metadata_version)
        except Exception:
            items = []
        if items:
            return list(items), candidate
    return [], ""