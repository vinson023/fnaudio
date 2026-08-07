# fnAudio 0.1.163 Validation

## Build identity

| Item | Value |
| --- | --- |
| Build date | `2026-08-07` |
| fnOS source | `C:\path\to\fnAudio\src` |
| Android source | `C:\path\to\fnAudio\android-client` |
| fnOS package | `fnaudio-0.1.163.fpk` |
| FPK size | `4,882,182` bytes |
| FPK SHA-256 | `DA31F9DFF9974A416CBB088CD30C8530D00D1AAF25BD6AC4DCFC04D0933856C2` |
| Android package | `fnaudio-android-0.1.163-debug.apk` |
| APK size | `10,071,583` bytes |
| APK SHA-256 | `7DD22857DE994B89E8877FE38890A5972733938CA2A989219B8F4E660C4ED053` |
| FPK tool | `fnpack 1.2.3` |
| Android toolchain | AGP `9.3.1`, Gradle `9.6.1`, Media3 `1.10.1`, compile/target SDK `36` |

## Completed local checks

- 53 Python unit tests passed.
- `node --check app/ui/app.js` passed.
- `tests/test_ui_queue_columns.js`, `tests/test_ui_mobile_layout.js` and `tests/test_ui_android_bridge.js` passed.
- Android `:app:lintDebug` and `:app:assembleDebug` passed.
- APK manifest confirms `com.fnaudio.client`, version `0.1.163`, min SDK 26 and target SDK 36.
- APK verifies with Android APK Signature Scheme v2 and the Android Debug certificate.
- FPK outer archive has 21 readable entries; inner `app.tgz` has 110 readable entries.
- Packaged manifest is `fnaudio / 0.1.163 / x86`.
- `SOURCE_MANIFEST.sha256` records 175 fnOS/Android source and build-entry files while excluding Gradle/build output, local properties, FPK and APK files.

## Behavior covered by this build

- The CGI page installs an `/index.cgi/` base URL before loading styles, scripts and relative API paths.
- The Android launcher uses an adaptive icon instead of a legacy icon wrapped by the launcher.
- Passwords can be saved inside the existing Android Keystore AES-GCM encrypted connection payload; Android application backup remains disabled.
- The login screen opens connection history through one button; selection, editing and deletion happen on a separate Activity.
- Expired token recovery can fall back to the encrypted saved password.
- Existing WebView/native playback bridge and Media3 foreground playback remain compiled and covered by the existing regression checks.

## Device validation

Pending. The FPK/APK have not been installed in this round. Verify on a real fnOS and Android device:

1. launcher icon has no unintended white legacy border;
2. login opens fnAudio with complete CSS and JavaScript rather than unstyled HTML;
3. saved password survives process restart, history selection switches connections, and delete removes local credentials;
4. expired tokens fall back to the saved password without exposing it in logs or UI;
5. background, lock-screen and automatic next-track playback still work.

The APK is Debug-signed and is intended for development testing only.
