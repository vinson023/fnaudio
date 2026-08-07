# fnAudio 0.1.167 Validation

## Build identity

| Item | Value |
| --- | --- |
| Build date | `2026-08-07` |
| fnOS source | `C:\path\to\fnAudio\src` |
| Android source | `C:\path\to\fnAudio\android-client` |
| fnOS package | `fnaudio-0.1.167.fpk` |
| FPK size | `4,884,107` bytes |
| FPK SHA-256 | `A5F5CF912C2477F1597D288201B5386552206B97870C49D1992D72D9741700DD` |
| Android package | `fnaudio-android-0.1.167-debug.apk` |
| APK size | `10,111,653` bytes |
| APK SHA-256 | `5723CDAE06C7D94FCCD1B5D3E705D33AFC3165157996FFB23FE1C7DFB020FC34` |
| FPK tool | `fnpack 1.2.3` |
| Android toolchain | AGP `9.3.1`, Gradle `9.6.1`, Media3 `1.10.1`, compile/target SDK `36` |

## Root cause confirmed

- The reported queue error was not an HTTP routing failure in `cgi_proxy.py`. A real fnOS request returned HTTP 200 with the plain-text body `invalid token` before the request reached fnAudio.
- WebView request interception can attach authentication to GET subresources, but Android WebView does not expose a POST body through `shouldInterceptRequest()`. Queue and other API POST requests therefore bypassed the authenticated OkHttp path.
- A native request carrying the saved fnOS token in `Authorization`, `X-Fnaudio-Trim-Token` and the same-origin token Cookie reached `/cgi/ThirdParty/fnaudio/index.cgi/api/playback/queue` and returned JSON successfully.

## Completed local checks

- 59 Python unit tests passed.
- `node --check app/ui/app.js` passed.
- `tests/test_ui_queue_columns.js`, `tests/test_ui_mobile_layout.js` and `tests/test_ui_android_bridge.js` passed.
- Android `:app:lintDebug` and `:app:assembleDebug` passed.
- APK manifest confirms `com.fnaudio.client`, version `0.1.167`, versionCode 167, min SDK 26 and target SDK 36.
- APK verifies with Android APK Signature Scheme v2 and the Android Debug certificate.
- FPK outer archive has 21 readable entries; inner `app.tgz` has 110 readable entries and no Python bytecode cache.
- Packaged manifest is `fnaudio / 0.1.167 / x86`.
- Android non-GET fnAudio API calls use `FnAudioNative.requestJson()`. MainActivity validates the current NAS and `/api/` path, then sends the request through authenticated OkHttp and returns status, headers and body to JavaScript.
- Queue, user-state, playback-control, transcode-warm, library/metadata settings, shared-folder sync, playback-target and playback-load POST requests use the native-aware API client in Android while ordinary browsers keep the standard Fetch path.
- Android back first closes fnAudio dialogs, menus, lyrics and nested views. At the root, the first press shows `APP 即将退出，再按一次返回登录界面`; a second press within 2.2 seconds opens the login page and suppresses its automatic reconnection.
- `SOURCE_MANIFEST.sha256` records current fnOS/Android sources while excluding Gradle/build output, local properties, FPK and APK files.

## Device validation

Pending for the new Android behavior. Verify on a real fnOS and Android device:

1. install both `0.1.167` packages and confirm the main fnAudio page loads with CSS and JavaScript;
2. play at least two songs and confirm the queue POST returns JSON with no `播放队列保存失败（HTTP 200）` message;
3. exercise a dialog, mobile menu, lyrics view and nested album/creator view, confirming one back press closes the current layer;
4. at the root, confirm the first back press only shows the exit warning and the second press opens the login page without immediately reconnecting;
5. verify automatic next-track, background/lock-screen playback, notifications and media controls.

The APK is Debug-signed and is intended for development testing only. No Android device was connected during this local validation, so the return-key and playback fixes are not claimed as completed on-device.
