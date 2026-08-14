from __future__ import annotations

import threading
import time
from typing import Dict


class AudioOutputLease:
    """Serialize ownership of the physical ALSA playback endpoint."""

    def __init__(self):
        self._lock = threading.RLock()
        self._owner = ""
        self._device_id = ""
        self._acquired_at = 0.0

    def acquire(self, owner: str, device_id: str = "", replace: bool = False) -> Dict:
        owner = str(owner or "")
        with self._lock:
            if self._owner and self._owner != owner and not replace:
                return {"ok": False, **self.snapshot(), "message": "audio device is owned by %s" % self._owner}
            self._owner = owner
            self._device_id = str(device_id or "")
            self._acquired_at = time.time()
            return {"ok": True, **self.snapshot()}

    def release(self, owner: str) -> bool:
        with self._lock:
            if self._owner != str(owner or ""):
                return False
            self._owner = ""
            self._device_id = ""
            self._acquired_at = 0.0
            return True

    def owns(self, owner: str) -> bool:
        with self._lock:
            return self._owner == str(owner or "")

    def snapshot(self) -> Dict:
        with self._lock:
            return {"owner": self._owner, "device_id": self._device_id, "acquired_at": self._acquired_at}


AUDIO_OUTPUT_LEASE = AudioOutputLease()
