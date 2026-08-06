# fnAudio 0.1.143

- Resolve a track's real NAS location only when a file-manager action is requested.
- Reject resolved locations outside the configured music roots.
- Open containing folders through the official fnOS file-manager bridge.
- Open fnOS file details for sharing instead of exposing a public fnAudio media URL.
- Avoid waiting on long-running host bridge actions after they have been dispatched.
