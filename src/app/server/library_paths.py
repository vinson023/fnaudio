"""Pure music-library root/path rules shared by scanning and HTTP settings."""
from __future__ import annotations

import os
import re
import time


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


# --- Remote mounts ----------------------------------------------------------
# fnOS keeps mounted shares outside the user home: the platform's own 远程挂载
# feature parks them in a system directory beside @appdata rather than inside
# 我的文件, and a share mounted by hand through /etc/fstab can land anywhere at
# all.  Walking 我的文件 therefore never reached a mounted library, so a share
# that the fnOS file manager displayed was simply missing from the music
# directory picker.  The mount table is the only place that knows where a share
# really is, so it is read directly instead of guessing a path convention that
# differs per fnOS release and per mount type.
REMOTE_FILESYSTEM_TYPES = frozenset({
    "9p", "afs", "ceph", "cifs", "davfs", "davfs2", "glusterfs",
    "nfs", "nfs4", "smb3", "smbfs", "trim_ftp", "trim_nfs", "webdav",
})
# ``fuse.<backend>`` covers rclone (cloud drives), sshfs, smbnetfs and the
# davfs/curlftpfs helpers.  These backends are local-only FUSE filesystems that
# never hold a share, so they stay hidden even though they share the prefix.
LOCAL_FUSE_BACKENDS = frozenset({"fuseblk", "gvfs", "gvfsd-fuse", "lxcfs", "portal", "snapfuse"})
# Nothing under these trees is ever a share a user would pick as a library.
REMOTE_MOUNT_SKIP_PREFIXES = ("/proc", "/sys", "/dev")
MAX_REMOTE_MOUNTS = 32
MOUNT_TABLE_PATH = "/proc/mounts"
# ``is_allowed_library_path`` runs once per directory entry while browsing, so
# the table is read once per window instead of once per entry.  A share that
# appears while a listing is open shows up on the next refresh.
REMOTE_MOUNT_CACHE_SECONDS = 2.0
_REMOTE_MOUNT_CACHE = {"read_at": None, "paths": []}


def _decode_mount_field(value):
    """Undo the octal escapes ``/proc/mounts`` uses for space, tab and newline."""
    if "\\" not in value:
        return value
    decoded = []
    index = 0
    length = len(value)
    while index < length:
        char = value[index]
        if char == "\\" and index + 3 < length:
            digits = value[index + 1:index + 4]
            if all(digit in "01234567" for digit in digits):
                decoded.append(chr(int(digits, 8)))
                index += 4
                continue
        decoded.append(char)
        index += 1
    return "".join(decoded)


def _looks_like_network_source(source):
    """True for ``//host/share`` and ``host:/export`` style mount sources."""
    if source.startswith("//"):
        return True
    return ":" in source and not source.startswith("/")


def is_remote_filesystem(fstype, source=""):
    """True when a mount is backed by another machine or a network protocol."""
    if not isinstance(fstype, str):
        return False
    name = fstype.strip().lower()
    if name in REMOTE_FILESYSTEM_TYPES:
        return True
    if name.startswith("fuse."):
        return name[5:] not in LOCAL_FUSE_BACKENDS
    return _looks_like_network_source(source if isinstance(source, str) else "")


def remote_mount_paths(mount_table=None):
    """Return the mount points of remote shares, innermost duplicates dropped.

    ``mount_table`` accepts the text of a mount table so the parser can be
    tested without a real share; the default reads this process's table.
    """
    if mount_table is None:
        try:
            with open(MOUNT_TABLE_PATH, "r", encoding="utf-8", errors="replace") as handle:
                mount_table = handle.read(1 << 20)
        except OSError:
            return []
    if not isinstance(mount_table, str):
        return []
    paths = []
    seen = set()
    for line in mount_table.splitlines():
        fields = line.split(" ")
        if len(fields) < 3:
            continue
        source, mountpoint, fstype = (_decode_mount_field(field) for field in fields[:3])
        if not mountpoint.startswith("/") or mountpoint == "/":
            continue
        if any(mountpoint == prefix or mountpoint.startswith(prefix + "/") for prefix in REMOTE_MOUNT_SKIP_PREFIXES):
            continue
        if not is_remote_filesystem(fstype, source):
            continue
        normalized = mountpoint.rstrip("/") or "/"
        if normalized in seen:
            continue
        seen.add(normalized)
        paths.append(normalized)
    # A share mounted inside another share is already reachable by walking the
    # outer one; offering both would list the same files twice.
    paths = [path for path in paths if not any(path != other and path.startswith(other + "/") for other in paths)]
    paths.sort()
    return paths[:MAX_REMOTE_MOUNTS]


def reset_remote_mount_cache():
    _REMOTE_MOUNT_CACHE["read_at"] = None
    _REMOTE_MOUNT_CACHE["paths"] = []


