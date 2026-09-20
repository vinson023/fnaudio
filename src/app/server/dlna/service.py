from __future__ import annotations

import html
import math
import re
import threading
import time
import urllib.request
import uuid
from collections import deque
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Iterable, Tuple
from urllib.parse import quote, unquote
from resource_limits import ConcurrencyGate, ResourceLimitError
from .network import fetch_lan, lan_http_url, optional_lan_http_url
from .xml_policy import safe_fromstring
from .event_payload import renderer_event_body
from .text_policy import MAX_DLNA_ID_CHARS, dlna_text
from library_browse_rows import materialize_browse_rows
from library_query_spec import MAX_LIBRARY_OFFSET
from version import APP_VERSION


AVTRANSPORT = "urn:schemas-upnp-org:service:AVTransport:1"
RENDERING_CONTROL = "urn:schemas-upnp-org:service:RenderingControl:1"
CONNECTION_MANAGER = "urn:schemas-upnp-org:service:ConnectionManager:1"
CONTENT_DIRECTORY = "urn:schemas-upnp-org:service:ContentDirectory:1"
MAX_EVENT_COUNTER = 10**12
MAX_DLNA_ARGUMENT_CHARS = 8192
MAX_DLNA_SOAP_ARGUMENTS = 32
MAX_DLNA_ACTION_CHARS = 128
MAX_EVENT_SUBSCRIPTIONS = 64
# A GENA callback is validated by resolving its host, and ``getaddrinfo`` has no timeout of
# its own.  Measured: 16 simultaneous SUBSCRIBE put 16 of the 32 HTTP workers inside the
# resolver at once, so 32 of them would take the whole pool - the web UI, ``/api/health`` and
# the playback controls included.  The delivery path already caches validated addresses
# (`network.py:_cached_lan_addresses`); the accept path must not, because an answer that
# outlives the moment it was checked is how a callback gets pointed somewhere new.  So bound
# how many validations run at once instead of caching their results: at worst a quarter of the
# pool, with a short queue and a wait shorter than a resolver timeout, so an overflow is
# refused in about a second rather than stacking up behind a dead name.
GENA_VALIDATION_LIMIT = 4
GENA_VALIDATION_WAIT_SECONDS = 1.0
GENA_VALIDATION_WAITERS = 4
# The only Seek units this renderer can honour; a track or byte counter seek has
# no meaning without a track table, so it is refused rather than guessed at.
SEEK_UNITS = ("ABS_TIME", "REL_TIME")


def _next_event_sequence(value: Any) -> int:
    """Advance a GENA sequence without getting stuck at the safety ceiling."""
    if isinstance(value, bool):
        current = 0
    else:
        try:
            current = max(0, int(value))
        except (TypeError, ValueError, OverflowError):
            current = 0
    return 0 if current >= MAX_EVENT_COUNTER else current + 1


def _event_sequence(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        current = int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, min(MAX_EVENT_COUNTER, current))


def _is_count_number(value: Any, allow_string: bool = False) -> bool:
    """The one type gate the forgiving numeric readers share.

    ``bool`` is an ``int`` subclass, so a ``true`` from a device would otherwise read as
    a count of one; every reader here rejects it the same way.  Strings belong to the one
    reader that parses a UPnP field.  What happens *after* this gate stays per reader,
    because their contracts differ: some clamp to ``MAX_EVENT_COUNTER``, some fall back.
    None of them may convert a magnitude a float cannot hold, since ``float(10 ** 400)``
    raises ``OverflowError`` rather than returning ``inf``.
    """
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float, str) if allow_string else (int, float))


def _saturating_increment(value: Any, amount: int = 1) -> int:
    if not _is_count_number(value):
        value = 0
    try:
        current = max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        current = 0
    try:
        delta = max(0, int(amount))
    except (TypeError, ValueError, OverflowError):
        delta = 0
    return min(MAX_EVENT_COUNTER, current + delta)


def _safe_count(value: Any, fallback: int = 0) -> int:
    if not _is_count_number(value, allow_string=True):
        return fallback
    if isinstance(value, str) and len(value) > 64:
        return fallback
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    if not math.isfinite(number) or number < 0:
        return fallback
    return min(MAX_EVENT_COUNTER, int(number))


def _provider_browse_page(value: Any, rows_key: str) -> Tuple[Any, int | None]:
    """Split a browse provider result into its page rows and its stated total.

    Only a Mapping that carries the container's real total next to its own row
    list proves the read was bounded. Anything else - a plain row list from a
    provider that ignores the page, or a Mapping whose rows or total are
    unusable - comes back with no total, so the caller keeps owning the sort and
    the slice exactly as it did before the browse providers learned to page.
    """
    if isinstance(value, Mapping) and rows_key in value:
        total = _safe_count(value.get("count"), fallback=-1)
        if total >= 0:
            return value[rows_key], total
    return value, None


class UpnpActionError(ValueError):
    def __init__(self, code: int, description: str):
        super().__init__(description)
        self.code = int(code)


def _tag_name(tag: str) -> str:
    return str(tag or "").split("}")[-1]


def _duration(seconds: Any) -> str:
    if isinstance(seconds, bool):
        seconds = 0.0
    try:
        numeric = float(seconds or 0)
        seconds = max(0, int(numeric)) if math.isfinite(numeric) else 0
    except (TypeError, ValueError, OverflowError):
        seconds = 0
    return "%d:%02d:%02d" % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)


def _time_seconds(value: Any) -> float:
    """Parse one UPnP clock into seconds, or raise ``ValueError``.

    This is the strict half of the pair; :func:`_seconds` below is the projection
    half that turns an unreadable value into ``0`` because a status response must
    stay renderable.  A control that arrives from the network has to use the
    strict half, otherwise a malformed argument quietly becomes position zero.
    """
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("invalid UPnP time")
    match = re.match(r"^(\d+):(\d{1,2}):(\d{1,2})(?:\.(\d+))?$", value.strip())
    if not match:
        raise ValueError("invalid UPnP time")
    hours, minutes, seconds, fraction = match.groups()
    try:
        hours_value = int(hours)
        minutes_value = int(minutes)
        seconds_value = int(seconds)
        if minutes_value > 59 or seconds_value > 59:
            raise ValueError("invalid UPnP time")
        result = hours_value * 3600 + minutes_value * 60 + seconds_value + float("0." + (fraction or "0"))
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("invalid UPnP time") from error
    if not math.isfinite(result) or result > 24 * 60 * 60:
        raise ValueError("invalid UPnP time")
    return result


def _seconds(value: Any) -> float:
    """The forgiving clock reader used for projections: unreadable means zero."""
    try:
        return _time_seconds(value)
    except ValueError:
        return 0.0


def _finite(value: Any) -> float:
    if not _is_count_number(value):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        # `float(10 ** 400)` raises instead of producing an infinity, and the value this
        # reader is documented to forgive is every unreadable shape, not just the
        # non-numeric ones.  Answering the same way as `inf` and `nan` (zero) keeps a
        # large integer in the transport state from turning a projection into a 500.
        return 0.0
    return number if math.isfinite(number) else 0.0


