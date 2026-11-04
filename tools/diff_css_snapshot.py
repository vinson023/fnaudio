"""Diff two computed-style snapshots produced by `tools/browser-e2e/css_snapshot.js`.

The snapshot harness keys every element by its index path from
`documentElement`, so removing DOM is indistinguishable from a style change
unless the two are told apart.  This script does that:

* a key present only in the baseline is a **removal** -- reported in full, and
  only accepted when it sits under `--allow-removed-prefix` (a DOM path such as
  `body:2>header:1>div:3`, i.e. the subtree that was deleted on purpose);
* a key present only in the run is a **new element** and is always reported;
* a key in both whose value changed is a **style change** and is always
  reported.

Usage:
    node css_snapshot.js before.json
    node css_snapshot.js after.json
    python tools/diff_css_snapshot.py before.json after.json \
        --allow-removed-prefix body:2>header:1>div:3

Exit code 0 means every surviving element resolved to identical computed
styles; anything else prints the offending paths.

Two sources of noise are worth knowing before reading a failure:

* Take the baseline from a WARM run.  The first capture after a cold fixture
  start lags the async settings panes and shows ~109 spurious diffs in three
  `w1440-light/settings-*` states.
* An open `<dialog>` resolves `margin:auto` to a centering offset, and whether
  the used value has been recomputed at capture time is not deterministic.  The
  border box stays identical, so a diff confined to the four margin properties
  of a `dialog` is harness noise, not a layout change.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    with path.open("rb") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("baseline", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument(
        "--allow-removed-prefix",
        action="append",
        default=[],
        help="DOM path prefix whose disappearance is expected (repeatable)",
    )
    args = parser.parse_args()

    base = load(args.baseline)
    after = load(args.after)
    states = sorted(set(base) | set(after))

    missing = [s for s in states if s not in after]
    extra = [s for s in states if s not in base]
    removed = added = changed = 0
    stray: list[str] = []

    for state in states:
        if state not in base or state not in after:
            continue
        old, new = base[state], after[state]
        for key in old:
            if key in new:
                continue
            removed += 1
            if not any(key.startswith(prefix) for prefix in args.allow_removed_prefix):
                stray.append(f"{state}  removed: {key}")
        for key in new:
            if key not in old:
                added += 1
                stray.append(f"{state}  new element: {key}")
            elif old[key] != new[key]:
                changed += 1
                stray.append(f"{state}  changed style: {key}")

    print(f"states compared     : {len(states) - len(missing) - len(extra)}")
    if missing:
        print(f"states only in base : {missing}")
    if extra:
        print(f"states only in after: {extra}")
    print(f"records removed     : {removed}")
    print(f"records added       : {added}")
    print(f"records changed     : {changed}")
    print()
    if stray:
        print(f"!! {len(stray)} difference(s) outside the allowed removals:")
        for line in stray[:80]:
            print("  ", line)
        if len(stray) > 80:
            print(f"   ... and {len(stray) - 80} more")
        return 1
    print("OK: every surviving element resolved to identical computed styles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