def cached_remote_mount_paths():
    now = time.monotonic()
    read_at = _REMOTE_MOUNT_CACHE["read_at"]
    if read_at is not None and now - read_at < REMOTE_MOUNT_CACHE_SECONDS:
        return _REMOTE_MOUNT_CACHE["paths"]
    paths = remote_mount_paths()
    _REMOTE_MOUNT_CACHE["read_at"] = now
    _REMOTE_MOUNT_CACHE["paths"] = paths
    return paths


def is_allowed_library_path(path):
    value = bounded_library_path_text(path)
    if not value:
        return False
    if os.name == "nt":
        return True
    root = os.path.realpath(os.path.abspath(os.path.expanduser(value)))
    if re.match(r"^/vol\d+(/|$)", root):
        return True
    if any(root == prefix or root.startswith(prefix + os.sep) for prefix in ALLOWED_LIBRARY_PREFIXES):
        return True
    # A mounted share is storage the user deliberately attached to this host,
    # so it is library material wherever the mount point happens to live.
    for mount in cached_remote_mount_paths():
        if root == mount or root.startswith(mount + os.sep):
            return True
    return False


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
    if not paths and config.get("library_path") == "" and config.get("library_paths") == []:
        return []
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


# --- Server-side directory browsing -----------------------------------------
# The fnOS host picker (pickUserFile) only exists inside the fnOS App/desktop
# WebView.  The Android client and any standalone browser have no host, so the
# settings pane falls back to this listing: it walks the same allowed roots the
# scanner may index and never exposes file contents, only directory names.

MAX_BROWSE_ENTRIES = 200
MAX_BROWSE_SCAN = 2000
# fnOS mounts a data volume as /vol1 (older builds: /volume1), and keeps each
# user's storage in a numeric directory at the volume root: /vol1/1000 for uid
# 1000, or /vol1/1000-0-ab026773 when the same uid owns a second space.
VOLUME_ROOT_PATTERN = re.compile(r"^/vol(?:ume)?\d+$")
USER_HOME_PATTERN = re.compile(r"^\d+(?:-\d+-[0-9a-z]+)?$")
# fnOS keeps platform state in @-prefixed directories (@appcenter, @appconf,
# @appdata, @apphome, @appmeta, @appshare, @apptemp, @sysappmeta...) and every
# ext4 volume root carries lost+found.  They never hold a music library and the
# platform's own file manager hides them too.
BROWSE_HIDDEN_NAMES = frozenset({"lost+found"})
BROWSE_HIDDEN_PREFIXES = (".", "@")
# Extra storage that is not under a user home.  Only offered when it actually
# holds a visible directory, so an empty /mnt does not become a dead end.
BROWSE_EXTRA_PREFIXES = ("/mnt", "/var/apps/fnaudio/share")


def _browse_entry_hidden(name):
    if not name or name in BROWSE_HIDDEN_NAMES:
        return True
    return name.startswith(BROWSE_HIDDEN_PREFIXES)


def _volume_root_candidates():
    if os.name == "nt":
        return []
    candidates = []
    try:
        with os.scandir("/") as iterator:
            for entry in iterator:
                try:
                    if entry.is_dir(follow_symlinks=False) and VOLUME_ROOT_PATTERN.match("/" + entry.name):
                        candidates.append("/" + entry.name)
                except OSError:
                    continue
    except OSError:
        pass
    candidates.sort()
    return candidates


def _user_home_roots(volumes):
    """Return each user's storage directory, the platform's "我的文件" node.

    The fnOS file picker opens at the caller's home (/vol1/1000) and never shows
    the volume root, which is where the platform keeps @appdata, docker, thumb
    and friends.  Starting at the home is what makes this picker look like the
    one on the desktop instead of a dump of system directories.
    """
    homes = []
    for volume in volumes:
        try:
            with os.scandir(volume) as iterator:
                for entry in iterator:
                    name = entry.name
                    if not USER_HOME_PATTERN.match(name):
                        continue
                    try:
                        if not entry.is_dir():
                            continue
                    except OSError:
                        continue
                    real = os.path.realpath(os.path.join(volume, name))
                    if is_allowed_library_path(real):
                        homes.append(real)
        except OSError:
            continue
    homes.sort()
    return homes


def _has_visible_child_directory(path):
    try:
        with os.scandir(path) as iterator:
            for entry in iterator:
                if _browse_entry_hidden(entry.name):
                    continue
                try:
                    if entry.is_dir():
                        return True
                except OSError:
                    continue
    except OSError:
        return False
    return False


def _dedupe_roots(entries):
    roots = []
    seen = set()
    for path in entries:
        try:
            if not os.path.isdir(path):
                continue
            real = os.path.realpath(path)
        except OSError:
            continue
        if real in seen or not is_allowed_library_path(real):
            continue
        seen.add(real)
        roots.append(real)
    return roots


def _unique_root_name(roots, name, path):
    """Return a label no other root already uses.

    Two shares are routinely mounted under the same folder name (``music`` on
    two different servers), and a picker listing the same word twice gives the
    user no way to tell them apart.
    """
    if all(entry["name"] != name for entry in roots):
        return name
    parent = os.path.basename(os.path.dirname(path.rstrip(os.sep))) or path
    candidate = "%s (%s)" % (name, parent)
    if all(entry["name"] != candidate for entry in roots):
        return candidate
    return "%s (%s)" % (name, path)


