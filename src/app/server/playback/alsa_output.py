from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from typing import Any, Dict

DAC_STATE = {"device_id": "", "item_id": "", "processes": [], "playing": False, "started_at": 0.0, "offset": 0.0, "duration": 0.0, "strategy": {}}
DAC_LOCK = threading.Lock()


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def seconds_to_upnp_time(value):
    value = max(0, int(round(float(value or 0))))
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)


def find_ffmpeg(config):
    candidates = [
        "/usr/trim/lib/mediasrv/bin/ffmpeg",
        "/usr/trim/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg",
        shutil.which("ffmpeg"),
        shutil.which("ffmpeg.exe"),
        config.get("ffmpeg_path") if config else None,
    ]
    for candidate in candidates:
        if not candidate or not os.path.isfile(candidate):
            continue
        try:
            mode = os.stat(candidate).st_mode
            os.chmod(candidate, mode | 0o755)
        except OSError:
            pass
        return candidate
    return ""


def find_aplay():
    for candidate in (shutil.which("aplay"), "/usr/bin/aplay", "/bin/aplay", "/usr/local/bin/aplay"):
        if candidate and os.path.isfile(candidate):
            return candidate
    return ""


def find_libasound():
    for candidate in ("libasound.so.2", "libasound.so"):
        try:
            import ctypes
            import ctypes.util

            path = ctypes.util.find_library("asound") or candidate
            ctypes.CDLL(path)
            return path
        except Exception:
            continue
    return ""


def empty_dac_caps():
    return {"source": "unknown", "pcm_rates": [], "pcm_max_rate": 192000, "pcm_max_bits": 24, "dsd": False, "dsd_rates": [], "notes": []}


def merge_dac_caps(base, override):
    result = dict(base or empty_dac_caps())
    rates = set(result.get("pcm_rates") or [])
    rates.update(override.get("pcm_rates") or [])
    result["pcm_rates"] = sorted(rates)
    result["pcm_max_rate"] = max(safe_int(result.get("pcm_max_rate")), safe_int(override.get("pcm_max_rate")))
    result["pcm_max_bits"] = max(safe_int(result.get("pcm_max_bits")), safe_int(override.get("pcm_max_bits")))
    result["dsd"] = bool(result.get("dsd") or override.get("dsd"))
    dsd_rates = list(result.get("dsd_rates") or [])
    for rate in override.get("dsd_rates") or []:
        if rate not in dsd_rates:
            dsd_rates.append(rate)
    result["dsd_rates"] = dsd_rates
    notes = list(result.get("notes") or [])
    for note in override.get("notes") or []:
        if note not in notes:
            notes.append(note)
    result["notes"] = notes
    if override.get("source") and result.get("source") == "unknown":
        result["source"] = override.get("source")
    return result


def parse_dac_stream_caps(card):
    caps = empty_dac_caps()
    base = os.path.join("/proc/asound", "card%s" % card)
    if not os.path.isdir(base):
        return caps
    try:
        names = [name for name in os.listdir(base) if name.startswith("stream")]
    except OSError:
        names = []
    text = ""
    for name in names:
        try:
            with open(os.path.join(base, name), "r", encoding="utf-8", errors="ignore") as fh:
                text += "\n" + fh.read()
        except OSError:
            pass
    if not text:
        return caps
    caps["source"] = "/proc/asound/card%s/stream*" % card
    lower = text.lower()
    if "dsd" in lower or "dop" in lower:
        caps["dsd"] = True
    rates = set()
    for match in re.finditer(r"(?:Rates|Sampling Frequency):\s*([0-9,\s]+)", text, re.I):
        for value in re.findall(r"\d+", match.group(1)):
            rate = safe_int(value)
            if 8000 <= rate <= 768000:
                rates.add(rate)
    for value in re.findall(r"\b(?:44[.,]?1|48|88[.,]?2|96|176[.,]?4|192|352[.,]?8|384|705[.,]?6|768)\s*kHz\b", text, re.I):
        rates.add(int(float(value.replace(",", ".")) * 1000))
    caps["pcm_rates"] = sorted(rates)
    if rates:
        caps["pcm_max_rate"] = max(rates)
    bits = []
    format_bits = {"S16": 16, "S24": 24, "S32": 32, "FLOAT": 32}
    for key, value in format_bits.items():
        if key.lower() in lower:
            bits.append(value)
    if bits:
        caps["pcm_max_bits"] = max(bits)
    for value in re.findall(r"DSD(?:_U\d+)?|DOP|DoP|2\.8MHz|5\.6MHz|11\.2MHz", text, re.I):
        normalized = value.upper().replace("DOP", "DoP")
        if normalized not in caps["dsd_rates"]:
            caps["dsd_rates"].append(normalized)
    return caps


