import base64
import json
import sqlite3
import sys
import unittest

sys.path.insert(0, "app/server")

from library_cursor_policy import (
    MAX_CURSOR_TEXT,
    anchor_is_encodable,
    cursor_group_tail_where,
    cursor_next_group_where,
    cursor_page,
    decode_track_cursor,
    encode_track_cursor,
)
from library_query_spec import TRACK_SORT_COLUMNS, parse_library_page_query

SORT_KEYS = ("title", "artist", "album", "format", "added", "track_no")
TEXT_SORT_KEYS = {"title", "artist", "album", "format"}
CURSORS = {"title": "Song 2", "artist": "Adele", "album": "Alpha", "format": "FLAC", "added": 42, "track_no": 3}
# t-09/t-10/t-11 share every ordering key, t-01/t-02 differ only in ASCII case,
# t-04 carries a NULL artist and t-05 an empty one, which is what an untagged
# file indexes as, t-13 has an empty title, and t-14 keeps the empty row id a
# TEXT primary key permits. One table therefore covers the tie-break, the NOCASE
# fold, the empty key group, the empty id, and the unencodable NULL.
ROWS = [
    {"id": "t-01", "title": "A Song", "artist": "Adele", "album": "Alpha", "format": "FLAC", "added_ns": 100, "track_no": 3},
    {"id": "t-02", "title": "a song", "artist": "ADELE", "album": "Alpha", "format": "FLAC", "added_ns": 100, "track_no": 0},
    {"id": "t-03", "title": "Z Song", "artist": "adele", "album": "Beta", "format": "MP3", "added_ns": 90, "track_no": -1},
    {"id": "t-04", "title": "\u00c5sa", "artist": None, "album": "", "format": "WAV", "added_ns": 120, "track_no": 1},
    {"id": "t-05", "title": "asa", "artist": "", "album": "\u00c5lpha", "format": "ALAC", "added_ns": 110, "track_no": 2147483647},
    {"id": "t-06", "title": "\u00c5SA", "artist": "Bj\u00f6rk", "album": "\u00e5lpha", "format": "MP3", "added_ns": 110, "track_no": 2},
    {"id": "t-07", "title": "0 Numeric", "artist": "Numerics", "album": "Ninety", "format": "DSD", "added_ns": 80, "track_no": 1},
    {"id": "t-08", "title": "numeric", "artist": "numerics", "album": "ninety", "format": "dsd", "added_ns": 80, "track_no": 1},
    {"id": "t-09", "title": "Same Title", "artist": "Twin", "album": "Twin", "format": "FLAC", "added_ns": 70, "track_no": 9},
    {"id": "t-10", "title": "Same Title", "artist": "Twin", "album": "Twin", "format": "FLAC", "added_ns": 70, "track_no": 9},
    {"id": "t-11", "title": "Same Title", "artist": "Twin", "album": "Twin", "format": "FLAC", "added_ns": 70, "track_no": 9},
    {"id": "t-12", "title": "Tie Tail", "artist": "Twin", "album": "Twin", "format": "AIFF", "added_ns": 70, "track_no": 9},
    {"id": "t-13", "title": "", "artist": "Adele", "album": "Alpha", "format": "FLAC", "added_ns": 130, "track_no": 4},
    {"id": "", "title": "Empty Id", "artist": "Adele", "album": "Alpha", "format": "FLAC", "added_ns": 100, "track_no": 5},
]
TIE = TRACK_SORT_COLUMNS["title"]


def _rewrite_token(token, changes=(), drops=()):
    """Rebuild a cursor token with payload keys changed or dropped."""
    payload = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode("utf-8"))
    for key in drops:
        payload.pop(key)
    payload.update(dict(changes))
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _fold(value):
    """Mirror SQLite NOCASE, which folds ASCII A-Z only."""
    if value is None:
        return None
    return "".join(chr(ord(char) + 32) if "A" <= char <= "Z" else char for char in value)