def library_browse_roots():
    """Return the directories a phone or browser may start browsing from.

    Mirrors the desktop picker: the user's own storage is the first and usually
    only screen, extra mounts appear only when they hold something, and the bare
    volume roots are a last resort so a NAS with no detected home is never left
    with an empty picker.

    Remote shares are appended last because they are not reachable by walking
    我的文件: fnOS mounts them outside the user home, so without this they were
    invisible here even though the platform file manager listed them.

    A home with no visible directory is dropped as long as another home can be
    offered instead: fnOS gives every volume its own user space
    (/vol02/1000-0-ab026773), which is empty on a fresh install, and an empty
    node is pure noise next to 我的文件.  When *every* home is empty they are all
    kept, because falling back to the volume root would put @appdata, docker and
    thumb back on the first screen -- the very bug this picker exists to avoid.
    """
    volumes = _dedupe_roots(_volume_root_candidates())
    homes = _dedupe_roots(_user_home_roots(volumes))
    filled = [home for home in homes if _has_visible_child_directory(home)]
    if filled:
        homes = filled
    roots = []
    if homes:
        single = len(homes) == 1
        for home in homes:
            if single:
                name = "我的文件"
            else:
                base = os.path.basename(home.rstrip(os.sep)) or home
                name = "我的文件 (%s)" % base
            roots.append({"name": name, "path": home})
    else:
        for volume in volumes:
            roots.append({"name": os.path.basename(volume.rstrip(os.sep)) or volume, "path": volume})
    for prefix in BROWSE_EXTRA_PREFIXES:
        if not os.path.isdir(prefix) or not _has_visible_child_directory(prefix):
            continue
        for extra in _dedupe_roots([prefix]):
            if all(entry["path"] != extra for entry in roots):
                roots.append({"name": os.path.basename(extra.rstrip(os.sep)) or extra, "path": extra})
    for mount in cached_remote_mount_paths():
        # A share that already sits inside an offered root is reachable by
        # walking down to it, so promoting it again would only duplicate the
        # same files under a second name.
        if any(mount == entry["path"] or mount.startswith(entry["path"].rstrip(os.sep) + os.sep) for entry in roots):
            continue
        for extra in _dedupe_roots([mount]):
            if all(entry["path"] != extra for entry in roots):
                base = os.path.basename(extra.rstrip(os.sep)) or extra
                roots.append({"name": _unique_root_name(roots, base, extra), "path": extra})
    return roots


def _browsable_directory(path):
    try:
        return os.path.isdir(path) and is_allowed_library_path(os.path.realpath(path))
    except OSError:
        return False


def list_library_directories(path=""):
    """List child directories under one allowed root.

    Raises ValueError with a user-facing message for anything the picker must
    refuse: paths outside the allowed prefixes, missing directories, symlinks
    that resolve outside the allowed prefixes, and unreadable directories.
    """
    text = bounded_library_path_text(path)
    roots = library_browse_roots()
    if not text:
        return {"path": "", "parent": "", "entries": [], "roots": roots, "truncated": False}
    canonical = canonical_library_path(text)
    if not is_allowed_library_path(canonical):
        raise ValueError("这个目录不在允许的音乐目录范围内")
    if not os.path.isdir(canonical):
        raise ValueError("目录不存在或无法访问")
    real = os.path.realpath(canonical)
    if not is_allowed_library_path(real):
        raise ValueError("这个目录不在允许的音乐目录范围内")
    found = []
    scanned = 0
    try:
        with os.scandir(real) as iterator:
            for entry in iterator:
                if scanned >= MAX_BROWSE_SCAN:
                    break
                scanned += 1
                name = entry.name
                if _browse_entry_hidden(name):
                    continue
                try:
                    if not entry.is_dir():
                        continue
                except OSError:
                    continue
                child = os.path.join(real, name)
                if not _browsable_directory(child):
                    continue
                found.append({"name": name, "path": child})
    except OSError as error:
        raise ValueError("无法读取这个目录：%s" % (getattr(error, "strerror", "") or "权限不足"))
    found.sort(key=lambda item: item["name"].casefold())
    entries = found[:MAX_BROWSE_ENTRIES]
    parent = os.path.dirname(real.rstrip(os.sep))
    # A browse root has no parent inside the picker.  Walking up from /vol1/1000
    # would land on /vol1 and show @appdata, docker, thumb and the rest, which is
    # exactly what the desktop picker never does.
    root_paths = {entry["path"] for entry in roots}
    parent_path = (
        parent
        if parent and parent != real and real not in root_paths and is_allowed_library_path(parent)
        else ""
    )
    return {
        "path": real,
        "parent": parent_path,
        "entries": entries,
        "roots": roots,
        "truncated": len(found) > len(entries),
    }
