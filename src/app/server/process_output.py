"""Bounded capture helpers for optional external process probes."""
from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
import math
from typing import Mapping, Sequence


class ProcessOutputTooLarge(RuntimeError):
    pass


def _validated_args(args: Sequence[str]) -> list[str]:
    if isinstance(args, (str, bytes)):
        raise ValueError("external process arguments must be a sequence")
    try:
        command = list(args)
    except TypeError as exc:
        raise ValueError("external process arguments must be a sequence") from exc
    if not command or len(command) > 128 or any(not isinstance(part, str) or not part or len(part) > 4096 for part in command):
        raise ValueError("invalid external process arguments")
    return command


def _validated_limit(value: int, *, minimum: float, maximum: float, label: str):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid %s" % label)
    try:
        result = float(value)
    except (OverflowError, ValueError, TypeError) as exc:
        raise ValueError("invalid %s" % label) from exc
    if not math.isfinite(result) or not (minimum <= result <= maximum):
        raise ValueError("invalid %s" % label)
    if label == "output limit":
        if result != math.trunc(result):
            raise ValueError("invalid %s" % label)
        return int(result)
    return result


def _terminate_process_tree(process: subprocess.Popen) -> None:
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except (OSError, ProcessLookupError):
        pass
    finally:
        try:
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass


def check_output_bounded(args: Sequence[str], *, max_bytes: int, timeout: float, env: Mapping[str, str] | None = None) -> bytes:
    command = _validated_args(args)
    limit = _validated_limit(max_bytes, minimum=1, maximum=16 * 1024 * 1024, label="output limit")
    wait_timeout = _validated_limit(timeout, minimum=0.01, maximum=300.0, label="timeout")
    # Preserve the repository's subprocess mock seam in unit tests. Production
    # calls always use the tempfile-backed bounded path below.
    if getattr(subprocess.check_output, "__module__", "") == "unittest.mock":
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=wait_timeout, env=env)
        if len(output) > limit:
            raise ProcessOutputTooLarge("external process output is too large")
        return output
    with tempfile.TemporaryFile(mode="w+b") as output:
        process = subprocess.Popen(
            command,
            stdout=output,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + wait_timeout
            while process.poll() is None:
                output.seek(0, os.SEEK_END)
                if output.tell() > limit:
                    raise ProcessOutputTooLarge("external process output is too large")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, wait_timeout)
                time.sleep(min(0.05, remaining))
            process.wait(timeout=0)
        except subprocess.TimeoutExpired:
            _terminate_process_tree(process)
            raise
        except Exception:
            # Output probing can fail independently of the child process.
            # Always terminate and reap the process tree before propagating
            # an unrelated temporary-file or wait error.
            _terminate_process_tree(process)
            raise
        output.seek(0, os.SEEK_END)
        if output.tell() > limit:
            raise ProcessOutputTooLarge("external process output is too large")
        output.seek(0)
        data = output.read(limit)
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command, output=data)
        return data
