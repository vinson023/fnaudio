from __future__ import annotations

import hashlib
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import math
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, Optional
from .network import fetch_lan, lan_address_cache_status, lan_http_url
from .profiles import device_supports_native_dsd
from .xml_policy import safe_fromstring

UPNP_CACHE = {
    "stamp": 0, "items": [], "refreshing": False,
    "refresh_started": 0, "refresh_completed": 0,
    "refresh_failed": 0, "refresh_skipped": 0,
}
_UPNP_CACHE_LOCK = threading.RLock()
_UPNP_REFRESH_GENERATION = 0
_UPNP_REFRESH_THREAD = None
_UPNP_KEEPER_STOP = None
_UPNP_KEEPER_THREAD = None
_UPNP_KEEPER_LOCK = threading.RLock()
UPNP_CAPABILITY_CACHE: Dict[str, Dict[str, Any]] = {}
UPNP_CAPABILITY_CACHE_LIMIT = 256
UPNP_MAX_DISCOVERED_DEVICES = 128
UPNP_DISCOVERY_DEVICE_PROBE_LIMIT = 16
UPNP_DISCOVERY_MAX_TRANSIENT_ERRORS = 8
UPNP_DISCOVERY_PROBE_BUDGET_SECONDS = 12.0
# How often the keeper thread re-arms discovery, and how old a cached list may be
# before a reader triggers a scan itself.
#
# The device dialog used to start a fresh discovery on nearly every open: the
# passive window was 15 s, and discovery can spend up to
# UPNP_DISCOVERY_PROBE_BUDGET_SECONDS, so anyone opening the dialog more than
# 15 s after the last visit paid that wait while staring at "正在扫描局域网".
# The keeper keeps the cache warm so an open almost always finds it fresh, and
# the passive window is wide enough to cover one full keepalive cycle plus a
# slow discovery pass.
UPNP_CACHE_KEEPALIVE_SECONDS = 25.0
UPNP_PASSIVE_MAX_AGE_SECONDS = 60.0
_UPNP_KEEPER_TICK_SECONDS = 5.0

# How long a renderer that has stopped answering SSDP stays in the published list.
#
# The list used to carry every device it had ever seen forward forever, so a renderer whose
# owner disabled it - or the same NAS after its port changed, which changes `location` and
# therefore its `id` - stayed on the target list for the life of the process, and no amount of
# rescanning removed it.  On the reference install the cache held four entries of which exactly
# one still answered M-SEARCH (192.168.5.22:53199); the other three were a disabled renderer, the
# same host's previous port, and a location whose description never loaded.
#
# The window is deliberately wider than UPNP_CACHE_KEEPALIVE_SECONDS (25 s): one lost M-SEARCH
# reply on Wi-Fi must not make a live renderer blink out of the list, so a single missed round is
# forgiven and only a device that misses two rounds in a row is evicted.
UPNP_RETAIN_UNPROBED_SECONDS = 30.0

# An explicit rescan is a request for the truth now, so it runs a round in the
# caller's thread instead of promising one later. The budget is far smaller than
# a background pass (1.5 s instead of 12 s) because the whole round has to fit
# inside the dialog's 6 s request timeout: 2.5 s of M-SEARCH replies plus this
# is what the click actually waits for. Anything the budget skips still shows up
# as "answered, not described yet", and a LAN description fetch is milliseconds.
UPNP_RESCAN_PROBE_BUDGET_SECONDS = 1.5
# How long an explicit rescan waits for a background round that was already
# running before the click, before answering from the cache as it stands.
UPNP_RESCAN_WAIT_SECONDS = 3.5

