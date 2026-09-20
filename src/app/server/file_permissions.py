from __future__ import annotations

import json
import os
import stat
import tempfile
from typing import Any


PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
PUBLIC_FILE_MODE = 0o644
PUBLIC_DIRECTORY_MODE = 0o755


def secure_directory(path: str, mode: int = PRIVATE_DIRECTORY_MODE) -> str:
    target = _normalized_path(path, ".")
    if os.path.islink(target):
        raise OSError("refusing to secure a symlink directory")
    os.makedirs(target, exist_ok=True)
    if os.path.islink(target) or not os.path.isdir(target):
        raise OSError("secure directory is not a directory")
    _chmod(target, mode)
    return target


def secure_directory_on_drift(path: str, mode: int = PRIVATE_DIRECTORY_MODE) -> str:
    """Harden a directory only when one lstat says it needs it.

    Same contract as `secure_directory` - refuse a symlink, create what is missing, keep the
    mode private - but the common case costs one lstat instead of six syscalls, so a caller
    that touches a directory on every log line stops paying for a check that almost always
    passes. Anything this fast path cannot vouch for falls back to the full
    `secure_directory`, which keeps its symlink refusal and its creation behaviour.
    """
    target = _normalized_path(path, ".")
    try:
        info = os.lstat(target)
    except OSError:
        return secure_directory(target, mode)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        # A symlink or a plain file where a directory belongs is `secure_directory`'s
        # refusal, not this function's decision, so it stays that way.
        return secure_directory(target, mode)
    if stat.S_IMODE(info.st_mode) != mode:
        _chmod(target, mode)
    return target


def secure_file(path: str, mode: int = PRIVATE_FILE_MODE) -> bool:
    target = _normalized_path(path, "")
    if not target or not os.path.isfile(target) or os.path.islink(target):
        return False
    _chmod(target, mode)
    return True


def secure_file_on_drift(path: str, mode: int = PRIVATE_FILE_MODE) -> bool:
    """Harden an existing file only when one lstat says it needs it.

    Same contract as `secure_file` - a missing or symlinked path is not our business, and the
    mode ends up private - but the steady state costs one lstat rather than a `isfile` plus two
    `islink` probes plus a chmod. A file that was just created still gets hardened, because its
    mode comes from the umask and differs from what we require.
    """
    target = _normalized_path(path, "")
    if not target:
        return False
    try:
        info = os.lstat(target)
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return False
    if stat.S_IMODE(info.st_mode) != mode:
        _chmod(target, mode)
    return True


def secure_sqlite_files(path: str) -> None:
    """Keep a database and its sidecars private.

    Called on every read of a pooled connection, so each sidecar is probed once with
    lstat and only chmodded when its mode actually drifted. The refresh itself stays
    on every path: the frequency is the security invariant, and a reused handle only
    proves the pragmas, not that another process left the files private.
    """
    for suffix in ("", "-wal", "-shm"):
        secure_file_on_drift(path + suffix, PRIVATE_FILE_MODE)


def atomic_write_text(path: str, text: str, mode: int = PRIVATE_FILE_MODE) -> None:
    target = _normalized_path(path, None)
    if not target:
        raise TypeError("path must be text or PathLike")
    parent_mode = PRIVATE_DIRECTORY_MODE if mode == PRIVATE_FILE_MODE else PUBLIC_DIRECTORY_MODE
    parent = secure_directory(os.path.dirname(target), parent_mode)
    fd, temporary = tempfile.mkstemp(prefix=".fnaudio-write-", dir=parent)
    try:
        if os.name != "nt":
            os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            fd = -1
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        secure_file(target, mode)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            if os.path.exists(temporary):
                os.unlink(temporary)
        except OSError:
            pass


def atomic_write_json(path: str, payload: Any, mode: int = PRIVATE_FILE_MODE) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False), mode)


def preserve_owner_and_mode(source: str, replacement: str) -> None:
    source = _path_argument(source)
    replacement = _path_argument(replacement)
    if not source or not replacement:
        raise TypeError("paths must be text or PathLike")
    source_stat = os.stat(source, follow_symlinks=False)
    if not stat.S_ISREG(source_stat.st_mode):
        raise OSError("source is not a regular file")
    _chmod(replacement, stat.S_IMODE(source_stat.st_mode))
    if os.name != "nt" and hasattr(os, "chown") and getattr(os, "geteuid", lambda: 1)() == 0:
        os.chown(replacement, source_stat.st_uid, source_stat.st_gid, follow_symlinks=False)


def _chmod(path: str, mode: int) -> None:
    if os.name == "nt" or os.path.islink(path):
        return
    # SQLite creates and removes WAL/SHM sidecars independently.  A sidecar
    # can disappear after the existence check in secure_file(), which must not
    # turn a normal library or cover request into a server error.
    try:
        os.chmod(path, int(mode), follow_symlinks=False)
    except FileNotFoundError:
        return


def _normalized_path(path: str, fallback: str | None) -> str:
    """Normalize only text/PathLike paths without invoking arbitrary str()."""
    if isinstance(path, str):
        value = path
    elif isinstance(path, os.PathLike):
        try:
            value = os.fspath(path)
        except (OSError, TypeError, ValueError):
            value = ""
    else:
        value = ""
    if not isinstance(value, str):
        value = ""
    if not value.strip():
        value = fallback or ""
    return os.path.abspath(value) if value else ""


def _path_argument(path: str) -> str:
    """Validate a path argument while preserving its caller-visible form."""
    if isinstance(path, str):
        return path
    if isinstance(path, os.PathLike):
        try:
            value = os.fspath(path)
        except (OSError, TypeError, ValueError):
            return ""
        return value if isinstance(value, str) else ""
    return ""


__all__ = [
    "PRIVATE_DIRECTORY_MODE",
    "PRIVATE_FILE_MODE",
    "PUBLIC_DIRECTORY_MODE",
    "PUBLIC_FILE_MODE",
    "atomic_write_json",
    "atomic_write_text",
    "preserve_owner_and_mode",
    "secure_directory",
    "secure_directory_on_drift",
    "secure_file_on_drift",
    "secure_file",
    "secure_sqlite_files",
]
