# fnAudio 0.1.166 Validation

## Build identity

| Item | Value |
| --- | --- |
| Build date | `2026-08-07` |
| fnOS source | `C:\path\to\fnAudio\src` |
| Android source | `C:\path\to\fnAudio\android-client` |
| fnOS package | `fnaudio-0.1.166.fpk` |
| FPK size | `4,883,638` bytes |
| FPK SHA-256 | `03993A17CA0E87BA063BFBE6764847B0650A0743BA6D5B5827C9913DA95FBD53` |
| Android package | `fnaudio-android-0.1.166-debug.apk` |
| APK size | `10,105,834` bytes |
| APK SHA-256 | `84A476C8F62A68955A52A385A37D4E4DF71103A8FED514452753CF042F8B3909` |
| FPK tool | `fnpack 1.2.3` |
| Android toolchain | AGP `9.3.1`, Gradle `9.6.1`, Media3 `1.10.1`, compile/target SDK `36` |

## Completed local checks

- 59 Python unit tests passed.
- `node --check app/ui/app.js` passed.
- `tests/test_ui_queue_columns.js`, `tests/test_ui_mobile_layout.js` and `tests/test_ui_android_bridge.js` passed.
- Android `:app:lintDebug` and `:app:assembleDebug` passed.
- APK manifest confirms `com.fnaudio.client`, version `0.1.166`, min SDK 26 and target SDK 36.
- APK verifies with Android APK Signature Scheme v2 and the Android Debug certificate.
- FPK outer archive has 21 readable entries; inner `app.tgz` has 110 readable entries and no Python bytecode cache.
- Packaged manifest is `fnaudio / 0.1.166 / x86`.
- Queue POST carries compact track IDs and an explicit `/api/playback/queue` route Header. CGI path recovery also covers a full `REQUEST_URI` when `PATH_INFO` contains only the script path.
- HTML CGI fallback responses are diagnosed separately from JSON API failures.
- LoginActivity leaves the task after successful login. Android back is delegated to the fnAudio page for overlays and nested views; the root page backgrounds the task instead of opening WebView/fnOS login history.
- `SOURCE_MANIFEST.sha256` records the current fnOS/Android source and build-entry files while excluding Gradle/build output, local properties, FPK and APK files.

## Device validation

Pending. The FPK/APK have not been installed in this round. Verify on a real fnOS and Android device:

1. install both `0.1.166` packages and confirm the main fnAudio page loads with CSS and JavaScript;
2. play from a large list and confirm `/api/playback/queue` returns JSON and no “播放队列保存失败（HTTP 200）” message appears;
3. press Android back in a dialog, mobile menu, lyrics view and nested album/creator view, then at the root page;
4. confirm the root back action backgrounds the app, and reopening it returns to fnAudio rather than the login page;
5. verify automatic next-track, background and lock-screen playback still work.

The APK is Debug-signed and is intended for development testing only.
