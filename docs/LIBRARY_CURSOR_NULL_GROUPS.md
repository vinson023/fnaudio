# Library cursor pagination and NULL label groups

TODO.md:73 ruling A closed the entry by writing down what the browse pager already
guarantees and what it deliberately does not.  This document is that wording.  The
code it describes is unchanged; what changed is that the behaviour now has a name, so
a later round can tell a design consequence from a defect.

## Why NULL is a pagination problem at all

A keyset cursor is a comparison.  `cursor_group_tail_where()` narrows to the rest of
the cursor's own key group with `artist = ? AND (title, id) > (?, ?)`, and
`cursor_next_group_where()` continues with the groups after it using a single strict
`artist > ?` (or `< ?` descending) - see `library_cursor_policy.py:150-190`.  SQL
three-valued logic answers *unknown* for `NULL = ?`, `NULL > ?` and `NULL < ?` alike,
so a row that stores SQL NULL in the sorted column matches neither predicate.  It is
not misordered; it is unaddressable.  A page that ends on such a row can report
`has_more` truthfully and still be unable to name the position to continue from.

SQLite still groups those rows: NULL sorts before every text value ascending and
after every text value descending, and that block is contiguous.  Only the *boundary*
of the block is expressible, and only in one direction.  Both facts below follow from
that asymmetry.

The label columns this can bite are enumerated once, in
`library_write.NULLABLE_LABEL_COLUMNS` (`library_write.py:29-38`): `title`, `artist`,
`album`, `album_artist`, `composer`, `genre`, `format`, `mime`.

## The four guaranteed behaviours

### 1. A NULL page anchors on its look-ahead row - but only where the block ends

A served row whose key cannot be encoded is not the end of the story: the row the
pager read ahead of it *may* be able to name the position.  `_continuation_anchor()`
(`library_page_result_policy.py:38-60`) swaps to that row and marks the cursor
`inclusive`, because the look-ahead row has not been served yet - the tail predicate
then starts *at* it (`>=`) instead of after it.  The marker is sparse in the payload
(`library_cursor_policy.py:84-87`) so every token issued before it existed keeps
encoding byte-identical.

The swap is only safe at the end of the NULL block.  If the look-ahead row is itself
NULL it cannot anchor either, and the page falls back to the old answer - `has_more`
with no `next_cursor`, and a client that finishes the walk on OFFSET.  Choosing the
honest dead end over a cursor that would silently skip the rest of the block is the
guarantee, and `test_cursor_walk_never_skips_the_rest_of_a_null_key_group` is what
pins it.

### 2. Descending: the trailing NULL block is not cursor-reachable, and no row is lost

Descending puts the NULL block at the end, so the page just before it hands out a
normal `< ?` continuation that can never reach those rows; the walk ends on a short
page reporting `has_more` false.  The rows are still there and still counted, so a
client that also reads the total notices the difference and can finish on an offset
request - which is the opposite of row loss, and the reason this residual is recorded
rather than fixed.  `test_a_descending_cursor_walk_stops_short_of_a_trailing_null_group`
pins the exact shape: the cursor walk returns `offset_ids[:-1]`.

### 3. A continuation never degrades into the old counted-OFFSET scan

Both pager helpers read the group tail and then the following groups as two single
comparisons, sharing one `limit + 1` budget (`library.py:1190-1257`).  SQLite only
turns a contiguous range into an index seek and cannot prove an OR over the same
prefix contiguous once every value arrives as its own anonymous parameter, so the
widened predicate is not merely slower, it is a different query shape.
`test_no_browse_continuation_falls_back_to_the_offset_scan_shape` traces real
statements and refuses three things: the retired `browse_cursor_where` symbol coming
back, `OFFSET` appearing in a continuation read, and the two single comparisons being
stitched back into an `OR`.

### 4. Reading one row more than a page shows is the design, not a defect

The offset path requests `limit + 1` rows too (`library.py:1412-1419`,
`decode_track_cursor_page_rows`).  It is how `has_more` is decided without a `COUNT`,
and it is what makes behaviour 1 possible on the offset path as well as the keyset
path.  A later round that sees an extra row read and calls it waste would be
removing the only mechanism that keeps a NULL-terminated offset page continuable.

