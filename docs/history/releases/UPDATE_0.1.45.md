# fnAudio 0.1.45

- Propagate incoming DLNA Renderer output errors into Playback Core.
- The unified playback status API now reports the same failure reason as the
  Renderer endpoint when MPD cannot open its selected output.
