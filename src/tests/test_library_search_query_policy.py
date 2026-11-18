import sqlite3
import sys
import unittest

sys.path.insert(0, "app/server")
from library_search_policy import SEARCH_COLUMNS, track_search_condition
from library_search_query_policy import (
    MAX_CLAUSES,
    MAX_QUERY_CHARS,
    clauses_support_fts,
    describe_search_query,
    fts_expression,
    like_conditions,
    parse_search_query,
)


class SearchQueryParsingTests(unittest.TestCase):
    def test_bare_query_stays_one_global_phrase(self):
        # The box must keep meaning what it meant before field syntax existed:
        # one substring over nine columns. Splitting on spaces would turn
        # "Singer B" into "singer" AND "b" and start matching album titles that
        # happen to contain a "b" (regression caught by
        # test_library_sqlite's group-search case).
        self.assertEqual(parse_search_query("pink floyd"), [
            {"field": "", "term": "pink floyd"},
        ])
        self.assertEqual(describe_search_query("  Singer B  "), [{"field": "*", "term": "Singer B"}])

    def test_known_field_is_scoped(self):
        self.assertEqual(parse_search_query("artist:pink"), [{"field": "artist", "term": "pink"}])

    def test_quoted_term_keeps_spaces(self):
        self.assertEqual(
            parse_search_query('artist:"pink floyd"'),
            [{"field": "artist", "term": "pink floyd"}],
        )

    def test_unknown_prefix_and_url_stay_text(self):
        # "http://x" must not lose its "http" and "//x" must not become a field.
        self.assertEqual(
            describe_search_query("http://example"),
            [{"field": "*", "term": "http://example"}],
        )
        self.assertEqual(describe_search_query("live:1975"), [{"field": "*", "term": "live:1975"}])

    def test_empty_field_value_is_ignored(self):
        self.assertEqual(parse_search_query("artist:"), [])

    def test_duplicates_collapse(self):
        self.assertEqual(len(parse_search_query("rock Rock")), 1)

    def test_clause_count_and_length_are_bounded(self):
        query = " ".join("title:t%d" % index for index in range(MAX_CLAUSES + 5))
        self.assertEqual(len(parse_search_query(query)), MAX_CLAUSES)
        parsed = parse_search_query("x" * (MAX_QUERY_CHARS * 2))
        self.assertEqual(len(parsed), 1)
        self.assertEqual(len(parsed[0]["term"]), MAX_QUERY_CHARS)

    def test_non_text_input_is_empty(self):
        self.assertEqual(parse_search_query(None), [])
        self.assertEqual(parse_search_query(object()), [])
        self.assertEqual(parse_search_query(""), [])

    def test_sql_metacharacters_stay_inside_parameters(self):
        condition, args = track_search_condition('artist:"x; DROP TABLE tracks"')
        self.assertNotIn("DROP", condition)
        self.assertIn("drop table tracks", args[0].lower())


class SearchExpressionTests(unittest.TestCase):
    def test_fts_expression_uses_column_filters_and_escapes_quotes(self):
        expression = fts_expression([
            {"field": "artist", "term": 'a"b'},
            {"field": "title", "term": "song"},
        ])
        self.assertEqual(expression, 'artist : "a""b" title : "song"')

    def test_short_clause_disqualifies_fts(self):
        self.assertFalse(clauses_support_fts(parse_search_query("artist:ab")))
        self.assertTrue(clauses_support_fts(parse_search_query("artist:abc")))
        self.assertFalse(clauses_support_fts([]))

    def test_like_fallback_ands_clauses(self):
        condition, args = like_conditions(parse_search_query("artist:pink album:wall"), SEARCH_COLUMNS)
        self.assertIn(" AND ", condition)
        self.assertEqual(args, ["%pink%", "%wall%"])
        self.assertNotIn(" OR ", condition)

    def test_like_global_clause_expands_to_every_column(self):
        condition, args = like_conditions(parse_search_query("floyd"), SEARCH_COLUMNS)
        self.assertEqual(len(args), len(SEARCH_COLUMNS))
        self.assertIn(" OR ", condition)

    def test_alias_is_applied_to_scoped_columns(self):
        condition, _ = like_conditions(parse_search_query("genre:rock"), SEARCH_COLUMNS, "t.")
        self.assertIn("t.genre", condition)


class SearchConditionIntegrationTests(unittest.TestCase):
    """The FTS expression must be accepted by the real trigram tokenizer."""

    def _database(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE tracks (id TEXT, title TEXT, artist TEXT, album TEXT)")
        conn.execute(
            "CREATE VIRTUAL TABLE tracks_search USING fts5("
            "title,artist,album, content='tracks', content_rowid='rowid', tokenize='trigram')"
        )
        rows = [
            ("1", "Another Brick", "Pink Floyd", "The Wall"),
            ("2", "Wish You Were Here", "Pink Floyd", "Wish You Were Here"),
            ("3", "Pink", "Aerosmith", "Nine Lives"),
        ]
        conn.executemany("INSERT INTO tracks(id,title,artist,album) VALUES (?,?,?,?)", rows)
        conn.execute("INSERT INTO tracks_search(tracks_search) VALUES ('rebuild')")
        return conn

    def test_column_filter_only_matches_that_column(self):
        conn = self._database()
        condition, args = track_search_condition('artist:"pink floyd"', use_fts=True)
        rows = conn.execute("SELECT id FROM tracks WHERE " + condition, args).fetchall()
        self.assertEqual(sorted(row[0] for row in rows), ["1", "2"])

    def test_global_term_still_matches_any_column(self):
        conn = self._database()
        condition, args = track_search_condition("pink", use_fts=True)
        rows = conn.execute("SELECT id FROM tracks WHERE " + condition, args).fetchall()
        self.assertEqual(sorted(row[0] for row in rows), ["1", "2", "3"])

    def test_two_scoped_clauses_are_anded(self):
        conn = self._database()
        condition, args = track_search_condition("artist:pink album:wall", use_fts=True)
        rows = conn.execute("SELECT id FROM tracks WHERE " + condition, args).fetchall()
        self.assertEqual([row[0] for row in rows], ["1"])

    def test_like_path_handles_the_same_query(self):
        conn = self._database()
        condition, args = track_search_condition("artist:pink album:wall")
        rows = conn.execute("SELECT id FROM tracks WHERE " + condition, args).fetchall()
        self.assertEqual([row[0] for row in rows], ["1"])


if __name__ == "__main__":
    unittest.main()
