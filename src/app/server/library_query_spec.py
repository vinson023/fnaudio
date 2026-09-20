"""Normalized, transport-agnostic music-library query inputs."""

from dataclasses import dataclass
import math
import re


TRACK_SORT_COLUMNS = {
    "title": "title COLLATE NOCASE",
    "artist": "artist COLLATE NOCASE",
    "album": "album COLLATE NOCASE",
    "format": "format COLLATE NOCASE",
    "added": "added_ns",
    "track_no": "CASE WHEN track_no <= 0 THEN 2147483647 ELSE track_no END",
}
GROUP_TRACK_COLUMNS = {"albums": "album", "artists": "artist", "composers": "composer", "genres": "genre"}
LIBRARY_ITEM_ID_LIMIT = 120
MAX_LIBRARY_QUERY_TEXT_CHARS = 512
MAX_LIBRARY_PATH_CHARS = 4096
MAX_LIBRARY_ITEM_ID_CHARS = 512
MAX_LIBRARY_ITEM_IDS_CHARS = LIBRARY_ITEM_ID_LIMIT * (MAX_LIBRARY_ITEM_ID_CHARS + 1)
# Offset pagination makes SQLite visit skipped rows. Deep browsing uses the
# cursor contract, so keep a generous direct-page ceiling without allowing an
# untrusted query to turn one request into an effectively full-table walk.
MAX_LIBRARY_OFFSET = 100000
_NUMBER_TEXT = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


def _safe_bound(value, default, minimum=0, maximum=10 ** 9):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        number = int(value)
    except (OverflowError, ValueError, TypeError):
        return default
    return max(minimum, min(maximum, number))


def first_param(params, key, default=""):
    getter = getattr(params, "get", None)
    if callable(getter):
        try:
            value = getter(key)
        except Exception:
            return default
        if isinstance(value, (list, tuple)):
            return value[0] if value else default
        return value if value is not None else default
    return default


def param_int(params, key, default=0):
    return numeric_int(first_param(params, key, default), default)


def numeric_int(value, default=0):
    """Parse ordinary finite integer values without truncating fractions."""
    if isinstance(value, bool):
        return default
    if isinstance(value, str):
        text = value.strip()
        if not _NUMBER_TEXT.fullmatch(text):
            return default
        try:
            value = float(text)
        except (OverflowError, ValueError):
            return default
    elif not isinstance(value, (int, float)):
        return default
    if isinstance(value, float) and not math.isfinite(value):
        return default
    if isinstance(value, float) and not value.is_integer():
        return default
    try:
        number = int(value)
    except (OverflowError, ValueError):
        return default
    # Do not let arbitrary-precision integers propagate into pagination or
    # cache keys. Normal callers are far below this bound, while values above
    # it are malformed input and should use the caller's safe default.
    if isinstance(value, int):
        return number if abs(number) <= 10 ** 9 else default
    return number


def param_text(params, key, default="", maximum=MAX_LIBRARY_QUERY_TEXT_CHARS, strip=False, lower=False):
    """Read only ordinary text query values and cap their cache/SQL footprint."""
    value = first_param(params, key, default)
    if not isinstance(value, str):
        return default if isinstance(default, str) else ""
    if strip:
        value = value.strip()
    if lower:
        value = value.lower()
    return value[:_safe_bound(maximum, MAX_LIBRARY_QUERY_TEXT_CHARS, 0, MAX_LIBRARY_PATH_CHARS)]


@dataclass(frozen=True)
class LibraryPageQuery:
    limit: int
    offset: int
    view: str
    group: str
    album: str
    folder: str
    root: str
    search: str
    sort_key: str
    sort_dir: str
    cursor: str

    @property
    def sql_sort_dir(self):
        return "DESC" if self.sort_dir == "desc" else "ASC"

    @property
    def sql_order(self):
        return TRACK_SORT_COLUMNS.get(self.sort_key, TRACK_SORT_COLUMNS["title"])

    @property
    def sql_order_by(self):
        """Return deterministic page order without duplicating the title key."""
        if self.sql_order == TRACK_SORT_COLUMNS["title"]:
            return "%s %s, id ASC" % (self.sql_order, self.sql_sort_dir)
        return "%s %s, title COLLATE NOCASE ASC, id ASC" % (self.sql_order, self.sql_sort_dir)

    @property
    def group_column(self):
        return GROUP_TRACK_COLUMNS.get(self.view, "")

    @property
    def cache_values(self):
        return (self.view, self.group, self.album, self.folder, self.root, self.search, self.sort_key, self.sql_sort_dir, self.limit, self.offset, self.cursor)


@dataclass(frozen=True)
class LibraryPageWindow:
    """A normalized optional SQL page shared by groups and folders."""

    limit: int
    offset: int


@dataclass(frozen=True)
class LibraryGroupQuery:
    view: str
    search: str
    page: LibraryPageWindow | None
    sql_sort_dir: str
    artist: str
    composer: str
    cursor: str


@dataclass(frozen=True)
class LibraryFolderQuery:
    parent: str
    root: str
    search: str
    page: LibraryPageWindow | None
    sql_sort_dir: str
    cursor: str


def parse_optional_page(limit, offset, default_limit=100, maximum_limit=500):
    """Return a bounded page, or ``None`` when a caller asks for all rows."""
    if limit is None:
        return None
    safe_default = _safe_bound(default_limit, 100, 1, 500)
    safe_maximum = _safe_bound(maximum_limit, 500, 1, 500)
    normalized_limit = max(1, min(safe_maximum, numeric_int(limit, safe_default)))
    normalized_offset = min(MAX_LIBRARY_OFFSET, max(0, numeric_int(offset, 0)))
    return LibraryPageWindow(limit=normalized_limit, offset=normalized_offset)


