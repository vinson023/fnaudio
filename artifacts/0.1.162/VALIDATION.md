# fnAudio 0.1.162 Validation

## Build identity

| Item | Value |
| --- | --- |
| fnOS source | `C:\path\to\fnAudio\src` |
| Android source | `C:\path\to\fnAudio\android-client` |
| fnOS package | `fnaudio-0.1.162.fpk` |
| FPK size | `4,881,829` bytes |
| FPK SHA-256 | `7253729113AEA07F55B93372EDC78BFE4E04E4EB991D71B3EFADEABD8C17CB9A` |
| Android package | `fnaudio-android-0.1.162-debug.apk` |
| APK size | `10,066,887` bytes |
| APK SHA-256 | `17898F32B6824C152AF5AA7DE34CE7F8C160547E1BB82028164D785A619C6EF9` |
| FPK tool | `fnpack 1.2.3` |
| Android toolchain | AGP `9.3.1`, Gradle `9.6.1`, Media3 `1.10.1`, compile/target SDK `36` |

## Completed local checks

- 53 Python unit tests passed, including CGI Header/Cookie token precedence and URL-decoding checks.
- `node --check app/ui/app.js` passed.
- `tests/test_ui_queue_columns.js`, `tests/test_ui_mobile_layout.js` and `tests/test_ui_android_bridge.js` passed.
- Android `:app:lintDebug` and `:app:assembleDebug` passed.
- APK is signed with the Android debug certificate and verifies with APK Signature Scheme v2.
- APK manifest confirms package `com.fnaudio.client`, version `0.1.162`, min SDK 26 and target SDK 36.
- FPK outer archive is readable; packaged manifest is `fnaudio / 0.1.162 / x86`.
- FPK inner `app.tgz` contains 97 runtime files and excludes tests, databases, Python bytecode and transcode cache.
- Packaged `app.js`, `index.html` and `cgi_proxy.py` hashes match the current source exactly.

## Behavior covered by this build

- Android multi-connection login/history UI and encrypted token storage.
- Direct fnAudio route after login.
- WebView/native playback bridge.
- Media3 foreground playback queue, notification and media controls.
- fnAudio CGI same-origin token Cookie fallback for the hybrid client.
- Browser-only fnAudio behavior remains available when the native bridge is absent.

## Device validation

Pending. `adb devices -l` returned no connected Android device, so the APK has not yet been installed or exercised on a phone. The fnOS FPK has also not been installed in this round. Login token handoff, direct CGI access, real media playback, background/lock-screen continuation, multi-profile switching and self-signed HTTPS require device validation before release.
