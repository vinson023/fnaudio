package com.fnaudio.client.tv;

import com.fnaudio.client.data.ConnectionProfile;

import org.json.JSONException;
import org.json.JSONObject;

/**
 * What actually crosses the wire when a phone hands a connection to the
 * television.
 *
 * <p>{@link ConnectionProfile#toJson()} is deliberately not used: it serialises
 * the password and the short-lived token as well. The whitelist below is the
 * contract - routing information and the long-lived ticket, nothing a viewer
 * typed.
 *
 * <table>
 *   <tr><td>name / host / port / https</td><td>required to reach the server</td></tr>
 *   <tr><td>trustSelfSigned / certificatePinSha256</td><td>most installs are on a
 *       home NAS with a self-signed certificate; dropping these makes the TV
 *       refuse a server the phone talks to happily</td></tr>
 *   <tr><td>username</td><td>shown on screen, and named in token-expiry errors</td></tr>
 *   <tr><td>longToken</td><td>{@code user.tokenLogin} exchanges it for a fresh
 *       short token, which is what lets the TV stay signed in</td></tr>
 *   <tr><td>webSession / fnConnectRelay / fnConnectMode / accessCode</td>
 *       <td>decide between a direct connection and the relay tunnel</td></tr>
 *   <tr><td>password, token</td><td><b>never sent</b></td></tr>
 * </table>
 */
final class PairingTransfer {
    private PairingTransfer() {
    }

    /** Serialises the whitelist; the password is dropped even if it is set. */
    static String encode(ConnectionProfile profile) throws JSONException {
        JSONObject json = new JSONObject();
        json.put("name", profile.name);
        json.put("host", profile.host);
        json.put("port", profile.port);
        json.put("https", profile.https);
        json.put("trustSelfSigned", profile.trustSelfSigned);
        json.put("certificatePinSha256", profile.certificatePinSha256);
        json.put("username", profile.username);
        json.put("longToken", profile.longToken);
        json.put("webSession", profile.webSession);
        json.put("fnConnectRelay", profile.fnConnectRelay);
        json.put("fnConnectMode", profile.fnConnectMode);
        json.put("accessCode", profile.accessCode);
        return json.toString();
    }

    /**
     * Rebuilds a profile from a received body.
     *
     * @throws IllegalArgumentException when the body is not a usable connection,
     *                                  so the phone gets a stated reason instead
     *                                  of a television that silently fails later
     */
    static ConnectionProfile decode(String body) {
        JSONObject json;
        try {
            json = new JSONObject(body);
        } catch (JSONException error) {
            throw new IllegalArgumentException("报文不是 JSON");
        }
        String host = string(json, "host");
        int port = integer(json, "port");
        if (host.isEmpty()) throw new IllegalArgumentException("缺少服务器地址");
        if (port <= 0 || port > 65535) throw new IllegalArgumentException("端口不合法");
        String username = string(json, "username");
        if (username.isEmpty()) throw new IllegalArgumentException("缺少用户名");

        boolean https = flag(json, "https");
        return new ConnectionProfile(
                "pair:" + host + ":" + port + ":" + username,
                string(json, "name"),
                host,
                port,
                https,
                flag(json, "trustSelfSigned"),
                string(json, "certificatePinSha256"),
                username,
                // Password and short token stay empty on purpose: the television
                // was never trusted with them, and the long token is what it
                // needs to sign in.
                "",
                "",
                string(json, "longToken"),
                flag(json, "webSession"),
                flag(json, "fnConnectRelay"),
                string(json, "fnConnectMode"),
                string(json, "accessCode"),
                System.currentTimeMillis());
    }

    // Typed reads, never optString/optInt: those coerce whatever the sender put
    // in the field (a number becomes "42", a boolean becomes "true") and the
    // project forbids them by test. An unexpected type is treated as absent.

    private static String string(JSONObject json, String key) {
        Object value = json.opt(key);
        return value instanceof String ? ((String) value).trim() : "";
    }

    private static boolean flag(JSONObject json, String key) {
        Object value = json.opt(key);
        return value instanceof Boolean && (Boolean) value;
    }

    private static int integer(JSONObject json, String key) {
        Object value = json.opt(key);
        return value instanceof Number ? ((Number) value).intValue() : 0;
    }
}
