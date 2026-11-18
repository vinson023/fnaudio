package com.fnaudio.client.network;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.webkit.CookieManager;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.fnaudio.client.data.ConnectionProfile;

import org.json.JSONObject;

import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import java.security.cert.Certificate;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

public final class FnOsAuthClient {
    private static final String TAG = "FnOsAuth";
    private static final int MAX_AUTH_MESSAGE_CHARS = 256 * 1024;
    private static final int MAX_AUTH_VALUE_CHARS = 16 * 1024;
    private static final int MAX_ACCESS_CODE_REDIRECTS = 4;

    // fnOS answers every rejection with {"errno":N,"result":"fail"} and never
    // sends an `errmsg`, so the number is the only thing a user-facing message
    // can be built from. These three were measured by replaying the frames
    // against fnOS 1.37.3 (docs/ANALYSIS_FNOS_LOGIN_ERRNO.md):
    //
    //   131072  credentials rejected -- wrong password, unknown user, and an
    //           empty password all land here; fnOS does not tell them apart
    //     8192  a required field is missing from the request; an absent
    //           `password`, or `username` sent instead of `user`
    //    65534  the request name itself is not recognised
    static final int ERRNO_CREDENTIALS_REJECTED = 131072;
    static final int ERRNO_MISSING_FIELD = 8192;
    static final int ERRNO_UNKNOWN_REQUEST = 65534;

    public interface Callback {
        void onSuccess(ConnectionProfile authenticatedProfile);

        void onError(String message);

        /** Called only when fnOS explicitly rejects the stored credentials. */
        default void onCredentialRejected(String message) {
            onError(message);
        }
    }

    enum Attempt {
        AUTH_TOKEN,
        LONG_TOKEN,
        LOGIN_USER,
        LOGIN_USERNAME
    }

    /**
     * Which hop to try after fnOS rejected {@code current}, or {@code null} when
     * nothing is left and the rejection must be reported.
     *
     * <p>Package-private so the table can be tested without a socket: the
     * ordering here is the whole login contract, and one branch of it used to
     * hide the real error (see the comment inside).
     */
    static Attempt nextAttemptAfterFailure(Attempt current, int errno, boolean hasLongToken, boolean hasPassword) {
        if (current == Attempt.AUTH_TOKEN) {
            return hasLongToken ? Attempt.LONG_TOKEN : null;
        }
        if (current == Attempt.LONG_TOKEN) {
            return hasPassword ? Attempt.LOGIN_USER : null;
        }
        // Swapping `user` for `username` is only worth a round trip when fnOS
        // said it did not recognise the request at all. A rejected password
        // (131072) has to be reported as it is: the swapped frame is answered
        // with errno 8192 ("a required field is missing"), and because only the
        // last message was surfaced, a wrong password reached the user as
        // "错误码 8192" while the real 131072 was thrown away.
        if (current == Attempt.LOGIN_USER && errno == ERRNO_UNKNOWN_REQUEST) {
            return Attempt.LOGIN_USERNAME;
        }
        return null;
    }

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    @Nullable private Session currentSession;

    public synchronized void authenticate(Context context, ConnectionProfile profile, @Nullable String password, Callback callback) {
        if (currentSession != null) currentSession.cancel();
        AuthDiagnostics.reset();
        AuthDiagnostics.record("start host=" + profile.host + " port=" + profile.port
                + " https=" + profile.https + " mode=" + profile.fnConnectMode);
        Session session = new Session(context.getApplicationContext(), profile, password == null ? "" : password, callback);
        currentSession = session;
        session.connect();
    }

    public synchronized void cancel() {
        if (currentSession != null) currentSession.cancel();
        currentSession = null;
    }

    private synchronized void clear(Session session) {
        if (currentSession == session) currentSession = null;
    }

