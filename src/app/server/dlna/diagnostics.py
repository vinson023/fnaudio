from __future__ import annotations

from collections import deque
from threading import RLock
import time
from typing import Any, Deque, Dict


MAX_DIAGNOSTIC_ENTRIES = 1000


def _safe_limit(value: Any, default: int = 200) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(1, min(MAX_DIAGNOSTIC_ENTRIES, number))


class DlnaDiagnostics:
    """Small in-memory trace for diagnosing MediaServer interoperability."""

    def __init__(self, limit: int = 200):
        self._entries: Deque[Dict[str, Any]] = deque(maxlen=_safe_limit(limit))
        self._lock = RLock()

    @staticmethod
    def _text(value: Any, limit: int = 300) -> str:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            return ""
        try:
            text = str(value)
        except Exception:
            return ""
        return text.replace("\r", " ").replace("\n", " ").strip()[:limit]

    def record(self, event: str, **values: Any) -> None:
        entry: Dict[str, Any] = {"time": int(time.time()), "event": self._text(event, 80)}
        for key, value in values.items():
            if value is not None and value != "":
                projected = self._text(value)
                if projected:
                    entry[key] = projected
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            entries = list(self._entries)
        clients: Dict[str, int] = {}
        for entry in entries:
            client = entry.get("user_agent") or "Unknown client"
            clients[client] = clients.get(client, 0) + 1
        return {"limit": self._entries.maxlen, "count": len(entries), "clients": clients, "entries": list(reversed(entries))}


__all__ = ["DlnaDiagnostics"]
