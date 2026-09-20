package com.fnaudio.client.playback;

import com.fnaudio.client.data.ConnectionProfile;

import org.junit.After;
import org.junit.Test;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public final class PlaybackRuntimeConfigTest {
    @After
    public void tearDown() {
        PlaybackRuntimeConfig.activate(null);
    }

    @Test
    public void sameProfileIdButNewEndpointRequiresServiceRestart() {
        ConnectionProfile original = profile("nas.example", 5666, "token-a");
        ConnectionProfile moved = profile("198.51.100.7", 5666, "token-a");

        assertFalse(PlaybackRuntimeConfig.activate(original));
        assertTrue(PlaybackRuntimeConfig.activate(moved));
    }

    @Test
    public void tokenRotationRequiresServiceRestart() {
        ConnectionProfile original = profile("nas.example", 5666, "token-a");
        ConnectionProfile rotated = profile("nas.example", 5666, "token-b");

        assertFalse(PlaybackRuntimeConfig.activate(original));
        assertTrue(PlaybackRuntimeConfig.activate(rotated));
    }

    @Test
    public void unchangedRuntimeConnectionDoesNotRequireServiceRestart() {
        ConnectionProfile original = profile("nas.example", 5666, "token-a");
        ConnectionProfile same = profile("nas.example", 5666, "token-a");

        assertFalse(PlaybackRuntimeConfig.activate(original));
        assertFalse(PlaybackRuntimeConfig.activate(same));
    }

    private static ConnectionProfile profile(String host, int port, String token) {
        return new ConnectionProfile(
                "runtime-test", "Test NAS", host, port, false, false, "",
                "admin", "password", token, "", false, false, "public", 100L);
    }
}
