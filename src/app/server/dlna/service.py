from __future__ import annotations

import html
import re
import threading
import time
import urllib.request
import uuid
from typing import Any, Callable, Dict, Iterable, Tuple
from urllib.parse import quote, unquote
from xml.etree import ElementTree as ET


AVTRANSPORT = "urn:schemas-upnp-org:service:AVTransport:1"
RENDERING_CONTROL = "urn:schemas-upnp-org:service:RenderingControl:1"
CONNECTION_MANAGER = "urn:schemas-upnp-org:service:ConnectionManager:1"
CONTENT_DIRECTORY = "urn:schemas-upnp-org:service:ContentDirectory:1"


def _tag_name(tag: str) -> str:
    return str(tag or "").split("}")[-1]


def _duration(seconds: Any) -> str:
    try:
        seconds = max(0, int(float(seconds or 0)))
    except (TypeError, ValueError):
        seconds = 0
    return "%d:%02d:%02d" % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)


def _seconds(value: Any) -> float:
    match = re.match(r"^(\d+):(\d{1,2}):(\d{1,2})(?:\.(\d+))?$", str(value or "").strip())
    if not match:
        return 0.0
    hours, minutes, seconds, fraction = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + float("0." + (fraction or "0"))


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
    root = ET.fromstring(raw)
    action_node = next((node for node in root.iter() if _tag_name(node.tag) not in ("Envelope", "Body")), None)
    if action_node is None:
        raise ValueError("missing SOAP action")
    action = _tag_name(action_node.tag)
    if soap_action_header and "#" in soap_action_header:
        action = soap_action_header.strip().strip('"').rsplit("#", 1)[-1]
    return action, {_tag_name(child.tag): child.text or "" for child in action_node}


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
    state_table = "".join("<stateVariable sendEvents=\"no\"><name>%s</name><dataType>%s</dataType></stateVariable>" % (name, data_type) for name, data_type in states.items())
    return (
        '<?xml version="1.0"?><scpd xmlns="urn:schemas-upnp-org:service-1-0">'
        "<specVersion><major>1</major><minor>0</minor></specVersion><actionList>%s</actionList><serviceStateTable>%s</serviceStateTable></scpd>" % (actions, state_table)
    ).encode("utf-8")


class DlnaEventService:
    """Small UPnP eventing implementation for renderer state changes."""

    def __init__(self):
        self._lock = threading.RLock()
        self._subscriptions: Dict[str, Dict[str, Any]] = {}

    def subscribe(self, role: str, service: str, callback: str, sid: str, timeout_header: str) -> Tuple[str, int]:
        if role != "renderer" or service not in ("avtransport", "rendering"):
            raise ValueError("eventing is not available for this service")
        timeout = self._timeout(timeout_header)
        with self._lock:
            if sid:
                item = self._subscriptions.get(sid)
                if not item:
                    raise ValueError("unknown subscription")
                item["expires"] = time.time() + timeout
                return sid, timeout
            endpoint = self._callback_url(callback)
            sid = "uuid:%s" % uuid.uuid4()
            self._subscriptions[sid] = {"role": role, "service": service, "callback": endpoint, "expires": time.time() + timeout, "sequence": 0}
        return sid, timeout

    def unsubscribe(self, sid: str) -> bool:
        with self._lock:
            return self._subscriptions.pop(str(sid or ""), None) is not None

    def notify_renderer(self, state: Dict[str, Any]) -> None:
        with self._lock:
            now = time.time()
            expired = [sid for sid, item in self._subscriptions.items() if item["expires"] <= now]
            for sid in expired:
                self._subscriptions.pop(sid, None)
            subscriptions = [(sid, dict(item)) for sid, item in self._subscriptions.items()]
        for sid, item in subscriptions:
            body = self._body(item["service"], state)
            sequence = int(item.get("sequence") or 0)
            threading.Thread(target=self._send, args=(sid, item, sequence, body), daemon=True).start()

    @staticmethod
    def _timeout(value: str) -> int:
        match = re.search(r"Second-(\d+)", str(value or ""), re.I)
        seconds = int(match.group(1)) if match else 1800
        return max(30, min(86400, seconds))

    @staticmethod
    def _callback_url(value: str) -> str:
        match = re.search(r"<([^>]+)>", str(value or ""))
        endpoint = match.group(1).strip() if match else ""
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("invalid callback URL")
        return endpoint

    @staticmethod
    def _body(service: str, state: Dict[str, Any]) -> bytes:
        if service == "rendering":
            properties = "<Volume channel=\"Master\">%s</Volume><Mute channel=\"Master\">%s</Mute>" % (int(state.get("volume") or 0), "1" if state.get("muted") else "0")
        else:
            inner = '<Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/"><InstanceID val="0"><TransportState val="%s"/><CurrentTrackURI val="%s"/><CurrentTrackMetaData val="%s"/><RelativeTimePosition val="%s"/></InstanceID></Event>' % (html.escape(str(state.get("transport") or "STOPPED"), quote=True), html.escape(str(state.get("uri") or ""), quote=True), html.escape(str(state.get("metadata") or ""), quote=True), _duration(state.get("position")))
            properties = "<LastChange>%s</LastChange>" % html.escape(inner)
        return ('<?xml version="1.0"?><e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0"><e:property>%s</e:property></e:propertyset>' % properties).encode("utf-8")

    def _send(self, sid: str, item: Dict[str, Any], sequence: int, body: bytes) -> None:
        try:
            request = urllib.request.Request(item["callback"], data=body, method="NOTIFY")
            request.add_header("CONTENT-TYPE", "text/xml; charset=utf-8")
            request.add_header("NT", "upnp:event")
            request.add_header("NTS", "upnp:propchange")
            request.add_header("SID", sid)
            request.add_header("SEQ", str(sequence))
            urllib.request.urlopen(request, timeout=3).read(1)
            with self._lock:
                current = self._subscriptions.get(sid)
                if current:
                    current["sequence"] = sequence + 1
        except Exception:
            # Controllers can disappear without unsubscribing. The lease will
            # expire naturally and a failed callback must not affect playback.
            pass


