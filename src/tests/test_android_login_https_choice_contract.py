"""The HTTPS checkbox belongs to the user (R562).

It used to be forced on when logging in with an FN ID, and the main screen then
rewrote any stored http profile to https. Both existed for a real reason: a NAS
with 「强制 HTTPS」 answers every http request with a 302, and that surfaced as
「读取歌曲列表失败（响应体不完整）」(2026-11-11). But forcing it also made the
checkbox describe the app's decision instead of the user's.

The fix keeps the choice and moves the consequence somewhere visible: the scheme
stays as resolved, and a failing http FN Connect profile gets an error that names
the switch. These assertions keep both halves in place — losing either one brings
back a bug (silent override, or a dead end with no explanation).
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "ui"
LOGIN = (UI / "LoginActivity.java").read_text(encoding="utf-8")
MAIN = (UI / "MainActivity.java").read_text(encoding="utf-8")

# 1. The login screen reads the box instead of writing it.
assert "final boolean httpsRequested = useHttps.isChecked();" in LOGIN
assert "if (!useHttps.isChecked()) useHttps.setChecked(true);" not in LOGIN, \
    "the FN Connect login must not tick HTTPS for the user"
assert "final boolean httpsRequested = true;" not in LOGIN

# 2. When the device only answers on one scheme, say so — do not flip silently.
assert "if (resolved.https != httpsRequested) {" in LOGIN
assert "该设备只提供 HTTPS 访问，已自动勾选" in LOGIN
assert "该设备只提供 HTTP 访问，已取消勾选" in LOGIN

# 3. The main screen keeps the stored scheme.
assert "private void useProfile(ConnectionProfile next)" in MAIN
assert "httpFnConnectProfile = next != null && next.isFnConnectRoute() && !next.https;" in MAIN
assert "profile = profile.withEndpoint(profile.host, port, true);" not in MAIN, \
    "the entry path must not rewrite an http FN Connect profile to https"

# 4. …and a load failure on that profile explains the switch.
assert "errorMessage.setText(httpFnConnectProfile" in MAIN
assert "HTTPS 安全访问" in MAIN

# Every profile assignment goes through the helper, so the flag can never describe
# a profile that is no longer installed.
assert MAIN.count("useProfile(") >= 3
for stale in ("profile = authenticatedProfile;", "profile = refreshed;"):
    assert stale not in MAIN, "assignments must go through useProfile: " + stale
