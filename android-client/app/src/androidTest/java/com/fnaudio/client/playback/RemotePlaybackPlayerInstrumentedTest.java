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
    private final List<Long> requestTokens = new ArrayList<>();
    private RemotePlaybackPlayer player;

    @Before
    public void setUp() {
        runOnMain(() -> player = new RemotePlaybackPlayer(Looper.getMainLooper(), (action, positionMs, trackId, requestToken) -> {
            commands.add(action + ":" + (positionMs == null ? "" : positionMs) + ":" + (trackId == null ? "" : trackId));
            requestTokens.add(requestToken);
        }));
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
        // Remote mode is backend-authoritative: the local mirror advances only
        // after the server/SSE snapshot confirms the new queue index.
        invokeAndWait(() -> player.updateStatus(1, 0L, 180000L, true));
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
        assertEquals(Arrays.asList("play::", "seek:4500:", "load:0:track-2",
                "repeat::", "shuffle::", "pause::"), commands);
    }

    @Test
    public void invalidStateIsClampedAndEmptySeekIsIgnored() {
        runOnMain(() -> player.activate(Arrays.asList(
                new MediaItem.Builder().setMediaId("track-1").build()
        ), 99, Long.MAX_VALUE, Long.MAX_VALUE, false, 99, false));
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();

        long[] state = new long[2];
        runOnMain(() -> {
            state[0] = player.getCurrentPosition();
            state[1] = player.getDuration();
        });
        assertEquals(state[1], state[0]);
        int[] repeatMode = new int[1];
        runOnMain(() -> repeatMode[0] = player.getRepeatMode());
        assertEquals(Player.REPEAT_MODE_OFF, repeatMode[0]);

        runOnMain(() -> player.deactivate());
        invokeAndWait(() -> player.seekTo(0, 1000L));
        assertEquals(0, commands.size());
    }

    @Test
    public void staleSeekFailureCannotClearNewerSeek() {
        runOnMain(() -> player.activate(Arrays.asList(
                new MediaItem.Builder().setMediaId("track-1").build()
        ), 0, 0L, 180000L, false, Player.REPEAT_MODE_OFF, false));
        invokeAndWait(() -> player.seekTo(0, 1000L));
        long oldToken = requestTokens.get(0);
        invokeAndWait(() -> player.seekTo(0, 9000L));
        invokeAndWait(() -> player.clearPendingCommand("seek", oldToken));
        invokeAndWait(() -> player.updateStatus(0, 0L, 180000L, false));

        long[] position = new long[1];
        runOnMain(() -> position[0] = player.getCurrentPosition());
        assertEquals(9000L, position[0]);
    }

    private static void runOnMain(Runnable task) {
        InstrumentationRegistry.getInstrumentation().runOnMainSync(task);
    }

    private static void invokeAndWait(Runnable command) {
        runOnMain(command);
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
    }
}
