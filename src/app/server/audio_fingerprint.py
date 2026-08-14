"""Optional Chromaprint capability checks; disabled unless explicitly configured."""
from __future__ import annotations

import json
import os
import shutil
import subprocess


def find_fpcalc(config=None):
    configured = str((config or {}).get("metadata_fpcalc_path") or "").strip()
    candidates = [configured] if configured else []
    candidates.extend([shutil.which("fpcalc") or "", "/var/apps/fnaudio/target/bin/fpcalc"])
    return next((path for path in candidates if path and os.path.isfile(path) and os.access(path, os.X_OK)), "")


def capability(config=None, environ=None):
    config = config or {}
    environ = os.environ if environ is None else environ
    executable = find_fpcalc(config)
    enabled = bool(config.get("metadata_fingerprint_enabled", False))
    has_key = bool(str(environ.get("FNAUDIO_ACOUSTID_CLIENT_KEY") or "").strip())
    reason = "" if executable and has_key else ("fpcalc 未安装" if not executable else "未配置 AcoustID Key")
    return {"enabled": enabled, "available": bool(enabled and executable and has_key), "fpcalc": bool(executable), "acoustid_key": has_key, "reason": reason}


def fingerprint(path, config=None, timeout_seconds=120):
    executable = find_fpcalc(config)
    if not executable:
        raise RuntimeError("fpcalc 未安装")
    if not os.path.isfile(path):
        raise ValueError("音频文件不存在")
    completed = subprocess.run([executable, "-json", path], capture_output=True, text=True, timeout=max(1, min(int(timeout_seconds), 300)), check=False)
    if completed.returncode:
        raise RuntimeError((completed.stderr or "fpcalc 执行失败").strip()[:500])
    payload = json.loads(completed.stdout)
    value = str(payload.get("fingerprint") or "").strip()
    if not value:
        raise RuntimeError("fpcalc 未返回指纹")
    return {"duration": int(payload.get("duration") or 0), "fingerprint": value}
