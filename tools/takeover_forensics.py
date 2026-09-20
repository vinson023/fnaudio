"""Answer the first question of a takeover: what has changed since the last gate?

A round writes sources, refreshes SOURCE_MANIFEST.sha256, runs the offline gate,
then records itself in the root documents. When a round is interrupted between
those steps, the documents describe a state the tree may no longer be in, so the
takeover rule is to compare the manifest with the working tree instead of
trusting the prose: every covered file that is newer than the manifest, every
covered file whose bytes no longer match, and every covered file the manifest
never listed counts as unverified. Each answer carries the test files named
after its module so the next step is to run those, not to guess.

Exit status is 1 when anything is stale or unlisted, 0 otherwise; drift alone is
reported but not failed, because the round order deliberately refreshes the
manifest after the sources and a re-written file can be byte-identical.
"""

import argparse
import hashlib
import json
import os


MANIFEST_NAME = "SOURCE_MANIFEST.sha256"
COVERED_DIRECTORIES = ("src", "android-client")
TESTS_DIRECTORY = os.path.join("src", "tests")
SUGGESTED_TEST_LIMIT = 12
EXCLUDED_SEGMENTS = frozenset((".gradle", ".media3-inspect", ".idea", "build", "__pycache__"))
EXCLUDED_NAMES = frozenset(("local.properties",))
EXCLUDED_SUFFIXES = frozenset((".apk", ".aab", ".aar", ".class", ".fpk", ".pyc"))
HASH_SEPARATOR = "  "
READ_CHUNK = 1024 * 1024


def relative_path(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(READ_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().upper()


def listed_entries(manifest_path):
    """Parse HASH<two spaces>relative/path lines, the shape the writer emits."""
    entries = {}
    with open(manifest_path, encoding="utf-8") as handle:
        for number, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            digest, separator, relative = line.partition(HASH_SEPARATOR)
            if not separator or not relative or not digest:
                raise ValueError("manifest line %d is not HASH  PATH" % number)
            entries[relative.strip()] = digest.strip().upper()
    return entries


def worktree_files(root):
    """List the files the manifest is supposed to cover, using its own rules."""
    found = []
    for directory in COVERED_DIRECTORIES:
        base = os.path.join(root, directory)
        if not os.path.isdir(base):
            continue
        for current, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(name for name in dirnames if name not in EXCLUDED_SEGMENTS)
            for name in filenames:
                if name in EXCLUDED_NAMES:
                    continue
                if os.path.splitext(name)[1].lower() in EXCLUDED_SUFFIXES:
                    continue
                path = os.path.join(current, name)
                if os.path.isfile(path):
                    found.append(relative_path(root, path))
    return sorted(found)


def suggest_tests(root, relative, limit=SUGGESTED_TEST_LIMIT):
    """Return the test files named after the module so the next step is to run
    those instead of the whole suite. An exact `test_<module>` answer comes
    first, a `test_<module>_...` family is the fallback, and the report carries
    the real total so a truncated family cannot be mistaken for the whole one.
    """
    stem = os.path.splitext(os.path.basename(relative))[0].lower()
    folder = os.path.join(root, TESTS_DIRECTORY)
    if not stem or not os.path.isdir(folder):
        return []
    exact = []
    family = []
    for name in sorted(os.listdir(folder)):
        if not name.startswith("test_"):
            continue
        if not (name.endswith(".py") or name.endswith(".js")):
            continue
        if stem not in name.lower():
            continue
        bucket = exact if name.lower().startswith("test_" + stem + ".") else family
        bucket.append(relative_path(root, os.path.join(folder, name)))
    return exact + family[:max(0, limit - len(exact))]


def inspect_repo(root, manifest_path=None, full=False):
    root = os.path.abspath(root)
    manifest_path = manifest_path or os.path.join(root, MANIFEST_NAME)
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(manifest_path)
    listed = listed_entries(manifest_path)
    manifest_mtime = os.stat(manifest_path).st_mtime
    drift = []
    stale = []
    for relative in sorted(listed):
        path = os.path.join(root, *relative.split("/"))
        if not os.path.isfile(path):
            stale.append({"path": relative, "reason": "listed but missing from the tree"})
            continue
        newer = os.stat(path).st_mtime > manifest_mtime
        if not (newer or full):
            continue
        if sha256_of(path) != listed[relative]:
            stale.append({"path": relative, "reason": "content differs from the manifest"})
        elif newer:
            drift.append({"path": relative, "reason": "newer than the manifest, bytes match"})
    unlisted = sorted(set(worktree_files(root)) - set(listed))
    unverified = sorted({item["path"] for item in drift} | {item["path"] for item in stale} | set(unlisted))
    return {
        "manifest": relative_path(root, manifest_path),
        "listed": len(listed),
        "drift": drift,
        "stale": stale,
        "unlisted": unlisted,
        "unverified": unverified,
        "suggested_tests": {path: suggest_tests(root, path) for path in unverified},
        "suggested_total": {path: len(suggest_tests(root, path, limit=1000000)) for path in unverified},
    }


def format_report(report):
    lines = [
        "manifest %s lists %d files" % (report["manifest"], report["listed"]),
        "drift (newer than the manifest, bytes match): %d" % len(report["drift"]),
        "stale (content differs or missing): %d" % len(report["stale"]),
        "unlisted (covered but never hashed): %d" % len(report["unlisted"]),
    ]
    for group in ("stale", "unlisted", "drift"):
        for item in report[group]:
            path = item if isinstance(item, str) else item["path"]
            reason = "" if isinstance(item, str) else " <- " + item["reason"]
            lines.append("  " + group + ": " + path + reason)
    for path, tests in sorted(report["suggested_tests"].items()):
        total = report["suggested_total"].get(path, len(tests))
        tail = "" if total == len(tests) else " (+%d more)" % (total - len(tests))
        lines.append("  run first: " + path + " -> " + (", ".join(tests) if tests else "no name match") + tail)
    return lines


def main(argv=None):
    default_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=default_root, help="project root holding the manifest")
    parser.add_argument("--manifest", default=None, help="override the manifest path")
    parser.add_argument("--full", action="store_true", help="hash every listed file, not only the drifted ones")
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit the report as one JSON object")
    parser.add_argument("--quiet", action="store_true", help="summary counts only, no per-file lines")
    args = parser.parse_args(argv)
    report = inspect_repo(args.repo_root, args.manifest, full=args.full)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    elif args.quiet:
        print("listed=%d drift=%d stale=%d unlisted=%d" % (
            report["listed"], len(report["drift"]), len(report["stale"]), len(report["unlisted"])))
    else:
        for line in format_report(report):
            print(line)
    return 1 if (report["stale"] or report["unlisted"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