def enrich_dac_device(device):
    caps = parse_dac_stream_caps(str(device.get("alsa_id", "")).replace("hw:", "").split(",", 1)[0])
    if not caps.get("pcm_rates"):
        caps["pcm_rates"] = [caps.get("pcm_max_rate") or 192000]
    device["caps"] = caps
    return device


def is_music_alsa_device(*parts):
    text = " ".join(str(part or "") for part in parts).lower()
    blocked = ("pcsp", "pc speaker", "pc-speaker", "pcspeaker", "beep", "speaker at port 0x61")
    return not any(token in text for token in blocked)


def _proc_asound_path(*parts):
    root = os.environ.get("FNAUDIO_ASOUND_ROOT") or "/proc/asound"
    return os.path.join(root, *[str(part) for part in parts])


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def _read_card_codecs(card):
    base = _proc_asound_path("card%s" % card)
    codecs = []
    try:
        names = os.listdir(base)
    except OSError:
        names = []
    for name in names:
        if not name.startswith("codec"):
            continue
        text = _read_text(os.path.join(base, name))
        for line in text.splitlines():
            match = re.match(r"\s*Codec:\s*(.+?)\s*$", line, re.I)
            if match:
                codec = match.group(1).strip()
                if codec and codec not in codecs:
                    codecs.append(codec)
    return codecs


def _read_card_usb_name(card):
    base = _proc_asound_path("card%s" % card)
    try:
        names = [name for name in os.listdir(base) if name.startswith("stream")]
    except OSError:
        names = []
    for name in names:
        text = _read_text(os.path.join(base, name))
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if not first:
            continue
        first = re.sub(r"\s+at\s+usb-.*$", "", first, flags=re.I).strip()
        first = re.sub(r"\s+at\s+.*$", "", first, flags=re.I).strip()
        if first:
            return first
    return ""


def _read_sysfs_value(card, name):
    path = os.path.join("/sys/class/sound/card%s/device" % card, name)
    return _read_text(path).strip().lower()


def _is_usb_card(card, *parts):
    text = " ".join(str(part or "") for part in parts).lower()
    if "usb" in text:
        return True
    try:
        real = os.path.realpath("/sys/class/sound/card%s/device" % card).lower()
        if "usb" in real:
            return True
    except OSError:
        pass
    driver = _read_sysfs_value(card, "driver")
    return "usb" in driver


def _card_vendor_label(card, *parts):
    text = " ".join(str(part or "") for part in parts).lower()
    text_without_driver_alias = re.sub(r"\bhda[-_ ]intel\b", " ", text)
    vendor_id = _read_sysfs_value(card, "vendor")
    vendor_map = {
        "0x1002": "AMD",
        "0x1022": "AMD",
        "0x8086": "Intel",
        "0x10de": "NVIDIA",
        "0x10ec": "Realtek",
    }
    if vendor_id in vendor_map:
        return vendor_map[vendor_id]
    if "amd" in text_without_driver_alias or "ati" in text_without_driver_alias:
        return "AMD"
    if "nvidia" in text_without_driver_alias:
        return "NVIDIA"
    if "realtek" in text_without_driver_alias:
        return "Realtek"
    if "intel" in text_without_driver_alias:
        return "Intel"
    return ""


