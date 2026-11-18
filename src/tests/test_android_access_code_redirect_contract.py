"""The access-code verification must survive the gateway redirecting it.

Reported: on a public / FN Connect route the app failed with
"访问码验证成功但未取得会话 Cookie" most of the time, while the same account
worked on the LAN.

Cause: the verification is a plain GET, and OkHttp follows redirects by itself
while discarding every intermediate response. A gateway that answers the check
with a 302 to the HTTPS origin (and sets the session cookie on that 302) therefore
left the app reading a final response with no Set-Cookie at all. The LAN origin
answers once, which is why it only showed up off-LAN.

These are source contracts, like the sibling access-code test: the login flow is
a chain of OkHttp callbacks, so the shape is what can be checked without a device.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NETWORK = ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network"
AUTH = (NETWORK / "FnOsAuthClient.java").read_text(encoding="utf-8")
COOKIES = (NETWORK / "SessionCookies.java").read_text(encoding="utf-8")

# The redirect is followed here, one hop at a time, so the cookie on the 302 is read.
assert "followRedirects(false)" in AUTH, "the access-code request must inspect every hop itself"
assert "followSslRedirects(false)" in AUTH, "an http->https redirect must be visible, not swallowed"
assert "MAX_ACCESS_CODE_REDIRECTS" in AUTH, "the manual follow needs a bound"
assert "verifyAccessCode(resolveLocation(url, location), accessCode, hop + 1)" in AUTH, \
    "every redirect hop re-sends the access code to the absolute target"
assert "collectSessionCookies(response);" in AUTH, "each hop's Set-Cookie is collected"

# Ordering: the cookie collection has to happen before the redirect branch returns,
# otherwise the hop that carried the cookie is the one that gets dropped.
_verify = AUTH[AUTH.index("private void verifyAccessCode("):AUTH.index("private void collectSessionCookies(")]
assert _verify.index("collectSessionCookies(response)") < _verify.index("response.isRedirect()"), \
    "collect first, decide afterwards"

# A verification response without a cookie is not a failure: the handshake carries
# the same access code, and some routes issue no cookie at all.
assert "访问码验证成功但未取得会话 Cookie。" not in AUTH, \
    "a cookie-less verification must be proven by the handshake, not refused here"
assert "connectWebSocket(sessionCookie);" in _verify, "the handshake follows the verification unconditionally"

# Session cookies are recognised under every name the gateway uses, not only the
# access-code spelling.
assert "public static String sessionCookie(String setCookie)" in COOKIES
for name in ("trim_token", "fnos-token", "token"):
    assert '"' + name + '"' in COOKIES, "the session cookie list must recognise " + name
assert "os-access-code" in COOKIES, "the original access-code cookie stays first"

# The WebSocket client keeps OkHttp's redirect defaults: a handshake upgrade must
# never be replayed onto another URL.
assert "client.newBuilder()" in AUTH, "the redirect-off client is a per-exchange copy"
assert ".followRedirects(false)\n                    .followSslRedirects(false)" in AUTH

# Both stored tokens expire eventually, which is the "worked for a few days, then
# stopped" report. The saved password must be spent in the same chain instead of
# bouncing the user to the connection chooser.  R607 moved the hop order out of
# the failure handler into nextAttemptAfterFailure(), so the table is what has to
# keep saying it; the handler is now only the caller.
_handle = AUTH[AUTH.index("private void handleAttemptFailure("):AUTH.index("private void logFailure(")]
_next = AUTH[AUTH.index("static Attempt nextAttemptAfterFailure("):AUTH.index("private final Handler mainHandler")]
assert "current == Attempt.LONG_TOKEN" in _next, "the long-token hop is still in the chain"
assert "hasPassword ? Attempt.LOGIN_USER : null" in _next, \
    "an expired long token must fall back to the saved password"
assert _handle.index("send(next);") < _handle.index("finishCredentialRejected(message);"), \
    "the password attempt comes before giving up"

# Failures name their phase, so a recurrence is diagnosable from logcat alone.
assert "private void logFailure(String kind, String message)" in AUTH
for field in ("phase=", "attempt=", "sessionCookie=", "redirects=", "usedPassword="):
    assert field in AUTH, "the failure line must report " + field
assert 'logFailure("error", message);' in AUTH and 'logFailure("rejected", message);' in AUTH, \
    "both failure exits log the phase"
