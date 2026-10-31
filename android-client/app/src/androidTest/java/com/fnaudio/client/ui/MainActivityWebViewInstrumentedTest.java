package com.fnaudio.client.ui;

import android.Manifest;
import android.app.Activity;
import android.app.Instrumentation;
import android.content.Context;
import android.content.Intent;
import android.os.ParcelFileDescriptor;
import android.os.SystemClock;
import android.view.View;
import android.webkit.WebView;
import android.widget.TextView;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;
import com.fnaudio.client.network.CertificatePin;

import org.json.JSONObject;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.IOException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import okhttp3.mockwebserver.Dispatcher;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import okhttp3.tls.HandshakeCertificates;
import okhttp3.tls.HeldCertificate;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.pressBackUnconditionally;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

@RunWith(AndroidJUnit4.class)
public final class MainActivityWebViewInstrumentedTest {
    private static final String PROFILE_ID = "instrument-main-webview";

    private SecureProfileStore store;
    private String originalActiveId;
    private MockWebServer server;
    private MockWebServer secureServer;
    private CountDownLatch coverRequest;
    private CountDownLatch tokenRefreshRequests;
    private volatile String coverAuthorization = "";
    private volatile String coverTrimToken = "";
    private volatile String coverCookie = "";

    @Before
    public void setUp() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        store = new SecureProfileStore(context);
        ConnectionProfile active = store.active();
        originalActiveId = active == null ? "" : active.id;
        store.remove(PROFILE_ID);
        grantNotificationPermission();