def _seek_position(unit: Any, target: Any, position: Any, duration: Any) -> float:
    """Resolve a networked Seek into the absolute position the renderer should get.

    Two things used to go wrong here.  ``Unit`` was ignored, and every value the
    clock parser could not read collapsed to ``0.0``, so a controller asking for
    ``REL_TIME/+0:00:30`` (a legal thirty second fast forward) was rewound to the
    start of the track and answered 200 for it.  An unreadable argument is now an
    argument fault raised *before* the transport state moves.

    A leading ``+`` or ``-`` offsets from the position the backend just reported.
    An unsigned clock is absolute under either unit, because this server's own
    control point sends ``REL_TIME`` with an unsigned time
    (``control_point.upnp_control``) and refusing that would break fnAudio
    controlling fnAudio.  ``ABS_TIME`` never accepts a sign: that combination is
    self-contradictory, so it faults rather than guessing.
    """
    if unit is None:
        unit = ""
    if not isinstance(unit, str):
        raise ValueError("invalid Seek unit")
    normalized_unit = unit.strip().upper()
    if normalized_unit and normalized_unit not in SEEK_UNITS:
        raise ValueError("unsupported Seek unit")
    if not isinstance(target, str):
        raise ValueError("invalid Seek target")
    text = target.strip()
    sign = ""
    if text[:1] in ("+", "-"):
        sign, text = text[0], text[1:]
        if normalized_unit == "ABS_TIME":
            raise ValueError("signed target requires REL_TIME")
    try:
        seconds = _time_seconds(text)
    except ValueError as error:
        # Name the argument the controller actually sent: the fault string is what
        # a controller logs, and "invalid UPnP time" would not say which field.
        raise ValueError("invalid Seek target") from error
    if not sign:
        resolved = seconds
    else:
        base = _finite(position)
        resolved = base + seconds if sign == "+" else base - seconds
    resolved = max(0.0, resolved)
    known_duration = _finite(duration)
    if known_duration > 0:
        resolved = min(resolved, known_duration)
    return resolved


def _volume(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("invalid volume")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        try:
            number = int(value.strip())
        except (TypeError, ValueError, OverflowError):
            raise ValueError("invalid volume")
    else:
        raise ValueError("invalid volume")
    return max(0, min(100, number))


def _mute(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 32:
        raise ValueError("invalid mute value")
    normalized = value.strip().lower()
    if normalized in ("0", "false", "no", "off"):
        return False
    if normalized in ("1", "true", "yes", "on"):
        return True
    raise ValueError("invalid mute value")


def _soap_envelope(service: str, action: str, values: Dict[str, Any]) -> bytes:
    payload = "".join("<%s>%s</%s>" % (key, html.escape(str(value)), key) for key, value in values.items())
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        "<s:Body><u:%sResponse xmlns:u=\"%s\">%s</u:%sResponse></s:Body></s:Envelope>"
        % (action, service, payload, action)
    ).encode("utf-8")


def soap_fault(code: int, description: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><s:Fault>'
        "<faultcode>s:Client</faultcode><faultstring>UPnPError</faultstring>"
        '<detail><UPnPError xmlns="urn:schemas-upnp-org:control-1-0"><errorCode>%s</errorCode><errorDescription>%s</errorDescription></UPnPError></detail>'
        "</s:Fault></s:Body></s:Envelope>" % (int(code), html.escape(description))
    ).encode("utf-8")


def parse_soap_action(raw: bytes, soap_action_header: str = "") -> Tuple[str, Dict[str, str]]:
    root = safe_fromstring(raw)
    # The action is the Body's first element child. Walking the whole document
    # makes any controller that sends a SOAP <Header> resolve to the header
    # element instead, and every transport command then fails as
    # "unsupported action: Header". An empty header is enough to trigger it.
    body = next((node for node in root.iter() if _tag_name(node.tag) == "Body"), None)
    candidates = list(body) if body is not None else [root]
    action_node = next((node for node in candidates if _tag_name(node.tag) != "Header"), None)
    if action_node is None:
        raise ValueError("missing SOAP action")
    action = _tag_name(action_node.tag)
    if isinstance(soap_action_header, str) and "#" in soap_action_header:
        action = soap_action_header.strip().strip('"').rsplit("#", 1)[-1]
    if not action or len(action) > MAX_DLNA_ACTION_CHARS:
        raise ValueError("invalid SOAP action")
    arguments = {}
    for index, child in enumerate(action_node):
        if index >= MAX_DLNA_SOAP_ARGUMENTS:
            raise ValueError("too many SOAP arguments")
        name = _tag_name(child.tag)
        value = child.text or ""
        if not name or len(name) > MAX_DLNA_ACTION_CHARS or not isinstance(value, str) or len(value) > MAX_DLNA_ARGUMENT_CHARS:
            raise ValueError("invalid SOAP argument")
        arguments[name] = value
    return action, arguments


def scpd(service: str) -> bytes:
    # Controllers inspect SCPD before sending transport commands.  In
    # particular, Synology rejects an otherwise working renderer when the
    # advertised actions have no InstanceID/URI/Speed arguments or state
    # variables.  Keep this compact but standards-shaped rather than emitting
    # a placeholder action list.
    if service == AVTRANSPORT:
        specs = {
            "SetAVTransportURI": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("CurrentURI", "in", "AVTransportURI"), ("CurrentURIMetaData", "in", "AVTransportURIMetaData")),
            "SetNextAVTransportURI": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("NextURI", "in", "AVTransportURI"), ("NextURIMetaData", "in", "AVTransportURIMetaData")),
            "Play": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("Speed", "in", "TransportPlaySpeed")),
            "Pause": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"),),
            "Stop": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"),),
            "Next": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"),),
            "Previous": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"),),
            "Seek": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("Unit", "in", "A_ARG_TYPE_SeekMode"), ("Target", "in", "A_ARG_TYPE_SeekTarget")),
            "GetTransportInfo": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("CurrentTransportState", "out", "TransportState"), ("CurrentTransportStatus", "out", "TransportStatus"), ("CurrentSpeed", "out", "TransportPlaySpeed")),
            "GetPositionInfo": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("Track", "out", "A_ARG_TYPE_Track"), ("TrackDuration", "out", "CurrentTrackDuration"), ("TrackMetaData", "out", "CurrentTrackMetaData"), ("TrackURI", "out", "CurrentTrackURI"), ("RelTime", "out", "RelativeTimePosition"), ("AbsTime", "out", "AbsoluteTimePosition"), ("RelCount", "out", "RelativeCounterPosition"), ("AbsCount", "out", "AbsoluteCounterPosition")),
            "GetMediaInfo": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("NrTracks", "out", "NumberOfTracks"), ("MediaDuration", "out", "CurrentMediaDuration"), ("CurrentURI", "out", "AVTransportURI"), ("CurrentURIMetaData", "out", "AVTransportURIMetaData"), ("NextURI", "out", "AVTransportURI"), ("NextURIMetaData", "out", "AVTransportURIMetaData"), ("PlayMedium", "out", "PlaybackStorageMedium"), ("RecordMedium", "out", "RecordStorageMedium"), ("WriteStatus", "out", "RecordMediumWriteStatus")),
            "GetDeviceCapabilities": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("PlayMedia", "out", "PossiblePlaybackStorageMedia"), ("RecMedia", "out", "PossibleRecordStorageMedia"), ("RecQualityModes", "out", "PossibleRecordQualityModes")),
            "GetTransportSettings": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("PlayMode", "out", "CurrentPlayMode"), ("RecQualityMode", "out", "CurrentRecordQualityMode")),
            "SetPlayMode": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("NewPlayMode", "in", "CurrentPlayMode")),
        }
        states = {
            "A_ARG_TYPE_InstanceID": "ui4", "AVTransportURI": "string", "AVTransportURIMetaData": "string", "TransportPlaySpeed": "string", "TransportState": "string", "TransportStatus": "string", "A_ARG_TYPE_SeekMode": "string", "A_ARG_TYPE_SeekTarget": "string", "A_ARG_TYPE_Track": "ui4", "CurrentTrackDuration": "string", "CurrentTrackMetaData": "string", "CurrentTrackURI": "string", "RelativeTimePosition": "string", "AbsoluteTimePosition": "string", "RelativeCounterPosition": "i4", "AbsoluteCounterPosition": "i4", "NumberOfTracks": "ui4", "CurrentMediaDuration": "string", "PlaybackStorageMedium": "string", "RecordStorageMedium": "string", "RecordMediumWriteStatus": "string", "PossiblePlaybackStorageMedia": "string", "PossibleRecordStorageMedia": "string", "PossibleRecordQualityModes": "string", "CurrentPlayMode": "string", "CurrentRecordQualityMode": "string",
        }
    elif service == RENDERING_CONTROL:
        specs = {
            "GetVolume": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("Channel", "in", "A_ARG_TYPE_Channel"), ("CurrentVolume", "out", "Volume")),
            "SetVolume": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("Channel", "in", "A_ARG_TYPE_Channel"), ("DesiredVolume", "in", "Volume")),
            "GetMute": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("Channel", "in", "A_ARG_TYPE_Channel"), ("CurrentMute", "out", "Mute")),
            "SetMute": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("Channel", "in", "A_ARG_TYPE_Channel"), ("DesiredMute", "in", "Mute")),
            "ListPresets": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("CurrentPresetNameList", "out", "PresetNameList")),
            "SelectPreset": (("InstanceID", "in", "A_ARG_TYPE_InstanceID"), ("PresetName", "in", "A_ARG_TYPE_PresetName")),
        }
        states = {"A_ARG_TYPE_InstanceID": "ui4", "A_ARG_TYPE_Channel": "string", "Volume": "ui2", "Mute": "boolean", "PresetNameList": "string", "A_ARG_TYPE_PresetName": "string"}
    elif service == CONNECTION_MANAGER:
        specs = {
            "GetProtocolInfo": (("Source", "out", "SourceProtocolInfo"), ("Sink", "out", "SinkProtocolInfo")),
            "GetCurrentConnectionIDs": (("ConnectionIDs", "out", "CurrentConnectionIDs"),),
            "GetCurrentConnectionInfo": (("ConnectionID", "in", "A_ARG_TYPE_ConnectionID"), ("RcsID", "out", "A_ARG_TYPE_RcsID"), ("AVTransportID", "out", "A_ARG_TYPE_AVTransportID"), ("ProtocolInfo", "out", "A_ARG_TYPE_ProtocolInfo"), ("PeerConnectionManager", "out", "A_ARG_TYPE_ConnectionManager"), ("PeerConnectionID", "out", "A_ARG_TYPE_ConnectionID"), ("Direction", "out", "A_ARG_TYPE_Direction"), ("Status", "out", "A_ARG_TYPE_ConnectionStatus")),
        }
        states = {"SourceProtocolInfo": "string", "SinkProtocolInfo": "string", "CurrentConnectionIDs": "string", "A_ARG_TYPE_ConnectionID": "i4", "A_ARG_TYPE_RcsID": "i4", "A_ARG_TYPE_AVTransportID": "i4", "A_ARG_TYPE_ProtocolInfo": "string", "A_ARG_TYPE_ConnectionManager": "string", "A_ARG_TYPE_Direction": "string", "A_ARG_TYPE_ConnectionStatus": "string"}
    else:
        specs = {
            "Browse": (("ObjectID", "in", "A_ARG_TYPE_ObjectID"), ("BrowseFlag", "in", "A_ARG_TYPE_BrowseFlag"), ("Filter", "in", "A_ARG_TYPE_Filter"), ("StartingIndex", "in", "A_ARG_TYPE_Index"), ("RequestedCount", "in", "A_ARG_TYPE_Count"), ("SortCriteria", "in", "A_ARG_TYPE_SortCriteria"), ("Result", "out", "A_ARG_TYPE_Result"), ("NumberReturned", "out", "A_ARG_TYPE_Count"), ("TotalMatches", "out", "A_ARG_TYPE_Count"), ("UpdateID", "out", "A_ARG_TYPE_UpdateID")),
            "GetSearchCapabilities": (("SearchCaps", "out", "SearchCapabilities"),),
            "GetSortCapabilities": (("SortCaps", "out", "SortCapabilities"),),
            "GetSystemUpdateID": (("Id", "out", "SystemUpdateID"),),
        }
        states = {"A_ARG_TYPE_ObjectID": "string", "A_ARG_TYPE_BrowseFlag": "string", "A_ARG_TYPE_Filter": "string", "A_ARG_TYPE_Index": "ui4", "A_ARG_TYPE_Count": "ui4", "A_ARG_TYPE_SortCriteria": "string", "A_ARG_TYPE_Result": "string", "A_ARG_TYPE_UpdateID": "ui4", "SearchCapabilities": "string", "SortCapabilities": "string", "SystemUpdateID": "ui4"}
    actions = "".join(
        "<action><name>%s</name><argumentList>%s</argumentList></action>" % (
            name,
            "".join("<argument><name>%s</name><direction>%s</direction><relatedStateVariable>%s</relatedStateVariable></argument>" % arg for arg in arguments),
        )
        for name, arguments in specs.items()
    )
    # The SCPD is a self-declaration: a control point may build its seek UI from the
    # values listed here instead of letting the user type anything.  The list is read
    # from ``SEEK_UNITS``, the very tuple ``_seek_position`` validates against, so the
    # declaration and the handler cannot drift apart into "advertised but refused" or
    # "accepted but undeclared".
    allowed_values = {"A_ARG_TYPE_SeekMode": SEEK_UNITS}
    state_table = "".join(
        "<stateVariable sendEvents=\"no\"><name>%s</name><dataType>%s</dataType>%s</stateVariable>" % (
            name,
            data_type,
            "".join("<allowedValue>%s</allowedValue>" % value for value in allowed_values.get(name, ())),
        )
        for name, data_type in states.items()
    )
    return (
        '<?xml version="1.0"?><scpd xmlns="urn:schemas-upnp-org:service-1-0">'
        "<specVersion><major>1</major><minor>0</minor></specVersion><actionList>%s</actionList><serviceStateTable>%s</serviceStateTable></scpd>" % (actions, state_table)
    ).encode("utf-8")


