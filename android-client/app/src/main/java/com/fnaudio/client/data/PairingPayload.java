package com.fnaudio.client.data;

import androidx.annotation.Nullable;

/**
 * The QR payload: where the television is listening and which one-time code it
 * will accept.
 *
 * <p>Carries no credentials. The phone reads the address and the code from the
 * picture, then pushes the profile over the LAN; anything sensitive travels in
 * that POST body, never in a string a camera can read from across the room.
 */
public final class PairingPayload {
    private static final String SCHEME = "fnaudio://pair";
    private static final String VERSION = "1";

    public final String host;
    public final int port;
    public final String code;

    private PairingPayload(String host, int port, String code) {
        this.host = host;
        this.port = port;
        this.code = code;
    }

    public static PairingPayload of(String host, int port, String code) {
        return new PairingPayload(host, port, code);
    }

    public String toUri() {
        return SCHEME + "?v=" + VERSION + "&h=" + host + "&p=" + port + "&c=" + code;
    }

    /**
     * Parses a scanned URI.
     *
     * @throws IllegalArgumentException when the text is not a pairing code, so a
     *                                  scanner pointed at some other QR can say
     *                                  "不是 fnAudio 的配对码" instead of failing later
     */
    public static PairingPayload parse(@Nullable String raw) {
        if (raw == null) throw new IllegalArgumentException("空的二维码");
        String text = raw.trim();
        if (!text.startsWith(SCHEME)) throw new IllegalArgumentException("不是 fnAudio 的配对码");
        String query = text.substring(SCHEME.length());
        if (query.startsWith("?")) query = query.substring(1);
        String host = null;
        String code = null;
        int port = -1;
        for (String pair : query.split("&")) {
            int equals = pair.indexOf('=');
            if (equals <= 0) continue;
            String key = pair.substring(0, equals);
            String value = pair.substring(equals + 1);
            switch (key) {
                case "h": host = value; break;
                case "p": port = parseInt(value); break;
                case "c": code = value; break;
                default: break;
            }
        }
        if (host == null || host.isEmpty() || port <= 0 || code == null || code.isEmpty()) {
            throw new IllegalArgumentException("配对码不完整");
        }
        return new PairingPayload(host, port, code);
    }

    private static int parseInt(String value) {
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException error) {
            return -1;
        }
    }
}
