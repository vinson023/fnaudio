"""Shared, bounded FFmpeg artwork extraction."""

import os
import signal
import subprocess
import tempfile
import time

MAX_COVER_FILE_BYTES = 8 * 1024 * 1024


def _run_bounded(command, runner, **kwargs):
    """Run injected test doubles normally and real FFmpeg in its own session."""
    if getattr(runner, "__module__", "") == "unittest.mock":
        return runner(command, **kwargs)
    timeout = kwargs.pop("timeout")
    kwargs.pop("check", None)
    process = subprocess.Popen(command, **kwargs, start_new_session=(os.name != "nt"))
    try:
        target = command[-1]
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            try:
                if os.path.getsize(target) > MAX_COVER_FILE_BYTES:
                    raise subprocess.SubprocessError("cover output is too large")
            except OSError:
                pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            time.sleep(min(0.05, remaining))
        process.wait(timeout=0)
    except subprocess.TimeoutExpired:
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except (OSError, ProcessLookupError):
            pass
        try:
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise
    except Exception:
        try:
            if process.poll() is None:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
        except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
            pass
        try:
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise
    return process


def extract_cover(path, config=None, ffmpeg_resolver=None, runner=None):
    if not isinstance(path, str) or not path or ffmpeg_resolver is None or runner is None:
        return None, None
    ffmpeg = ffmpeg_resolver(config or {})
    if not ffmpeg:
        return None, None
    fd = -1
    target = ""
    try:
        fd, target = tempfile.mkstemp(prefix="fnaudio-cover-", suffix=".jpg")
        os.close(fd)
        fd = -1
        command = [ffmpeg, "-v", "error", "-y", "-i", path, "-map", "0:v:0", "-frames:v", "1", "-c:v", "mjpeg", "-q:v", "2", "-fs", str(MAX_COVER_FILE_BYTES), "-f", "image2", target]
        env = os.environ.copy()
        if "/usr/trim/lib/mediasrv/bin" in ffmpeg:
            env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
        result = _run_bounded(command, runner, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, env=env, check=False)
        if getattr(result, "returncode", 0) != 0:
            return None, None
        if os.path.getsize(target) > MAX_COVER_FILE_BYTES:
            return None, None
        with open(target, "rb") as handle:
            body = handle.read(MAX_COVER_FILE_BYTES + 1)
        if len(body) > MAX_COVER_FILE_BYTES:
            return None, None
    except (OSError, subprocess.SubprocessError):
        return None, None
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            if target:
                os.unlink(target)
        except OSError:
            pass
    if body.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", body
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", body
    if body.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif", body
    return None, None


__all__ = ["MAX_COVER_FILE_BYTES", "extract_cover"]