    private final class Session extends WebSocketListener {
        private final ConnectionProfile profile;
        private final String password;
        private final Callback callback;
        private final AtomicBoolean completed = new AtomicBoolean(false);
        private final AtomicBoolean deliverCallback = new AtomicBoolean(true);
        private final CertificatePin.Observation tlsObservation = new CertificatePin.Observation();
        private final OkHttpClient client;
        private final Runnable timeoutRunnable = () -> finishError("连接超时，请检查地址、端口和 HTTPS 设置。");
        private ConnectionProfile verifiedProfile;
        private WebSocket socket;
        private Attempt attempt;
        /** Message from the hop before {@code LOGIN_USERNAME}, kept so the
         *  swapped frame's generic rejection does not become the only thing the
         *  user sees. */
        private String loginFallbackMessage = "";
        private String requestId = "";
        private String sessionCookie = "";
        private int accessCodeHops = 0;

        private Session(Context context, ConnectionProfile profile, String password, Callback callback) {
            this.profile = profile;
            this.verifiedProfile = profile;
            this.password = password;
            this.callback = callback;
            this.client = HttpClientFactory.createAuthenticationClient(context, profile, tlsObservation);
        }

        private void connect() {
            String accessCode = SessionCookies.accessCodeHeader(profile.accessCode);
            if (accessCode.isEmpty()) {
                connectWebSocket("");
                return;
            }
            verifyAccessCode(profile.httpOrigin() + "/access_code_verify", accessCode, 0);
        }

        /**
         * Verify the access code, following redirects by hand.
         *
         * OkHttp follows redirects itself and keeps only the final response, so a
         * gateway that answers the verification with a 302 to the HTTPS origin - and
         * sets the session cookie on that 302 - left this call reading a final
         * response with no Set-Cookie at all. That is why the app reported
         * "访问码验证成功但未取得会话 Cookie" mostly from outside the LAN: a public
         * or FN Connect entry redirects first, while the LAN origin answered once.
         * Every hop is inspected here, and the access code rides along so the
         * follow-up request is authenticated exactly like the first one.
         */
        private void verifyAccessCode(String url, String accessCode, int hop) {
            Request request;
            try {
                // An empty host only shows up in a stored profile, not in the form
                // (which validates), and it makes the origin "https://:5667" -
                // OkHttp rejects that with an IllegalArgumentException on the
                // caller's thread, i.e. the UI thread, with the error panel not
                // yet built.
                request = new Request.Builder()
                        .url(url)
                        .header("X-Access-Code", accessCode)
                        .header("X-Access-Source", "web")
                        .get()
                        .build();
            } catch (IllegalArgumentException malformed) {
                // Name the origin that could not be turned into a URL: this
                // branch fires before any request exists, so nothing else in
                // the app can report what the address actually was.
                Log.e(TAG, "cannot build the access-code request for " + url, malformed);
                finishError("访问码验证失败：连接地址无效（" + profile.httpOrigin()
                        + "），请在连接设置里重新填写。");
                return;
            }
            // The redirect policy belongs to this exchange only: the WebSocket below
            // has to keep OkHttp's defaults, where a handshake upgrade is never
            // replayed onto another URL.
            OkHttpClient verifier = client.newBuilder()
                    .followRedirects(false)
                    .followSslRedirects(false)
                    .build();
            try {
                verifier.newCall(request).enqueue(new okhttp3.Callback() {
                    @Override public void onFailure(@NonNull okhttp3.Call call, @NonNull java.io.IOException exception) {
                        finishError(describeConnectFailure(exception));
                    }

                    @Override public void onResponse(@NonNull okhttp3.Call call, @NonNull Response response) {
                        try (Response ignored = response) {
                            collectSessionCookies(response);
                            AuthDiagnostics.record("verify hop=" + hop + " status=" + response.code()
                                    + " cookie=" + (sessionCookie.isEmpty() ? "absent" : "present"));
                            String location = response.header("Location");
                            if (response.isRedirect() && location != null && hop < MAX_ACCESS_CODE_REDIRECTS) {
                                accessCodeHops = hop + 1;
                                verifyAccessCode(resolveLocation(url, location), accessCode, hop + 1);
                                return;
                            }
                            if (!response.isSuccessful()) {
                                finishError("访问码验证失败：HTTP " + response.code());
                                return;
                            }
                            // No cookie is not proof of a refusal. The gateway issues
                            // os-access-code only on some routes, and the handshake
                            // carries the same access code in its own header, so the
                            // handshake - not this response - decides whether the
                            // access code was accepted.
                            connectWebSocket(sessionCookie);
                        }
                    }
                });
            } catch (RuntimeException rejected) {
                // The dispatcher is shut down by finishError/cancel, so a retry
                // from the error panel can land here as RejectedExecutionException.
                // The attempt is over either way; it must not reach the UI thread.
                finishError("连接 NAS 失败：请稍后重试。");
            }
        }

