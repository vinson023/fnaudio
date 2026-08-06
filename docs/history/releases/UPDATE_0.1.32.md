# fnAudio 0.1.32

- Serialized incoming DLNA Renderer source loads and transport commands.
- Stop, pause and track changes invalidate an older pending source load, so a
  stopped track cannot start again after a delayed load completes.
- Limited MPD remote-source connection attempts to five seconds so an
  unreachable server does not delay later playback commands for a long time.
