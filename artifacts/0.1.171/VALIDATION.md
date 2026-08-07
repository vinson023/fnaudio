# fnAudio 0.1.171 Validation

## Build identity

| Item | Value |
| --- | --- |
| Build date | `2026-08-07` |
| fnOS source | `C:\path\to\fnAudio\src` |
| Android source | `C:\path\to\fnAudio\android-client` |
| fnOS package | `fnaudio-0.1.171.fpk` |
| FPK size | `4,883,192` bytes |
| FPK SHA-256 | `27FB3527EFE22179D4E34E89DB26C8351BE54159FCEC999A9C21F530AD9ECCEE` |
| Android package | `fnaudio-android-0.1.171-debug.apk` |
| APK size | `10,097,118` bytes |
| APK SHA-256 | `2B5ED40DE3EABBFCF39D7CD221A1047F11FF5F73491216DEE333EB7FA4E030B7` |

## Change summary

- Desktop track right-click restored the full action list; mobile long-press remains the four-item shortcut menu.
- File-manager handoff now passes the complete track path so fnOS can locate the file directly.
- Track rows show no music glyph over a valid cover; all missing-cover formats, including DSD, use `♫`. Failed image loads restore the fallback.
- Android Media3 now uses `AuthenticatedBitmapLoader`, which attaches fnOS token headers for same-origin artwork, stores bytes in the app-private `media-artwork` cache, and supplies the decoded bitmap to the notification provider.
- The white local fallback artwork remains available for tracks without a real cover.

## Completed local checks

- 59 Python unit tests passed.
- `node --check app/ui/app.js` and the three Node regression scripts passed.
- Android `:app:lintDebug` and `:app:assembleDebug` passed.
- APK badging: `com.fnaudio.client / 0.1.171 / versionCode 171 / minSdk 26 / targetSdk 36`.
- APK v2 Debug signature verified.
- FPK manifest: `fnaudio / 0.1.171 / x86`; outer archive has 21 entries and `app.tgz` has 110 entries with no Python bytecode cache.

## Device validation

Not performed in this build session. Install the paired FPK/APK and verify:

1. PC right-click still shows the complete desktop action list while Android long-press shows only the four mobile actions.
2. “打开包含的文件夹” opens fnOS File Manager at the selected file.
3. Covered rows do not show `♫`; no-cover and DSD rows show the same `♫` fallback.
4. Android notifications show real artwork when available and the white fallback when not, including foreground, background, and screen-off playback.

The APK is Debug-signed and intended for development testing only.
