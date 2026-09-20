package com.fnaudio.client.network;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.fnaudio.client.data.ConnectionProfile;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.Inet6Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.concurrent.RejectedExecutionException;

import okhttp3.Call;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.ResponseBody;

/** Resolves an FN ID to the NAS public endpoint. IPv6 is always preferred. */
public final class FnConnectResolver {
    private static final String TAG = "FnConnect";
    private static final int MAX_RESPONSE_BYTES = 512 * 1024;
    private static final int MAX_HOSTS_PER_FAMILY = 64;
    private static final int MAX_HOST_CHARS = 255;
    private static final long DIRECT_PROBE_BUDGET_MS = 8000L;
    private static final int DIRECT_PROBE_TIMEOUT_MS = 1800;
    public enum Mode { AUTO, PUBLIC, RELAY }
    public interface Callback {
        void onResolved(ConnectionProfile profile);
        void onError(String message);
    }

    private static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");
    private final Handler main = new Handler(Looper.getMainLooper());
    private final OkHttpClient client = new OkHttpClient.Builder().build();
    @Nullable private final FnConnectRelayConfigClient relayConfigClient;
    @Nullable private final TppsTunnel tunnel;
    private final Object callLock = new Object();
    private Call activeCall;
    @Nullable private Socket activeProbeSocket;
    private long callGeneration;
    private boolean closed;

    public FnConnectResolver() {
        this(null);
    }

    public FnConnectResolver(@Nullable Context context) {
        relayConfigClient = context == null ? null : new FnConnectRelayConfigClient(client);
        tunnel = context == null ? null : TppsTunnel.get(context);
    }

    public void resolve(String rawFnId, Callback callback) {
        resolve(rawFnId, Mode.AUTO, callback);
    }

    public void resolve(String rawFnId, Mode mode, Callback callback) {
        String fnId = rawFnId == null ? "" : rawFnId.trim().toLowerCase(java.util.Locale.ROOT);
        // Reserve the request generation before constructing the request. A
        // caller can issue two resolves concurrently; the later invocation
        // must remain authoritative even if the earlier thread is delayed
        // while building its payload or Call object.
        final long generation = replaceActiveWork(null);
        if (generation < 0L) {
            main.post(() -> callback.onError("FN Connect 解析器已关闭"));
            return;
        }
        if (!fnId.matches("[a-z0-9-]{3,64}")) {
            deliver(generation, () -> callback.onError("FN ID 格式不正确"));
            return;
        }
        JSONObject payload = new JSONObject();
        try { payload.put("fnId", fnId); } catch (Exception ignored) { }
        String body = payload.toString();
        long timestamp = System.currentTimeMillis();
        String nonce = String.valueOf(100000 + (int) (Math.random() * 900000));
        String fnSign = sha256("trim_connect`" + fnId + "`" + timestamp + "`anna");
        String authDigest = md5("NDzZTVxnRKP8Z0jXg1VAMonaG8akvh_/api/v1/fn/con_" + nonce + "_" + timestamp
                + "_" + md5(body) + "_zIGtkc3dqZnJpd29qZXJqa2w7c");
        Request request = new Request.Builder().url("https://fnos.net/api/v1/fn/con")
                .header("fn-sign", fnSign)
                .header("authx", "nonce=" + nonce + "&timestamp=" + timestamp + "&sign=" + authDigest)
                .post(RequestBody.create(body, JSON)).build();
        Call call = client.newCall(request);
        if (!attachActiveCall(call, generation)) {
            return;
        }
        try {
            call.enqueue(new okhttp3.Callback() {
            @Override public void onFailure(@NonNull Call call, @NonNull IOException error) {
                finish(call, generation, () -> callback.onError("无法解析 FN ID：" + readable(error)));
            }

            @Override public void onResponse(@NonNull Call call, @NonNull Response response) {
                if (!isActive(call, generation)) {
                    response.close();
                    return;
                }
                try (Response closeable = response) {
                    ResponseBody responseBody = closeable.body();
                    String responseText = readBoundedText(responseBody, MAX_RESPONSE_BYTES);
                    if (!closeable.isSuccessful()) {
                        finish(call, generation, () -> callback.onError("FN Connect 解析失败（HTTP " + closeable.code() + "）"));
                        return;
                    }
                    JSONObject root = new JSONObject(responseText);
                    JSONObject data = root.optJSONObject("data");
                    if (data == null) data = root;
                    if (mode == Mode.RELAY) {
                        if (relayConfigClient != null && tunnel != null) {
                            beginRelay(call, generation, fnId, null, callback);
                        } else {
                            finish(call, generation, () -> callback.onError("当前环境不支持 FN Connect P2P 中继"));
                        }
                        return;
                    }
                    ConnectionProfile resolved = choose(fnId, data, generation);
                    if (resolved != null) {
                        finish(call, generation, () -> callback.onResolved(resolved));
                    } else {
                        ConnectionProfile fallback = fallback(fnId, data);
                        if (mode == Mode.AUTO && relayConfigClient != null && tunnel != null) {
                            beginRelay(call, generation, fnId, fallback, callback);
                        } else if (fallback != null) {
                            finish(call, generation, () -> callback.onResolved(fallback));
                        } else {
                            finish(call, generation, () -> callback.onError("FN Connect 未发现可用的公网地址或中继"));
                        }
                    }
                } catch (Exception error) {
                    finish(call, generation, () -> callback.onError("FN Connect 返回数据无法识别"));
                }
            }
            });
        } catch (RejectedExecutionException error) {
            finish(call, generation, () -> callback.onError("FN Connect 解析器已关闭"));
        }
    }

