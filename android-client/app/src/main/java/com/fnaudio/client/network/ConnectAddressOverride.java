package com.fnaudio.client.network;

import androidx.annotation.Nullable;

import java.net.InetAddress;
import java.net.UnknownHostException;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import okhttp3.Dns;

/**
 * Lets a profile keep a host name while connecting to a specific address.
 *
 * <p>FN Connect publishes the NAS under a name ({@code <fnid>.fnos.net}) whose
 * certificate is issued by a public CA, and it also publishes the addresses that
 * name currently resolves to.  Connecting by address therefore reaches the
 * server but cannot pass hostname verification — no CA issues certificates for
 * bare addresses — while resolving the name can fail outright on mobile networks.
 *
 * <p>Overriding the lookup keeps both halves: TLS sees the name (so SNI and the
 * certificate check use it, and the certificate really is verified against a
 * trusted root), and the socket opens to the address that was just proven
 * reachable.  This replaces trusting every certificate, which was the only way
 * an address endpoint could connect before.
 *
 * <p>Entries are process-local and bounded.  They are re-registered on every
 * resolve, which FN Connect profiles do on each reconnect, so nothing depends on
 * surviving a restart.
 */
final class ConnectAddressOverride {

    /** Enough for the IPv4 and IPv6 candidates of a couple of profiles. */
    private static final int MAX_ENTRIES = 16;

    private static final Map<String, InetAddress> OVERRIDES =
            new LinkedHashMap<String, InetAddress>(MAX_ENTRIES, 0.75f, true) {
                @Override
                protected boolean removeEldestEntry(Map.Entry<String, InetAddress> eldest) {
                    return size() > MAX_ENTRIES;
                }
            };

    private ConnectAddressOverride() {
    }

    /** The client-level resolver; anything not pinned keeps the platform lookup. */
    static final Dns DNS = hostname -> {
        InetAddress pinned = pinned(hostname);
        if (pinned != null) return Collections.singletonList(pinned);
        return Dns.SYSTEM.lookup(hostname);
    };

    /**
     * Pins {@code host} to {@code address} for this process.
     *
     * <p>Silently ignores input that is not a literal address: a name here would
     * reintroduce the lookup this method exists to avoid.
     */
    static void pin(@Nullable String host, @Nullable String address) {
        String normalizedHost = normalize(host);
        if (normalizedHost.isEmpty() || !HttpClientFactory.isIpLiteral(address)) return;
        try {
            InetAddress resolved = InetAddress.getByName(address.trim());
            synchronized (OVERRIDES) {
                OVERRIDES.put(normalizedHost, resolved);
            }
        } catch (UnknownHostException ignored) {
            // A malformed literal is not worth failing a connection over; the
            // caller falls back to its previous behaviour.
        }
    }

    @Nullable
    static InetAddress pinned(@Nullable String host) {
        String normalizedHost = normalize(host);
        if (normalizedHost.isEmpty()) return null;
        synchronized (OVERRIDES) {
            return OVERRIDES.get(normalizedHost);
        }
    }

    static void clear() {
        synchronized (OVERRIDES) {
            OVERRIDES.clear();
        }
    }

    private static String normalize(@Nullable String host) {
        if (host == null) return "";
        String value = host.trim().toLowerCase(Locale.ROOT);
        // A bracketed IPv6 literal is only a URL spelling, never a lookup key.
        if (value.startsWith("[") && value.endsWith("]") && value.length() > 2) {
            value = value.substring(1, value.length() - 1);
        }
        return value;
    }
}
