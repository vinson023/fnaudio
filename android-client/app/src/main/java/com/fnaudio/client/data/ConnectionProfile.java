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
    public final boolean fnConnectRelay;
    public final String fnConnectMode;
    public final String accessCode;
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
        this(id, name, host, port, https, trustSelfSigned, certificatePinSha256,
                username, password, token, longToken, webSession, false, "public", updatedAt);
    }

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
            boolean fnConnectRelay,
            long updatedAt
    ) {
        this(id, name, host, port, https, trustSelfSigned, certificatePinSha256,
                username, password, token, longToken, webSession, fnConnectRelay,
                fnConnectRelay ? "relay" : "public", updatedAt);
    }

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
            boolean fnConnectRelay,
            String fnConnectMode,
            long updatedAt
    ) {
        this(id, name, host, port, https, trustSelfSigned, certificatePinSha256, username,
                password, token, longToken, webSession, fnConnectRelay, fnConnectMode, "", updatedAt);
    }

    public ConnectionProfile(
            String id, String name, String host, int port, boolean https, boolean trustSelfSigned,
            String certificatePinSha256, String username, String password, String token, String longToken,
            boolean webSession, boolean fnConnectRelay, String fnConnectMode, String accessCode, long updatedAt
    ) {
        this.id = clean(id).isEmpty() ? UUID.randomUUID().toString() : clean(id);
        this.host = normalizeHost(host);
        this.https = https;
        this.port = normalizePort(port, https);
        this.trustSelfSigned = trustSelfSigned;
        this.certificatePinSha256 = https && trustSelfSigned ? CertificatePin.normalize(certificatePinSha256) : "";
        this.username = clean(username);
        this.password = password == null ? "" : password;
        this.token = clean(token);
        this.longToken = clean(longToken);
        this.webSession = webSession;
        this.fnConnectRelay = fnConnectRelay;
        this.fnConnectMode = normalizeFnConnectMode(fnConnectMode, fnConnectRelay);
        this.accessCode = clean(accessCode);
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
                fnConnectRelay,
                fnConnectMode,
                accessCode,
                System.currentTimeMillis()
        );
    }

    /** Keeps identity, credentials and session state while changing a resolved endpoint. */
    /**
     * Moves this profile to a different endpoint, keeping the user's choices.
     *
     * <p>This used to clear {@code trustSelfSigned}.  The FN Connect resolver
     * moves a saved profile from the relay (127.0.0.1) to an address, or the
     * other way round, every time it reconnects; clearing the flag there made a
     * profile whose owner had ticked 允许自签名证书 fail with "HTTPS 证书校验失败"
     * the moment the address changed (reported 2026-11-11).  Trusting a
     * self-signed certificate is a decision about the device, not about one
     * route to it.
     *
     * <p>The pin is the opposite: it names one certificate seen on one
     * endpoint, so it is dropped when the host changes.  Comparing a new
     * address's certificate against a fingerprint observed somewhere else could
     * only ever produce a false mismatch.
     */
    public ConnectionProfile withEndpoint(String nextHost, int nextPort, boolean nextHttps) {
        String normalizedNextHost = normalizeHost(nextHost);
        boolean hostChanged = !host.equalsIgnoreCase(normalizedNextHost);
        boolean nextTrustSelfSigned = nextHttps && trustSelfSigned;
        String nextCertificatePinSha256 = hostChanged || !nextHttps ? "" : certificatePinSha256;
        return new ConnectionProfile(
                id, name, normalizedNextHost, nextPort, nextHttps, nextTrustSelfSigned,
                nextCertificatePinSha256, username, password, token, longToken, false,
                fnConnectRelay, fnConnectMode, accessCode, System.currentTimeMillis());
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
                fnConnectRelay,
                fnConnectMode,
                accessCode,
                System.currentTimeMillis()
        );
    }

    public ConnectionProfile asWebSession() {
        return new ConnectionProfile(id, name, host, port, https, trustSelfSigned,
                certificatePinSha256, username, password, token, longToken, true, fnConnectRelay, fnConnectMode,
                accessCode,
                System.currentTimeMillis());
    }

    public ConnectionProfile withFnConnectRelay(boolean enabled) {
        return new ConnectionProfile(id, name, host, port, https, trustSelfSigned,
                certificatePinSha256, username, password, token, longToken, webSession,
                enabled, enabled ? "relay" : "public", accessCode, System.currentTimeMillis());
    }

    public ConnectionProfile withFnConnectMode(String mode) {
        String normalized = normalizeFnConnectMode(mode, false);
        return new ConnectionProfile(id, name, host, port, https, trustSelfSigned,
                certificatePinSha256, username, password, token, longToken, webSession,
                "relay".equals(normalized), normalized, accessCode, System.currentTimeMillis());
    }

    public ConnectionProfile withAccessCode(String nextAccessCode) {
        return new ConnectionProfile(id, name, host, port, https, trustSelfSigned,
                certificatePinSha256, username, password, token, longToken, webSession,
                fnConnectRelay, fnConnectMode, nextAccessCode, System.currentTimeMillis());
    }

    public boolean matchesConnection(String candidateHost, int candidatePort, boolean candidateHttps, String candidateUsername) {
        return host.equals(normalizeHost(candidateHost))
                && port == candidatePort
                && https == candidateHttps
                && username.equals(clean(candidateUsername));
    }

    /**
     * Whether this profile is a route the server handed us rather than an
     * address the user typed.
     *
     * <p>Matters for TLS: an FN Connect route can be an address, a name the NAS
     * has no certificate for, or a relay port, and the user never chose any of
     * them — the resolver did. The official client treats those exactly this way
     * (its Dart HttpClient registers a bad-certificate callback, and the
     * payload even carries a {@code FnConnectBadCertificateReason} for logging
     * why it was needed), which is why it can log in over FN ID while a strict
     * client cannot.
     */
    public boolean isFnConnectRoute() {
        return id.startsWith("fnconnect:") || name.startsWith("FN Connect - ");
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
        json.put("fnConnectRelay", fnConnectRelay);
        json.put("fnConnectMode", fnConnectMode);
        json.put("accessCode", accessCode);
        json.put("updatedAt", updatedAt);
        return json;
    }

    public static ConnectionProfile fromJson(JSONObject json) {
        String storedId = stringField(json, "id");
        String storedName = stringField(json, "name");
        boolean storedWebSession = booleanField(json, "webSession", false);
        // 0.1.225 briefly persisted native FN Connect profiles as browser
        // sessions. Those records carry an fnOS token, not a web-session
        // cookie, so migrate them back when an updated app first reads them.
        if (storedId.startsWith("fnconnect:") || storedName.startsWith("FN Connect - ")) {
            storedWebSession = false;
        }
        return new ConnectionProfile(
                storedId,
                storedName,
                stringField(json, "host"),
                intField(json, "port", 0),
                booleanField(json, "https", false),
                booleanField(json, "trustSelfSigned", false),
                stringField(json, "certificatePinSha256"),
                stringField(json, "username"),
                stringField(json, "password"),
                stringField(json, "token"),
                stringField(json, "longToken"),
                storedWebSession,
                booleanField(json, "fnConnectRelay", false),
                stringField(json, "fnConnectMode"),
                stringField(json, "accessCode"),
                longField(json, "updatedAt", 0L)
        );
    }

    private static String stringField(JSONObject object, String key) {
        Object value = object == null ? null : object.opt(key);
        return value instanceof String ? (String) value : "";
    }

    private static boolean booleanField(JSONObject object, String key, boolean fallback) {
        Object value = object == null ? null : object.opt(key);
        return value instanceof Boolean ? (Boolean) value : fallback;
    }

    private static int intField(JSONObject object, String key, int fallback) {
        Object value = object == null ? null : object.opt(key);
        if (!(value instanceof Number)) return fallback;
        double numeric = ((Number) value).doubleValue();
        if (!Double.isFinite(numeric) || numeric != Math.rint(numeric)
                || numeric < Integer.MIN_VALUE || numeric > Integer.MAX_VALUE) return fallback;
        return (int) numeric;
    }

    private static int normalizePort(int value, boolean https) {
        if (value >= 1 && value <= 65535) return value;
        return https ? 5667 : 5666;
    }

    private static long longField(JSONObject object, String key, long fallback) {
        Object value = object == null ? null : object.opt(key);
        if (!(value instanceof Number)) return fallback;
        double numeric = ((Number) value).doubleValue();
        if (!Double.isFinite(numeric) || numeric != Math.rint(numeric)
                || numeric < Long.MIN_VALUE || numeric > Long.MAX_VALUE) return fallback;
        return ((Number) value).longValue();
    }

    private static String normalizeFnConnectMode(String value, boolean legacyRelay) {
        String mode = clean(value).toLowerCase(Locale.ROOT);
        if ("speed".equals(mode) || "public".equals(mode) || "relay".equals(mode)) return mode;
        return legacyRelay ? "relay" : "public";
    }

    private static String normalizeHost(String raw) {
        String value = clean(raw);
        value = value.replaceFirst("(?i)^https?://", "");
        value = value.replaceFirst("(?i)^wss?://", "");
        int end = value.length();
        for (char delimiter : new char[]{'/', '?', '#'}) {
            int index = value.indexOf(delimiter);
            if (index >= 0 && index < end) end = index;
        }
        value = value.substring(0, end);
        // Do not preserve URL userinfo as a host. Such input cannot produce a
        // valid authenticated origin and could make diagnostics misleading.
        if (value.indexOf('@') >= 0) return "";
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