        /**
         * Keep every session cookie this hop offered, in the order the gateway sent
         * them, and mirror them into the WebView jar the library page reads from.
         */
        private void collectSessionCookies(Response response) {
            for (String setCookie : response.headers("Set-Cookie")) {
                String cookie = SessionCookies.sessionCookie(setCookie);
                if (cookie.isEmpty()) continue;
                String name = cookie.substring(0, cookie.indexOf('=') + 1);
                if (!sessionCookie.contains(name)) {
                    sessionCookie = sessionCookie.isEmpty() ? cookie : sessionCookie + "; " + cookie;
                }
                try {
                    CookieManager cookies = CookieManager.getInstance();
                    cookies.setAcceptCookie(true);
                    cookies.setCookie(profile.httpOrigin(), setCookie);
                    cookies.flush();
                } catch (RuntimeException ignored) {
                    // The handshake only needs the pair collected above; a WebView
                    // jar that refuses the same value must not abort the login.
                }
            }
        }

        /** Absolute target of a redirect, or the same URL when it cannot be parsed. */
        private String resolveLocation(String base, String location) {
            try {
                return java.net.URI.create(base).resolve(location.trim()).toString();
            } catch (RuntimeException unparsable) {
                return base;
            }
        }

        private void connectWebSocket(String accessCookie) {
            try {
                Request.Builder requestBuilder = new Request.Builder()
                        .url(profile.webSocketUrl())
                        .header("Origin", profile.httpOrigin())
                        .header("User-Agent", "fnAudio-Android/" + com.fnaudio.client.BuildConfig.VERSION_NAME);
                String accessCode = SessionCookies.accessCodeHeader(profile.accessCode);
                if (!accessCode.isEmpty()) requestBuilder.header("X-Access-Code", accessCode);
                if (accessCookie != null && !accessCookie.isEmpty()) requestBuilder.header("Cookie", accessCookie);
                Request request = requestBuilder.build();
                socket = client.newWebSocket(request, this);
                mainHandler.postDelayed(timeoutRunnable, 20000);
            } catch (Exception exception) {
                finishError(readableError(exception));
            }
        }

        @Override
        public void onOpen(@NonNull WebSocket webSocket, @NonNull Response response) {
            AuthDiagnostics.record("ws open");
            // Same condition the client used to accept the certificate: an
            // address endpoint is trusted without the checkbox, so its pin has
            // to be observed and stored too, or every later request would be
            // verified against the platform roots and fail.
            if (profile.https && HttpClientFactory.shouldTrustEndpoint(profile)) {
                String observedPin = "";
                if (response.handshake() != null && !response.handshake().peerCertificates().isEmpty()) {
                    Certificate certificate = response.handshake().peerCertificates().get(0);
                    observedPin = CertificatePin.of(certificate);
                }
                // Some Android WebSocket stacks omit peerCertificates even
                // after the pinned trust manager accepted the TLS connection.
                // A stored pin is safe here because the handshake already
                // proved the peer matched it; first-use still requires the
                // trust-manager observation below.
                observedPin = CertificatePin.firstAvailable(
                        observedPin, tlsObservation.pin(), profile.certificatePinSha256);
                if (observedPin.isEmpty()) {
                    finishError("无法读取服务器证书指纹，已拒绝自签名 HTTPS 连接。");
                    return;
                }
                if (!profile.certificatePinSha256.isEmpty()
                        && !profile.certificatePinSha256.equals(observedPin)) {
                    finishError("服务器证书已变更，指纹与此历史连接不一致。");
                    return;
                }
                verifiedProfile = profile.withCertificatePin(observedPin);
            }
            if (password.isEmpty() && !profile.token.isEmpty()) {
                send(Attempt.AUTH_TOKEN);
            } else if (password.isEmpty() && !profile.longToken.isEmpty()) {
                send(Attempt.LONG_TOKEN);
            } else if (!password.isEmpty()) {
                send(Attempt.LOGIN_USER);
            } else {
                finishCredentialRejected("此连接没有可恢复的登录令牌，请重新输入密码。 ");
            }
        }

