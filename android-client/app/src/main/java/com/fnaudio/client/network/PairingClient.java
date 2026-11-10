package com.fnaudio.client.network;

import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.PairingPayload;
import com.fnaudio.client.data.PairingTransfer;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

/**
 * Sends one connection to a television that is waiting for it.
 *
 * <p>The request goes to the television, not to a server: the television opened
 * a temporary HTTP port and put its address in the QR code, which is the only
 * way to solve the chicken-and-egg problem of a TV that does not yet know which
 * server to talk to.
 *
 * <p>Blocking on purpose. It runs off the main thread from a single call site,
 * and a one-shot request that must finish within the television's sixty-second
 * window is easier to reason about without another callback layer.
 */
public final class PairingClient {
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");
    private static final OkHttpClient CLIENT = new OkHttpClient.Builder()
            .connectTimeout(3, TimeUnit.SECONDS)
            .readTimeout(6, TimeUnit.SECONDS)
            .build();

    private PairingClient() {
    }

    /**
     * @throws IOException with a message meant for the viewer when the
     *                     television refused, expired, or could not be reached
     */
    public static void send(PairingPayload payload, ConnectionProfile profile) throws IOException {
        JSONObject profileJson;
        JSONObject body = new JSONObject();
        try {
            profileJson = new JSONObject(PairingTransfer.encode(profile));
            body.put("v", 1);
            body.put("code", payload.code);
            body.put("profile", profileJson);
        } catch (JSONException impossible) {
            throw new IOException("连接信息无法序列化");
        }

        Request request = new Request.Builder()
                .url("http://" + payload.host + ":" + payload.port + "/pair")
                .post(RequestBody.create(body.toString(), JSON))
                .build();

        Response response = null;
        try {
            response = CLIENT.newCall(request).execute();
            int status = response.code();
            if (status == 200) return;
            throw new IOException(describe(status));
        } catch (IOException unreachable) {
            // A refused connection is the common case: wrong address, different
            // subnet, or the code already expired and the television stopped
            // listening. Say so instead of surfacing "failed to connect".
            String detail = unreachable.getMessage();
            if (detail != null && detail.startsWith(describe(401))) throw unreachable;
            throw new IOException("连不上电视 " + payload.host + ":" + payload.port
                    + "\n请确认手机和电视在同一个网络，二维码没有过期");
        } finally {
            if (response != null) response.close();
        }
    }

    private static String describe(int status) {
        switch (status) {
            case 401: return "配对码不对，请核对电视上的六位码";
            case 403: return "电视只接受同一局域网内的请求";
            case 410: return "二维码已过期，请在电视上按 OK 换一个";
            case 413: return "连接信息太大，电视拒绝了";
            case 422: return "电视读不懂连接信息，请重试";
            default: return "电视返回了错误码 " + status;
        }
    }
}
