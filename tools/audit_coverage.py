#!/usr/bin/env python3
"""Rank the remaining app.js deep-read queue so a round can size itself.

Context (R168, 2026-09-23).  Two ledger entries carry the whole remaining code
debt: the not-yet-deep-read list and the symbol-coverage list.  Both close only
when every registered symbol of ``src/app/ui/app.js`` has actually been read.
Before R168 every round re-derived that queue with throwaway scripts written
under %TEMP% and deleted again, which cost several tooling steps per round and
left no way to plan a batch size.  This file makes that derivation permanent, so
a round can ask one question -- which contiguous face is the densest unread one?
-- and get a reproducible answer.

Two definitions are pinned here and nowhere else:

* symbol -- a line-anchored function declaration, i.e. a line that starts with
  ``function`` or ``async function`` followed by a name and an opening paren.
  This is the anchor the historical registrations used, so the numbers printed
  here are comparable with them.
* named -- the symbol's exact word occurs at least once across the three root
  records (TODO.md, CHANGELOG_AI.md, PROJECT_CONTEXT.md).  "Exact word" matters:
  the ledger counts ``loadLibrary`` and ``loadLibraryResponse`` as two different
  symbols, so a record that only ever mentions the longer one has *not* named the
  shorter.  An earlier round recorded that treating a short name as a substring of
  a long one shifted a historical count by exactly one symbol; that drift is a
  measurement bug, and the boundary rule below is what prevents it.

Deliberately *not* stored in this file: any live count.  How many symbols exist,
how many are still unnamed, and how large the top face is all move whenever
app.js or the root records change, so freezing one of those numbers here would
turn a working tree into a red gate.  The guarded invariants are structural
instead -- the two naming methods agree, the queue partitions exactly once, the
ranking is deterministic.

Usage:

    python tools/audit_coverage.py             # ranked report, densest first
    python tools/audit_coverage.py --json      # machine-readable
    python tools/audit_coverage.py --limit 8   # fewer rows
    python tools/audit_coverage.py --gap 24    # split faces more finely
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = "src/app/ui/app.js"
ROOT_DOCS = ("TODO.md", "CHANGELOG_AI.md", "PROJECT_CONTEXT.md")

# Line-anchored declaration: the historical convention.  Indented inner
# functions are not counted, which is what keeps this index comparable with the
# per-round registrations quoted in TODO.md.
FUNCTION_START = re.compile(r"^(?:async )?function ([A-Za-z_$][A-Za-z0-9_$]*)[ \t]*\(")

# An identifier as it appears inside prose.  Matching is maximal, so a name
# written directly against adjacent word characters -- including CJK, which
# ``[A-Za-z0-9_$]`` excludes but the historical boundary regex treats as a word
# character only when unicode -- is absorbed into a longer token and is
# therefore not a naming occurrence.  Keeping this method in agreement with
# ``reference_named`` is guarded rather than assumed.
IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")

# Symbols this far apart are still the same face.  A face is a chunk one round
# reads in one sitting; isolated leftovers are better merged into a neighbour
# than scheduled as their own round.
DEFAULT_GAP_LINES = 40

REPORT_KEYS = (
    "target",
    "target_content_lines",
    "symbols",
    "unique_symbols",
    "named_symbols",
    "zero_named_symbols",
    "gap_lines",
    "faces",
)

FACE_KEYS = ("start", "end", "count", "span", "held", "named_inside", "symbols")


def read_text(repo_root: Path, relative: str) -> str:
    return (repo_root / relative).read_text(encoding="utf-8", newline="")


def content_lines(text: str) -> int:
    """The repo-wide line convention: newline-delimited content lines."""
    return len(text.split("\n")) - 1


def index_functions(text: str) -> tuple:
    """Every line-anchored function in *text*, with its inclusive line span."""
    lines = text.split("\n")
    found = []
    for number, line in enumerate(lines, 1):
        match = FUNCTION_START.match(line)
        if match:
            found.append({"name": match.group(1), "start": number, "end": number})
    for position, entry in enumerate(found):
        if position + 1 < len(found):
            entry["end"] = found[position + 1]["start"] - 1
        else:
            entry["end"] = len(lines)
    return tuple(found)


def reference_named(names, blob: str):
    """Which names occur as their own word: one boundary-checked scan per name."""
    return frozenset(
        name
        for name in names
        if re.search(
            r"(?<![A-Za-z0-9_$])" + re.escape(name) + r"(?![A-Za-z0-9_$])", blob
        )
    )


def token_named(names, blobs):
    """The same question, answered by scanning the documents once rather than
    once per name.  Used for the report; guarded to agree with reference_named."""
    wanted = set(names)
    hit = set()
    for blob in blobs:
        for token in IDENTIFIER.findall(blob):
            if token in wanted:
                hit.add(token)
    return frozenset(hit)


def _face(members, symbols, named):
    start = members[0]["start"]
    end = members[-1]["end"]
    inside = sum(
        1
        for entry in symbols
        if start <= entry["start"] <= end and entry["name"] not in named
    )
    return {
        "start": start,
        "end": end,
        "count": len(members),
        "span": end - start + 1,
        # Cross-check: the grouping and the span must agree on how many unread
        # symbols a face holds.  If they ever diverge, a face has swallowed or
        # dropped a symbol, and the queue no longer partitions the debt.
        "held": inside,
        "named_inside": sum(
            1
            for entry in symbols
            if start <= entry["start"] <= end and entry["name"] in named
        ),
        "symbols": [entry["name"] for entry in members],
    }


def build_faces(symbols, named, gap_lines: int = DEFAULT_GAP_LINES):
    """Group unnamed symbols into contiguous faces, densest queues first.

    A face runs from its first unnamed symbol to its last; two unnamed symbols
    more than *gap_lines* apart start separate faces.  Named symbols inside a
    span still cost reading time, so ``named_inside`` is reported next to
    ``count`` instead of being folded into it.
    """
    queue = [entry for entry in symbols if entry["name"] not in named]
    faces = []
    current = []
    for entry in queue:
        if current and entry["start"] - current[-1]["end"] > gap_lines:
            faces.append(_face(current, symbols, named))
            current = []
        current.append(entry)
    if current:
        faces.append(_face(current, symbols, named))
    faces.sort(key=lambda face: (-face["count"], face["span"], face["start"]))
    return faces


def measure(repo_root=REPO_ROOT, gap_lines: int = DEFAULT_GAP_LINES):
    repo_root = Path(repo_root)
    text = read_text(repo_root, TARGET)
    symbols = index_functions(text)
    names = [entry["name"] for entry in symbols]
    blobs = [read_text(repo_root, relative) for relative in ROOT_DOCS]
    named = token_named(names, blobs)
    faces = build_faces(symbols, named, gap_lines)
    # The debt counts unread *declarations*.  It is deliberately not written as
    # ``len(names) - len(named)``: that subtraction only agrees with the queue
    # while every name is unique.  A name declared twice and named once would
    # make the report claim a debt the faces cannot hold, and the accounting
    # guard would then measure a number the tool itself cannot reproduce.
    zero_named = sum(1 for entry in symbols if entry["name"] not in named)
    return {
        "target": TARGET,
        "target_content_lines": content_lines(text),
        "symbols": len(symbols),
        "unique_symbols": len(set(names)),
        "named_symbols": len(named),
        "zero_named_symbols": zero_named,
        "gap_lines": gap_lines,
        "faces": faces,
    }


def format_report(result, limit=None):
    rows = result["faces"] if not limit else result["faces"][:limit]
    out = [
        "target=%s content_lines=%d" % (result["target"], result["target_content_lines"]),
        "symbols=%d unique=%d named=%d zero_named=%d"
        % (
            result["symbols"],
            result["unique_symbols"],
            result["named_symbols"],
            result["zero_named_symbols"],
        ),
        "gap_lines=%d faces=%d" % (result["gap_lines"], len(result["faces"])),
    ]
    for rank, face in enumerate(rows, 1):
        out.append(
            "#%-2d :%-5d-%-6d count=%-3d span=%-5d density=%5.2f%% named_inside=%-3d  %s"
            % (
                rank,
                face["start"],
                face["end"],
                face["count"],
                face["span"],
                100.0 * face["count"] / face["span"],
                face["named_inside"],
                ", ".join(face["symbols"]),
            )
        )
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--limit", type=int, default=14, help="rows to print (0 = all)")
    parser.add_argument("--gap", type=int, default=DEFAULT_GAP_LINES, help="face gap in lines")
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    result = measure(args.repo_root, args.gap)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0
    print(format_report(result, args.limit or None))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())