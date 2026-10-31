package com.fnaudio.client.network;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.security.PublicKey;
import java.security.cert.Certificate;

import static org.junit.Assert.assertEquals;

public final class CertificatePinTest {
    @Test
    public void sha256PinUsesTheCompleteCertificateEncoding() {
        assertEquals(
                "sha256/ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0=",
                CertificatePin.ofEncoded("abc".getBytes(StandardCharsets.UTF_8))
        );
    }

    @Test
    public void malformedStoredPinsAreRejected() {
        assertEquals("", CertificatePin.normalize(""));
        assertEquals("", CertificatePin.normalize("sha256/not-a-fingerprint"));
        assertEquals(
                "sha256/ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0=",
                CertificatePin.normalize(" sha256/ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0= ")
        );
    }

    @Test
    public void pinCanBeReadFromTheGenericCertificateTypeReturnedByTls() {
        Certificate observed = new Certificate("X.509") {
            @Override public byte[] getEncoded() { return "abc".getBytes(StandardCharsets.UTF_8); }
            @Override public void verify(PublicKey key) { }
            @Override public void verify(PublicKey key, String sigProvider) { }
            @Override public String toString() { return "test-certificate"; }
            @Override public PublicKey getPublicKey() { return null; }
        };
        assertEquals(
                "sha256/ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0=",
                CertificatePin.of(observed)
        );
    }

    @Test
    public void firstAvailablePinUsesTlsObservationOnlyWhenHandshakePinIsMissing() {
        String first = "sha256/ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0=";
        String second = "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
        assertEquals(first, CertificatePin.firstAvailable("", first));
        assertEquals(second, CertificatePin.firstAvailable(second, first));
        assertEquals(first, CertificatePin.firstAvailable("", "invalid", first));
        assertEquals("", CertificatePin.firstAvailable("invalid", "also-invalid"));
    }
}
