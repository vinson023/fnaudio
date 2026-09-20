import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "server"))

from library_write import normalize_scan_items, root_index_summary


class LibraryWriteTests(unittest.TestCase):
    def test_scan_text_rejects_non_text_and_bounds_values_without_coercion(self):
        from library_write import MAX_SCAN_TEXT, scan_text

        class Exploding:
            def __str__(self):
                raise AssertionError("scan persistence must not stringify arbitrary values")

        self.assertEqual(scan_text(Exploding()), "")
        self.assertEqual(scan_text("x" * (MAX_SCAN_TEXT + 5)), "x" * MAX_SCAN_TEXT)

    def test_normalize_scan_items_bounds_root_iterator(self):
        from library_write import MAX_ROOT_CANDIDATES

        class RootStream:
            def __init__(self):
                self.reads = 0

            def __iter__(self):
                return self

            def __next__(self):
                self.reads += 1
                if self.reads > MAX_ROOT_CANDIDATES:
                    raise AssertionError("root iterator was read past the configured bound")
                return "/music-%d" % self.reads

        roots = RootStream()
        result = normalize_scan_items(
            [{"id": "one", "path": "/outside/song.flac"}], roots,
            is_under=lambda *_: False,
            relative_folder=lambda *_: "",
            root_label=lambda root: root,
        )
        self.assertEqual(roots.reads, MAX_ROOT_CANDIDATES)
        self.assertEqual(result[0]["_index_root"], "")

    def test_persistence_batches_preserve_order_without_materializing_all_rows(self):
        from library_write import iter_track_persistence_batches

        seen = []

        def prepare(value):
            seen.append(value)
            return "row-%s" % value

        batches = list(iter_track_persistence_batches((value for value in range(5)), 2, prepare=prepare))
        self.assertEqual(batches, [["row-0", "row-1"], ["row-2", "row-3"], ["row-4"]])
        self.assertEqual(seen, [0, 1, 2, 3, 4])

    def test_persistence_batches_reject_invalid_adapters(self):
        from library_write import iter_track_persistence_batches

        self.assertEqual(list(iter_track_persistence_batches([1], True, prepare=lambda value: value)), [])
        self.assertEqual(list(iter_track_persistence_batches([1], 2, prepare=None)), [])

    def test_persistence_batches_skip_one_bad_record_and_continue(self):
        from library_write import iter_track_persistence_batches

        def prepare(value):
            if value == "bad":
                raise RuntimeError("broken")
            return value.upper()

        batches = list(iter_track_persistence_batches(["a", "bad", "b"], 2, prepare=prepare))
        self.assertEqual(batches, [["A", "B"]])

    def test_persistence_batches_isolate_broken_input_container(self):
        from library_write import iter_track_persistence_batches

        class Broken:
            def __bool__(self):
                raise RuntimeError("broken")

        self.assertEqual(list(iter_track_persistence_batches(Broken(), 2, prepare=lambda value: value)), [])

    def test_normalize_scan_items_isolated_and_deterministic(self):
        original = [{"id": "1", "path": "/music/a/song.flac", "cue_path": ""}, {"id": "2", "path": "/other/x.mp3", "folder": "legacy"}]
        snapshot = copy.deepcopy(original)
        result = normalize_scan_items(
            original,
            ["/music"],
            is_under=lambda path, root: path.startswith(root + "/"),
            relative_folder=lambda path, root: path[len(root) + 1 :].rsplit("/", 1)[0],
            root_label=lambda root: "Music",
        )
        self.assertEqual(original, snapshot)
        self.assertEqual(result[0]["folder"], "a")
        self.assertEqual(result[0]["library_root"], "Music")
        self.assertEqual(result[0]["_index_root"], "/music")
        self.assertEqual(result[1]["folder"], "legacy")
        self.assertEqual(result[1]["library_root"], "")

    def test_normalize_scan_items_rejects_non_text_and_oversized_paths(self):
        result = normalize_scan_items(
            [{"id": "bad", "path": object()}, {"id": "long", "path": "/music/" + ("x" * 4096)}],
            ["/music"],
            is_under=lambda path, root: True,
            relative_folder=lambda path, root: "unexpected",
            root_label=lambda root: "Music",
        )
        self.assertEqual([item["_index_root"] for item in result], ["", ""])
        self.assertEqual([item["folder"] for item in result], ["", ""])

    def test_normalize_scan_items_isolates_broken_items_and_iterators(self):
        class Broken:
            def __iter__(self):
                raise RuntimeError("broken")

        class BadMapping:
            def keys(self):
                raise RuntimeError("broken")

        self.assertEqual(normalize_scan_items(Broken(), [], is_under=lambda *_: False,
                                              relative_folder=lambda *_: "", root_label=lambda *_: ""), [])
        self.assertEqual(normalize_scan_items([BadMapping(), {"id": "ok"}], [],
                                              is_under=lambda *_: False,
                                              relative_folder=lambda *_: "", root_label=lambda *_: ""),
                         [{"id": "ok", "folder": "", "library_root": "", "_index_root": ""}])

    def test_normalize_scan_items_isolates_root_callback_failures(self):
        result = normalize_scan_items(
            [{"id": "one", "path": "/music/song.flac"}], ["/music"],
            is_under=lambda *_: (_ for _ in ()).throw(RuntimeError("broken")),
            relative_folder=lambda *_: (_ for _ in ()).throw(RuntimeError("broken")),
            root_label=lambda *_: (_ for _ in ()).throw(RuntimeError("broken")),
        )
        self.assertEqual(result[0]["_index_root"], "")
        self.assertEqual(result[0]["folder"], "")

    def test_prepare_track_persistence_keeps_private_root_out_of_json(self):
        from library_write import prepare_track_persistence
        item = {"id": "7", "path": "/music/a.flac", "_index_root": "/music", "cue_track": True, "track_no": "2"}
        row, cue, path, public = prepare_track_persistence(
            item, safe_int=lambda value: int(value or 0), safe_float=lambda value: float(value or 0), dumps=lambda value: str(value),
        )
        self.assertEqual(item["_index_root"], "/music")
        self.assertEqual(path, "/music/a.flac")
        self.assertNotIn("_index_root", public)
        self.assertEqual(row[2], "/music")
        self.assertEqual(cue[:4], ("7", "", "/music/a.flac", 2))

    # Positions of the label columns inside the track_row tuple that
    # prepare_track_persistence returns, matching the INSERT column list in
    # library.save_items_to_sqlite.
    TRACK_LABEL_SLOTS = {
        "title": 4, "artist": 5, "album": 6, "album_artist": 8,
        "composer": 9, "genre": 10, "format": 11, "mime": 12,
    }

    def test_prepare_track_persistence_collapses_every_none_label(self):
        # SQL NULL in a label column is unreachable to every keyset predicate, so the
        # writer is the boundary that has to refuse it (TODO.md:153 ruling C).  A None
        # from a tag reader must land as "" in the column *and* in the item_json that
        # is dumped from the same dict, or the two disagree about one track.
        from library_write import NULLABLE_LABEL_COLUMNS, prepare_track_persistence
        item = {"id": "nulls", "path": "/music/silent.flac"}
        item.update({column: None for column in NULLABLE_LABEL_COLUMNS})
        row, _cue, _path, public = prepare_track_persistence(
            item, safe_int=lambda value: 0, safe_float=lambda value: 0.0,
            dumps=lambda value: json.dumps(value, ensure_ascii=False),
        )
        self.assertEqual(len(self.TRACK_LABEL_SLOTS), len(NULLABLE_LABEL_COLUMNS))
        for column, slot in self.TRACK_LABEL_SLOTS.items():
            self.assertEqual(row[slot], "", "column %s must not be written as NULL" % column)
            self.assertEqual(public[column], "", "item_json must agree with the %s column" % column)
        # The whole row, not just the eight labels: no slot may carry the value SQLite
        # would store as NULL, and the payload the same call dumps must agree.
        self.assertNotIn(None, row)
        self.assertEqual(json.loads(row[-1]), public)
        self.assertNotIn(None, json.loads(row[-1]).values())

    def test_prepare_track_persistence_leaves_an_absent_label_key_absent(self):
        # Absent and None are the same *value* but not the same *payload*: adding the
        # key here would change item_json for every track in an existing index and
        # force a full rewrite for no behavioural difference.
        from library_write import NULLABLE_LABEL_COLUMNS, prepare_track_persistence
        row, _cue, _path, public = prepare_track_persistence(
            {"id": "sparse", "path": "/music/a.flac", "title": "Kept"},
            safe_int=lambda value: 0, safe_float=lambda value: 0.0, dumps=lambda value: "{}",
        )
        self.assertEqual(row[self.TRACK_LABEL_SLOTS["title"]], "Kept")
        self.assertEqual(row[self.TRACK_LABEL_SLOTS["artist"]], "")
        for column in NULLABLE_LABEL_COLUMNS:
            if column != "title":
                self.assertNotIn(column, public)

    def test_collapse_missing_labels_prepares_a_copy_and_leaves_the_scan_item_alone(self):
        # The helper collapses in place, which is what lets the row and its JSON come
        # from one source; prepare_track_persistence therefore has to hand it a copy, or
        # the scanner would see its own items rewritten under it.
        from library_write import collapse_missing_labels, prepare_track_persistence
        direct = {"id": "keep", "artist": None, "title": "Real"}
        self.assertIs(collapse_missing_labels(direct), direct, "the helper is in-place by contract")
        self.assertEqual(direct["artist"], "")
        scanned = {"id": "keep", "artist": None, "title": "Real"}
        row, _cue, _path, public = prepare_track_persistence(
            scanned, safe_int=lambda value: 0, safe_float=lambda value: 0.0, dumps=lambda value: "{}",
        )
        self.assertEqual(row[self.TRACK_LABEL_SLOTS["artist"]], "")
        self.assertEqual(public["artist"], "")
        self.assertIsNone(scanned["artist"], "preparation must not touch the caller's dict")

    def test_prepare_track_persistence_bounds_path_without_stringification(self):
        from library_write import prepare_track_persistence
        row, cue, path, public = prepare_track_persistence(
            {"id": "long", "path": object(), "_index_root": "/music"},
            safe_int=lambda value: 0,
            safe_float=lambda value: 0.0,
            dumps=lambda value: "{}",
        )
        self.assertEqual(path, "")
        self.assertEqual(row[1], "")

    def test_prepare_track_persistence_bounds_private_index_root(self):
        from library_write import prepare_track_persistence
        row, cue, path, public = prepare_track_persistence(
            {"id": "root", "path": "/music/song.flac", "_index_root": object()},
            safe_int=lambda value: 0,
            safe_float=lambda value: 0.0,
            dumps=lambda value: "{}",
        )
        self.assertEqual(row[2], "")

    def test_prepare_track_persistence_rejects_non_text_folder(self):
        from library_write import prepare_track_persistence
        row, cue, path, public = prepare_track_persistence(
            {"id": "folder", "path": "/music/song.flac", "folder": object()},
            safe_int=lambda value: 0,
            safe_float=lambda value: 0.0,
            dumps=lambda value: "{}",
        )
        self.assertEqual(row[3], "")

    def test_root_index_summary_keeps_configured_empty_roots_and_lowest_cover_id(self):
        summary = root_index_summary(
            [
                {"_index_root": "/music-a", "id": "z"},
                {"_index_root": "/music-a", "id": "a"},
                {"_index_root": "/outside", "id": "ignored"},
            ],
            ["/music-a", "/music-b"],
        )
        self.assertEqual(summary["/music-a"], {"track_count": 2, "cover_track_id": "a"})
        self.assertEqual(summary["/music-b"], {"track_count": 0, "cover_track_id": ""})

    def test_root_index_summary_isolates_broken_containers(self):
        class Broken:
            def __bool__(self):
                raise RuntimeError("broken")

        self.assertEqual(root_index_summary(Broken(), Broken()), {})

    def test_root_index_summary_bounds_root_iterator(self):
        from library_write import MAX_ROOT_CANDIDATES

        class RootStream:
            def __init__(self):
                self.reads = 0

            def __iter__(self):
                return self

            def __next__(self):
                self.reads += 1
                if self.reads > MAX_ROOT_CANDIDATES:
                    raise AssertionError("summary read past root bound")
                return "/root-%d" % self.reads

        roots = RootStream()
        summary = root_index_summary([], roots)
        self.assertEqual(roots.reads, MAX_ROOT_CANDIDATES)
        self.assertEqual(len(summary), MAX_ROOT_CANDIDATES)
    def test_prepare_track_persistence_writes_no_artwork_field_for_scanned_rows(self):
        # The scanned row is the only writer of `item_json` in production, and
        # it never carries an artwork reference; that producer-side fact, not a
        # carrier limitation, is why the projection has a separate donor.
        from library_write import prepare_track_persistence

        scanned = {
            "id": "t1", "path": "/music/a.flac", "title": "A", "artist": "B", "album": "C",
            "duration": 1.0, "size": 10, "_index_root": "/music",
            "metadata_source": {"title": "tag", "artist": "tag", "album": "tag"},
        }
        row, cue, path, public = prepare_track_persistence(
            scanned, safe_int=lambda value: int(value or 0),
            safe_float=lambda value: float(value or 0), dumps=json.dumps,
        )
        self.assertEqual(path, "/music/a.flac")
        self.assertIsNone(cue)
        payload = json.loads(row[-1])
        self.assertNotIn("_index_root", payload)
        self.assertEqual(
            [key for key in payload if "artwork" in key or key.startswith("cover_")], [],
        )

    def test_prepare_track_persistence_has_no_key_whitelist_so_a_copy_would_persist(self):
        # Mechanically the copy would land, which is exactly why the R107
        # decision had to rest on enrichment-lane behaviour instead of
        # "item_json cannot hold the field anyway".
        from library_write import prepare_track_persistence

        row, cue, path, public = prepare_track_persistence(
            {"id": "t2", "path": "/music/b.flac", "metadata_artwork_id": "a" * 64},
            safe_int=lambda value: 0, safe_float=lambda value: 0.0, dumps=json.dumps,
        )
        payload = json.loads(row[-1])
        self.assertIn(
            "metadata_artwork_id", payload,
            "the carrier must have no key filter, otherwise a copy could never persist",
        )
        self.assertEqual(payload["metadata_artwork_id"], "a" * 64)


if __name__ == "__main__":
    unittest.main()