        @Override
        public void onMessage(@NonNull WebSocket webSocket, @NonNull String text) {
            if (completed.get()) return;
            JSONObject root = parseJson(text);
            if (root == null) return;
            JSONObject payload = findAuthPayload(root, 0);
            if (payload == null) return;
            String envelopeRequestId = firstString(root, "reqid", "reqId");
            String responseRequestId = firstString(payload, "reqid", "reqId");
            if (!requestIdMatches(requestId, envelopeRequestId, responseRequestId)) return;

            String token = firstString(payload, "token", "accessToken", "access_token");
            String longToken = firstString(payload, "longToken", "refreshToken", "refresh_token");
            String result = firstString(payload, "result", "status").toLowerCase(Locale.ROOT);
            boolean success = !token.isEmpty()
                    || "succ".equals(result)
                    || "success".equals(result)
                    || booleanField(payload, "success")
                    || intField(payload, "code", -1) == 0 && payload.has("code");
            if (success) {
                String finalToken = token;
                // authToken verifies the short token itself, so a successful
                // response may legitimately omit a replacement. Long-token
                // and password login must return a real session token; never
                // resurrect the stale short token that led to the recovery.
                if (finalToken.isEmpty() && attempt == Attempt.AUTH_TOKEN) {
                    finalToken = verifiedProfile.token;
                }
                String finalLongToken = longToken.isEmpty() ? verifiedProfile.longToken : longToken;
                if (finalToken.isEmpty()) {
                    handleAttemptFailure(intField(payload, "errno", 0),
                            messageFrom(payload, "登录成功响应中缺少会话令牌。"));
                    return;
                }
                finishSuccess(verifiedProfile.withTokens(finalToken, finalLongToken));
                return;
            }

            if (payload.has("result") || payload.has("errno") || payload.has("errmsg") || payload.has("error")) {
                handleAttemptFailure(intField(payload, "errno", 0), messageFrom(payload, "fnOS 拒绝了登录请求。"));
            }
        }

        @Override
        public void onFailure(@NonNull WebSocket webSocket, @NonNull Throwable throwable, @Nullable Response response) {
            // finishSuccess closes the socket immediately after receiving the
            // credential response. OkHttp may report that close as EOF/cancel.
            if (completed.get()) return;
            AuthDiagnostics.record("ws failure " + throwable.getClass().getSimpleName());
            Log.w(TAG, "WebSocket authentication connection failed: host=" + profile.host
                    + ", port=" + profile.port + ", https=" + profile.https
                    + ", error=" + throwable.getClass().getSimpleName()
                    + ", detail=" + safeDiagnostic(throwable));
            finishError(readableError(throwable));
        }

        @Override
        public void onClosed(@NonNull WebSocket webSocket, int code, @NonNull String reason) {
            if (!completed.get()) finishError(reason.isEmpty() ? "fnOS 在登录完成前关闭了连接。" : reason);
        }

        private void send(Attempt nextAttempt) {
            if (completed.get() || socket == null) return;
            attempt = nextAttempt;
            AuthDiagnostics.record("login attempt=" + nextAttempt);
            requestId = requestId();
            JSONObject request = new JSONObject();
            put(request, "reqid", requestId);
            switch (nextAttempt) {
                case AUTH_TOKEN:
                    put(request, "req", "user.authToken");
                    put(request, "token", profile.token);
                    put(request, "main", true);
                    put(request, "active", true);
                    break;
                case LONG_TOKEN:
                    put(request, "req", "user.tokenLogin");
                    put(request, "token", profile.longToken);
                    put(request, "deviceName", "fnAudio Android");
                    put(request, "deviceType", "Android");
                    break;
                case LOGIN_USER:
                case LOGIN_USERNAME:
                    put(request, "req", "user.login");
                    put(request, nextAttempt == Attempt.LOGIN_USER ? "user" : "username", profile.username);
                    put(request, "password", password);
                    put(request, "stay", 1);
                    put(request, "deviceName", "fnAudio Android");
                    put(request, "deviceType", "Android");
                    break;
            }
            if (!socket.send(request.toString())) finishError("登录请求未能发送到 fnOS。 ");
        }

