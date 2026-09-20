import inspect
import os
import random
import sys
import unittest

sys.path.insert(0, "app/server")

import cue_parser
from cue_numeric_policy import cue_segment_end, finite_number, track_number
from cue_parser import parse_cue_structure


class CueParserTests(unittest.TestCase):
    def test_invalid_numeric_values_do_not_trigger_object_coercion(self):
        self.assertEqual(finite_number(object()), 0.0)
        self.assertEqual(finite_number(True), 0.0)
        self.assertEqual(finite_number("nan"), 0.0)
        self.assertEqual(track_number("123456789" , 4), 4)
        self.assertEqual(track_number("12", 4), 12)

    def test_parses_album_tracks_and_offsets_per_source_file(self):
        data = parse_cue_structure([
            'PERFORMER "Album Artist"', 'TITLE "Album"', 'FILE "disc.flac" WAVE',
            '  TRACK 01 AUDIO', '    TITLE "First"', '    INDEX 01 00:00:00',
            '  TRACK 02 AUDIO', '    PERFORMER "Guest"', '    TITLE "Second"', '    INDEX 01 04:12:00',
            'FILE "bonus.flac" WAVE', '  TRACK 03 AUDIO', '    TITLE "Third"', '    INDEX 01 00:10:00',
        ], "fallback")
        self.assertEqual(data["album"], "Album")
        self.assertEqual(data["album_artist"], "Album Artist")
        self.assertEqual(data["tracks"], [
            {"track_no": 1, "file": "disc.flac", "title": "First", "artist": "", "start": 0.0, "end": 252.0},
            {"track_no": 2, "file": "disc.flac", "title": "Second", "artist": "Guest", "start": 252.0, "end": 0.0},
            {"track_no": 3, "file": "bonus.flac", "title": "Third", "artist": "", "start": 10.0, "end": 0.0},
        ])

    def test_uses_fallbacks_and_ignores_non_text_lines(self):
        data = parse_cue_structure([b"TRACK 99 AUDIO", "TRACK AUDIO", "INDEX 01 invalid"], "fallback")
        self.assertEqual(data["album"], "fallback")
        self.assertEqual(data["album_artist"], "未知艺术家")
        self.assertEqual(data["tracks"], [{"track_no": 1, "file": "", "title": "", "artist": "", "start": 0.0, "end": 0.0}])

    def test_ignores_oversized_lines_before_parsing(self):
        data = parse_cue_structure(["TITLE " + "x" * 10000, "TRACK 01 AUDIO"], "fallback")
        self.assertEqual(data["album"], "fallback")
        self.assertEqual(len(data["tracks"]), 1)

    def test_stops_after_bounded_line_count(self):
        lines = ["TRACK 01 AUDIO"] + ["REM filler"] * 25000
        data = parse_cue_structure(lines, "fallback")
        self.assertEqual(len(data["tracks"]), 1)

    def _reference_ends(self, tracks):
        """The original nested definition, kept here as the expected answer.

        The nested scan reaches its closing 0.0 two different ways, and the two
        have to be told apart now that the parser does: a track with nothing after
        it on the file, which really does end where the file ends, and a track all
        of whose later entries fail to start further in, which states no boundary
        at all and is None.
        """
        ends = []
        for index, track in enumerate(tracks):
            start = finite_number(track.get("start"))
            if not isinstance(track.get("file"), str):
                # The parser refuses to group such a track with anything.
                ends.append(None)
                continue
            boundary = None
            followed = False
            for candidate in tracks[index + 1:]:
                if candidate.get("file") != track.get("file"):
                    continue
                followed = True
                candidate_start = finite_number(candidate.get("start"))
                if boundary is None and candidate_start > start:
                    boundary = candidate_start
            ends.append(boundary if boundary is not None else (None if followed else 0.0))
        return ends

    def test_track_end_matches_the_nearest_later_start_on_the_same_file(self):
        # The linear stack must answer exactly what the nested scan answered: the
        # nearest later track on the same file that starts further in. Repeated
        # FILE names and out-of-order offsets are what make that non-trivial.
        rng = random.Random(20260917)
        states = set()
        for _ in range(60):
            files = ["disc%d.flac" % number for number in range(rng.randint(1, 3))]
            lines = []
            for track_no in range(1, rng.randint(6, 24)):
                lines.append('FILE "%s" FLAC' % rng.choice(files))
                lines.append("  TRACK %02d AUDIO" % track_no)
                for index_no in rng.choice(([1], [0, 1], [1, 3], [2], [], [1, 1])):
                    minutes = rng.choice([0, 1, 2, 1, 3, 0])
                    lines.append("    INDEX %02d %02d:00:00" % (index_no, minutes))
            tracks = parse_cue_structure(lines, "album")["tracks"]
            ends = [track["end"] for track in tracks]
            self.assertEqual(ends, self._reference_ends(tracks))
            for end in ends:
                states.add("unknown" if end is None else
                           ("final-track" if end == 0.0 else "known-boundary"))
        # The reference only separates three answers if the generated sheets contain
        # all three, so a mutation that quietly folds one state back into another has
        # to fail here instead of agreeing on whichever shape the run happened to make.
        self.assertEqual(states, {"known-boundary", "final-track", "unknown"})

    def test_a_track_whose_file_is_not_a_string_degrades_instead_of_raising(self):
        # Finding a track's end means looking tracks up by their file, so that value is used
        # as a dictionary key - which quietly assumes it is a string.  `cue_value()` cleans
        # every field it returns, so a parsed sheet always arrives hashable; the guard is for
        # a track assembled by another path, where an unusable value has to degrade into an
        # ungrouped track instead of raising TypeError out of a parser whose job is to
        # survive unusable sheets.
        tracks = [
            {"file": "a.flac", "start": 0.0},
            {"file": ["a.flac"], "start": 10.0},
            {"file": None, "start": 20.0},
            {"file": "a.flac", "start": 30.0},
            {"file": {"index": 1}, "start": 40.0},
            {"file": "a.flac", "start": 50.0},
        ]
        cue_parser._attach_track_ends(tracks)
        self.assertEqual([track["end"] for track in tracks],
                         [30.0, None, None, 50.0, None, 0.0],
                         "the usable group must be laid out exactly as if the others were alone")
        # An ungrouped track cannot claim to be the final track of its file either, so
        # it reports the state that means "the sheet never said" rather than the 0.0
        # that means "nothing follows me".
        # A hashable non-string is not rescued either: "7" and 7 must not share a stack.
        mixed = [{"file": 7, "start": 0.0}, {"file": "7", "start": 5.0}]
        cue_parser._attach_track_ends(mixed)
        self.assertEqual([track["end"] for track in mixed], [None, 0.0])

    def test_the_three_end_states_survive_one_ordinary_sheet(self):
        # The point of the third state: two tracks on the same file can both be
        # answered 0.0 by the old rule while meaning opposite things. Walking one
        # sheet through the production parser keeps the known boundary, the unknown
        # boundary and the genuine end of the file apart.
        tracks = parse_cue_structure([
            'FILE "disc.flac" FLAC',
            '  TRACK 01 AUDIO', '    INDEX 01 00:00:00',
            '  TRACK 02 AUDIO', '    INDEX 01 04:00:00',
            '  TRACK 03 AUDIO', '    INDEX 01 02:00:00',
        ], "album")["tracks"]
        self.assertEqual([track["start"] for track in tracks], [0.0, 240.0, 120.0])
        # TRACK 01 stops where TRACK 02 starts; TRACK 02 is followed only by a track
        # that starts earlier, so nothing states its end; TRACK 03 is the last entry
        # the sheet makes for this file, so it stops where the file does.
        self.assertEqual([track["end"] for track in tracks], [240.0, None, 0.0])

    def test_only_a_final_track_may_borrow_the_file_duration(self):
        # The stored cue_end has to keep the distinction the parser just made, so the
        # boundary reaches it through cue_segment_end: a positive value is the next
        # track, 0.0 is the end of the file, and None is no boundary at all.
        self.assertEqual(cue_segment_end(252.0, 300.0), 252.0)
        self.assertEqual(cue_segment_end(252.0, 0.0), 252.0)
        self.assertEqual(cue_segment_end(0.0, 300.0), 300.0)
        self.assertEqual(cue_segment_end(None, 300.0), 0.0)

    def test_cue_segment_end_refuses_to_invent_a_length(self):
        # Everything that is not a usable boundary degrades to the same 0.0 the
        # cue_end column uses for "no known end", and never to the file duration,
        # which would turn a broken sheet into a claimed full-file segment.
        for value in (None, True, False, float("nan"), float("inf"), float("-inf"),
                      -5.0, object(), "nan", ""):
            with self.subTest(value=value):
                self.assertEqual(cue_segment_end(value, 300.0), 0.0)
        # A final track whose duration is unusable still answers "no known end".
        for duration in (None, True, "unknown", float("nan"), object()):
            with self.subTest(duration=duration):
                self.assertEqual(cue_segment_end(0.0, duration), 0.0)
        # Numeric text from either side is still usable, and a boundary of its own
        # is never replaced by the duration.
        self.assertEqual(cue_segment_end("30.5", 300.0), 30.5)
        self.assertEqual(cue_segment_end(0.0, "300.5"), 300.5)

    def _count_end_stage(self, lines):
        """Parse a sheet and report how much work its track-end stage did.

        The counter is the production parser\u2019s own measurement seam, so it
        counts candidate starts examined rather than calls to some numeric helper.
        """
        counts = [0]

        def observe():
            counts[0] += 1

        tracks = parse_cue_structure(lines, "album", observe_end_stage=observe)["tracks"]
        return tracks, counts[0]

    def test_end_stage_count_is_exact_for_a_three_track_sheet(self):
        # Precision first: a small sheet has one right answer, and it is not "a few
        # calls". Walking backwards, the last track finds an empty stack and compares
        # nothing, while each earlier track examines exactly the stack entry that
        # starts later than it does. Two comparisons, no more and no less.
        tracks, count = self._count_end_stage([
            'FILE "disc.flac" FLAC',
            '  TRACK 01 AUDIO', '    INDEX 01 00:00:00',
            '  TRACK 02 AUDIO', '    INDEX 01 00:10:00',
            '  TRACK 03 AUDIO', '    INDEX 01 00:20:00',
        ])
        self.assertEqual(count, 2)
        self.assertEqual([track["end"] for track in tracks], [10.0, 20.0, 0.0])

    def test_end_stage_does_not_rescan_a_one_file_per_track_sheet(self):
        # One FILE per track is the common CUE shape and was the worst case for the
        # nested scan: no later track shares the file, so every track walked the rest
        # of the sheet. The stack keeps a separate stack per file and visits each file
        # once, so the bound here is a ceiling on cost, not a target.
        track_count = 1200
        lines = []
        for number in range(track_count):
            lines.append('FILE "track%04d.flac" FLAC' % number)
            lines.append("  TRACK 01 AUDIO")
            lines.append("    INDEX 01 00:00:00")
        tracks, count = self._count_end_stage(lines)
        self.assertEqual(len(tracks), track_count)
        self.assertLessEqual(count, 2 * track_count)

    def test_end_stage_examines_one_candidate_per_track_on_a_flat_sheet(self):
        # The ceiling above would also pass if the seam silently counted nothing, so
        # pin the floor with the other ordinary shape: no usable INDEX line, every
        # track at 0.0 on one file. Each track then discards exactly one superseded
        # candidate, which is n-1 examinations and not n^2.
        track_count = 1200
        lines = ['FILE "disc.flac" FLAC']
        for number in range(track_count):
            lines.append("  TRACK %02d AUDIO" % (number % 99 + 1))
        tracks, count = self._count_end_stage(lines)
        self.assertEqual(len(tracks), track_count)
        self.assertEqual(count, track_count - 1)
        # Every one of these tracks ties with the one after it, so the sheet states no
        # boundary for any of them; only the last entry on the file has a stated end.
        self.assertEqual([track["end"] for track in tracks],
                         [None] * (track_count - 1) + [0.0])
    def test_end_stage_work_grows_in_proportion_to_the_sheet(self):
        # The claim worth keeping is about scaling rather than a constant: this shape
        # costs about one examination per track, so quadrupling the sheet may only
        # quadruple the work with a small margin. A quadratic stage would multiply it
        # by about sixteen and fail here even if it passed a fixed ceiling.
        def count_for(track_count):
            lines = ['FILE "disc.flac" FLAC']
            for number in range(track_count):
                lines.append("  TRACK %02d AUDIO" % (number % 99 + 1))
            tracks, count = self._count_end_stage(lines)
            self.assertEqual(len(tracks), track_count)
            self.assertGreaterEqual(count, track_count // 2)
            return count

        small = count_for(600)
        large = count_for(2400)
        self.assertLessEqual(large, small * 6)

    def test_the_nested_definition_would_break_these_bounds(self):
        # A bound is only evidence if something can fail it. This is the retired
        # nested definition counting the same unit of work: on the sheet above it
        # examines about n^2/2 candidate starts, so the ceiling in
        # test_end_stage_does_not_rescan_a_one_file_per_track_sheet really does
        # separate the two algorithms instead of describing neither.
        track_count = 1200
        tracks = [{"file": "track%04d.flac" % number, "start": 0.0} for number in range(track_count)]
        examined = [0]
        for index, track in enumerate(tracks):
            start = finite_number(track.get("start"))
            for candidate in tracks[index + 1:]:
                examined[0] += 1
                candidate_start = finite_number(candidate.get("start"))
                if candidate.get("file") == track.get("file") and candidate_start > start:
                    track["end"] = candidate_start
                    break
            else:
                track["end"] = 0.0
        self.assertGreater(examined[0], 2 * track_count)
        self.assertEqual(set(track["end"] for track in tracks), {0.0})

    def test_the_measurement_seam_never_changes_the_answer(self):
        # A counter must not become behaviour, so the two runs have to agree on a
        # sheet where an extra pop is visible: out-of-order offsets make a track
        # discard a superseded candidate, two files keep the groups apart, and ties
        # make the discarded value differ from the answer.
        lines = [
            'FILE "disc.flac" FLAC', '  TRACK 01 AUDIO', '    INDEX 01 00:00:00',
            '  TRACK 02 AUDIO', '    INDEX 01 00:10:00',
            '  TRACK 03 AUDIO', '    INDEX 01 00:05:00',
            'FILE "bonus.flac" FLAC', '  TRACK 04 AUDIO', '    INDEX 01 00:00:00',
            '  TRACK 05 AUDIO', '    INDEX 01 00:00:00',
        ]
        plain = parse_cue_structure(lines, "album")["tracks"]
        counted, count = self._count_end_stage(lines)
        self.assertEqual(counted, plain)
        self.assertGreater(count, 0)

    def test_the_seam_is_optional_and_the_suite_does_not_patch_helpers(self):
        # Two shapes have to stay true for the bound above to keep meaning anything:
        # every caller may ignore the hook - library.py passes positional arguments
        # only - and no test may go back to asserting on a numeric helper call count.
        hook = inspect.signature(parse_cue_structure).parameters["observe_end_stage"]
        self.assertIsNone(hook.default)
        self.assertNotEqual(hook.kind, inspect.Parameter.POSITIONAL_ONLY)
        inner = inspect.signature(cue_parser._attach_track_ends).parameters["observe"]
        self.assertIsNone(inner.default)
        self.assertNotEqual(inner.kind, inspect.Parameter.POSITIONAL_ONLY)
        with open(os.path.abspath(__file__), encoding="utf-8") as handle:
            own_source = handle.read()
        patched_helper = "cue_parser.finite_number" + " ="
        self.assertNotIn(patched_helper, own_source)
    def test_index_separator_and_digit_spacing_variants_all_set_the_start(self):
        variants = [
            "    INDEX 01 04:00:00",
            "    INDEX 1 04:00:00",
            "    INDEX  01  04:00:00",
            "\tINDEX\t01\t04:00:00",
            "    index 01 04:00:00",
        ]
        for line in variants:
            with self.subTest(line=line):
                tracks = parse_cue_structure(
                    ['FILE "disc.flac" FLAC', "  TRACK 01 AUDIO", line], "album")["tracks"]
                self.assertEqual(tracks[0]["start"], 240.0)

    def test_pregap_and_cue_point_indexes_do_not_move_the_start(self):
        lines = ['FILE "disc.flac" FLAC', "  TRACK 01 AUDIO",
                 "    INDEX 00 00:00:00", "    INDEX 01 04:00:00", "    INDEX 02 08:00:00"]
        tracks = parse_cue_structure(lines, "album")["tracks"]
        self.assertEqual(tracks[0]["start"], 240.0)

    def test_a_trailing_index_keyword_does_not_erase_an_earlier_start(self):
        lines = ['FILE "disc.flac" FLAC', "  TRACK 01 AUDIO",
                 "    INDEX 01 04:00:00", "    INDEX 01"]
        tracks = parse_cue_structure(lines, "album")["tracks"]
        self.assertEqual(tracks[0]["start"], 240.0)
    def test_non_iterable_lines_fall_back_to_empty_source(self):
        self.assertEqual(parse_cue_structure(object(), "fallback"), {"album": "fallback", "album_artist": "未知艺术家", "tracks": []})


if __name__ == "__main__":
    unittest.main()
