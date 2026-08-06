# fnAudio 0.1.28

- The DLNA Renderer now queues consecutive `SetNextAVTransportURI` requests.
- `Next` advances through the pending incoming-controller queue instead of
  replacing earlier queued tracks.
