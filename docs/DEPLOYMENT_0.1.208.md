# fnAudio 0.1.208 Deployment Recovery Record

Date: 2026-08-11

## Purpose

Version 0.1.208 fixes redundant playback SSE events. Before the fix, the DLNA
monitor called `PlaybackCore.sync_output_status()` every 1.25 seconds and that
method published a new state version even when transport, position, duration,
and error were unchanged. This could create unnecessary browser/WebView UI
work while an output was stopped.

## Change

- `sync_output_status()` now compares the normalized incoming snapshot with the
  authoritative state and calls `_touch()` only when a meaningful value changed.
- New regression: duplicate stopped-output status must not increment
  `state_version`.
- Position changes while actually playing remain publishable, so remote state
  remains authoritative rather than becoming a client-side estimate.

## Artifacts

| Artifact | Location | SHA-256 |
| --- | --- | --- |
| fnOS package | `artifacts/0.1.208/fnaudio-0.1.208-fnpack.fpk` | `B7EA3CDC8F961B603F244BB120886318003D932F00EC7C993D725902FE7338B9` |
| Android Debug APK | `artifacts/0.1.208/fnaudio-android-0.1.208-debug.apk` | `2D8C6B732C08FAA5D138DFD205A7BA018DE909B1DEE35AF0006DB1B77CB15DCC` |

## Deployment

- NAS: `198.51.100.24:5666`; fnAudio service port: `18081`.
- Remote source package: `/vol1/1000/fnaudio-0.1.208.fpk`.
- Installed via fnOS App Center manual install from NAS as an overlay update.
  Never use uninstall/reinstall or directly replace the installed directory:
  overlay updates preserve configuration, output selection, and queue state.

## Verification

- `GET /api/health` returned HTTP 200 and
  `Server: fnAudio/0.1.208 Python/3.12.4`.
- The existing persisted session remained intact: target kind `dlna_push`,
  228 queue items, current index 2, transport `STOPPED`.
- A 17-second idle SSE test returned exactly the initial `playback` event and
  the expected `: keepalive`; it no longer emitted the prior 1.25-second
  duplicate state events.
- Local checks: 129 Python tests, JavaScript syntax, Android bridge regression,
  Android `lintDebug`, Android `assembleDebug`, package manifest inspection,
  and `git diff --check` passed.

## Continue From Here

1. Treat `0.1.208` as the installed fnOS baseline.
2. Before any playback test, read `/api/playback/core`; preserve the user's
   228-item queue, current index, and output target.
3. For SSE diagnosis, expect one immediate snapshot, changes only for semantic
   state updates, and `: keepalive` after 15 seconds of idle time.
4. Android lock-screen notification, background playback, and automatic
   next-track behavior have been verified by the user. Remaining physical
   acceptance work is external DLNA/UPnP Renderer refresh/close behavior and
   release-signed APK testing. The Renderer item is blocked only because no
   suitable external Renderer is currently available for testing.
