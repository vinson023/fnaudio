package com.fnaudio.client.network;

import android.content.Context;

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
        if (profile != null && profile.https && profile.trustSelfSigned) {
            trustPinnedSelfSigned(builder, profile.certificatePinSha256);
        }
        return builder.build();
    }

    private static void trustPinnedSelfSigned(OkHttpClient.Builder builder, String expectedPin) {
        try {
            String normalizedPin = CertificatePin.normalize(expectedPin);
            X509TrustManager trustManager = new X509TrustManager() {
                @Override
                public void checkClientTrusted(X509Certificate[] chain, String authType) {
                }

                @Override
                public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
                    if (chain == null || chain.length == 0) {
                        throw new CertificateException("server certificate chain is empty");
                    }
                    chain[0].checkValidity();
                    if (!normalizedPin.isEmpty() && !CertificatePin.matches(normalizedPin, chain[0])) {
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
}
