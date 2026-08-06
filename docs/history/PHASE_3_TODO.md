# fnAudio Phase 3: DLNA Service and Renderer

## Completed in the first implementation slice

- [x] Separate DLNA protocol module from `server.py` routing logic.
- [x] SSDP alive/byebye announcements and M-SEARCH responses for fnAudio MediaServer and MediaRenderer roles.
- [x] MediaRenderer device description, SCPD documents and SOAP control endpoints.
- [x] AVTransport actions: set URI, play, pause, stop, seek, transport info, position info and media info.
- [x] AVTransport next-item entry: `SetNextAVTransportURI`, next and previous actions.
- [x] RenderingControl actions: get/set software volume and get/set mute state.
- [x] ConnectionManager protocol-info responses.
- [x] Incoming HTTP media URI playback through the private MPD service and selected USB DAC output.
- [x] External renderer sessions mirrored into Playback Core without mixing SOAP parsing into the core.
- [x] MediaServer device description, ContentDirectory browse, and DIDL-Lite output.
- [x] ContentDirectory root containers for music, albums, artists, genres and folders.
- [x] Reuse SQLite library pagination, group tables and multi-root folder hierarchy for DLNA browse requests.
- [x] Local protocol and HTTP/SOAP smoke tests.
- [x] UPnP `SUBSCRIBE`/`UNSUBSCRIBE` leases and asynchronous AVTransport/RenderingControl event notifications.
- [x] DIDL-Lite title and artist extraction for incoming renderer sessions.
- [x] Isolated fnOS validation on `198.51.100.24`: service start, HTTP descriptions, capability endpoint, real multi-root SQLite scan and ContentDirectory browse.
- [x] MediaServer original-resource plus explicit MP3 fallback-resource policy, validated against the real library.

## Next work

- [x] Validate SSDP discovery and Renderer push on a real fnOS LAN with third-party DLNA controllers.
- [x] Add incoming DIDL-Lite cover-art extraction and expose supplied title/artist to the UI.
- [x] Add incoming-renderer session state to the UI without adding Renderer as a selectable output target.
- [x] Expand ConnectionManager profiles from the conservative PCM set according to the selected MPD/USB DAC capabilities.
- [x] Expand incoming controller queue support beyond one pending `SetNextAVTransportURI` item.
- [ ] Add device-specific MediaServer profiles after interoperability testing identifies clients that do not select the advertised MP3 fallback resource.
- [x] Add a bounded DLNA interoperability trace for device description, SOAP, subscription and media-resource requests; use captured client behavior before adding a device profile.
- [x] Add repeatable protocol smoke tests for common controller/renderer flows before packaging a Phase 3 test build.
