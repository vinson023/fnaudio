#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Collapse duplicate selector blocks into one, without changing what wins.

The file was built by appending, so the same selector often appears two to five
times. Merging those blocks is only safe when the move cannot change a winner,
and that takes three separate proofs:

1. **Inside the group** the selector text is identical, so specificity is
   identical too and only order + importance decide. A declaration that a later
   declaration in the same group beats can never win, so it is dropped.

2. **Between the blocks** a rule can only overtake a moved declaration if it
   overlaps on longhands, ties on specificity *and* ties on importance. The
   longhand sets come from the browser's own shorthand expansion
   (`tools/browser-e2e/css_longhand_table.js`), not from a name-prefix guess:
   `border-radius` and `border-color` share a prefix but never compete.

3. **On the page** a tying rule only matters if it can land on the same element
   as the group's selector. `tools/browser-e2e/css_selector_overlap.js` answers
   that by intersecting matched-element sets across the 96 sampled states, and
   any rule carrying a dynamic pseudo-class (`:hover`, `:focus`, ...) counts as
   tying unconditionally, because the sampler cannot observe those.

When all three pass, the group's blocks are replaced by a single block at the
position of its last block, holding the surviving declarations in their original
order.

  python tools/merge_duplicate_selectors.py src/app/ui/app.css \\
      --longhands artifacts/r478/longhands.json --overlap artifacts/r478/overlap.json --report
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prune_dead_css import declarations, mask_comments, parse_rules

DYNAMIC = re.compile(
    r':(hover|active|focus|focus-visible|focus-within|visited|target|checked|disabled|'
    r'enabled|placeholder-shown|autofill|user-invalid|user-valid|open|popover-open|modal)\b'
)
SKIP_CONTEXT = ('@keyframes', '@font-face', '@page')
VAR = re.compile(r'var\(\s*(--[\w-]+)')


def norm(selector):
    out = ' '.join(selector.split())
    out = re.sub(r'\s*([>+~,])\s*', r'\1', out)
    out = re.sub(r'\(\s*', '(', out)
    out = re.sub(r'\s*\)', ')', out)
    return out


SPEC_CACHE = {}


def specificity(part):
    if part in SPEC_CACHE:
        return SPEC_CACHE[part]
    a = b = c = 0
    text = re.sub(r':where\([^()]*\)', ' ', part)
    for inner in re.findall(r':(?:not|is|has|matches)\(([^()]*)\)', text):
        best = (0, 0, 0)
        for piece in inner.split(','):
            s = specificity(piece.strip())
            if s > best:
                best = s
        a += best[0]
        b += best[1]
        c += best[2]
    text = re.sub(r':(?:not|is|has|matches)\([^()]*\)', ' ', text)

    def take(pattern, weight):
        nonlocal a, b, c, text

        def repl(match):
            nonlocal a, b, c
            if weight == 0:
                a += 1
            elif weight == 1:
                b += 1
            else:
                c += 1
            inner = match.group(1) if match.groups() else None
            return ' ' if inner is None else inner

        text = re.sub(pattern, repl, text)

    take(r'#[\w-]+', 0)
    take(r'\.[\w-]+', 1)
    take(r'\[[^\]]*\]', 1)
    take(r'::[\w-]+(?:\([^()]*\))?', 2)
    take(r':[\w-]+(?:\([^()]*\))?', 1)
    take(r'(?:^|[\s>+~,])([a-zA-Z][\w-]*)', 2)
    take(r'\*', 2)
    SPEC_CACHE[part] = (a, b, c)
    return (a, b, c)


def selector_specificities(selector):
    """Every specificity the selector list can take, one per comma part.

    A list like `dialog, #folderDialog` is `(0,0,1)` on a bare `<dialog>` and
    `(1,0,0)` on the id, so a single "max" number is wrong in both directions:
    it hides a real order tie on the plain element and invents one on the id.
    Comparing the sets keeps every tie that can actually happen.
    """
    out = set()
    depth = 0
    cur = []
    parts = []
    for ch in selector:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(0, depth - 1)
        if ch == ',' and depth == 0:
            parts.append(''.join(cur))
            cur = []
            continue
        cur.append(ch)
    parts.append(''.join(cur))
    for part in parts:
        out.add(specificity(part.strip()))
    return out


