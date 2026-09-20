from __future__ import annotations

import hashlib
import re
import socket
import threading
import time
import urllib.parse
import urllib.request
import math
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, Optional
from .network import fetch_lan, lan_address_cache_status, lan_http_url
from .xml_policy import safe_fromstring

UPNP_CACHE = {
    "stamp": 0, "items": [], "refreshing": False,
    "refresh_started": 0, "refresh_completed": 0,
    "refresh_failed": 0, "refresh_skipped": 0,
}
_UPNP_CACHE_LOCK = threading.RLock()
_UPNP_REFRESH_GENERATION = 0
_UPNP_REFRESH_THREAD = None
UPNP_CAPABILITY_CACHE: Dict[str, Dict[str, Any]] = {}
UPNP_CAPABILITY_CACHE_LIMIT = 256
UPNP_MAX_DISCOVERED_DEVICES = 128
UPNP_DISCOVERY_DEVICE_PROBE_LIMIT = 16
UPNP_DISCOVERY_MAX_TRANSIENT_ERRORS = 8
UPNP_DISCOVERY_PROBE_BUDGET_SECONDS = 12.0

# Locations the previous discovery pass spent a description request on. This is the whole
# rotation memory: it is bounded by UPNP_DISCOVERY_DEVICE_PROBE_LIMIT by construction, so it
# needs no cap of its own, and one round of history is enough to give every responder a turn
# within two rounds.
_UPNP_LAST_PROBED = frozenset()
MAX_UPNP_IDENTITY_CHARS = 4096
_UPNP_CAPABILITY_CACHE_LOCK = threading.RLock()
LOCAL_RENDERER_IDENTITY = {"location": "", "udn": ""}


def _capability_cache_entry(value):
    """Copy only ordinary capability maps; stale cache data is a cache miss."""
    if not isinstance(value, dict):
        return {}
    try:
        return dict(value)
    except Exception:
        return {}


def _identity_text(value):
    """Project a discovery identity without coercing arbitrary values."""
    return value[:MAX_UPNP_IDENTITY_CHARS] if isinstance(value, str) else ""


def _device_value(device, key):
    if not isinstance(device, dict):
        return None
    try:
        return device.get(key)
    except Exception:
        return None


def configure_local_renderer_identity(location="", udn=""):
    """Configure the exact renderer identity that discovery must hide."""
    LOCAL_RENDERER_IDENTITY["location"] = _identity_text(location).rstrip("/").lower()
    LOCAL_RENDERER_IDENTITY["udn"] = _identity_text(udn).split("::", 1)[0].strip().lower()


def is_local_renderer(device, udns):
    location = _identity_text(_device_value(device, "location")).rstrip("/").lower()
    values = list(udns) if isinstance(udns, (list, tuple, set)) else []
    values.append(_device_value(device, "usn"))
    advertised = {
        text.split("::", 1)[0].strip().lower()
        for text in (_identity_text(value) for value in values)
        if text.strip()
    }
    local_location = LOCAL_RENDERER_IDENTITY.get("location") or ""
    local_udn = LOCAL_RENDERER_IDENTITY.get("udn") or ""
    return bool(
        (local_location and location == local_location)
        or (local_udn and local_udn in advertised)
        or "uuid:fnaudio-renderer" in advertised
    )


class DlnaControlPoint:
    """Discovers and controls external UPnP/DLNA renderers."""

    def devices(self):
        return discover_upnp()

    def push(self, device: Dict[str, Any], item: Dict[str, Any], handler: Any, push_track: Callable):
        return push_track(device, item, handler)

    def command(self, device: Dict[str, Any], action: str, position: Optional[float] = None):
        return upnp_control(device, action, position)

    def status(self, device: Dict[str, Any]):
        return {
            "transport": upnp_transport_state(device),
            "position": upnp_position_info(device),
        }


def find_service_url(root, description_url, name):
    service = find_service(root, description_url, name)
    return service.get("control_url") if service else None


def find_service(root, description_url, name):
    for node in root.iter():
        if not node.tag.endswith("service"):
            continue
        text = {child.tag.split("}")[-1]: (child.text or "") for child in node}
        if name in text.get("serviceType", ""):
            return {
                "service_type": text.get("serviceType", ""),
                "control_url": urllib.parse.urljoin(description_url, text.get("controlURL", "")),
                "event_url": urllib.parse.urljoin(description_url, text.get("eventSubURL", "")),
                "scpd_url": urllib.parse.urljoin(description_url, text.get("SCPDURL", "")),
            }
    return None


