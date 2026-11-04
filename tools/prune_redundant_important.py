#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Drop `!important` from declarations that the cascade map proves redundant.

The map (`tools/browser-e2e/css_cascade_map.js`) records, for every declaration
that actually wins a property on some element in some sampled state, whether it
would still win with its `!important` removed. This tool turns that verdict into
an edit, but only for declarations it can locate unambiguously in the source:

  * the (file, at-rule context, selector, property) tuple must appear exactly
    once -- two rules with the same selector and property are the duplicate
    layering this project deliberately keeps, and guessing which one the map
    meant is not worth the risk;
  * the source declaration must carry `!important` and its value must match the
    one the browser serialized (after normalising whitespace, `0` vs `0px`, and
    hex vs `rgb()` colours);
  * `@keyframes` and `@font-face` bodies are skipped -- `!important` is ignored
    there anyway, so touching them would be churn without effect.

The snapshot harness is the oracle: `tools/browser-e2e/css_snapshot.js` before
and after, diffed with `tools/diff_css_snapshot.py`, must report zero changes.

  python tools/prune_redundant_important.py --map artifacts/r477/cascade_map_before.json --report
  python tools/prune_redundant_important.py --map artifacts/r477/cascade_map_before.json --write
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prune_dead_css import declarations, mask_comments, parse_rules

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_CONTEXT = ("@keyframes", "@font-face", "@page")

HEX = re.compile(r"^#([0-9a-f]{3}|[0-9a-f]{6})$")
RGB = re.compile(r"^rgba?\(([^)]*)\)$")


def _color(value):
    """Normalise a colour to an (r, g, b, a) tuple, or None when it is not one."""
    value = value.strip().lower()
    match = HEX.match(value)
    if match:
        digits = match.group(1)
        if len(digits) == 3:
            digits = "".join(ch * 2 for ch in digits)
        return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16), 1.0)
    match = RGB.match(value)
    if match:
        parts = [p.strip() for p in match.group(1).split(",")]
        if len(parts) in (3, 4) and all(p.endswith("%") or p.replace(".", "").isdigit() for p in parts):
            numbers = [float(p[:-1]) * 2.55 if p.endswith("%") else float(p) for p in parts]
            alpha = numbers[3] if len(numbers) == 4 else 1.0
            return (int(round(numbers[0])), int(round(numbers[1])), int(round(numbers[2])), round(alpha, 3))
    return None


def normalise(value):
    """Make the browser's serialisation comparable with the hand-written source."""
    text = " ".join(value.split()).lower()
    text = re.sub(r"\s*,\s*", ",", text)
    text = re.sub(r"\s*/\s*", "/", text)
    # CSSOM serialises a bare zero length as `0px`; the source usually writes `0`.
    text = re.sub(r"(?<![\w.#-])0(?![\w.%])", "0px", text)
    return text


def values_match(browser_value, source_value):
    if normalise(browser_value) == normalise(source_value):
        return True
    left, right = _color(browser_value), _color(source_value)
    return left is not None and left == right


def norm_selector(text):
    """Compare selector text the way the browser serialises it, not as typed.

    CSSOM rewrites `.a>.b` as `.a > .b` and drops spaces inside `:not( ... )`, so
    both sides go through the same combiner/whitespace normalisation.
    """
    out = " ".join(text.split())
    out = re.sub(r"\s*([>+~,])\s*", r"\1", out)
    out = re.sub(r"\(\s*", "(", out)
    out = re.sub(r"\s*\)", ")", out)
    return out


def norm_context(parts):
    """At-rule conditions are serialised with spaces the source may omit.

    The browser reports `(min-width: 761px)`; the stylesheet writes
    `(min-width:761px)`. Both sides collapse to the same text.
    """
    out = norm_selector(" ".join(p for p in parts if p))
    out = re.sub(r"(@[\w-]+)\s*\(", r"\1(", out)
    out = re.sub(r":\s+", ":", out)
    return out


def collect(path):
    """Return {key: [declaration, ...]} for one stylesheet."""
    with open(path, "rb") as handle:
        text = handle.read().decode("utf-8")
    masked = mask_comments(text)
    index = collections.defaultdict(list)
    for context, selector, _sel_start, body_start, body_end, _end in parse_rules(masked):
        if any(token in " ".join(context) for token in SKIP_CONTEXT):
            continue
        key = (norm_context(context), norm_selector(selector))
        for decl in declarations(text, masked, body_start, body_end):
            decl["context"] = key[0]
            decl["selector"] = key[1]
            index[key + (decl["prop"],)].append(decl)
    return text, index


