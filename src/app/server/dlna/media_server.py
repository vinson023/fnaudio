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
    if item.get("is_dsd"):
        ext = os.path.splitext(item.get("path") or "")[1].lower()
        return "audio/x-dsf" if ext == ".dsf" else "audio/x-dff" if ext == ".dff" else item.get("mime") or "audio/dsd"
    ext = os.path.splitext(item["path"])[1].lower()
    # APE is served through the lossless FLAC compatibility resource.  The
    # DIDL metadata must describe the bytes the renderer will actually get.
    if ext == ".ape":
        return "audio/flac"
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
    elif os.path.splitext(item.get("path") or "")[1].lower() == ".ape":
        filename = safe_filename(item.get("title") or os.path.splitext(os.path.basename(item["path"]))[0]) + ".flac"
    elif item.get("is_dsd"):
        source_ext = os.path.splitext(item.get("path") or "")[1].lower() or ".dsf"
        filename = safe_filename(item.get("title") or os.path.splitext(os.path.basename(item["path"]))[0]) + source_ext
    else:
        filename = os.path.basename(item["path"])
    url = "%s/upnp/media/%s/%s" % (
        upnp_base_url(handler),
        item["id"],
        urllib.parse.quote(filename),
    )
    return url


def upnp_resource_size(item: Dict[str, Any], config: Dict[str, Any], transcode_to_audio: Callable) -> int:
    if item.get("cue_track"):
        try:
            target, _ = transcode_to_audio(item, config, "cue_flac")
            return os.path.getsize(target)
        except Exception:
            return 0
    if item.get("is_dsd"):
        try:
            return os.path.getsize(item["path"])
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
    next_item: Dict[str, Any] | None = None,
):
    control = device.get("control_url")
    if not control:
        return False, "device has no AVTransport service"

    # Do not silently hand a DSD source to a renderer that explicitly
    # advertises no DSD sink profile.  Volumio treats this as a capability
    # negotiation failure instead of falling back to PCM; fnAudio follows the
    # same bit-perfect rule.  An empty/unknown capability probe remains
    # permissive so older renderers can still be tried and diagnosed by the
    # transport layer.
    if item.get("is_dsd"):
        capabilities = device.get("capabilities") or {}
        protocol = capabilities.get("protocol_info") or {}
        if protocol and not bool(protocol.get("supports_dsd")):
            return False, "设备不支持源码 DSD，已阻止 PCM 转码"

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
        advertised_actions = set(((device.get("capabilities") or {}).get("actions") or []))
        can_set_next = not advertised_actions or "SetNextAVTransportURI" in advertised_actions
        if action == "SetAVTransportURI" and next_item and can_set_next:
            try:
                next_uri = upnp_media_url(handler, next_item, safe_filename, upnp_base_url)
                next_mime = upnp_resource_mime(next_item)
                next_protocol = protocol_info({**next_item, "mime": next_mime}, device)
                next_title = "%s - %s" % (next_item.get("artist") or "", next_item.get("title") or "")
                next_metadata = (
                    '<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" '
                    'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" '
                    'xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">'
                    '<item id="2" parentID="0" restricted="1"><dc:title>%s</dc:title>'
                    '<upnp:class>object.item.audioItem.musicTrack</upnp:class>'
                    '<res protocolInfo="%s">%s</res></item></DIDL-Lite>'
                ) % (html.escape(next_title), html.escape(next_protocol, quote=True), html.escape(next_uri, quote=True))
                soap_request(
                    control,
                    "urn:schemas-upnp-org:service:AVTransport:1",
                    "SetNextAVTransportURI",
                    "<InstanceID>0</InstanceID><NextURI>%s</NextURI><NextURIMetaData>%s</NextURIMetaData>"
                    % (html.escape(next_uri, quote=True), html.escape(next_metadata, quote=True)),
                )
            except Exception:
                # SetNextAVTransportURI is optional on many renderers. The
                # current track must still start when preloading is rejected.
                pass
    return True, "pushed and started"


__all__ = [
    "DlnaMediaServer",
    "soap_push",
    "upnp_media_url",
    "upnp_resource_mime",
    "upnp_resource_size",
]
