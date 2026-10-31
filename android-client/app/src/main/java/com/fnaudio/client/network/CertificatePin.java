package com.fnaudio.client.network;

import android.net.http.SslCertificate;
import android.os.Bundle;

import java.io.ByteArrayInputStream;
import java.security.cert.CertificateFactory;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;

import okio.ByteString;

public final class CertificatePin {
    private static final String PREFIX = "sha256/";

    public static final class Observation {
        private volatile String pin = "";

        public void record(X509Certificate certificate) {
            String observed = CertificatePin.of(certificate);
            if (!observed.isEmpty()) pin = observed;
        }

        public String pin() {
            return pin;
        }
    }

    private CertificatePin() {
    }

    public static String normalize(String value) {
        String pin = value == null ? "" : value.trim();
        return pin.matches("sha256/[A-Za-z0-9+/]{43}=") ? pin : "";
    }

    public static String of(X509Certificate certificate) {
        return of((Certificate) certificate);
    }

    /**
     * OkHttp exposes TLS peer certificates as the generic Certificate type.
     * Do not require the concrete object to be an X509Certificate: Android's
     * provider may wrap the same X.509 leaf with another Certificate class.
     */
    public static String of(Certificate certificate) {
        if (certificate == null) return "";
        try {
            return ofEncoded(certificate.getEncoded());
        } catch (Exception ignored) {
            return "";
        }
    }

    static String ofEncoded(byte[] encoded) {
        if (encoded == null || encoded.length == 0) return "";
        return PREFIX + ByteString.of(encoded).sha256().base64();
    }

    static String firstAvailable(String... candidates) {
        if (candidates == null) return "";
        for (String candidate : candidates) {
            String normalized = normalize(candidate);
            if (!normalized.isEmpty()) return normalized;
        }
        return "";
    }

    public static boolean matches(String expected, X509Certificate certificate) {
        String normalized = normalize(expected);
        return !normalized.isEmpty() && normalized.equals(of(certificate));
    }

    public static String of(SslCertificate certificate) {
        if (certificate == null) return "";
        try {
            Bundle state = SslCertificate.saveState(certificate);
            byte[] encoded = state == null ? null : state.getByteArray("x509-certificate");
            if (encoded == null || encoded.length == 0) return "";
            X509Certificate x509 = (X509Certificate) CertificateFactory.getInstance("X.509")
                    .generateCertificate(new ByteArrayInputStream(encoded));
            return of(x509);
        } catch (Exception ignored) {
            return "";
        }
    }
}
