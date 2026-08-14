#!/usr/bin/env python3
import json
import os
import shutil
import sys
import time


server_root = "/vol1/@appcenter/fnaudio/server"
sys.path.insert(0, server_root)

from cover_cache import cached_thumbnail_for_item, cover_is_known_missing
from library import query_library_page, read_cover_for_item


def elapsed(call):
    started = time.perf_counter()
    value = call()
    return value, round((time.perf_counter() - started) * 1000, 2)


def main():
    with open("/vol1/@appconf/fnaudio/config.json", "r", encoding="utf-8") as handle:
        config = json.load(handle)
    config.setdefault("cache_dir", "/vol1/@appconf/fnaudio/transcode")
    cache_root = os.path.join(config["cache_dir"], "covers")
    if os.path.isdir(cache_root):
        shutil.rmtree(cache_root)

    page = query_library_page(config, {"view": ["all"], "limit": ["500"], "offset": ["0"]})
    covered = None
    missing = None
    for item in page.get("items") or []:
        mime, body = read_cover_for_item(item, config)
        if body and covered is None:
            covered = (item, mime, len(body))
        elif not body and missing is None:
            missing = item
        if covered and missing:
            break

    result = {"cache_root": cache_root, "covered": None, "missing": None}
    if covered:
        item, original_mime, original_bytes = covered
        first, cold_ms = elapsed(lambda: cached_thumbnail_for_item(item, config, 160, read_cover_for_item))
        second, hot_ms = elapsed(lambda: cached_thumbnail_for_item(item, config, 160, read_cover_for_item))
        result["covered"] = {
            "id": item["id"],
            "title": item.get("title"),
            "original_mime": original_mime,
            "original_bytes": original_bytes,
            "thumbnail_mime": first[0],
            "thumbnail_bytes": len(first[1] or b""),
            "cold_ms": cold_ms,
            "hot_ms": hot_ms,
            "stable": first == second,
        }
    if missing:
        _first, cold_ms = elapsed(lambda: cached_thumbnail_for_item(missing, config, 160, read_cover_for_item))
        _second, hot_ms = elapsed(lambda: cached_thumbnail_for_item(missing, config, 160, read_cover_for_item))
        result["missing"] = {
            "id": missing["id"],
            "title": missing.get("title"),
            "cold_ms": cold_ms,
            "hot_ms": hot_ms,
            "negative_cached": cover_is_known_missing(missing, config, 160),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