class LibraryCursorPolicyTests(unittest.TestCase):
    def test_round_trip_is_bounded_and_detached(self):
        token = encode_track_cursor("title", "asc", "Song 2", "Song 2", "track-2")
        decoded = decode_track_cursor(token)
        self.assertEqual(
            decoded,
            {"sort": "title", "dir": "asc", "primary": "Song 2", "title": "Song 2", "id": "track-2", "inclusive": False},
        )
        self.assertIsNot(decoded, decode_track_cursor(token))
        # The flag is sparse: a page that ends on a row it already served keeps
        # producing the byte-identical token it produced before the field existed.
        self.assertNotIn("i", json.loads(base64.urlsafe_b64decode(token + "==")))

    def test_next_group_predicate_is_a_single_seekable_range(self):
        # SQLite only seeks a contiguous range, and it cannot prove that an OR
        # over the same prefix is contiguous when each repeat of the cursor value
        # arrives as its own anonymous parameter. A single comparison is the
        # shape that measured 0.07ms instead of a 2.8-6.5ms index walk.
        for sort_key in SORT_KEYS:
            for sort_dir in ("asc", "desc"):
                query = parse_library_page_query({"sort": sort_key, "dir": sort_dir})
                token = encode_track_cursor(sort_key, sort_dir, CURSORS[sort_key], "Song 2", "track-2")
                predicate, args = cursor_next_group_where(query, decode_track_cursor(token))
                label = "%s/%s" % (sort_key, sort_dir)
                operator = "<" if sort_dir == "desc" else ">"
                self.assertEqual(predicate, "%s %s ?" % (query.sql_order, operator), label)
                self.assertNotIn(" OR ", predicate)
                self.assertEqual(len(args), 1, label)
                expected = "Song 2" if sort_key == "title" else CURSORS[sort_key]
                self.assertEqual(args, [expected], label)

    def test_group_tail_predicate_is_direction_independent(self):
        # The tie-break is always ascending, whichever way the primary key runs,
        # because `sql_order_by` keeps `title COLLATE NOCASE ASC, id ASC`. The
        # continuation of one group therefore has to be the same statement in
        # both directions, and it has to be strict: the cursor row was served.
        for sort_key in SORT_KEYS:
            statements = {}
            for sort_dir in ("asc", "desc"):
                query = parse_library_page_query({"sort": sort_key, "dir": sort_dir})
                token = encode_track_cursor(sort_key, sort_dir, CURSORS[sort_key], "Song 2", "track-2")
                predicate, args = cursor_group_tail_where(query, decode_track_cursor(token))
                label = "%s/%s" % (sort_key, sort_dir)
                self.assertNotIn(" OR ", predicate)
                self.assertEqual(predicate.count("?"), len(args), label)
                statements[sort_dir] = (predicate, args)
            self.assertEqual(statements["asc"], statements["desc"], sort_key)
            predicate, args = statements["asc"]
            if sort_key == "title":
                self.assertEqual(predicate, "title COLLATE NOCASE = ? AND id > ?")
                self.assertEqual(args, ["Song 2", "track-2"])
            else:
                self.assertEqual(predicate, "%s = ? AND (title COLLATE NOCASE, id) > (?, ?)" % query.sql_order)
                self.assertEqual(args, [CURSORS[sort_key], "Song 2", "track-2"])

    def test_inconsistent_title_cursor_follows_the_title_key(self):
        # `sort=title` orders by the title itself, so a cursor carrying a
        # different primary value must not move the window off that row.
        query = parse_library_page_query({"sort": "title", "dir": "asc"})
        decoded = decode_track_cursor(encode_track_cursor("title", "asc", "Song 2", "Song 9", "track-9"))
        self.assertEqual(cursor_next_group_where(query, decoded), ("title COLLATE NOCASE > ?", ["Song 9"]))
        self.assertEqual(
            cursor_group_tail_where(query, decoded),
            ("title COLLATE NOCASE = ? AND id > ?", ["Song 9", "track-9"]),
        )

    def test_malformed_or_mismatched_cursor_is_ignored(self):
        query = parse_library_page_query({"sort": "title", "dir": "asc"})
        self.assertIsNone(decode_track_cursor("not-a-cursor"))
        for decoder in (decode_track_cursor("not-a-cursor"), None):
            self.assertIsNone(cursor_page(decoder, query))
            self.assertEqual(cursor_next_group_where(query, decoder), ("", []))
            self.assertEqual(cursor_group_tail_where(query, decoder), ("", []))
        token = encode_track_cursor("album", "asc", "A", "Song", "track-1")
        self.assertIsNone(cursor_page(decode_track_cursor(token), query))
        self.assertEqual(cursor_next_group_where(query, decode_track_cursor(token)), ("", []))
        self.assertEqual(cursor_group_tail_where(query, decode_track_cursor(token)), ("", []))
        self.assertIsNone(decode_track_cursor("!!!!"))

    def test_untrusted_values_never_trigger_object_conversion(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("must not stringify")

        self.assertEqual(encode_track_cursor("title", "asc", Explosive(), "Song", "id"), "")
        self.assertIsNone(decode_track_cursor(Explosive()))

    def test_overlong_primary_key_is_rejected_instead_of_truncated(self):
        primary = "x" * (MAX_CURSOR_TEXT + 1)
        self.assertEqual(encode_track_cursor("title", "asc", primary, "Song", "id"), "")

    def test_an_empty_key_group_is_encodable_but_a_missing_field_is_not(self):
        # Untagged files are indexed with "" for artist, album and format, so the
        # empty value has to survive a round trip or every page ending inside that
        # cluster loses its continuation.
        for sort_key in ("artist", "album", "format"):
            for sort_dir in ("asc", "desc"):
                token = encode_track_cursor(sort_key, sort_dir, "", "Song 2", "track-2")
                self.assertEqual(
                    decode_track_cursor(token),
                    {"sort": sort_key, "dir": sort_dir, "primary": "", "title": "Song 2", "id": "track-2", "inclusive": False},
                    "%s/%s" % (sort_key, sort_dir),
                )
                query = parse_library_page_query({"sort": sort_key, "dir": sort_dir})
                decoded = decode_track_cursor(token)
                operator = "<" if sort_dir == "desc" else ">"
                self.assertEqual(cursor_next_group_where(query, decoded), ("%s %s ?" % (query.sql_order, operator), [""]))
                self.assertEqual(
                    cursor_group_tail_where(query, decoded),
                    ("%s = ? AND (title COLLATE NOCASE, id) > (?, ?)" % query.sql_order, ["", "Song 2", "track-2"]),
                )

    def test_an_empty_row_id_anchors_a_continuation(self):
        # tracks.id is a TEXT primary key, so "" is a value a row can really hold -
        # prepare_track_persistence falls back to it for an item that lost its id -
        # and it is the smallest id there is, so a cursor naming it still resolves
        # its group exactly: the strict tail skips that one row and nothing else.
        for sort_key in ("artist", "title"):
            token = encode_track_cursor(sort_key, "asc", "Adele", "Song", "")
            query = parse_library_page_query({"sort": sort_key, "dir": "asc"})
            decoded = decode_track_cursor(token)
            self.assertEqual(
                decoded,
                {"sort": sort_key, "dir": "asc", "primary": "Adele", "title": "Song", "id": "", "inclusive": False},
            )
            expected = (
                ("title COLLATE NOCASE = ? AND id > ?", ["Song", ""])
                if sort_key == "title"
                else ("artist COLLATE NOCASE = ? AND (title COLLATE NOCASE, id) > (?, ?)", ["Adele", "Song", ""])
            )
            self.assertEqual(cursor_group_tail_where(query, decoded), expected, sort_key)

    def test_unusable_anchor_values_stay_unencodable(self):
        self.assertEqual(encode_track_cursor("artist", "asc", "Adele", None, "track-9"), "")
        self.assertEqual(encode_track_cursor("artist", "asc", None, "Song", "track-9"), "")
        self.assertEqual(encode_track_cursor("artist", "asc", 1.5, "Song", "track-9"), "")
        self.assertEqual(encode_track_cursor("artist", "asc", True, "Song", "track-9"), "")
        self.assertEqual(encode_track_cursor("artist", "asc", "x" * (MAX_CURSOR_TEXT + 1), "Song", "track-9"), "")

    def test_absent_payload_fields_stay_malformed(self):
        token = encode_track_cursor("artist", "asc", "Adele", "Song 2", "track-2")
        raw = json.loads(base64.urlsafe_b64decode(token + "==").decode("utf-8"))
        for dropped in ("p", "t", "id"):
            payload = dict(raw)
            payload.pop(dropped)
            rebuilt = base64.urlsafe_b64encode(
                json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).decode("ascii").rstrip("=")
            self.assertIsNone(decode_track_cursor(rebuilt), dropped)
        # An explicit empty string is a value, not a missing field, for all three
        # keys: the empty id is the smallest one the table can hold.
        for field, accepted in (("p", True), ("t", True), ("id", True)):
            payload = dict(raw)
            payload[field] = ""
            rebuilt = base64.urlsafe_b64encode(
                json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).decode("ascii").rstrip("=")
            decoded = decode_track_cursor(rebuilt)
            self.assertEqual(decoded is not None, accepted, field)

    def test_an_empty_title_still_resolves_by_id(self):
        query = parse_library_page_query({"sort": "artist", "dir": "asc"})
        decoded = decode_track_cursor(encode_track_cursor("artist", "asc", "Adele", "", "track-9"))
        self.assertEqual(
            cursor_group_tail_where(query, decoded),
            ("artist COLLATE NOCASE = ? AND (title COLLATE NOCASE, id) > (?, ?)", ["Adele", "", "track-9"]),
        )


class LibraryCursorEquivalenceTests(unittest.TestCase):
    """The group tail plus the following groups must be exactly the rows after the cursor."""

    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect(":memory:")
        cls.conn.row_factory = sqlite3.Row
        cls.conn.execute(
            "CREATE TABLE tracks (id TEXT PRIMARY KEY, title TEXT, artist TEXT, album TEXT,"
            " format TEXT, added_ns INTEGER, track_no INTEGER)"
        )
        cls.conn.executemany(
            "INSERT INTO tracks (id, title, artist, album, format, added_ns, track_no)"
            " VALUES (:id, :title, :artist, :album, :format, :added_ns, :track_no)",
            ROWS,
        )

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def _primary_value(self, row, sort_key):
        if sort_key == "added":
            return row["added_ns"]
        if sort_key == "track_no":
            return 2147483647 if row["track_no"] <= 0 else row["track_no"]
        return row[sort_key]

    def _primary_key(self, row, sort_key):
        primary = self._primary_value(row, sort_key)
        if sort_key in TEXT_SORT_KEYS:
            primary = _fold(primary)
        # NULL sorts before every value, so reversing only the primary key puts
        # NULL last for DESC, which is what SQLite does as well.
        return (0, None) if primary is None else (1, primary)

    def _suffix_key(self, row, sort_key):
        # `sql_order_by` keeps the tie-break ascending even for a DESC primary,
        # and omits the title entirely when the title already is the primary.
        if sort_key == "title":
            return (row["id"],)
        return (_fold(row["title"]), row["id"])

    def _ordered_rows(self, sort_key, sort_dir):
        # Two stable passes reproduce a mixed-direction index: order by the
        # ascending tie-break first, then reverse only the primary key.
        rows = sorted(ROWS, key=lambda row: self._suffix_key(row, sort_key))
        return sorted(rows, key=lambda row: self._primary_key(row, sort_key), reverse=sort_dir == "desc")

    def _token(self, query, anchor, inclusive=False):
        return encode_track_cursor(
            query.sort_key,
            query.sort_dir,
            self._primary_value(anchor, query.sort_key),
            anchor["title"],
            anchor["id"],
            inclusive,
        )

    def _sql_page(self, query, anchor, limit, inclusive=False):
        decoded = decode_track_cursor(self._token(query, anchor, inclusive))
        self.assertIsNotNone(decoded, "%s/%s from %s" % (query.sort_key, query.sort_dir, anchor["id"]))
        tail_predicate, tail_args = cursor_group_tail_where(query, decoded)
        next_predicate, next_args = cursor_next_group_where(query, decoded)
        self.assertTrue(tail_predicate and next_predicate, "cursor predicates must not be empty")
        # This mirrors what library._cursor_page_rows does: read the rest of the
        # cursor's own group, then continue with the groups that follow it.
        rows = self.conn.execute(
            "SELECT id FROM tracks WHERE %s ORDER BY %s LIMIT ?" % (tail_predicate, query.sql_order_by),
            tail_args + [limit + 1],
        ).fetchall()
        budget = limit + 1 - len(rows)
        if budget > 0:
            rows = rows + self.conn.execute(
                "SELECT id FROM tracks WHERE %s ORDER BY %s LIMIT ?" % (next_predicate, query.sql_order_by),
                next_args + [budget],
            ).fetchall()
        return [row["id"] for row in rows][:limit]

    def test_every_cursor_position_continues_the_page_order(self):
        limit = 4
        for sort_key in SORT_KEYS:
            for sort_dir in ("asc", "desc"):
                query = parse_library_page_query({"sort": sort_key, "dir": sort_dir})
                ordered = self._ordered_rows(sort_key, sort_dir)
                for index, anchor in enumerate(ordered):
                    label = "%s/%s after %s" % (sort_key, sort_dir, anchor["id"])
                    if self._primary_value(anchor, sort_key) is None:
                        # A NULL primary is deliberately unencodable: no comparison
                        # predicate can express it. The page omits next_cursor and
                        # the client stays on offset pagination. Assert the
                        # rejection, do not skip it.
                        self.assertEqual(self._token(query, anchor), "", label)
                        continue
                    # Every other key, the empty group included, has to produce a
                    # token, otherwise the walk silently falls back to OFFSET.
                    self.assertTrue(self._token(query, anchor), label)
                    continuation = [
                        row for row in ordered[index + 1:]
                        # A NULL primary satisfies neither the range nor the
                        # equality branch, so it stays unreachable after a cursor.
                        if self._primary_value(row, sort_key) is not None
                    ]
                    expected = [row["id"] for row in continuation[:limit]]
                    self.assertEqual(self._sql_page(query, anchor, limit), expected, label)

    def test_an_inclusive_cursor_starts_at_its_own_anchor_row(self):
        # A page whose last served row carries an unrepresentable key anchors on
        # its look-ahead row instead, and that row has not been served yet, so the
        # continuation begins at the anchor rather than strictly after it.
        limit = 4
        for sort_key in SORT_KEYS:
            for sort_dir in ("asc", "desc"):
                query = parse_library_page_query({"sort": sort_key, "dir": sort_dir})
                ordered = self._ordered_rows(sort_key, sort_dir)
                for index, anchor in enumerate(ordered):
                    label = "%s/%s at index %d" % (sort_key, sort_dir, index)
                    token = self._token(query, anchor, inclusive=True)
                    if not token:
                        self.assertIsNone(self._primary_value(anchor, sort_key), label)
                        self.assertFalse(anchor_is_encodable(
                            self._primary_value(anchor, sort_key), anchor["title"], anchor["id"]), label)
                        continue
                    self.assertTrue(decode_track_cursor(token)["inclusive"], label)
                    expected = [
                        row["id"] for row in ordered[index:]
                        # A NULL primary stays unreachable either way: an inclusive
                        # cursor cannot express it any better than an exclusive one.
                        if self._primary_value(row, sort_key) is not None
                    ][:limit]
                    self.assertEqual(self._sql_page(query, anchor, limit, inclusive=True), expected, label)

    def test_the_exclusive_and_inclusive_walks_differ_by_exactly_one_row(self):
        # The flag is the only difference between the two cursors, so it must move
        # the boundary by that one anchor row and nothing else.
        query = parse_library_page_query({"sort": "artist", "dir": "asc"})
        anchor = next(row for row in ROWS if row["id"] == "t-09")
        exclusive = self._sql_page(query, anchor, 4)
        inclusive = self._sql_page(query, anchor, 4, inclusive=True)
        self.assertEqual(inclusive, ["t-09"] + exclusive)

    def test_the_inclusive_flag_is_opt_in_and_strictly_typed(self):
        token = encode_track_cursor("artist", "asc", "Adele", "Song 2", "track-2")
        for flag, accepted in ((0, True), (False, True), (1, True), (True, True),
                               (2, False), ("1", False), (1.0, False), (None, False), ([], False)):
            rebuilt = _rewrite_token(token, {"i": flag})
            decoded = decode_track_cursor(rebuilt)
            self.assertEqual(decoded is not None, accepted, repr(flag))
            if accepted:
                self.assertEqual(decoded["inclusive"], bool(flag), repr(flag))
        self.assertFalse(decode_track_cursor(token)["inclusive"])
        self.assertFalse(anchor_is_encodable(None, "Song 2", "track-2"))
        self.assertFalse(anchor_is_encodable("Adele", None, "track-2"))
        self.assertFalse(anchor_is_encodable("Adele", "Song 2", None))
        self.assertTrue(anchor_is_encodable("Adele", "Song 2", ""))

    def test_duplicate_primary_and_title_only_skip_the_visited_rows(self):
        # t-09, t-10 and t-11 share every ordering key, so a cursor on t-10 has
        # to resume at t-11 without repeating it or jumping past it.
        query = parse_library_page_query({"sort": "artist", "dir": "asc"})
        anchor = next(row for row in ROWS if row["id"] == "t-10")
        self.assertEqual(self._sql_page(query, anchor, 5), ["t-11", "t-12"])


if __name__ == "__main__":
    unittest.main()
