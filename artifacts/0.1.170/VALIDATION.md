# fnAudio 0.1.170 Validation

## Build identity

| Item | Value |
| --- | --- |
| Build date | `2026-08-07` |
| fnOS source | `C:\path\to\fnAudio\src` |
| Android source | `C:\path\to\fnAudio\android-client` |
| fnOS package | `fnaudio-0.1.170.fpk` |
| FPK size | `4,885,020` bytes |
| FPK SHA-256 | `3996D1E8E4E693EF889B46845F3ED59D677C5BD2B2A3295345485DDDD4FA7493` |
| Android package | `fnaudio-android-0.1.170-debug.apk` |
| APK size | `10,085,880` bytes |
| APK SHA-256 | `1D4CE15B07B46289DC277A4EB26CCB7FFCA29488A6A1E29D41EC812C171A41BF` |

## Change summary

- Media3 now uses `R.drawable.ic_notification`, a white outlined play-circle resource, instead of the library default notification icon.
- When a queue item has no real artwork URL, the Android bridge generates a transparent 512×512 PNG containing the same play circle in white and stores it once as `media_placeholder_white.png` in app-private files.
- Missing-artwork metadata references the private PNG with a file URI. The image bytes are not copied into every `MediaItem`, avoiding large queues multiplying bitmap data or exceeding Binder transaction limits.
- A real song artwork URL still takes priority and is never replaced by the fallback.
- The fnOS/Web UI behavior from `0.1.169`, including the right-click/long-press four-action track menu, is unchanged.

## Completed local checks

- 59 Python unit tests passed.
- JavaScript syntax and all 3 Node regression scripts passed.
- Android Java compilation, `:app:lintDebug` and `:app:assembleDebug` passed.
- APK resources contain `com.fnaudio.client:drawable/ic_notification`.
- APK manifest is `com.fnaudio.client / 0.1.170 / versionCode 170 / minSdk 26 / targetSdk 36`.
- APK v2 Debug signature verifies.
- FPK manifest is `fnaudio / 0.1.170 / x86`; outer archive has 21 entries and `app.tgz` has 110 entries with no Python bytecode cache.

## Device validation

Not performed in this build session. Install the paired FPK/APK and verify:

1. play a track with no artwork and confirm the media card uses a white play-circle icon instead of the black icon shown in the reference screenshot;
2. confirm the status-bar/notification small icon is also the custom white symbol;
3. play a track with real cover art and confirm the cover remains visible;
4. switch across several no-cover and covered tracks in foreground, background and screen-off states;
5. confirm large queues still save and switch tracks normally.

The APK is Debug-signed and intended for development testing only.