class DlnaProtocolService:
    """HTTP/SOAP surface for fnAudio's MediaServer and MediaRenderer roles."""

    def __init__(
        self,
        base_url: Callable[[], str],
        renderer: Any,
        library_page: Callable[[Dict[str, Any]], Dict[str, Any]],
        library_groups: Callable[[str], Iterable[Dict[str, Any]]],
        media_mime: Callable[[Dict[str, Any]], str],
        library_roots: Callable[[], Iterable[Dict[str, Any]]] | None = None,
        library_folders: Callable[[str, str], Iterable[Dict[str, Any]]] | None = None,
        output_capabilities: Callable[[], Dict[str, Any]] | None = None,
    ):
        self.base_url = base_url
        self.renderer = renderer
        self.library_page = library_page
        self.library_groups = library_groups
        self.media_mime = media_mime
        self.library_roots = library_roots or (lambda: [])
        self.library_folders = library_folders or (lambda parent, root: [])
        self.output_capabilities = output_capabilities or (lambda: {})
        self.events = DlnaEventService()
        self.renderer.add_state_listener(self.events.notify_renderer)

    def subscribe(self, role: str, service: str, callback: str, sid: str, timeout: str) -> Tuple[str, int]:
        return self.events.subscribe(role, service, callback, sid, timeout)

    def unsubscribe(self, sid: str) -> bool:
        return self.events.unsubscribe(sid)

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
            "<device><deviceType>urn:schemas-upnp-org:device:%s</deviceType><friendlyName>%s</friendlyName><manufacturer>fnaudio</manufacturer><modelName>fnAudio</modelName><modelNumber>0.1</modelNumber><UDN>uuid:%s</UDN><serviceList>%s</serviceList></device></root>"
            % (device_type, friendly, udn, "".join(rows))
        ).encode("utf-8")

    def control(self, role: str, service_name: str, raw: bytes, header: str = "") -> Tuple[int, bytes]:
        try:
            action, args = parse_soap_action(raw, header)
            service = self._service_for(role, service_name)
            values = self._dispatch(role, service, action, args)
            return 200, _soap_envelope(service, action, values)
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
                return {"SearchCaps": "dc:title,upnp:artist,upnp:album"}
            if action == "GetSortCapabilities":
                return {"SortCaps": "dc:title,upnp:artist,upnp:album"}
            if action == "GetSystemUpdateID":
                return {"Id": "1"}
        if role != "renderer":
            raise ValueError("unsupported MediaServer action")
        state = self.renderer.snapshot()
        if service == AVTRANSPORT:
            if action == "SetAVTransportURI":
                self.renderer.set_uri(args.get("CurrentURI", ""), args.get("CurrentURIMetaData", ""))
                return {}
            if action == "SetNextAVTransportURI":
                self.renderer.set_next_uri(args.get("NextURI", ""), args.get("NextURIMetaData", ""))
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
                return self._result(self.renderer.command("seek", _seconds(args.get("Target"))))
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
                return self._result(self.renderer.set_volume(int(float(args.get("DesiredVolume") or 100))))
            if action == "GetMute":
                return {"CurrentMute": "1" if state["muted"] else "0"}
            if action == "SetMute":
                self.renderer.set_mute(args.get("DesiredMute", "0") not in ("0", "false", "False"))
                return {}
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
        object_id = str(args.get("ObjectID") or "0")
        start = max(0, int(args.get("StartingIndex") or 0))
        requested = max(0, int(args.get("RequestedCount") or 100)) or 100
        returned = None
        if object_id == "0":
            entries = [("music", "Music", "object.container"), ("albums", "Albums", "object.container.album.musicAlbum"), ("artists", "Artists", "object.container.person.musicArtist"), ("genres", "Genres", "object.container.genre.musicGenre"), ("folders", "Folders", "object.container.storageFolder")]
            xml = "".join('<container id="%s" parentID="0" restricted="1"><dc:title>%s</dc:title><upnp:class>%s</upnp:class></container>' % (item_id, html.escape(title), kind) for item_id, title, kind in entries)
            total = len(entries)
        elif object_id in ("albums", "artists", "genres"):
            groups = list(self.library_groups(object_id))
            page = groups[start:start + requested]
            xml = "".join('<container id="%s:%s" parentID="%s" restricted="1"><dc:title>%s</dc:title><upnp:class>object.container</upnp:class></container>' % (object_id, quote(str(row.get("name") or ""), safe=""), object_id, html.escape(str(row.get("name") or ""))) for row in page)
            total = len(groups)
        elif object_id == "folders":
            roots = list(self.library_roots())
            page = roots[start:start + requested]
            xml = "".join(self._folder_container("folders-root:%s" % quote(str(row.get("root") or row.get("path") or ""), safe=""), "folders", str(row.get("name") or row.get("root") or "Music")) for row in page)
            total = len(roots)
        elif object_id.startswith("folders-root:") or object_id.startswith("folder:"):
            root, parent = self._folder_target(object_id)
            folders = list(self.library_folders(parent, root))
            page_folders = folders[start:start + requested]
            xml = "".join(self._folder_container("folder:%s:%s" % (quote(root, safe=""), quote(str(row.get("path") or ""), safe="")), object_id, str(row.get("name") or "Folder")) for row in page_folders)
            track_offset = max(0, start - len(folders))
            remaining = max(0, requested - len(page_folders))
            item_page = self.library_page({"view": "folders", "root": root, "folder": parent, "limit": max(1, remaining), "offset": track_offset}) if remaining else {"items": [], "count": 0}
            tracks = item_page.get("items") or []
            # A folder can contain subfolders and tracks. Direct children are
            # always returned in that order, consistent with fnAudio's UI.
            xml += "".join(self._didl_item(item) for item in tracks)
            total = len(folders) + int(item_page.get("count") or len(tracks))
            returned = len(page_folders) + len(tracks)
        else:
            params: Dict[str, Any] = {"view": "all", "limit": requested, "offset": start}
            if object_id.startswith(("albums:", "artists:", "genres:")):
                view, group = object_id.split(":", 1)
                params.update({"view": view, "group": unquote(group)})
            page = self.library_page(params)
            items = page.get("items") or []
            xml = "".join(self._didl_item(item) for item in items)
            total = int(page.get("count") or len(items))
        didl = '<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">%s</DIDL-Lite>' % xml
        return {"Result": didl, "NumberReturned": str(returned if returned is not None else min(requested, max(0, total - start))), "TotalMatches": str(total), "UpdateID": "1"}

    @staticmethod
    def _folder_container(item_id: str, parent_id: str, title: str) -> str:
        return '<container id="%s" parentID="%s" restricted="1"><dc:title>%s</dc:title><upnp:class>object.container.storageFolder</upnp:class></container>' % (html.escape(item_id, quote=True), html.escape(parent_id, quote=True), html.escape(title))

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

    def _didl_item(self, item: Dict[str, Any]) -> str:
        item_id = str(item.get("id") or "")
        title = html.escape(str(item.get("title") or "Unknown title"))
        artist = html.escape(str(item.get("artist") or ""))
        album = html.escape(str(item.get("album") or ""))
        mime = html.escape(self.media_mime(item), quote=True)
        resource_path = "%s/upnp/media/%s/%s" % (self.base_url(), item_id, quote(str(item.get("title") or "track")))
        uri = html.escape(resource_path, quote=True)
        art = html.escape("%s/cover/%s" % (self.base_url(), quote(item_id, safe="")), quote=True)
        duration = _duration(item.get("duration"))
        resources = '<res protocolInfo="http-get:*:%s:*" duration="%s">%s</res>' % (mime, duration, uri)
        # Offer a separate, explicit fallback instead of changing the primary
        # resource. Renderers that support FLAC/DSD keep direct playback;
        # constrained clients may select this MP3 resource themselves.
        if str(item.get("format") or "").upper() != "MP3" and not item.get("cue_track"):
            fallback = html.escape(resource_path + "?transcode=mp3", quote=True)
            resources += '<res protocolInfo="http-get:*:audio/mpeg:*" duration="%s">%s</res>' % (duration, fallback)
        return '<item id="%s" parentID="music" restricted="1"><dc:title>%s</dc:title><dc:creator>%s</dc:creator><upnp:artist>%s</upnp:artist><upnp:album>%s</upnp:album><upnp:albumArtURI>%s</upnp:albumArtURI><upnp:class>object.item.audioItem.musicTrack</upnp:class>%s</item>' % (html.escape(item_id, quote=True), title, artist, artist, album, art, resources)