        private void handleAttemptFailure(int errno, String message) {
            AuthDiagnostics.record("login rejected attempt=" + attempt + " errno=" + errno);
            // fnOS expires both stored tokens eventually (the short one in
            // minutes, the long one in weeks), so a record that worked for a
            // while stops working days later. The saved password is still the
            // credential the user already gave this app; spend it here instead of
            // surfacing a failure the caller then has to recover from with a
            // second round trip and a chooser screen.
            Attempt next = nextAttemptAfterFailure(
                    attempt, errno, !profile.longToken.isEmpty(), !password.isEmpty());
            if (next != null) {
                // The swapped-user frame only runs after fnOS said the request
                // itself was not understood, and it is answered with a generic
                // "missing field" number. Keep the earlier message so the user
                // is told what actually happened.
                if (attempt == Attempt.LOGIN_USER) loginFallbackMessage = message;
                send(next);
                return;
            }
            if (attempt == Attempt.LOGIN_USERNAME && !loginFallbackMessage.isEmpty()) {
                finishCredentialRejected(loginFallbackMessage);
                return;
            }
            finishCredentialRejected(message);
        }

        /**
         * One line that says where the attempt died.
         *
         * "登录过几天就不行" is impossible to diagnose from a toast: the phase
         * (access-code verification, redirect hop, handshake, credential round)
         * and whether a session cookie was ever obtained are what separate a
         * gateway change from an expired token. `adb logcat -s FnOsAuth` is then
         * enough, with no rebuild.
         */
        private void logFailure(String kind, String message) {
            AuthDiagnostics.record("failure kind=" + kind
                    + " phase=" + (socket == null ? "pre-handshake" : "handshake")
                    + " attempt=" + attempt
                    + " cookie=" + (sessionCookie.isEmpty() ? "absent" : "present")
                    + " hops=" + accessCodeHops
                    + " msg=" + message);
            Log.w(TAG, "authentication " + kind
                    + ": phase=" + (socket == null ? "pre-handshake" : "handshake")
                    + ", attempt=" + attempt
                    + ", sessionCookie=" + (sessionCookie.isEmpty() ? "absent" : "present")
                    + ", redirects=" + accessCodeHops
                    + ", usedPassword=" + !password.isEmpty()
                    + ", message=" + message);
        }

        private void finishSuccess(ConnectionProfile authenticatedProfile) {
            if (!completed.compareAndSet(false, true)) return;
            mainHandler.removeCallbacks(timeoutRunnable);
            if (socket != null) socket.close(1000, "authenticated");
            client.dispatcher().executorService().shutdown();
            mainHandler.post(() -> {
                if (deliverCallback.get()) callback.onSuccess(authenticatedProfile);
                clear(this);
            });
        }

        private void finishError(String message) {
            if (!completed.compareAndSet(false, true)) return;
            logFailure("error", message);
            mainHandler.removeCallbacks(timeoutRunnable);
            if (socket != null) socket.cancel();
            client.dispatcher().executorService().shutdown();
            mainHandler.post(() -> {
                if (deliverCallback.get()) callback.onError(message);
                clear(this);
            });
        }

        private void finishCredentialRejected(String message) {
            if (!completed.compareAndSet(false, true)) return;
            logFailure("rejected", message);
            mainHandler.removeCallbacks(timeoutRunnable);
            if (socket != null) socket.cancel();
            client.dispatcher().executorService().shutdown();
            mainHandler.post(() -> {
                if (deliverCallback.get()) callback.onCredentialRejected(message);
                clear(this);
            });
        }

