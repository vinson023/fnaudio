#!/usr/bin/env python3
"""Build a synthetic library index and measure bounded SQLite page reads."""

from __future__ import annotations

import argparse
import contextlib
import gc
import json
import os
import platform
import sqlite3
import sys
import tempfile
import time
import tracemalloc
from typing import Any, Dict


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "src", "app", "server")
if SERVER not in sys.path:
    sys.path.insert(0, SERVER)

import library  # noqa: E402
import metadata_service  # noqa: E402


# Group cardinality has to scale with the library. The fixture used to stop at 2000 albums no
# matter how many tracks it was handed, while the browse-cursor gain this benchmark guards only
# shows up above ten thousand groups: eight runs on one build overlapped at 2.05-2.63 ms, so a
# regression on that path was invisible at the pinned shape (TODO.md:109).
ALBUMS_PER_TRACK = 8
# Both folder failure classes this benchmark guards (paging and the folder search page) are driven
# by the number of siblings under one parent, not by how many top-level directories exist
# (TODO.md:69). A quarter of the tracks each land in their own directory under one parent: 625
# siblings at 2.5k tracks, 25k at the 100k default, which is the regime the R58 fold was bought for.
WIDE_FOLDER_SHARE = 4
WIDE_FOLDER_PARENT = "Wide"
# Top-level directories in the deep shape. The wide parent is added on top of these, so anything
# that pins how many roots the directory view shows has to account for both.
DEEP_FOLDER_PARENTS = 80


def expected_top_level_folder_count() -> int:
    return DEEP_FOLDER_PARENTS + 1


