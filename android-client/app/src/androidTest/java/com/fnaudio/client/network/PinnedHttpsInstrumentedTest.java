package com.fnaudio.client.network;

import com.fnaudio.client.data.ConnectionProfile;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.IOException;

import okhttp3.Request;
import okhttp3.Response;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.tls.HandshakeCertificates;
import okhttp3.tls.HeldCertificate;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.fail;

@RunWith(AndroidJUnit4.class)
public final class PinnedHttpsInstrumentedTest {
    @Test
    public void pinnedSelfSignedHttpsAcceptsItsFirstCertificateAndRejectsReplacement() throws Exception {
        HeldCertificate trustedCertificate = new HeldCertificate.Builder()
                .commonName("localhost")
                .addSubjectAlternativeName("localhost")
                .build();
        HandshakeCertificates serverCertificates = new HandshakeCertificates.Builder()
                .heldCertificate(trustedCertificate)
                .build();

        try (MockWebServer server = new MockWebServer()) {
            server.useHttps(serverCertificates.sslSocketFactory(), false);
            server.enqueue(new MockResponse().setBody("trusted"));
            server.start();

            ConnectionProfile trustedProfile = new ConnectionProfile(
                    "tls", "TLS", "localhost", server.getPort(), true, true,
                    CertificatePin.of(trustedCertificate.certificate()), "admin", "", "", "", 1L);
            try (Response response = HttpClientFactory.create(
                    InstrumentationRegistry.getInstrumentation().getTargetContext(), trustedProfile)
                    .newCall(new Request.Builder().url(server.url("/")).build()).execute()) {
                assertEquals(200, response.code());
                assertEquals("trusted", response.body().string());
            }

            server.enqueue(new MockResponse().setBody("must-not-be-read"));
            ConnectionProfile mismatchedProfile = trustedProfile.withCertificatePin(
                    "sha256/ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0=");
            try {
                HttpClientFactory.create(
                                InstrumentationRegistry.getInstrumentation().getTargetContext(), mismatchedProfile)
                        .newCall(new Request.Builder().url(server.url("/")).build()).execute();
                fail("a different certificate pin must fail before the HTTP response is accepted");
            } catch (IOException expected) {
                // Expected: Android's TLS stack wraps the pin mismatch in IOException.
            }
        }
    }
}