## What the write path fixed, and what it did not

The NULL block is legacy.  `prepare_track_persistence()` collapses an explicit `None`
tag to `""` through `collapse_missing_labels()` (`library_write.py:41-53`), and it
does so on the same dict that is serialised into `item_json`, so a column and its
JSON copy can no longer disagree about whether a track carries a tag.  `""` is already
this project's "no value": an item that omits a key reaches the row as `""`, and
`group_match_condition()` folds `""` and NULL into `UNCLASSIFIED` together
(`library_group_policy.py:8-16`).  A sentinel key value was rejected as the fix
because the `COALESCE` expression needed to match it costs every ordinary
artist/album/genre page its index seek - the hard evidence is the docstring at
`library.py:1135-1143` (TODO.md recorded it as `:1127-1135`; the import restructuring
in this round shifted everything after `library.py:73` by 8 lines, and history
entries are left as written).

Two things the writer-side rule cannot do, and the migration that can:

- It only covers rows a scan rewrites.  A stored `item_json` that already spells the
  tag `""` makes the upsert's `WHERE tracks.item_json <> excluded.item_json` guard
  (`library.py:2619`) skip the row, so a legacy NULL column outlives every later
  scan.  `_collapse_null_labels()` (`library.py:2485-2524`) repairs exactly those
  rows, once, guarded by the `null_label_collapse` marker in `library_meta`, at
  `library.py:2661`.
- It is a migration, not a sweep.  A per-save sweep would quietly undo any future
  write path that reintroduced NULL - the regression the writer-side guard exists to
  make visible - and would turn a one-time cost into one paid per track per scan.
  With the marker stored, an injected NULL survives the next save.

**Division of labour, stated plainly.**  Re-indexing a library rescues its rows.  A
library that is never re-indexed keeps its NULLs until the migration marker is
absent and a save runs, so *read*-side behaviour 1 and 2 remain the live contract for
every existing install until then, and this document stays accurate either way.
`item_json` heals without help: once the scanner reports the same track without the
`None`, the two JSON spellings differ, the guard stops skipping the row, and columns
and payload are rewritten together.

## Verification

```powershell
Set-Location C:\path\to\fnAudio\src
python -B -m unittest tests.test_library_sqlite tests.test_library_write
```

The tests that pin this document, by name:

| Behaviour | Test |
| --- | --- |
| 1 (walk through a NULL group) | `test_cursor_walk_continues_through_a_null_key_group` |
| 1 (NULL title inside a tagged group) | `test_cursor_walk_continues_through_a_null_title_inside_a_group` |
| 1 (no cursor across a NULL run) | `test_cursor_walk_never_skips_the_rest_of_a_null_key_group` |
| 2 (descending trailing block) | `test_a_descending_cursor_walk_stops_short_of_a_trailing_null_group` |
| 3 (two reads, no COUNT of the group) | `test_cursor_page_reads_two_ranges_without_counting_the_group` |
| 3 (no OFFSET/OR fallback) | `test_no_browse_continuation_falls_back_to_the_offset_scan_shape` |
| migration (legacy row is repaired) | `test_a_legacy_index_loses_its_null_labels_on_the_next_save` |
| migration (marker means one time) | `test_the_null_label_collapse_is_a_one_time_migration_not_a_sweep` |
| write path (every `None` label collapses) | `test_prepare_track_persistence_collapses_every_none_label` |
| write path (absent keys stay absent) | `test_prepare_track_persistence_leaves_an_absent_label_key_absent` |
| write path (in-place on the prepared copy) | `test_collapse_missing_labels_prepares_a_copy_and_leaves_the_scan_item_alone` |

## Deployment boundary

`inclusive` is a new cursor field, and an *older* server would ignore it and resume
strictly after the anchor, dropping the look-ahead row.  fnAudio runs one server
process that issues and consumes its own tokens, and this project has never supported
a browser cache holding a cursor across a server upgrade, so the skew is out of scope
under the existing single-process premise.  If that premise ever goes away, the
marker for the cursor payload (`"v": 1`) is where a version rule would have to go.
