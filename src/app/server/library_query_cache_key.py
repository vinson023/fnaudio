"""Pure, bounded normalization for music-library query cache keys."""

from __future__ import annotations

import math
import os


MAX_CACHE_KEY_TEXT = 4096
MAX_CACHE_KEY_VALUES = 32
MAX_CACHE_KEY_NUMBER = 10**12
MAX_DATABASE_IDENTITY_VALUES = 8
MAX_DATABASE_IDENTITY_NUMBER = 2**64 - 1


def normalize_database_path(value):
    if not isinstance(value, str):
        return None
    if not value or len(value) > MAX_CACHE_KEY_TEXT:
        return None
    return os.path.abspath(value)


def normalize_namespace(value):
    if not isinstance(value, str) or not value or len(value) > MAX_CACHE_KEY_TEXT:
        return None
    return value


def normalize_values(values):
    if values is None:
        return None
    if isinstance(values, str):
        values = (values,)
    try:
        iterator = iter(values)
    except TypeError:
        return None
    except Exception:
        return None
    normalized = []
    try:
        for _ in range(MAX_CACHE_KEY_VALUES):
            try:
                value = next(iterator)
            except StopIteration:
                break
            except Exception:
                return None
            if isinstance(value, str):
                if len(value) > MAX_CACHE_KEY_TEXT:
                    return None
                normalized.append(value)
            elif value is None or isinstance(value, bool):
                normalized.append(value)
            elif isinstance(value, int):
                if abs(value) > MAX_CACHE_KEY_NUMBER:
                    return None
                normalized.append(value)
            elif isinstance(value, float) and math.isfinite(value):
                if abs(value) > MAX_CACHE_KEY_NUMBER:
                    return None
                normalized.append(value)
            elif isinstance(value, float):
                return None
            else:
                return None
        # A truncated sequence is not a cache key: two queries that only
        # differ after the limit must never share a stored result. Probe once
        # so arbitrary or infinite iterables remain bounded at 33 reads.
        try:
            next(iterator)
        except StopIteration:
            pass
        except Exception:
            return None
        else:
            return None
    except Exception:
        return None
    return tuple(normalized)


def normalize_database_identity(value):
    """Normalize an optional filesystem identity without widening cache keys.

    Callers that serve a replaceable SQLite file can attach its current stat
    fingerprint.  The base cache remains useful for non-file-backed callers,
    so ``None`` deliberately means "no additional identity".
    """
    if value is None:
        return None
    if not isinstance(value, (tuple, list)) or not value or len(value) > MAX_DATABASE_IDENTITY_VALUES:
        return None
    normalized = []
    for part in value:
        if isinstance(part, bool) or not isinstance(part, int) or abs(part) > MAX_DATABASE_IDENTITY_NUMBER:
            return None
        normalized.append(part)
    return tuple(normalized)


def build_cache_key(database_path, namespace, values, database_identity=None):
    database = normalize_database_path(database_path)
    cache_namespace = normalize_namespace(namespace)
    if database is None or cache_namespace is None:
        return None
    normalized = normalize_values(values)
    if normalized is None:
        return None
    identity = normalize_database_identity(database_identity)
    if database_identity is not None and identity is None:
        return None
    # Keep the optional file identity structurally separate from query
    # parameters. Flat concatenation let a non-identity request manufacture
    # the same tuple by starting its values with the marker and identity.
    return (database, cache_namespace, normalized if identity is None else ("database_identity", identity, normalized))


__all__ = [
    "MAX_CACHE_KEY_TEXT",
    "MAX_CACHE_KEY_VALUES",
    "MAX_CACHE_KEY_NUMBER",
    "MAX_DATABASE_IDENTITY_VALUES",
    "MAX_DATABASE_IDENTITY_NUMBER",
    "build_cache_key",
    "normalize_database_identity",
    "normalize_database_path",
    "normalize_namespace",
    "normalize_values",
]
