# Remote playback mode

## Why this exists

When USB DAC, MPD, or a DLNA renderer is selected, the audio output belongs to fnAudio/NAS or the renderer. The Android client must not start a second decoder. It therefore exposes a Media3 `RemotePlaybackPlayer` that mirrors metadata, queue, transport, duration, and position only.

## Reference model

- Volumio keeps the playback state in the MPD/output state machine, pushes state to the UI, and sends UI commands back to the output controller.
- moOde reads MPD `status`/`currentsong` and sends commands such as `play`, `pause`, `stop`, `next`, `previous`, and `seek` to MPD.
- fnAudio follows the same separation: the server-side output remains authoritative; Android MediaSession is a control and notification surface.

## Android flow

1. WebView calls `FnAudioNative.enterRemoteMode(...)` with the queue and current item metadata.
2. `PlaybackService` switches the MediaSession from ExoPlayer to `RemotePlaybackPlayer`.
3. `RemotePlaybackPlayer` does not receive playable URIs and never decodes audio. Its media buttons call the authenticated fnAudio `/api/playback/control` endpoint.
4. `PlaybackService` polls `/api/playback/status` while remote mode is active and updates position, transport state, and current queue index.
5. Removing the Android task does not stop the service while a remote session is active, so the notification and lock-screen card remain available.
6. Returning to local playback calls `exitRemoteMode()`, restores ExoPlayer, and leaves the existing local playback path unchanged.

## Verification boundary

The source, lint, Java build, JavaScript syntax, and static bridge regression checks are automated. Notification appearance, lock-screen controls, USB DAC background playback, and device-specific foreground-service behavior still require installation on physical Android devices.