def group_cardinality(track_count: int) -> int:
    """Album count for a synthetic library of `track_count` tracks."""
    return max(1, track_count // ALBUMS_PER_TRACK)


def wide_folder_sibling_count(track_count: int) -> int:
    """Siblings under `WIDE_FOLDER_PARENT` for a synthetic library of `track_count` tracks."""
    return max(1, track_count // WIDE_FOLDER_SHARE)


def folder_shape(index: int, track_count: int):
    """Return (folder, album) for synthetic track `index`.

    Every `WIDE_FOLDER_SHARE`-th track gets its own directory under one wide parent. The rest keep
    the deep `Collection %03d/Disc %02d` shape, and the deep counter is compressed rather than
    skipped so all 80 x 4 combinations stay present instead of collapsing to 60 top-level ones.
    """
    album = "Album %05d" % (index % group_cardinality(track_count))
    if index % WIDE_FOLDER_SHARE == 0:
        return "%s/Sibling %06d" % (WIDE_FOLDER_PARENT, index), album
    slot = index // WIDE_FOLDER_SHARE
    return "Collection %03d/Disc %02d" % (slot % DEEP_FOLDER_PARENTS, slot % 4), album


def _populate(config: Dict[str, Any], track_count: int) -> float:
    started = time.perf_counter()
    index_root = library.normalize_library_paths(config)[0]
    insert_sql = """
        INSERT INTO tracks(id,path,root,folder,title,artist,album,track_no,format,added_ns,item_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """
    with library.library_db_connect(config) as conn:
        for first in range(0, track_count, 2000):
            rows = []
            for index in range(first, min(first + 2000, track_count)):
                track_id = "track-%06d" % index
                track_no = (index % 20) + 1
                audio_format = ("FLAC", "MP3", "WAV", "APE", "M4A")[index % 5]
                folder_name, album_name = folder_shape(index, track_count)
                folder_parts = tuple(folder_name.split("/"))
                item = {
                    "id": track_id,
                    "path": os.path.join(index_root, folder_parts[0], folder_parts[1], track_id + ".flac"),
                    "root": index_root,
                    "folder": folder_name,
                    "title": "Track %06d" % index,
                    "artist": "Artist %04d" % (index % 1000),
                    "album": album_name,
                    "track_no": track_no,
                    "format": audio_format,
                    # Real scan rows preserve field provenance. The metadata
                    # overlay uses it to avoid replacing embedded Tag values;
                    # retain that contract in the synthetic benchmark too.
                    "metadata_source": {"title": "tag", "artist": "tag", "album": "tag"},
                }
                rows.append((track_id, item["path"], item["root"], item["folder"], item["title"], item["artist"], item["album"], track_no, item["format"], index * 1000000000, json.dumps(item, separators=(",", ":"))))
            conn.executemany(insert_sql, rows)
        conn.execute("INSERT OR REPLACE INTO library_meta(key,value) VALUES (?,?)", ("library_path", library.display_library_path(config)))
        conn.execute("INSERT OR REPLACE INTO library_meta(key,value) VALUES (?,?)", ("metadata_version", str(library.METADATA_VERSION)))
        conn.execute("INSERT OR REPLACE INTO library_meta(key,value) VALUES (?,?)", ("signature", "synthetic-%d" % track_count))
        conn.execute("INSERT OR REPLACE INTO library_meta(key,value) VALUES (?,?)", ("track_count", str(track_count)))
        conn.execute("INSERT OR REPLACE INTO library_meta(key,value) VALUES (?,?)", ("dsd_count", "0"))
        conn.execute(
            "INSERT OR REPLACE INTO library_meta(key,value) VALUES (?,?)",
            ("root_summary", json.dumps({index_root: {"track_count": track_count, "cover_track_id": "track-000000"}}, separators=(",", ":"))),
        )
        library._rebuild_group_table(conn, "albums", "album", "album_artist")
        library._rebuild_simple_group(conn, "artists", "artist")
        library._rebuild_simple_group(conn, "composers", "composer")
        library._rebuild_simple_group(conn, "genres", "genre")
        library._rebuild_folders(conn)
        library._rebuild_library_search_index(conn, config)
    return time.perf_counter() - started


def run_benchmark(cache_dir: str, track_count: int = 100000, page_size: int = 120) -> Dict[str, Any]:
    config = {"cache_dir": cache_dir, "library_paths": ["/benchmark"]}
    index_root = library.normalize_library_paths(config)[0]
    build_seconds = _populate(config, track_count)
    offsets = sorted(set([0, max(0, track_count // 2), max(0, track_count - page_size)]))
    pages = []
    gc.collect()
    tracemalloc.start()
    query_started = time.perf_counter()
    for offset in offsets:
        started = time.perf_counter()
        page = library.query_library_page(config, {"view": "all", "sort": "title", "dir": "asc", "limit": str(page_size), "offset": str(offset)})
        pages.append({
            "offset": offset,
            "seconds": round(time.perf_counter() - started, 6),
            "returned": len(page["items"]),
            "count": page["count"],
            "first_id": page["items"][0]["id"] if page["items"] else "",
        })
        if page["count"] != track_count or len(page["items"]) > page_size or not page.get("paged"):
            raise RuntimeError("library query violated bounded pagination")
    query_seconds = time.perf_counter() - query_started
    # Compare a keyset continuation with the OFFSET page that starts at the same
    # row, at several depths.  A cursor predicate SQLite cannot seek degrades into
    # exactly the traversal it is meant to replace, so what has to stay visible is
    # the cursor/OFFSET ratio as depth grows, not the absolute duration of a page.
    # Below this many rows both paths finish inside the per-page overhead they
    # share, so comparing their durations there would only measure noise.
    seek_evidence_depth = 10000
    # One sample of a 5-9ms page on a busy machine swings by more than the whole
    # effect this section looks for, so both sides are sampled repeatedly.
    pagination_samples = 3
    cursor_ceiling = max(0, track_count - 2 * page_size)
    cursor_depths = sorted({
        0,
        min(1200, cursor_ceiling),
        min(12000, cursor_ceiling),
        min(cursor_ceiling, track_count // 2),
    })
    cursor_pagination = {
        "depths": cursor_depths,
        "seek_evidence_depth": seek_evidence_depth,
        "samples": pagination_samples,
        "sorts": {},
    }
    legacy_keys = ("cursor_seconds", "offset_seconds", "cursor_returned", "offset_returned",
                   "count", "matching_page", "has_more", "cursor_versus_offset")
    # "format" is the huge-key-group case: five distinct values over the whole
    # library, so a deep page sits tens of thousands of rows into one group. That
    # is where skipping by counted OFFSET costs real time and two seeks do not.
    for sort_key in ("title", "artist", "format"):
        measurements = []
        for depth in cursor_depths:
            seed = library.query_library_page(config, {
                "view": "all", "sort": sort_key, "dir": "asc",
                "limit": str(page_size), "offset": str(depth),
            })
            cursor_token = seed.get("next_cursor")
            cursor_seconds = []
            offset_seconds = []
            for _ in range(pagination_samples):
                # Drop the short-lived page cache before each side so both are read
                # cold; a warm OFFSET page would otherwise flatter the traversal the
                # keyset is supposed to avoid.
                library.LIBRARY_QUERY_CACHE.invalidate_database(library.library_db_path(config))
                cursor_started = time.perf_counter()
                cursor_page = library.query_library_page(config, {
                    "view": "all", "sort": sort_key, "dir": "asc",
                    "limit": str(page_size), "offset": "0", "cursor": cursor_token or "",
                })
                cursor_seconds.append(time.perf_counter() - cursor_started)
                library.LIBRARY_QUERY_CACHE.invalidate_database(library.library_db_path(config))
                offset_started = time.perf_counter()
                offset_page = library.query_library_page(config, {
                    "view": "all", "sort": sort_key, "dir": "asc",
                    "limit": str(page_size), "offset": str(depth + page_size),
                })
                offset_seconds.append(time.perf_counter() - offset_started)
            cursor_seconds = sorted(cursor_seconds)[len(cursor_seconds) // 2]
            offset_seconds = sorted(offset_seconds)[len(offset_seconds) // 2]
            matching_page = [item.get("id") for item in cursor_page.get("items", [])] == [
                item.get("id") for item in offset_page.get("items", [])
            ]
            measurements.append({
                "offset": depth,
                "cursor_seconds": round(cursor_seconds, 6),
                "offset_seconds": round(offset_seconds, 6),
                "cursor_returned": len(cursor_page.get("items", [])),
                "offset_returned": len(offset_page.get("items", [])),
                "count": cursor_page.get("count", 0),
                "matching_page": matching_page,
                "has_more": cursor_page.get("has_more") is True,
            })
            if not cursor_token or cursor_page.get("count") != track_count:
                raise RuntimeError("keyset cursor pagination lost the page total")
            if not matching_page or len(cursor_page.get("items", [])) != page_size:
                raise RuntimeError("keyset cursor pagination did not preserve the following page")
            # A keyset continuation that still walks every row before the cursor
            # is indistinguishable from OFFSET, so only the ratio proves the seek
            # survived a schema change.  Deep pages are compared because shallow
            # ones are dominated by per-page overhead both paths share.
            measurements[-1]["cursor_versus_offset"] = round(
                cursor_seconds / offset_seconds if offset_seconds > 0 else 0.0, 3
            )
            if depth == cursor_depths[-1] and depth >= seek_evidence_depth and cursor_seconds > offset_seconds:
                raise RuntimeError(
                    "keyset cursor pagination stopped being faster than OFFSET at depth %d (%s)"
                    % (depth, sort_key)
                )
        cursor_pagination["sorts"][sort_key] = measurements
        if sort_key == "title":
            # Keep the historical top-level shape: the original benchmark reported
            # the title continuation seeded at half the library, so the sweep
            # exposes that page unchanged and keeps the rest as extra detail.
            midpoint = track_count // 2
            seeded = min(measurements, key=lambda page: abs(page["offset"] - midpoint))
            for name, value in seeded.items():
                if name in legacy_keys:
                    cursor_pagination[name] = value
            cursor_pagination["seed_offset"] = seeded["offset"]
    # The title page is the default first screen, but artist/album ordering is
    # also selectable from the same table. Measure their first/middle/tail
    # pages and retain the query plans so a future schema migration cannot
    # quietly reintroduce a full temporary sort for those common views.
    sorted_pages = {}
    with library.library_db_connect(config) as conn:
        for sort_key in ("artist", "album", "added", "format", "track_no"):
            for sort_dir in ("asc", "desc"):
                label = sort_key + "_" + sort_dir
                pages_for_sort = []
                for offset in offsets:
                    started = time.perf_counter()
                    page = library.query_library_page(config, {
                        "view": "all", "sort": sort_key, "dir": sort_dir,
                        "limit": str(page_size), "offset": str(offset),
                    })
                    pages_for_sort.append({
                        "offset": offset,
                        "seconds": round(time.perf_counter() - started, 6),
                        "returned": len(page["items"]),
                        "count": page["count"],
                    })
                    if page["count"] != track_count or len(page["items"]) > page_size or not page.get("paged"):
                        raise RuntimeError("sorted library query violated bounded pagination")
                if sort_key == "added":
                    order_by = "added_ns %s, title COLLATE NOCASE ASC, id ASC" % ("DESC" if sort_dir == "desc" else "ASC")
                elif sort_key == "track_no":
                    order_by = "CASE WHEN track_no <= 0 THEN 2147483647 ELSE track_no END %s, title COLLATE NOCASE ASC, id ASC" % ("DESC" if sort_dir == "desc" else "ASC")
                else:
                    order_by = "%s COLLATE NOCASE %s, title COLLATE NOCASE ASC, id ASC" % (
                        sort_key, "DESC" if sort_dir == "desc" else "ASC",
                    )
                plan = [
                    row[3] for row in conn.execute(
                        "EXPLAIN QUERY PLAN SELECT item_json FROM tracks ORDER BY %s LIMIT ? OFFSET ?" % order_by,
                        (page_size, offsets[-1]),
                    )
                ]
                sorted_pages[label] = {"pages": pages_for_sort, "plan": plan}
    # Measure the short-lived server-side page cache independently from the
    # preceding offset sweep. This represents a user reopening the same view
    # or two UI consumers asking for page one during the cache TTL; the first
    # read is deliberately cold and the second must retain identical output.
    library.invalidate_library_query_cache(config)
    first_page_params = {"view": "all", "sort": "title", "dir": "asc", "limit": str(page_size), "offset": "0"}
    cache_cold_started = time.perf_counter()
    cache_cold = library.query_library_page(config, first_page_params)
    cache_cold_seconds = time.perf_counter() - cache_cold_started
    cache_hot_started = time.perf_counter()
    cache_hot = library.query_library_page(config, first_page_params)
    cache_hot_seconds = time.perf_counter() - cache_hot_started
    cache_status = library.library_query_cache_status()
    if (
        cache_cold != cache_hot
        or cache_cold.get("count") != track_count
        or cache_status.get("hits", 0) < 1
        or cache_status.get("misses", 0) < 1
    ):
        raise RuntimeError("library page cache did not preserve a repeat page")
    # `/api/library` applies the cached metadata overlay after the raw SQLite
    # page has been read. Keep this cost visible beside the raw-page cache so
    # a fast index benchmark cannot conceal a slow lyrics/cover projection.
    # Seed one page with realistic cached rows; this path must remain bounded
    # to the visible page and preserve original Tag precedence.
    metadata = metadata_service.MetadataService(config)
    overlay_ids = [str(item.get("id") or "") for item in cache_cold.get("items", []) if item.get("id")]
    with metadata._connect() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO metadata_tracks(track_id,lyrics,artwork_id,orphaned_at) VALUES (?,?,?,0)",
            [(track_id, "[00:01.00]cached lyric %s" % track_id, "") for track_id in overlay_ids],
        )
        conn.executemany(
            """INSERT OR REPLACE INTO metadata_track_matches(
                   track_id,fields_json,status,orphaned_at
               ) VALUES (?,?, 'confirmed', 0)""",
            [
                (track_id, json.dumps({"best": {"album": "Cached Album %s" % track_id}}, separators=(",", ":")))
                for track_id in overlay_ids
            ],
        )
    overlay_cold_started = time.perf_counter()
    overlay_cold = metadata.enrich_track_page(cache_cold, include_lyrics=True)
    overlay_cold_seconds = time.perf_counter() - overlay_cold_started
    overlay_repeat_started = time.perf_counter()
    overlay_repeat = metadata.enrich_track_page(cache_cold, include_lyrics=True)
    overlay_repeat_seconds = time.perf_counter() - overlay_repeat_started
    overlay_cache = metadata._track_page_cache_status()
    if (
        len(overlay_cold.get("items", [])) != len(overlay_ids)
        or overlay_cold != overlay_repeat
        or not overlay_cold["items"]
        or not overlay_cold["items"][0].get("lyrics")
        or overlay_cold["items"][0].get("album") != cache_cold["items"][0].get("album")
        or overlay_cache.get("hits", 0) < 1
        or overlay_cache.get("misses", 0) < 1
    ):
        raise RuntimeError("metadata page overlay violated bounded, cache, or Tag-priority behavior")
    # Favorites, playlists and restored queues hydrate rows by ID rather than
    # through the visible library page. Measure that hot path independently so
    # its cache behavior remains visible as the front-end recovery flow evolves.
    library.invalidate_library_query_cache(config)
    hydration_ids = ["track-%06d" % index for index in range(min(page_size, track_count))]
    hydration_cold_started = time.perf_counter()
    hydration_cold = library.query_library_items_by_ids(config, hydration_ids)
    hydration_cold_seconds = time.perf_counter() - hydration_cold_started
    hydration_hot_started = time.perf_counter()
    hydration_hot = library.query_library_items_by_ids(config, hydration_ids)
    hydration_hot_seconds = time.perf_counter() - hydration_hot_started
    hydration_status = library.library_query_cache_status()
    if (
        hydration_cold != hydration_hot
        or [item.get("id") for item in hydration_hot] != hydration_ids
        or hydration_status.get("hits", 0) < 1
        or hydration_status.get("misses", 0) < 1
    ):
        raise RuntimeError("library item hydration cache did not preserve the ordered result")
    # Switching left-side categories is a common large-library hotspot. Measure
    # each independently so a slow group aggregation cannot hide behind a fast
    # folder query, and prove the short-lived SQLite cache keeps the result
    # stable for an immediate revisit.
    def repeat_browse(label, query):
        library.invalidate_library_query_cache(config)
        cold_started = time.perf_counter()
        cold = query()
        cold_seconds = time.perf_counter() - cold_started
        hot_started = time.perf_counter()
        hot = query()
        hot_seconds = time.perf_counter() - hot_started
        status = library.library_query_cache_status()
        if cold != hot or status.get("hits", 0) < 1 or status.get("misses", 0) < 1:
            raise RuntimeError("%s browse cache did not preserve the repeat result" % label)
        return cold, {
            "cold_seconds": round(cold_seconds, 6),
            "hot_seconds": round(hot_seconds, 6),
            "speedup": round(cold_seconds / hot_seconds if hot_seconds > 0 else 0.0, 3),
            "hits": status.get("hits", 0),
            "misses": status.get("misses", 0),
            "entries": status.get("entries", 0),
        }

    albums, album_cache = repeat_browse(
        "albums", lambda: library.query_library_groups(config, "albums", limit=page_size, offset=0)
    )
    album_tail_offset = max(0, group_cardinality(track_count) - page_size)
    albums_tail, album_tail_cache = repeat_browse(
        "albums_tail",
        lambda: library.query_library_groups(config, "albums", limit=page_size, offset=album_tail_offset),
    )
    library.invalidate_library_query_cache(config)
    album_seed = library.query_library_groups(config, "albums", limit=page_size, offset=0)
    album_cursor = album_seed.get("next_cursor") or ""
    cursor_started = time.perf_counter()
    album_cursor_page = library.query_library_groups(config, "albums", limit=page_size, offset=0, cursor=album_cursor)
    cursor_seconds = time.perf_counter() - cursor_started
    offset_started = time.perf_counter()
    album_offset_page = library.query_library_groups(config, "albums", limit=page_size, offset=page_size)
    offset_seconds = time.perf_counter() - offset_started
    albums_cursor = {
        "cursor_seconds": round(cursor_seconds, 6),
        "offset_seconds": round(offset_seconds, 6),
        "cursor_returned": len(album_cursor_page.get("groups", [])),
        "offset_returned": len(album_offset_page.get("groups", [])),
        "count": album_cursor_page.get("count", 0),
        "matching_page": [row.get("name") for row in album_cursor_page.get("groups", [])]
        == [row.get("name") for row in album_offset_page.get("groups", [])],
        "has_more": album_cursor_page.get("has_more") is True,
    }
    if not album_cursor or not albums_cursor["matching_page"]:
        raise RuntimeError("group cursor pagination did not match the following offset page")
    # A browse continuation has to stay two single-comparison statements: SQLite can
    # seek on each of them but not on the OR they replaced, which was one fewer query
    # and cost 1.90-11.90ms per page against 1.8-2.4ms here. Asserting the statement
    # shape is what stops a future predicate change from quietly going back to a scan.
    group_cursor_pages = {}
    plain_connect = library.library_db_connect
    traced_statements = []

    @contextlib.contextmanager
    def tracing_connect(current_config):
        with plain_connect(current_config) as connection:
            connection.set_trace_callback(traced_statements.append)
            yield connection

    library.library_db_connect = tracing_connect
    try:
        for sort_dir in ("asc", "desc"):
            seed_offset = page_size if sort_dir == "asc" else max(0, albums["count"] - 2 * page_size)
            cursor_seconds = []
            offset_seconds = []
            continuation = []
            offset_page = {}
            for _ in range(pagination_samples):
                library.LIBRARY_QUERY_CACHE.invalidate_database(library.library_db_path(config))
                seed = library.query_library_groups(
                    config, "albums", limit=page_size, offset=seed_offset, sort_dir=sort_dir
                )
                cursor_token = seed.get("next_cursor") or ""
                traced_statements.clear()
                started = time.perf_counter()
                cursor_page = library.query_library_groups(
                    config, "albums", limit=page_size, offset=0, cursor=cursor_token, sort_dir=sort_dir
                )
                cursor_seconds.append(time.perf_counter() - started)
                continuation = [
                    line for line in traced_statements
                    if line.startswith("SELECT * FROM (SELECT * FROM albums)")
                ]
                library.LIBRARY_QUERY_CACHE.invalidate_database(library.library_db_path(config))
                started = time.perf_counter()
                offset_page = library.query_library_groups(
                    config, "albums", limit=page_size, offset=seed_offset + page_size, sort_dir=sort_dir
                )
                offset_seconds.append(time.perf_counter() - started)
            if len(continuation) != 2 or any(" OR " in line for line in continuation):
                raise RuntimeError(
                    "group browse cursor stopped using two seekable statements: %s"
                    % " | ".join(continuation)
                )
            if not cursor_token or [row.get("name") for row in cursor_page.get("groups", [])] != [
                row.get("name") for row in offset_page.get("groups", [])
            ]:
                raise RuntimeError("group browse cursor page did not match the offset page")
            cursor_median = sorted(cursor_seconds)[len(cursor_seconds) // 2]
            offset_median = sorted(offset_seconds)[len(offset_seconds) // 2]
            group_cursor_pages[sort_dir] = {
                "offset": seed_offset + page_size,
                "cursor_seconds": round(cursor_median, 6),
                "offset_seconds": round(offset_median, 6),
                "cursor_versus_offset": round(
                    cursor_median / offset_median if offset_median > 0 else 0.0, 3
                ),
                "returned": len(cursor_page.get("groups", [])),
                "count": cursor_page.get("count", 0),
                "statements": len(continuation),
            }
    finally:
        library.library_db_connect = plain_connect
    creator_name = "Artist %04d" % 0
    creator_albums, creator_album_cache = repeat_browse(
        "creator_albums",
        lambda: library.query_library_groups(config, "albums", limit=page_size, offset=0, artist=creator_name),
    )
    folders, folder_cache = repeat_browse(
        "folders", lambda: library.query_library_folders(config, "", index_root, limit=page_size, offset=0)
    )
    roots, root_cache = repeat_browse("roots", lambda: library.query_library_root_folders(config))
    # An unfiltered browse page used to carry its total inside COUNT(*) OVER(),
    # which forced SQLite to sort every group before it could emit row one. Keep
    # the plan itself under test so a schema change cannot quietly come back.
    group_pages = {}
    with library.library_db_connect(config) as conn:
        for view in ("albums", "artists", "composers", "genres"):
            for sort_dir in ("asc", "desc"):
                plan = [
                    row[3] for row in conn.execute(
                        "EXPLAIN QUERY PLAN SELECT * FROM %s"
                        " ORDER BY name COLLATE NOCASE %s, name ASC LIMIT ? OFFSET ?"
                        % (view, "DESC" if sort_dir == "desc" else "ASC"),
                        (page_size, 0),
                    )
                ]
                index_name = "idx_%s_name_nocase_%s" % (view, sort_dir)
                detail = " | ".join(plan)
                if index_name not in detail or "TEMP B-TREE" in detail:
                    raise RuntimeError("group browse page lost its ordering index: %s %s" % (view, sort_dir))
                library.invalidate_library_query_cache(config)
                started = time.perf_counter()
                page = library.query_library_groups(config, view, limit=page_size, offset=0, sort_dir=sort_dir)
                seconds = time.perf_counter() - started
                if not page.get("paged") or len(page["groups"]) > page_size:
                    raise RuntimeError("group browse page violated bounded pagination: %s" % view)
                group_pages[view + "_" + sort_dir] = {
                    "seconds": round(seconds, 6),
                    "count": page["count"],
                    "returned": len(page["groups"]),
                    "plan": plan,
                }
        # A folder page is the first screen of the directory view, and its
        # ordering is the one browse shape that a plain (root, parent) index
        # cannot serve: without the NOCASE sibling of that index SQLite sorts
        # every child of the directory for a page of a hundred.
        folder_pages = {}
        for sort_dir in ("asc", "desc"):
            plan = [
                row[3] for row in conn.execute(
                    "EXPLAIN QUERY PLAN SELECT f.* FROM folders f"
                    " WHERE f.root = ? AND f.parent = ?"
                    " ORDER BY f.name COLLATE NOCASE %s, f.path ASC LIMIT ? OFFSET ?"
                    % ("DESC" if sort_dir == "desc" else "ASC"),
                    (index_root, "", page_size, 0),
                )
            ]
            index_name = "idx_folders_root_parent_name_nocase_%s" % sort_dir
            detail = " | ".join(plan)
            if index_name not in detail or "TEMP B-TREE" in detail:
                raise RuntimeError("folder browse page lost its ordering index: %s" % sort_dir)
            library.invalidate_library_query_cache(config)
            started = time.perf_counter()
            page = library.query_library_folders(config, "", index_root, sort_dir, page_size, 0)
            seconds = time.perf_counter() - started
            if (not page.get("paged") or len(page["folders"]) > page_size
                    or page["count"] != expected_top_level_folder_count()):
                raise RuntimeError("folder browse page violated bounded pagination: %s" % sort_dir)
            folder_pages[sort_dir] = {
                "seconds": round(seconds, 6),
                "count": page["count"],
                "returned": len(page["folders"]),
                "plan": plan,
            }
    # A folder search page over the wide parent. The unit tests assert this plan, but they build
    # a few dozen siblings, which is the regime where a seek and a scan cost the same; the R58
    # fold that replaced the per-sibling pass over `tracks` (library.py:1566-1588) only pays off
    # at thousands of siblings, so that is where the guard has to live.
    siblings = wide_folder_sibling_count(track_count)
    with library.library_db_connect(config) as conn:
        search_plan = [
            row[3] for row in conn.execute(
                "EXPLAIN QUERY PLAN SELECT f.* FROM folders f"
                " WHERE f.root = ? AND f.parent = ?"
                " ORDER BY f.name COLLATE NOCASE ASC, f.path ASC LIMIT ? OFFSET ?",
                (index_root, WIDE_FOLDER_PARENT, page_size, 0),
            )
        ]
    library.invalidate_library_query_cache(config)
    started = time.perf_counter()
    search_page = library.query_library_folders(
        config, WIDE_FOLDER_PARENT, index_root, search="Sibling 0000", limit=page_size, offset=0)
    search_seconds = time.perf_counter() - started
    search_detail = " | ".join(search_plan)
    if "idx_folders_root_parent_name_nocase_asc" not in search_detail or "TEMP B-TREE" in search_detail:
        raise RuntimeError("folder search page lost its ordering index: %s" % search_detail)
    if not search_page.get("paged") or len(search_page["folders"]) > page_size:
        raise RuntimeError("folder search page violated bounded pagination")
    if not search_page["folders"]:
        raise RuntimeError("folder search page matched nothing in a directory of %d siblings" % siblings)
    folder_search = {
        "siblings": siblings,
        "seconds": round(search_seconds, 6),
        "count": search_page["count"],
        "returned": len(search_page["folders"]),
        "plan": search_plan,
    }
    if (
        not albums.get("paged")
        or not folders.get("paged")
        or albums["count"] != group_cardinality(track_count)
        or not albums_tail.get("paged")
        or albums_tail["count"] != group_cardinality(track_count)
        or len(albums_tail["groups"]) > page_size
        or not creator_albums.get("paged")
        or creator_albums["count"] < 1
        or folders["count"] != expected_top_level_folder_count()
        or len(albums["groups"]) > page_size
        or len(folders["folders"]) > page_size
        or len(roots) != 1
        or roots[0]["track_count"] != track_count
        or roots[0]["cover_track_id"] != "track-000000"
    ):
        raise RuntimeError("group or folder query violated bounded pagination")
    search_term = "track %06d" % (track_count // 2)

    def search_page(mode):
        database = os.path.abspath(library.library_db_path(config))
        original_mode = library.LIBRARY_SEARCH_INDEX_MODE.get(database, "like")
        library.LIBRARY_SEARCH_INDEX_MODE[database] = mode
        library.invalidate_library_query_cache(config)
        try:
            started = time.perf_counter()
            page = library.query_library_page(config, {
                "view": "all", "search": search_term, "limit": str(page_size), "offset": "0",
            })
            return {
                "mode": mode,
                "seconds": round(time.perf_counter() - started, 6),
                "count": page["count"],
                "first_id": page["items"][0]["id"] if page["items"] else "",
            }
        finally:
            library.LIBRARY_SEARCH_INDEX_MODE[database] = original_mode
            library.invalidate_library_query_cache(config)

    search = {"term": search_term, "active": search_page(library.library_search_index_status(config)["mode"])}
    if search["active"]["mode"] == "fts5-trigram":
        search["like_baseline"] = search_page("like")
        active_seconds = search["active"]["seconds"]
        baseline_seconds = search["like_baseline"]["seconds"]
        # This is evidence for comparison only, not a pass/fail performance gate.
        search["speedup_vs_like"] = round(
            baseline_seconds / active_seconds if active_seconds > 0 else 0.0,
            3,
        )
    else:
        search["speedup_vs_like"] = None
    if search["active"]["count"] != 1 or search["active"]["first_id"] != "track-%06d" % (track_count // 2):
        raise RuntimeError("library search did not return the expected track")
    # Fixed per-request cost.  The first-screen page used to spend most of its
    # time reopening the WAL index instead of reading it, so compare the same cold
    # page with read handles reopened per request and reused from an idle pool.
    def cold_first_screen():
        library.invalidate_library_query_cache(config)
        started = time.perf_counter()
        page = library.query_library_page(config, {"view": "all", "limit": str(page_size), "offset": "0"})
        if len(page["items"]) != page_size:
            raise RuntimeError("first-screen page returned an unexpected number of rows")
        return time.perf_counter() - started

    def median_sample(function, samples=5):
        return sorted(function() for _ in range(samples))[samples // 2]

    pool_samples = 5
    unpooled_seconds = median_sample(cold_first_screen, pool_samples)
    library.close_library_connections()
    config[library.LIBRARY_CONNECTION_POOL_CONFIG_KEY] = True
    # Draining closes idle handles but does not rewind the counters, and this tool
    # also runs inside the offline gate where other modules may already have used
    # the pool, so the evidence has to be the traffic this sample window produced.
    pooled_before = library.library_connection_pool_status()
    try:
        pooled_seconds = median_sample(cold_first_screen, pool_samples)
        pool_status = library.library_connection_pool_status()
    finally:
        library.close_library_connections()
        config.pop(library.LIBRARY_CONNECTION_POOL_CONFIG_KEY, None)
    reuses = pool_status.get("reuses", 0) - pooled_before.get("reuses", 0)
    creations = pool_status.get("creations", 0) - pooled_before.get("creations", 0)
    if reuses < pool_samples - 1 or creations > 1:
        raise RuntimeError("library connection pool reopened the index instead of reusing it")
    if pooled_seconds >= unpooled_seconds:
        raise RuntimeError("pooled library reads are not faster than reopening the index")
    first_screen_connection = {
        "samples": pool_samples,
        "unpooled_seconds": round(unpooled_seconds, 6),
        "pooled_seconds": round(pooled_seconds, 6),
        "saving_seconds": round(unpooled_seconds - pooled_seconds, 6),
        "speedup": round(unpooled_seconds / pooled_seconds if pooled_seconds > 0 else 0.0, 3),
        "reuses": reuses,
        "creations": creations,
        "idle_after_drain": library.library_connection_pool_status().get("idle", 0),
    }
    # Untagged files are indexed with "" for artist, album, and format, which makes
    # the empty key group one of the largest in a real library. While an empty
    # primary could not be encoded, every page that ended inside that group answered
    # has_more with no next_cursor and the client had to keep paging by OFFSET.
    # The cluster is written after every timing section above so it cannot move them.
    empty_group_rows = min(1200, max(2, track_count // 2))
    empty_group_pages = []
    with library.library_db_connect(config) as conn:
        cluster = [row["id"] for row in conn.execute(
            "SELECT id FROM tracks ORDER BY id DESC LIMIT ?", (empty_group_rows,)
        )]
        for first in range(0, len(cluster), 500):
            batch = cluster[first:first + 500]
            rows = conn.execute(
                "SELECT id, item_json FROM tracks WHERE id IN (%s)" % ",".join("?" * len(batch)), batch
            ).fetchall()
            updates = []
            for row in rows:
                payload = json.loads(row["item_json"])
                for key in ("artist", "album", "format"):
                    payload.pop(key, None)
                updates.append((json.dumps(payload, separators=(",", ":")), row["id"]))
            conn.executemany("UPDATE tracks SET artist='', album='', format='', item_json=? WHERE id=?", updates)
    library.invalidate_library_query_cache(config)
    if empty_group_rows < 2:
        raise RuntimeError("empty key group cluster is too small to cross in one page")
    wide_page = min(500, max(page_size, 500))

    def empty_group_walk(sort_key, sort_dir, start_offset, steps=4):
        """Cross the empty key group by cursor and compare each page to its OFFSET twin."""
        library.invalidate_library_query_cache(config)
        query = {"view": "all", "sort": sort_key, "dir": sort_dir, "limit": str(wide_page)}

        def offset_page(at):
            started = time.perf_counter()
            page = library.query_library_page(config, dict(query, offset=str(at)))
            return page, time.perf_counter() - started

        def cursor_page_after(token):
            started = time.perf_counter()
            page = library.query_library_page(config, dict(query, offset="0", cursor=token))
            return page, time.perf_counter() - started

        seed, _ = offset_page(start_offset)
        if not seed.get("has_more"):
            raise RuntimeError("empty key group seed page is not paged (%s/%s)" % (sort_key, sort_dir))
        token = seed.get("next_cursor") or ""
        if not token:
            raise RuntimeError(
                "a page ending in the empty key group lost its continuation cursor (%s/%s)" % (sort_key, sort_dir)
            )
        visited = []
        for step in range(steps):
            page, offset_seconds = offset_page(start_offset + wide_page * (step + 1))
            expected = [item.get("id") for item in page.get("items", [])]
            returned_page, cursor_seconds = cursor_page_after(token)
            returned = [item.get("id") for item in returned_page.get("items", [])]
            if returned != expected or not returned_page.get("paged"):
                raise RuntimeError(
                    "keyset continuation across the empty key group diverged from OFFSET (%s/%s)" % (sort_key, sort_dir)
                )
            visited.append({
                "step": step,
                "cursor_seconds": round(cursor_seconds, 6),
                "offset_seconds": round(offset_seconds, 6),
                "returned": len(returned),
                "has_more": returned_page.get("has_more") is True,
                "continues": bool(returned_page.get("next_cursor")),
            })
            token = returned_page.get("next_cursor") or ""
            if not returned_page.get("has_more") or not token:
                break
        return visited

    empty_group = {
        "rows": empty_group_rows,
        "page_size": wide_page,
        "walks": {},
    }
    # The asc walk seeds at offset 0, so its OFFSET twin stays shallow and cannot show
    # deep-paging cost; that comparison is measured by cursor_pagination above. This
    # section only proves continuation across the empty key group is correct.
    for sort_key, sort_dir, start_offset in (
        ("artist", "asc", 0),
        ("artist", "desc", max(0, track_count - empty_group_rows - wide_page)),
        ("format", "desc", max(0, track_count - empty_group_rows - wide_page)),
    ):
        steps = empty_group_walk(sort_key, sort_dir, start_offset)
        if not steps:
            raise RuntimeError("empty key group walk visited no page (%s/%s)" % (sort_key, sort_dir))
        for entry in steps:
            if entry["has_more"] and not entry["continues"]:
                raise RuntimeError(
                    "has_more was reported without a continuation cursor (%s/%s)" % (sort_key, sort_dir)
                )
        empty_group["walks"]["%s_%s" % (sort_key, sort_dir)] = steps

    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    db_path = library.library_db_path(config)
    return {
        "tracks": track_count,
        "page_size": page_size,
        "runtime": {
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
        },
        "database_bytes": os.path.getsize(db_path),
        "build_seconds": round(build_seconds, 6),
        "query_seconds": round(query_seconds, 6),
        "query_peak_python_bytes": peak_bytes,
        "bounded_pagination": True,
        "pages": pages,
        "cursor_pagination": cursor_pagination,
        "first_screen_connection": first_screen_connection,
        "empty_key_group_pagination": empty_group,
        "sorted_pages": sorted_pages,
        "page_cache": {
            "cold_seconds": round(cache_cold_seconds, 6),
            "hot_seconds": round(cache_hot_seconds, 6),
            "speedup": round(cache_cold_seconds / cache_hot_seconds if cache_hot_seconds > 0 else 0.0, 3),
            "hits": cache_status.get("hits", 0),
            "misses": cache_status.get("misses", 0),
            "entries": cache_status.get("entries", 0),
        },
        "metadata_page_overlay": {
            "items": len(overlay_ids),
            "cold_seconds": round(overlay_cold_seconds, 6),
            "repeat_seconds": round(overlay_repeat_seconds, 6),
            "speedup": round(overlay_cold_seconds / overlay_repeat_seconds if overlay_repeat_seconds > 0 else 0.0, 3),
            "cache_hits": overlay_cache.get("hits", 0),
            "cache_misses": overlay_cache.get("misses", 0),
            "cache_entries": overlay_cache.get("entries", 0),
            "cache_limit": overlay_cache.get("limit", 0),
            "tag_precedence": True,
        },
        "item_hydration_cache": {
            "ids": len(hydration_ids),
            "cold_seconds": round(hydration_cold_seconds, 6),
            "hot_seconds": round(hydration_hot_seconds, 6),
            "speedup": round(hydration_cold_seconds / hydration_hot_seconds if hydration_hot_seconds > 0 else 0.0, 3),
            "hits": hydration_status.get("hits", 0),
            "misses": hydration_status.get("misses", 0),
            "entries": hydration_status.get("entries", 0),
        },
        "browse": {
            "albums": {"count": albums["count"], "returned": len(albums["groups"]), **album_cache},
        "albums_tail": {
                "offset": album_tail_offset,
                "count": albums_tail["count"],
                "returned": len(albums_tail["groups"]),
                **album_tail_cache,
            },
            "albums_cursor": albums_cursor,
            "group_cursor_pages": group_cursor_pages,
            "creator_albums": {
                "artist": creator_name, "count": creator_albums["count"],
                "returned": len(creator_albums["groups"]), **creator_album_cache,
            },
            "folders": {"count": folders["count"], "returned": len(folders["folders"]), **folder_cache},
            "roots": {"count": len(roots), "track_count": roots[0]["track_count"], **root_cache},
            "group_pages": group_pages,
            "folder_pages": folder_pages,
            "folder_search": folder_search,
        },
        "search": search,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracks", type=int, default=100000)
    parser.add_argument("--page-size", type=int, default=120)
    parser.add_argument("--cache-dir")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.tracks < 1 or args.page_size < 1 or args.page_size > 500:
        parser.error("tracks must be positive and page-size must be between 1 and 500")
    if args.cache_dir:
        os.makedirs(args.cache_dir, exist_ok=True)
        result = run_benchmark(args.cache_dir, args.tracks, args.page_size)
    else:
        with tempfile.TemporaryDirectory(prefix="fnaudio-library-benchmark-") as cache_dir:
            result = run_benchmark(cache_dir, args.tracks, args.page_size)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(output), exist_ok=True)
        with open(output, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload + "\n")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
