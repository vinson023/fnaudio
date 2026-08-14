package com.fnaudio.client.playback;

import android.os.Looper;

import androidx.media3.common.MediaItem;
import androidx.media3.common.Player;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

@RunWith(AndroidJUnit4.class)
public final class RemotePlaybackPlayerInstrumentedTest {
    private final List<String> commands = new ArrayList<>();
    private RemotePlaybackPlayer player;

    @Before
    public void setUp() {
        runOnMain(() -> player = new RemotePlaybackPlayer(Looper.getMainLooper(), (action, positionMs) ->
                commands.add(action + ":" + (positionMs == null ? "" : positionMs))));
    }

    @After
    public void tearDown() {
        if (player != null) runOnMain(() -> player.release());
    }

    @Test
    public void remoteModeMirrorsQueueAndForwardsMediaSessionCommands() {
        runOnMain(() -> player.activate(Arrays.asList(
                new MediaItem.Builder().setMediaId("track-1").build(),
                new MediaItem.Builder().setMediaId("track-2").build()
        ), 0, 1200L, 180000L, false, Player.REPEAT_MODE_OFF, false));
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();

        invokeAndWait(() -> player.play());
        invokeAndWait(() -> player.seekTo(0, 4500L));
        invokeAndWait(() -> player.seekToNextMediaItem());
        invokeAndWait(() -> player.setRepeatMode(Player.REPEAT_MODE_ONE));
        invokeAndWait(() -> player.setShuffleModeEnabled(true));
        invokeAndWait(() -> player.pause());

        int[] mediaCount = new int[1];
        String[] currentMediaId = new String[1];
        runOnMain(() -> {
            mediaCount[0] = player.getMediaItemCount();
            currentMediaId[0] = player.getCurrentMediaItem().mediaId;
        });
        assertEquals(2, mediaCount[0]);
        assertEquals("track-2", currentMediaId[0]);
        assertTrue("commands=" + commands, commands.contains("play:"));
        assertTrue("commands=" + commands, commands.contains("seek:4500"));
        assertTrue("commands=" + commands, commands.contains("next:"));
        assertTrue("commands=" + commands, commands.contains("repeat:"));
        assertTrue("commands=" + commands, commands.contains("shuffle:"));
        assertTrue("commands=" + commands, commands.contains("pause:"));
    }

    private static void runOnMain(Runnable task) {
        InstrumentationRegistry.getInstrumentation().runOnMainSync(task);
    }

    private static void invokeAndWait(Runnable command) {
        runOnMain(command);
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
    }
}
