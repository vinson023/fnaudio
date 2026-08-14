# fnAudio 0.1.209 Remote MediaSession Record

Date: 2026-08-11

## Implemented

- DLNA push no longer sends `SetNextAVTransportURI` from the managed queue
  output. fnAudio's renderer monitor is now the sole owner of automatic queue
  advancement after a confirmed track end, avoiding incompatible Renderer
  NextURI state machines replaying the same song.
- Android remote mode always starts `PlaybackService` with
  `ContextCompat.startForegroundService`, including when the remote output is
  paused, connecting, or waiting for its first SSE snapshot.
- `PlaybackService` now calls `startForeground` immediately after activating
  its metadata-only `RemotePlaybackPlayer`. The notification uses the existing
  media playback service type and notification icon.
- MediaSession remains attached to `RemotePlaybackPlayer`, which does not
  download or decode media. Lock-screen and Bluetooth transport commands enter
  MediaSession, become a fnAudio API command with `command_id`, and are then
  reconciled from the server response/SSE snapshot.
- Switching back to local mode stops the temporary remote foreground
  notification and reconnects the MediaSession to the local ExoPlayer.

## AirPlay Boundary

fnAudio currently implements AirPlay through `shairport-sync`, which is an
AirPlay receiver/input. It accepts an external sender's audio stream and owns
an ALSA lease; it is not a protocol client capable of pushing the fnAudio
queue to an AirPlay speaker. Therefore it must not be registered as a
`PlaybackCore` queue output: doing so would falsely imply that `load`, `next`,
and track-end detection are available.

The existing `AirplayService` remains the backend authority for receiver
lifecycle, capability probing, process supervision, and audio ownership. A
future AirPlay-speaker output requires a separate RAOP/AirPlay sender backend,
its own output adapter, and actual speaker interoperability tests.

## Validation

- Python unit tests: 130 passed.
- JavaScript syntax and Android bridge regression: passed.
- Android `lintDebug` and `assembleDebug`: passed.
- FPK manifest: `0.1.209`.

## Artifacts

| Artifact | Location | SHA-256 |
| --- | --- | --- |
| fnOS package | `artifacts/0.1.209/fnaudio-0.1.209-fnpack.fpk` | `B9030B8EDCF4753B3834BE37C21182042C70332A4FBB6332488BC332C9600061` |
| Android Debug APK | `artifacts/0.1.209/fnaudio-android-0.1.209-debug.apk` | `CB139A72861D9EAD94D8B4A5B47241323DD2CE9A1D9842542D5C154CEEB7DE56` |

## Required Device Check

Install the Android APK and select a remote output while it is paused or
connecting. Confirm that the fnAudio media notification appears immediately,
then verify lock-screen and Bluetooth play/pause/next/previous actions update
only after the authoritative fnAudio state returns.

## Completion Status

As of 2026-08-11, the five playback-state architecture goals are temporarily
accepted as complete:

1. `PlaybackCore` is the versioned server authority and publishes SSE state.
2. Browser and Android remote mode consume that same state, with HTTP only as
   a disconnect-recovery fallback.
3. Android remote mode starts its foreground media service without requiring
   local ExoPlayer decoding.
4. Remote notification, lock-screen and media-key commands flow through
   Android MediaSession and are confirmed by the server state.
5. Browser, MPD/USB DAC and DLNA push use backend output adapters; DLNA queue
   advancement is owned by the server monitor. AirPlay remains an input-only
   receiver and is intentionally outside the queue-output scope.

The DLNA duplicate-track report has been resolved by removing managed
`SetNextAVTransportURI` preloading. Acceptance is based on the reported
successful repeat-playback verification; broader device compatibility testing
remains future regression work.
