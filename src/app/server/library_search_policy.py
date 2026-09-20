"""Pure SQL-condition policy for library text search."""

import re

SEARCH_COLUMNS = ("title", "artist", "album", "album_artist", "composer", "genre", "folder", "path", "format")
MAX_SEARCH_TEXT = 4096
MAX_SQL_IDENTIFIER = 128
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$")

def track_search_condition(search, alias="", use_fts=False, rowid_column=None):
    value = search.strip().lower()[:MAX_SEARCH_TEXT] if isinstance(search, str) else ""
    if not value:
        return "", []
    raw_alias = alias.strip() if isinstance(alias, str) else ""
    safe_alias = raw_alias[:MAX_SQL_IDENTIFIER] if _IDENTIFIER_RE.fullmatch(raw_alias[:MAX_SQL_IDENTIFIER]) else ""
    prefix = (safe_alias + ".") if safe_alias else ""
    if use_fts and len(value) >= 3:
        escaped = value.replace('"', '""')
        raw_rowid = rowid_column.strip() if isinstance(rowid_column, str) else ""
        rowid = raw_rowid[:MAX_SQL_IDENTIFIER] if _IDENTIFIER_RE.fullmatch(raw_rowid[:MAX_SQL_IDENTIFIER]) else (prefix + "rowid")
        return "%s IN (SELECT rowid FROM tracks_search WHERE tracks_search MATCH ?)" % rowid, ['"%s"' % escaped]
    condition = "(" + " OR ".join("lower(COALESCE(%s%s, '')) LIKE ?" % (prefix, column) for column in SEARCH_COLUMNS) + ")"
    return condition, ["%" + value + "%"] * len(SEARCH_COLUMNS)
