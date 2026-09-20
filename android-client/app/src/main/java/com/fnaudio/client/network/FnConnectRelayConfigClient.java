package com.fnaudio.client.network;

import androidx.annotation.NonNull;

import org.json.JSONObject;

import java.io.IOException;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.RejectedExecutionException;

import okhttp3.Call;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.ResponseBody;

final class FnConnectRelayConfigClient {
    interface Callback {
        void onConfig(JSONObject config);
        void onError(String message);
    }

    private static final String PATH = "/api/v1/visit/info";
    private static final int MAX_RESPONSE_BYTES = 256 * 1024;
    private static final int MAX_TOKEN_CHARS = 4096;
    private static final int MAX_SECRET_CHARS = 4096;
    private static final int MAX_HOST_CHARS = 255;
    private static final int MAX_NAS_ID_CHARS = 256;
    private static final int MAX_STUN_CHARS = 512;
    private static final int MAX_PROTOCOL_CHARS = 32;
    private static final int MAX_LOG_LEVEL_CHARS = 32;
    private static final int MAX_FN_ID_CHARS = 64;
    private static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");
    private final OkHttpClient client;
    private final Object lock = new Object();
    private Call activeCall;

    FnConnectRelayConfigClient(OkHttpClient client) {
        this.client = client;
    }

    void fetch(String fnId, Callback callback) {
        if (!validFnId(fnId)) {
            callback.onError("FN Connect ID 格式不正确");
            return;
        }
        JSONObject payload = new JSONObject();
        try {
            payload.put("fnId", fnId);
        } catch (Exception ignored) {
        }
        String body = payload.toString();
        long timestamp = System.currentTimeMillis();
        String nonce = String.valueOf(100000 + (int) (Math.random() * 900000));
        String fnSign = sha256("trim_connect`" + fnId + "`" + timestamp + "`anna");
        String authDigest = md5("NDzZTVxnRKP8Z0jXg1VAMonaG8akvh_" + PATH + "_" + nonce + "_"
                + timestamp + "_" + md5(body) + "_zIGtkc3dqZnJpd29qZXJqa2w7c");
        Request request = new Request.Builder()
                .url("https://fnos.net" + PATH)
                .header("fn-sign", fnSign)
                .header("authx", "nonce=" + nonce + "&timestamp=" + timestamp + "&sign=" + authDigest)
                .post(RequestBody.create(body, JSON))
                .build();
        Call call = client.newCall(request);
        synchronized (lock) {
            if (activeCall != null) activeCall.cancel();
            activeCall = call;
        }
        try {
            call.enqueue(new okhttp3.Callback() {
            @Override
            public void onFailure(@NonNull Call failedCall, @NonNull IOException error) {
                if (!finish(failedCall)) return;
                callback.onError("中继配置获取失败：" + readable(error));
            }

            @Override
            public void onResponse(@NonNull Call completedCall, @NonNull Response response) {
                if (!isActive(completedCall)) {
                    response.close();
                    return;
                }
                try (Response closeable = response) {
                    ResponseBody responseBody = closeable.body();
                    String text = readBoundedText(responseBody, MAX_RESPONSE_BYTES);
                    if (!closeable.isSuccessful()) {
                        if (finish(completedCall)) {
                            callback.onError("中继配置获取失败（HTTP " + closeable.code() + "）");
                        }
                        return;
                    }
                    JSONObject config = parseConfig(fnId, new JSONObject(text));
                    if (finish(completedCall)) callback.onConfig(config);
                } catch (Exception error) {
                    if (finish(completedCall)) callback.onError("FN Connect 中继配置无效");
                }
            }
            });
        } catch (RejectedExecutionException error) {
            if (finish(call)) callback.onError("中继配置获取失败：网络客户端已关闭");
        }
    }

    private static String readBoundedText(ResponseBody body, int maxBytes) throws IOException {
        if (body == null || maxBytes <= 0) throw new IOException("empty response body");
        long declared = body.contentLength();
        if (declared > maxBytes) throw new IOException("response body is too large");
        InputStream input = body.byteStream();
        ByteArrayOutputStream output = new ByteArrayOutputStream(
                (int) Math.min(Math.max(declared, 0L), maxBytes));
        byte[] buffer = new byte[8192];
        int total = 0;
        int count;
        while ((count = input.read(buffer)) != -1) {
            if (count == 0) continue;
            if (count > maxBytes - total) throw new IOException("response body is too large");
            output.write(buffer, 0, count);
            total += count;
        }
        return output.toString(StandardCharsets.UTF_8.name());
    }

    void cancel() {
        synchronized (lock) {
            if (activeCall != null) activeCall.cancel();
            activeCall = null;
        }
    }

