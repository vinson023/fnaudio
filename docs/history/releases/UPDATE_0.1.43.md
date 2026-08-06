# fnAudio 0.1.43

- Hardened the DLNA Renderer transport session against stale MPD status.
- A newly accepted URI no longer flips back to STOPPED before MPD reports its
  first active state.
- Added regression coverage for Play/Stop races, Pause/Play recovery and
  SetNextAVTransportURI/Next handling.
