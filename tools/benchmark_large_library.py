#!/usr/bin/env python3
"""Build a synthetic library index and measure bounded SQLite page reads."""

from __future__ import annotations

import argparse
import gc
import json
import os
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


def _populate(config: Dict[str, Any], track_count: int) -> float:
    started = time.perf_counter()
    insert_sql = """
        INSERT INTO tracks(id,path,title,artist,album,format,item_json)
        VALUES (?,?,?,?,?,?,?)
    """
    with library.library_db_connect(config) as conn:
        for first in range(0, track_count, 2000):
            rows = []
            for index in range(first, min(first + 2000, track_count)):
                track_id = "track-%06d" % index
                item = {
                    "id": track_id,
                    "path": "/benchmark/%s.flac" % track_id,
                    "title": "Track %06d" % index,
                    "artist": "Artist %04d" % (index % 1000),
                    "album": "Album %04d" % (index % 2000),
                    "format": "FLAC",
                }
                rows.append((track_id, item["path"], item["title"], item["artist"], item["album"], item["format"], json.dumps(item, separators=(",", ":"))))
            conn.executemany(insert_sql, rows)
        conn.execute("INSERT OR REPLACE INTO library_meta(key,value) VALUES (?,?)", ("library_path", library.display_library_path(config)))
        conn.execute("INSERT OR REPLACE INTO library_meta(key,value) VALUES (?,?)", ("metadata_version", str(library.METADATA_VERSION)))
        conn.execute("INSERT OR REPLACE INTO library_meta(key,value) VALUES (?,?)", ("signature", "synthetic-%d" % track_count))
    return time.perf_counter() - started


def run_benchmark(cache_dir: str, track_count: int = 100000, page_size: int = 120) -> Dict[str, Any]:
    config = {"cache_dir": cache_dir, "library_paths": ["/benchmark"]}
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
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    db_path = library.library_db_path(config)
    return {
        "tracks": track_count,
        "page_size": page_size,
        "database_bytes": os.path.getsize(db_path),
        "build_seconds": round(build_seconds, 6),
        "query_seconds": round(query_seconds, 6),
        "query_peak_python_bytes": peak_bytes,
        "bounded_pagination": True,
        "pages": pages,
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
