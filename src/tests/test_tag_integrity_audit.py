import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest


TOOL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tools", "audit_tag_integrity.py"))
SPEC = importlib.util.spec_from_file_location("tag_integrity_audit", TOOL_PATH)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class TagIntegrityAuditTests(unittest.TestCase):
    def _database(self, root, status="done", tag_sources=True):
        path = os.path.join(root, "library.sqlite3")
        media = os.path.join(root, "song.mp3")
        with open(media, "wb") as handle:
            handle.write(b"not a real audio file")
        conn = sqlite3.connect(path)
        try:
            conn.executescript(
                """CREATE TABLE tracks(id TEXT PRIMARY KEY,path TEXT,title TEXT,artist TEXT,album TEXT,format TEXT,item_json TEXT);
                   CREATE TABLE metadata_jobs(job_key TEXT,job_type TEXT,status TEXT,updated_at INTEGER);"""
            )
            sources = {"title": "tag", "artist": "tag", "album": "tag"} if tag_sources else {"title": "filename", "artist": "filename", "album": "unknown"}
            item_json = json.dumps({"metadata_source": sources})
            conn.execute("INSERT INTO tracks VALUES (?,?,?,?,?,?,?)", ("one", media, "Title", "Artist", "Album", "MP3", item_json))
            conn.execute("INSERT INTO metadata_jobs VALUES (?,?,?,?)", ("tag:one", "tag_write", status, 123))
            conn.commit()
        finally:
            conn.close()
        return path

    def test_completed_tag_write_with_lost_tag_data_is_high_confidence(self):
        with tempfile.TemporaryDirectory() as root:
            result = AUDIT.audit(self._database(root))
        self.assertEqual(result["summary"]["findings"], 1)
        finding = result["findings"][0]
        self.assertEqual(finding["confidence"], "high")
        self.assertEqual(finding["recovery"], "restore_from_snapshot_or_backup")
        self.assertEqual(finding["missing_tag_fields"], ["title", "artist", "album"])
        self.assertIn("completed_tag_write_record", finding["reasons"])

    def test_missing_cover_without_tag_write_is_review_only(self):
        with tempfile.TemporaryDirectory() as root:
            result = AUDIT.audit(self._database(root, status="pending", tag_sources=False))
        finding = result["findings"][0]
        self.assertEqual(finding["confidence"], "review")
        self.assertNotIn("completed_tag_write_record", finding["reasons"])