def soap_request(control, service, action, args=""):
    # ``fetch_lan`` below is the single endpoint choke point: it parses the URL,
    # classifies every resolved address as LAN and pins the socket to one of them
    # before a byte leaves. Validating here as well used to resolve the same host
    # before a byte leaves. Validating here as well used to resolve the same host
    # a second time inside every action, so a renderer burst paid the resolver
    # twice per request for an answer that cannot change the outcome.
    # The text check stays here because building a Request out of a non-string
    # would raise an AttributeError instead of the ValueError callers catch.
    if not isinstance(control, str):
        raise ValueError("DLNA endpoint must be a text URL")
    envelope = (
        '<?xml version="1.0" encoding="utf-8"?><s:Envelope '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" '
        'xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
        "<s:Body><u:%s xmlns:u=\"%s\">%s</u:%s></s:Body></s:Envelope>"
        % (action, service, args, action)
    ).encode("utf-8")
    request = urllib.request.Request(
        control,
        data=envelope,
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": '"%s#%s"' % (service, action),
        },
        method="POST",
    )
    return fetch_lan(request, timeout=6)


def soap_text(response, tag):
    try:
        root = safe_fromstring(response)
    except (ET.ParseError, TypeError, ValueError):
        return ""
    for node in root.iter():
        if node.tag.endswith(tag):
            return (node.text or "").strip()
    return ""


def soap_fault(response):
    """Return a bounded SOAP fault message, or an empty string on success."""
    try:
        root = safe_fromstring(response)
    except (ET.ParseError, TypeError, ValueError):
        return ""
    for node in root.iter():
        if not node.tag.endswith("Fault"):
            continue
        for child in node.iter():
            if child is node or not child.tag.endswith(("faultstring", "errorDescription")):
                continue
            text = (child.text or "").strip()
            if text:
                return text[:512]
        return "SOAP Fault"
    return ""


def seconds_to_upnp_time(value):
    if isinstance(value, bool):
        value = 0.0
    try:
        numeric = float(value or 0)
    except (TypeError, ValueError, OverflowError):
        numeric = 0.0
    value = max(0, int(round(numeric))) if math.isfinite(numeric) else 0
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)


def upnp_time_to_seconds(value):
    if not isinstance(value, str):
        return 0
    clean = value[:32].strip().split(".", 1)[0]
    if not re.match(r"^\d{1,3}:\d{1,2}:\d{1,2}$", clean):
        return 0
    try:
        parts = [int(x or 0) for x in clean.split(":")]
    except (TypeError, ValueError, OverflowError):
        return 0
    while len(parts) < 3:
        parts.insert(0, 0)
    hours, minutes, seconds = parts[-3:]
    if minutes > 59 or seconds > 59:
        return 0
    # Keep malformed or hostile renderer values from inflating playback state
    # and seek calculations beyond the bounded protocol representation.
    total = hours * 3600 + minutes * 60 + seconds
    return total if total <= 24 * 60 * 60 else 0


def upnp_soap_action(control, action, args=""):
    return soap_request(control, "urn:schemas-upnp-org:service:AVTransport:1", action, args)


def upnp_transport_state(device):
    control = device.get("control_url")
    if not control:
        return None
    response = upnp_soap_action(control, "GetTransportInfo", "<InstanceID>0</InstanceID>")
    return {
        "state": soap_text(response, "CurrentTransportState") or "UNKNOWN",
        "rate": soap_text(response, "CurrentSpeed") or "1",
    }


def upnp_position_info(device):
    control = device.get("control_url")
    if not control:
        return None
    response = upnp_soap_action(control, "GetPositionInfo", "<InstanceID>0</InstanceID>")
    rel_time = soap_text(response, "RelTime") or "00:00:00"
    track_duration = soap_text(response, "TrackDuration") or "00:00:00"
    track_uri = soap_text(response, "TrackURI") or ""
    try:
        duration_seconds = upnp_time_to_seconds(track_duration)
        rel_seconds = upnp_time_to_seconds(rel_time)
    except Exception:
        duration_seconds = 0
        rel_seconds = 0
    return {
        "rel_time": rel_time,
        "track_duration": track_duration,
        "rel_seconds": rel_seconds,
        "duration_seconds": duration_seconds,
        "track_uri": track_uri,
    }


