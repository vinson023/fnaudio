from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterable

from file_permissions import secure_directory, secure_sqlite_files
from state_count_policy import (CHILD_INTEGRITY_VERIFIED,
                                child_integrity_is_recorded,
                                children_are_within_budget)
from state_projection import (MAX_STATE_PAYLOAD_BYTES as STATE_PAYLOAD_LIMIT,
                              MAX_STATE_TEXT_BYTES,
                              MAX_PLAYLIST_TRACK_IDS_TOTAL,
                              playback_queue_ids,
                              load_json_bounded as _load_json_bounded,
                              dump_json_bounded_strict as _dump_json_bounded,
                              mapping_or_empty as _mapping_or_empty,
                              playlists as _playlists,
                              strings as _strings,
                              ui_preferences as _ui_preferences)


class StateConflict(Exception):
    pass


# Playback controls can arrive concurrently from several browser tabs or
# DLNA callbacks. Serialize writes inside this process before SQLite has to
# contend for its write lock; the busy timeout still covers separate workers.
_STATE_WRITE_LOCK = threading.RLock()
MAX_STATE_PAYLOAD_BYTES = STATE_PAYLOAD_LIMIT
MAX_PERSISTED_PLAYLISTS = 1000
MAX_PERSISTED_TRACK_IDS = 10000
MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL = MAX_PLAYLIST_TRACK_IDS_TOTAL
MAX_PERSISTED_FAVORITES = 50000
# Request-side bounds: how much a single patch or save may carry.  These are deliberately
# separate from the MAX_PERSISTED_* retention bounds.  Favorites and playlist deletions
# coincide with a retention number by history, not by meaning: a request bound stops one
# client from making the server parse an unbounded list, a retention bound decides what
# survives on disk.  Merging them would make a retention change silently alter what a
# client is allowed to send.
MAX_REQUEST_FAVORITES = 50000
MAX_REQUEST_PLAYLIST_DELETIONS = 1000

MAX_CACHE_DIR_TEXT = 4096
MAX_STATE_REVISION = 10**12


def _cache_directory(config: Dict[str, Any]) -> str:
    if not isinstance(config, dict):
        return os.path.abspath(".")
    try:
        raw = config.get("cache_dir", "")
    except Exception:
        raw = ""
    if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_CACHE_DIR_TEXT:
        return os.path.abspath(".")
    return os.path.abspath(os.path.expanduser(raw.strip()))


def state_db_path(config: Dict[str, Any]) -> str:
    return os.path.join(_cache_directory(config), "state.sqlite3")


