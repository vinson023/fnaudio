package com.fnaudio.client.playback;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;

import androidx.core.content.ContextCompat;
import androidx.media3.session.MediaController;
import androidx.media3.session.SessionToken;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import com.fnaudio.client.data.ConnectionProfile;
import com.google.common.util.concurrent.ListenableFuture;

import org.json.JSONObject;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.concurrent.TimeUnit;

import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.QueueDispatcher;
import okhttp3.mockwebserver.RecordedRequest;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

/** Verifies a mismatched command ticket cannot optimistically alter remote state. */
@RunWith(AndroidJUnit4.class)
public final class PlaybackServiceCommandTicketInstrumentedTest {
    private Context context;
    private MockWebServer server;
    private ConnectionProfile originalProfile;

    @Before
    public void setUp() throws Exception {
        context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        originalProfile = PlaybackRuntimeConfig.activeProfile();
        server = new MockWebServer();
        server.setDispatcher(new QueueDispatcher() {
            @Override
            public MockResponse dispatch(RecordedRequest request) {
                if (request.getPath() != null && request.getPath().contains("/api/playback/control")) {
                    try {
                        JSONObject body = new JSONObject(request.getBody().readUtf8());
                        return new MockResponse().setResponseCode(200)
                                .addHeader("Content-Type", "application/json")
                                .setBody(new JSONObject()
                                        .put("ok", true)
                                        .put("command_id", body.optString("command_id"))
                                        .put("core", new JSONObject().put("command_ticket", "wrong-ticket"))
                                        .toString());
                    } catch (Exception ignored) {
                    }
                }
                return new MockResponse().setResponseCode(200).setBody("{\"state_version\":1}");
            }
        });
        server.start();
        PlaybackRuntimeConfig.activate(new ConnectionProfile(
                "instrument-command-ticket", "Mock NAS", "127.0.0.1", server.getPort(), false,
                false, "", "admin", "password", "token", "", false,
                false, "public", System.currentTimeMillis()));
    }

    @After
    public void tearDown() throws Exception {
        context.stopService(new Intent(context, PlaybackService.class));
        if (originalProfile != null) PlaybackRuntimeConfig.activate(originalProfile);
        server.shutdown();
    }

    @Test
    public void mismatchedTicketLeavesRemoteStatePaused() throws Exception {
        Intent intent = new Intent(context, PlaybackService.class)
                .setAction(PlaybackService.ACTION_REMOTE_ENABLE)
                .putExtra(PlaybackService.EXTRA_TARGET_ID, "dac:ticket-test")
                .putExtra(PlaybackService.EXTRA_TARGET_NAME, "USB DAC")
                .putExtra(PlaybackService.EXTRA_QUEUE_JSON,
                        "[{\"id\":\"ticket-track\",\"title\":\"Ticket track\",\"artist\":\"fnAudio\",\"durationMs\":180000}]")
                .putExtra(PlaybackService.EXTRA_SESSION_GENERATION, 7L)
                .putExtra(PlaybackService.EXTRA_ENGINE_EPOCH, 3L)
                .putExtra(PlaybackService.EXTRA_PLAYING, false);
        ContextCompat.startForegroundService(context, intent);
        Thread.sleep(500L);

        ListenableFuture<MediaController> future = new MediaController.Builder(
                context, new SessionToken(context, new ComponentName(context, PlaybackService.class))).buildAsync();
        MediaController controller = future.get(5, TimeUnit.SECONDS);
        try {
            assertNotNull(controller);
            assertFalse(onMain(controller::getPlayWhenReady));
            InstrumentationRegistry.getInstrumentation().runOnMainSync(controller::play);
            RecordedRequest request = null;
            long deadline = System.currentTimeMillis() + 5000L;
            while (System.currentTimeMillis() < deadline) {
                RecordedRequest next = server.takeRequest(500, TimeUnit.MILLISECONDS);
                if (next != null && next.getPath() != null && next.getPath().contains("/api/playback/control")) {
                    request = next;
                    break;
                }
            }
            assertNotNull(request);
            Thread.sleep(500L);
            // Backend confirmation had a wrong ticket, so state remains paused.
            assertFalse(onMain(controller::getPlayWhenReady));
            assertTrue(request.getPath().contains("/api/playback/control"));
        } finally {
            InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> MediaController.releaseFuture(future));
        }
    }

    private static <T> T onMain(java.util.concurrent.Callable<T> callable) throws Exception {
        java.util.concurrent.atomic.AtomicReference<T> result = new java.util.concurrent.atomic.AtomicReference<>();
        java.util.concurrent.atomic.AtomicReference<Throwable> failure = new java.util.concurrent.atomic.AtomicReference<>();
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            try { result.set(callable.call()); } catch (Throwable error) { failure.set(error); }
        });
        if (failure.get() != null) throw new RuntimeException(failure.get());
        return result.get();
    }
}
