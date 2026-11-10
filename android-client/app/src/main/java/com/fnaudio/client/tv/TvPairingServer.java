package com.fnaudio.client.tv;

import android.os.Handler;
import android.os.Looper;

import androidx.annotation.Nullable;

import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.PairingTransfer;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.NetworkInterface;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Collections;
import java.util.Locale;

/**
 * The television's side of pairing: a temporary HTTP server that accepts one
 * connection for sixty seconds.
 *
 * <p>Why the TV hosts and the phone dials rather than the other way round: the
 * television does not know the server's address, which is the entire problem
 * being solved, so it cannot poll a server-side pairing endpoint. Having the TV
 * listen means the address and the credentials arrive in the same request and
 * no backend change is needed at all.
 *
 * <p>Guards, in order: the request must come from a private address, must carry
 * the six-digit code that is on screen, and must arrive before the deadline.
 * After three wrong codes the server shuts itself down, so guessing is bounded
 * by three attempts in a minute rather than by the code space.
 */
final class TvPairingServer {
    interface Listener {
        /** Main thread. {@code profile} carries the long token, never a password. */
        void onPaired(ConnectionProfile profile);

        /** Main thread. {@code reason} is shown on screen as-is. */
        void onClosed(String reason);
    }

    private static final int FIRST_PORT = 42001;
    private static final int LAST_PORT = 42010;
    private static final int MAX_BODY = 8 * 1024;
    private static final int MAX_ATTEMPTS = 3;
    /** Sixty seconds, matching the countdown printed under the code. */
    static final long LIFETIME_MS = 60_000L;

    private final Listener listener;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final String code;

    @Nullable private ServerSocket server;
    private Thread worker;
    private volatile boolean running;
    private int attempts;
    @Nullable private String boundHost;

    private final Runnable expiry = () -> close("二维码已过期");

    TvPairingServer(Listener listener) {
        this.listener = listener;
        this.code = String.format(Locale.ROOT, "%06d", new SecureRandom().nextInt(1_000_000));
    }

    String code() {
        return code;
    }

    @Nullable
    String host() {
        return boundHost;
    }

    int port() {
        return server == null ? -1 : server.getLocalPort();
    }

    /**
     * Binds the first free port in the range and starts accepting.
     *
     * @return false when every port in the range is taken, which the login page
     *         reports as "只剩配对码可用" instead of showing a QR that leads
     *         nowhere
     */
    boolean start() {
        if (running) return true;
        String host = lanAddress();
        if (host == null) return false;
        for (int port = FIRST_PORT; port <= LAST_PORT; port++) {
            try {
                server = new ServerSocket();
                server.setReuseAddress(true);
                server.bind(new InetSocketAddress(port), 4);
                boundHost = host;
                running = true;
                main.postDelayed(expiry, LIFETIME_MS);
                worker = new Thread(this::acceptLoop, "tv-pairing");
                worker.setDaemon(true);
                worker.start();
                return true;
            } catch (IOException busy) {
                server = null;
            }
        }
        return false;
    }

    /** Stops accepting and cancels the countdown; safe to call twice. */
    void stop() {
        close(null);
    }

    private void close(@Nullable String reason) {
        if (!running) return;
        running = false;
        main.removeCallbacks(expiry);
        ServerSocket socket = server;
        server = null;
        if (socket != null) {
            try {
                socket.close();
            } catch (IOException ignored) {
                // Closing a listening socket racing with accept() is expected.
            }
        }
        if (reason != null) {
            final String text = reason;
            main.post(() -> listener.onClosed(text));
        }
    }

    private void acceptLoop() {
        ServerSocket socket = server;
        if (socket == null) return;
        while (running && socket == server) {
            try {
                Socket client = socket.accept();
                handle(client);
            } catch (SocketTimeoutException timeout) {
                // Nothing connected yet; keep waiting until the deadline.
            } catch (IOException closed) {
                return;
            }
        }
    }

    private void handle(Socket client) {
        try (Socket socket = client) {
            socket.setSoTimeout(5000);
            if (!isPrivate(socket.getInetAddress())) {
                respond(socket, 403, "{\"ok\":false,\"error\":\"not_lan\"}");
                return;
            }
            String head = readHead(socket.getInputStream());
            if (head == null) {
                respond(socket, 400, "{\"ok\":false,\"error\":\"bad_request\"}");
                return;
            }
            String requestLine = head.split("\r\n", 2)[0];
            if (!requestLine.startsWith("POST /pair")) {
                respond(socket, 404, "{\"ok\":false,\"error\":\"not_found\"}");
                return;
            }
            int length = contentLength(head);
            if (length <= 0) {
                respond(socket, 400, "{\"ok\":false,\"error\":\"empty_body\"}");
                return;
            }
            if (length > MAX_BODY) {
                respond(socket, 413, "{\"ok\":false,\"error\":\"too_large\"}");
                return;
            }
            String body = readBody(socket.getInputStream(), length);
            if (body == null) {
                respond(socket, 400, "{\"ok\":false,\"error\":\"short_body\"}");
                return;
            }
            String receivedCode = codeIn(body);
            if (!code.equals(receivedCode)) {
                attempts++;
                respond(socket, 401, "{\"ok\":false,\"error\":\"code_mismatch\"}");
                if (attempts >= MAX_ATTEMPTS) close("配对码错误次数过多");
                return;
            }
            ConnectionProfile profile;
            try {
                profile = PairingTransfer.decode(profileIn(body));
            } catch (IllegalArgumentException rejected) {
                respond(socket, 422, "{\"ok\":false,\"error\":\"payload\",\"detail\":\""
                        + rejected.getMessage() + "\"}");
                return;
            }
            respond(socket, 200, "{\"ok\":true,\"tv\":\"fnAudio TV\"}");
            // One code, one use: the server goes away before the credentials are
            // handed to the activity, so a replayed request cannot arrive.
            close(null);
            main.post(() -> listener.onPaired(profile));
        } catch (IOException failed) {
            close(null);
        }
    }