def upnp_control(device, action, position=None):
    control = device.get("control_url")
    if not control:
        return False, "设备没有 AVTransport 服务"
    try:
        response = None
        if action == "seek":
            target = seconds_to_upnp_time(position)
            response = upnp_soap_action(control, "Seek", "<InstanceID>0</InstanceID><Unit>REL_TIME</Unit><Target>%s</Target>" % target)
        elif action == "play":
            response = upnp_soap_action(control, "Play", "<InstanceID>0</InstanceID><Speed>1</Speed>")
        elif action == "pause":
            response = upnp_soap_action(control, "Pause", "<InstanceID>0</InstanceID>")
        elif action == "stop":
            response = upnp_soap_action(control, "Stop", "<InstanceID>0</InstanceID>")
        elif action == "next":
            response = upnp_soap_action(control, "Next", "<InstanceID>0</InstanceID>")
        elif action == "previous":
            response = upnp_soap_action(control, "Previous", "<InstanceID>0</InstanceID>")
        else:
            return False, "未知控制操作"
        fault = soap_fault(response)
        if fault:
            return False, fault
    except Exception as exc:
        return False, str(exc)
    return True, "ok"


def device_protocol_info(control):
    if not control:
        return {"source": [], "sink": [], "mime_types": [], "supports_dsd": False}
    service = "urn:schemas-upnp-org:service:ConnectionManager:1"
    try:
        response = soap_request(control, service, "GetProtocolInfo")
        source = [value.strip() for value in soap_text(response, "Source").split(",") if value.strip()]
        sink = [value.strip() for value in soap_text(response, "Sink").split(",") if value.strip()]
        mime_types = sorted(
            {
                parts[2].lower()
                for value in sink
                for parts in [value.split(":", 3)]
                if len(parts) >= 3 and parts[2]
            }
        )
        dsd_mimes = {"audio/dsd", "audio/x-dsd", "audio/dsf", "audio/x-dsf", "audio/x-dff"}
        return {
            "source": source,
            "sink": sink,
            "mime_types": mime_types,
            "supports_dsd": bool(dsd_mimes.intersection(mime_types)),
        }
    except Exception:
        return {"source": [], "sink": [], "mime_types": [], "supports_dsd": False}


def device_supports_dsd(control):
    value = device_protocol_info(control).get("supports_dsd")
    return value if isinstance(value, bool) else False


def scpd_actions(url):
    if not url:
        return []
    try:
        body = fetch_lan(url, timeout=3)
        root = safe_fromstring(body)
        return sorted(
            {
                (child.text or "").strip()
                for action in root.iter()
                if action.tag.endswith("action")
                for child in action
                if child.tag.endswith("name") and (child.text or "").strip()
            }
        )
    except Exception:
        return []


def probe_device_capabilities(device):
    cache_key = _identity_text(_device_value(device, "location") or _device_value(device, "id"))
    with _UPNP_CAPABILITY_CACHE_LOCK:
        cached = _capability_cache_entry(UPNP_CAPABILITY_CACHE.get(cache_key))
    try:
        cached_at = float(cached.get("probed_at") or 0)
    except (TypeError, ValueError, OverflowError):
        cached_at = 0.0
    if not math.isfinite(cached_at):
        cached_at = 0.0
    try:
        cached_monotonic = float(cached.get("probed_at_monotonic") or 0)
    except (TypeError, ValueError, OverflowError):
        cached_monotonic = 0.0
    if not math.isfinite(cached_monotonic):
        cached_monotonic = 0.0
    if cached and cached_monotonic > 0 and time.monotonic() - cached_monotonic < 300:
        return cached
    now_wall = time.time()
    now_monotonic = time.monotonic()
    protocol = device_protocol_info(_device_value(device, "connection_url"))
    actions = scpd_actions(_device_value(device, "avtransport_scpd_url"))
    capabilities = {
        "probed_at": now_wall,
        "probed_at_monotonic": now_monotonic,
        "protocol_info": protocol,
        "actions": actions,
        "set_next_uri": "SetNextAVTransportURI" in actions,
        "seek_rel_time": "Seek" in actions,
        "next": "Next" in actions,
        "previous": "Previous" in actions,
        "pause": "Pause" in actions,
        "eventing": bool(_identity_text(_device_value(device, "avtransport_event_url"))),
    }
    if cache_key:
        with _UPNP_CAPABILITY_CACHE_LOCK:
            UPNP_CAPABILITY_CACHE[cache_key] = dict(capabilities)
            if len(UPNP_CAPABILITY_CACHE) > UPNP_CAPABILITY_CACHE_LIMIT:
                oldest_key = min(
                    UPNP_CAPABILITY_CACHE,
                    key=lambda key: _finite_timestamp(
                        _capability_cache_entry(UPNP_CAPABILITY_CACHE.get(key)).get("probed_at_monotonic")
                    ),
                )
                UPNP_CAPABILITY_CACHE.pop(oldest_key, None)
    return capabilities




