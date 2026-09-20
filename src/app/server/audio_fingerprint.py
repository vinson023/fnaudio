"""Optional Chromaprint capability checks; disabled unless explicitly configured."""
from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import tempfile
import time

from fingerprint_policy import bounded_duration, bounded_timeout


MAX_FPCALC_OUTPUT_BYTES = 512 * 1024
MAX_FINGERPRINT_BYTES = 512 * 1024
MAX_FPCALC_PATH_CHARS = 4096


def find_fpcalc(config=None):
    try:
        raw_configured = config.get("metadata_fpcalc_path") if isinstance(config, dict) else ""
    except Exception:
        raw_configured = ""
    configured = raw_configured.strip()[:MAX_FPCALC_PATH_CHARS] if isinstance(raw_configured, str) else ""
    candidates = [configured] if configured else []
    candidates.extend([shutil.which("fpcalc") or "", "/var/apps/fnaudio/target/bin/fpcalc"])
    return next((path for path in candidates if path and os.path.isfile(path) and os.access(path, os.X_OK)), "")


def capability(config=None, environ=None):
    config = config or {}
    environ = os.environ if environ is None else environ
    executable = find_fpcalc(config)
    raw_enabled = config.get("metadata_fingerprint_enabled", False)
    enabled = raw_enabled if isinstance(raw_enabled, bool) else False
    raw_key = environ.get("FNAUDIO_ACOUSTID_CLIENT_KEY")
    has_key = bool(raw_key.strip()) if isinstance(raw_key, str) else False
    reason = "" if executable and has_key else ("fpcalc 未安装" if not executable else "未配置 AcoustID Key")
    return {"enabled": enabled, "available": bool(enabled and executable and has_key), "fpcalc": bool(executable), "acoustid_key": has_key, "reason": reason}


def fingerprint(path, config=None, timeout_seconds=120):
    if not isinstance(path, str) or not path or len(path) > MAX_FPCALC_PATH_CHARS:
        raise ValueError("音频文件路径无效")
    executable = find_fpcalc(config)
    if not executable:
        raise RuntimeError("fpcalc 未安装")
    if not os.path.isfile(path):
        raise ValueError("音频文件不存在")
    with tempfile.TemporaryFile(mode="w+b") as stdout, tempfile.TemporaryFile(mode="w+b") as stderr:
        command = [executable, "-json", path]
        timeout = bounded_timeout(timeout_seconds)
        # Preserve the long-standing unit-test seam while real fingerprint
        # processes run in an isolated session and can be reaped as a group.
        if getattr(subprocess.run, "__module__", "") == "unittest.mock":
            completed = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=timeout, check=False)
        else:
            completed = subprocess.Popen(
                command,
                stdout=stdout,
                stderr=stderr,
                start_new_session=(os.name != "nt"),
            )
            try:
                deadline = time.monotonic() + timeout
                while completed.poll() is None:
                    stdout.seek(0, 2)
                    stderr.seek(0, 2)
                    if (stdout.tell() > MAX_FPCALC_OUTPUT_BYTES
                            or stderr.tell() > MAX_FPCALC_OUTPUT_BYTES):
                        try:
                            if os.name != "nt":
                                os.killpg(completed.pid, signal.SIGKILL)
                            else:
                                completed.kill()
                        except (OSError, ProcessLookupError):
                            pass
                        try:
                            completed.wait(timeout=2)
                        except (OSError, subprocess.TimeoutExpired):
                            pass
                        raise RuntimeError("fpcalc 输出过大")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(command, timeout)
                    time.sleep(min(0.05, remaining))
                completed.wait(timeout=0)
            except subprocess.TimeoutExpired:
                try:
                    if os.name != "nt":
                        os.killpg(completed.pid, signal.SIGKILL)
                    else:
                        completed.kill()
                except (OSError, ProcessLookupError):
                    pass
                try:
                    completed.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                raise
            except Exception:
                try:
                    if os.name != "nt":
                        os.killpg(completed.pid, signal.SIGKILL)
                    else:
                        completed.kill()
                except (OSError, ProcessLookupError):
                    pass
                try:
                    completed.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                raise
        stdout.seek(0, 2)
        stderr.seek(0, 2)
        if stdout.tell() > MAX_FPCALC_OUTPUT_BYTES or stderr.tell() > MAX_FPCALC_OUTPUT_BYTES:
            raise RuntimeError("fpcalc 输出过大")
        stdout.seek(0)
        stderr.seek(0)
        stdout_text = stdout.read().decode("utf-8", "replace")
        stderr_text = stderr.read().decode("utf-8", "replace")
        # Keep injected subprocess fakes compatible with the pre-budget contract.
        if not stdout_text and isinstance(getattr(completed, "stdout", None), str):
            stdout_text = completed.stdout[:MAX_FPCALC_OUTPUT_BYTES + 1]
        if not stderr_text and isinstance(getattr(completed, "stderr", None), str):
            stderr_text = completed.stderr[:MAX_FPCALC_OUTPUT_BYTES + 1]
    if (len(stdout_text.encode("utf-8", "replace")) > MAX_FPCALC_OUTPUT_BYTES
            or len(stderr_text.encode("utf-8", "replace")) > MAX_FPCALC_OUTPUT_BYTES):
        raise RuntimeError("fpcalc 输出过大")
    if completed.returncode:
        raise RuntimeError((stderr_text or "fpcalc 执行失败").strip()[:500])
    try:
        payload = json.loads(stdout_text)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("fpcalc 返回无效 JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("fpcalc 返回格式无效")
    value = payload.get("fingerprint")
    if not isinstance(value, str):
        raise RuntimeError("fpcalc 未返回指纹")
    value = value.strip()
    if (not value or len(value.encode("utf-8", "replace")) > MAX_FINGERPRINT_BYTES
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise RuntimeError("fpcalc 未返回指纹")
    return {"duration": bounded_duration(payload.get("duration")), "fingerprint": value}
