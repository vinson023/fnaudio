package com.fnaudio.client.playback;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.ParcelFileDescriptor;
import android.service.notification.StatusBarNotification;

import androidx.core.content.ContextCompat;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import static org.junit.Assert.fail;

/** Verifies that server-side playback still owns a real Android media notification. */
@RunWith(AndroidJUnit4.class)
public final class PlaybackServiceRemoteNotificationInstrumentedTest {
    private static final int NOTIFICATION_ID = 7011;
    private Context context;

    @Before
    public void setUp() {
        context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        grantNotificationPermission();
    }

    @After
    public void tearDown() {
        context.stopService(new Intent(context, PlaybackService.class));
    }

    @Test
    public void dacAndDlnaTargetsExposeMediaSessionNotification() throws Exception {
        startRemoteTarget("dac:usb-test", "USB DAC");
        assertMediaNotification("DAC");

        startRemoteTarget("upnp:renderer-test", "DLNA Renderer");
        assertMediaNotification("DLNA");
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