def discover_upnp():
    global _UPNP_LAST_PROBED
    message = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 2\r\n"
        "ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n\r\n"
    ).encode("ascii")
    found = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    # Default multicast TTL is 1, which routers never forward, so renderers
    # outside the local subnet stay invisible. The announce path uses 2.
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(0.7)
    try:
        sock.sendto(message, ("239.255.255.250", 1900))
        deadline = time.monotonic() + 2.5
        transient_errors = 0
        while time.monotonic() < deadline:
            try:
                data, _ = sock.recvfrom(8192)
            except socket.timeout:
                continue
            except OSError:
                # An undeliverable reply surfaces as an ICMP-derived error on
                # the next receive (ConnectionResetError on Windows, ECONNRESET
                # or EHOSTUNREACH on Linux). Renderers that are reachable can
                # still answer later in the window, so keep reading, but cap
                # the retries so a permanent socket error cannot spin until the
                # discovery deadline.
                transient_errors += 1
                if transient_errors >= UPNP_DISCOVERY_MAX_TRANSIENT_ERRORS:
                    break
                continue
            transient_errors = 0
            headers = {}
            lines = data.decode("utf-8", "ignore").split("\r\n")
            for line in lines[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.lower()] = value.strip()
            location = headers.get("location")
            if location:
                try:
                    location = lan_http_url(location)
                except ValueError:
                    continue
                if location not in found and len(found) >= UPNP_MAX_DISCOVERED_DEVICES:
                    continue
                found[location] = {
                    "id": hashlib.sha1(location.encode()).hexdigest()[:16],
                    "location": location,
                    "usn": headers.get("usn", ""),
                }
    finally:
        sock.close()
    devices = []
    probe_deadline = time.monotonic() + UPNP_DISCOVERY_PROBE_BUDGET_SECONDS
    # "A later refresh can continue probing the remainder" was only true if the arrival order
    # happened to change.  With more responders than the probe budget, the services that answer
    # within the first milliseconds (several on a single NAS) took all the slots in every round,
    # and a renderer deep behind an access point that answers late was never described at all, so
    # it could never appear as a playback target.  Reordering against the previous round's probed
    # set rotates the budget deterministically instead, and it costs nothing when every responder
    # already fits in the budget.
    previously_probed = _UPNP_LAST_PROBED
    rotation = [device for device in found.values() if device["location"] not in previously_probed]
    rotation += [device for device in found.values() if device["location"] in previously_probed]
    # SSDP announcements are unauthenticated and can be plentiful.  Do not let a burst of
    # unreachable renderers monopolize the single background discovery worker with sequential
    # description/protocol requests; the rotation above is what makes "a later refresh can
    # continue probing the remainder" actually hold.  Only the *choice* of whom to ask rotates:
    # the loop below still walks `found` in arrival order, because the target list the UI shows
    # keeps the order it is handed and would reshuffle on every refresh otherwise.
    chosen = {id(device) for device in rotation[:UPNP_DISCOVERY_DEVICE_PROBE_LIMIT]}
    probed_now = set()
    for device in found.values():
        if id(device) not in chosen:
            continue
        if time.monotonic() >= probe_deadline:
            break
        # A request was spent on this location, whether or not it answered.  Recording it before
        # the attempt is what stops one unreachable device from being retried ahead of a healthy
        # one that has never been asked.
        probed_now.add(device["location"])
        device["probed"] = True
        try:
            body = fetch_lan(device["location"], timeout=3)
            root = safe_fromstring(body)
            names = [x.text for x in root.iter() if x.tag.endswith("friendlyName") and x.text]
            udns = [x.text for x in root.iter() if x.tag.endswith("UDN") and x.text]
            device["name"] = names[0] if names else "UPnP 播放器"
            avtransport = find_service(root, device["location"], "AVTransport") or {}
            connection = find_service(root, device["location"], "ConnectionManager") or {}
            device["control_url"] = avtransport.get("control_url")
            device["avtransport_scpd_url"] = avtransport.get("scpd_url")
            device["avtransport_event_url"] = avtransport.get("event_url")
            device["connection_url"] = connection.get("control_url")
            # Every fnAudio renderer uses the same control URL path. Compare
            # the exact SSDP identity so another NAS is not mistaken for us.
            if is_local_renderer(device, udns):
                continue
            device["capabilities"] = probe_device_capabilities(device)
            raw_supports_dsd = (device["capabilities"].get("protocol_info") or {}).get("supports_dsd")
            device["supports_dsd"] = raw_supports_dsd if isinstance(raw_supports_dsd, bool) else False
            device["online"] = bool(device["control_url"])
            devices.append(device)
        except Exception:
            device["name"] = "UPnP 播放器"
            device["online"] = False
            device["supports_dsd"] = False
            devices.append(device)
    # Rebind rather than mutate: the discovery worker is serialized by the refresh flag, but a
    # direct caller must never observe a half-written set.
    _UPNP_LAST_PROBED = frozenset(probed_now)
    return devices


