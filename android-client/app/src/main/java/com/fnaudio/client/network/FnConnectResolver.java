package com.fnaudio.client.network;

import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import androidx.annotation.NonNull;

import com.fnaudio.client.data.ConnectionProfile;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.net.Inet6Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.LinkedHashSet;
import java.util.Set;

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
    public interface Callback {
        void onResolved(ConnectionProfile profile);
        void onError(String message);
    }

    private static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");
    private final Handler main = new Handler(Looper.getMainLooper());
    private final OkHttpClient client = new OkHttpClient.Builder().build();

    public void resolve(String rawFnId, Callback callback) {
        String fnId = rawFnId == null ? "" : rawFnId.trim().toLowerCase(java.util.Locale.ROOT);
        if (!fnId.matches("[a-z0-9-]{3,64}")) {
            callback.onError("FN ID 格式不正确");
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
        client.newCall(request).enqueue(new okhttp3.Callback() {
            @Override public void onFailure(@NonNull Call call, @NonNull IOException error) {
                fail(callback, "无法解析 FN ID：" + readable(error));
            }

            @Override public void onResponse(@NonNull Call call, @NonNull Response response) {
                try (Response closeable = response) {
                    ResponseBody responseBody = closeable.body();
                    String responseText = responseBody == null ? "" : responseBody.string();
                    if (!closeable.isSuccessful()) {
                        fail(callback, "FN Connect 解析失败（HTTP " + closeable.code() + "）");
                        return;
                    }
                    JSONObject root = new JSONObject(responseText);
                    JSONObject data = root.optJSONObject("data");
                    if (data == null) data = root;
                    ConnectionProfile resolved = choose(fnId, data);
                    if (resolved != null) {
                        main.post(() -> callback.onResolved(resolved));
                    } else {
                        fail(callback, "FN Connect 未发现可直连的公网 IPv6 或 IPv4 地址");
                    }
                } catch (Exception error) {
                    fail(callback, "FN Connect 返回数据无法识别");
                }
            }
        });
    }

    private ConnectionProfile choose(String fnId, JSONObject data) {
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
        ConnectionProfile ipv6 = firstReachable(fnId, ipv6Hosts, true, httpPort, httpsPort);
        if (ipv6 != null) return ipv6;
        ConnectionProfile ipv4 = firstReachable(fnId, ipv4Hosts, false, httpPort, httpsPort);
        if (ipv4 != null) return ipv4;
        return null;
    }

    private ConnectionProfile firstReachable(String fnId, Set<String> hosts, boolean ipv6,
                                             int httpPort, int httpsPort) {
        // Keep the service order supplied by FN Connect. A device can expose
        // multiple IPv6 addresses (for example different WAN prefixes); each
        // is probed before falling back to IPv4.
        Endpoint fallbackEndpoint = null;
        String fallbackHost = "";
        for (String rawHost : hosts) {
            String host = normalizeHost(rawHost);
            if (host.isEmpty() || isIpv6(host) != ipv6) continue;
            if (fallbackHost.isEmpty()) {
                fallbackHost = host;
                fallbackEndpoint = new Endpoint(httpPort, false);
            }
            for (Endpoint endpoint : endpoints(httpPort, httpsPort)) {
                if (!isReachable(host, endpoint.port)) continue;
                Log.i(TAG, ipv6 ? "resolved reachable public IPv6 endpoint" : "resolved reachable public IPv4 endpoint");
                return ConnectionProfile.create("", "FN Connect - " + fnId, host, endpoint.port,
                        endpoint.https, false, "", "");
            }
        }
        // fnos.net is the authority for FN Connect endpoint discovery. A
        // short local TCP probe is useful for ranking addresses, but must not
        // turn a valid published IPv6 address into "no address": some mobile
        // networks delay the first IPv6 SYN or apply a transient power-save
        // policy. Keep the first official candidate and let fnOS login report
        // a real connection error if it ultimately cannot be reached.
        if (!fallbackHost.isEmpty() && fallbackEndpoint != null) {
            Log.i(TAG, ipv6 ? "using official public IPv6 fallback endpoint" : "using official public IPv4 fallback endpoint");
            return ConnectionProfile.create("", "FN Connect - " + fnId, fallbackHost,
                    fallbackEndpoint.port, fallbackEndpoint.https, false, "", "");
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

    private boolean isReachable(String host, int port) {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(host, port), 1800);
            return true;
        } catch (Exception ignored) { return false; }
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
            if (value instanceof String && !((String) value).trim().isEmpty()) hosts.add(((String) value).trim());
            if (value instanceof JSONArray) for (int i = 0; i < ((JSONArray) value).length(); i++) {
                String host = ((JSONArray) value).optString(i).trim();
                if (!host.isEmpty()) hosts.add(host);
            }
        }
    }

    private static int port(JSONObject object, String first, String second, int fallback) {
        int value = object.optInt(first, object.optInt(second, fallback));
        return value >= 1 && value <= 65535 ? value : fallback;
    }

    private void fail(Callback callback, String message) { main.post(() -> callback.onError(message)); }
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
