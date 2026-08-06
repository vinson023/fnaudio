# 0.1.4 Playback Architecture

The playback migration separates playback state from output transport.

## Layers

- `core.py`: queue, current track, target and transport state.
- `models.py`: small data contracts shared by the core and plugins.
- `plugins.py`: output plugin interface plus browser, DLNA push and ALSA adapter plugins.
- `../server.py`: legacy integration boundary during migration.

## Planned plugins

- `browser`: browser media URL and server-side transcode policy.
- `alsa`: USB DAC and regular sound-card playback through ALSA.
- `mpd`: optional local MPD backend for NAS sound-card / USB DAC playback.
- `dlna_push`: UPnP/DLNA control-point output to another renderer.
- `dlna_renderer`: a local renderer endpoint controlled by another DLNA control point.
- `upmpdcli_renderer`: optional upmpdcli probe for future UPnP/OpenHome renderer mode.
- `dlna_server`: ContentDirectory and media-resource serving.

The frontend should only select a target and send transport commands. SOAP, ALSA,
FFmpeg, MIME negotiation, renderer capabilities and device-specific behavior
belong behind these plugin boundaries.
