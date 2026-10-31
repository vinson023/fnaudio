package com.fnaudio.client.network;

import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.network.FnOsAuthClient;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.json.JSONObject;

import java.io.IOException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.tls.HandshakeCertificates;
import okhttp3.tls.HeldCertificate;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.fail;

@RunWith(AndroidJUnit4.class)
public final class PinnedHttpsInstrumentedTest {
    @Test
    public void explicitlyTrustedSelfSignedHttpsDoesNotDependOnCertificateDates() throws Exception {
        long now = System.currentTimeMillis();
        HeldCertificate expiredCertificate = new HeldCertificate.Builder()
                .commonName("localhost")
                .addSubjectAlternativeName("localhost")
                .validityInterval(now - 86_400_000L * 3, now - 86_400_000L)
                .build();
        HandshakeCertificates serverCertificates = new HandshakeCertificates.Builder()
                .heldCertificate(expiredCertificate)
                .build();

        try (MockWebServer server = new MockWebServer()) {
            server.useHttps(serverCertificates.sslSocketFactory(), false);
            server.enqueue(new MockResponse().setBody("trusted"));
            server.start();

            ConnectionProfile profile = new ConnectionProfile(
                    "tls-expired", "TLS", "localhost", server.getPort(), true, true,
                    "", "admin", "", "", "", 1L);
            CertificatePin.Observation observation = new CertificatePin.Observation();
            try (Response response = HttpClientFactory.createAuthenticationClient(
                    InstrumentationRegistry.getInstrumentation().getTargetContext(), profile, observation)
                    .newCall(new Request.Builder().url(server.url("/")).build()).execute()) {
                assertEquals(200, response.code());
                assertEquals("trusted", response.body().string());
            }
            assertEquals(CertificatePin.of(expiredCertificate.certificate()), observation.pin());
        }
    }

    @Test
    public void firstUseHttpsLoginPersistsTheCertificateObservedDuringTlsValidation() throws Exception {
        HeldCertificate certificate = new HeldCertificate.Builder()
                .commonName("localhost")
                .addSubjectAlternativeName("localhost")
                .build();
        HandshakeCertificates serverCertificates = new HandshakeCertificates.Builder()
                .heldCertificate(certificate)
                .build();
        CountDownLatch authenticated = new CountDownLatch(1);
        AtomicReference<ConnectionProfile> result = new AtomicReference<>();
        AtomicReference<String> error = new AtomicReference<>("");
        MockWebServer server = new MockWebServer();
        FnOsAuthClient client = new FnOsAuthClient();

        try {
            server.useHttps(serverCertificates.sslSocketFactory(), false);
            server.enqueue(new MockResponse().withWebSocketUpgrade(new WebSocketListener() {
                @Override
                public void onMessage(WebSocket socket, String text) {
                    try {
                        JSONObject request = new JSONObject(text);
                        socket.send(new JSONObject()
                                .put("reqid", request.optString("reqid"))
                                .put("result", "succ")
                                .put("data", new JSONObject()
                                        .put("token", "fresh-token")
                                        .put("longToken", "fresh-long-token"))
                                .toString());
                    } catch (Exception exception) {
                        error.set(exception.getMessage());
                        authenticated.countDown();
                    }
                }
            }));
            server.start();

            ConnectionProfile profile = new ConnectionProfile(
                    "tls-first-use", "TLS", "localhost", server.getPort(), true, true,
                    "", "admin", "password", "", "", 1L);
            client.authenticate(InstrumentationRegistry.getInstrumentation().getTargetContext(), profile,
                    "password", new FnOsAuthClient.Callback() {
                        @Override public void onSuccess(ConnectionProfile authenticatedProfile) {
                            result.set(authenticatedProfile);
                            authenticated.countDown();
                        }

                        @Override public void onError(String message) {
                            error.set(message);
                            authenticated.countDown();
                        }
                    });

            assertEquals("HTTPS login did not complete: " + error.get(), true,
                    authenticated.await(10, TimeUnit.SECONDS));
            assertEquals("", error.get());
            assertEquals(CertificatePin.of(certificate.certificate()),
                    result.get() == null ? "" : result.get().certificatePinSha256);
        } finally {
            client.cancel();
            try {
                server.shutdown();
            } catch (IOException ignored) {
                // A closed WebSocket may leave MockWebServer's task queue alive briefly on Android.
            }
        }
    }

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
