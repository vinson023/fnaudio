"""Pure music-library root/path rules shared by scanning and HTTP settings."""
from __future__ import annotations

import os
import re


ALLOWED_LIBRARY_PREFIXES = ("/vol", "/volume", "/mnt", "/share", "/var/apps/fnaudio/share")
MAX_LIBRARY_PATHS = 64
MAX_LIBRARY_PATH_TEXT = 4096


def bounded_library_path_text(value):
    """Return bounded text for an already-typed library path value."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return text if len(text) <= MAX_LIBRARY_PATH_TEXT else ""


def _safe_path_text(value):
    if value is None:
        return ""
    if not isinstance(value, (str, bytes, int, float)):
        return ""
    try:
        text = str(value).strip()
        return text if len(text) <= MAX_LIBRARY_PATH_TEXT else ""
    except Exception:
        return ""


def is_allowed_library_path(path):
    value = bounded_library_path_text(path)
    if not value:
        return False
    if os.name == "nt":
        return True
    root = os.path.realpath(os.path.abspath(os.path.expanduser(value)))
    if re.match(r"^/vol\d+(/|$)", root):
        return True
    return any(root == prefix or root.startswith(prefix + os.sep) for prefix in ALLOWED_LIBRARY_PREFIXES)


def canonical_library_path(path):
    value = bounded_library_path_text(path)
    if not value:
        value = "."
    value = os.path.abspath(os.path.expanduser(value))
    # Windows may expand an 8.3 temporary path to its long form in realpath(),
    # which breaks the path identity stored in SQLite. Linux still resolves
    # symlinks here so configured roots cannot escape the allowed boundary.
    return value if os.name == "nt" else os.path.realpath(value)


def normalize_library_paths(config):
    if not isinstance(config, dict):
        return [canonical_library_path(".")]
    values = []
    raw_paths = config.get("library_paths")
    if isinstance(raw_paths, list):
        values.extend(raw_paths[:MAX_LIBRARY_PATHS * 4])
    raw = config.get("library_path", "")
    if isinstance(raw, str):
        values.extend(re.split(r"[\r\n;]+", raw)[:MAX_LIBRARY_PATHS * 4])
    paths = []
    seen = set()
    for value in values:
        if len(paths) >= MAX_LIBRARY_PATHS:
            break
        raw_value = _safe_path_text(value)
        if not raw_value:
            continue
        path = canonical_library_path(raw_value)
        if path in seen:
            continue
        seen.add(path)
        paths.append(path)
    fallback = _safe_path_text(config.get("library_path", ".")) or "."
    return paths or [canonical_library_path(fallback)]


def merge_library_paths(current_paths, extra_paths):
    """Merge configured roots using the same identity as scanning and SQLite."""
    paths = []
    seen = set()
    def bounded_values(values):
        try:
            iterator = iter(values or ())
        except Exception:
            return
        for _ in range(MAX_LIBRARY_PATHS):
            try:
                yield next(iterator)
            except StopIteration:
                return
            except Exception:
                return
    for value in bounded_values(current_paths):
        yield_value = value
        raw_value = _safe_path_text(yield_value)
        if not raw_value:
            continue
        path = canonical_library_path(raw_value)
        if path in seen:
            continue
        seen.add(path)
        paths.append(path)
        if len(paths) >= MAX_LIBRARY_PATHS:
            break
    if len(paths) < MAX_LIBRARY_PATHS:
        for value in bounded_values(extra_paths):
            raw_value = _safe_path_text(value)
            if not raw_value:
                continue
            path = canonical_library_path(raw_value)
            if path in seen:
                continue
            seen.add(path)
            paths.append(path)
            if len(paths) >= MAX_LIBRARY_PATHS:
                break
    return paths


def apply_library_paths(config, paths):
    if not isinstance(config, dict):
        return
    safe_paths = []
    try:
        iterator = iter(paths or ())
    except Exception:
        iterator = iter(())
    for _ in range(MAX_LIBRARY_PATHS):
        try:
            value = next(iterator)
        except (StopIteration, Exception):
            break
        value = bounded_library_path_text(value)
        if not value:
            continue
        safe_paths.append(value)
    config["library_path"] = "\n".join(safe_paths)
    config["library_paths"] = safe_paths


def display_library_path(config):
    return "\n".join(normalize_library_paths(config))


def library_root_labels(config):
    roots = normalize_library_paths(config)
    if len(roots) <= 1:
        return {}
    base_counts = {}
    for root in roots:
        base = os.path.basename(root.rstrip(os.sep)) or root.strip(os.sep).replace(os.sep, "-") or "音乐目录"
        base_counts[base] = base_counts.get(base, 0) + 1
    labels = {}
    for root in roots:
        base = os.path.basename(root.rstrip(os.sep)) or root.strip(os.sep).replace(os.sep, "-") or "音乐目录"
        if base_counts.get(base, 0) > 1:
            parent = os.path.basename(os.path.dirname(root.rstrip(os.sep))) or "目录"
            labels[os.path.abspath(root)] = "%s/%s" % (parent, base)
        else:
            labels[os.path.abspath(root)] = base
    return labels


def library_root_label(root, config):
    return library_root_labels(config or {}).get(os.path.abspath(root), "")


def relative_folder_for_path(path, root):
    try:
        rel = os.path.dirname(os.path.relpath(os.path.abspath(path), os.path.abspath(root)))
    except (OSError, ValueError):
        return ""
    parts = os.path.normpath(rel).split(os.sep)
    return "/".join(x for x in parts if x and x != ".")
