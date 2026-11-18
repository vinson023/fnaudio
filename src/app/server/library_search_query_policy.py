"""Field-scoped library search syntax.

The search box used to be one substring matched against nine columns at once.
That is fine for "floyd" and useless for "artist:pink floyd" when the album is
also called "Pink Floyd". This module parses an *additive* syntax:

    artist:pink            -> the artist column only
    artist:"pink floyd"    -> quoted term, spaces preserved
    live floyd             -> unchanged: one global substring
    http://example         -> unchanged: not a known field, stays a global term

Everything here is pure: no SQL is executed and no state is read. The SQL is
built by ``library_search_policy`` from the clauses this module returns, so a
malformed query can never reach SQLite as raw text.

Only the nine columns the index actually searches are addressable. A colon in
front of anything else is treated as ordinary text, because users search for
``AC/DC: Live`` and ``http://`` far more often than they type a typo'd field.
"""

from __future__ import annotations

SEARCH_FIELDS = (
    "title",
    "artist",
    "album",
    "album_artist",
    "composer",
    "genre",
    "folder",
    "path",
    "format",
)
MAX_QUERY_CHARS = 4096
MAX_CLAUSES = 8
# A single token may be as long as the whole box: a bare query must keep the
# historical 4096-character bound, and per-clause bounding adds no safety beyond
# the total bound that is already enforced before tokenizing.
MAX_TERM_CHARS = MAX_QUERY_CHARS
# FTS5's trigram tokenizer cannot answer a term shorter than three characters;
# a query with any short term falls back to LIKE for the whole query rather than
# silently dropping that clause.
FTS_MIN_TERM_CHARS = 3

_FIELD_SET = frozenset(SEARCH_FIELDS)


def _bounded(value, limit):
    text = value if isinstance(value, str) else ""
    return text[:limit]


def _split_tokens(text):
    """Split on whitespace that is outside double quotes.

    Quotes are kept in the token so the caller can tell ``artist:"a b"`` from a
    bare ``"a`` + ``b"``; an unterminated quote simply runs to the end, which is
    what a user typing mid-phrase expects.
    """
    tokens = []
    current = []
    quoted = False
    for char in text:
        if char == '"':
            quoted = not quoted
            current.append(char)
            continue
        if char.isspace() and not quoted:
            if current:
                tokens.append("".join(current))
                current = []
            continue
        current.append(char)
    if current:
        tokens.append("".join(current))
    return tokens


def _unquote(term):
    """Strip only a fully quoted term; inner quotes are literal text.

    ``a"b`` stays ``a"b`` (the FTS path escapes it to ``"a""b"``), while
    ``"pink floyd"`` loses its delimiters. Stripping inner quotes here would
    silently rewrite what the user asked for.
    """
    text = term.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1].replace('""', '"').strip()
    return text


def _clause(token):
    """Turn one token into ``{"field", "term"}`` or ``None`` when empty."""
    raw = _bounded(token, MAX_TERM_CHARS + 64).strip()
    if not raw:
        return None
    head, sep, tail = raw.partition(":")
    field = head.strip().lower()
    if sep and field in _FIELD_SET:
        # "artist:" is an abandoned field prefix, not a search for the literal
        # text "artist:" — dropping it is what a user expects while typing.
        if not tail.strip():
            return None
        term = _unquote(_bounded(tail, MAX_TERM_CHARS))
        return {"field": field, "term": term} if term else None
    term = _unquote(raw)
    return {"field": "", "term": term} if term else None


def _field_prefix(token):
    """Return the field a token addresses, or "" when it addresses none.

    An abandoned prefix (``artist:`` with nothing after it) still counts as a
    prefix: the query is then parsed token by token and that clause is dropped,
    rather than falling back to searching for the literal text "artist:".
    """
    head, sep, _tail = token.partition(":")
    if not sep:
        return ""
    field = head.strip().lower()
    return field if field in _FIELD_SET else ""


def parse_search_query(text):
    """Parse the search box into ordered clauses (field "" means global)."""
    if not isinstance(text, str):
        return []
    bounded = text[:MAX_QUERY_CHARS].strip()
    if not bounded:
        return []
    tokens = _split_tokens(bounded)
    if not any(_field_prefix(token) for token in tokens):
        # No field prefix anywhere, so this is the plain search box it always
        # was: one global substring over the whole text. Splitting it into words
        # here would silently change what the box means — "Singer B" would become
        # "singer" AND "b" and start matching albums whose titles contain a "b".
        term = _unquote(bounded)
        return [{"field": "", "term": term}] if term else []
    clauses = []
    seen = set()
    for token in tokens:
        clause = _clause(token)
        if clause is None:
            continue
        key = (clause["field"], clause["term"].lower())
        if key in seen:
            continue
        seen.add(key)
        clauses.append(clause)
        if len(clauses) >= MAX_CLAUSES:
            break
    return clauses


def clauses_support_fts(clauses):
    """True when every clause is long enough for the trigram index."""
    if not isinstance(clauses, list) or not clauses:
        return False
    return all(
        isinstance(clause, dict)
        and isinstance(clause.get("term"), str)
        and len(clause["term"].strip()) >= FTS_MIN_TERM_CHARS
        for clause in clauses
    )


def fts_expression(clauses):
    """Build an FTS5 MATCH expression, or "" when there is nothing to match.

    Column filters use FTS5's own ``column : term`` form; every clause is
    implicitly ANDed, which is what the LIKE path does with its ``AND`` join.
    """
    if not isinstance(clauses, list):
        return ""
    parts = []
    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        term = clause.get("term")
        if not isinstance(term, str) or not term:
            continue
        escaped = term.replace('"', '""')
        field = clause.get("field") if isinstance(clause.get("field"), str) else ""
        if field in _FIELD_SET:
            parts.append('%s : "%s"' % (field, escaped))
        else:
            parts.append('"%s"' % escaped)
    return " ".join(parts)


def like_conditions(clauses, columns, prefix=""):
    """Build one ``(sql, args)`` pair for the LIKE fallback.

    ``columns`` is the global column list, so this module stays independent of
    the index's column order.
    """
    safe_prefix = prefix if isinstance(prefix, str) else ""
    safe_columns = tuple(column for column in (columns or ()) if isinstance(column, str) and column)
    if not safe_columns or not isinstance(clauses, list):
        return "", []
    conditions = []
    args = []
    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        term = clause.get("term")
        if not isinstance(term, str) or not term:
            continue
        needle = "%" + term.lower() + "%"
        field = clause.get("field")
        if isinstance(field, str) and field in _FIELD_SET:
            conditions.append("lower(COALESCE(%s%s, '')) LIKE ?" % (safe_prefix, field))
            args.append(needle)
            continue
        conditions.append(
            "(" + " OR ".join(
                "lower(COALESCE(%s%s, '')) LIKE ?" % (safe_prefix, column) for column in safe_columns
            ) + ")"
        )
        args.extend([needle] * len(safe_columns))
    if not conditions:
        return "", []
    return " AND ".join(conditions), args


def describe_search_query(text):
    """Short human-readable projection used by tests and diagnostics."""
    clauses = parse_search_query(text)
    return [{"field": clause["field"] or "*", "term": clause["term"]} for clause in clauses]


__all__ = [
    "FTS_MIN_TERM_CHARS",
    "MAX_CLAUSES",
    "MAX_QUERY_CHARS",
    "MAX_TERM_CHARS",
    "SEARCH_FIELDS",
    "clauses_support_fts",
    "describe_search_query",
    "fts_expression",
    "like_conditions",
    "parse_search_query",
]
