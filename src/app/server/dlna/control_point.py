from __future__ import annotations

import hashlib
import re
import socket
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Optional
from xml.etree import ElementTree as ET

UPNP_CACHE = {"stamp": 0, "items": [], "refreshing": False}


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
    for node in root.iter():
        if not node.tag.endswith("service"):
            continue
        text = {child.tag.split("}")[-1]: (child.text or "") for child in node}
        if name in text.get("serviceType", ""):
            return urllib.parse.urljoin(description_url, text.get("controlURL", ""))
    return None


def soap_request(control, service, action, args=""):
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
    with urllib.request.urlopen(request, timeout=6) as response:
        return response.read()


def soap_text(response, tag):
    try:
        root = ET.fromstring(response)
    except ET.ParseError:
        return ""
    for node in root.iter():
        if node.tag.endswith(tag):
            return (node.text or "").strip()
    return ""


def seconds_to_upnp_time(value):
    value = max(0, int(round(float(value or 0))))
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)


def upnp_time_to_seconds(value):
    clean = str(value or "0:00:00").split(".", 1)[0]
    if not re.match(r"^\d{1,3}:\d{1,2}:\d{1,2}$", clean):
        return 0
    parts = [int(x or 0) for x in clean.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    hours, minutes, seconds = parts[-3:]
    return hours * 3600 + minutes * 60 + seconds


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
        if action == "seek":
            target = seconds_to_upnp_time(position)
            upnp_soap_action(control, "Seek", "<InstanceID>0</InstanceID><Unit>REL_TIME</Unit><Target>%s</Target>" % target)
        elif action == "play":
            upnp_soap_action(control, "Play", "<InstanceID>0</InstanceID><Speed>1</Speed>")
        elif action == "pause":
            upnp_soap_action(control, "Pause", "<InstanceID>0</InstanceID>")
        elif action == "stop":
            upnp_soap_action(control, "Stop", "<InstanceID>0</InstanceID>")
        elif action == "next":
            upnp_soap_action(control, "Next", "<InstanceID>0</InstanceID>")
        elif action == "previous":
            upnp_soap_action(control, "Previous", "<InstanceID>0</InstanceID>")
        else:
            return False, "未知控制操作"
    except Exception as exc:
        return False, str(exc)
    return True, "ok"


def device_supports_dsd(control):
    if not control:
        return False
    service = "urn:schemas-upnp-org:service:ConnectionManager:1"
    try:
        response = soap_request(control, service, "GetProtocolInfo")
        text = response.decode("utf-8", "ignore").lower()
        return any(x in text for x in ("audio/dsd", "audio/x-dsd", "audio/dsf", "audio/x-dsf", "audio/x-dff"))
    except Exception:
        return False




def discover_upnp():
    message = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 2\r\n"
        "ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n\r\n"
    ).encode("ascii")
    found = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(0.7)
    try:
        sock.sendto(message, ("239.255.255.250", 1900))
        deadline = time.time() + 2.5
        while time.time() < deadline:
            try:
                data, _ = sock.recvfrom(8192)
            except socket.timeout:
                continue
            headers = {}
            lines = data.decode("utf-8", "ignore").split("\r\n")
            for line in lines[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.lower()] = value.strip()
            location = headers.get("location")
            if location:
                found[location] = {
                    "id": hashlib.sha1(location.encode()).hexdigest()[:16],
                    "location": location,
                    "usn": headers.get("usn", ""),
                }
    finally:
        sock.close()
    devices = []
    for device in found.values():
        try:
            body = urllib.request.urlopen(device["location"], timeout=3).read()
            root = ET.fromstring(body)
            names = [x.text for x in root.iter() if x.tag.endswith("friendlyName") and x.text]
            udns = [x.text for x in root.iter() if x.tag.endswith("UDN") and x.text]
            device["name"] = names[0] if names else "UPnP 播放器"
            device["control_url"] = find_avtransport_url(root, device["location"])
            device["connection_url"] = find_service_url(root, device["location"], "ConnectionManager")
            # The local responder receives its own M-SEARCH request. It is an
            # input endpoint, so it must never be shown as a push destination.
            is_local_renderer = (
                "uuid:fnaudio-renderer" in udns
                or str(device["control_url"] or "").endswith("/dlna/renderer/avtransport/control")
            )
            if is_local_renderer:
                continue
            device["supports_dsd"] = device_supports_dsd(device["connection_url"])
            device["online"] = bool(device["control_url"])
            devices.append(device)
        except Exception:
            device["name"] = "UPnP 播放器"
            device["online"] = False
            device["supports_dsd"] = False
            devices.append(device)
    return devices


def refresh_upnp_cache_background():
    if UPNP_CACHE.get("refreshing"):
        return

    def worker():
        UPNP_CACHE["refreshing"] = True
        try:
            UPNP_CACHE["items"] = discover_upnp()
            UPNP_CACHE["stamp"] = time.time()
        finally:
            UPNP_CACHE["refreshing"] = False

    threading.Thread(target=worker, daemon=True).start()


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


