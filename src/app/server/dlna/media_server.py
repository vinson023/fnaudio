from __future__ import annotations

import html
import os
import urllib.parse
from typing import Any, Callable, Dict

from .control_point import soap_request
from .profiles import protocol_info


def _dlna_duration(seconds: Any) -> str:
    try:
        value = max(0, int(round(float(seconds or 0))))
    except (TypeError, ValueError):
        value = 0
    hours = value // 3600
    minutes = (value % 3600) // 60
    secs = value % 60
    return "%d:%02d:%02d" % (hours, minutes, secs)


class DlnaMediaServer:
    """Serves local library resources to DLNA clients and pushed renderers."""

    def __init__(
        self,
        media_url: Callable[[Any, Dict[str, Any]], str],
        media_mime: Callable[[Dict[str, Any]], str],
        media_size: Callable[[Dict[str, Any], Dict[str, Any]], int],
    ):
        self.media_url = media_url
        self.media_mime = media_mime
        self.media_size = media_size

    def resource(self, handler: Any, item: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "url": self.media_url(handler, item),
            "mime": self.media_mime(item),
            "size": self.media_size(item, config),
            "direct": not bool(item.get("cue_track")),
        }


def upnp_resource_mime(item: Dict[str, Any]) -> str:
    if item.get("cue_track"):
        return "audio/flac"
    ext = os.path.splitext(item["path"])[1].lower()
    if ext == ".dsf":
        return "audio/x-dsf"
    if ext == ".dff":
        return "audio/x-dff"
    return item.get("mime") or "application/octet-stream"


def upnp_media_url(
    handler: Any,
    item: Dict[str, Any],
    safe_filename: Callable[[str], str],
    upnp_base_url: Callable[[Any], str],
) -> str:
    if item.get("cue_track"):
        filename = safe_filename(item.get("title") or os.path.basename(item["path"])) + ".flac"
    else:
        filename = os.path.basename(item["path"])
    return "%s/upnp/media/%s/%s" % (
        upnp_base_url(handler),
        item["id"],
        urllib.parse.quote(filename),
    )


def upnp_resource_size(item: Dict[str, Any], config: Dict[str, Any], transcode_to_audio: Callable) -> int:
    if item.get("cue_track"):
        try:
            target, _ = transcode_to_audio(item, config, "cue_flac")
            return os.path.getsize(target)
        except Exception:
            return 0
    try:
        return os.path.getsize(item["path"])
    except OSError:
        return 0


def soap_push(
    device: Dict[str, Any],
    item: Dict[str, Any],
    handler: Any,
    safe_filename: Callable[[str], str],
    upnp_base_url: Callable[[Any], str],
    transcode_to_audio: Callable,
):
    control = device.get("control_url")
    if not control:
        return False, "device has no AVTransport service"

    uri = upnp_media_url(handler, item, safe_filename, upnp_base_url)
    resource_mime = upnp_resource_mime(item)
    resource_protocol = protocol_info({**item, "mime": resource_mime}, device)
    resource_size = upnp_resource_size(item, handler.server.config, transcode_to_audio)
    duration_attr = ' duration="%s"' % html.escape(_dlna_duration(item.get("duration")), quote=True) if item.get("duration") else ""
    title = "%s - %s" % (item.get("artist") or "", item.get("title") or "")
    metadata = (
        '<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" '
        'xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">'
        '<item id="1" parentID="0" restricted="1"><dc:title>%s</dc:title>'
        "<dc:creator>%s</dc:creator>"
        "<upnp:artist>%s</upnp:artist>"
        "<upnp:album>%s</upnp:album>"
        "<upnp:class>object.item.audioItem.musicTrack</upnp:class>"
        '<res protocolInfo="%s" size="%s"%s>%s</res></item></DIDL-Lite>'
    ) % (
        html.escape(title),
        html.escape(str(item.get("artist") or "")),
        html.escape(str(item.get("artist") or "")),
        html.escape(str(item.get("album") or "")),
        html.escape(resource_protocol, quote=True),
        resource_size,
        duration_attr,
        html.escape(uri, quote=True),
    )
    escaped_uri = html.escape(uri, quote=True)
    escaped_meta = html.escape(metadata, quote=True)

    try:
        soap_request(control, "urn:schemas-upnp-org:service:AVTransport:1", "Stop", "<InstanceID>0</InstanceID>")
    except Exception:
        pass

    for action, args in (
        (
            "SetAVTransportURI",
            "<InstanceID>0</InstanceID><CurrentURI>%s</CurrentURI><CurrentURIMetaData>%s</CurrentURIMetaData>"
            % (escaped_uri, escaped_meta),
        ),
        ("Play", "<InstanceID>0</InstanceID><Speed>1</Speed>"),
    ):
        try:
            soap_request(control, "urn:schemas-upnp-org:service:AVTransport:1", action, args)
        except Exception as exc:
            return False, str(exc)
    return True, "pushed and started"


__all__ = [
    "DlnaMediaServer",
    "soap_push",
    "upnp_media_url",
    "upnp_resource_mime",
    "upnp_resource_size",
]