def retain_unprobed_devices(previous, current):
    """Merge a rotated discovery round back over the devices it did not probe this time.

    `online` has always meant "the last description fetch produced a control URL" (see :468), not
    "answered a ping a moment ago", and nothing re-pings between rounds.  So carrying an entry
    forward does not make a stronger liveness claim than the list already makes; dropping it does
    lose the renderer the user selected, because the target projection can only mark a device
    `selected` if it is present in this list (playback_targets_presentation.py:136).  Carried
    entries are marked `probed: False` so a consumer that cares about freshness can see it.
    """
    merged = [dict(device) if isinstance(device, dict) else device for device in (current or ())]
    known = {device.get("location") for device in merged if isinstance(device, dict)}
    for device in previous or ():
        if len(merged) >= UPNP_MAX_DISCOVERED_DEVICES:
            break
        if not isinstance(device, dict) or device.get("location") in known:
            continue
        retained = dict(device)
        retained["probed"] = False
        merged.append(retained)
        known.add(device.get("location"))
    return merged


def refresh_upnp_cache_background():
    """Start at most one bounded discovery worker and publish its state."""
    global _UPNP_REFRESH_GENERATION, _UPNP_REFRESH_THREAD
    with _UPNP_CACHE_LOCK:
        if UPNP_CACHE.get("refreshing"):
            UPNP_CACHE["refresh_skipped"] = _bounded_counter(UPNP_CACHE.get("refresh_skipped")) + 1
            return False
        # Publish the in-flight state before the thread starts. Otherwise a
        # client can observe an empty cache with refreshing=false in the small
        # window before the worker is scheduled and discard a valid saved target.
        UPNP_CACHE["refreshing"] = True
        UPNP_CACHE["refresh_started"] = _bounded_counter(UPNP_CACHE.get("refresh_started")) + 1
        _UPNP_REFRESH_GENERATION += 1
        generation = _UPNP_REFRESH_GENERATION

    def worker():
        global _UPNP_REFRESH_THREAD
        try:
            items = discover_upnp()
            with _UPNP_CACHE_LOCK:
                if generation == _UPNP_REFRESH_GENERATION:
                    UPNP_CACHE["items"] = retain_unprobed_devices(UPNP_CACHE.get("items"), items)
                    UPNP_CACHE["stamp"] = time.time()
                    UPNP_CACHE["refresh_completed"] = _bounded_counter(UPNP_CACHE.get("refresh_completed")) + 1
        except Exception:
            # Preserve the last known device list. Discovery is optional and
            # transient network failures must not erase a selected renderer.
            with _UPNP_CACHE_LOCK:
                if generation == _UPNP_REFRESH_GENERATION:
                    UPNP_CACHE["refresh_failed"] = _bounded_counter(UPNP_CACHE.get("refresh_failed")) + 1
        finally:
            with _UPNP_CACHE_LOCK:
                if generation == _UPNP_REFRESH_GENERATION:
                    UPNP_CACHE["refreshing"] = False
                if _UPNP_REFRESH_THREAD is threading.current_thread():
                    _UPNP_REFRESH_THREAD = None
                    UPNP_CACHE["refreshing"] = False

    try:
        thread = threading.Thread(target=worker, daemon=True)
        with _UPNP_CACHE_LOCK:
            _UPNP_REFRESH_THREAD = thread
        thread.start()
    except Exception:
        with _UPNP_CACHE_LOCK:
            _UPNP_REFRESH_THREAD = None
            UPNP_CACHE["refreshing"] = False
            UPNP_CACHE["refresh_failed"] = _bounded_counter(UPNP_CACHE.get("refresh_failed")) + 1
        return False
    return True


