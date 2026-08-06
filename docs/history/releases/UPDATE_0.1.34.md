# fnAudio 0.1.34

- Made playback-target selection optimistic: the selected marker changes
  immediately instead of waiting for the backend response.
- Prevented repeated target-switch requests while the current switch is being
  applied, and restore the prior selection if the request fails.