    private static String readBoundedText(@Nullable ResponseBody body, int maxBytes) throws IOException {
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
        return output.toString(java.nio.charset.StandardCharsets.UTF_8.name());
    }

    public void cancel() {
        replaceActiveWork(null);
    }

    /** Replaces all phases of one resolve request as one cancellation domain. */
    private long replaceActiveWork(@Nullable Call replacement) {
        synchronized (callLock) {
            // Once closed, no new generation may be created. This also
            // covers resolve() racing with close(): otherwise a post-close
            // request could build a Call and fail silently on the shut
            // dispatcher, while invalid input could report the wrong error.
            if (closed) return -1L;
            if (relayConfigClient != null) relayConfigClient.cancel();
            if (tunnel != null) tunnel.cancel();
            if (activeCall != null) activeCall.cancel();
            if (activeProbeSocket != null) {
                try { activeProbeSocket.close(); } catch (IOException ignored) { }
                activeProbeSocket = null;
            }
            activeCall = replacement;
            return ++callGeneration;
        }
    }

    /** Attach a request only if its generation is still the latest one. */
    private boolean attachActiveCall(Call call, long generation) {
        synchronized (callLock) {
            if (closed || callGeneration != generation) {
                call.cancel();
                return false;
            }
            activeCall = call;
            return true;
        }
    }

    public void close() {
        synchronized (callLock) {
            if (closed) return;
            closed = true;
            // Do not call cancel() after setting closed: replaceActiveWork()
            // intentionally rejects new generations once closed, so that
            // sequence would leave the current call, relay request, and
            // probe socket running during Activity teardown.
            ++callGeneration;
            if (relayConfigClient != null) relayConfigClient.cancel();
            if (tunnel != null) tunnel.cancel();
            if (activeCall != null) {
                activeCall.cancel();
                activeCall = null;
            }
            if (activeProbeSocket != null) {
                try { activeProbeSocket.close(); } catch (IOException ignored) { }
                activeProbeSocket = null;
            }
        }
        // This resolver owns a dedicated OkHttp dispatcher. Cancelling calls
        // alone leaves its executor available after Activity destruction and
        // repeated login/connection switches accumulate idle worker threads.
        // Executor shutdown is non-blocking; avoid evicting the connection
        // pool here because that can synchronously touch TLS sockets on the
        // main thread on some Android builds.
        client.dispatcher().executorService().shutdown();
    }

    private boolean isActive(Call call, long generation) {
        synchronized (callLock) {
            return activeCall == call && callGeneration == generation;
        }
    }

    private void finish(Call call, long generation, Runnable callback) {
        synchronized (callLock) {
            if (activeCall != call || callGeneration != generation) return;
            activeCall = null;
        }
        main.post(() -> {
            synchronized (callLock) {
                if (callGeneration != generation) return;
            }
            callback.run();
        });
    }

    private void beginRelay(Call call, long generation, String fnId,
                            @Nullable ConnectionProfile directFallback, Callback callback) {
        synchronized (callLock) {
            if (activeCall != call || callGeneration != generation) return;
            activeCall = null;
        }
        relayConfigClient.fetch(fnId, new FnConnectRelayConfigClient.Callback() {
            @Override
            public void onConfig(JSONObject config) {
                if (!isGenerationActive(generation)) return;
                tunnel.start(config, new TppsTunnel.Callback() {
                    @Override
                    public void onReady(int port) {
                        deliver(generation, () -> callback.onResolved(ConnectionProfile.create(
                                "", "FN Connect - " + fnId, "127.0.0.1", port,
                                false, false, "", "")));
                    }

                    @Override
                    public void onError(String message) {
                        relayFailed(generation, directFallback, callback, message);
                    }
                });
            }

            @Override
            public void onError(String message) {
                relayFailed(generation, directFallback, callback, message);
            }
        });
    }

