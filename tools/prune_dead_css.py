#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Delete CSS declarations that a later declaration provably overrides.

The scope is deliberately narrow: a declaration is only removable when a later
declaration in the SAME file, the SAME at-rule context, the SAME selector and for
the SAME property beats it under the cascade's order + importance rules.
Identical selector text means identical specificity, so order and `!important`
are the only things that decide, and the loser can never win.

Shorthand/longhand interactions are intentionally not modelled (a later
`padding` does not retire an earlier `padding-top`), so the tool leaves some dead
declarations behind. That is the point: it must never remove a live one.

  python tools/prune_dead_css.py src/app/ui/app.css --report
  python tools/prune_dead_css.py src/app/ui/app.css --write
"""
import argparse
import collections
import hashlib
import re
import sys


def mask_comments(text):
    """Blank out comments but keep every offset, so spans stay valid."""
    out = list(text)
    for m in re.finditer(r"/\*.*?\*/", text, re.S):
        for i in range(m.start(), m.end()):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


def parse_rules(masked):
    """Return [(context_tuple, selector_text, sel_start, body_start, body_end, end)]."""
    rules = []
    stack = []
    buf_start = 0
    i = 0
    n = len(masked)
    while i < n:
        ch = masked[i]
        if ch == "{":
            head = masked[buf_start:i].strip()
            if head.startswith("@"):
                stack.append(head)
                i += 1
                buf_start = i
                continue
            depth = 1
            j = i + 1
            while j < n and depth:
                if masked[j] == "{":
                    depth += 1
                elif masked[j] == "}":
                    depth -= 1
                j += 1
            rules.append((tuple(stack), head, buf_start, i + 1, j - 1, j))
            i = j
            buf_start = i
            continue
        if ch == "}":
            if stack:
                stack.pop()
            i += 1
            buf_start = i
            continue
        i += 1
    return rules


def declarations(text, masked, body_start, body_end):
    """Split a rule body into declarations, tracking parens and strings."""
    chunks = []
    start = body_start
    depth = 0
    quote = None
    i = body_start
    while i <= body_end:
        at_end = i >= body_end
        ch = ";" if at_end else masked[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            raw = text[start:i]
            if raw.strip():
                chunks.append((start, i, at_end, raw))
            start = i + 1
        i += 1
    out = []
    for s, e, at_end, raw in chunks:
        body = raw.strip()
        if ":" not in body:
            continue
        prop, value = body.split(":", 1)
        prop = prop.strip().lower()
        if not prop or prop.startswith("--"):
            # Custom properties are read by name from other rules and from JS;
            # retiring one is not a safe local decision.
            continue
        out.append(
            {
                "start": s,
                "end": e,
                "has_semicolon": not at_end,
                "prop": prop,
                "important": bool(re.search(r"!\s*important\s*$", value, re.I)),
                "raw": raw,
            }
        )
    return out


def split_selectors(sel):
    parts = []
    depth = 0
    cur = []
    for ch in sel:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append(" ".join("".join(cur).split()))
            cur = []
            continue
        cur.append(ch)
    parts.append(" ".join("".join(cur).split()))
    return [p for p in parts if p]


VAR_REF = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)")


def keep_last_custom_property_reference(text, removable):
    """Refuse to delete a declaration that is a custom property's last reader.

    A shadowed `width: var(--grid)` is dead as a cascade participant, but it can
    still be the only thing that reads `--grid`. Deleting it would leave the
    definition behind as an orphan, and would silently empty out any test that
    pins the pair. Pruning must not create new dead code.
    """
    drop = {d["start"] for d in removable}
    if not removable:
        return removable

    def refs_after(skip):
        out = []
        cursor = 0
        for d in sorted(removable, key=lambda x: x["start"]):
            if d["start"] not in skip:
                continue
            out.append(text[cursor:d["start"]])
            cursor = d["end"] + (1 if d["has_semicolon"] else 0)
        out.append(text[cursor:])
        return set(VAR_REF.findall("".join(out)))

    full = set(VAR_REF.findall(text))
    without = refs_after(drop)
    orphaned = full - without
    if not orphaned:
        return removable

    rescued = set()
    for d in removable:
        if set(VAR_REF.findall(d["raw"])) & orphaned:
            rescued.add(d["start"])
    if not rescued:
        return removable
    return [d for d in removable if d["start"] not in rescued]


def analyse(path):
    text = open(path, "rb").read().decode("utf-8")
    if "\r\n" in text:
        raise SystemExit(path + " has CRLF; normalise line endings first")
    masked = mask_comments(text)
    rules = parse_rules(masked)

    buckets = collections.defaultdict(list)   # (ctx, selector, prop) -> [decl_id]
    decl_index = {}                           # decl_id -> (decl, [bucket keys])
    rule_decls = collections.defaultdict(list)
    for order, (ctx, sel, sel_start, body_start, body_end, end) in enumerate(rules):
        selectors = split_selectors(sel)
        for d in declarations(text, masked, body_start, body_end):
            decl_id = (order, d["start"])
            keys = [(ctx, one, d["prop"]) for one in selectors]
            for key in keys:
                buckets[key].append(decl_id)
            decl_index[decl_id] = (d, keys)
            rule_decls[order].append(decl_id)

    dead_votes = collections.Counter()
    for ids in buckets.values():
        if len(ids) < 2:
            continue
        # Same selector, same context, same property: specificity and origin are
        # equal, so only `!important` and source order decide. If any declaration
        # is important, the last important one wins and every other declaration
        # in the bucket - including later normal ones - is dead. Otherwise the
        # last declaration wins and all earlier ones are dead.
        important = [i for i in ids if decl_index[i][0]["important"]]
        winner = important[-1] if important else ids[-1]
        for decl_id in ids:
            if decl_id != winner:
                dead_votes[decl_id] += 1

    removable = []
    for decl_id, (d, keys) in decl_index.items():
        if keys and dead_votes[decl_id] == len(keys):
            removable.append(d)

    removable = keep_last_custom_property_reference(text, removable)

    # Rules that lose every declaration are removed whole, selector included.
    dead_starts = {d["start"] for d in removable}
    whole_rules = []
    for order, ids in rule_decls.items():
        if ids and all(i[1] in dead_starts for i in ids):
            _, _, sel_start, _, _, end = rules[order]
            whole_rules.append((sel_start, end))
    covered = set()
    for order, ids in rule_decls.items():
        if ids and all(i[1] in dead_starts for i in ids):
            covered.update(i[1] for i in ids)
    removable = [d for d in removable if d["start"] not in covered]
    return text, removable, whole_rules, len(decl_index)


def drop_empty_at_rules(text):
    """Remove @media/@supports blocks whose body became whitespace only."""
    changed = True
    while changed:
        changed = False
        masked = mask_comments(text)
        for m in re.finditer(r"@[a-zA-Z-]+[^{]*\{", masked):
            depth = 1
            j = m.end()
            while j < len(masked) and depth:
                if masked[j] == "{":
                    depth += 1
                elif masked[j] == "}":
                    depth -= 1
                j += 1
            body = masked[m.end():j - 1]
            if body.strip():
                continue
            line_start = text.rfind("\n", 0, m.start()) + 1
            text = text[:line_start] + text[j:]
            changed = True
            break
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    text, removable, whole_rules, total = analyse(args.path)
    print(f"{args.path}: declarations={total} removable={len(removable)} "
          f"whole_rules={len(whole_rules)}")
    if args.report:
        counts = collections.Counter(d["prop"] for d in removable)
        for prop, n in counts.most_common(15):
            print(f"  {n:5d}  {prop}")

    if not args.write:
        return 0

    spans = [(d["start"], d["end"] + (1 if d["has_semicolon"] else 0)) for d in removable]
    spans += whole_rules
    spans.sort()
    out = []
    cursor = 0
    for s, e in spans:
        if s < cursor:
            continue
        out.append(text[cursor:s])
        cursor = e
    out.append(text[cursor:])
    new = "".join(out)
    new = drop_empty_at_rules(new)
    new = re.sub(r"\{\s*\}", "", new)
    new = re.sub(r"\n{3,}", "\n\n", new)
    new = re.sub(r"[ \t]+\n", "\n", new)
    open(args.path, "wb").write(new.encode("utf-8"))
    print(f"wrote {args.path}: {len(text)} -> {len(new)} bytes "
          f"sha256 {hashlib.sha256(new.encode('utf-8')).hexdigest().upper()[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
