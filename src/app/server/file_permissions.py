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
    target = os.path.abspath(str(path or "."))
    os.makedirs(target, exist_ok=True)
    _chmod(target, mode)
    return target


def secure_file(path: str, mode: int = PRIVATE_FILE_MODE) -> bool:
    target = os.path.abspath(str(path or ""))
    if not target or not os.path.isfile(target) or os.path.islink(target):
        return False
    _chmod(target, mode)
    return True


def secure_sqlite_files(path: str) -> None:
    for suffix in ("", "-wal", "-shm"):
        secure_file(path + suffix, PRIVATE_FILE_MODE)


def atomic_write_text(path: str, text: str, mode: int = PRIVATE_FILE_MODE) -> None:
    target = os.path.abspath(path)
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


__all__ = [
    "PRIVATE_DIRECTORY_MODE",
    "PRIVATE_FILE_MODE",
    "PUBLIC_DIRECTORY_MODE",
    "PUBLIC_FILE_MODE",
    "atomic_write_json",
    "atomic_write_text",
    "preserve_owner_and_mode",
    "secure_directory",
    "secure_file",
    "secure_sqlite_files",
]
