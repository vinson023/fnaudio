package com.fnaudio.client.playback;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.ParcelFileDescriptor;
import android.service.notification.StatusBarNotification;

import androidx.core.content.ContextCompat;
import androidx.media3.session.MediaController;
import androidx.media3.session.SessionToken;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import com.google.common.util.concurrent.ListenableFuture;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import org.json.JSONObject;

import java.util.concurrent.TimeUnit;

import static org.junit.Assert.fail;

/** Verifies that server-side playback still owns a real Android media notification. */
@RunWith(AndroidJUnit4.class)
public final class PlaybackServiceRemoteNotificationInstrumentedTest {
    private static final int NOTIFICATION_ID = 7011;
    private Context context;

    @Before
    public void setUp() {
        context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        context.getSharedPreferences("fnaudio_remote_session", Context.MODE_PRIVATE).edit()
                .clear().commit();
        grantNotificationPermission();
    }

    @After
    public void tearDown() {
        context.stopService(new Intent(context, PlaybackService.class));
        context.getSharedPreferences("fnaudio_remote_session", Context.MODE_PRIVATE).edit()
                .clear().commit();
    }

    @Test
    public void dacAndDlnaTargetsExposeMediaSessionNotification() throws Exception {
        startRemoteTarget("dac:usb-test", "USB DAC");
        assertMediaNotification("DAC");

        startRemoteTarget("upnp:renderer-test", "DLNA Renderer");
        assertMediaNotification("DLNA");
    }

    @Test
    public void remoteUpdateWithStaleIdentityDoesNotReplaceSession() throws Exception {
        startRemoteTarget("dac:identity-test", "USB DAC");
        Thread.sleep(400L);
        Intent stale = new Intent(context, PlaybackService.class)
                .setAction(PlaybackService.ACTION_REMOTE_UPDATE)
                .putExtra(PlaybackService.EXTRA_TARGET_ID, "dac:identity-test")
                .putExtra(PlaybackService.EXTRA_SESSION_GENERATION, 9999L)
                .putExtra(PlaybackService.EXTRA_ENGINE_EPOCH, 9999L)
                .putExtra(PlaybackService.EXTRA_INDEX, 0)
                .putExtra(PlaybackService.EXTRA_POSITION_MS, 123456L)
                .putExtra(PlaybackService.EXTRA_DURATION_MS, 180000L)
                .putExtra(PlaybackService.EXTRA_PLAYING, true);
        ContextCompat.startForegroundService(context, stale);
        Thread.sleep(500L);
        assertMediaNotification("stale identity");
    }

    @Test
    public void explicitRemoteEnableWinsOverQueuedRestore() throws Exception {
        context.getSharedPreferences("fnaudio_remote_session", Context.MODE_PRIVATE).edit()
                .putString("snapshot", new JSONObject()
                        .put("schema", 1)
                        .put("saved_at_ms", System.currentTimeMillis())
                        .put("target_id", "dac:old-restore")
                        .put("target_name", "Old target")
                        .put("queue_json", "[{\"id\":\"old-track\"}]")
                        .put("index", 0)
                        .put("position_ms", 0)
                        .put("duration_ms", 0)
                        .put("playing", false)
                        .put("repeat_mode", 0)
                        .put("shuffle", false)
                        .put("generation", 1)
                        .put("engine_epoch", 1)
                        .toString())
                .commit();

        startRemoteTarget("dac:new-session", "New target");
        ListenableFuture<MediaController> future = new MediaController.Builder(
                context, new SessionToken(context, new ComponentName(context, PlaybackService.class)))
                .buildAsync();
        MediaController controller = future.get(5, TimeUnit.SECONDS);
        try {
            long deadline = System.currentTimeMillis() + 3000L;
            while (System.currentTimeMillis() < deadline
                    && !"test-track".equals(currentMediaId(controller))) {
                Thread.sleep(50L);
            }
            org.junit.Assert.assertEquals("test-track", currentMediaId(controller));
        } finally {
            InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> MediaController.releaseFuture(future));
        }
    }

    private void startRemoteTarget(String targetId, String targetName) {
        Intent intent = new Intent(context, PlaybackService.class)
                .setAction(PlaybackService.ACTION_REMOTE_ENABLE)
                .putExtra(PlaybackService.EXTRA_TARGET_ID, targetId)
                .putExtra(PlaybackService.EXTRA_TARGET_NAME, targetName)
                .putExtra(PlaybackService.EXTRA_QUEUE_JSON,
                        "[{\"id\":\"test-track\",\"title\":\"Test track\",\"artist\":\"fnAudio\",\"durationMs\":180000}]")
                .putExtra(PlaybackService.EXTRA_INDEX, 0)
                .putExtra(PlaybackService.EXTRA_DURATION_MS, 180000L)
                .putExtra(PlaybackService.EXTRA_PLAYING, false);
        ContextCompat.startForegroundService(context, intent);
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

    private static String currentMediaId(MediaController controller) throws Exception {
        androidx.media3.common.MediaItem item = onMain(controller::getCurrentMediaItem);
        return item == null ? "" : item.mediaId;
    }

    private void assertMediaNotification(String target) throws InterruptedException {
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        long deadline = System.currentTimeMillis() + 5000L;
        while (System.currentTimeMillis() < deadline) {
            for (StatusBarNotification entry : manager.getActiveNotifications()) {
                Notification notification = entry.getNotification();
                if (entry.getPackageName().equals(context.getPackageName())
                        && entry.getId() == NOTIFICATION_ID
                        && Notification.CATEGORY_TRANSPORT.equals(notification.category)
                        && notification.extras.getParcelable(Notification.EXTRA_MEDIA_SESSION) != null
                        && notification.contentIntent != null) {
                    return;
                }
            }
            Thread.sleep(100L);
        }
        StringBuilder found = new StringBuilder();
        for (StatusBarNotification entry : manager.getActiveNotifications()) {
            if (!entry.getPackageName().equals(context.getPackageName())) continue;
            Notification notification = entry.getNotification();
            found.append("id=").append(entry.getId())
                    .append(", category=").append(notification.category)
                    .append(", mediaToken=").append(notification.extras.getParcelable(Notification.EXTRA_MEDIA_SESSION) != null)
                    .append(", contentIntent=").append(notification.contentIntent != null)
                    .append("; ");
        }
        fail(target + " remote notification was not published as media: " + found);
    }

    private static void grantNotificationPermission() {
        if (Build.VERSION.SDK_INT < 33) return;
        try (ParcelFileDescriptor ignored = InstrumentationRegistry.getInstrumentation().getUiAutomation()
                .executeShellCommand("pm grant com.fnaudio.client " + Manifest.permission.POST_NOTIFICATIONS)) {
            // The test needs notification visibility, not a runtime permission dialog.
        } catch (Exception ignored) {
        }
    }
}