@contextmanager
def state_db_connect(config: Dict[str, Any]):
    cache_dir = _cache_directory(config)
    secure_directory(cache_dir)
    db_path = state_db_path(config)
    conn = sqlite3.connect(db_path, timeout=15)
    failed = False
    try:
        secure_sqlite_files(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        # The schema relies on this cascade when a playlist is removed. SQLite
        # leaves foreign-key enforcement disabled per connection by default,
        # which otherwise permits dangling playlist_tracks rows whenever a
        # future maintenance path does not manually delete children first.
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        secure_sqlite_files(db_path)
        conn.execute("PRAGMA synchronous=NORMAL")
        ensure_state_schema(conn)
        yield conn
        conn.commit()
    except BaseException:
        failed = True
        try:
            conn.rollback()
        except Exception:
            # A broken connection can reject rollback. Preserve the exception
            # that caused this transaction to fail.
            pass
        raise
    finally:
        if failed:
            try:
                conn.close()
            except Exception:
                pass
            try:
                secure_sqlite_files(db_path)
            except Exception:
                pass
        else:
            try:
                conn.close()
            finally:
                # The transaction has already committed. A best-effort
                # post-close permission refresh must not report that durable
                # state as a failed save and prompt a conflicting retry.
                try:
                    secure_sqlite_files(db_path)
                except Exception:
                    pass


def ensure_state_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS playback_sessions (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS state_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ui_preferences (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS favorites (
            track_id TEXT PRIMARY KEY,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS playlists (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            track_count INTEGER
        );
        CREATE TABLE IF NOT EXISTS playlist_tracks (
            playlist_id TEXT NOT NULL,
            track_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (playlist_id, track_id),
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_playlist_tracks_order ON playlist_tracks(playlist_id, position);
        """
    )
    # A database created before this column existed keeps its old rows and reads
    # back NULL for them, which the trim treats as "unknown" and repairs from the
    # child table.  A default of 0 would instead claim every legacy playlist was
    # empty, and the save after an upgrade would then be trusted into never
    # trimming anything at all.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(playlists)")}
    if "track_count" not in columns:
        conn.execute("ALTER TABLE playlists ADD COLUMN track_count INTEGER")


def _revision(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT value FROM state_meta WHERE key = ?", ("revision",)).fetchone()
        raw = row["value"] if row else 0
        if isinstance(raw, bool) or not isinstance(raw, (str, int)):
            return 0
        value = int(raw)
        return max(0, min(MAX_STATE_REVISION, value))
    except Exception:
        return 0


def _next_revision(conn: sqlite3.Connection) -> int:
    value = min(MAX_STATE_REVISION, _revision(conn) + 1)
    conn.execute("INSERT OR REPLACE INTO state_meta(key, value) VALUES (?, ?)", ("revision", str(value)))
    return value


def _state_changes(payload: Any) -> Dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    try:
        favorites_add = payload.get("favorites_add")
        favorites_remove = payload.get("favorites_remove")
        playlist_upserts = payload.get("playlist_upserts")
        playlist_delete = payload.get("playlist_delete")
    except Exception:
        return None
    return {
        "favorites_add": _strings(favorites_add if isinstance(favorites_add, list) else [],
                                  MAX_REQUEST_FAVORITES),
        "favorites_remove": _strings(favorites_remove if isinstance(favorites_remove, list) else [],
                                     MAX_REQUEST_FAVORITES),
        "playlist_upserts": _playlists(playlist_upserts),
        "playlist_delete": _strings(playlist_delete if isinstance(playlist_delete, list) else [],
                                    MAX_REQUEST_PLAYLIST_DELETIONS),
    }


def _payload_value(payload: Any, key: str, default=None):
    if not isinstance(payload, dict):
        return default
    try:
        return payload.get(key, default)
    except Exception:
        return default


_PLAYLIST_KEEP_ROWS_SQL = (
    "SELECT id, track_count FROM playlists ORDER BY created_at ASC, id ASC LIMIT ?"
)
# One statement drops every child row whose parent is gone, and the parent
# delete re-derives the keep-set inside SQLite so neither binds a value per
# stored playlist.
_ORPHAN_TRACK_ROWS_SQL = (
    "DELETE FROM playlist_tracks WHERE playlist_id NOT IN ("
    "SELECT id FROM playlists ORDER BY created_at ASC, id ASC LIMIT ?"
    ")"
)
_UNKEPT_PLAYLIST_ROWS_SQL = (
    "DELETE FROM playlists WHERE id NOT IN ("
    "SELECT id FROM playlists ORDER BY created_at ASC, id ASC LIMIT ?"
    ")"
)
_REFETCH_TRACK_COUNTS_SQL = (
    "UPDATE playlists SET track_count = ("
    "SELECT COUNT(*) FROM playlist_tracks"
    " WHERE playlist_tracks.playlist_id = playlists.id"
    ")"
)
_CHILD_INTEGRITY_KEY = "playlist_children_verified"


def _child_integrity_verified(conn: sqlite3.Connection) -> bool:
    """Ask whether child rows were last found to all have a parent."""
    try:
        row = conn.execute(
            "SELECT value FROM state_meta WHERE key = ?", (_CHILD_INTEGRITY_KEY,)
        ).fetchone()
    except Exception:
        return False
    return child_integrity_is_recorded(row)


def _trim_persisted_playlists(conn: sqlite3.Connection) -> None:
    """Keep committed playlist rows within the same limits as recovery.

    Full state writes are normalized before they reach SQLite, but stale-client
    delta writes merge with rows already on disk.  Without this final
    transaction-local trim, repeated independent deltas could grow the stored
    playlist tables beyond the limits that protect response and restore work.

    R115 took the fixed cost out of this path.  It used to scan the whole child
    table on every save -- once for the two NOT IN deletes and once for a
    grouped count of every playlist -- so the work grew with the number of
    stored track ids, which is precisely the term that made
    MAX_PERSISTED_TRACK_IDS_TOTAL hard to raise.  Both scans are now
    conditional:

    * playlists.track_count carries the row count of each playlist, written by
      the same statement batch that writes the rows themselves, so
      children_are_within_budget() can prove from the parent rows alone that no
      delete is possible and leave the child table untouched.
    * A child row without a parent can only survive in a database written
      before the foreign key was declared.  One NOT IN sweep removes those, and
      the state_meta marker records that the sweep happened, so it does not
      repeat on every save.

    Whenever the answer is not "nothing to do", every count is re-derived from
    the child rows by _REFETCH_TRACK_COUNTS_SQL before it is used: a trimming
    decision is never taken from a number that might have drifted.
    """
    cap = MAX_PERSISTED_PLAYLISTS
    rows = conn.execute(_PLAYLIST_KEEP_ROWS_SQL, (cap + 1,)).fetchall()
    if not rows:
        conn.execute("DELETE FROM playlist_tracks")
        conn.execute("DELETE FROM playlists")
        return
    # The look-ahead row is the whole overflow test: a short read proves the
    # table holds no playlist beyond the retention cap.
    overflow = len(rows) > cap
    verified = _child_integrity_verified(conn)
    if not overflow and verified and children_are_within_budget(
        [row["track_count"] for row in rows],
        MAX_PERSISTED_TRACK_IDS,
        MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL,
    ):
        return
    if overflow or not verified:
        conn.execute(_ORPHAN_TRACK_ROWS_SQL, (cap,))
        conn.execute(_UNKEPT_PLAYLIST_ROWS_SQL, (cap,))
        if not verified:
            conn.execute(
                "INSERT OR REPLACE INTO state_meta(key, value) VALUES (?, ?)",
                (_CHILD_INTEGRITY_KEY, CHILD_INTEGRITY_VERIFIED),
            )
    conn.execute(_REFETCH_TRACK_COUNTS_SQL)
    rows = conn.execute(_PLAYLIST_KEEP_ROWS_SQL, (cap,)).fetchall()
    remaining_track_ids = MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL
    for row in rows:
        # The statement above just wrote this number from the child rows, so it
        # is the authoritative count and needs no normalising here.
        count = int(row["track_count"])
        keep_count = min(MAX_PERSISTED_TRACK_IDS, remaining_track_ids)
        if count > keep_count:
            # `rowid` keeps the delete bounded in Python even if a damaged legacy
            # database contains far more rows than the current policy permits.
            conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id = ? AND rowid NOT IN ("
                "SELECT rowid FROM playlist_tracks WHERE playlist_id = ? "
                "ORDER BY position ASC, rowid ASC LIMIT ?"
                ")",
                (row["id"], row["id"], keep_count),
            )
            conn.execute(
                "UPDATE playlists SET track_count = ? WHERE id = ?",
                (keep_count, row["id"]),
            )
        remaining_track_ids = max(0, remaining_track_ids - min(keep_count, count))


def load_user_state(config: Dict[str, Any]) -> Dict[str, Any]:
    with _STATE_WRITE_LOCK, state_db_connect(config) as conn:
        favorites = [row["track_id"] for row in conn.execute(
            "SELECT track_id FROM favorites ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (MAX_PERSISTED_FAVORITES,),
        )]
        playlist_rows = conn.execute(
            "SELECT id, name FROM playlists ORDER BY created_at ASC, id ASC LIMIT ?",
            (MAX_PERSISTED_PLAYLISTS,),
        ).fetchall()
        playlists = []
        remaining_track_ids = MAX_PERSISTED_PLAYLIST_TRACK_IDS_TOTAL
        for row in playlist_rows:
            track_ids = []
            if remaining_track_ids:
                track_ids = [track["track_id"] for track in conn.execute(
                    "SELECT track_id FROM playlist_tracks WHERE playlist_id = ? ORDER BY position ASC LIMIT ?",
                    (row["id"], min(MAX_PERSISTED_TRACK_IDS, remaining_track_ids)),
                )]
                remaining_track_ids = max(0, remaining_track_ids - len(track_ids))
            playlists.append({"id": row["id"], "name": row["name"], "trackIds": track_ids})
        session = conn.execute("SELECT payload FROM playback_sessions WHERE id = ?", ("default",)).fetchone()
        ui_row = conn.execute("SELECT payload FROM ui_preferences WHERE id = ?", ("default",)).fetchone()
        revision = _revision(conn)
    playback = _mapping_or_empty(_load_json_bounded(session["payload"] if session else "{}"))
    ui = _ui_preferences(_load_json_bounded(ui_row["payload"] if ui_row else "{}"))
    return {"initialized": bool(session or ui_row), "revision": revision, "favorites": favorites, "playlists": playlists, "playback": playback, "ui": ui}


def _trim_persisted_favorites(conn: sqlite3.Connection) -> None:
    """Keep at most ``MAX_PERSISTED_FAVORITES`` favorite rows on disk.

    ``load_user_state`` already reads only the newest ``cap`` rows, so every row
    beyond that was invisible work rather than a longer list: a stale-client delta
    save adds up to the request cap of new ids and ``INSERT OR IGNORE`` never
    revisits a row, so four such saves measured 150000 stored rows behind a reader
    still returning 50000, 3.1 MiB of extra ``state.sqlite3`` per save, and the
    save itself slowed from 24 ms to 184 ms.

    The delete removes exactly the oldest excess in the reader's own order (newest
    ``created_at``, then highest ``rowid``), so trimming cannot change what any
    client sees.  A cheap ``COUNT`` guards the delete: at or below the cap, which
    is every ordinary save, nothing is scanned or deleted.
    """
    count = int(conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0])
    excess = count - MAX_PERSISTED_FAVORITES
    if excess <= 0:
        return
    conn.execute(
        "DELETE FROM favorites WHERE rowid IN ("
        "SELECT rowid FROM favorites ORDER BY created_at ASC, rowid ASC LIMIT ?"
        ")",
        (excess,),
    )


def save_user_state(config: Dict[str, Any], payload: Dict[str, Any], expected_revision: int | None = None) -> Dict[str, Any]:
    raw_favorites = _payload_value(payload, "favorites")
    favorites = _strings(raw_favorites if isinstance(raw_favorites, list) else [], MAX_REQUEST_FAVORITES)
    playlists = _playlists(_payload_value(payload, "playlists"))
    changes = _state_changes(_payload_value(payload, "changes"))
    raw_playback = _payload_value(payload, "playback")
    playback = raw_playback if isinstance(raw_playback, dict) else {}
    ui = _ui_preferences(_payload_value(payload, "ui"))
    # Validate before the transaction so an oversized or malformed payload
    # cannot partially replace favorites or playlists before failing.
    playback_payload = _dump_json_bounded(playback)
    ui_payload = _dump_json_bounded(ui)
    now = int(time.time())
    with _STATE_WRITE_LOCK, state_db_connect(config) as conn:
        conn.execute("BEGIN IMMEDIATE")
        current_revision = _revision(conn)
        if expected_revision is not None and expected_revision != current_revision:
            if changes is None:
                raise StateConflict("state changed by another client")
            conn.executemany("DELETE FROM favorites WHERE track_id = ?", [(track_id,) for track_id in changes["favorites_remove"]])
            # A batch add has to land in the client's newest-first order. Every
            # new row shares this save's timestamp, so the tie-break in
            # load_user_state (rowid DESC) decides the sequence: insert in
            # reverse and the first requested id keeps the highest rowid.
            conn.executemany(
                "INSERT OR IGNORE INTO favorites(track_id, created_at) VALUES (?, ?)",
                [(track_id, now) for track_id in reversed(changes["favorites_add"])],
            )
            for playlist_id in changes["playlist_delete"]:
                conn.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))
                conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
            for index, playlist in enumerate(changes["playlist_upserts"]):
                existing = conn.execute("SELECT created_at FROM playlists WHERE id = ?", (playlist["id"],)).fetchone()
                # The child rows are replaced wholesale just below, from this same
                # already-deduplicated id list, so its length is the exact count and
                # the trim never has to ask the child table for it.
                if existing:
                    conn.execute("UPDATE playlists SET name = ?, updated_at = ?, track_count = ? WHERE id = ?", (playlist["name"], now, len(playlist["trackIds"]), playlist["id"]))
                else:
                    conn.execute("INSERT INTO playlists(id, name, created_at, updated_at, track_count) VALUES (?, ?, ?, ?, ?)", (playlist["id"], playlist["name"], now + index, now, len(playlist["trackIds"])))
                conn.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist["id"],))
                conn.executemany(
                    "INSERT INTO playlist_tracks(playlist_id, track_id, position) VALUES (?, ?, ?)",
                    [(playlist["id"], track_id, position) for position, track_id in enumerate(playlist["trackIds"])],
                )
            _trim_persisted_playlists(conn)
        else:
            conn.execute("DELETE FROM favorites")
            conn.executemany("INSERT INTO favorites(track_id, created_at) VALUES (?, ?)", [(track_id, now - index) for index, track_id in enumerate(favorites)])
            conn.execute("DELETE FROM playlist_tracks")
            conn.execute("DELETE FROM playlists")
            for index, playlist in enumerate(playlists):
                conn.execute("INSERT INTO playlists(id, name, created_at, updated_at, track_count) VALUES (?, ?, ?, ?, ?)", (playlist["id"], playlist["name"], now + index, now, len(playlist["trackIds"])))
                conn.executemany("INSERT INTO playlist_tracks(playlist_id, track_id, position) VALUES (?, ?, ?)", [(playlist["id"], track_id, position) for position, track_id in enumerate(playlist["trackIds"])])
            _trim_persisted_playlists(conn)
            conn.execute("INSERT OR REPLACE INTO playback_sessions(id, payload, updated_at) VALUES (?, ?, ?)", ("default", playback_payload, now))
            conn.execute("INSERT OR REPLACE INTO ui_preferences(id, payload, updated_at) VALUES (?, ?, ?)", ("default", ui_payload, now))
        _trim_persisted_favorites(conn)
        _next_revision(conn)
    return load_user_state(config)


def save_playback_session(config: Dict[str, Any], playback: Dict[str, Any]) -> int:
    source = playback if isinstance(playback, dict) else {}
    raw_queue = source.get("queue")
    if isinstance(raw_queue, list):
        for value in raw_queue:
            if isinstance(value, str) and len(value.encode("utf-8")) > MAX_STATE_TEXT_BYTES:
                raise ValueError("playback queue item exceeds size limit")
    # Keep this low-level writer safe even when a caller bypasses the server's
    # normal core projection. Recovery and persistence must share one queue and
    # field budget rather than relying on every caller to remember it.
    persisted = {
        "queue": playback_queue_ids(source.get("queue")),
        "current_id": source.get("current_id") if isinstance(source.get("current_id"), str) else "",
        "position": source.get("position", 0),
        "playing": source.get("playing") is True,
        "repeat": source.get("repeat") if source.get("repeat") in ("off", "all", "one") else "off",
        "shuffle": source.get("shuffle") is True,
        "target_id": source.get("target_id") if isinstance(source.get("target_id"), str) else "local",
        "target_kind": source.get("target_kind") if isinstance(source.get("target_kind"), str) else "browser",
    }
    playback_payload = _dump_json_bounded(persisted)
    now = int(time.time())
    with _STATE_WRITE_LOCK, state_db_connect(config) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT OR REPLACE INTO playback_sessions(id, payload, updated_at) VALUES (?, ?, ?)",
            ("default", playback_payload, now),
        )
        return _next_revision(conn)


__all__ = ["MAX_STATE_PAYLOAD_BYTES", "MAX_STATE_TEXT_BYTES", "StateConflict", "load_user_state", "save_user_state", "save_playback_session", "state_db_path"]
