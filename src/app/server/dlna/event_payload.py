"""Bounded, XML-safe projections for DLNA GENA event notifications."""

from __future__ import annotations

import html


# AVTransport LastChange escapes URI/metadata once for the inner XML and once
# more for the outer property. A quote can expand to ten ASCII bytes after the
# two passes. Keep the source budgets below the final 512 KiB cap even for
# deliberately escape-heavy controller metadata, rather than constructing a
# multi-megabyte body and discarding it afterwards.
MAX_EVENT_URI_CHARS = 4096
MAX_EVENT_METADATA_CHARS = 40 * 1024
MAX_EVENT_BODY_BYTES = 512 * 1024


def _text(value, limit):
    if not isinstance(value, str):
        return ""
    return value[:limit]


def _seconds(value):
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError, OverflowError):
        return 0


def _duration(value):
    seconds = _seconds(value)
    return "%d:%02d:%02d" % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)


def renderer_event_body(service, state):
    """Build a bounded GENA XML body without coercing arbitrary state values."""
    source = state if isinstance(state, dict) else {}
    if service == "rendering":
        volume = _seconds(source.get("volume"))
        raw_muted = source.get("muted")
        muted = raw_muted if isinstance(raw_muted, bool) else False
        properties = '<Volume channel="Master">%s</Volume><Mute channel="Master">%s</Mute>' % (min(100, volume), "1" if muted else "0")
    else:
        transport = _text(source.get("transport"), 64) or "STOPPED"
        uri = _text(source.get("uri"), MAX_EVENT_URI_CHARS)
        metadata = _text(source.get("metadata"), MAX_EVENT_METADATA_CHARS)
        inner = '<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/"><InstanceID val="0"><TransportState val="%s"/><CurrentTrackURI val="%s"/><CurrentTrackMetaData val="%s"/><RelativeTimePosition val="%s"/></InstanceID></Event>' % (
            html.escape(transport, quote=True),
            html.escape(uri, quote=True),
            html.escape(metadata, quote=True),
            _duration(source.get("position")),
        )
        properties = "<LastChange>%s</LastChange>" % html.escape(inner)
    body = ('<?xml version="1.0"?><e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0"><e:property>%s</e:property></e:propertyset>' % properties).encode("utf-8")
    return body if len(body) <= MAX_EVENT_BODY_BYTES else b""


__all__ = [
    "MAX_EVENT_BODY_BYTES",
    "MAX_EVENT_METADATA_CHARS",
    "MAX_EVENT_URI_CHARS",
    "renderer_event_body",
]