def friendly_alsa_device_name(card, device, card_info, pcm_name, dev_name, raw_line=""):
    card = str(int(card))
    device = str(int(device))
    card_name = card_info.get("name") or ""
    card_key = card_info.get("key") or ""
    driver = card_info.get("driver") or ""
    codecs = _read_card_codecs(card)
    usb_name = _read_card_usb_name(card)
    raw = " ".join([raw_line, card_name, card_key, driver, pcm_name, dev_name, usb_name, " ".join(codecs)])
    lower = raw.lower()
    dev_clean = dev_name.strip()
    if usb_name or "usb" in lower:
        usb_candidates = [
            value.strip()
            for value in (card_name, usb_name, pcm_name.strip())
            if value and value.strip() and value.strip().lower() not in ("usb audio", "usb-audio")
        ]
        base = min(usb_candidates, key=len) if usb_candidates else "USB Audio"
        base = _compact_audio_name(base)
        if dev_clean and dev_clean.lower() not in base.lower():
            generic_device = dev_clean.lower() in ("usb audio", "usb-audio", "usb audio playback")
            return base if generic_device else "%s 路 %s" % (base, dev_clean)
        return base
    if "hdmi" in lower:
        vendor = _card_vendor_label(card, raw)
        match = re.search(r"hdmi\s*(\d+)", dev_clean, re.I)
        suffix = match.group(1) if match else device
        return "%s HDMI %s" % (vendor, suffix) if vendor else "HDMI %s" % suffix
    analog_codec = next((codec for codec in codecs if "realtek" in codec.lower() or re.search(r"\balc\d+\b", codec, re.I)), "")
    if "analog" in lower:
        if analog_codec:
            return "%s Analog" % analog_codec
        vendor = _card_vendor_label(card, raw)
        if vendor:
            return "%s Analog" % vendor
    if codecs:
        return "%s 路 %s" % (codecs[0], dev_clean or pcm_name.strip())
    return "%s - %s" % (card_name or pcm_name.strip(), dev_clean)


def _compact_audio_name(value):
    text = re.sub(r"\b(?:Corporation|Corp\.?|Co\.?|Ltd\.?|Limited)\b", "", str(value or ""), flags=re.I)
    text = re.sub(r"\bUSB[- ]?Audio\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -路")
    return text or str(value or "")


