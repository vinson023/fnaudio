package com.fnaudio.client.network;

import android.content.Context;
import android.webkit.CookieManager;

import androidx.annotation.Nullable;

import com.fnaudio.client.data.ConnectionProfile;

import java.security.SecureRandom;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.util.concurrent.TimeUnit;

import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

import okhttp3.OkHttpClient;
import okhttp3.Request;

public final class HttpClientFactory {
    private HttpClientFactory() {
    }

    public static OkHttpClient create(@Nullable Context context, ConnectionProfile profile) {
        OkHttpClient.Builder builder = new OkHttpClient.Builder()
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(15, TimeUnit.SECONDS)
                .pingInterval(20, TimeUnit.SECONDS);
        // Let Android select the active default network. Binding an IPv6 FN Connect
        // endpoint to an arbitrary Network can fail with EPERM on VPN, dual-SIM,
        // or restricted networks and breaks every API request sharing this client.
        // A self-signed profile is only safe after the first certificate has
        // been pinned by FnOsAuthClient.  Enabling the permissive trust
        // manager with an empty or malformed pin would accept any certificate
        // and the hostname verifier below deliberately cannot compensate.
        if (profile != null && profile.https && profile.trustSelfSigned
                && !CertificatePin.normalize(profile.certificatePinSha256).isEmpty()) {
            trustPinnedSelfSigned(builder, profile.certificatePinSha256);
        }
        return builder.build();
    }

    /**
     * Creates the one-time trust-on-first-use client used only to authenticate
     * a user-selected self-signed endpoint that has no stored pin yet. The
     * authentication WebSocket records the observed certificate pin before it
     * returns a usable profile; regular media/UI clients always use create().
     */
    public static OkHttpClient createAuthenticationClient(@Nullable Context context, ConnectionProfile profile) {
        return createAuthenticationClient(context, profile, null);
    }

    public static OkHttpClient createAuthenticationClient(@Nullable Context context, ConnectionProfile profile,
                                                           @Nullable CertificatePin.Observation observation) {
        if (profile == null || !profile.https || !profile.trustSelfSigned
                || !CertificatePin.normalize(profile.certificatePinSha256).isEmpty()) {
            return create(context, profile);
        }
        OkHttpClient.Builder builder = create(context, profile).newBuilder();
        trustFirstUseSelfSigned(builder, observation);
        return builder.build();
    }

    /**
     * Creates the media client with token headers scoped to the configured
     * fnOS origin. A network interceptor also sees follow-up redirect
     * requests, so credentials cannot be carried to another host.
     */
    public static OkHttpClient createMediaClient(@Nullable Context context, ConnectionProfile profile) {
        OkHttpClient.Builder builder = create(context, profile).newBuilder();
        if (profile != null && !profile.webSession && !profile.token.isEmpty()) {
            builder.addNetworkInterceptor(chain -> {
                Request request = chain.request();
                Request.Builder scoped = request.newBuilder()
                        .removeHeader("Authorization")
                        .removeHeader("X-Fnaudio-Trim-Token")
                        .removeHeader("Cookie");
                if (sameProfileOrigin(profile, request)) {
                    String encodedToken = encodeCookie(profile.token);
                    scoped.header("Authorization", "Bearer " + profile.token)
                            .header("X-Fnaudio-Trim-Token", profile.token)
                            .header("Cookie", "fnaudio_trim_token=" + encodedToken
                                    + "; trim_token=" + encodedToken + "; token=" + encodedToken
                                    + "; fnos-token=" + encodedToken
                                    + accessCodeCookie(context, profile));
                    String accessCode = SessionCookies.accessCodeHeader(profile.accessCode);
                    if (!accessCode.isEmpty()) scoped.header("X-Access-Code", accessCode);
                }
                return chain.proceed(scoped.build());
            });
        }
        return builder.build();
    }

    private static boolean sameProfileOrigin(ConnectionProfile profile, Request request) {
        if (profile == null || request == null || request.url() == null) return false;
        String expectedScheme = profile.https ? "https" : "http";
        if (!expectedScheme.equalsIgnoreCase(request.url().scheme())
                || !profile.host.equalsIgnoreCase(request.url().host())) return false;
        int defaultPort = profile.https ? 443 : 80;
        int expectedPort = profile.port > 0 ? profile.port : defaultPort;
        return request.url().port() == expectedPort;
    }

    private static String encodeCookie(String value) {
        return SessionCookies.encodeToken(value);
    }

    private static String accessCodeCookie(@Nullable Context context, ConnectionProfile profile) {
        if (context == null || profile == null) return "";
        String cookies = CookieManager.getInstance().getCookie(profile.httpOrigin());
        if (cookies == null || cookies.trim().isEmpty()) return "";
        for (String cookie : cookies.split(";")) {
            String pair = cookie.trim();
            if (pair.startsWith("os-access-code=") && pair.length() > "os-access-code=".length()) {
                return "; " + pair;
            }
        }
        return "";
    }

    private static void trustPinnedSelfSigned(OkHttpClient.Builder builder, String expectedPin) {
        try {
            String normalizedPin = CertificatePin.normalize(expectedPin);
            if (normalizedPin.isEmpty()) {
                throw new CertificateException("certificate pin is missing or invalid");
            }
            X509TrustManager trustManager = new X509TrustManager() {
                @Override
                public void checkClientTrusted(X509Certificate[] chain, String authType) {
                }

                @Override
                public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                    if (chain == null || chain.length == 0) {
                        throw new CertificateException("server certificate chain is empty");
                    }
                    if (!CertificatePin.matches(normalizedPin, chain[0])) {
                        throw new CertificateException("certificate pin mismatch");
                    }
                }

                @Override
                public X509Certificate[] getAcceptedIssuers() {
                    return new X509Certificate[0];
                }
            };
            SSLContext sslContext = SSLContext.getInstance("TLS");
            sslContext.init(null, new TrustManager[]{trustManager}, new SecureRandom());
            builder.sslSocketFactory(sslContext.getSocketFactory(), trustManager);
            builder.hostnameVerifier((hostname, session) -> true);
        } catch (Exception exception) {
            throw new IllegalStateException("无法启用自签名证书指纹模式", exception);
        }
    }

    private static void trustFirstUseSelfSigned(OkHttpClient.Builder builder,
                                                @Nullable CertificatePin.Observation observation) {
        try {
            X509TrustManager trustManager = new X509TrustManager() {
                @Override
                public void checkClientTrusted(X509Certificate[] chain, String authType) {
                }

                @Override
                public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                    if (chain == null || chain.length == 0) {
                        throw new CertificateException("server certificate chain is empty");
                    }
                    if (observation != null) observation.record(chain[0]);
                    // The user explicitly opted into a self-signed endpoint.
                    // FnOsAuthClient observes and persists this certificate's
                    // exact pin before any regular client is created. For this
                    // explicitly trusted pinned identity, validity dates do
                    // not add identity assurance and can block local NASes
                    // using expired self-signed certificates.
                }

                @Override
                public X509Certificate[] getAcceptedIssuers() {
                    return new X509Certificate[0];
                }
            };
            SSLContext sslContext = SSLContext.getInstance("TLS");
            sslContext.init(null, new TrustManager[]{trustManager}, new SecureRandom());
            builder.sslSocketFactory(sslContext.getSocketFactory(), trustManager);
            builder.hostnameVerifier((hostname, session) -> true);
        } catch (Exception exception) {
            throw new IllegalStateException("无法启用自签名证书首次确认模式", exception);
        }
    }
}
