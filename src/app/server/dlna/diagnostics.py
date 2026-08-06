from __future__ import annotations

from collections import deque
from threading import RLock
import time
from typing import Any, Deque, Dict


class DlnaDiagnostics:
    """Small in-memory trace for diagnosing MediaServer interoperability."""

    def __init__(self, limit: int = 200):
        self._entries: Deque[Dict[str, Any]] = deque(maxlen=max(1, int(limit)))
        self._lock = RLock()

    @staticmethod
    def _text(value: Any, limit: int = 300) -> str:
        return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]

    def record(self, event: str, **values: Any) -> None:
        entry: Dict[str, Any] = {"time": int(time.time()), "event": self._text(event, 80)}
        for key, value in values.items():
            if value is not None and value != "":
                entry[key] = self._text(value)
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
