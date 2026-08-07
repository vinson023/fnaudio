# fnAudio 0.1.165 Validation

## Build identity

| Item | Value |
| --- | --- |
| Build date | `2026-08-07` |
| fnOS source | `C:\path\to\fnAudio\src` |
| Android source | `C:\path\to\fnAudio\android-client` |
| fnOS package | `fnaudio-0.1.165.fpk` |
| FPK size | `4,880,353` bytes |
| FPK SHA-256 | `7D134D517321F6C8A247A1F75D5B2B1FCE2AB3BB897FA5E2AE6651281A6C2E97` |
| Android package | `fnaudio-android-0.1.165-debug.apk` |
| APK size | `10,079,754` bytes |
| APK SHA-256 | `569B0A1F6D6FB21A186B5C477920EE01CE7D94FA0775DDC4B8BF5A6B4EBFBDE5` |
| FPK tool | `fnpack 1.2.3` |
| Android toolchain | AGP `9.3.1`, Gradle `9.6.1`, Media3 `1.10.1`, compile/target SDK `36` |

## Completed local checks

- 57 Python unit tests passed.
- `node --check app/ui/app.js` passed.
- `tests/test_ui_queue_columns.js`, `tests/test_ui_mobile_layout.js` and `tests/test_ui_android_bridge.js` passed.
- Android `:app:lintDebug` and `:app:assembleDebug` passed.
- APK manifest confirms `com.fnaudio.client`, version `0.1.165`, min SDK 26 and target SDK 36.
- APK verifies with Android APK Signature Scheme v2 and the Android Debug certificate.
- FPK outer archive has 21 readable entries; inner `app.tgz` has 110 readable entries and no Python bytecode cache.
- Packaged manifest is `fnaudio / 0.1.165 / x86`.
- Login, history and WebView host roots apply system-bar/display-cutout safe padding; the login port field defaults to `5666` without a port explanation hint.
- Playback queue requests now transmit compact track IDs; the server accepts both compact IDs and legacy track objects, and failed requests expose the HTTP status/message.
- `SOURCE_MANIFEST.sha256` records the current fnOS/Android source and build-entry files while excluding Gradle/build output, local properties, FPK and APK files.

## Device validation

Pending. The FPK/APK have not been installed in this round. Verify on a real fnOS and Android device:

1. login content starts below the status bar and front-camera cutout, with port `5666` already filled;
2. fnAudio top header no longer overlaps status icons or the camera area;
3. playing one track and using “从当前开始播放” with a large library no longer shows “播放队列保存失败”;
4. saved password/history selection and CSS/JavaScript/cover loading continue to work;
5. background, lock-screen and automatic next-track playback still work.

The APK is Debug-signed and is intended for development testing only.
