package com.fnaudio.client.playback;

import androidx.annotation.Nullable;

import com.fnaudio.client.data.ConnectionProfile;

public final class PlaybackRuntimeConfig {
    private static volatile ConnectionProfile activeProfile;

    private PlaybackRuntimeConfig() {
    }

    public static synchronized boolean activate(ConnectionProfile profile) {
        boolean changed = activeProfile != null && !activeProfile.id.equals(profile.id);
        activeProfile = profile;
        return changed;
    }

    @Nullable
    public static ConnectionProfile activeProfile() {
        return activeProfile;
    }
}
