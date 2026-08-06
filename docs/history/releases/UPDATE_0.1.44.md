# fnAudio 0.1.44

- DLNA Renderer now reflects asynchronous MPD output failures as a stopped
  session with the underlying error message.
- Playback Core is notified when an incoming renderer session fails, keeping
  its displayed transport state aligned with MPD.
- Added regression coverage for ALSA/output startup failures.
