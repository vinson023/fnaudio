#!/usr/bin/env python3
"""Mirror the vendored fnOS ``trim-cli`` skill documentation into the repository.

The tool drop lives in ``tools/skill`` and stays untracked on purpose: it ships
roughly fifty megabytes of platform binaries.  Its markdown, however, is the
material later rounds actually read when they touch device behaviour, so this
script copies exactly that markdown into ``references/fnos-skill`` and can prove
afterwards that nothing drifted.

Layout is preserved byte for byte because the skill cross-links with relative
paths (``SKILL.md`` -> ``entries/*.md`` -> ``../reference/<module>.md``);
flattening the tree would silently break every one of those links.
"""

import argparse
import hashlib
import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SKILL_ROOT = os.path.join(REPO_ROOT, "tools", "skill")
DEFAULT_MIRROR_ROOT = os.path.join(REPO_ROOT, "references", "fnos-skill")

# Root-level documents that belong to the skill itself.
INCLUDED_FILES = ("SKILL.md", "manifest.json")
# Directories mirrored recursively.
INCLUDED_DIRS = ("entries", "reference")
# Never mirrored, wherever they appear: binaries and wrappers belong to the
# untracked tool drop, and copying them would drag megabytes into history.
EXCLUDED_DIRS = ("bin", "scripts")
# Text payloads only, so a future binary drop cannot be committed by accident.
ALLOWED_EXTENSIONS = (".md", ".json")


def to_posix(path):
    return path.replace(os.sep, "/")


def relative_paths(root):
    """Every path this tool owns inside ``root``, as sorted posix paths."""
    found = []
    for name in INCLUDED_FILES:
        if os.path.isfile(os.path.join(root, name)):
            found.append(name)
    for name in INCLUDED_DIRS:
        base = os.path.join(root, name)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
            for filename in filenames:
                if not filename.endswith(ALLOWED_EXTENSIONS):
                    continue
                relative = to_posix(os.path.relpath(os.path.join(dirpath, filename), root))
                if any(part in EXCLUDED_DIRS for part in relative.split("/")):
                    continue
                found.append(relative)
    return sorted(set(found))


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compare(skill_root, mirror_root):
    """Return the diff between the tool drop and the mirrored copy."""
    expected = relative_paths(skill_root)
    actual = relative_paths(mirror_root) if os.path.isdir(mirror_root) else []
    missing = []
    changed = []
    for relative in expected:
        target = os.path.join(mirror_root, *relative.split("/"))
        if not os.path.isfile(target):
            missing.append(relative)
        elif digest(target) != digest(os.path.join(skill_root, *relative.split("/"))):
            changed.append(relative)
    extra = [relative for relative in actual if relative not in expected]
    return {"source": expected, "missing": missing, "changed": changed, "extra": extra}


def prune_empty_dirs(mirror_root):
    for dirpath, dirnames, filenames in os.walk(mirror_root, topdown=False):
        if os.path.abspath(dirpath) == os.path.abspath(mirror_root):
            continue
        if not dirnames and not filenames:
            os.rmdir(dirpath)


def apply_diff(skill_root, mirror_root, result):
    """Copy what is new or stale and delete what the tool no longer ships."""
    for relative in result["missing"] + result["changed"]:
        source = os.path.join(skill_root, *relative.split("/"))
        target = os.path.join(mirror_root, *relative.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(source, target)
    for relative in result["extra"]:
        os.unlink(os.path.join(mirror_root, *relative.split("/")))
    if result["extra"]:
        prune_empty_dirs(mirror_root)
    return result


def format_report(result, written):
    lines = []
    lines.append("files=%d" % len(result["source"]))
    for key in ("missing", "changed", "extra"):
        label = key if not written else {"missing": "copied", "changed": "refreshed", "extra": "removed"}[key]
        lines.append("%s=%d%s" % (label, len(result[key]),
                                  "" if not result[key] else " " + ",".join(result[key])))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skill-root", default=DEFAULT_SKILL_ROOT)
    parser.add_argument("--mirror-root", default=DEFAULT_MIRROR_ROOT)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="refresh the mirrored copy")
    group.add_argument("--check", action="store_true", help="fail when the mirrored copy drifted")
    args = parser.parse_args(argv)

    skill_root = os.path.abspath(args.skill_root)
    mirror_root = os.path.abspath(args.mirror_root)
    if not os.path.isdir(skill_root):
        sys.stderr.write("skill root absent: %s\n" % skill_root)
        return 2

    result = compare(skill_root, mirror_root)
    if args.check:
        drift = len(result["missing"]) + len(result["changed"]) + len(result["extra"])
        print(format_report(result, written=False))
        if drift:
            sys.stderr.write("drift=%d\n" % drift)
            return 1
        return 0

    apply_diff(skill_root, mirror_root, result)
    after = compare(skill_root, mirror_root)
    print(format_report(result, written=True))
    residual = len(after["missing"]) + len(after["changed"]) + len(after["extra"])
    if residual:
        sys.stderr.write("residual=%d\n" % residual)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
