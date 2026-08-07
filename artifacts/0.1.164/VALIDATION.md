# fnAudio 0.1.164 Validation

## Build identity

| Item | Value |
| --- | --- |
| Build date | `2026-08-07` |
| fnOS source | `C:\path\to\fnAudio\src` |
| Android source | `C:\path\to\fnAudio\android-client` |
| fnOS package | `fnaudio-0.1.164.fpk` |
| FPK size | `4,882,412` bytes |
| FPK SHA-256 | `C114A0F9360F9E6D12C3487D2543F751F958B3E1B8E42362E4273591F66D62F5` |
| Android package | `fnaudio-android-0.1.164-debug.apk` |
| APK size | `10,078,542` bytes |
| APK SHA-256 | `81831D01106DADAB2A2C39DCDA305228F7F809BD7D44FFC7126D16F23500B089` |
| FPK tool | `fnpack 1.2.3` |
| Android toolchain | AGP `9.3.1`, Gradle `9.6.1`, Media3 `1.10.1`, compile/target SDK `36` |

## Completed local checks

- 55 Python unit tests passed.
- `node --check app/ui/app.js` passed.
- `tests/test_ui_queue_columns.js`, `tests/test_ui_mobile_layout.js` and `tests/test_ui_android_bridge.js` passed.
- Android `:app:lintDebug` and `:app:assembleDebug` passed.
- APK manifest confirms `com.fnaudio.client`, version `0.1.164`, min SDK 26 and target SDK 36.
- APK verifies with Android APK Signature Scheme v2 and the Android Debug certificate.
- FPK outer archive has 21 readable entries; inner `app.tgz` has 110 readable entries.
- Packaged manifest is `fnaudio / 0.1.164 / x86`.
- `MainActivity` re-authenticates same-origin WebView GET subresources and synchronizes response cookies; CGI injects an `/index.cgi/` base URL and has resource path fallback rewriting.
- Android legacy and adaptive launcher icons use the same white-background/blue-note visual as the FPK icon; adaptive foreground is scaled to stay inside the safe area.
- `SOURCE_MANIFEST.sha256` records the current fnOS/Android source and build-entry files while excluding Gradle/build output, local properties, FPK and APK files.

## Device validation

Pending. The FPK/APK have not been installed in this round. Verify on a real fnOS and Android device:

1. launcher icon matches the FPK logo and the blue note is not clipped;
2. login opens fnAudio with complete CSS, JavaScript, images and cover art rather than unstyled HTML;
3. saved password survives process restart, history selection switches connections, and delete removes local credentials;
4. expired token recovery falls back to the encrypted saved password without exposing it in logs or UI;
5. background, lock-screen and automatic next-track playback still work.

The APK is Debug-signed and is intended for development testing only.
