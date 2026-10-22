package com.fnaudio.client.network;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

/** Cookie encoding for the fnOS gateway, distinct from HTML form encoding. */
public final class SessionCookies {
    private SessionCookies() { }

    public static String encodeToken(String value) {
        try {
            // Base64 + / = are valid cookie octets. The gateway reads these
            // literally and rejects their percent-encoded form.
            return URLEncoder.encode(value == null ? "" : value, "UTF-8")
                    .replace("+", "%20").replace("%2B", "+")
                    .replace("%2F", "/").replace("%3D", "=");
        } catch (java.io.UnsupportedEncodingException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    public static int responseStatus(int status, String body) {
        // Some fnOS gateways report rejected cookies with HTTP 200 text/plain.
        return status == 200 && body != null && "invalid token".equalsIgnoreCase(body.trim())
                ? 401 : status;
    }

    public static String accessCodeHeader(String value) {
        if (value == null || value.indexOf('\r') >= 0 || value.indexOf('\n') >= 0) return "";
        String trimmed = value.trim();
        if (trimmed.isEmpty()) return "";
        return encodeBase64(trimmed.getBytes(StandardCharsets.UTF_8));
    }

    private static String encodeBase64(byte[] bytes) {
        final char[] alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".toCharArray();
        StringBuilder encoded = new StringBuilder(((bytes.length + 2) / 3) * 4);
        for (int offset = 0; offset < bytes.length; offset += 3) {
            int first = bytes[offset] & 0xff;
            int second = offset + 1 < bytes.length ? bytes[offset + 1] & 0xff : 0;
            int third = offset + 2 < bytes.length ? bytes[offset + 2] & 0xff : 0;
            encoded.append(alphabet[first >>> 2]);
            encoded.append(alphabet[((first & 0x03) << 4) | (second >>> 4)]);
            encoded.append(offset + 1 < bytes.length ? alphabet[((second & 0x0f) << 2) | (third >>> 6)] : '=');
            encoded.append(offset + 2 < bytes.length ? alphabet[third & 0x3f] : '=');
        }
        return encoded.toString();
    }

    /** Extracts the gateway's signed access-code cookie from one Set-Cookie value. */
    public static String accessCodeCookie(String setCookie) {
        if (setCookie == null) return "";
        String value = setCookie.trim();
        int separator = value.indexOf(';');
        String pair = separator >= 0 ? value.substring(0, separator).trim() : value;
        return pair.startsWith("os-access-code=") && pair.length() > "os-access-code=".length()
                ? pair : "";
    }
}