# Locations the previous discovery pass spent a description request on. This is the whole
# rotation memory: it is bounded by UPNP_DISCOVERY_DEVICE_PROBE_LIMIT by construction, so it
# needs no cap of its own, and one round of history is enough to give every responder a turn
# within two rounds.
_UPNP_LAST_PROBED = frozenset()
# Locations that answered the last M-SEARCH, whether or not the probe budget reached them.
# Answering SSDP is the liveness signal; being described is not.  `_UPNP_SEEN_GENERATION` exists
# so a caller can tell "discovery published a fresh answer" from "discovery never ran" (a mocked
# or failed pass must not evict anything on a stale set).
_UPNP_LAST_SEEN = frozenset()
_UPNP_SEEN_GENERATION = 0
# location -> time.monotonic() of the last round it answered.  Kept beside the device dicts rather
# than inside them so the published payload shape does not grow an internal clock.
_UPNP_SEEN_AT: Dict[str, float] = {}
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


def soap_failure(exc):
    """Describe a refused SOAP action without leaking urllib's own wording.

    ``str(HTTPError)`` is "HTTP Error 403: Forbidden" - no verb, no host, no
    route - and that string is what the push dialog showed when a peer answered
    a control request with its direct-access notice page. The status is the only
    part of it worth keeping, so name what was refused and keep the code.
    """
    if isinstance(exc, urllib.error.HTTPError):
        try:
            status = int(getattr(exc, "code", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            status = 0
        if status:
            return "目标设备拒绝了 DLNA 控制请求（HTTP %d）" % status
    return str(exc)


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


RENDERING_SERVICE = "urn:schemas-upnp-org:service:RenderingControl:1"


def upnp_set_volume(device, percent):
    """Ask the renderer to change its own volume (RenderingControl SetVolume).

    This is the only attenuation that costs nothing: the device applies it, the
    bytes fnAudio sends are untouched, so bit-perfect output survives. When the
    renderer has no RenderingControl service there is no such call to make and
    the caller has to decide between refusing and scaling the samples itself.
    """
    control = device.get("volume_url")
    if not control:
        return False, "该设备不提供 RenderingControl 音量服务"
    try:
        value = int(round(float(percent)))
    except (TypeError, ValueError, OverflowError):
        value = 100
    value = max(0, min(100, value))
    try:
        soap_request(
            control,
            RENDERING_SERVICE,
            "SetVolume",
            "<InstanceID>0</InstanceID><Channel>Master</Channel><DesiredVolume>%d</DesiredVolume>" % value,
        )
    except Exception as exc:
        return False, soap_failure(exc)
    return True, "ok"


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
        return False, soap_failure(exc)
    return True, "ok"


def device_protocol_info(control):
    # A missing or failing ConnectionManager is silence, not a refusal: the
    # record deliberately carries no `supports_dsd` key so `unknown` cannot be
    # read back as "this renderer does not do DSD".
    if not control:
        return {"source": [], "sink": [], "mime_types": []}
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
        return {"source": [], "sink": [], "mime_types": []}


def device_supports_dsd(control):
    return device_supports_native_dsd(device_protocol_info(control))


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
    # RenderingControl is what makes "change this device's volume" possible at
    # all; asking its SCPD is how we learn it before the user drags a slider.
    volume_actions = scpd_actions(_device_value(device, "volume_scpd_url"))
    capabilities = {
        "probed_at": now_wall,
        "probed_at_monotonic": now_monotonic,
        "protocol_info": protocol,
        "actions": actions,
        "volume": "SetVolume" in volume_actions,
        "mute": "SetMute" in volume_actions,
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




def _publish_seen(locations):
    """Record which locations answered this M-SEARCH round.

    Answering is the only liveness fact discovery has; the probe budget decides who gets
    described, not who is alive.  Publishing through one function (rather than assigning the
    module global from the call site) is what lets the refresh worker distinguish a real round
    from a pass that never reached the network.
    """
    global _UPNP_LAST_SEEN, _UPNP_SEEN_GENERATION
    _UPNP_LAST_SEEN = frozenset(location for location in (locations or ()) if isinstance(location, str))
    _UPNP_SEEN_GENERATION += 1


def discover_upnp(probe_budget=None):
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
                    # Filled from the description when the probe succeeds; empty
                    # means "not described yet", never "no identity".
                    "udn": "",
                }
    finally:
        sock.close()
    # Publish before the probe phase: an exception or an exhausted budget while describing must
    # not erase the answer this round already received.
    _publish_seen(found.keys())
    devices = []
    if isinstance(probe_budget, bool) or not isinstance(probe_budget, (int, float)):
        probe_budget = UPNP_DISCOVERY_PROBE_BUDGET_SECONDS
    probe_deadline = time.monotonic() + max(0.0, float(probe_budget))
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
            # The UDN is the only identity the device itself claims, and unlike
            # `location` it does not contain the port. Keeping it on the record
            # is what lets the cache recognise "same renderer, new address".
            device["udn"] = udns[0] if udns else ""
            avtransport = find_service(root, device["location"], "AVTransport") or {}
            connection = find_service(root, device["location"], "ConnectionManager") or {}
            rendering = find_service(root, device["location"], "RenderingControl") or {}
            device["control_url"] = avtransport.get("control_url")
            device["avtransport_scpd_url"] = avtransport.get("scpd_url")
            device["avtransport_event_url"] = avtransport.get("event_url")
            device["connection_url"] = connection.get("control_url")
            # Needed for the volume command: without it the only way to attenuate
            # a push is to re-encode the stream, which costs bit-perfect output.
            device["volume_url"] = rendering.get("control_url")
            device["volume_scpd_url"] = rendering.get("scpd_url")
            # Every fnAudio renderer uses the same control URL path. Compare
            # the exact SSDP identity so another NAS is not mistaken for us.
            if is_local_renderer(device, udns):
                continue
            device["capabilities"] = probe_device_capabilities(device)
            # The flat field is a display cache derived from the probe through the
            # same predicate the push gate uses, so it can never outvote or drift
            # from the record it was computed from.
            device["supports_dsd"] = device_supports_native_dsd(device)
            device["online"] = bool(device["control_url"])
            devices.append(device)
        except Exception:
            device["name"] = "UPnP 播放器"
            device["online"] = False
            devices.append(device)
    # Rebind rather than mutate: the discovery worker is serialized by the refresh flag, but a
    # direct caller must never observe a half-written set.
    _UPNP_LAST_PROBED = frozenset(probed_now)
    return devices


def retain_unprobed_devices(previous, current, seen=None, now=None, strict=False):
    """Merge a rotated discovery round back over the devices it did not probe this time.

    `online` has always meant "the last description fetch produced a control URL" (see :468), not
    "answered a ping a moment ago", and nothing re-pings between rounds.  So carrying an entry
    forward does not make a stronger liveness claim than the list already makes; dropping it does
    lose the renderer the user selected, because the target projection can only mark a device
    `selected` if it is present in this list (playback_targets_presentation.py:136).  Carried
    entries are marked `probed: False` so a consumer that cares about freshness can see it.

    Carrying forward is bounded by `UPNP_RETAIN_UNPROBED_SECONDS`, not by the 128-device ceiling
    alone.  `seen` is the set of locations that answered this round's M-SEARCH: a device inside it
    is alive even if the probe budget never reached it, so it is kept and its clock is refreshed.
    A device outside it has gone quiet, and is evicted once it has been quiet for longer than the
    window - which is what finally removes a renderer that was disabled, and the ghost left behind
    when a NAS changed port (a new port is a new `location`, hence a new `id`; nothing else ties
    the two together).  `seen=None` means this round has no liveness answer at all (discovery never
    ran); nothing is evicted on a guess.

    Two additions for the explicit rescan (R628):

    * A device whose UDN matches one discovered this round has moved, not multiplied.  The fresh
      record already describes it at its new address, so the old row is dropped instead of carried
      - this is what removes the duplicate the moment a NAS changes port.
    * `strict=True` evicts anything that did not answer this round, without waiting out the window.
      It is only used for a user-initiated rescan, where "重新扫描" is a request for the current
      truth and a 30-second grace period reads as "the ghost never goes away".
    """
    if now is None:
        now = time.monotonic()
    merged = [dict(device) if isinstance(device, dict) else device for device in (current or ())]
    known = set()
    moved = set()
    for device in merged:
        if isinstance(device, dict) and isinstance(device.get("location"), str):
            known.add(device["location"])
            # Probed this round: it answered SSDP and its description loaded.
            _UPNP_SEEN_AT[device["location"]] = now
            udn = device.get("udn")
            if isinstance(udn, str) and udn:
                moved.add(udn)
    for device in previous or ():
        if len(merged) >= UPNP_MAX_DISCOVERED_DEVICES:
            break
        if not isinstance(device, dict) or device.get("location") in known:
            continue
        location = device.get("location")
        if not isinstance(location, str) or not location:
            continue
        udn = device.get("udn")
        if isinstance(udn, str) and udn and udn in moved:
            # Same device, new address: the live record above is the only row
            # it should occupy. Its clock goes with the entry.
            _UPNP_SEEN_AT.pop(location, None)
            continue
        if seen is None:
            keep = True
        elif location in seen:
            # Alive, just not described this round: refresh the clock so rotation can never
            # starve a renderer out of the list.
            keep = True
            _UPNP_SEEN_AT[location] = now
        elif strict:
            keep = False
        else:
            last_seen = _UPNP_SEEN_AT.get(location)
            if last_seen is None:
                # First round we are tracking it (carried over from a build without this clock):
                # start the window now rather than evict on an age we cannot know.
                keep = True
                _UPNP_SEEN_AT[location] = now
            else:
                keep = (now - last_seen) <= UPNP_RETAIN_UNPROBED_SECONDS
        if not keep:
            _UPNP_SEEN_AT.pop(location, None)
            continue
        retained = dict(device)
        retained["probed"] = False
        merged.append(retained)
        known.add(location)
    for location in [key for key in _UPNP_SEEN_AT if key not in known]:
        _UPNP_SEEN_AT.pop(location, None)
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
        seen_generation = _UPNP_SEEN_GENERATION
        try:
            items = discover_upnp()
            # Only a pass that actually published an answer may evict. A mocked or crashed
            # discovery leaves the previous generation in place, and then `seen` stays None so
            # nothing is dropped on a stale liveness set.
            seen = _UPNP_LAST_SEEN if _UPNP_SEEN_GENERATION != seen_generation else None
            with _UPNP_CACHE_LOCK:
                if generation == _UPNP_REFRESH_GENERATION:
                    UPNP_CACHE["items"] = retain_unprobed_devices(UPNP_CACHE.get("items"), items, seen)
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


def rescan_upnp_devices(wait_seconds=UPNP_RESCAN_WAIT_SECONDS):
    """Run one discovery round now and publish it, for an explicit rescan.

    `/api/upnp/devices` and `/api/playback/targets?refresh=1` used to answer
    with ``refreshing: true`` and the *previous* list, so the button labelled
    重新扫描 could only ever show what discovery already knew - which is why a
    ghost survived every click.  This runs the round in the caller's thread and
    merges it strictly, so the response that comes back is the answer to the
    click.

    Returns True when a round was applied.  A round already in flight is waited
    on rather than duplicated: two M-SEARCH passes racing would let the older
    reply set the liveness answer, and `refreshing` is the same flag the keeper
    and the worker use, so holding it is also what keeps them out.
    """
    deadline = time.monotonic() + (wait_seconds if isinstance(wait_seconds, (int, float))
                                   and not isinstance(wait_seconds, bool) else UPNP_RESCAN_WAIT_SECONDS)
    with _UPNP_CACHE_LOCK:
        busy = bool(UPNP_CACHE.get("refreshing"))
        if not busy:
            UPNP_CACHE["refreshing"] = True
            UPNP_CACHE["refresh_started"] = _bounded_counter(UPNP_CACHE.get("refresh_started")) + 1
    if busy:
        while time.monotonic() < deadline:
            with _UPNP_CACHE_LOCK:
                if not UPNP_CACHE.get("refreshing"):
                    return True
            time.sleep(0.05)
        return False
    seen_generation = _UPNP_SEEN_GENERATION
    try:
        items = discover_upnp(probe_budget=UPNP_RESCAN_PROBE_BUDGET_SECONDS)
    except Exception:
        with _UPNP_CACHE_LOCK:
            UPNP_CACHE["refresh_failed"] = _bounded_counter(UPNP_CACHE.get("refresh_failed")) + 1
            UPNP_CACHE["refreshing"] = False
        return False
    seen = _UPNP_LAST_SEEN if _UPNP_SEEN_GENERATION != seen_generation else None
    try:
        with _UPNP_CACHE_LOCK:
            UPNP_CACHE["items"] = retain_unprobed_devices(UPNP_CACHE.get("items"), items, seen, strict=True)
            UPNP_CACHE["stamp"] = time.time()
            UPNP_CACHE["refresh_completed"] = _bounded_counter(UPNP_CACHE.get("refresh_completed")) + 1
    finally:
        with _UPNP_CACHE_LOCK:
            UPNP_CACHE["refreshing"] = False
    return True


def start_upnp_cache_keeper():
    """Keep the renderer cache warm instead of discovering on first use.

    Idempotent: a second call while the thread is alive returns False and leaves
    the running keeper alone, which matters because server start-up can be
    retried after a failed bind.
    """
    global _UPNP_KEEPER_STOP, _UPNP_KEEPER_THREAD
    with _UPNP_KEEPER_LOCK:
        existing = _UPNP_KEEPER_THREAD
        if existing is not None and existing.is_alive():
            return False
        stop = threading.Event()

        def loop():
            # The first pass runs immediately: a fresh process has an empty cache,
            # and the point of this thread is that no user request waits for the
            # first answer.  Every later pass only re-arms discovery when the
            # cache has actually aged past the keepalive window, so the loop costs
            # one timestamp comparison most of the time.
            while not stop.is_set():
                try:
                    if upnp_cache_needs_refresh(UPNP_CACHE_KEEPALIVE_SECONDS):
                        refresh_upnp_cache_background()
                except Exception:
                    # Discovery is optional and the cache keeps the last known
                    # renderers; one bad pass must not stop the keeper.
                    pass
                stop.wait(_UPNP_KEEPER_TICK_SECONDS)

        thread = threading.Thread(target=loop, name="fnaudio-upnp-cache-keeper", daemon=True)
        _UPNP_KEEPER_STOP = stop
        _UPNP_KEEPER_THREAD = thread
        try:
            thread.start()
        except Exception:
            _UPNP_KEEPER_STOP = None
            _UPNP_KEEPER_THREAD = None
            return False
    return True


def stop_upnp_cache_keeper(timeout=2.0):
    """Stop the keeper before the cache itself is invalidated on shutdown."""
    global _UPNP_KEEPER_STOP, _UPNP_KEEPER_THREAD
    with _UPNP_KEEPER_LOCK:
        stop = _UPNP_KEEPER_STOP
        thread = _UPNP_KEEPER_THREAD
        _UPNP_KEEPER_STOP = None
        _UPNP_KEEPER_THREAD = None
    if stop is None:
        return
    stop.set()
    if thread is None or thread is threading.current_thread():
        return
    try:
        bounded_timeout = float(timeout)
    except (TypeError, ValueError, OverflowError):
        bounded_timeout = 2.0
    if not math.isfinite(bounded_timeout):
        bounded_timeout = 2.0
    thread.join(timeout=max(0.0, bounded_timeout))


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


def upnp_cache_needs_refresh(max_age_seconds=UPNP_PASSIVE_MAX_AGE_SECONDS):
    """Check cache age under the same lock used to admit discovery workers.

    The default is the passive window, not the keepalive one: a reader should
    only pay for discovery when the keeper has not managed to refresh for a
    while, never merely because the last refresh is a few seconds old.
    """
    try:
        maximum = max(0.0, float(max_age_seconds))
    except (TypeError, ValueError, OverflowError):
        maximum = UPNP_PASSIVE_MAX_AGE_SECONDS
    if not math.isfinite(maximum):
        maximum = UPNP_PASSIVE_MAX_AGE_SECONDS
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


