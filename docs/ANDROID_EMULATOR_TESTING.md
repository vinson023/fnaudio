# Android emulator automated testing

## Scope

`tools/test_android_emulator.ps1` creates and uses the isolated
`fnaudio-api35-atd` Android 15 (API 35) x86_64 AOSP ATD emulator. It runs
`connectedDebugAndroidTest` against the Debug application and never contacts a
real fnOS server.

The current suite has six instrumented tests in five test classes:

1. `SecureProfileStoreInstrumentedTest` verifies multiple encrypted connection
   profiles, active-profile behavior, deletion, password ciphertext storage and
   persisted self-signed certificate pins.
2. `LoginHistoryInstrumentedTest` verifies that the active saved profile fills
   the login form and that the separate history screen lists multiple profiles.
3. `PinnedHttpsInstrumentedTest` starts an in-process TLS server, verifies a
   matching self-signed certificate pin succeeds and a replacement pin fails
   before an HTTP response is accepted.
4. `RemotePlaybackPlayerInstrumentedTest` verifies Media3 remote-mode queue
   state plus play, pause, indexed seek, next, repeat and shuffle forwarding.
5. `MainActivityWebViewInstrumentedTest` uses a local MockWebServer WebSocket
   auth response and page fixture to verify authenticated WebView loading and
   the double-back transition from the root page to the login screen.

After the instrumented task, the runner explicitly installs the freshly built
Debug APK and checks the emulator package's `versionCode` against
`app/build.gradle`. This validates installability and version identity, but not
a cross-version production upgrade or formal signing path.

The profile tests use only `instrument-*` record IDs and restore the former
active selection, so the test code does not clear unrelated saved connections.

## Run

```powershell
Set-Location C:\path\to\fnAudio
powershell -NoProfile -ExecutionPolicy Bypass -File tools\test_android_emulator.ps1 -InstallSdk
```

`-InstallSdk` is needed once to install the Android Emulator and the API 35 ATD
image under the selected SDK root. Later runs omit it. The script boots a
headless AVD when none is available, runs the test task and shuts down only the
emulator it started. Use `-KeepRunning` to retain that emulator for debugging.

Reports are written to
`android-client/app/build/reports/androidTests/connected/debug/index.html`.

## Boundaries

This is not physical-device acceptance. It does not establish fnOS WebSocket
login compatibility, CGI token handoff, WebView navigation against a real NAS,
network switching, lock-screen rendering, OEM background policy, Bluetooth or
wired media-key behavior, USB DAC remote notifications, IPv6, reverse proxies
or formal-release upgrade behavior. Those items remain in `TODO.md`.