class Longhands(object):
    """Browser-expanded longhand sets, keyed by (property, value)."""

    def __init__(self, path):
        self.table = json.load(open(path, encoding='utf-8')) if path else {}
        self.by_prop = {}
        for key, names in self.table.items():
            prop = key.split('\u0000')[0]
            self.by_prop.setdefault(prop, set()).update(names)

    def of(self, prop, value):
        hit = self.table.get(prop + '\u0000' + value)
        if hit is not None:
            return set(hit)
        return set(self.by_prop.get(prop, {prop}))


def split_body(text, masked, body_start, body_end):
    """Every declaration in a rule body, custom properties included.

    `prune_dead_css.declarations` deliberately drops `--*` declarations, but this
    tool rebuilds rule bodies, so dropping them would delete the design tokens in
    `:root`. They are carried through untouched and never marked dead.
    """
    chunks = []
    start = body_start
    depth = 0
    quote = None
    i = body_start
    while i <= body_end:
        at_end = i >= body_end
        ch = ';' if at_end else masked[i]
        if quote:
            if ch == '\\':
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in '"\'':
            quote = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(0, depth - 1)
        elif ch == ';' and depth == 0:
            raw = text[start:i]
            if raw.strip():
                chunks.append(raw)
            start = i + 1
        i += 1
    out = []
    for raw in chunks:
        body = raw.strip()
        if ':' not in body:
            continue
        prop, value = body.split(':', 1)
        prop = prop.strip().lower()
        if not prop:
            continue
        important = bool(re.search(r'!\s*important\s*$', value, re.I))
        out.append({
            'prop': prop,
            'value': re.sub(r'\s*!\s*important\s*$', '', value, flags=re.I).strip(),
            'important': important,
            'custom': prop.startswith('--'),
            'raw': body,
        })
    return out


def load_rules(text, longhands):
    masked = mask_comments(text)
    rules = []
    for index, (ctx, sel, sel_start, body_start, body_end, end) in enumerate(parse_rules(masked)):
        if any(token in ' '.join(ctx) for token in SKIP_CONTEXT):
            continue
        # `parse_rules` reports the start of the run-up to the selector, which
        # includes the newline and indentation before it. Edits have to begin at
        # the first real character, or a deletion of one rule eats the newline
        # that the next rule's span starts on.
        head = text[sel_start:body_start - 1]
        sel_start += len(head) - len(head.lstrip())
        decls = []
        for d in split_body(text, masked, body_start, body_end):
            d['longhands'] = {d['prop']} if d['custom'] else longhands.of(d['prop'], d['value'])
            decls.append(d)
        rules.append({
            'index': index,
            'ctx': ' '.join(ctx),
            'selector': sel,
            'nsel': norm(sel),
            'specs': selector_specificities(sel),
            'sel_start': sel_start,
            'body_start': body_start,
            'body_end': body_end,
            'end': end,
            'decls': decls,
        })
    return rules


def line_span(text, start, end):
    """Widen [start, end) to whole lines when the span already sits on its own."""
    line_start = text.rfind('\n', 0, start) + 1
    if text[line_start:start].strip() == '':
        start = line_start
    # `sel_start` points at the start of the whitespace run in front of the
    # selector, and comments were masked into whitespace, so a rule that follows
    # a comment starts at the comment. Deleting from there would take the
    # comment with it -- and a few suites slice the sheet on those comments.
    while start < end:
        if text[start].isspace():
            start += 1
        elif text.startswith('/*', start):
            close = text.find('*/', start + 2)
            if close == -1:
                break
            start = close + 2
        else:
            break
    line_end = text.find('\n', end)
    if line_end != -1 and text[end:line_end].strip() == '':
        end = line_end + 1
    return start, end


