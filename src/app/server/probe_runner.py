"""Bounded ffprobe execution boundary used by library metadata scanning."""

import json
import math
import os
import re
import signal
import subprocess
import tempfile
import time


MAX_PROBE_OUTPUT_BYTES = 2 * 1024 * 1024


def _terminate_probe(process):
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


def _strict_nonnegative_int(value):
    """Project ffprobe numeric fields without bool or fractional coercion."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value)) if math.isfinite(value) and value.is_integer() else 0
    if isinstance(value, str):
        text = value.strip()
        if not re.fullmatch(r"\d+", text):
            return 0
        try:
            return int(text)
        except (TypeError, ValueError, OverflowError):
            return 0
    return 0


def _run_probe(command, env):
    """Capture real ffprobe output on disk so oversized output never peaks in RAM."""
    with tempfile.TemporaryFile(mode="w+b") as output:
        # Keep injected subprocess.run fakes working, but isolate real probes
        # in their own session so a timeout can terminate spawned helpers too.
        if getattr(subprocess.run, "__module__", "") == "unittest.mock":
            result = subprocess.run(command, stdout=output, stderr=subprocess.DEVNULL, timeout=20, env=env)
        else:
            process = subprocess.Popen(
                command,
                stdout=output,
                stderr=subprocess.DEVNULL,
                env=env,
                start_new_session=(os.name != "nt"),
            )
            try:
                deadline = time.monotonic() + 20
                while process.poll() is None:
                    output.seek(0, os.SEEK_END)
                    if output.tell() > MAX_PROBE_OUTPUT_BYTES:
                        _terminate_probe(process)
                        return process, None
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(command, 20)
                    time.sleep(min(0.05, remaining))
                process.wait(timeout=0)
            except subprocess.TimeoutExpired:
                _terminate_probe(process)
                raise
            except Exception:
                _terminate_probe(process)
                raise
            result = process
        output.seek(0, os.SEEK_END)
        if output.tell() > MAX_PROBE_OUTPUT_BYTES:
            return result, None
        output.seek(0)
        captured = output.read(MAX_PROBE_OUTPUT_BYTES + 1)
        if captured:
            return result, captured
        mocked = getattr(result, "stdout", None)
        if isinstance(mocked, (bytes, bytearray)):
            return result, bytes(mocked)
        return result, b""


def _safe_native(native_reader, path):
    try:
        value = native_reader(path)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _safe_ffprobe(ffprobe_resolver, config):
    try:
        value = ffprobe_resolver(config or {})
    except Exception:
        return ""
    return value if isinstance(value, str) else ""


def _probe_succeeded(result):
    """Treat a real non-zero ffprobe exit as unusable, while keeping simple test doubles compatible."""
    return getattr(result, "returncode", 0) == 0


def _prefer_native_container_facts(path, audio_info, native_info):
    """Prefer DSD container facts over ffprobe's DSD transport fields."""
    try:
        ext = os.path.splitext(os.fspath(path))[1].lower()
    except TypeError:
        ext = ""
    if ext not in (".dsf", ".dff"):
        return audio_info
    for key in ("sample_rate", "bit_depth", "bit_rate", "duration"):
        if native_info.get(key):
            audio_info[key] = native_info[key]
    return audio_info


def read_probe_metadata(path, config, *, ffprobe_resolver, native_reader, payload_normalizer):
    """Run ffprobe with bounded output and merge a native container fallback."""
    ffprobe = _safe_ffprobe(ffprobe_resolver, config)
    if not ffprobe:
        return {}, _safe_native(native_reader, path)
    command = [
        ffprobe,
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "format=duration:format_tags:stream_tags:stream=sample_rate,bits_per_raw_sample,bits_per_sample,bit_rate",
        "-of", "json",
        path,
    ]
    env = os.environ.copy()
    if "/usr/trim/lib/mediasrv/bin" in ffprobe:
        env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
    try:
        result, output = _run_probe(command, env)
        if not _probe_succeeded(result) or output is None or len(output) > MAX_PROBE_OUTPUT_BYTES:
            return {}, _safe_native(native_reader, path)
        data = json.loads(output.decode("utf-8", "ignore") or "{}")
        tags, audio_info = payload_normalizer(data)
    except Exception:
        return {}, _safe_native(native_reader, path)
    native_info = _safe_native(native_reader, path)
    _prefer_native_container_facts(path, audio_info, native_info)
    for key, value in native_info.items():
        if not audio_info.get(key):
            audio_info[key] = value
    return tags, audio_info


def read_audio_info(path, config, *, ffprobe_resolver, native_reader):
    """Read bounded stream facts for callers that do not need text tags."""
    ffprobe = _safe_ffprobe(ffprobe_resolver, config)
    if not ffprobe:
        return _safe_native(native_reader, path)
    command = [
        ffprobe,
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=sample_rate,bits_per_raw_sample,bits_per_sample,bit_rate",
        "-of", "json",
        path,
    ]
    env = os.environ.copy()
    if "/usr/trim/lib/mediasrv/bin" in ffprobe:
        env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
    try:
        result, output = _run_probe(command, env)
        if not _probe_succeeded(result) or output is None or len(output) > MAX_PROBE_OUTPUT_BYTES:
            return _safe_native(native_reader, path)
        data = json.loads(output.decode("utf-8", "ignore") or "{}")
        streams = data.get("streams") if isinstance(data, dict) else None
        stream = streams[0] if isinstance(streams, list) and streams and isinstance(streams[0], dict) else {}
        result_info = {
            "sample_rate": _strict_nonnegative_int(stream.get("sample_rate")),
            "bit_depth": _strict_nonnegative_int(stream.get("bits_per_raw_sample") or stream.get("bits_per_sample")),
            "bit_rate": _strict_nonnegative_int(stream.get("bit_rate")),
        }
    except Exception:
        # A truncated or schema-invalid ffprobe response must not hide the
        # native reader's usable stream facts. Treat parse failures like the
        # other probe failures and keep the fallback path available.
        return _safe_native(native_reader, path)
    native_info = _safe_native(native_reader, path)
    _prefer_native_container_facts(path, result_info, native_info)
    for key, value in native_info.items():
        if not result_info.get(key):
            result_info[key] = value
    return result_info
