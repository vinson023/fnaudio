# fnAudio 0.1.26 Phase 3 DLNA Compatibility Build

- Added common ConnectionManager, AVTransport and RenderingControl compatibility actions used by DLNA controllers.
- Fixed URL-decoding when browsing album, artist and genre containers.
- Renderer status now reuses the private MPD idle-state cache instead of adding an independent fixed polling loop.
- MediaServer now advertises DSD source profiles while keeping the renderer sink tied to detected MPD/DAC capabilities.
- Added explicit MP3 fallback resources alongside original non-MP3 MediaServer resources. Direct-capable DLNA devices continue to use original files.
- Verified on the internal fnOS test machine using the real multi-root music library and ContentDirectory SOAP responses.
