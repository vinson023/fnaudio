"""Bounded scan-error state kept safe for status and diagnostics output."""

from __future__ import annotations

MAX_SCAN_ERRORS = 20
MAX_SCAN_ERROR_TEXT = 512


def _text(value):
    return value[:MAX_SCAN_ERROR_TEXT] if isinstance(value, str) else ""


def scan_error_text(message):
    return _text(message)


def append_scan_error(errors, path, message):
    """Append a bounded public error record and retain only the newest rows."""
    target = errors if isinstance(errors, list) else []
    target.append({"path": _text(path), "message": _text(message)})
    if len(target) > MAX_SCAN_ERRORS:
        del target[:-MAX_SCAN_ERRORS]
    return target


def snapshot_scan_errors(errors):
    """Return a bounded copy without trusting the source iterable."""
    if not isinstance(errors, (list, tuple)):
        return []
    result = []
    try:
        iterator = iter(errors)
        for _ in range(MAX_SCAN_ERRORS):
            try:
                item = next(iterator)
            except StopIteration:
                break
            except Exception:
                break
            if isinstance(item, dict):
                try:
                    result.append({"path": _text(item.get("path")), "message": _text(item.get("message"))})
                except Exception:
                    continue
    except Exception:
        return result
    return result


__all__ = ["MAX_SCAN_ERRORS", "MAX_SCAN_ERROR_TEXT", "append_scan_error", "scan_error_text", "snapshot_scan_errors"]
