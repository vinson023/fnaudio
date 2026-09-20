"""Pure, bounded projections for persisted user state."""

import json
import math
from typing import Any, Dict, Iterable

MAX_STATE_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_STATE_TEXT_BYTES = 4096
MAX_PLAYBACK_QUEUE_TRACKS = 50000
MAX_PLAYLISTS = 1000
MAX_PLAYLIST_TRACK_IDS = 10000
MAX_PLAYLIST_TRACK_IDS_TOTAL = 50000


def _bounded_state_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    try:
        value = value.strip()
        if len(value.encode("utf-8")) > MAX_STATE_TEXT_BYTES:
            return ""
    except Exception:
        return ""
    return value


def load_json_bounded(payload: Any) -> Any:
    if not isinstance(payload, str):
        return {}
    try:
        if len(payload.encode("utf-8")) > MAX_STATE_PAYLOAD_BYTES:
            return {}
        return json.loads(payload)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        return {}


def mapping_or_empty(value: Any) -> Dict[str, Any]:
    """Keep persisted object-shaped state object-shaped after JSON decode."""
    return value if isinstance(value, dict) else {}


def dump_json_bounded(payload: Any) -> str:
    """Serialize state with the same byte ceiling used during recovery."""
    try:
        return dump_json_bounded_strict(payload)
    except ValueError:
        return "{}"


def dump_json_bounded_strict(payload: Any) -> str:
    """Serialize state or raise instead of silently replacing it with ``{}``."""
    try:
        # Persist strict JSON so NaN/Infinity cannot leak into the SQLite
        # payload and break clients that use a standards-compliant parser.
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode("utf-8")) > MAX_STATE_PAYLOAD_BYTES:
            raise ValueError("state payload exceeds size limit")
        return encoded
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError) as exc:
        raise ValueError("state payload cannot be serialized") from exc
def strings(values: Iterable[Any], limit: int) -> list[str]:
    result, seen = [], set()
    try:
        iterator = iter(values)
    except Exception:
        return result
    while len(result) < limit:
        try:
            value = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        text = _bounded_state_text(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def playback_queue_ids(values: Any) -> list[str]:
    """Project persisted playback queue IDs without coercing arbitrary objects."""
    if not isinstance(values, list):
        return []
    result, seen = [], set()
    try:
        iterator = iter(values)
    except Exception:
        return result
    while len(result) < MAX_PLAYBACK_QUEUE_TRACKS:
        try:
            value = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        text = _bounded_state_text(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def playlists(payload: Any) -> list[Dict[str, Any]]:
    source = payload if isinstance(payload, list) else []
    result, seen = [], set()
    remaining_track_ids = MAX_PLAYLIST_TRACK_IDS_TOTAL
    try:
        iterator = iter(source)
    except Exception:
        return result
    while len(result) < MAX_PLAYLISTS:
        try:
            entry = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if not isinstance(entry, dict):
            continue
        try:
            playlist_id = _bounded_state_text(entry.get("id"))[:512]
            name = _bounded_state_text(entry.get("name"))[:160]
            track_ids = entry.get("trackIds")
        except Exception:
            continue
        if not playlist_id or not name or playlist_id in seen:
            continue
        seen.add(playlist_id)
        track_limit = min(MAX_PLAYLIST_TRACK_IDS, remaining_track_ids)
        projected_track_ids = strings(
            track_ids if isinstance(track_ids, list) else [], track_limit
        )
        remaining_track_ids -= len(projected_track_ids)
        result.append({"id": playlist_id, "name": name,
                       "trackIds": projected_track_ids})
    return result


def ui_preferences(payload: Any) -> Dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    try:
        raw_columns, raw_widths = source.get("track_columns"), source.get("track_column_widths")
    except Exception:
        raw_columns, raw_widths = {}, {}
    columns = raw_columns if isinstance(raw_columns, dict) else {}
    widths = raw_widths if isinstance(raw_widths, dict) else {}
    result: Dict[str, list[str]] = {}
    try:
        entries = columns.items()
    except Exception:
        entries = ()
    try:
        iterator = iter(entries)
    except Exception:
        iterator = iter(())
    while len(result) < 2000:
        try:
            scope, values = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        key = _bounded_state_text(scope)[:512]
        if key and isinstance(values, list):
            selected = strings(values, 16)
            if selected:
                result[key] = selected
    width_result: Dict[str, Dict[str, int]] = {}
    try:
        entries = widths.items()
    except Exception:
        entries = ()
    try:
        iterator = iter(entries)
    except Exception:
        iterator = iter(())
    while len(width_result) < 2000:
        try:
            scope, values = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        key = _bounded_state_text(scope)[:512]
        if not key or not isinstance(values, dict):
            continue
        selected = {}
        try:
            width_entries = values.items()
        except Exception:
            width_entries = ()
        try:
            width_iterator = iter(width_entries)
        except Exception:
            width_iterator = iter(())
        while len(selected) < 16:
            try:
                column, width = next(width_iterator)
            except StopIteration:
                break
            except Exception:
                break
            column_key = _bounded_state_text(column)[:64]
            if isinstance(width, bool):
                continue
            if isinstance(width, int):
                value = width
            elif isinstance(width, float):
                if not math.isfinite(width) or not width.is_integer():
                    continue
                value = int(width)
            elif isinstance(width, str):
                text = width.strip()
                if not text or not text.isascii() or not text.isdecimal():
                    continue
                try:
                    value = int(text)
                except (TypeError, ValueError, OverflowError):
                    continue
            else:
                continue
            if column_key and 64 <= value <= 900:
                selected[column_key] = value
        if selected:
            width_result[key] = selected
    return {"track_columns": result, "track_column_widths": width_result}


__all__ = ["MAX_PLAYBACK_QUEUE_TRACKS", "MAX_PLAYLISTS", "MAX_PLAYLIST_TRACK_IDS", "MAX_PLAYLIST_TRACK_IDS_TOTAL", "MAX_STATE_PAYLOAD_BYTES", "MAX_STATE_TEXT_BYTES", "dump_json_bounded", "dump_json_bounded_strict", "load_json_bounded", "mapping_or_empty", "playback_queue_ids", "playlists", "strings", "ui_preferences"]
