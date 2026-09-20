package com.fnaudio.client.playback;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.webkit.WebView;
import android.view.View;
import android.widget.TextView;

import androidx.media3.session.MediaController;
import androidx.media3.session.SessionToken;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;
import com.fnaudio.client.network.FnOsAuthClient;
import com.fnaudio.client.ui.MainActivity;
import com.google.common.util.concurrent.ListenableFuture;

import org.json.JSONObject;
import org.junit.Assume;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Callable;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

/** Optional real-NAS regression. Credentials are supplied as instrumentation arguments. */
@RunWith(AndroidJUnit4.class)
public final class RealNasPlaybackRestoreInstrumentedTest {
    private static final String PROFILE_ID = "instrument-real-playback-restore";

    @Test
    public void restoredServerQueueRehydratesNativePlayerBeforePlay() throws Exception {
        Bundle arguments = InstrumentationRegistry.getArguments();
        String host = clean(arguments.getString("fnaudioHost"));
        String username = clean(arguments.getString("fnaudioUser"));
        String password = clean(arguments.getString("fnaudioPassword"));
        int port = parsePort(arguments.getString("fnaudioPort", "5666"));
        boolean https = Boolean.parseBoolean(arguments.getString("fnaudioHttps", "false"));
        boolean trustSelfSigned = Boolean.parseBoolean(arguments.getString("fnaudioTrustSelfSigned", "false"));
        Assume.assumeTrue("Real NAS arguments were not supplied", !host.isEmpty() && !username.isEmpty() && !password.isEmpty());

        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        SecureProfileStore store = new SecureProfileStore(context);
        ConnectionProfile originalActive = store.active();
        ConnectionProfile authenticated = authenticate(context, new ConnectionProfile(
                PROFILE_ID,
                "Real NAS restore test",
                host,
                port,
                https,
                trustSelfSigned,
                "",
                username,
                password,
                "",
                "",
                System.currentTimeMillis()
        ), password);
        assertNotNull("fnOS authentication did not return a profile", authenticated);

        store.upsert(authenticated, true);
        context.stopService(new Intent(context, PlaybackService.class));
        Thread.sleep(500L);

        Intent intent = new Intent(context, MainActivity.class)
                .putExtra(MainActivity.EXTRA_PROFILE_ID, PROFILE_ID)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        ListenableFuture<MediaController> controllerFuture = null;
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(intent)) {
            JSONObject restored = waitForRestoredWebQueue(scenario, 30_000L);
            int webQueueSize = restored.optInt("queueSize");
            String webCurrentId = restored.optString("currentId");
            assertTrue("The server playback snapshot did not restore a WebView queue: " + restored,
                    webQueueSize > 0);
            assertFalse("The restored server snapshot has no current song: " + restored,
                    webCurrentId.isEmpty());

            SessionToken token = new SessionToken(context, new ComponentName(context, PlaybackService.class));
            controllerFuture = new MediaController.Builder(context, token).buildAsync();
            MediaController controller = controllerFuture.get(10, TimeUnit.SECONDS);
            waitFor(() -> onMain(controller::getMediaItemCount) == webQueueSize, 15_000L,
                    "The restored WebView queue was not rehydrated into ExoPlayer");
            assertEquals(webCurrentId, currentMediaId(controller));
            assertFalse("Opening the app must not auto-play the restored song", onMain(controller::getPlayWhenReady));

            evaluateJavascript(scenario,
                    "document.getElementById('playBtn').click(); true");
            waitFor(() -> onMain(controller::getPlayWhenReady), 15_000L,
                    "Clicking Play did not start the rehydrated native queue");
            assertEquals(webCurrentId, currentMediaId(controller));
            onMain(() -> {
                // The real-NAS gate starts from a stopped server session. A
                // remote MediaController pause would leave that session
                // paused after the test and contaminate the next gate.
                controller.stop();
                return null;
            });
        } finally {
            if (controllerFuture != null) {
                ListenableFuture<MediaController> future = controllerFuture;
                onMain(() -> {
                    MediaController.releaseFuture(future);
                    return null;
                });
            }
            context.stopService(new Intent(context, PlaybackService.class));
            store.remove(PROFILE_ID);
            store.setActive(originalActive == null ? "" : originalActive.id);
        }
    }

    private static ConnectionProfile authenticate(Context context, ConnectionProfile profile, String password)
            throws InterruptedException {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<ConnectionProfile> result = new AtomicReference<>();
        AtomicReference<String> error = new AtomicReference<>("");
        new FnOsAuthClient().authenticate(context, profile, password, new FnOsAuthClient.Callback() {
            @Override
            public void onSuccess(ConnectionProfile authenticatedProfile) {
                result.set(authenticatedProfile);
                done.countDown();
            }

            @Override
            public void onError(String message) {
                error.set(message == null ? "" : message);
                done.countDown();
            }
        });
        assertTrue("fnOS authentication timed out", done.await(25, TimeUnit.SECONDS));
        assertTrue("fnOS authentication failed: " + error.get(), error.get().isEmpty());
        return result.get();
    }

    private static JSONObject waitForRestoredWebQueue(ActivityScenario<MainActivity> scenario, long timeoutMs)
            throws Exception {
        long deadline = System.currentTimeMillis() + timeoutMs;
        JSONObject latest = new JSONObject();
        while (System.currentTimeMillis() < deadline) {
            String raw = evaluateJavascript(scenario,
                    "(() => { const hasState=typeof state!=='undefined';"
                            + " const item=typeof currentItem==='function'?currentItem():null;"
                            + " return JSON.stringify({queueSize:hasState&&Array.isArray(state.queue)?state.queue.length:0,"
                            + " currentId:item?.id||'',href:location.href,title:document.title,"
                            + " ready:document.readyState,body:(document.body?.innerText||'').slice(0,160),hasState}); })()");
            if (raw != null && !raw.equals("null") && !raw.equals("\"\"")) {
                String decoded = new org.json.JSONTokener(raw).nextValue().toString();
                latest = new JSONObject(decoded);
                if (latest.optInt("queueSize") > 0 && !latest.optString("currentId").isEmpty()) return latest;
            }
            Thread.sleep(250L);
        }
        JSONObject nativeSnapshot = javaWebViewSnapshot(scenario);
        java.util.Iterator<String> keys = nativeSnapshot.keys();
        while (keys.hasNext()) {
            String key = keys.next();
            latest.put(key, nativeSnapshot.opt(key));
        }
        return latest;
    }

    private static JSONObject javaWebViewSnapshot(ActivityScenario<MainActivity> scenario)
            throws InterruptedException {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<JSONObject> result = new AtomicReference<>(new JSONObject());
        scenario.onActivity(activity -> {
            JSONObject snapshot = new JSONObject();
            try {
                WebView webView = activity.findViewById(R.id.webView);
                View errorPanel = activity.findViewById(R.id.errorPanel);
                TextView errorMessage = activity.findViewById(R.id.errorMessage);
                snapshot.put("javaUrl", webView.getUrl());
                snapshot.put("javaTitle", webView.getTitle());
                snapshot.put("javaProgress", webView.getProgress());
                snapshot.put("webViewVisibility", webView.getVisibility());
                snapshot.put("errorVisible", errorPanel.getVisibility() == View.VISIBLE);
                snapshot.put("errorMessage", errorMessage.getText());
            } catch (Exception exception) {
                try {
                    snapshot.put("snapshotError", exception.toString());
                } catch (Exception ignored) {
                }
            }
            result.set(snapshot);
            done.countDown();
        });
        assertTrue("WebView Java snapshot timed out", done.await(5, TimeUnit.SECONDS));
        return result.get();
    }

    private static String evaluateJavascript(ActivityScenario<MainActivity> scenario, String script)
            throws InterruptedException {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> result = new AtomicReference<>("null");
        scenario.onActivity(activity -> {
            WebView webView = activity.findViewById(R.id.webView);
            webView.evaluateJavascript(script, value -> {
                result.set(value);
                done.countDown();
            });
        });
        assertTrue("WebView JavaScript evaluation timed out", done.await(5, TimeUnit.SECONDS));
        return result.get();
    }

    private static void waitFor(Check check, long timeoutMs, String failure) throws Exception {
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            if (check.get()) return;
            Thread.sleep(100L);
        }
        assertTrue(failure, check.get());
    }

    private static String currentMediaId(MediaController controller) throws Exception {
        return onMain(() -> controller.getCurrentMediaItem() == null
                ? "" : controller.getCurrentMediaItem().mediaId);
    }

    private static <T> T onMain(Callable<T> callable) throws Exception {
        AtomicReference<T> value = new AtomicReference<>();
        AtomicReference<Exception> failure = new AtomicReference<>();
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            try {
                value.set(callable.call());
            } catch (Exception exception) {
                failure.set(exception);
            }
        });
        if (failure.get() != null) throw failure.get();
        return value.get();
    }

    private static int parsePort(String value) {
        try {
            return Integer.parseInt(value);
        } catch (Exception ignored) {
            return 5666;
        }
    }

    private static String clean(String value) {
        return value == null ? "" : value.trim();
    }

    private interface Check {
        boolean get() throws Exception;
    }
}