        private void cancel() {
            deliverCallback.set(false);
            completed.set(true);
            mainHandler.removeCallbacks(timeoutRunnable);
            if (socket != null) socket.cancel();
            client.dispatcher().cancelAll();
            client.dispatcher().executorService().shutdownNow();
            // Evicting the pool closes pooled sockets, including TLS ones, and
            // this runs on whichever thread cancelled the attempt — the UI
            // thread whenever a rejected token falls back to the saved password.
            // Doing that inline killed the process on Android 13:
            //   RealConnectionPool.evictAll -> Util.closeQuietly
            //   at FnOsAuthClient$Session.cancel
            //   at LoginActivity$3.onCredentialRejected   (2026-11-11)
            // Hand it to a throwaway thread; the pool expires on its own anyway.
            final okhttp3.OkHttpClient draining = client;
            try {
                new Thread(() -> {
                    try { draining.connectionPool().evictAll(); } catch (RuntimeException ignored) { }
                }, "fnaudio-auth-pool-drain").start();
            } catch (RuntimeException ignored) {
                // Refusing to spawn a thread must not take down the caller.
            }
        }
    }

    private static JSONObject parseJson(String text) {
        if (text == null || text.length() > MAX_AUTH_MESSAGE_CHARS) return null;
        int start = text.indexOf('{');
        int end = text.lastIndexOf('}');
        if (start < 0 || end < start) return null;
        try {
            return new JSONObject(text.substring(start, end + 1));
        } catch (Exception ignored) {
            return null;
        }
    }

    private static JSONObject findAuthPayload(JSONObject object, int depth) {
        if (object == null || depth > 5) return null;
        if (object.has("token") || object.has("longToken")
                || object.has("accessToken") || object.has("access_token")
                || object.has("refreshToken") || object.has("refresh_token")) {
            return object;
        }
        String[] keys = {"data", "body", "payload", "response", "rsp"};
        for (String key : keys) {
            JSONObject nested = object.optJSONObject(key);
            JSONObject found = findAuthPayload(nested, depth + 1);
            if (found != null) return found;
            Object rawEncoded = object.opt(key);
            String encoded = rawEncoded instanceof String ? (String) rawEncoded : "";
            JSONObject parsed = parseJson(encoded);
            found = findAuthPayload(parsed, depth + 1);
            if (found != null) return found;
        }
        // Some fnOS versions put errno/result on the outer envelope and the
        // real credentials in data/body. Only fall back to envelope status
        // after every nested credential location has been inspected.
        return object.has("errno") || object.has("errmsg") || object.has("error")
                || object.has("result") || object.has("status") ? object : null;
    }

    private static String messageFrom(JSONObject payload, String fallback) {
        String message = firstString(payload, "errmsg", "message", "error", "msg");
        int errno = intField(payload, "errno", 0);
        if (message.isEmpty()) message = knownErrnoMessage(errno);
        if (message.isEmpty()) message = fallback;
        return errno == 0 ? message : message + "（错误码 " + errno + "）";
    }

    /**
     * What a bare {@code errno} means, in words a user can act on.
     *
     * <p>Returns an empty string for anything unmapped so the caller can fall
     * back to its own wording. The number is still appended by the caller: it is
     * the only thing support can match against a server log.
     */
    static String knownErrnoMessage(int errno) {
        switch (errno) {
            case ERRNO_CREDENTIALS_REJECTED:
                return "账号或密码错误，请检查后重试。";
            case ERRNO_MISSING_FIELD:
                return "登录请求缺少参数，这台 fnOS 的登录接口可能变了，请更新客户端。";
            case ERRNO_UNKNOWN_REQUEST:
                return "这台 fnOS 不支持当前的登录方式，请更新客户端。";
            default:
                return "";
        }
    }

    private static boolean booleanField(JSONObject object, String key) {
        Object value = object == null ? null : object.opt(key);
        return value instanceof Boolean && (Boolean) value;
    }