def parse_library_item_ids(value, maximum=LIBRARY_ITEM_ID_LIMIT):
    """Normalize a bounded comma-separated ID list used by the item hydrator."""
    if not isinstance(value, str):
        return []
    maximum = _safe_bound(maximum, LIBRARY_ITEM_ID_LIMIT, 1, LIBRARY_ITEM_ID_LIMIT)
    if len(value) > MAX_LIBRARY_ITEM_IDS_CHARS:
        raise ValueError("item id input is too large")
    values = []
    seen = set()
    for raw in value.split(","):
        item_id = raw.strip()
        if not item_id or item_id in seen:
            continue
        if len(item_id) > MAX_LIBRARY_ITEM_ID_CHARS:
            raise ValueError("item id is too large")
        seen.add(item_id)
        values.append(item_id)
        if len(values) > maximum:
            raise ValueError("too many item ids")
    return values


def normalize_library_item_id(value):
    """Accept one bounded text ID without coercing arbitrary input objects."""
    if not isinstance(value, str):
        return ""
    item_id = value.strip()
    return item_id if item_id and len(item_id) <= MAX_LIBRARY_ITEM_ID_CHARS else ""


def normalize_library_item_sequence(values):
    """Normalize trusted internal ID sequences without object coercion.

    HTTP callers use ``parse_library_item_ids`` and are limited to 120 IDs.
    Playback restore may legitimately carry a much longer persisted queue, so
    this helper keeps its full order but only accepts ordinary list/tuple text
    values. The SQLite caller is responsible for bounded query batching.
    """
    if not isinstance(values, (list, tuple)):
        return []
    result = []
    seen = set()
    for raw in values:
        item_id = normalize_library_item_id(raw)
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        result.append(item_id)
    return result


def parse_library_page_query(params):
    return LibraryPageQuery(
        limit=max(1, min(500, param_int(params, "limit", 100))),
        offset=min(MAX_LIBRARY_OFFSET, max(0, param_int(params, "offset", 0))),
        view=param_text(params, "view", "all", maximum=64, strip=True) or "all",
        group=param_text(params, "group"),
        album=param_text(params, "album"),
        folder=param_text(params, "folder", maximum=MAX_LIBRARY_PATH_CHARS),
        root=param_text(params, "root", maximum=MAX_LIBRARY_PATH_CHARS),
        search=param_text(params, "search", strip=True, lower=True),
        sort_key=param_text(params, "sort", "title", maximum=64, strip=True) or "title",
        sort_dir="desc" if param_text(params, "dir", "asc", maximum=16, strip=True, lower=True) == "desc" else "asc",
        cursor=param_text(params, "cursor", maximum=768, strip=True),
    )


def parse_library_group_query(view, search="", limit=None, offset=0, sort_dir="asc", artist="", composer="", cursor=""):
    """Normalize group browsing inputs before building SQLite filters/cache keys."""
    values = {
        "view": view, "search": search, "dir": sort_dir,
        "artist": artist, "composer": composer, "cursor": cursor,
    }
    return LibraryGroupQuery(
        view=param_text(values, "view", "", maximum=64, strip=True, lower=True),
        search=param_text(values, "search", strip=True, lower=True),
        page=parse_optional_page(limit, offset),
        sql_sort_dir="DESC" if param_text(values, "dir", "asc", maximum=16, strip=True, lower=True) == "desc" else "ASC",
        artist=param_text(values, "artist", maximum=MAX_LIBRARY_QUERY_TEXT_CHARS),
        composer=param_text(values, "composer", maximum=MAX_LIBRARY_QUERY_TEXT_CHARS),
        cursor=param_text(values, "cursor", maximum=768, strip=True),
    )


def parse_library_folder_query(parent="", root="", sort_dir="asc", limit=None, offset=0, search="", cursor=""):
    """Normalize folder browsing inputs before building SQLite filters/cache keys."""
    values = {"parent": parent, "root": root, "dir": sort_dir, "search": search, "cursor": cursor}
    return LibraryFolderQuery(
        parent=param_text(values, "parent", maximum=MAX_LIBRARY_PATH_CHARS),
        root=param_text(values, "root", maximum=MAX_LIBRARY_PATH_CHARS),
        search=param_text(values, "search", strip=True, lower=True),
        page=parse_optional_page(limit, offset),
        sql_sort_dir="DESC" if param_text(values, "dir", "asc", maximum=16, strip=True, lower=True) == "desc" else "ASC",
        cursor=param_text(values, "cursor", maximum=768, strip=True),
    )


def parse_library_root_search(search=""):
    """Normalize the root browser search term and its cache identity."""
    return param_text({"search": search}, "search", strip=True, lower=True)


__all__ = ["GROUP_TRACK_COLUMNS", "LIBRARY_ITEM_ID_LIMIT", "LibraryFolderQuery", "LibraryGroupQuery", "LibraryPageQuery", "LibraryPageWindow", "MAX_LIBRARY_ITEM_ID_CHARS", "MAX_LIBRARY_ITEM_IDS_CHARS", "MAX_LIBRARY_OFFSET", "MAX_LIBRARY_PATH_CHARS", "MAX_LIBRARY_QUERY_TEXT_CHARS", "TRACK_SORT_COLUMNS", "first_param", "normalize_library_item_id", "normalize_library_item_sequence", "numeric_int", "param_int", "param_text", "parse_library_folder_query", "parse_library_group_query", "parse_library_item_ids", "parse_library_page_query", "parse_library_root_search", "parse_optional_page"]