    private void relayFailed(long generation, @Nullable ConnectionProfile directFallback,
                             Callback callback, String message) {
        Log.w(TAG, message);
        deliver(generation, () -> {
            if (directFallback != null) callback.onResolved(directFallback);
            else callback.onError(message);
        });
    }

    private boolean isGenerationActive(long generation) {
        synchronized (callLock) {
            return callGeneration == generation;
        }
    }

    private void deliver(long generation, Runnable callback) {
        main.post(() -> {
            if (isGenerationActive(generation)) callback.run();
        });
    }

    private ConnectionProfile choose(String fnId, JSONObject data, long generation) {
        JSONObject ports = data.optJSONObject("port");
        int httpPort = port(ports != null ? ports : data, "httpPort", "http_port", 5666);
        int httpsPort = port(ports != null ? ports : data, "httpsPort", "https_port", 5667);
        Set<String> ipv6Hosts = new LinkedHashSet<>();
        Set<String> ipv4Hosts = new LinkedHashSet<>();
        collect(ipv6Hosts, data, "publicIpv6", "publicIPv6", "ipv6", "public_ipv6");
        collect(ipv4Hosts, data, "publicIpv4", "publicIPv4", "publicIp", "publicIP", "ipv4", "public_ipv4");
        JSONObject network = data.optJSONObject("network");
        if (network != null) {
            collect(ipv6Hosts, network, "publicIpv6", "publicIPv6", "ipv6", "public_ipv6");
            collect(ipv4Hosts, network, "publicIpv4", "publicIPv4", "publicIp", "publicIP", "ipv4", "public_ipv4");
        }
        long deadlineElapsedRealtime = SystemClock.elapsedRealtime() + DIRECT_PROBE_BUDGET_MS;
        ConnectionProfile ipv6 = firstReachable(fnId, ipv6Hosts, true, httpPort, httpsPort, generation, deadlineElapsedRealtime);
        if (ipv6 != null) return ipv6;
        ConnectionProfile ipv4 = firstReachable(fnId, ipv4Hosts, false, httpPort, httpsPort, generation, deadlineElapsedRealtime);
        if (ipv4 != null) return ipv4;
        return null;
    }

    @Nullable
    private ConnectionProfile fallback(String fnId, JSONObject data) {
        JSONObject ports = data.optJSONObject("port");
        int httpPort = port(ports != null ? ports : data, "httpPort", "http_port", 5666);
        int httpsPort = port(ports != null ? ports : data, "httpsPort", "https_port", 5667);
        Set<String> ipv6Hosts = new LinkedHashSet<>();
        Set<String> ipv4Hosts = new LinkedHashSet<>();
        collect(ipv6Hosts, data, "publicIpv6", "publicIPv6", "ipv6", "public_ipv6");
        collect(ipv4Hosts, data, "publicIpv4", "publicIPv4", "publicIp", "publicIP", "ipv4", "public_ipv4");
        JSONObject network = data.optJSONObject("network");
        if (network != null) {
            collect(ipv6Hosts, network, "publicIpv6", "publicIPv6", "ipv6", "public_ipv6");
            collect(ipv4Hosts, network, "publicIpv4", "publicIPv4", "publicIp", "publicIP", "ipv4", "public_ipv4");
        }
        ConnectionProfile ipv6 = firstPublished(fnId, ipv6Hosts, true, httpPort, httpsPort);
        return ipv6 != null ? ipv6 : firstPublished(fnId, ipv4Hosts, false, httpPort, httpsPort);
    }

    private ConnectionProfile firstReachable(String fnId, Set<String> hosts, boolean ipv6,
                                             int httpPort, int httpsPort, long generation,
                                             long deadlineElapsedRealtime) {
        // Keep the service order supplied by FN Connect. A device can expose
        // multiple IPv6 addresses (for example different WAN prefixes); each
        // is probed before falling back to IPv4.
        for (String rawHost : hosts) {
            if (!isGenerationActive(generation)) return null;
            long remainingMs = deadlineElapsedRealtime - SystemClock.elapsedRealtime();
            if (remainingMs <= 0L) return null;
            String host = normalizeHost(rawHost);
            if (host.isEmpty() || isIpv6(host) != ipv6) continue;
            for (Endpoint endpoint : endpoints(httpPort, httpsPort)) {
                remainingMs = deadlineElapsedRealtime - SystemClock.elapsedRealtime();
                if (remainingMs <= 0L) return null;
                int timeoutMs = (int) Math.min(DIRECT_PROBE_TIMEOUT_MS, Math.max(1L, remainingMs));
                if (!isReachable(host, endpoint.port, generation, timeoutMs)) continue;
                Log.i(TAG, ipv6 ? "resolved reachable public IPv6 endpoint" : "resolved reachable public IPv4 endpoint");
                return ConnectionProfile.create("", "FN Connect - " + fnId, host, endpoint.port,
                        endpoint.https, false, "", "");
            }
        }
        return null;
    }

