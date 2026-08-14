from __future__ import annotations

import os
import re
import hashlib
import ctypes
import ctypes.util
import shutil
import signal
import subprocess
import sys
import threading
import time
from typing import Any, Dict

DAC_STATE = {"device_id": "", "item_id": "", "processes": [], "playing": False, "started_at": 0.0, "offset": 0.0, "duration": 0.0, "strategy": {}}
DAC_LOCK = threading.Lock()
ALSA_CAPS_CACHE = {}
ALSA_CAPS_LOCK = threading.Lock()


def preserve_verified_busy_probe(previous, current):
    """Keep the last successful ALSA negotiation while the PCM is occupied."""
    previous = dict(previous or {})
    current = dict(current or {})
    if not current.get("busy") or not previous.get("verified"):
        return current
    preserved = dict(previous)
    preserved.update(
        {
            "busy": True,
            "available": True,
            "error": current.get("error") or "ALSA PCM is busy",
            "probed_at": current.get("probed_at") or time.time(),
        }
    )
    return preserved


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


def probe_alsa_hw_params(device, force=False, cache_seconds=300.0):
    """Verify formats by opening the selected ALSA PCM and testing hw_params.

    `/proc/asound/.../stream*` describes driver-advertised USB descriptors.
    This probe answers the stricter question: can ALSA actually configure this
    PCM endpoint with the requested rate, sample format and channel count?
    """
    device = dict(device or {})
    cache_key = str(device.get("stable_id") or device.get("stable_alsa_id") or device.get("alsa_id") or "")
    now = time.time()
    with ALSA_CAPS_LOCK:
        cached = dict(ALSA_CAPS_CACHE.get(cache_key) or {})
    effective_cache_seconds = min(float(cache_seconds), 5.0) if cached.get("busy") else float(cache_seconds)
    if cached and not force and now - safe_float(cached.get("probed_at")) <= max(1.0, effective_cache_seconds):
        return cached
    result = {
        "source": "alsa-hw-params",
        "verified": False,
        "available": False,
        "busy": False,
        "device": str(device.get("stable_alsa_id") or device.get("alsa_id") or "default"),
        "pcm_rates": [],
        "pcm_formats": [],
        "pcm_max_rate": 0,
        "pcm_max_bits": 0,
        "native_dsd": False,
        "native_dsd_formats": [],
        "error": "",
        "probed_at": now,
    }
    library_path = ctypes.util.find_library("asound") or find_libasound()
    if not library_path:
        result["error"] = "libasound is unavailable"
        return result
    pcm = ctypes.c_void_p()
    params = ctypes.c_void_p()
    try:
        lib = ctypes.CDLL(library_path)
        lib.snd_pcm_open.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
        lib.snd_pcm_open.restype = ctypes.c_int
        lib.snd_pcm_close.argtypes = [ctypes.c_void_p]
        lib.snd_pcm_hw_params_malloc.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        lib.snd_pcm_hw_params_malloc.restype = ctypes.c_int
        lib.snd_pcm_hw_params_free.argtypes = [ctypes.c_void_p]
        lib.snd_pcm_hw_params_any.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.snd_pcm_hw_params_any.restype = ctypes.c_int
        lib.snd_pcm_hw_params_test_channels.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
        lib.snd_pcm_hw_params_test_channels.restype = ctypes.c_int
        lib.snd_pcm_hw_params_test_rate.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_int]
        lib.snd_pcm_hw_params_test_rate.restype = ctypes.c_int
        lib.snd_pcm_hw_params_test_format.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        lib.snd_pcm_hw_params_test_format.restype = ctypes.c_int
        lib.snd_pcm_format_value.argtypes = [ctypes.c_char_p]
        lib.snd_pcm_format_value.restype = ctypes.c_int
        # MPD may have just stopped or switched tracks while the kernel is
        # still releasing the USB PCM handle.  A short bounded retry avoids
        # treating that transition as a permanent inability to verify Native
        # DSD/DoP.  Non-forced status probes remain single-shot so polling
        # never adds latency to the playback UI.
        attempts = 4 if force else 1
        open_code = -16
        for attempt in range(attempts):
            open_code = lib.snd_pcm_open(ctypes.byref(pcm), result["device"].encode("utf-8"), 0, 1)
            if open_code >= 0 or open_code != -16 or attempt >= attempts - 1:
                break
            time.sleep(0.15)
        if open_code < 0:
            result["busy"] = open_code == -16
            result["error"] = "ALSA open failed (%s)" % open_code
            # MPD owns the PCM while it is playing.  Do not throw away a
            # successful probe from the stopped/initial state merely because
            # a status refresh happens during playback.  Keep the verified
            # formats, but expose the current busy condition to callers.
            if result["busy"]:
                with ALSA_CAPS_LOCK:
                    previous = dict(ALSA_CAPS_CACHE.get(cache_key) or {})
                preserved = preserve_verified_busy_probe(previous, result)
                if preserved is not result:
                    # Continue through the common finally block so the
                    # preserved result, rather than the transient `-16`
                    # probe result, is written back to the cache.
                    result = preserved
                    return result
            return result
        result["available"] = True
        if lib.snd_pcm_hw_params_malloc(ctypes.byref(params)) < 0 or not params:
            result["error"] = "ALSA hw_params allocation failed"
            return result
        if lib.snd_pcm_hw_params_any(pcm, params) < 0:
            result["error"] = "ALSA hw_params query failed"
            return result
        if lib.snd_pcm_hw_params_test_channels(pcm, params, 2) < 0:
            result["error"] = "stereo playback is unsupported"
            return result
        pcm_formats = (("S16_LE", 16), ("S24_3LE", 24), ("S24_LE", 24), ("S32_LE", 32))
        for name, bits in pcm_formats:
            format_id = lib.snd_pcm_format_value(name.encode("ascii"))
            if format_id >= 0 and lib.snd_pcm_hw_params_test_format(pcm, params, format_id) == 0:
                result["pcm_formats"].append(name)
                result["pcm_max_bits"] = max(result["pcm_max_bits"], bits)
        for rate in (44100, 48000, 88200, 96000, 176400, 192000, 352800, 384000, 705600, 768000):
            if lib.snd_pcm_hw_params_test_rate(pcm, params, rate, 0) == 0:
                result["pcm_rates"].append(rate)
        dsd_names = ("DSD_U8", "DSD_U16_LE", "DSD_U16_BE", "DSD_U32_LE", "DSD_U32_BE")
        for name in dsd_names:
            format_id = lib.snd_pcm_format_value(name.encode("ascii"))
            if format_id >= 0 and lib.snd_pcm_hw_params_test_format(pcm, params, format_id) == 0:
                result["native_dsd_formats"].append(name)
        result["pcm_max_rate"] = max(result["pcm_rates"] or [0])
        result["native_dsd"] = bool(result["native_dsd_formats"])
        result["verified"] = bool(result["pcm_formats"] or result["native_dsd_formats"])
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        try:
            if params:
                lib.snd_pcm_hw_params_free(params)
        except Exception:
            pass
        try:
            if pcm:
                lib.snd_pcm_close(pcm)
        except Exception:
            pass
        result["probed_at"] = time.time()
        with ALSA_CAPS_LOCK:
            ALSA_CAPS_CACHE[cache_key] = dict(result)
    return result


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
    base = _proc_asound_path("card%s" % card)
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
    caps["source"] = "%s/stream*" % base
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
    card, pcm_device = _alsa_card_device(device.get("alsa_id"))
    identity = alsa_device_identity(card, pcm_device, device)
    device.update(identity)
    caps = parse_dac_stream_caps(card)
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


