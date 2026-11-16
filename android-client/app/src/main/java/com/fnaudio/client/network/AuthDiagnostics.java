package com.fnaudio.client.network;

import androidx.annotation.Nullable;

import com.fnaudio.client.BuildConfig;
import com.fnaudio.client.data.ConnectionProfile;

import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
import java.util.Date;
import java.util.Deque;
import java.util.Locale;

/**
 * A small, phone-only record of the last authentication attempt.
 *
 * <p>Reported 2026-11-16: the login fails only from outside the LAN, and reading
 * what happened needed a PC, an emulator and a TLS proxy. That is too much to ask
 * for a one-off "it broke again" report, so the attempt records its own facts and
 * the failure dialog copies them to the clipboard in one tap.
 *
 * <p>Nothing secret is stored: no password, no token, no access-code text. The
 * report only says whether each of them is present, plus the endpoint, the route
 * and the phase where the attempt died. That is exactly what separates "the
 * gateway stopped issuing a session cookie" from "the token expired".
 */
public final class AuthDiagnostics {

    private static final int MAX_EVENTS = 40;
    private static final int MAX_EVENT_CHARS = 220;
    private static final Deque<String> EVENTS = new ArrayDeque<>();

    private AuthDiagnostics() {
    }

    /** Append one fact. Called from the authentication callbacks, so it must stay cheap. */
    public static synchronized void record(String event) {
        if (event == null) return;
        String text = event.trim();
        if (text.isEmpty()) return;
        if (text.length() > MAX_EVENT_CHARS) text = text.substring(0, MAX_EVENT_CHARS);
        String stamp = new SimpleDateFormat("HH:mm:ss", Locale.ROOT).format(new Date());
        EVENTS.addLast(stamp + "  " + text);
        while (EVENTS.size() > MAX_EVENTS) EVENTS.removeFirst();
    }

    /** Start a fresh attempt: keep nothing from a previous one. */
    public static synchronized void reset() {
        EVENTS.clear();
    }

    /**
     * The text the user copies. Deliberately describes the profile instead of
     * printing it, so a shared screenshot or clipboard never carries a credential.
     */
    public static synchronized String report(@Nullable ConnectionProfile profile) {
        StringBuilder out = new StringBuilder(1024);
        out.append("fnAudio ").append(BuildConfig.VERSION_NAME)
                .append(" (").append(BuildConfig.VERSION_CODE).append(')')
                .append(System.lineSeparator());
        out.append("time: ")
                .append(new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.ROOT).format(new Date()))
                .append(System.lineSeparator());
        if (profile != null) {
            out.append("endpoint: host=").append(safe(profile.host))
                    .append(" port=").append(profile.port)
                    .append(" https=").append(profile.https)
                    .append(System.lineSeparator());
            out.append("route: ").append(safe(profile.fnConnectMode))
                    .append("  id=").append(prefix(safe(profile.id), 40))
                    .append(System.lineSeparator());
            out.append("has: accessCode=").append(profile.accessCode.isEmpty() ? "no" : "yes")
                    .append(" token=").append(profile.token.isEmpty() ? "no" : "yes")
                    .append(" longToken=").append(profile.longToken.isEmpty() ? "no" : "yes")
                    .append(" savedPassword=").append(profile.password.isEmpty() ? "no" : "yes")
                    .append(System.lineSeparator());
        } else {
            out.append("endpoint: (unknown)").append(System.lineSeparator());
        }
        out.append("events:").append(System.lineSeparator());
        if (EVENTS.isEmpty()) {
            out.append("  (none)").append(System.lineSeparator());
        } else {
            for (String event : EVENTS) {
                out.append("  ").append(event).append(System.lineSeparator());
            }
        }
        return out.toString();
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }

    private static String prefix(String value, int limit) {
        if (value == null) return "";
        return value.length() <= limit ? value : value.substring(0, limit) + "…";
    }
}
