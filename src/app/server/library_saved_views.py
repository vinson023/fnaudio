"""Persistence for saved library views.

The rules live in ``library_saved_view_policy`` (pure, unit-tested). This module
only moves validated records in and out of ``state.sqlite3``, next to favorites
and playlists, so a library rescan or index rebuild never touches them.

All reads are bounded: at most ``MAX_VIEWS`` rows, newest first. A write trims
the table to the same bound, so a client cannot grow it without limit.
"""

from __future__ import annotations

import json
import sqlite3

from library_saved_view_policy import (
    MAX_VIEWS,
    normalize_view,
    normalize_views,
)
from state_store import state_db_connect

_SELECT_SQL = (
    "SELECT id, name, criteria, created_at, updated_at FROM saved_views "
    "ORDER BY updated_at DESC, id ASC LIMIT ?"
)
_UPSERT_SQL = (
    "INSERT INTO saved_views(id, name, criteria, created_at, updated_at) "
    "VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
    "name=excluded.name, criteria=excluded.criteria, updated_at=excluded.updated_at"
)


def _row_to_view(row):
    try:
        criteria = json.loads(row["criteria"])
    except (TypeError, ValueError):
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "criteria": criteria,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _read(conn):
    rows = conn.execute(_SELECT_SQL, (MAX_VIEWS,)).fetchall()
    return normalize_views([view for view in (_row_to_view(row) for row in rows) if view])


def _trim(conn):
    conn.execute(
        "DELETE FROM saved_views WHERE id NOT IN ("
        "SELECT id FROM saved_views ORDER BY updated_at DESC, id ASC LIMIT ?"
        ")",
        (MAX_VIEWS,),
    )


def list_saved_views(config):
    with state_db_connect(config) as conn:
        return _read(conn)


def views_snapshot(config):
    """Public response shape; ``limit`` lets the UI disable "save" when full."""
    views = list_saved_views(config)
    return {"views": views, "limit": MAX_VIEWS}


def save_saved_view(config, raw, now=None):
    """Validate, upsert, trim, and return the resulting list."""
    view = normalize_view(raw, now=now)
    with state_db_connect(config) as conn:
        existing = _read(conn)
        created = next(
            (item["created_at"] for item in existing if item["id"] == view["id"]),
            view["created_at"],
        )
        conn.execute(
            _UPSERT_SQL,
            (
                view["id"],
                view["name"],
                json.dumps(view["criteria"], ensure_ascii=False, sort_keys=True),
                created,
                view["updated_at"],
            ),
        )
        _trim(conn)
        # Re-read so the caller sees exactly what a later GET would return,
        # including the order a re-save moved this view to.
        return _read(conn)


def delete_saved_view(config, view_id):
    with state_db_connect(config) as conn:
        conn.execute("DELETE FROM saved_views WHERE id = ?", (str(view_id or "")[:24],))
        _trim(conn)
        return _read(conn)


__all__ = [
    "delete_saved_view",
    "list_saved_views",
    "save_saved_view",
    "views_snapshot",
]
