# fnAudio 0.1.30

- Fixed DLNA Renderer playback handshake with strict controllers such as
  Synology Media Server.
- Renderer now returns the UPnP Play response immediately and starts MPD
  network-source loading in the background, preventing controller timeouts.
- Renderer status records a source-loading error when MPD cannot access the
  submitted media URI.
