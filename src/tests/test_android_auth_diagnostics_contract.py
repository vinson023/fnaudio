"""The failure report the user copies must describe the attempt, not leak it.

A copied diagnostic is pasted into a chat window, so it is the one place where a
credential leak would be irreversible. The report is also what replaces the PC +
mitmproxy export for a phone-only "it broke again" report, which is why the shape
of it is pinned here.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NETWORK = ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network"
UI = ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "ui"
DIAG = (NETWORK / "AuthDiagnostics.java").read_text(encoding="utf-8")
AUTH = (NETWORK / "FnOsAuthClient.java").read_text(encoding="utf-8")
LOGIN = (UI / "LoginActivity.java").read_text(encoding="utf-8")

# The report exists and is bounded: a pasted block has to stay readable.
assert "public static synchronized String report(@Nullable ConnectionProfile profile)" in DIAG
assert "MAX_EVENTS" in DIAG and "MAX_EVENT_CHARS" in DIAG

# Presence only -- never the value. A pasted report must not carry a password, a
# token, or an access code, no matter how useful the raw value would be locally.
for credential in ("profile.password", "profile.token", "profile.longToken", "profile.accessCode"):
    assert ("+ " + credential) not in DIAG, "the report must not append " + credential
    assert ("+ " + credential + " ") not in DIAG, "the report must not append " + credential
for presence in (
    'profile.accessCode.isEmpty() ? "no" : "yes"',
    'profile.token.isEmpty() ? "no" : "yes"',
    'profile.longToken.isEmpty() ? "no" : "yes"',
    'profile.password.isEmpty() ? "no" : "yes"',
):
    assert presence in DIAG, "the report states presence for every credential"

# The attempt records the facts that separate the two known failure shapes.
for fact in (
    "verify hop=",
    'cookie=',
    "login attempt=",
    "failure kind=",
    "ws open",
):
    assert fact in AUTH, "the attempt must record " + fact

# One tap: the failure dialog copies the report instead of only showing a toast.
assert "private void showAuthFailure(" in LOGIN
assert "ClipboardManager" in LOGIN and "setPrimaryClip" in LOGIN
assert "复制诊断" in LOGIN
assert "Toast.makeText(LoginActivity.this, message, Toast.LENGTH_LONG).show();" not in LOGIN, \
    "a failure must not disappear with a toast that carries no detail"
