# fnAudio 0.1.46

- Added a bounded, read-only DLNA compatibility diagnostic endpoint: `/api/dlna/diagnostics`.
- The diagnostic trace records recent MediaServer/Renderer description, SOAP control, event subscription and media-resource requests, including client identifier, Range request, accepted MIME types and selected transfer mode.
- This provides concrete evidence for future device-specific MediaServer profiles without changing the existing direct-play and MP3 fallback policy.
- Added regression coverage for the diagnostic trace and re-ran DLNA Renderer protocol tests.
