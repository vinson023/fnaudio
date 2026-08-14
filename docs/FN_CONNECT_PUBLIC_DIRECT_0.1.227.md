# FN Connect Public Direct Access (0.1.227)

FN Connect relay mode has been intentionally removed from fnAudio Android.
The client resolves an FN ID through the existing official discovery endpoint,
then probes public IPv6 addresses first. If no IPv6 endpoint is reachable it
falls back to public IPv4. It uses the discovered HTTP port (default 5666),
then performs normal fnOS WebSocket authentication and loads fnAudio through
that authenticated endpoint.

No Tpps credentials, native tunnel library, relay profile, or `127.0.0.1:9018`
route is packaged or used. Historical FN Connect profiles pointing at the old
localhost relay route are re-resolved from their stored FN ID when opened.

Verification completed on Xiaomi 15 Pro:

- Debug APK installed successfully.
- FN Connect preferences render `IPv6 preferred`, IPv4 fallback, and relay
  disabled.
- Android build completed from a clean build with no native relay libraries.

Remaining acceptance is a manual FN ID login on a network with the NAS public
IPv6 route reachable, followed by fnAudio library and playback verification.
