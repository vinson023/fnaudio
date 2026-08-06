from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterable


class StateConflict(Exception):
    pass


# Playback controls can arrive concurrently from several browser tabs or
# DLNA callbacks. Serialize writes inside this process before SQLite has to
# contend for its write lock; the busy timeout still covers separate workers.
_STATE_WRITE_LOCK = threading.RLock()


def state_db_path(config: Dict[str, Any]) -> str:
    return os.path.join(str(config["cache_dir"]), "state.sqlite3")


@contextmanager
def state_db_connect(config: Dict[str, Any]):
    os.makedirs(str(config["cache_dir"]), exist_ok=True)
    conn = sqlite3.connect(state_db_path(config), timeout=15)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        ensure_state_schema(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
            updated_at INTEGER NOT NULL
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


def _strings(values: Iterable[Any], limit: int) -> list[str]:
    result = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _revision(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT value FROM state_meta WHERE key = ?", ("revision",)).fetchone()
    try:
        return max(0, int(row["value"] if row else 0))
    except (TypeError, ValueError):
        return 0


def _next_revision(conn: sqlite3.Connection) -> int:
    value = _revision(conn) + 1
    conn.execute("INSERT OR REPLACE INTO state_meta(key, value) VALUES (?, ?)", ("revision", str(value)))
    return value


def _ui_preferences(payload: Any) -> Dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    columns = source.get("track_columns") if isinstance(source.get("track_columns"), dict) else {}
    widths = source.get("track_column_widths") if isinstance(source.get("track_column_widths"), dict) else {}
    result: Dict[str, list[str]] = {}
    for scope, values in columns.items():
        key = str(scope or "").strip()[:512]
        if not key or not isinstance(values, list):
            continue
        selected = _strings(values, 16)
        if selected:
            result[key] = selected
        if len(result) >= 2000:
            break
    width_result: Dict[str, Dict[str, int]] = {}
    for scope, values in widths.items():
        key = str(scope or "").strip()[:512]
        if not key or not isinstance(values, dict):
            continue
        selected = {}
        for column, width in values.items():
            column_key = str(column or "").strip()[:64]
            try:
                value = int(width)
            except (TypeError, ValueError):
                continue
            if column_key and 64 <= value <= 900:
                selected[column_key] = value
            if len(selected) >= 16:
                break
        if selected:
            width_result[key] = selected
        if len(width_result) >= 2000:
            break
    return {"track_columns": result, "track_column_widths": width_result}


def load_user_state(config: Dict[str, Any]) -> Dict[str, Any]:
    with _STATE_WRITE_LOCK, state_db_connect(config) as conn:
        favorites = [row["track_id"] for row in conn.execute("SELECT track_id FROM favorites ORDER BY created_at DESC, rowid DESC")]
        playlist_rows = conn.execute("SELECT id, name FROM playlists ORDER BY created_at ASC, id ASC").fetchall()
        playlists = []
        for row in playlist_rows:
            track_ids = [track["track_id"] for track in conn.execute("SELECT track_id FROM playlist_tracks WHERE playlist_id = ? ORDER BY position ASC", (row["id"],))]
            playlists.append({"id": row["id"], "name": row["name"], "trackIds": track_ids})
        session = conn.execute("SELECT payload FROM playback_sessions WHERE id = ?", ("default",)).fetchone()
        ui_row = conn.execute("SELECT payload FROM ui_preferences WHERE id = ?", ("default",)).fetchone()
        revision = _revision(conn)
    try:
        playback = json.loads(session["payload"]) if session else {}
    except (TypeError, ValueError):
        playback = {}
    try:
        ui = _ui_preferences(json.loads(ui_row["payload"]) if ui_row else {})
    except (TypeError, ValueError):
        ui = {"track_columns": {}, "track_column_widths": {}}
    return {"initialized": bool(session or ui_row), "revision": revision, "favorites": favorites, "playlists": playlists, "playback": playback, "ui": ui}


def save_user_state(config: Dict[str, Any], payload: Dict[str, Any], expected_revision: int | None = None) -> Dict[str, Any]:
    favorites = _strings(payload.get("favorites") if isinstance(payload.get("favorites"), list) else [], 50000)
    source_playlists = payload.get("playlists") if isinstance(payload.get("playlists"), list) else []
    playlists = []
    seen = set()
    for entry in source_playlists:
        if not isinstance(entry, dict):
            continue
        playlist_id = str(entry.get("id") or "").strip()
        name = str(entry.get("name") or "").strip()[:160]
        if not playlist_id or not name or playlist_id in seen:
            continue
        seen.add(playlist_id)
        playlists.append({"id": playlist_id, "name": name, "trackIds": _strings(entry.get("trackIds") if isinstance(entry.get("trackIds"), list) else [], 10000)})
        if len(playlists) >= 1000:
            break
    playback = payload.get("playback") if isinstance(payload.get("playback"), dict) else {}
    ui = _ui_preferences(payload.get("ui"))
    now = int(time.time())
    with _STATE_WRITE_LOCK, state_db_connect(config) as conn:
        conn.execute("BEGIN IMMEDIATE")
        current_revision = _revision(conn)
        if expected_revision is not None and expected_revision != current_revision:
            raise StateConflict("state changed by another client")
        conn.execute("DELETE FROM favorites")
        conn.executemany("INSERT INTO favorites(track_id, created_at) VALUES (?, ?)", [(track_id, now - index) for index, track_id in enumerate(favorites)])
        conn.execute("DELETE FROM playlist_tracks")
        conn.execute("DELETE FROM playlists")
        for index, playlist in enumerate(playlists):
            conn.execute("INSERT INTO playlists(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)", (playlist["id"], playlist["name"], now + index, now))
            conn.executemany("INSERT INTO playlist_tracks(playlist_id, track_id, position) VALUES (?, ?, ?)", [(playlist["id"], track_id, position) for position, track_id in enumerate(playlist["trackIds"])])
        conn.execute("INSERT OR REPLACE INTO playback_sessions(id, payload, updated_at) VALUES (?, ?, ?)", ("default", json.dumps(playback, ensure_ascii=False, separators=(",", ":")), now))
        conn.execute("INSERT OR REPLACE INTO ui_preferences(id, payload, updated_at) VALUES (?, ?, ?)", ("default", json.dumps(ui, ensure_ascii=False, separators=(",", ":")), now))
        _next_revision(conn)
    return load_user_state(config)


def save_playback_session(config: Dict[str, Any], playback: Dict[str, Any]) -> int:
    now = int(time.time())
    with _STATE_WRITE_LOCK, state_db_connect(config) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT OR REPLACE INTO playback_sessions(id, payload, updated_at) VALUES (?, ?, ?)",
            ("default", json.dumps(playback if isinstance(playback, dict) else {}, ensure_ascii=False, separators=(",", ":")), now),
        )
        return _next_revision(conn)


__all__ = ["StateConflict", "load_user_state", "save_user_state", "save_playback_session", "state_db_path"]