    private static int intField(JSONObject object, String key, int fallback) {
        Object value = object == null ? null : object.opt(key);
        if (!(value instanceof Number)) return fallback;
        double numeric = ((Number) value).doubleValue();
        if (!Double.isFinite(numeric) || numeric != Math.rint(numeric)
                || numeric < Integer.MIN_VALUE || numeric > Integer.MAX_VALUE) return fallback;
        return (int) numeric;
    }

    private static String firstString(JSONObject object, String... keys) {
        for (String key : keys) {
            Object value = object.opt(key);
            if (!(value instanceof String)) continue;
            String text = ((String) value).trim();
            if (!text.isEmpty() && text.length() <= MAX_AUTH_VALUE_CHARS) return text;
        }
        return "";
    }

    private static void put(JSONObject object, String key, Object value) {
        try {
            object.put(key, value);
        } catch (Exception ignored) {
        }
    }

    private static String requestId() {
        String timestamp = Long.toHexString(System.currentTimeMillis());
        String random = UUID.randomUUID().toString().replace("-", "");
        String value = timestamp + random;
        return value.length() > 32 ? value.substring(0, 32) : value;
    }

    static boolean requestIdMatches(String expected, String envelope, String payload) {
        if (expected == null || expected.isEmpty()) return false;
        if (envelope != null && !envelope.isEmpty() && !expected.equals(envelope)) return false;
        return payload == null || payload.isEmpty() || expected.equals(payload);
    }

    /**
     * The prefix for a failed connection attempt.
     *
     * <p>"访问码验证失败" is right when the request reached the server and was
     * refused, but it is actively misleading when the name never resolved: the
     * user sees an English {@code Unable to resolve host} behind a prefix that
     * blames the access code.  Reported 2026-11-11 with an fnos.net address on
     * mobile data.
     */
    private static String describeConnectFailure(java.io.IOException exception) {
        if (isHostResolutionFailure(exception)) return readableError(exception);
        return "访问码验证失败：" + readableError(exception);
    }

    private static boolean isHostResolutionFailure(Throwable throwable) {
        for (Throwable current = throwable; current != null; current = current.getCause()) {
            if (current instanceof java.net.UnknownHostException) return true;
            String message = current.getMessage();
            if (message == null) continue;
            String lower = message.toLowerCase(Locale.ROOT);
            if (lower.contains("unable to resolve host") || lower.contains("no address associated")) {
                return true;
            }
        }
        return false;
    }

    private static String readableError(Throwable throwable) {
        String raw = throwable == null ? "" : String.valueOf(throwable.getMessage());
        String lower = raw.toLowerCase(Locale.ROOT);
        if (lower.contains("certificate") || lower.contains("sslpeer") || lower.contains("trust anchor")) {
            if (lower.contains("pin mismatch")) {
                return "服务器证书已变更，已拒绝连接。请确认 NAS 证书后删除该历史连接并重新建立。";
            }
            return "HTTPS 证书校验失败；如果 NAS 使用自签名证书，请开启自签名证书兼容。";
        }
        if (isHostResolutionFailure(throwable)) {
            // The DNS answer is missing, so nothing about the NAS, its
            // certificate or the access code has been tested yet.
            return "无法解析服务器域名。请检查手机网络（若开启「私有 DNS」可先关闭），或改用 FN ID 登录。";
        }
        if (lower.contains("failed to connect") || lower.contains("connection refused")) {
            return "无法连接 NAS，请检查地址和端口。";
        }
        if (lower.contains("timeout")) return "连接超时，请确认 NAS 可以从手机访问。";
        return raw.isEmpty() ? "fnOS 登录连接失败。" : raw;
    }

    private static String safeDiagnostic(Throwable throwable) {
        if (throwable == null) return "";
        String message = throwable.getMessage();
        Throwable cause = throwable.getCause();
        String causeMessage = cause == null ? "" : cause.getMessage();
        // Socket diagnostics do not include application credentials or tokens.
        return (message == null ? "" : message) + (causeMessage == null || causeMessage.isEmpty()
                ? "" : " cause=" + cause.getClass().getSimpleName() + ": " + causeMessage);
    }
}