class DlnaEventService:
    """Small UPnP eventing implementation for renderer state changes."""

    def __init__(self, max_workers=4, max_pending=64):
        self._lock = threading.RLock()
        self._delivery_ready = threading.Condition(self._lock)
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        self._max_workers = self._bounded_limit(max_workers, 4, 1, 8)
        self._max_pending = self._bounded_limit(max_pending, 64, 1, 256)
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers, thread_name_prefix="fnaudio-gena")
        # ThreadPoolExecutor deliberately uses an unbounded internal queue.
        # Bound work before submit so a noisy renderer cannot retain an
        # arbitrary number of controller notification bodies in memory.
        self._pending_notifications = 0
        self._active_notifications = 0
        self._peak_notifications = 0
        self._accepted_notifications = 0
        self._dropped_notifications = 0
        self._shutdown = False
        self._validation_gate = ConcurrencyGate("gena-callback", max_waiters=GENA_VALIDATION_WAITERS)

    @staticmethod
    def _bounded_limit(value: Any, default: int, minimum: int, maximum: int) -> int:
        if isinstance(value, bool):
            return default
        try:
            number = int(value)
        except (TypeError, ValueError, OverflowError):
            return default
        return max(minimum, min(maximum, number))

    def _hopeless_admission_reason(self) -> str:
        """Return why a new subscription cannot be admitted, or "" when it still might.

        Runs *before* the callback host is resolved.  Resolving costs a worker for as long as
        the resolver takes, so paying for it to learn something this object already knows is
        the waste `:22` described.  The answer must only be non-empty when refusal is
        certain: this holds the lock for a dictionary scan and touches no I/O, and the
        authoritative sweep and cap check still run after validation, so a race between two
        controllers is settled by the real check rather than by this one.
        """
        now = time.monotonic()
        with self._lock:
            if self._shutdown:
                return "the event service is shutting down"
            if len(self._subscriptions) < MAX_EVENT_SUBSCRIPTIONS:
                return ""
            if any(item.get("expires", 0) <= now for item in self._subscriptions.values()):
                # The sweep inside the real admission path would reclaim these slots, so this
                # request may well succeed and must still be resolved.
                return ""
        return "too many event subscriptions"

    def _sweep_expired_locked(self, now: float) -> None:
        """Drop lapsed leases and release the bodies still queued for them.

        The caller must hold ``self._lock``.  Admission needs this on its own
        terms: the cap counts slots, and a controller that subscribes and then
        vanished kept its slot until some unrelated path happened to sweep, so
        with an idle renderer and the UI closed nothing did and the table stayed
        full of dead leases.
        """
        expired = [sid for sid, item in self._subscriptions.items() if item.get("expires", 0) <= now]
        released = 0
        for sid in expired:
            item = self._subscriptions.pop(sid, None)
            if item:
                released += len(item.get("deliveries") or ())
        if expired:
            if released:
                self._pending_notifications = max(0, self._pending_notifications - released)
            self._delivery_ready.notify_all()

    def subscribe(self, role: str, service: str, callback: str, sid: str, timeout_header: str) -> Tuple[str, int]:
        if role != "renderer" or service not in ("avtransport", "rendering"):
            raise ValueError("eventing is not available for this service")
        timeout = self._timeout(timeout_header)
        endpoint = ""
        if not sid:
            certain = self._hopeless_admission_reason()
            if certain:
                raise ValueError(certain)
            # Validate the callback *before* taking the lock.  The check resolves
            # the host, and ``socket.getaddrinfo`` has no timeout of its own: a
            # controller naming a host on a broken resolver can block for the
            # full resolver timeout, and this is the lock every subscription,
            # renewal and renderer notification also needs.  Moving it out is safe
            # because the check is a property of the URL, not of shared state.  The gate is
            # the only thing standing between one controller's dead hostname and every other
            # request this server can no longer answer.
            try:
                with self._validation_gate.slot(GENA_VALIDATION_LIMIT, GENA_VALIDATION_WAIT_SECONDS):
                    endpoint = self._callback_url(callback)
            except ResourceLimitError as exc:
                # Same shape as every other rejection on this path: a reason string, which
                # the HTTP layer turns into a 412.  A saturated validator means busy, not
                # invalid, so the controller is free to retry.
                raise ValueError("event callback validation is busy") from exc
        with self._lock:
            if sid:
                item = self._subscriptions.get(sid)
                if not item or item.get("expires", 0) <= time.monotonic():
                    if item:
                        self._subscriptions.pop(sid, None)
                        self._pending_notifications = max(
                            0, self._pending_notifications - len(item.get("deliveries") or ())
                        )
                    raise ValueError("unknown subscription")
                item["expires"] = time.monotonic() + timeout
                return sid, timeout
            now = time.monotonic()
            self._sweep_expired_locked(now)
            if len(self._subscriptions) >= MAX_EVENT_SUBSCRIPTIONS:
                raise ValueError("too many event subscriptions")
            sid = "uuid:%s" % uuid.uuid4()
            self._subscriptions[sid] = {
                "role": role, "service": service, "callback": endpoint,
                "expires": now + timeout, "sequence": 0,
                "deliveries": deque(), "delivery_scheduled": False,
            }
        return sid, timeout

    def unsubscribe(self, sid: str) -> bool:
        with self._lock:
            removed_item = self._subscriptions.pop(str(sid or ""), None)
            if removed_item:
                self._pending_notifications = max(
                    0, self._pending_notifications - len(removed_item.get("deliveries") or ())
                )
            removed = removed_item is not None
            self._delivery_ready.notify_all()
            return removed

    def notify_renderer(self, state: Dict[str, Any]) -> None:
        with self._lock:
            if self._shutdown:
                return
            now = time.monotonic()
            self._sweep_expired_locked(now)
            subscriptions = [(sid, dict(item)) for sid, item in self._subscriptions.items()]
        for sid, item in subscriptions:
            body = self._body(item["service"], state)
            with self._lock:
                current = self._subscriptions.get(sid)
                if not current or self._shutdown:
                    continue
                # Body construction happens outside the lock and may cross
                # the lease boundary. Do not admit a notification for a
                # subscription that expired while it was being built.
                if current.get("expires", 0) <= time.monotonic():
                    self._subscriptions.pop(sid, None)
                    self._pending_notifications = max(
                        0, self._pending_notifications - len(current.get("deliveries") or ())
                    )
                    continue
                if self._pending_notifications >= self._max_pending:
                    self._dropped_notifications = _saturating_increment(self._dropped_notifications)
                    continue
                sequence = _event_sequence(current.get("sequence"))
                current["sequence"] = _next_event_sequence(sequence)
                deliveries = current.get("deliveries")
                if not isinstance(deliveries, deque):
                    deliveries = deque()
                    current["deliveries"] = deliveries
                deliveries.append((item, sequence, body))
                self._pending_notifications += 1
                self._peak_notifications = min(MAX_EVENT_COUNTER, max(self._peak_notifications, self._pending_notifications))
                self._accepted_notifications = _saturating_increment(self._accepted_notifications)
                if current.get("delivery_scheduled"):
                    continue
                current["delivery_scheduled"] = True
            try:
                self._executor.submit(self._drain_subscription, sid)
            except Exception:
                with self._lock:
                    current = self._subscriptions.get(sid)
                    dropped = 0
                    if current:
                        deliveries = current.get("deliveries")
                        if isinstance(deliveries, deque):
                            dropped = len(deliveries)
                            deliveries.clear()
                        current["delivery_scheduled"] = False
                    # A concurrent notification can append to this mailbox
                    # after it is scheduled but before submit() fails. Release
                    # every discarded body, not only the one that initiated
                    # the submission, so admission pressure remains truthful.
                    if dropped:
                        self._pending_notifications = max(0, self._pending_notifications - dropped)
                        self._dropped_notifications = _saturating_increment(self._dropped_notifications, dropped)

    def snapshot(self) -> Dict[str, int]:
        """Expose bounded eventing pressure counters without callback URLs."""
        # Read the validator's own counters *before* taking the bus lock: the gate has its
        # own condition, and no path may hold one while waiting on the other.
        validating = self._validation_gate.snapshot()
        with self._lock:
            self._sweep_expired_locked(time.monotonic())
            return {
                "subscriptions": len(self._subscriptions),
                "subscription_limit": MAX_EVENT_SUBSCRIPTIONS,
                "workers": self._active_notifications,
                "worker_limit": self._max_workers,
                "pending": self._pending_notifications,
                "pending_limit": self._max_pending,
                "peak_pending": self._peak_notifications,
                "accepted": self._accepted_notifications,
                "dropped": self._dropped_notifications,
                "validating": validating["active"],
                "validation_limit": GENA_VALIDATION_LIMIT,
                "validation_waiter_limit": validating["waiter_limit"],
                "validation_waited": validating["waited"],
                "validation_rejected": validating["rejected"],
            }

    @staticmethod
    def _timeout(value: str) -> int:
        match = re.search(r"Second-(\d+)", str(value or ""), re.I)
        seconds = int(match.group(1)) if match else 1800
        return max(30, min(86400, seconds))

    @staticmethod
    def _callback_url(value: str) -> str:
        match = re.search(r"<([^>]+)>", str(value or ""))
        endpoint = match.group(1).strip() if match else ""
        return lan_http_url(endpoint)

    @staticmethod
    def _body(service: str, state: Dict[str, Any]) -> bytes:
        return renderer_event_body(service, state)

    def _drain_subscription(self, sid: str) -> None:
        """Deliver one subscription serially without parking executor workers."""
        while True:
            with self._lock:
                current = self._subscriptions.get(sid)
                if self._shutdown or current is None:
                    return
                if current.get("expires", 0) <= time.monotonic():
                    self._subscriptions.pop(sid, None)
                    self._pending_notifications = max(
                        0, self._pending_notifications - len(current.get("deliveries") or ())
                    )
                    self._delivery_ready.notify_all()
                    return
                deliveries = current.get("deliveries")
                if not isinstance(deliveries, deque) or not deliveries:
                    current["delivery_scheduled"] = False
                    return
                item, sequence, body = deliveries.popleft()
                self._active_notifications += 1
            try:
                request = urllib.request.Request(item["callback"], data=body, method="NOTIFY")
                request.add_header("CONTENT-TYPE", "text/xml; charset=utf-8")
                request.add_header("NT", "upnp:event")
                request.add_header("NTS", "upnp:propchange")
                request.add_header("SID", sid)
                request.add_header("SEQ", str(sequence))
                fetch_lan(request, timeout=3, max_bytes=4096)
            except Exception:
                # Controllers can disappear without unsubscribing. The lease will
                # expire naturally and a failed callback must not affect playback.
                pass
            finally:
                with self._lock:
                    self._active_notifications = max(0, self._active_notifications - 1)
                    self._pending_notifications = max(0, self._pending_notifications - 1)
                    self._delivery_ready.notify_all()

    def shutdown(self, wait=True, timeout=3.0) -> None:
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            self._subscriptions.clear()
            self._pending_notifications = 0
            self._delivery_ready.notify_all()
        # ``ThreadPoolExecutor.shutdown`` has no timeout. Cancel queued work
        # first, then wait only for the requested interval so an unreachable
        # controller cannot make service shutdown unbounded.
        self._executor.shutdown(wait=False, cancel_futures=True)
        if not wait:
            return
        try:
            bounded_timeout = float(timeout)
        except (TypeError, ValueError, OverflowError):
            bounded_timeout = 3.0
        if not math.isfinite(bounded_timeout):
            bounded_timeout = 3.0
        deadline = time.monotonic() + max(0.0, bounded_timeout)
        with self._lock:
            while self._active_notifications > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._delivery_ready.wait(timeout=remaining)


