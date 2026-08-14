package com.fnaudio.client.network;

import org.junit.Test;

import java.nio.charset.StandardCharsets;

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
}