def _sys_sound_path(*parts):
    root = os.environ.get("FNAUDIO_SYS_SOUND_ROOT") or "/sys/class/sound"
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
    path = os.path.join(_sys_sound_path("card%s" % card, "device"), name)
    return _read_text(path).strip().lower()


def _alsa_card_device(alsa_id):
    match = re.search(r"(?:hw:)?(\d+)\s*,\s*(\d+)", str(alsa_id or ""), re.I)
    return (match.group(1), match.group(2)) if match else ("", "0")


def _safe_identity_part(value):
    normalized = re.sub(r"[^a-z0-9._-]+", "-", str(value or "").strip().lower()).strip("-.")
    return normalized[:80]


def _usb_sysfs_identity(card):
    """Read USB identity from the sound interface or one of its USB parents."""
    start = os.path.realpath(_sys_sound_path("card%s" % card, "device"))
    current = start
    fields = {}
    for _ in range(8):
        for name in ("idVendor", "idProduct", "serial", "product", "manufacturer"):
            if name not in fields:
                value = _read_text(os.path.join(current, name)).strip()
                if value:
                    fields[name] = value
        if fields.get("idVendor") and fields.get("idProduct") and (fields.get("serial") or fields.get("product")):
            break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return fields


def alsa_device_identity(card, pcm_device="0", hints=None):
    """Return a persistent identity plus the current ALSA runtime address.

    Numeric card indexes are intentionally excluded from ``stable_id``. USB
    reconnects may change ``hw:X,Y`` while the ALSA card id, VID/PID and serial
    continue to identify the same physical DAC.
    """
    hints = dict(hints or {})
    card = str(card or "")
    pcm_device = str(pcm_device or "0")
    card_id = _read_text(_proc_asound_path("card%s" % card, "id")).strip()
    usb = _usb_sysfs_identity(card) if card else {}
    vendor = _safe_identity_part(usb.get("idVendor"))
    product_id = _safe_identity_part(usb.get("idProduct"))
    serial = _safe_identity_part(usb.get("serial"))
    product = _safe_identity_part(usb.get("product") or hints.get("raw_name") or hints.get("name"))
    card_key = _safe_identity_part(card_id)
    if vendor and product_id:
        discriminator = serial or card_key or product
        stable_id = "usb:%s:%s:%s:dev%s" % (vendor, product_id, discriminator or "unknown", pcm_device)
    elif card_key:
        stable_id = "alsa:%s:dev%s" % (card_key, pcm_device)
    else:
        fallback = "%s|%s|%s" % (hints.get("raw_name", ""), hints.get("name", ""), pcm_device)
        stable_id = "alsa:fallback-%s:dev%s" % (hashlib.sha1(fallback.encode("utf-8", "ignore")).hexdigest()[:12], pcm_device)
    stable_alsa_id = "hw:CARD=%s,DEV=%s" % (card_id, pcm_device) if card_id else str(hints.get("alsa_id") or "default")
    return {
        "stable_id": stable_id,
        "stable_alsa_id": stable_alsa_id,
        "card_id": card_id,
        "card_index": safe_int(card, -1),
        "pcm_device": safe_int(pcm_device, 0),
        "usb_vendor_id": vendor,
        "usb_product_id": product_id,
        "usb_serial": str(usb.get("serial") or ""),
        "usb_product": str(usb.get("product") or ""),
        "usb_manufacturer": str(usb.get("manufacturer") or ""),
    }


