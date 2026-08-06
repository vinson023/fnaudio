# fnAudio 0.1.25 Phase 3 Test Build

- Added independent DLNA MediaServer and MediaRenderer protocol services.
- Added SSDP discovery announcements and M-SEARCH responses.
- Added AVTransport, RenderingControl and ConnectionManager SOAP endpoints.
- Incoming DLNA playback now routes to the private MPD and selected USB DAC output.
- Added ContentDirectory browsing backed by the SQLite music library, including multi-root folders and album artwork resources.
- Added basic UPnP event subscriptions, pending next-track URI support and DIDL-Lite metadata parsing.

This is a Phase 3 interoperability test build. It requires LAN validation with third-party DLNA controllers and renderers before a general release.
