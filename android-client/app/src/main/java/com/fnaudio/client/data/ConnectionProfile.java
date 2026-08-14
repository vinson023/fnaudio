package com.fnaudio.client.data;

import org.json.JSONException;
import org.json.JSONObject;

import com.fnaudio.client.network.CertificatePin;

import java.util.Locale;
import java.util.UUID;

public final class ConnectionProfile {
    public final String id;
    public final String name;
    public final String host;
    public final int port;
    public final boolean https;
    public final boolean trustSelfSigned;
    public final String certificatePinSha256;
    public final String username;
    public final String password;
    public final String token;
    public final String longToken;
    public final boolean webSession;
    public final long updatedAt;

    public ConnectionProfile(
            String id,
            String name,
            String host,
            int port,
            boolean https,
            boolean trustSelfSigned,
            String certificatePinSha256,
            String username,
            String password,
            String token,
            String longToken,
            boolean webSession,
            long updatedAt
    ) {
        this.id = clean(id).isEmpty() ? UUID.randomUUID().toString() : clean(id);
        this.host = normalizeHost(host);
        this.port = port;
        this.https = https;
        this.trustSelfSigned = trustSelfSigned;
        this.certificatePinSha256 = https && trustSelfSigned ? CertificatePin.normalize(certificatePinSha256) : "";
        this.username = clean(username);
        this.password = password == null ? "" : password;
        this.token = clean(token);
        this.longToken = clean(longToken);
        this.webSession = webSession;
        this.updatedAt = updatedAt > 0 ? updatedAt : System.currentTimeMillis();
        String defaultName = this.host + (this.port > 0 ? ":" + this.port : "");
        this.name = clean(name).isEmpty() ? defaultName : clean(name);
    }

    public ConnectionProfile(String id, String name, String host, int port, boolean https,
                             boolean trustSelfSigned, String certificatePinSha256,
                             String username, String password, String token, String longToken,
                             long updatedAt) {
        this(id, name, host, port, https, trustSelfSigned, certificatePinSha256,
                username, password, token, longToken, false, updatedAt);
    }

    public static ConnectionProfile create(
            String existingId,
            String name,
            String host,
            int port,
            boolean https,
            boolean trustSelfSigned,
            String username,
            String password
    ) {
        return new ConnectionProfile(
                existingId,
                name,
                host,
                port,
                https,
                trustSelfSigned,
                "",
                username,
                password,
                "",
                "",
                false,
                System.currentTimeMillis()
        );
    }

    public ConnectionProfile withTokens(String nextToken, String nextLongToken) {
        return new ConnectionProfile(
                id,
                name,
                host,
                port,
                https,
                trustSelfSigned,
                certificatePinSha256,
                username,
                password,
                nextToken,
                nextLongToken,
                webSession,
                System.currentTimeMillis()
        );
    }

    /** Keeps identity, credentials and session state while changing a resolved endpoint. */
    public ConnectionProfile withEndpoint(String nextHost, int nextPort, boolean nextHttps) {
        return new ConnectionProfile(
                id, name, nextHost, nextPort, nextHttps, false, "", username, password,
                token, longToken, false, System.currentTimeMillis());
    }

    public ConnectionProfile withCertificatePin(String nextCertificatePinSha256) {
        return new ConnectionProfile(
                id,
                name,
                host,
                port,
                https,
                trustSelfSigned,
                nextCertificatePinSha256,
                username,
                password,
                token,
                longToken,
                webSession,
                System.currentTimeMillis()
        );
    }

    public ConnectionProfile asWebSession() {
        return new ConnectionProfile(id, name, host, port, https, trustSelfSigned,
                certificatePinSha256, username, password, token, longToken, true,
                System.currentTimeMillis());
    }

    public boolean matchesConnection(String candidateHost, int candidatePort, boolean candidateHttps, String candidateUsername) {
        return host.equals(normalizeHost(candidateHost))
                && port == candidatePort
                && https == candidateHttps
                && username.equals(clean(candidateUsername));
    }

    public String httpOrigin() {
        return (https ? "https" : "http") + "://" + authority();
    }

    public String webSocketUrl() {
        return (https ? "wss" : "ws") + "://" + authority() + "/websocket?type=main";
    }

    public String fnAudioUrl() {
        return httpOrigin() + "/cgi/ThirdParty/fnaudio/index.cgi/";
    }

    private String authority() {
        String value = host;
        if (value.contains(":") && !value.startsWith("[")) value = "[" + value + "]";
        return value + (port > 0 ? ":" + port : "");
    }

    public JSONObject toJson() throws JSONException {
        JSONObject json = new JSONObject();
        json.put("id", id);
        json.put("name", name);
        json.put("host", host);
        json.put("port", port);
        json.put("https", https);
        json.put("trustSelfSigned", trustSelfSigned);
        json.put("certificatePinSha256", certificatePinSha256);
        json.put("username", username);
        json.put("password", password);
        json.put("token", token);
        json.put("longToken", longToken);
        json.put("webSession", webSession);
        json.put("updatedAt", updatedAt);
        return json;
    }

    public static ConnectionProfile fromJson(JSONObject json) {
        String storedId = json.optString("id");
        String storedName = json.optString("name");
        boolean storedWebSession = json.optBoolean("webSession");
        // 0.1.225 briefly persisted native FN Connect profiles as browser
        // sessions. Those records carry an fnOS token, not a web-session
        // cookie, so migrate them back when an updated app first reads them.
        if (storedId.startsWith("fnconnect:") || storedName.startsWith("FN Connect - ")) {
            storedWebSession = false;
        }
        return new ConnectionProfile(
                storedId,
                storedName,
                json.optString("host"),
                json.optInt("port", 0),
                json.optBoolean("https"),
                json.optBoolean("trustSelfSigned"),
                json.optString("certificatePinSha256"),
                json.optString("username"),
                json.optString("password"),
                json.optString("token"),
                json.optString("longToken"),
                storedWebSession,
                json.optLong("updatedAt")
        );
    }

    private static String normalizeHost(String raw) {
        String value = clean(raw);
        value = value.replaceFirst("(?i)^https?://", "");
        value = value.replaceFirst("(?i)^wss?://", "");
        int slash = value.indexOf('/');
        if (slash >= 0) value = value.substring(0, slash);
        if (value.startsWith("[") && value.contains("]")) {
            return value.substring(1, value.indexOf(']'));
        }
        int colon = value.lastIndexOf(':');
        if (colon > 0 && value.indexOf(':') == colon && value.substring(colon + 1).matches("\\d+")) {
            value = value.substring(0, colon);
        }
        return value.toLowerCase(Locale.ROOT);
    }

    private static String clean(String value) {
        return value == null ? "" : value.trim();
    }
}