def _is_usb_card(card, *parts):
    text = " ".join(str(part or "") for part in parts).lower()
    if "usb" in text:
        return True
    try:
        real = os.path.realpath(_sys_sound_path("card%s" % card, "device")).lower()
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
                enriched = enrich_dac_device({"alsa_id": alsa_id, "name": name, "raw_name": raw_name, "online": True, "kind": "dac", "is_usb": is_usb})
                enriched["id"] = "dac:" + enriched["stable_id"]
                devices.append(enriched)
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
        enriched = enrich_dac_device({"alsa_id": alsa_id, "name": name, "raw_name": raw_name, "online": True, "kind": "dac", "is_usb": is_usb})
        enriched["id"] = "dac:" + enriched["stable_id"]
        devices.append(enriched)
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
        raise RuntimeError("系统中未找到可用的 ffmpeg")
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
        return {
            "mode": "dsd_requires_mpd",
            "label": "DSD must use verified MPD Native DSD/DoP output",
            "rate": 0,
            "bits": 0,
            "needs_transcode": False,
            "direct_possible": bool(caps.get("dsd")),
            "actual": "blocked_no_pcm_fallback",
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


def _nice_preexec(value):
    value = int(value or 0)
    if os.name == "nt" or not value:
        return None
    def apply_nice():
        try:
            os.nice(value)
        except (OSError, ValueError):
            pass
    return apply_nice


def start_dac_playback(device_id, item, config, start=0):
    device = dac_device_by_id(device_id)
    if not device:
        return False, "没有找到这个 USB/ALSA 音频设备"
    alsa_id = str(device.get("stable_alsa_id") or device.get("alsa_id") or "")
    strategy = choose_dac_strategy(item, device)
    if item.get("is_dsd"):
        return False, "DSD 直连模式不允许转为 PCM，请使用 MPD USB DAC 输出进行 Native DSD/DoP 播放"
    playback_item = dict(item)
    playback_item["_dac_strategy"] = strategy
    try:
        from services.dac_profiles import dac_quirk_profile
        quirk = dac_quirk_profile(device, (config or {}).get("dac_profiles") or [])
    except Exception:
        quirk = {"track_settle_ms": 0}
    # Never overlap the previous aplay/ffmpeg pair with the new one.  On USB
    # DACs that overlap can produce an ALSA busy/open retry and visible first-
    # frame stalls.  The settle window is opt-in per DAC profile.
    with DAC_LOCK:
        stop_dac_locked()
    settle_ms = max(0, min(500, safe_int(quirk.get("track_settle_ms"))))
    if settle_ms:
        time.sleep(settle_ms / 1000.0)
    nice_value = safe_int((config or {}).get("ffmpeg_nice"))
    try:
        aplay = find_aplay()
        if aplay:
            ffmpeg_cmd, env, profile = dac_ffmpeg_pcm_command(playback_item, config, start)
            ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, preexec_fn=_nice_preexec(nice_value))
            player_process = subprocess.Popen(
                [aplay, "-q", "-D", alsa_id, "-f", aplay_format_name(profile["sample_format"]), "-r", str(profile["rate"]), "-c", str(profile["channels"]), "-"],
                stdin=ffmpeg_process.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                preexec_fn=_nice_preexec(nice_value),
            )
            if ffmpeg_process.stdout:
                ffmpeg_process.stdout.close()
            processes = [ffmpeg_process, player_process]
        else:
            if not find_libasound():
                return False, "系统没有 aplay，也没有找到 libasound，暂时无法直接输出到 USB DAC"
            ffmpeg_cmd, env, _profile = dac_ffmpeg_alsa_command(playback_item, config, alsa_id, start)
            player_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=_nice_preexec(nice_value),
            )
            processes = [player_process]
    except Exception as exc:
        return False, str(exc)
    failed = process_failure_message(processes, "audio output process exited immediately")
    if failed:
        return False, failed
    with DAC_LOCK:
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