    private ConnectionProfile firstPublished(String fnId, Set<String> hosts, boolean ipv6,
                                              int httpPort, int httpsPort) {
        for (String rawHost : hosts) {
            String host = normalizeHost(rawHost);
            if (host.isEmpty() || isIpv6(host) != ipv6) continue;
            Endpoint endpoint = endpoints(httpPort, httpsPort).get(0);
            return ConnectionProfile.create("", "FN Connect - " + fnId, host,
                    endpoint.port, endpoint.https, false, "", "");
        }
        return null;
    }

    private static List<Endpoint> endpoints(int httpPort, int httpsPort) {
        List<Endpoint> endpoints = new ArrayList<>();
        endpoints.add(new Endpoint(httpPort, false));
        if (httpsPort != httpPort) endpoints.add(new Endpoint(httpsPort, true));
        return endpoints;
    }

    private static final class Endpoint {
        final int port;
        final boolean https;
        Endpoint(int port, boolean https) { this.port = port; this.https = https; }
    }

    private boolean isReachable(String host, int port, long generation) {
        return isReachable(host, port, generation, DIRECT_PROBE_TIMEOUT_MS);
    }

    private boolean isReachable(String host, int port, long generation, int timeoutMs) {
        Socket socket = new Socket();
        try {
            synchronized (callLock) {
                if (callGeneration != generation) return false;
                activeProbeSocket = socket;
            }
            socket.connect(new InetSocketAddress(host, port), Math.max(1, timeoutMs));
            return isGenerationActive(generation);
        } catch (Exception ignored) {
            return false;
        } finally {
            synchronized (callLock) {
                if (activeProbeSocket == socket) activeProbeSocket = null;
            }
            try { socket.close(); } catch (IOException ignored) { }
        }
    }

    private static boolean isIpv6(String host) {
        try { return InetAddress.getByName(host) instanceof Inet6Address; }
        catch (Exception ignored) { return host != null && host.contains(":"); }
    }

    private static String normalizeHost(String value) {
        String host = value == null ? "" : value.trim();
        if (host.startsWith("[") && host.endsWith("]") && host.length() > 2) {
            host = host.substring(1, host.length() - 1);
        }
        int zone = host.indexOf('%');
        return zone >= 0 ? host.substring(0, zone) : host;
    }

    private static void collect(Set<String> hosts, JSONObject object, String... keys) {
        for (String key : keys) {
            Object value = object.opt(key);
            if (value instanceof String && hosts.size() < MAX_HOSTS_PER_FAMILY) {
                String host = ((String) value).trim();
                if (!host.isEmpty() && host.length() <= MAX_HOST_CHARS) hosts.add(host);
            }
            if (value instanceof JSONArray) for (int i = 0; i < ((JSONArray) value).length(); i++) {
                if (hosts.size() >= MAX_HOSTS_PER_FAMILY) break;
                Object item = ((JSONArray) value).opt(i);
                if (!(item instanceof String)) continue;
                String host = ((String) item).trim();
                if (!host.isEmpty() && host.length() <= MAX_HOST_CHARS) hosts.add(host);
            }
        }
    }

    private static int port(JSONObject object, String first, String second, int fallback) {
        int value = intField(object, first, Integer.MIN_VALUE);
        if (value == Integer.MIN_VALUE) value = intField(object, second, fallback);
        return value >= 1 && value <= 65535 ? value : fallback;
    }

    private static int intField(JSONObject object, String key, int fallback) {
        Object value = object == null ? null : object.opt(key);
        if (!(value instanceof Number)) return fallback;
        double numeric = ((Number) value).doubleValue();
        if (!Double.isFinite(numeric) || numeric != Math.rint(numeric)
                || numeric < Integer.MIN_VALUE || numeric > Integer.MAX_VALUE) return fallback;
        return (int) numeric;
    }

    private static String readable(Exception error) { return error.getMessage() == null ? "网络错误" : error.getMessage(); }
    private static String md5(String value) { return digest("MD5", value); }
    private static String sha256(String value) { return digest("SHA-256", value); }
    private static String digest(String algorithm, String value) {
        try {
            byte[] bytes = MessageDigest.getInstance(algorithm).digest(value.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            StringBuilder output = new StringBuilder(bytes.length * 2);
            for (byte item : bytes) output.append(String.format(java.util.Locale.ROOT, "%02x", item & 0xff));
            return output.toString();
        } catch (Exception ignored) { return ""; }
    }
}
