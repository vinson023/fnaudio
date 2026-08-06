# fnAudio 0.1.40

- Persisted the playback queue, selected track, repeat mode, shuffle mode and
  selected output target in the NAS state database.
- Restores the saved session when fnAudio starts, without resuming playback.
- Added versioned, throttled state writes and automatic merge/retry handling
  for simultaneous browser windows.
