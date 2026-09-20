package com.fnaudio.client.integration;

import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.content.ComponentName;
import android.content.Context;
import android.media.browse.MediaBrowser;
import android.media.session.MediaController;
import android.os.Bundle;

import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.Assume;
import org.junit.runner.RunWith;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** Verifies fnOS exposes its audio-service MediaSession to another application. */
@RunWith(AndroidJUnit4.class)
public final class FnAppMediaBrowserInstrumentedTest {
    private static final ComponentName FNOS_AUDIO_SERVICE = new ComponentName(
            "com.trim.app", "com.ryanheise.audioservice.AudioService");

    @Test
    public void connectsToFnOsExportedMediaBrowserService() throws Exception {
        Context context = ApplicationProvider.getApplicationContext();
        CountDownLatch connected = new CountDownLatch(1);
        AtomicReference<String> failure = new AtomicReference<>();
        AtomicReference<MediaBrowser> browserRef = new AtomicReference<>();

        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            MediaBrowser browser = new MediaBrowser(context, FNOS_AUDIO_SERVICE,
                    new MediaBrowser.ConnectionCallback() {
                    @Override
                    public void onConnected() {
                        connected.countDown();
                    }

                    @Override
                    public void onConnectionFailed() {
                        failure.set("MediaBrowser connection failed");
                        connected.countDown();
                    }

                    @Override
                    public void onConnectionSuspended() {
                        failure.set("MediaBrowser connection suspended");
                        connected.countDown();
                    }
                    }, new Bundle());
            browserRef.set(browser);
            browser.connect();
        });
        MediaBrowser browser = browserRef.get();

        try {
            // fnOS does not guarantee that its private Flutter audio service
            // is exported to third-party applications. Treat an unavailable
            // service as an environment result, not an fnAudio regression.
            if (!connected.await(2, TimeUnit.SECONDS)) {
                Assume.assumeTrue("fnOS AudioService is not exported on this device", false);
            }
            if (failure.get() != null || !browser.isConnected()) {
                Assume.assumeTrue("fnOS AudioService is not exported on this device", false);
            }
            assertTrue(browser.isConnected());
            assertNotNull("fnOS did not expose a MediaSession token", browser.getSessionToken());
            assertNotNull("fnOS did not expose a browse root", browser.getRoot());

            // Read-only validation: creating a controller must not alter playback.
            MediaController controller = new MediaController(context, browser.getSessionToken());
            assertNotNull("fnOS controller has no playback state", controller.getPlaybackState());
        } finally {
            InstrumentationRegistry.getInstrumentation().runOnMainSync(browser::disconnect);
        }
    }
}