def plan_file(path, longhands, overlap, verbose=False, blocked_groups=None, no_merge=()):
    text = open(path, 'rb').read().decode('utf-8')
    rules = load_rules(text, longhands)
    sheet = os.path.basename(path)

    # A declaration that is the last reader of a custom property must survive:
    # dropping it would leave the property declared and never read, which is the
    # same orphan `prune_dead_css.py` guards against.
    readers = collections.Counter()
    for rule in rules:
        for d in rule['decls']:
            d['refs'] = set(VAR.findall(d['value']))
            readers.update(d['refs'])
    groups = collections.defaultdict(list)
    for rule in rules:
        groups[(rule['ctx'], rule['nsel'])].append(rule)

    edits = []
    stats = collections.Counter()
    skipped = collections.Counter()
    position = {rule['index']: offset for offset, rule in enumerate(rules)}

    for key, blocks in groups.items():
        if len(blocks) < 2:
            continue
        if key[1] in no_merge:
            skipped['the group text is pinned by a CSS contract test'] += 1
            continue
        blocks.sort(key=lambda r: r['index'])
        flat = []
        for bi, block in enumerate(blocks):
            for d in block['decls']:
                d['seq'] = len(flat)
                flat.append((bi, d))
        dead = set()
        for i, (bi, d) in enumerate(flat):
            if d['custom']:
                continue
            # A declaration is dead only when EVERY longhand it sets is covered by
            # a later declaration. `border:1px solid X` followed by `border-top:0`
            # still decides the other three border colours, and `flex:0 0 60px`
            # followed by `flex-grow:1` still decides the basis.
            remaining = set(d['longhands'])
            for bj, f in flat[i + 1:]:
                if f['custom']:
                    continue
                if d['important'] and not f['important']:
                    continue
                remaining -= f['longhands']
                if not remaining:
                    break
            if not remaining:
                dead.add(i)
        # Nothing in this group may be the only thing keeping a custom property
        # read: `--x` declared and never used is the orphan `prune_dead_css.py`
        # already refuses to create.
        dropped = collections.Counter()
        for i in dead:
            dropped.update(flat[i][1]['refs'])
        for name, count in dropped.items():
            if readers[name] - count <= 0:
                for i in list(dead):
                    if name in flat[i][1]['refs']:
                        dead.discard(i)
        readers.subtract(collections.Counter(
            name for i in dead for name in flat[i][1]['refs']))
        live = [(bi, d) for i, (bi, d) in enumerate(flat) if i not in dead]
        last_block = blocks[-1]
        last_index = len(blocks) - 1
        earlier = [(bi, d) for bi, d in live if bi < last_index]

        if not earlier:
            # Everything before the last block is dead: pure deletion, no move.
            for block in blocks[:-1]:
                start, end = line_span(text, block['sel_start'], block['end'])
                edits.append((start, end, ''))
            stats['deleted_blocks'] += len(blocks) - 1
            stats['dead_declarations'] += len(dead)
            stats['groups_deleted'] += 1
            continue

        # Can any rule between the blocks overtake a moved declaration?
        between = rules[position[blocks[0]['index']] + 1:position[last_block['index']]]
        names = set()
        importance = set()
        for _, d in earlier:
            names |= d['longhands']
            importance.add(d['important'])
        overlap_key = '%s|%s|%s' % (sheet, key[0], key[1])
        co_occurring = set(overlap.get(overlap_key, []))
        group_indices = set(block['index'] for block in blocks)
        tying = []
        clash = None
        for rule in between:
            if rule['index'] in group_indices:
                continue
            rule_names = set()
            rule_importance = set()
            for d in rule['decls']:
                rule_names |= d['longhands']
                rule_importance.add(d['important'])
            if not (rule_names & names):
                continue
            if not (rule['specs'] & blocks[0]['specs']):
                continue
            if not (rule_importance & importance):
                continue
            tying.append(rule)
            # The same selector in another at-rule context matches exactly the
            # same elements, so it always competes; no overlap probe needed.
            same_selector = rule['nsel'] == key[1]
            if DYNAMIC.search(rule['selector']) or same_selector or rule['nsel'] in co_occurring:
                if clash is None:
                    clash = rule
        if blocked_groups is not None:
            blocked_groups.append({
                'ctx': key[0],
                'selector': key[1],
                'blockers': sorted(set(rule['nsel'] for rule in tying)),
            })
        if clash is not None:
            skipped['a tying rule shares an element with the group'] += 1
            if verbose:
                print('  skip %-46s blocked by %s' % (key[1][:46], clash['selector'][:60]))
            continue

        raws = [d['raw'] for _, d in live]
        # Keep the one-declaration-per-line layout when any block in the group
        # used it. Several suites read a declaration block line by line, and a
        # rule that suddenly runs everything together would silently stop
        # satisfying them even though the cascade is identical.
        formatted = [text[b['body_start']:b['body_end']] for b in blocks
                     if '\n' in text[b['body_start']:b['body_end']]]
        original = text[last_block['body_start']:last_block['body_end']]
        # Only trailing whitespace may be carried over. A body whose last
        # declaration has no semicolon would otherwise hand its own tail back as
        # "closing" and duplicate that declaration in the rebuilt rule.
        closing = re.search(r'\s*$', original).group(0)
        if formatted:
            match = re.match(r'\s*\n([ \t]*)', formatted[-1])
            indent = match.group(1) if match else '  '
            body = '\n' + indent + (';\n' + indent).join(raws) + ';' + closing
        else:
            body = ';'.join(raws) + closing
        replacement = last_block['selector'] + '{' + body + '}'
        edits.append((last_block['sel_start'], last_block['end'], replacement))
        for block in blocks[:-1]:
            start, end = line_span(text, block['sel_start'], block['end'])
            edits.append((start, end, ''))
        stats['merged_groups'] += 1
        stats['deleted_blocks'] += len(blocks) - 1
        stats['moved_declarations'] += len(earlier)
        stats['dead_declarations'] += len(dead)

    # Apply back to front; drop edits that overlap an earlier one.
    edits.sort(key=lambda item: item[0], reverse=True)
    out = text
    last_start = len(text) + 1
    applied = 0
    for start, end, replacement in edits:
        if end > last_start:
            continue
        out = out[:start] + replacement + out[end:]
        last_start = start
        applied += 1
    return out, stats, skipped, applied


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+')
    parser.add_argument('--longhands', default='artifacts/r478/longhands.json')
    parser.add_argument('--overlap', default='artifacts/r478/overlap.json')
    parser.add_argument('--report', action='store_true')
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--export-blockers', default=None,
                        help='write the tying selectors per group, for css_selector_overlap.js')
    parser.add_argument('--no-merge', default='tools/css_merge_contracts.json',
                        help='selectors whose rule text a test reads verbatim')
    args = parser.parse_args(argv)

    longhands = Longhands(args.longhands)
    overlap = json.load(open(args.overlap, encoding='utf-8')) if args.overlap else {}
    export = {} if args.export_blockers else None
    no_merge = set()
    if args.no_merge and os.path.exists(args.no_merge):
        no_merge = set(json.load(open(args.no_merge, encoding='utf-8')))

    for path in args.files:
        collected = [] if export is not None else None
        out, stats, skipped, applied = plan_file(
            path, longhands, overlap, args.verbose, collected, no_merge)
        if export is not None:
            export[os.path.basename(path)] = collected
        print('%-16s edits=%-4d merged=%-4d deleted_blocks=%-4d moved=%-4d dead=%-3d bytes %d -> %d' % (
            os.path.basename(path), applied, stats['merged_groups'], stats['deleted_blocks'],
            stats['moved_declarations'], stats['dead_declarations'],
            len(open(path, 'rb').read()), len(out.encode('utf-8'))))
        for reason, count in skipped.most_common():
            print('  skipped: %-52s %d' % (reason, count))
        if args.write:
            data = out.encode('utf-8')
            assert b'\r\n' not in data
            with open(path, 'wb') as handle:
                handle.write(data)
            print('  wrote %s' % path)
    if export is not None:
        with open(args.export_blockers, 'w', encoding='utf-8') as handle:
            json.dump(export, handle, ensure_ascii=False)
        print('wrote %s (%d groups)' % (args.export_blockers, sum(len(v) for v in export.values())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
