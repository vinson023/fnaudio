#!/usr/bin/env python3
"""Read-only audit for media tags potentially affected by fnAudio 0.1.213-0.1.215."""

import argparse
import csv
import json
import os
import sqlite3
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1] / "src" / "app" / "server"
sys.path.insert(0, str(SERVER_DIR))

from library import read_cover_for_item, read_probe_tags  # noqa: E402

WRITABLE = {".mp3", ".flac", ".m4a", ".mp4"}
PLACEHOLDERS = {"", "unknown", "未知艺术家", "未分类", "未分类专辑"}


def readonly_connection(path):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def stored_tag_sources(item_json):
    try:
        return (json.loads(item_json or "{}").get("metadata_source") or {})
    except (TypeError, ValueError):
        return {}


def audit(database, limit=0):
    findings = []
    summary = {"tracks_checked": 0, "missing_cover": 0, "tag_regression": 0, "tag_write_evidence": 0}
    conn = readonly_connection(database)
    try:
        rows = conn.execute(
            """SELECT t.id,t.path,t.title,t.artist,t.album,t.format,t.item_json,
                      j.status AS tag_status,j.updated_at AS tag_updated_at
               FROM tracks t
               LEFT JOIN metadata_jobs j ON j.job_key='tag:' || t.id AND j.job_type='tag_write'
               ORDER BY t.path"""
        )
        for row in rows:
            if limit and summary["tracks_checked"] >= limit:
                break
            summary["tracks_checked"] += 1
            path = str(row["path"] or "")
            if os.path.splitext(path)[1].lower() not in WRITABLE or not os.path.isfile(path):
                continue
            item = {"path": path, "cue_path": ""}
            _, cover = read_cover_for_item(item)
            current = read_probe_tags(path)
            sources = stored_tag_sources(row["item_json"])
            missing_fields = []
            for field in ("title", "artist", "album"):
                expected = str(row[field] or "").strip()
                if sources.get(field) == "tag" and expected.casefold() not in PLACEHOLDERS and not str(current.get(field) or "").strip():
                    missing_fields.append(field)
            reasons = []
            if not cover:
                summary["missing_cover"] += 1
                reasons.append("missing_local_cover")
            if missing_fields:
                summary["tag_regression"] += 1
                reasons.append("stored_tag_now_empty:" + ",".join(missing_fields))
            if str(row["tag_status"] or "") == "done" and reasons:
                summary["tag_write_evidence"] += 1
                reasons.append("completed_tag_write_record")
            if not reasons:
                continue
            confidence = "high" if missing_fields or (not cover and str(row["tag_status"] or "") == "done") else "review"
            findings.append({
                "track_id": row["id"], "path": path, "title": row["title"], "artist": row["artist"], "album": row["album"],
                "missing_tag_fields": missing_fields, "has_local_cover": bool(cover), "tag_job_status": row["tag_status"] or "",
                "tag_job_updated_at": int(row["tag_updated_at"] or 0), "reasons": reasons, "confidence": confidence,
                "recovery": "restore_from_snapshot_or_backup" if confidence == "high" else "review_before_metadata_backfill",
            })
    finally:
        conn.close()
    summary["findings"] = len(findings)
    summary["high_confidence"] = sum(item["confidence"] == "high" for item in findings)
    return {"database": str(Path(database).resolve()), "read_only": True, "summary": summary, "findings": findings}


def write_csv(path, findings):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["confidence", "track_id", "path", "title", "artist", "album", "missing_tag_fields", "has_local_cover", "tag_job_status", "tag_job_updated_at", "reasons", "recovery"])
        writer.writeheader()
        for item in findings:
            row = dict(item)
            row["missing_tag_fields"] = ",".join(row["missing_tag_fields"])
            row["reasons"] = ";".join(row["reasons"])
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Read-only fnAudio tag integrity audit")
    parser.add_argument("--database", required=True, help="Path to fnAudio library.sqlite3")
    parser.add_argument("--report", required=True, help="Output JSON report path")
    parser.add_argument("--csv", help="Optional CSV findings path")
    parser.add_argument("--limit", type=int, default=0, help="Maximum tracks to inspect (0 means all)")
    args = parser.parse_args()
    result = audit(args.database, max(0, args.limit))
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    if args.csv:
        Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
        write_csv(args.csv, result["findings"])
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
