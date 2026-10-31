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
    public interface Callback {
        void onSuccess(ConnectionProfile authenticatedProfile);

        void onError(String message);

        /** Called only when fnOS explicitly rejects the stored credentials. */
        default void onCredentialRejected(String message) {
            onError(message);
        }
    }

    private enum Attempt {
        AUTH_TOKEN,
        LONG_TOKEN,
        LOGIN_USER,
        LOGIN_USERNAME
    }

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    @Nullable private Session currentSession;

    public synchronized void authenticate(Context context, ConnectionProfile profile, @Nullable String password, Callback callback) {
        if (currentSession != null) currentSession.cancel();
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
        private String requestId = "";
        private String accessCodeCookie = "";

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
            Request request = new Request.Builder()
                    .url(profile.httpOrigin() + "/access_code_verify")
                    .header("X-Access-Code", accessCode)
                    .header("X-Access-Source", "web")
                    .get()
                    .build();
            client.newCall(request).enqueue(new okhttp3.Callback() {
                @Override public void onFailure(@NonNull okhttp3.Call call, @NonNull java.io.IOException exception) {
                    finishError("访问码验证失败：" + readableError(exception));
                }

                @Override public void onResponse(@NonNull okhttp3.Call call, @NonNull Response response) {
                    try (Response ignored = response) {
                        if (!response.isSuccessful()) {
                            finishError("访问码验证失败：HTTP " + response.code());
                            return;
                        }
                        for (String setCookie : response.headers("Set-Cookie")) {
                            String cookie = SessionCookies.accessCodeCookie(setCookie);
                            if (!cookie.isEmpty()) {
                                accessCodeCookie = cookie;
                                CookieManager cookies = CookieManager.getInstance();
                                cookies.setAcceptCookie(true);
                                cookies.setCookie(profile.httpOrigin(), setCookie);
                                cookies.flush();
                                break;
                            }
                        }
                        if (accessCodeCookie.isEmpty()) {
                            finishError("访问码验证成功但未取得会话 Cookie。");
                            return;
                        }
                        connectWebSocket(accessCodeCookie);
                    }
                }
            });
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
            if (profile.https && profile.trustSelfSigned) {
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
                    handleAttemptFailure(messageFrom(payload, "登录成功响应中缺少会话令牌。"));
                    return;
                }
                finishSuccess(verifiedProfile.withTokens(finalToken, finalLongToken));
                return;
            }

            if (payload.has("result") || payload.has("errno") || payload.has("errmsg") || payload.has("error")) {
                handleAttemptFailure(messageFrom(payload, "fnOS 拒绝了登录请求。"));
            }
        }

        @Override
        public void onFailure(@NonNull WebSocket webSocket, @NonNull Throwable throwable, @Nullable Response response) {
            // finishSuccess closes the socket immediately after receiving the
            // credential response. OkHttp may report that close as EOF/cancel.
            if (completed.get()) return;
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

        private void handleAttemptFailure(String message) {
            if (attempt == Attempt.AUTH_TOKEN && !profile.longToken.isEmpty()) {
                send(Attempt.LONG_TOKEN);
                return;
            }
            if (attempt == Attempt.LOGIN_USER) {
                send(Attempt.LOGIN_USERNAME);
                return;
            }
            finishCredentialRejected(message);
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
            client.connectionPool().evictAll();
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
        if (message.isEmpty()) message = fallback;
        int errno = intField(payload, "errno", 0);
        return errno == 0 ? message : message + "（错误码 " + errno + "）";
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

    private static String readableError(Throwable throwable) {
        String raw = throwable == null ? "" : String.valueOf(throwable.getMessage());
        String lower = raw.toLowerCase(Locale.ROOT);
        if (lower.contains("certificate") || lower.contains("sslpeer") || lower.contains("trust anchor")) {
            if (lower.contains("pin mismatch")) {
                return "服务器证书已变更，已拒绝连接。请确认 NAS 证书后删除该历史连接并重新建立。";
            }
            return "HTTPS 证书校验失败；如果 NAS 使用自签名证书，请开启自签名证书兼容。";
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
