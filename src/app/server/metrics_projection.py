"""Bounded, side-effect-free projection for public metric payloads."""

from __future__ import annotations

import math


MAX_METRIC_ITEMS = 256
MAX_METRIC_KEY_LENGTH = 256
MAX_METRIC_VALUE_DEPTH = 4
MAX_METRIC_VALUE_ITEMS = 256
MAX_METRIC_VALUE_TEXT = 4096


def _safe_metric_value(value, depth=0):
    if depth > MAX_METRIC_VALUE_DEPTH:
        return "[TRUNCATED]"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value[:MAX_METRIC_VALUE_TEXT]
    if isinstance(value, int):
        return max(-(10**12), min(10**12, value))
    if isinstance(value, float):
        return value if math.isfinite(value) and abs(value) <= 10**12 else 0.0
    if isinstance(value, dict):
        result = {}
        try:
            iterator = iter(value.items())
        except Exception:
            return result
        for _ in range(MAX_METRIC_VALUE_ITEMS):
            try:
                key, nested = next(iterator)
            except StopIteration:
                break
            except Exception:
                break
            if isinstance(key, str) and 0 < len(key) <= MAX_METRIC_KEY_LENGTH:
                result[key] = _safe_metric_value(nested, depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        result = []
        try:
            iterator = iter(value)
        except Exception:
            return result
        for _ in range(MAX_METRIC_VALUE_ITEMS):
            try:
                result.append(_safe_metric_value(next(iterator), depth + 1))
            except StopIteration:
                break
            except Exception:
                break
        return result
    return "[UNAVAILABLE]"


def project_metrics(source):
    """Copy a bounded, JSON-safe metric mapping for public responses."""
    if not isinstance(source, dict):
        return {}
    result = {}
    try:
        iterator = iter(source.items())
    except Exception:
        return result
    for _ in range(MAX_METRIC_ITEMS):
        try:
            key, value = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if isinstance(key, str) and 0 < len(key) <= MAX_METRIC_KEY_LENGTH:
            result[key] = _safe_metric_value(value)
    return result


__all__ = ["project_metrics"]
