from __future__ import annotations

import html
import math
import os
import urllib.parse
from typing import Any, Callable, Dict

from .control_point import soap_request
from .profiles import DSD_CAPABILITY_UNSUPPORTED, dsd_capability_state, protocol_info
from .text_policy import MAX_DLNA_ID_CHARS, dlna_text


def _dlna_duration(seconds: Any) -> str:
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float, str)):
        return "0:00:00"
    if isinstance(seconds, str) and len(seconds) > 64:
        return "0:00:00"
    try:
        numeric = float(seconds or 0)
        value = max(0, int(round(numeric))) if math.isfinite(numeric) else 0
    except (TypeError, ValueError, OverflowError):
        value = 0
    hours = value // 3600
    minutes = (value % 3600) // 60
    secs = value % 60
    return "%d:%02d:%02d" % (hours, minutes, secs)


def upnp_resource_mime(item: Dict[str, Any]) -> str:
    source = _source_path(item)
    if item.get("cue_track"):
        return "audio/flac"
    if item.get("is_dsd"):
        ext = os.path.splitext(source)[1].lower()
        return "audio/x-dsf" if ext == ".dsf" else "audio/x-dff" if ext == ".dff" else item.get("mime") or "audio/dsd"
    ext = os.path.splitext(source)[1].lower()
    # APE is served through the lossless FLAC compatibility resource.  The
    # DIDL metadata must describe the bytes the renderer will actually get.
    if ext == ".ape":
        return "audio/flac"
    if ext == ".dsf":
        return "audio/x-dsf"
    if ext == ".dff":
        return "audio/x-dff"
    return item.get("mime") or "application/octet-stream"


def _source_path(item: Dict[str, Any]) -> str:
    """Return the audio source path, or an empty string for a malformed row."""
    value = item.get("path") if isinstance(item, dict) else None
    return value if isinstance(value, str) else ""


def _url_id_segment(value: Any) -> str:
    """Encode one library ID as exactly one URL path segment.

    Scanner IDs are short hashes, but the DIDL is also built for queue and
    legacy rows whose ID can be arbitrary text.  The browse DIDL and the
    artwork URI already percent-encode it, and the renderer monitor decodes it
    again, so a raw ID here would be the one path that cannot round-trip.
    """
    return urllib.parse.quote(dlna_text(value, MAX_DLNA_ID_CHARS), safe="")


def upnp_media_url(
    handler: Any,
    item: Dict[str, Any],
    safe_filename: Callable[[str], str],
    upnp_base_url: Callable[[Any], str],
) -> str:
    source = _source_path(item)
    if item.get("cue_track"):
        filename = safe_filename(item.get("title") or os.path.basename(source)) + ".flac"
    elif os.path.splitext(source)[1].lower() == ".ape":
        filename = safe_filename(item.get("title") or os.path.splitext(os.path.basename(source))[0]) + ".flac"
    elif item.get("is_dsd"):
        source_ext = os.path.splitext(source)[1].lower() or ".dsf"
        filename = safe_filename(item.get("title") or os.path.splitext(os.path.basename(source))[0]) + source_ext
    else:
        filename = os.path.basename(source)
    url = "%s/upnp/media/%s/%s" % (
        upnp_base_url(handler),
        _url_id_segment(item.get("id")),
        urllib.parse.quote(filename),
    )
    return url


def upnp_resource_size(item: Dict[str, Any], config: Dict[str, Any], transcode_to_audio: Callable) -> int:
    source = _source_path(item)
    if item.get("cue_track"):
        try:
            target, _ = transcode_to_audio(item, config, "cue_flac")
            return os.path.getsize(target)
        except Exception:
            return 0
    if os.path.splitext(source)[1].lower() == ".ape":
        try:
            target, _ = transcode_to_audio(item, config, "ape_flac")
            return os.path.getsize(target)
        except Exception:
            return 0
    if item.get("is_dsd"):
        try:
            return os.path.getsize(source)
        except Exception:
            return 0
    try:
        return os.path.getsize(source)
    except OSError:
        return 0


def renderer_track_metadata(
    item: Dict[str, Any],
    uri: str,
    artwork_uri: str,
    resource_protocol: str,
    resource_size: int = 0,
    item_id: str = "1",
) -> str:
    """Build Renderer metadata in the same broad DIDL form as upmpdcli."""
    artist = dlna_text(item.get("artist"))
    title = dlna_text(item.get("title"))
    display_title = "%s - %s" % (artist, title) if artist else title
    duration_text = _dlna_duration(item.get("duration"))
    duration_attr = ' duration="%s"' % html.escape(duration_text, quote=True) if duration_text != "0:00:00" else ""
    try:
        numeric_size = int(resource_size) if not isinstance(resource_size, bool) else 0
    except (TypeError, ValueError, OverflowError):
        numeric_size = 0
    size_attr = ' size="%s"' % max(0, numeric_size) if numeric_size > 0 else ""
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" '
        'xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
        'xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/">'
        '<item id="%s" parentID="0" restricted="1" searchable="0">'
        '<dc:title>%s</dc:title>'
        '<upnp:class>object.item.audioItem.musicTrack</upnp:class>'
        '<upnp:album>%s</upnp:album>'
        '<res protocolInfo="%s"%s%s>%s</res>'
        '<dc:creator>%s</dc:creator>'
        '<upnp:artist>%s</upnp:artist>'
        '<upnp:albumArtURI>%s</upnp:albumArtURI>'
        '</item></DIDL-Lite>'
    ) % (
        html.escape(item_id, quote=True),
        html.escape(display_title),
        html.escape(dlna_text(item.get("album"))),
        html.escape(resource_protocol, quote=True),
        duration_attr,
        size_attr,
        html.escape(uri),
        html.escape(artist),
        html.escape(artist),
        html.escape(artwork_uri),
    )


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

    # Do not silently hand a DSD source to a renderer that explicitly
    # advertises no DSD sink profile.  Volumio treats this as a capability
    # negotiation failure instead of falling back to PCM; fnAudio follows the
    # same bit-perfect rule.  An unknown probe stays permissive so older
    # renderers can still be tried and diagnosed by the transport layer, which
    # is why the gate reads the three-state predicate instead of testing the
    # probe record for truthiness: a failed ConnectionManager request carries no
    # DSD claim at all, and silence must not be reported as a refusal.
    type_detection_enabled = (
        getattr(handler.server, "config", {}) or {}
    ).get("dlna_type_detection", True) is True
    if item.get("is_dsd") and type_detection_enabled:
        if dsd_capability_state(device) == DSD_CAPABILITY_UNSUPPORTED:
            return False, "设备不支持源码 DSD，已阻止 PCM 转码"

    uri = upnp_media_url(handler, item, safe_filename, upnp_base_url)
    resource_mime = upnp_resource_mime(item)
    resource_protocol = protocol_info({**item, "mime": resource_mime}, device)
    resource_size = upnp_resource_size(item, handler.server.config, transcode_to_audio)
    artwork_uri = "%s/upnp/cover/%s?size=160" % (
        upnp_base_url(handler),
        _url_id_segment(item.get("id")),
    )
    metadata = renderer_track_metadata(
        item,
        uri,
        artwork_uri,
        resource_protocol,
        resource_size,
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
    "soap_push",
    "renderer_track_metadata",
    "upnp_media_url",
    "upnp_resource_mime",
    "upnp_resource_size",
]