def shutdown_upnp_cache_background(wait=True, timeout=3.0):
    """Invalidate and optionally wait for an in-flight discovery worker."""
    global _UPNP_REFRESH_GENERATION, _UPNP_REFRESH_THREAD
    with _UPNP_CACHE_LOCK:
        _UPNP_REFRESH_GENERATION += 1
        thread = _UPNP_REFRESH_THREAD
        # The invalidated worker can no longer publish anything. Release the
        # admission flag immediately so a later refresh may start a new
        # generation while the old socket/probe operation winds down.
        UPNP_CACHE["refreshing"] = False
    if not wait or thread is None or thread is threading.current_thread():
        return
    try:
        bounded_timeout = float(timeout)
    except (TypeError, ValueError, OverflowError):
        bounded_timeout = 3.0
    if not math.isfinite(bounded_timeout):
        bounded_timeout = 3.0
    thread.join(timeout=max(0.0, bounded_timeout))


def cached_upnp_devices():
    """Return a shallow snapshot so HTTP readers do not race cache updates."""
    with _UPNP_CACHE_LOCK:
        return [dict(item) for item in (UPNP_CACHE.get("items") or ()) if isinstance(item, dict)]


def upnp_cache_needs_refresh(max_age_seconds=15.0):
    """Check cache age under the same lock used to admit discovery workers."""
    try:
        maximum = max(0.0, float(max_age_seconds))
    except (TypeError, ValueError, OverflowError):
        maximum = 15.0
    if not math.isfinite(maximum):
        maximum = 15.0
    with _UPNP_CACHE_LOCK:
        try:
            stamp = float(UPNP_CACHE.get("stamp") or 0)
        except (TypeError, ValueError, OverflowError):
            stamp = 0.0
        if not math.isfinite(stamp):
            stamp = 0.0
        return time.time() - stamp > maximum


def upnp_cache_status():
    """Return bounded discovery pressure counters without renderer details."""
    with _UPNP_CACHE_LOCK:
        lan = lan_address_cache_status()
        items = UPNP_CACHE.get("items") or ()
        try:
            stamp = float(UPNP_CACHE.get("stamp") or 0)
        except (TypeError, ValueError, OverflowError):
            stamp = 0.0
        if not math.isfinite(stamp):
            stamp = 0.0
        age = max(0, int(time.time() - stamp)) if stamp > 0 else 0
        return {
            "refreshing": bool(UPNP_CACHE.get("refreshing")),
            "workers": 1 if UPNP_CACHE.get("refreshing") else 0,
            "worker_limit": 1,
            "cached_renderers": len(items) if isinstance(items, (list, tuple)) else 0,
            "cache_age_seconds": age,
            "refresh_started": _bounded_counter(UPNP_CACHE.get("refresh_started")),
            "refresh_completed": _bounded_counter(UPNP_CACHE.get("refresh_completed")),
            "refresh_failed": _bounded_counter(UPNP_CACHE.get("refresh_failed")),
            "refresh_skipped": _bounded_counter(UPNP_CACHE.get("refresh_skipped")),
            # The LAN resolver cache rides on this page rather than getting its own field:
            # one more diagnostics source would be more log noise than the question it
            # answers deserves, and this dict is already held to a "no device identity"
            # contract, which is exactly the constraint the counters were designed under.
            "lan_cache_entries": _bounded_counter(lan.get("entries")),
            "lan_cache_hits": _bounded_counter(lan.get("hits")),
            "lan_cache_misses": _bounded_counter(lan.get("misses")),
            "lan_cache_expired": _bounded_counter(lan.get("expired")),
            "lan_cache_evictions": _bounded_counter(lan.get("evictions")),
            "lan_cache_limit": _bounded_counter(lan.get("limit")),
        }


def _finite_timestamp(value):
    try:
        number = float(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _bounded_counter(value):
    if isinstance(value, bool):
        return 0
    try:
        number = int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, min(number, 10**12))


def find_avtransport_url(root, description_url):
    service = None
    for node in root.iter():
        if node.tag.endswith("service"):
            text = {child.tag.split("}")[-1]: (child.text or "") for child in node}
            if "AVTransport" in text.get("serviceType", ""):
                service = text
                break
    if not service:
        return None
    return urllib.parse.urljoin(description_url, service.get("controlURL", ""))