class DlnaProtocolService:
    """HTTP/SOAP surface for fnAudio's MediaServer and MediaRenderer roles."""

    def __init__(
        self,
        base_url: Callable[[], str],
        renderer: Any,
        library_page: Callable[[Dict[str, Any]], Dict[str, Any]],
        # Browse providers take their container identity plus an optional
        # bounded page ("limit", "offset", "sort_dir"). A provider that answers
        # a bounded read with {"<rows>": ..., "count": ...} states the true
        # table total; one that ignores the page still returns the whole row
        # list and keeps the historical whole-table path.
        library_groups: Callable[..., Any],
        media_mime: Callable[[Dict[str, Any]], str],
        library_roots: Callable[[], Iterable[Dict[str, Any]]] | None = None,
        library_folders: Callable[..., Any] | None = None,
        output_capabilities: Callable[[], Dict[str, Any]] | None = None,
        library_item: Callable[[str], Dict[str, Any] | None] | None = None,
        system_update_id: Callable[[], int] | None = None,
    ):
        self.base_url = base_url
        self.renderer = renderer
        self.library_page = library_page
        self.library_groups = library_groups
        self.media_mime = media_mime
        self.library_roots = library_roots or (lambda: [])
        self.library_folders = library_folders or (lambda parent, root: [])
        self.output_capabilities = output_capabilities or (lambda: {})
        self.library_item = library_item or (lambda item_id: None)
        self.system_update_id = system_update_id or (lambda: 1)
        self.events = DlnaEventService()
        self.renderer.add_state_listener(self.events.notify_renderer)

    def subscribe(self, role: str, service: str, callback: str, sid: str, timeout: str) -> Tuple[str, int]:
        return self.events.subscribe(role, service, callback, sid, timeout)

    def unsubscribe(self, sid: str) -> bool:
        return self.events.unsubscribe(sid)

    def event_status(self) -> Dict[str, int]:
        return self.events.snapshot()

    def shutdown(self) -> None:
        self.events.shutdown()

    def description(self, role: str) -> bytes:
        is_renderer = role == "renderer"
        # Must match the UUID advertised by SSDP. Strict DLNA controllers reject
        # a device description whose UDN differs from the SSDP USN.
        udn = str(uuid.uuid5(uuid.NAMESPACE_URL, self.base_url().rstrip("/") + "/" + role))
        device_type = "MediaRenderer:1" if is_renderer else "MediaServer:1"
        services = ((AVTRANSPORT, "avtransport"), (RENDERING_CONTROL, "rendering"), (CONNECTION_MANAGER, "connection")) if is_renderer else ((CONTENT_DIRECTORY, "content"), (CONNECTION_MANAGER, "connection"))
        rows = []
        for service_type, name in services:
            prefix = "/dlna/%s" % role
            rows.append("<service><serviceType>%s</serviceType><serviceId>urn:upnp-org:serviceId:%s</serviceId><SCPDURL>/dlna/scpd/%s.xml</SCPDURL><controlURL>%s/%s/control</controlURL><eventSubURL>%s/%s/event</eventSubURL></service>" % (service_type, name, name, prefix, name, prefix, name))
        friendly = "fnAudio Renderer" if is_renderer else "fnAudio Music Library"
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<root xmlns="urn:schemas-upnp-org:device-1-0"><specVersion><major>1</major><minor>0</minor></specVersion>'
            "<device><deviceType>urn:schemas-upnp-org:device:%s</deviceType><friendlyName>%s</friendlyName><manufacturer>fnaudio</manufacturer><modelName>fnAudio</modelName><modelNumber>%s</modelNumber><UDN>uuid:%s</UDN><serviceList>%s</serviceList></device></root>"
            % (device_type, friendly, APP_VERSION, udn, "".join(rows))
        ).encode("utf-8")

    def control(self, role: str, service_name: str, raw: bytes, header: str = "") -> Tuple[int, bytes]:
        try:
            action, args = parse_soap_action(raw, header)
            service = self._service_for(role, service_name)
            values = self._dispatch(role, service, action, args)
            return 200, _soap_envelope(service, action, values)
        except UpnpActionError as exc:
            return 500, soap_fault(exc.code, str(exc))
        except ValueError as exc:
            return 500, soap_fault(402, str(exc))
        except Exception as exc:
            return 500, soap_fault(501, str(exc))

    def _service_for(self, role: str, name: str) -> str:
        mapping = {"avtransport": AVTRANSPORT, "rendering": RENDERING_CONTROL, "connection": CONNECTION_MANAGER, "content": CONTENT_DIRECTORY}
        service = mapping.get(name)
        if not service or (role == "renderer" and service == CONTENT_DIRECTORY) or (role == "server" and service in (AVTRANSPORT, RENDERING_CONTROL)):
            raise ValueError("invalid DLNA service")
        return service

    def _dispatch(self, role: str, service: str, action: str, args: Dict[str, str]) -> Dict[str, Any]:
        if service == CONNECTION_MANAGER:
            if action == "GetProtocolInfo":
                source = self.protocol_info("server")
                sink = self.protocol_info("renderer") if role == "renderer" else ""
                return {"Source": source if role == "server" else "", "Sink": sink}
            if action == "GetCurrentConnectionIDs":
                return {"ConnectionIDs": "0"}
            if action == "GetCurrentConnectionInfo":
                return {"RcsID": "0", "AVTransportID": "0", "ProtocolInfo": "", "PeerConnectionManager": "", "PeerConnectionID": "-1", "Direction": "Input" if role == "renderer" else "Output", "Status": "OK"}
        if role == "server" and service == CONTENT_DIRECTORY:
            if action == "Browse":
                return self._browse(args)
            if action == "GetSearchCapabilities":
                # Do not advertise Search until the complete ContentDirectory
                # Search action and grammar are implemented. Strict clients
                # such as UAPP otherwise issue Search after discovery and
                # reject the server when it returns an unsupported-action fault.
                return {"SearchCaps": ""}
            if action == "GetSortCapabilities":
                return {"SortCaps": "dc:title,upnp:artist,upnp:album"}
            if action == "GetSystemUpdateID":
                return {"Id": str(self._update_id())}
        if role != "renderer":
            raise ValueError("unsupported MediaServer action")
        state = self.renderer.snapshot()
        if service == AVTRANSPORT:
            if action == "SetAVTransportURI":
                self.renderer.set_uri(optional_lan_http_url(args.get("CurrentURI", "")), args.get("CurrentURIMetaData", ""))
                return {}
            if action == "SetNextAVTransportURI":
                self.renderer.set_next_uri(optional_lan_http_url(args.get("NextURI", "")), args.get("NextURIMetaData", ""))
                return {}
            if action == "Play":
                return self._result(self.renderer.command("play"))
            if action == "Pause":
                return self._result(self.renderer.command("pause"))
            if action == "Stop":
                return self._result(self.renderer.command("stop"))
            if action == "Next":
                return self._result(self.renderer.command("next"))
            if action == "Previous":
                return self._result(self.renderer.command("previous"))
            if action == "Seek":
                target = _seek_position(args.get("Unit"), args.get("Target"), state["position"], state["duration"])
                return self._result(self.renderer.command("seek", target))
            if action == "GetTransportInfo":
                return {"CurrentTransportState": state["transport"], "CurrentTransportStatus": "OK", "CurrentSpeed": "1"}
            if action == "GetPositionInfo":
                return {"Track": "1", "TrackDuration": _duration(state["duration"]), "TrackMetaData": state["metadata"], "TrackURI": state["uri"], "RelTime": _duration(state["position"]), "AbsTime": _duration(state["position"]), "RelCount": "2147483647", "AbsCount": "2147483647"}
            if action == "GetMediaInfo":
                return {"NrTracks": "1" if state["uri"] else "0", "MediaDuration": _duration(state["duration"]), "CurrentURI": state["uri"], "CurrentURIMetaData": state["metadata"], "NextURI": state.get("next_uri", ""), "NextURIMetaData": state.get("next_metadata", ""), "PlayMedium": "NETWORK", "RecordMedium": "NOT_IMPLEMENTED", "WriteStatus": "NOT_IMPLEMENTED"}
            if action == "GetDeviceCapabilities":
                return {"PlayMedia": "NETWORK", "RecMedia": "NOT_IMPLEMENTED", "RecQualityModes": "NOT_IMPLEMENTED"}
            if action == "GetTransportSettings":
                return {"PlayMode": "NORMAL", "RecQualityMode": "NOT_IMPLEMENTED"}
            if action == "SetPlayMode":
                return {}
        if service == RENDERING_CONTROL:
            if action == "GetVolume":
                return {"CurrentVolume": str(state["volume"])}
            if action == "SetVolume":
                return self._result(self.renderer.set_volume(_volume(args.get("DesiredVolume", ""))))
            if action == "GetMute":
                return {"CurrentMute": "1" if state["muted"] else "0"}
            if action == "SetMute":
                return self._result(self.renderer.set_mute(_mute(args.get("DesiredMute", "0"))))
            if action == "ListPresets":
                return {"CurrentPresetNameList": "FactoryDefaults"}
            if action == "SelectPreset":
                return {}
        raise ValueError("unsupported action: %s" % action)

    @staticmethod
    def _result(result: Dict[str, Any]) -> Dict[str, Any]:
        if result.get("ok") is False:
            raise ValueError(str(result.get("message") or "playback failed"))
        return {}

    def _browse(self, args: Dict[str, str]) -> Dict[str, Any]:
        object_id = dlna_text(args.get("ObjectID"), MAX_DLNA_ARGUMENT_CHARS, "0")
        browse_flag = dlna_text(args.get("BrowseFlag"), 128, "BrowseDirectChildren")
        if browse_flag not in ("BrowseMetadata", "BrowseDirectChildren"):
            raise UpnpActionError(402, "Invalid BrowseFlag")
        try:
            start = int(args.get("StartingIndex") or 0)
            requested_value = int(args.get("RequestedCount") or 0)
        except (TypeError, ValueError):
            raise UpnpActionError(402, "Invalid paging arguments")
        if start < 0 or requested_value < 0:
            raise UpnpActionError(402, "Invalid paging arguments")
        # UPnP defines RequestedCount=0 as all remaining entries. Keep the
        # response bounded while still returning every child for small
        # containers; clients can continue from NumberReturned for large ones.
        requested = min(500, requested_value or 500)
        filter_fields = self._filter_fields(args.get("Filter", "*"))
        sort_key, sort_dir = self._sort_criteria(args.get("SortCriteria", ""))
        if browse_flag == "BrowseMetadata":
            xml = self._metadata_for_object(object_id, filter_fields)
            didl = self._didl(xml)
            return {"Result": didl, "NumberReturned": "1", "TotalMatches": "1", "UpdateID": str(self._update_id())}
        if object_id.startswith(("albums:", "artists:", "genres:", "folders-root:", "folder:")):
            self._metadata_for_object(object_id, filter_fields)
        returned = None
        if object_id == "0":
            entries = [("music", "Music", "object.container"), ("albums", "Albums", "object.container.album.musicAlbum"), ("artists", "Artists", "object.container.person.musicArtist"), ("genres", "Genres", "object.container.genre.musicGenre"), ("folders", "Folders", "object.container.storageFolder")]
            entries = self._sort_rows(entries, sort_key, sort_dir, lambda row, key: row[1])
            page = entries[start:start + requested]
            xml = "".join(self._container(item_id, "0", title, kind) for item_id, title, kind in page)
            total = len(entries)
        elif object_id in ("albums", "artists", "genres"):
            page, total = self._group_page(object_id, start, requested, sort_key, sort_dir)
            xml = "".join(
                self._container(
                    "%s:%s" % (object_id, quote(dlna_text(row.get("name"), MAX_DLNA_ID_CHARS), safe="")),
                    object_id,
                    dlna_text(row.get("name")),
                    "object.container",
                )
                for row in page
            )
        elif object_id == "folders":
            roots = materialize_browse_rows(self.library_roots())
            roots = self._sort_rows(roots, sort_key, sort_dir, lambda row, key: row.get("name") or row.get("root") or "")
            page = roots[start:start + requested]
            xml = "".join(
                self._folder_container(
                    "folders-root:%s" % quote(dlna_text(row.get("root") or row.get("path"), MAX_DLNA_ID_CHARS), safe=""),
                    "folders",
                    dlna_text(row.get("name") or row.get("root") or row.get("path"), fallback="Music"),
                )
                for row in page
            )
            total = len(roots)
        elif object_id.startswith("folders-root:") or object_id.startswith("folder:"):
            try:
                root, parent = self._folder_target(object_id)
            except ValueError:
                raise UpnpActionError(701, "No such object")
            page_folders, folder_total = self._folder_page(root, parent, start, requested, sort_key, sort_dir)
            xml = "".join(
                self._folder_container(
                    "folder:%s:%s" % (
                        quote(dlna_text(root, MAX_DLNA_ID_CHARS), safe=""),
                        quote(dlna_text(row.get("path"), MAX_DLNA_ID_CHARS), safe=""),
                    ),
                    object_id,
                    dlna_text(row.get("name"), fallback="Folder"),
                )
                for row in page_folders
            )
            track_offset = max(0, start - folder_total)
            remaining = max(0, requested - len(page_folders))
            # The track read happens even when the folder rows already fill the
            # window, because the count it reports belongs to this container's
            # total: a total that stops at the folder list makes a controller
            # stop paging before the first track. Only the probe row is dropped.
            item_page = self.library_page({"view": "folders", "root": root, "folder": parent, "sort": sort_key, "dir": sort_dir, "limit": max(1, remaining), "offset": track_offset}) or {}
            tracks = (item_page.get("items") or []) if remaining else []
            # A folder can contain subfolders and tracks. Direct children are
            # always returned in that order, consistent with fnAudio's UI.
            xml += "".join(self._didl_item(item, object_id, filter_fields) for item in tracks)
            total = folder_total + _safe_count(item_page.get("count"), len(tracks))
            returned = len(page_folders) + len(tracks)
        elif object_id == "music" or object_id.startswith(("albums:", "artists:", "genres:")):
            params: Dict[str, Any] = {"view": "all", "sort": sort_key, "dir": sort_dir, "limit": requested, "offset": start}
            if object_id != "music":
                view, group = object_id.split(":", 1)
                params.update({"view": view, "group": unquote(group)})
            page = self.library_page(params)
            items = page.get("items") or []
            xml = "".join(self._didl_item(item, object_id, filter_fields) for item in items)
            total = _safe_count(page.get("count"), len(items))
        elif self.library_item(object_id):
            raise UpnpActionError(710, "Object is not a container")
        else:
            raise UpnpActionError(701, "No such object")
        didl = self._didl(xml)
        return {"Result": didl, "NumberReturned": str(returned if returned is not None else min(requested, max(0, total - start))), "TotalMatches": str(total), "UpdateID": str(self._update_id())}

    def _group_page(self, view: str, start: int, requested: int, sort_key: str, sort_dir: str) -> Tuple[list, int]:
        """Read one page of group containers together with the whole-table total.

        `query_library_groups` already orders by `name COLLATE NOCASE` and
        states the full count next to the page, so the read can stop at the
        requested window. The unbounded read has to materialize the table
        first, and that materialization is capped: past the cap this container
        reports a total equal to the cap and every later group becomes
        unreachable for the controller. Two cases keep the whole-table path - a
        provider that does not prove its read was bounded, and listing albums
        by artist, where the group name is not the value being sorted.
        """
        paged = sort_key != "artist" and start <= MAX_LIBRARY_OFFSET
        if paged:
            rows, total = _provider_browse_page(
                self.library_groups(view, limit=requested, offset=start, sort_dir=sort_dir),
                "groups",
            )
            paged = total is not None
        if not paged:
            groups = self._sort_rows(
                materialize_browse_rows(self.library_groups(view)),
                sort_key,
                sort_dir,
                lambda row, key: row.get({"title": "name", "artist": "artist", "album": "name"}.get(key, "name")) or "",
            )
            return groups[start:start + requested], len(groups)
        return materialize_browse_rows(rows), total

    def _folder_page(self, root: str, parent: str, start: int, requested: int, sort_key: str, sort_dir: str) -> Tuple[list, int]:
        """Read one page of subfolders together with the sibling total.

        `query_library_folders` orders by the folder name - the order this
        container has always shown, which is why the caller's sort key is not
        forwarded - and states the sibling count next to the page. Without that
        page the folder list is materialized first, so a directory with more
        subfolders than the materialization cap reports a total that stops at
        the cap and hides both the remaining folders and the tracks behind them.
        """
        paged = start <= MAX_LIBRARY_OFFSET
        if paged:
            rows, total = _provider_browse_page(
                self.library_folders(parent, root, limit=requested, offset=start, sort_dir=sort_dir),
                "folders",
            )
            paged = total is not None
        if not paged:
            folders = self._sort_rows(
                materialize_browse_rows(self.library_folders(parent, root)),
                sort_key,
                sort_dir,
                lambda row, key: row.get("name") or "",
            )
            return folders[start:start + requested], len(folders)
        return materialize_browse_rows(rows), total

    @staticmethod
    def _didl(xml: str) -> str:
        return '<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/" xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">%s</DIDL-Lite>' % xml

    @staticmethod
    def _filter_fields(value: str) -> set[str]:
        raw = dlna_text(value, MAX_DLNA_ARGUMENT_CHARS, "*")
        fields = {entry.strip().lower() for entry in raw.split(",") if entry.strip()}
        return fields or {"*"}

    @staticmethod
    def _sort_criteria(value: str) -> Tuple[str, str]:
        raw = dlna_text(value, 1024).strip()
        if not raw:
            return "title", "asc"
        criteria = [entry.strip() for entry in raw.split(",") if entry.strip()]
        if len(criteria) != 1:
            raise UpnpActionError(709, "Unsupported SortCriteria")
        match = re.fullmatch(r"([+-]?)(dc:title|upnp:artist|upnp:album)", criteria[0], re.I)
        if not match:
            raise UpnpActionError(709, "Unsupported SortCriteria")
        key = {"dc:title": "title", "upnp:artist": "artist", "upnp:album": "album"}[match.group(2).lower()]
        return key, "desc" if match.group(1) == "-" else "asc"

    @staticmethod
    def _sort_rows(rows, key: str, direction: str, value):
        return sorted(rows, key=lambda row: dlna_text(value(row, key)).casefold(), reverse=direction == "desc")

    def _update_id(self) -> int:
        raw = self.system_update_id()
        if isinstance(raw, bool):
            return 0
        try:
            return max(0, min(0xFFFFFFFF, int(raw)))
        except (TypeError, ValueError, OverflowError):
            return 0

    @staticmethod
    def _container(item_id: str, parent_id: str, title: str, kind: str) -> str:
        return '<container id="%s" parentID="%s" restricted="1"><dc:title>%s</dc:title><upnp:class>%s</upnp:class></container>' % (
            html.escape(dlna_text(item_id, MAX_DLNA_ID_CHARS), quote=True),
            html.escape(dlna_text(parent_id, MAX_DLNA_ID_CHARS), quote=True),
            html.escape(dlna_text(title)),
            html.escape(dlna_text(kind)),
        )

    def _metadata_for_object(self, object_id: str, filter_fields: set[str]) -> str:
        static = {
            "0": ("-1", "fnAudio", "object.container"),
            "music": ("0", "Music", "object.container"),
            "albums": ("0", "Albums", "object.container.album.musicAlbum"),
            "artists": ("0", "Artists", "object.container.person.musicArtist"),
            "genres": ("0", "Genres", "object.container.genre.musicGenre"),
            "folders": ("0", "Folders", "object.container.storageFolder"),
        }
        if object_id in static:
            parent, title, kind = static[object_id]
            return self._container(object_id, parent, title, kind)
        if object_id.startswith(("albums:", "artists:", "genres:")):
            parent, name = object_id.split(":", 1)
            decoded_name = unquote(name)
            if not decoded_name or not self._group_exists(parent, decoded_name):
                raise UpnpActionError(701, "No such object")
            return self._container(
                dlna_text(object_id, MAX_DLNA_ID_CHARS),
                dlna_text(parent, MAX_DLNA_ID_CHARS),
                decoded_name,
                "object.container",
            )
        if object_id.startswith("folders-root:") or object_id.startswith("folder:"):
            try:
                root, folder = self._folder_target(object_id)
            except ValueError:
                raise UpnpActionError(701, "No such object")
            if object_id.startswith("folders-root:"):
                row = next((row for row in self.library_roots() if dlna_text(row.get("root") or row.get("path"), MAX_DLNA_ID_CHARS) == root), None)
                if not row:
                    raise UpnpActionError(701, "No such object")
                title = dlna_text(row.get("name") or root, fallback="Music")
                parent = "folders"
            else:
                parent_folder, _, title = folder.rpartition("/")
                title = title or folder or "Music"
                row = next((row for row in self.library_folders(parent_folder, root) if dlna_text(row.get("path"), MAX_DLNA_ID_CHARS) == folder), None)
                if not row:
                    raise UpnpActionError(701, "No such object")
                safe_root = dlna_text(root, MAX_DLNA_ID_CHARS)
                safe_parent = dlna_text(parent_folder, MAX_DLNA_ID_CHARS)
                parent = "folders-root:%s" % quote(safe_root, safe="") if not parent_folder else "folder:%s:%s" % (quote(safe_root, safe=""), quote(safe_parent, safe=""))
            return self._folder_container(object_id, parent, title)
        item = self.library_item(object_id)
        if item:
            return self._didl_item(item, "music", filter_fields)
        raise UpnpActionError(701, "No such object")

    def _group_exists(self, view: str, name: str) -> bool:
        """Check one group label without listing every group.

        ``library_groups(view)`` is called without a page, so it bypasses the
        library query cache entirely and materializes the whole group table
        through a NOCASE sort. Using it to answer "is this name known" made the
        most expensive browse in the library run on every Browse and
        BrowseMetadata request for a single album, artist, or genre. Groups are
        projections of tracks, so one indexed page probe answers the same
        question and matches the exact predicate the browse itself uses.
        """
        page = self.library_page({"view": view, "group": name, "limit": 1, "offset": 0})
        return _safe_count(page.get("count") if isinstance(page, dict) else None) > 0

    @staticmethod
    def _folder_container(item_id: str, parent_id: str, title: str) -> str:
        return '<container id="%s" parentID="%s" restricted="1"><dc:title>%s</dc:title><upnp:class>object.container.storageFolder</upnp:class></container>' % (
            html.escape(dlna_text(item_id, MAX_DLNA_ID_CHARS), quote=True),
            html.escape(dlna_text(parent_id, MAX_DLNA_ID_CHARS), quote=True),
            html.escape(dlna_text(title)),
        )

    def protocol_info(self, role: str) -> str:
        mime_types = ["audio/mpeg", "audio/flac", "audio/wav", "audio/x-wav", "audio/mp4", "audio/aac"]
        if role == "server":
            # The resource endpoint supports direct library delivery. A client
            # still chooses only the profiles it understands from this list.
            mime_types.extend(["audio/x-ms-wma", "audio/ogg", "audio/x-dsf", "audio/x-dff"])
        else:
            try:
                caps = self.output_capabilities() or {}
                rates = set()
                for value in caps.get("pcm_rates") or []:
                    try:
                        rate = int(value)
                    except (TypeError, ValueError):
                        continue
                    if rate > 0:
                        rates.add(rate)
                max_bits = int(caps.get("pcm_max_bits") or 16)
                # Keep the broadly compatible MIME entries above, then expose
                # explicit LPCM profiles only for rates the selected DAC can
                # actually accept. Controllers that understand these profiles
                # can avoid an unnecessary downsample before sending audio.
                for rate in sorted(rates):
                    if rate < 44100:
                        continue
                    mime_types.append("audio/L16;rate=%s;channels=2" % rate)
                    if max_bits >= 24:
                        mime_types.append("audio/L24;rate=%s;channels=2" % rate)
                if caps.get("dsd_native") or caps.get("dop"):
                    mime_types.extend(["audio/x-dsf", "audio/x-dff"])
            except Exception:
                pass
        return ",".join("http-get:*:%s:*" % mime for mime in mime_types)

    @staticmethod
    def _folder_target(object_id: str) -> Tuple[str, str]:
        if object_id.startswith("folders-root:"):
            return unquote(object_id.split(":", 1)[1]), ""
        _, root, folder = object_id.split(":", 2)
        return unquote(root), unquote(folder)

    def _didl_item(self, item: Dict[str, Any], parent_id: str = "music", filter_fields: set[str] | None = None) -> str:
        fields = filter_fields or {"*"}
        include_all = "*" in fields
        def include(name: str) -> bool:
            normalized = name.lower()
            return include_all or normalized in fields or any(field.startswith(normalized + "@") for field in fields)
        item_id = dlna_text(item.get("id"), MAX_DLNA_ID_CHARS)
        title = html.escape(dlna_text(item.get("title"), fallback="Unknown title"))
        artist = html.escape(dlna_text(item.get("artist")))
        album = html.escape(dlna_text(item.get("album")))
        mime = html.escape(self.media_mime(item), quote=True)
        resource_path = "%s/upnp/media/%s/%s" % (self.base_url(), quote(item_id, safe=""), quote(dlna_text(item.get("title"), fallback="track")))
        uri = html.escape(resource_path, quote=True)
        # DMS artwork must be independently reachable by controllers. Browser
        # cover URLs require fnOS auth, while a DLNA client only receives the
        # DIDL URI. Serve a bounded JPEG_TN representation on the public
        # UPnP media surface, like established DLNA servers do.
        art = html.escape("%s/upnp/cover/%s?size=160" % (self.base_url(), quote(item_id, safe="")), quote=True)
        duration = _duration(item.get("duration"))
        resources = '<res protocolInfo="http-get:*:%s:*" duration="%s">%s</res>' % (mime, duration, uri) if include("res") or any(name.startswith("res@") for name in fields) else ""
        # Offer a separate, explicit fallback instead of changing the primary
        # resource. Renderers that support FLAC/DSD keep direct playback;
        # constrained clients may select this MP3 resource themselves.
        if resources and dlna_text(item.get("format")).upper() != "MP3" and not item.get("cue_track"):
            fallback = html.escape(resource_path + "?transcode=mp3", quote=True)
            resources += '<res protocolInfo="http-get:*:audio/mpeg:*" duration="%s">%s</res>' % (duration, fallback)
        creator_xml = "<dc:creator>%s</dc:creator>" % artist if include("dc:creator") else ""
        artist_xml = "<upnp:artist>%s</upnp:artist>" % artist if include("upnp:artist") else ""
        album_xml = "<upnp:album>%s</upnp:album>" % album if include("upnp:album") else ""
        art_xml = '<upnp:albumArtURI dlna:profileID="JPEG_TN">%s</upnp:albumArtURI>' % art if include("upnp:albumarturi") else ""
        return '<item id="%s" parentID="%s" restricted="1"><dc:title>%s</dc:title>%s%s%s%s<upnp:class>object.item.audioItem.musicTrack</upnp:class>%s</item>' % (
            html.escape(dlna_text(item_id, MAX_DLNA_ID_CHARS), quote=True),
            html.escape(dlna_text(parent_id, MAX_DLNA_ID_CHARS), quote=True),
            title,
            creator_xml,
            artist_xml,
            album_xml,
            art_xml,
            resources,
        )