    /**
     * Reads headers up to the blank line.
     *
     * <p>Byte-wise with a four-byte rolling window rather than a BufferedReader:
     * the body follows immediately and must not be consumed by a buffered reader
     * that read ahead.
     */
    @Nullable
    private String readHead(InputStream input) throws IOException {
        ByteArrayOutputStream head = new ByteArrayOutputStream();
        int[] window = new int[4];
        int read;
        while ((read = input.read()) != -1) {
            head.write(read);
            window[0] = window[1];
            window[1] = window[2];
            window[2] = window[3];
            window[3] = read;
            if (window[0] == '\r' && window[1] == '\n' && window[2] == '\r' && window[3] == '\n') {
                break;
            }
            if (head.size() > 8192) return null;
        }
        String text = new String(head.toByteArray(), StandardCharsets.ISO_8859_1);
        return text.isEmpty() ? null : text;
    }

    private static int contentLength(String head) {
        for (String line : head.split("\r\n")) {
            int colon = line.indexOf(':');
            if (colon <= 0) continue;
            if (!line.substring(0, colon).trim().equalsIgnoreCase("Content-Length")) continue;
            try {
                return Integer.parseInt(line.substring(colon + 1).trim());
            } catch (NumberFormatException error) {
                return -1;
            }
        }
        return -1;
    }

    @Nullable
    private static String readBody(InputStream input, int length) throws IOException {
        byte[] buffer = new byte[length];
        int read = 0;
        while (read < length) {
            int step = input.read(buffer, read, length - read);
            if (step <= 0) return null;
            read += step;
        }
        return new String(buffer, StandardCharsets.UTF_8);
    }

    private static void respond(Socket socket, int status, String body) throws IOException {
        byte[] payload = body.getBytes(StandardCharsets.UTF_8);
        String head = "HTTP/1.1 " + status + " " + reason(status) + "\r\n"
                + "Content-Type: application/json; charset=utf-8\r\n"
                + "Content-Length: " + payload.length + "\r\n"
                + "Connection: close\r\n\r\n";
        OutputStream out = socket.getOutputStream();
        out.write(head.getBytes(StandardCharsets.ISO_8859_1));
        out.write(payload);
        out.flush();
    }

    private static String reason(int status) {
        switch (status) {
            case 200: return "OK";
            case 400: return "Bad Request";
            case 401: return "Unauthorized";
            case 403: return "Forbidden";
            case 404: return "Not Found";
            case 413: return "Payload Too Large";
            case 422: return "Unprocessable Entity";
            default: return "Error";
        }
    }

    /** The body is a flat object, so the code is read without a full parse. */
    private static String codeIn(String body) {
        try {
            Object value = new org.json.JSONObject(body).opt("code");
            return value instanceof String ? (String) value : "";
        } catch (org.json.JSONException error) {
            return "";
        }
    }

    /** Same, for the nested profile object, which is handed to {@link PairingTransfer}. */
    private static String profileIn(String body) {
        try {
            org.json.JSONObject root = new org.json.JSONObject(body);
            org.json.JSONObject profile = root.optJSONObject("profile");
            return profile == null ? "" : profile.toString();
        } catch (org.json.JSONException error) {
            return "";
        }
    }

    /** Only private, link-local and loopback sources are accepted. */
    private static boolean isPrivate(@Nullable InetAddress address) {
        return address != null
                && (address.isSiteLocalAddress() || address.isLinkLocalAddress()
                || address.isLoopbackAddress());
    }

    /**
     * The address a phone on the same network can reach.
     *
     * <p>Every non-loopback IPv4 interface is a candidate; the first site-local
     * one wins, which on a television is the Wi-Fi or Ethernet interface. An
     * IPv6-only network has no answer here, and the caller falls back to the
     * six-digit code.
     */
    @Nullable
    private static String lanAddress() {
        try {
            for (NetworkInterface network : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!network.isUp() || network.isLoopback()) continue;
                for (InetAddress address : Collections.list(network.getInetAddresses())) {
                    if (address instanceof Inet4Address && address.isSiteLocalAddress()) {
                        return address.getHostAddress();
                    }
                }
            }
        } catch (IOException ignored) {
            return null;
        }
        return null;
    }
}
