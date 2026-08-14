# fnAudio 0.1.207 Deployment Recovery Record

Date: 2026-08-11

## Scope

This record is the recovery entry point for the 0.1.207 browser/Android remote
playback synchronization update. It supplements the existing project context
files, which must not be rewritten while their character encoding is uncertain.

## Artifacts

| Artifact | Location | SHA-256 |
| --- | --- | --- |
| fnOS package | `artifacts/0.1.207/fnaudio-0.1.207-fnpack.fpk` | `04050A33FF6ECE7C996BFF76ED1AD48F045032D1D1224691D18D9EA65571D410` |
| Android Debug APK | `artifacts/0.1.207/fnaudio-android-0.1.207-debug.apk` | `379141F18DC0694DFC95B9F8D8C1651439840034C6A369C49ABD5182A20131AC` |

## NAS Deployment

- Target NAS: `198.51.100.24:5666`.
- fnAudio API service port: `18081`.
- Remote package source: `/vol1/1000/fnaudio-0.1.207.fpk`.
- Installation method: fnOS App Center UI -> Manual install -> Add from NAS ->
  select the package -> accept the unverified-app warning. This was an overlay
  update, not an uninstall/reinstall.
- Do not directly overwrite the installed application directory. Do not
  uninstall fnAudio when updating. Both operations can discard the persisted
  configuration, queue, and output selection that the overlay flow preserves.

## Post-install Evidence

- `/api/health` returned HTTP 200 and `Server: fnAudio/0.1.207 Python/3.12.4`.
- The prior session survived: DLNA target `2c55c281220ac041`, 228 queue items,
  current index 2, repeat `all`, shuffle `false`, and `STOPPED` transport.
- `GET /api/playback/events?target_id=2c55c281220ac041` emitted an SSE
  `playback` event with `state_version`, authoritative core state, normalized
  transport, and position.
- The web application loaded successfully through
  `/cgi/ThirdParty/fnaudio/index.cgi/` after deployment.

## Architecture Added In 0.1.207

- Server: SSE playback endpoint backed by `PlaybackCore.wait_for_version()`;
  it uses condition-variable wakeups and a 15-second heartbeat.
- Browser: remote control uses SSE first and a five-second HTTP status fallback.
  Page unload no longer sends `stop` to a remote output.
- Android: `PlaybackService` consumes the same SSE stream directly; WebView
  bridge state is used only before that stream becomes active.
- Commands: browser and Android send `command_id`; the server keeps a 30-second
  idempotency cache so an interrupted retry of `next` or `previous` cannot skip
  another song.

## Build Validation

- 128 Python tests passed.
- `node --check src/app/ui/app.js` passed.
- `node src/tests/test_ui_android_bridge.js` passed.
- Android `lintDebug` and `assembleDebug` passed.
- FPK manifest and packed application source were inspected before deployment.

## Resume Checklist

1. Query `http://198.51.100.24:18081/api/health` and confirm 0.1.207 before
   making any follow-up change.
2. Query `/api/playback/core` before playback testing; preserve the user's
   queue/current index/target if a temporary test queue is needed.
3. Confirm `/api/playback/events` produces `event: playback` with
   `state_version` before diagnosing a browser or Android state-sync issue.
4. Continue acceptance on physical hardware: Android foreground/background and
   lock-screen controls, external DLNA/UPnP Renderer refresh/close behavior,
   automatic remote advance, and a release-signed Android APK.