        coverRequest = new CountDownLatch(1);
        tokenRefreshRequests = new CountDownLatch(3);
        server = new MockWebServer();
        server.setDispatcher(new Dispatcher() {
            @Override
            public MockResponse dispatch(RecordedRequest request) {
                String path = request.getPath() == null ? "" : request.getPath();
                if (path.startsWith("/websocket")) {
                    return new MockResponse().withWebSocketUpgrade(new WebSocketListener() {
                        @Override
                        public void onMessage(WebSocket socket, String text) {
                            try {
                                JSONObject request = new JSONObject(text);
                                String reqid = request.optString("reqid");
                                String operation = request.optString("req");
                                tokenRefreshRequests.countDown();
                                if ("user.authToken".equals(operation) || "user.tokenLogin".equals(operation)) {
                                    socket.send(new JSONObject()
                                            .put("reqid", reqid)
                                            .put("result", "fail")
                                            .put("errno", 65534)
                                            .put("errmsg", "token expired")
                                            .toString());
                                } else {
                                    // Real fnOS password-login responses can
                                    // put result on the envelope and refreshed
                                    // tokens in data.
                                    socket.send(new JSONObject()
                                            .put("reqid", reqid)
                                            .put("result", "succ")
                                            .put("data", new JSONObject()
                                                    .put("token", "instrument-token")
                                                    .put("longToken", "instrument-long-token"))
                                            .toString());
                                }
                            } catch (Exception ignored) {
                            }
                        }
                    });
                }
                if (path.startsWith("/cgi/ThirdParty/fnaudio/index.cgi/")) {
                    if (path.contains("/cover/fixture")) {
                        coverAuthorization = request.getHeader("Authorization") == null ? "" : request.getHeader("Authorization");
                        coverTrimToken = request.getHeader("X-Fnaudio-Trim-Token") == null ? "" : request.getHeader("X-Fnaudio-Trim-Token");
                        coverCookie = request.getHeader("Cookie") == null ? "" : request.getHeader("Cookie");
                        coverRequest.countDown();
                        return new MockResponse().addHeader("Content-Type", "image/jpeg")
                                .addHeader("Cache-Control", "public, max-age=2592000, immutable")
                                .setBody(new okio.Buffer().write(new byte[]{(byte) 0xff, (byte) 0xd8, (byte) 0xff, (byte) 0xd9}));
                    }
                    return new MockResponse()
                            .addHeader("Content-Type", "application/json; charset=utf-8")
                            .setBody("{\"ok\":true}");
                }
                return new MockResponse().setResponseCode(404);
            }
        });
        server.start();
        store.upsert(new ConnectionProfile(
                PROFILE_ID, "模拟器 NAS", "127.0.0.1", server.getPort(), false, false, "",
                "admin", "test-saved-password", "expired-test-token", "expired-test-long-token", System.currentTimeMillis()), true);
    }

    @After
    public void tearDown() {
        if (server != null) {
            try {
                server.shutdown();
            } catch (Exception ignored) {
                // WebView can finish closing a pooled request after the activity
                // has been destroyed; the test server must not mask assertions.
            }
        }
        store.remove(PROFILE_ID);
        store.setActive(originalActiveId);
    }

    @Test
    public void authenticatedWebViewLoadsMockFnAudioAndDoubleBackReturnsToLogin() throws Exception {
        Intent intent = new Intent(InstrumentationRegistry.getInstrumentation().getTargetContext(), MainActivity.class)
                .putExtra(MainActivity.EXTRA_PROFILE_ID, PROFILE_ID)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(intent)) {
            onView(withId(R.id.webView)).check(matches(isDisplayed()));
            scenario.onActivity(activity -> {
                WebView webView = activity.findViewById(R.id.webView);
                webView.evaluateJavascript("(() => { const image = new Image(); image.src = 'cover/fixture?size=160'; document.body.appendChild(image); })()", null);
            });
            assertTrue("MainActivity did not proxy the private cover request", coverRequest.await(12, TimeUnit.SECONDS));
            assertTrue("Expired tokens did not fall back to the encrypted saved password", tokenRefreshRequests.await(2, TimeUnit.SECONDS));
            assertTrue("Cover request is missing Authorization", coverAuthorization.startsWith("Bearer "));
            assertTrue("Cover request is missing X-Fnaudio-Trim-Token", !coverTrimToken.isEmpty());
            assertTrue("Cover request is missing authenticated cookies", coverCookie.contains("fnaudio_trim_token="));
            onView(withId(R.id.webView)).check(matches(isDisplayed()));
            onView(withId(R.id.webView)).perform(pressBackUnconditionally());
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            onView(withId(R.id.webView)).perform(pressBackUnconditionally());
            onView(withId(R.id.fnId)).check(matches(isDisplayed()));
            onView(withId(R.id.fnId)).check(matches(withText("127.0.0.1:" + server.getPort())));
        }
    }

    @Test
    public void mobileLogoutClearsActiveTokensAndCookiesButKeepsConnectionHistory() throws Exception {
        Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
        Instrumentation.ActivityMonitor loginMonitor = instrumentation.addMonitor(
                LoginActivity.class.getName(), null, false);
        Intent intent = new Intent(instrumentation.getTargetContext(), MainActivity.class)
                .putExtra(MainActivity.EXTRA_PROFILE_ID, PROFILE_ID)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(intent)) {
            onView(withId(R.id.webView)).check(matches(isDisplayed()));
            scenario.onActivity(activity -> {
                WebView webView = activity.findViewById(R.id.webView);
                webView.evaluateJavascript("(() => { const image = new Image(); image.src = 'cover/fixture?size=160'; document.body.appendChild(image); })()", null);
            });
            assertTrue("WebView did not finish initializing its bundled UI", coverRequest.await(12, TimeUnit.SECONDS));
            awaitLogoutButtonReady(scenario);
            scenario.onActivity(activity -> {
                WebView webView = activity.findViewById(R.id.webView);
                webView.evaluateJavascript("document.getElementById('mobileLogoutBtn').click()", null);
            });

            Activity loginActivity = instrumentation.waitForMonitorWithTimeout(loginMonitor, 8000);
            assertNotNull("Logout should return to the native login screen", loginActivity);
            assertNull("Logout must clear the active connection", store.active());
            ConnectionProfile signedOut = store.find(PROFILE_ID);
            assertNotNull("Logout must preserve the connection history", signedOut);
            assertEquals("", signedOut.token);
            assertEquals("", signedOut.longToken);
            assertEquals("test-saved-password", signedOut.password);
            String cookies = android.webkit.CookieManager.getInstance().getCookie(signedOut.httpOrigin());
            assertTrue("Logout must clear this profile's WebView session cookies",
                    cookies == null || !cookies.contains("fnaudio_trim_token="));
        } finally {
            instrumentation.removeMonitor(loginMonitor);
        }
    }

    @Test
    public void mobileLogoutOnPinnedHttpsReturnsToLoginWithoutCrashing() throws Exception {
        HeldCertificate certificate = new HeldCertificate.Builder()
                .commonName("localhost")
                .addSubjectAlternativeName("localhost")
                .build();
        HandshakeCertificates serverCertificates = new HandshakeCertificates.Builder()
                .heldCertificate(certificate)
                .build();
        CountDownLatch secureCoverRequest = new CountDownLatch(1);
        secureServer = new MockWebServer();
        secureServer.useHttps(serverCertificates.sslSocketFactory(), false);
        secureServer.setDispatcher(new Dispatcher() {
            @Override
            public MockResponse dispatch(RecordedRequest request) {
                String path = request.getPath() == null ? "" : request.getPath();
                if (path.startsWith("/websocket")) {
                    return new MockResponse().withWebSocketUpgrade(new WebSocketListener() {
                        @Override
                        public void onMessage(WebSocket socket, String text) {
                            try {
                                JSONObject authRequest = new JSONObject(text);
                                socket.send(new JSONObject()
                                        .put("reqid", authRequest.optString("reqid"))
                                        .put("result", "succ")
                                        .put("data", new JSONObject()
                                                .put("token", "https-test-token")
                                                .put("longToken", "https-test-long-token"))
                                        .toString());
                            } catch (Exception ignored) {
                            }
                        }
                    });
                }
                if (path.contains("/cover/fixture")) {
                    secureCoverRequest.countDown();
                    return new MockResponse().addHeader("Content-Type", "image/jpeg")
                            .setBody(new okio.Buffer().write(new byte[]{(byte) 0xff, (byte) 0xd8, (byte) 0xff, (byte) 0xd9}));
                }
                return new MockResponse().setResponseCode(404);
            }
        });
        secureServer.start();
        ConnectionProfile secureProfile = new ConnectionProfile(
                PROFILE_ID, "Pinned HTTPS", "localhost", secureServer.getPort(), true, true,
                CertificatePin.of(certificate.certificate()), "admin", "test-saved-password",
                "https-test-token", "https-test-long-token", false, System.currentTimeMillis());
        store.upsert(secureProfile, true);

        Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
        Instrumentation.ActivityMonitor loginMonitor = instrumentation.addMonitor(
                LoginActivity.class.getName(), null, false);
        Intent intent = new Intent(instrumentation.getTargetContext(), MainActivity.class)
                .putExtra(MainActivity.EXTRA_PROFILE_ID, PROFILE_ID)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        Activity loginActivity = null;
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(intent)) {
            awaitWebViewVisible(scenario);
            scenario.onActivity(activity -> {
                WebView webView = activity.findViewById(R.id.webView);
                webView.evaluateJavascript("(() => { const image = new Image(); image.src = 'cover/fixture?size=160'; document.body.appendChild(image); })()", null);
            });
            assertTrue("Pinned HTTPS WebView request did not reach the test server",
                    secureCoverRequest.await(12, TimeUnit.SECONDS));

            awaitLogoutButtonReady(scenario);

            scenario.onActivity(activity -> {
                WebView webView = activity.findViewById(R.id.webView);
                webView.evaluateJavascript("document.getElementById('mobileLogoutBtn').click()", null);
            });
            loginActivity = instrumentation.waitForMonitorWithTimeout(loginMonitor, 8000);
            assertNotNull("HTTPS logout should return to the native login screen", loginActivity);
            instrumentation.waitForIdleSync();

            assertNull("HTTPS logout must clear the active connection", store.active());
            ConnectionProfile signedOut = store.find(PROFILE_ID);
            assertNotNull("HTTPS logout must preserve the connection history", signedOut);
            assertEquals("", signedOut.token);
            assertEquals("", signedOut.longToken);
            assertEquals("test-saved-password", signedOut.password);
            String cookies = android.webkit.CookieManager.getInstance().getCookie(signedOut.httpOrigin());
            assertTrue("HTTPS logout must clear the session cookie",
                    cookies == null || !cookies.contains("fnaudio_trim_token="));
            assertTrue("Login screen should remain available after HTTPS logout",
                    loginActivity.getWindow() != null);
        } finally {
            instrumentation.removeMonitor(loginMonitor);
            if (loginActivity != null && !loginActivity.isFinishing()) loginActivity.finish();
            if (secureServer != null) {
                try {
                    secureServer.shutdown();
                } catch (IOException ignored) {
                    // The test's HTTPS WebSocket can outlive ActivityScenario by a few seconds.
                }
                secureServer = null;
            }
        }
    }

    @Test
    public void responseCharsetPreservesServerDeclaredCharset() {
        assertEquals("GBK", MainActivity.responseCharset(
                okhttp3.MediaType.parse("text/plain; charset=GBK"), "text/plain"));
        assertNull(MainActivity.responseCharset(
                okhttp3.MediaType.parse("text/plain"), "text/plain"));
    }

    private static void grantNotificationPermission() {
        try (ParcelFileDescriptor ignored = InstrumentationRegistry.getInstrumentation().getUiAutomation()
                .executeShellCommand("pm grant " + InstrumentationRegistry.getInstrumentation().getTargetContext().getPackageName()
                        + " " + Manifest.permission.POST_NOTIFICATIONS)) {
            // Android 13+ notification prompt must not obscure the navigation assertion.
        } catch (Exception ignored) {
        }
    }

    private static void awaitWebViewVisible(ActivityScenario<MainActivity> scenario) throws Exception {
        AtomicReference<Boolean> visible = new AtomicReference<>(false);
        AtomicReference<String> error = new AtomicReference<>("");
        long deadline = SystemClock.uptimeMillis() + 12000;
        do {
            scenario.onActivity(activity -> {
                WebView webView = activity.findViewById(R.id.webView);
                visible.set(webView != null && webView.getVisibility() == View.VISIBLE);
                TextView message = activity.findViewById(R.id.errorMessage);
                error.set(message == null ? "" : message.getText().toString());
            });
            if (visible.get()) return;
            SystemClock.sleep(100);
        } while (SystemClock.uptimeMillis() < deadline);
        assertTrue("WebView did not become visible; activity error: " + error.get(), visible.get());
    }

    private static void awaitLogoutButtonReady(ActivityScenario<MainActivity> scenario) throws Exception {
        AtomicReference<String> buttonState = new AtomicReference<>("");
        long deadline = SystemClock.uptimeMillis() + 12000;
        do {
            CountDownLatch stateRead = new CountDownLatch(1);
            scenario.onActivity(activity -> {
                WebView webView = activity.findViewById(R.id.webView);
                webView.evaluateJavascript(
                        "(() => { const button = document.getElementById('mobileLogoutBtn'); "
                                + "return button ? (button.hidden ? 1 : 0) : -1; })()",
                        value -> {
                            buttonState.set(value);
                            stateRead.countDown();
                        });
            });
            assertTrue("Could not inspect HTTPS logout control", stateRead.await(5, TimeUnit.SECONDS));
            if ("0".equals(buttonState.get())) return;
            SystemClock.sleep(100);
        } while (SystemClock.uptimeMillis() < deadline);
        assertEquals("Native logout control never became available", "0", buttonState.get());
    }
}