def strip_important(raw):
    """Remove the `!important` token, keeping every other byte of the declaration."""
    head, sep, rest = raw.partition(":")
    if not sep:
        return None
    trimmed = re.sub(r"\s*!\s*important\s*$", "", rest, flags=re.I)
    if trimmed == rest:
        return None
    return head + sep + trimmed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True, help="cascade map JSON")
    parser.add_argument("--report", action="store_true", help="print what would change")
    parser.add_argument("--write", action="store_true", help="rewrite the stylesheets")
    parser.add_argument("--sheet", action="append", default=None,
                        help="limit to one stylesheet (repeatable); default is all")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--keep", default=None,
                        help="JSON list of {sheet, selector, prop} whose !important is a contract")
    args = parser.parse_args(argv)

    with open(args.map, encoding="utf-8") as handle:
        cascade = json.load(handle)

    keep = set()
    if args.keep:
        for item in json.load(open(args.keep, encoding="utf-8")):
            keep.add((item["sheet"], norm_selector(item["selector"]), item["prop"]))

    entries = [v for v in cascade["declarations"].values() if v["removable"]]
    by_sheet = collections.defaultdict(list)
    for entry in entries:
        by_sheet[entry["sheet"]].append(entry)

    reasons = collections.Counter()
    edits = collections.defaultdict(list)
    kept = collections.Counter()

    for sheet, items in sorted(by_sheet.items()):
        if not sheet.endswith(".css"):
            reasons["not a stylesheet"] += len(items)
            continue
        if args.sheet and sheet not in args.sheet:
            continue
        path = os.path.join(REPO, "src", "app", "ui", sheet)
        if not os.path.exists(path):
            reasons["missing file"] += len(items)
            continue
        text, index = collect(path)
        for entry in items:
            key = (norm_context([entry["context"]]) if entry["context"] else "",
                   norm_selector(entry["selector"]), entry["prop"])
            matches = index.get(key, [])
            if len(matches) != 1:
                reasons["ambiguous or missing (selector+prop appears %d times)" % len(matches)] += 1
                if args.verbose and len(matches) == 0 and reasons["ambiguous or missing (selector+prop appears 0 times)"] <= 12:
                    print("  no match  %-16s ctx=%r sel=%r prop=%s" % (
                        sheet, key[0], key[1], key[2]))
                continue
            decl = matches[0]
            if not decl["important"]:
                reasons["source is not !important"] += 1
                continue
            source_value = decl["raw"].partition(":")[2]
            source_value = re.sub(r"\s*!\s*important\s*$", "", source_value, flags=re.I)
            if (sheet, norm_selector(entry["selector"]), entry["prop"]) in keep:
                reasons["pinned by a CSS contract test"] += 1
                continue
            if not values_match(entry["value"], source_value):
                reasons["value mismatch"] += 1
                if args.verbose:
                    print("  mismatch %s %s %s: browser=%r source=%r" % (
                        sheet, entry["selector"], entry["prop"], entry["value"], source_value.strip()))
                continue
            replacement = strip_important(decl["raw"])
            if replacement is None:
                reasons["no !important token"] += 1
                continue
            edits[sheet].append((decl["start"], decl["end"], decl["raw"], replacement, entry))

    total = 0
    for sheet, items in sorted(edits.items()):
        path = os.path.join(REPO, "src", "app", "ui", sheet)
        with open(path, "rb") as handle:
            text = handle.read().decode("utf-8")
        # Apply back-to-front so earlier spans keep their offsets.
        for start, end, raw, replacement, _entry in sorted(items, key=lambda item: -item[0]):
            if text[start:end] != raw:
                reasons["span drift"] += 1
                continue
            text = text[:start] + replacement + text[end:]
        total += len(items)
        print("%-18s %4d declarations lose !important" % (sheet, len(items)))
        if args.write:
            data = text.encode("utf-8")
            assert b"\r\n" not in data
            with open(path, "wb") as handle:
                handle.write(data)
            print("%-18s wrote %d bytes" % (sheet, len(data)))

    print("\ncandidates from the map: %d" % len(entries))
    print("edits applied: %d" % total)
    for reason, count in reasons.most_common():
        print("  skipped: %-58s %d" % (reason, count))
    if not args.write:
        print("\n(report only; pass --write to apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