def alsa_devices_from_proc():
    cards = {}
    try:
        with open(_proc_asound_path("cards"), "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                match = re.match(r"\s*(\d+)\s+\[([^\]]+)\]\s*:\s*(.+?)\s+-\s+(.+)", line)
                if match:
                    card, key, driver, name = match.groups()
                    cards[card] = {"key": key.strip(), "driver": driver.strip(), "name": name.strip()}
    except OSError:
        pass
    devices = []
    try:
        with open(_proc_asound_path("pcm"), "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if "playback" not in line.lower():
                    continue
                match = re.match(r"\s*(\d+)-(\d+):\s*([^:]+):\s*([^:]+):", line)
                if not match:
                    continue
                card, device, pcm_name, dev_name = match.groups()
                card_info = cards.get(str(int(card)), {})
                alsa_id = "hw:%s,%s" % (int(card), int(device))
                raw_name = "%s - %s" % (card_info.get("name") or pcm_name.strip(), dev_name.strip())
                name = friendly_alsa_device_name(card, device, card_info, pcm_name, dev_name, line)
                if not is_music_alsa_device(line, name, card_info.get("key"), card_info.get("driver")):
                    continue
                is_usb = _is_usb_card(card, line, name, raw_name, card_info.get("driver", ""), card_info.get("key", ""))
                devices.append(enrich_dac_device({"id": "dac:" + alsa_id, "alsa_id": alsa_id, "name": name, "raw_name": raw_name, "online": True, "kind": "dac", "is_usb": is_usb}))
    except OSError:
        pass
    return devices


def alsa_devices():
    proc_devices = alsa_devices_from_proc()
    if proc_devices:
        return [device for device in proc_devices if device.get("is_usb")]
    aplay = find_aplay()
    if not aplay:
        return []
    try:
        result = subprocess.run([aplay, "-l"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=5)
    except Exception:
        return []
    text = result.stdout.decode("utf-8", "ignore")
    devices = []
    for line in text.splitlines():
        match = re.search(r"card\s+(\d+):\s*([^\[]+)\s*\[([^\]]+)\],\s*device\s+(\d+):\s*([^\[]+)\s*\[([^\]]+)\]", line, re.I)
        if not match:
            continue
        card, _card_key, card_name, device, _dev_key, dev_name = match.groups()
        alsa_id = "hw:%s,%s" % (card, device)
        raw_name = "%s - %s" % (card_name.strip(), dev_name.strip())
        name = friendly_alsa_device_name(card, device, {"name": card_name.strip(), "key": _card_key.strip(), "driver": ""}, _dev_key.strip(), dev_name.strip(), line)
        if not is_music_alsa_device(line, name, card_name, dev_name):
            continue
        is_usb = _is_usb_card(card, line, name, raw_name, card_name, dev_name)
        devices.append(enrich_dac_device({"id": "dac:" + alsa_id, "alsa_id": alsa_id, "name": name, "raw_name": raw_name, "online": True, "kind": "dac", "is_usb": is_usb}))
    return [device for device in devices if device.get("is_usb")]


def dac_public_status():
    with DAC_LOCK:
        if DAC_STATE.get("playing"):
            processes = list(DAC_STATE.get("processes") or [])
            if processes and any(process and process.poll() is not None for process in processes):
                DAC_STATE["offset"] = safe_float(DAC_STATE.get("offset")) + max(0, time.time() - safe_float(DAC_STATE.get("started_at")))
                DAC_STATE["playing"] = False
                DAC_STATE["processes"] = []
        state = dict(DAC_STATE)
    rel = safe_float(state.get("offset"))
    if state.get("playing"):
        rel += max(0, time.time() - safe_float(state.get("started_at")))
    duration = safe_float(state.get("duration"))
    if duration > 0:
        rel = min(rel, duration)
    return {
        "transport": {"state": "PLAYING" if state.get("playing") else "STOPPED", "rate": "1"},
        "position": {"rel_time": seconds_to_upnp_time(rel), "track_duration": seconds_to_upnp_time(duration), "rel_seconds": rel, "duration_seconds": duration, "track_uri": state.get("item_id", "")},
        "device_id": state.get("device_id", ""),
        "item_id": state.get("item_id", ""),
        "strategy": state.get("strategy") or {},
    }


def stop_dac_locked():
    processes = list(DAC_STATE.get("processes") or [])
    DAC_STATE["processes"] = []
    DAC_STATE["playing"] = False
    for process in reversed(processes):
        try:
            if process and process.poll() is None:
                process.terminate()
        except Exception:
            pass
    deadline = time.time() + 1.5
    for process in reversed(processes):
        try:
            while process and process.poll() is None and time.time() < deadline:
                time.sleep(0.05)
            if process and process.poll() is None:
                process.kill()
        except Exception:
            pass


def dac_ffmpeg_command(item, config, start=0):
    ffmpeg = find_ffmpeg(config)
    if not ffmpeg:
        raise RuntimeError("鏈壘鍒伴鐗涚郴缁熻浆鐮佸櫒 ffmpeg")
    command = [ffmpeg, "-threads", "0", "-hide_banner", "-loglevel", "error"]
    if start and start > 0:
        command += ["-ss", str(max(0, float(start)))]
    command += ["-i", item["path"], "-vn", "-map", "0:a:0"]
    if item.get("is_dsd"):
        command += ["-ar", "192000", "-codec:a", "pcm_s24le"]
    else:
        command += ["-codec:a", "pcm_s16le"]
    command += ["-f", "wav", "pipe:1"]
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
    return command, env


def dac_pcm_profile(item):
    strategy = item.get("_dac_strategy") or {}
    if item.get("is_dsd"):
        bits = safe_int(strategy.get("bits")) or 24
        codec = "pcm_s32le" if bits > 24 else "pcm_s24le"
        sample_format = "s32le" if bits > 24 else "s24le"
        return {"rate": safe_int(strategy.get("rate")) or 192000, "channels": 2, "sample_format": sample_format, "codec": codec}
    sample_rate = safe_int(item.get("sample_rate")) or 44100
    bits = safe_int(strategy.get("bits")) or min(max(safe_int(item.get("bit_depth")) or 16, 16), 32)
    codec = "pcm_s32le" if bits > 24 else ("pcm_s24le" if bits > 16 else "pcm_s16le")
    sample_format = "s32le" if bits > 24 else ("s24le" if bits > 16 else "s16le")
    return {"rate": safe_int(strategy.get("rate")) or min(max(sample_rate, 8000), 192000), "channels": 2, "sample_format": sample_format, "codec": codec}


def aplay_format_name(sample_format):
    return {"s16le": "S16_LE", "s24le": "S24_3LE", "s32le": "S32_LE"}.get(str(sample_format or "").lower(), "S16_LE")


def dac_ffmpeg_alsa_command(item, config, alsa_id, start=0):
    ffmpeg = find_ffmpeg(config)
    if not ffmpeg:
        raise RuntimeError("閺堫亝澹橀崚浼搭棧閻楁稓閮寸紒鐔绘祮閻礁娅?ffmpeg")
    profile = dac_pcm_profile(item)
    command = [ffmpeg, "-threads", "0", "-hide_banner", "-loglevel", "error"]
    if start and start > 0:
        command += ["-ss", str(max(0, float(start)))]
    command += [
        "-i", item["path"],
        "-vn",
        "-map", "0:a:0",
        "-ac", str(profile["channels"]),
        "-ar", str(profile["rate"]),
        "-codec:a", profile["codec"],
        "-f", "alsa",
        str(alsa_id or "default"),
    ]
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
    return command, env, profile


def process_failure_message(processes, fallback):
    time.sleep(0.35)
    failed = False
    messages = []
    for process in processes:
        if not process:
            continue
        if process.poll() is not None:
            failed = True
            try:
                _stdout, stderr = process.communicate(timeout=0.2)
                text = (stderr or b"").decode("utf-8", "replace").strip()
                if text:
                    messages.append(text.splitlines()[-1])
            except Exception:
                pass
    if not failed:
        return ""
    with DAC_LOCK:
        stop_dac_locked()
    return "; ".join(messages) or fallback


def dac_device_by_id(device_id):
    return next((d for d in alsa_devices() if d.get("id") == device_id), None)


def choose_dac_strategy(item, device):
    caps = (device or {}).get("caps") or empty_dac_caps()
    rates = [safe_int(x) for x in caps.get("pcm_rates") or [] if safe_int(x)]
    max_rate = safe_int(caps.get("pcm_max_rate")) or (max(rates) if rates else 192000)
    max_bits = safe_int(caps.get("pcm_max_bits")) or 24
    if caps.get("source") == "unknown":
        rates = [44100]
        max_rate = 44100
        max_bits = 16
    source_rate = safe_int(item.get("sample_rate")) or 44100
    source_bits = safe_int(item.get("bit_depth")) or 16
    if item.get("is_dsd"):
        if caps.get("dsd"):
            return {
                "mode": "dsd_direct_preferred",
                "label": "DSD direct preferred (PCM fallback test mode)",
                "rate": max_rate,
                "bits": min(max_bits, 32),
                "needs_transcode": False,
                "direct_possible": True,
                "actual": "pcm_fallback",
                "caps": caps,
            }
        return {
            "mode": "dsd_to_best_pcm",
            "label": "DSD to supported PCM %skHz/%sbit" % (int(max_rate / 1000), min(max_bits, 32)),
            "rate": max_rate,
            "bits": min(max_bits, 32),
            "needs_transcode": True,
            "direct_possible": False,
            "actual": "pcm",
            "caps": caps,
        }
    target_rate = source_rate if source_rate <= max_rate else max_rate
    if rates:
        allowed = [rate for rate in rates if rate >= min(source_rate, max_rate)]
        target_rate = min(allowed) if allowed else max(rates)
    target_bits = min(max(source_bits, 16), max_bits or 24)
    direct = target_rate == source_rate and target_bits >= source_bits
    return {
        "mode": "pcm_direct" if direct else "pcm_to_supported",
        "label": ("Use source PCM %skHz/%sbit" if direct else "Convert to DAC PCM %skHz/%sbit") % (int(target_rate / 1000), target_bits),
        "rate": target_rate,
        "bits": target_bits,
        "needs_transcode": not direct,
        "direct_possible": direct,
        "actual": "pcm",
        "caps": caps,
    }


def dac_ffmpeg_pcm_command(item, config, start=0):
    ffmpeg = find_ffmpeg(config)
    if not ffmpeg:
        raise RuntimeError("ffmpeg is not available")
    profile = dac_pcm_profile(item)
    command = [ffmpeg, "-threads", "0", "-hide_banner", "-loglevel", "error"]
    if start and start > 0:
        command += ["-ss", str(max(0, float(start)))]
    command += [
        "-i", item["path"],
        "-vn",
        "-map", "0:a:0",
        "-ac", str(profile["channels"]),
        "-ar", str(profile["rate"]),
        "-codec:a", profile["codec"],
        "-f", profile["sample_format"],
        "pipe:1",
    ]
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = "/usr/trim/lib/mediasrv/lib:" + env.get("LD_LIBRARY_PATH", "")
    return command, env, profile


def start_dac_playback(device_id, item, config, start=0):
    alsa_id = str(device_id or "").replace("dac:", "", 1)
    device = dac_device_by_id(device_id)
    if not device:
        return False, "娌℃湁鎵惧埌杩欎釜 USB/ALSA 闊抽璁惧"
    strategy = choose_dac_strategy(item, device)
    playback_item = dict(item)
    playback_item["_dac_strategy"] = strategy
    try:
        aplay = find_aplay()
        if aplay:
            ffmpeg_cmd, env, profile = dac_ffmpeg_pcm_command(playback_item, config, start)
            ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            player_process = subprocess.Popen(
                [aplay, "-q", "-D", alsa_id, "-f", aplay_format_name(profile["sample_format"]), "-r", str(profile["rate"]), "-c", str(profile["channels"]), "-"],
                stdin=ffmpeg_process.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if ffmpeg_process.stdout:
                ffmpeg_process.stdout.close()
            processes = [ffmpeg_process, player_process]
        else:
            if not find_libasound():
                return False, "绯荤粺娌℃湁 aplay锛屼篃娌℃湁鎵惧埌 libasound锛屾殏鏃舵棤娉曠洿鎺ヨ緭鍑哄埌 USB DAC"
            ffmpeg_cmd, env, _profile = dac_ffmpeg_alsa_command(playback_item, config, alsa_id, start)
            player_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=env,
            )
            processes = [player_process]
    except Exception as exc:
        return False, str(exc)
    failed = process_failure_message(processes, "audio output process exited immediately")
    if failed:
        return False, failed
    with DAC_LOCK:
        stop_dac_locked()
        DAC_STATE.update({"device_id": device_id, "item_id": item["id"], "processes": processes, "playing": True, "started_at": time.time(), "offset": safe_float(start), "duration": safe_float(item.get("duration")), "strategy": strategy})
    return True, "ok"


def dac_control(action, position=None, item=None, config=None):
    action = str(action or "").lower()
    with DAC_LOCK:
        state = dict(DAC_STATE)
        processes = list(DAC_STATE.get("processes") or [])
    if action == "stop":
        with DAC_LOCK:
            stop_dac_locked()
        return True, "ok"
    if action == "pause":
        if os.name != "posix":
            return False, "DAC pause is only supported on Linux"
        with DAC_LOCK:
            if DAC_STATE.get("playing"):
                DAC_STATE["offset"] = safe_float(DAC_STATE.get("offset")) + max(0, time.time() - safe_float(DAC_STATE.get("started_at")))
                DAC_STATE["playing"] = False
                for process in processes:
                    try:
                        if process and process.poll() is None:
                            os.kill(process.pid, signal.SIGSTOP)
                    except Exception:
                        pass
        return True, "ok"
    if action == "play":
        if os.name != "posix":
            return False, "DAC resume is only supported on Linux"
        with DAC_LOCK:
            DAC_STATE["started_at"] = time.time()
            DAC_STATE["playing"] = True
            for process in processes:
                try:
                    if process and process.poll() is None:
                        os.kill(process.pid, signal.SIGCONT)
                except Exception:
                    pass
        return True, "ok"
    if action == "seek":
        if not item or not config:
            return False, "missing current track information"
        return start_dac_playback(state.get("device_id"), item, config, safe_float(position))
    return False, "unsupported DAC control action"


