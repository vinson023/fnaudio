package com.fnaudio.client.ui;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.os.ParcelFileDescriptor;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;

import org.json.JSONObject;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import okhttp3.mockwebserver.Dispatcher;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.pressBackUnconditionally;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;
import static org.junit.Assert.assertTrue;

@RunWith(AndroidJUnit4.class)
public final class MainActivityWebViewInstrumentedTest {
    private static final String PROFILE_ID = "instrument-main-webview";

    private SecureProfileStore store;
    private String originalActiveId;
    private MockWebServer server;
    private CountDownLatch pageRequest;
    private CountDownLatch coverRequest;
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

        pageRequest = new CountDownLatch(1);
        coverRequest = new CountDownLatch(1);
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
                                String reqid = new JSONObject(text).optString("reqid");
                                socket.send(new JSONObject()
                                        .put("reqid", reqid)
                                        .put("token", "instrument-token")
                                        .put("longToken", "instrument-long-token")
                                        .put("result", "success")
                                        .toString());
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
                    pageRequest.countDown();
                    return new MockResponse()
                            .addHeader("Content-Type", "text/html; charset=utf-8")
                            .setBody("<html><body>Mock fnAudio<img src='cover/fixture?size=160'>"
                                    + "<script>function fnAudioHandleAndroidBack(){return false;}</script></body></html>");
                }
                return new MockResponse().setResponseCode(404);
            }
        });
        server.start();
        store.upsert(new ConnectionProfile(
                PROFILE_ID, "模拟器 NAS", "127.0.0.1", server.getPort(), false, false, "",
                "admin", "", "seed-token", "", System.currentTimeMillis()), true);
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
        try (ActivityScenario<MainActivity> ignored = ActivityScenario.launch(intent)) {
            assertTrue("MainActivity did not request the authenticated fnAudio page", pageRequest.await(12, TimeUnit.SECONDS));
            assertTrue("MainActivity did not proxy the private cover request", coverRequest.await(12, TimeUnit.SECONDS));
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

    private static void grantNotificationPermission() {
        try (ParcelFileDescriptor ignored = InstrumentationRegistry.getInstrumentation().getUiAutomation()
                .executeShellCommand("pm grant com.fnaudio.client " + Manifest.permission.POST_NOTIFICATIONS)) {
            // Android 13+ notification prompt must not obscure the navigation assertion.
        } catch (Exception ignored) {
        }
    }
}