    private boolean finish(Call call) {
        synchronized (lock) {
            if (activeCall != call) return false;
            activeCall = null;
            return true;
        }
    }

    private boolean isActive(Call call) {
        synchronized (lock) {
            return activeCall == call;
        }
    }

    static JSONObject parseConfig(String fnId, JSONObject root) throws Exception {
        if (!validFnId(fnId)) throw new IllegalArgumentException("invalid FN Connect id");
        if (intField(root, "code", -1) != 0) throw new IllegalArgumentException("visit info rejected");
        JSONObject data = root.optJSONObject("data");
        JSONObject server = data == null ? null : data.optJSONObject("applyServer");
        JSONObject connect = server == null ? null : server.optJSONObject("connectConfig");
        if (data == null || server == null) throw new IllegalArgumentException("visit info missing");

        String token = stringField(server, "t").trim();
        String secret = stringField(server, "s").trim();
        String host = stringField(server, "ip").trim();
        String nasId = stringField(data, "nasId").trim();
        int port = intField(server, "port", 0);
        String stun = connect == null ? "" : stringField(connect, "stunServer").trim();
        if (token.isEmpty() || secret.isEmpty() || host.isEmpty() || !safeHost(host) || nasId.isEmpty()
                || token.length() > MAX_TOKEN_CHARS || secret.length() > MAX_SECRET_CHARS
                || host.length() > MAX_HOST_CHARS || nasId.length() > MAX_NAS_ID_CHARS
                || stun.length() > MAX_STUN_CHARS || port < 1 || port > 65535) {
            throw new IllegalArgumentException("visit info incomplete");
        }

        String logLevel = stringField(server, "logLevel").trim();
        String protocol = stringField(server, "protocol").trim();
        if (logLevel.length() > MAX_LOG_LEVEL_CHARS || protocol.length() > MAX_PROTOCOL_CHARS) {
            throw new IllegalArgumentException("visit info contains oversized fields");
        }
        JSONObject result = new JSONObject();
        result.put("log_level", logLevel.isEmpty() ? "error" : logLevel);
        result.put("token", token);
        result.put("server_host", host);
        result.put("server_port", port);
        result.put("run_id", runId());
        result.put("stun_server", stun);
        result.put("transport_protocol", protocol.isEmpty() ? "quic" : protocol);
        result.put("visit_server", nasId);
        result.put("visitor_name", "v-" + fnId);
        result.put("visit_secret_key", secret);
        return result;
    }

    private static String stringField(JSONObject object, String key) {
        Object value = object == null ? null : object.opt(key);
        return value instanceof String ? (String) value : "";
    }

    private static boolean validFnId(String value) {
        return value != null && value.length() >= 3 && value.length() <= MAX_FN_ID_CHARS
                && value.matches("[a-z0-9-]+");
    }

    /** Native relay config accepts a host/IP literal, never a URI or control data. */
    private static boolean safeHost(String value) {
        if (value == null || value.isEmpty() || value.length() > MAX_HOST_CHARS) return false;
        boolean hasAddressCharacter = false;
        for (int index = 0; index < value.length(); index++) {
            char character = value.charAt(index);
            if ((character >= 'a' && character <= 'z')
                    || (character >= 'A' && character <= 'Z')
                    || (character >= '0' && character <= '9')) {
                hasAddressCharacter = true;
                continue;
            }
            if (character != '.' && character != '-' && character != ':'
                    && character != '[' && character != ']') return false;
        }
        return hasAddressCharacter;
    }

    private static int intField(JSONObject object, String key, int fallback) {
        Object value = object == null ? null : object.opt(key);
        if (!(value instanceof Number)) return fallback;
        double numeric = ((Number) value).doubleValue();
        if (!Double.isFinite(numeric) || numeric != Math.rint(numeric)
                || numeric < Integer.MIN_VALUE || numeric > Integer.MAX_VALUE) return fallback;
        return (int) numeric;
    }

    private static String runId() {
        String time = new SimpleDateFormat("yyyyMMdd-HHmm", Locale.ROOT).format(new Date());
        return "p2pv2-" + time + "-" + UUID.randomUUID();
    }

    private static String readable(Exception error) {
        String message = error.getMessage();
        return message == null || message.trim().isEmpty() ? "网络错误" : message;
    }

    private static String md5(String value) {
        return digest("MD5", value);
    }

    private static String sha256(String value) {
        return digest("SHA-256", value);
    }

    private static String digest(String algorithm, String value) {
        try {
            byte[] bytes = MessageDigest.getInstance(algorithm).digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder output = new StringBuilder(bytes.length * 2);
            for (byte item : bytes) output.append(String.format(Locale.ROOT, "%02x", item & 0xff));
            return output.toString();
        } catch (Exception ignored) {
            return "";
        }
    }
}
